"""pygame renderer: 640x480 logical screen laid out like the original, scaled to the window."""
from __future__ import annotations

import math
import os

import pygame

from .world import ROOM
from .bgi import BGI
from .hud import Hud
from . import anim, view3d
from .hands import Hands
from .face import Face

W, H = 640, 480
TILE = 40
MAP_PX = ROOM * TILE          # 400
MAP_BOX = (480, 276)          # the inside of the panel's Map box (hud.dmap), 100 x 100
STEP_MS = 140                 # FPS mode: how long a step or a turn takes to glide

# the EGA palette as the game shows it (see bgi.EGA)
from .bgi import EGA  # noqa: E402

# sprite kinds as the renderer keys them -> the pack's sprites/<folder>
SPRITE_DIRS = {'floor': 'floors', 'wall': 'walls', 'extra': 'decos', 'enemy': 'creatures', 'object': 'items',
               'spell': 'spells'}


class Sprites:
    """The pack's pictures: sprites/<kind>/<id>.png, sprites/bag/<id>.png (bagdraw()'s whole 40x40
    cells, grey background included), sprites/heroes/<class>.png and sprites/gold.png."""

    def __init__(self, pack):
        self.images: dict[tuple[str, int], pygame.Surface] = {}
        self.bag: dict[int, pygame.Surface] = {}
        self.names: dict[tuple[str, int], str] = pack.names()
        self.hero: dict[str, pygame.Surface] = {}
        self.gold = None
        for kind, folder in SPRITE_DIRS.items():
            for n, path in self._pngs(pack.sprite_dir(folder)):
                self.images[(kind, int(n))] = pygame.image.load(path).convert_alpha()
        for n, path in self._pngs(pack.sprite_dir('heroes')):
            self.hero[n] = pygame.image.load(path).convert_alpha()
        for n, path in self._pngs(pack.sprite_dir('bag')):
            self.bag[int(n)] = pygame.image.load(path).convert()
        gold = pack.path('sprites', 'gold.png')
        if os.path.exists(gold):
            self.gold = pygame.image.load(gold).convert_alpha()

    @staticmethod
    def _pngs(folder):
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith('.png'):
                    yield f[:-4], os.path.join(folder, f)

    def get(self, kind: str, n: int):
        return self.images.get((kind, n))


class Renderer:
    def __init__(self, window: pygame.Surface, source=None, pack=None):
        self.window = window
        self.screen = pygame.Surface((W, H))
        self.hud = Hud(self.screen, source)
        self.bgi = BGI(self.screen, source)
        self.bgi._fonts = self.hud.g._fonts
        self.pack = pack
        self.sprites = Sprites(pack)
        self.anchor = None             # the map square the running animation plays at (FPS mode)

    # ── tiles ─────────────────────────────────────────────────────────────────
    def draw_tile(self, surf, px, py, q, enemy=None):
        s = self.sprites
        surf.fill((0, 0, 0), (px, py, TILE, TILE))
        for kind, val, cond in (('floor', q.floor, True), ('extra', q.deco, q.deco), ('wall', q.wall, q.wall)):
            if cond:
                img = s.get(kind, val)
                if img:
                    surf.blit(img, (px, py))
                elif kind == 'wall':
                    pygame.draw.rect(surf, EGA[8], (px + 2, py + 2, TILE - 4, TILE - 4))
        if q.gold > 0 and s.gold:
            surf.blit(s.gold, (px, py))
        if q.item:
            img = s.get('object', q.item)
            if img:
                surf.blit(img, (px, py))
            else:
                pygame.draw.circle(surf, EGA[14], (px + 20, py + 20), 6)
        if q.mon and not self.pack.trait(q.mon, 'invisible'):
            img = s.get('enemy', q.mon)
            if img:
                surf.blit(img, (px, py))
            else:
                pygame.draw.circle(surf, EGA[12] if q.mon > 0 else EGA[11], (px + 20, py + 20), 12)

    def draw_hero(self, scr, game, hx, hy):
        """guy2(), ported call for call (engine.anim.draw_guy2), at pixel position (hx, hy)."""
        p, st = game.player, game.status
        self.bgi.s = scr
        anim.draw_guy2(self.bgi, hx // TILE + 1, hy // TILE + 1, p.hero.type, p.hero.invisible, p.hero.poisoned,
                       st.killer, st.powboost, st.Shield, st.fShield,
                       look=self.pack.classes.get(p.hero.type, {}).get('look'))

    # ── the original's animations ─────────────────────────────────────────────
    def play(self, game, gen, fast=False, redraw=True, raw=False):
        """Run an animation generator (engine.anim) on top of the current frame, blocking, as the
        original does. Each yielded value is a delay() in ms; time is kept exactly, and frames are
        only shown when there's time (or at least every 1/60 s)."""
        if fast:
            for _ in gen:
                pass
            return
        three_d = self.in_3d(game) and not raw      # raw: drawn on the screen as it is (a wipe)
        while three_d and self.gliding(game):               # a step or a turn finishes before the animation
            self.draw(game)
            pygame.event.pump()
            pygame.time.wait(10)
        if redraw:
            self.draw(game, present=False, flat=three_d)
        if three_d:
            # the animation draws on the map from above, out of sight; what it changes is carried
            # into the 3D view (see compose_3d)
            if redraw or getattr(self, '_anim_base', None) is None:
                self._anim_base = self.screen.copy()
            view = pygame.Surface((MAP_PX, MAP_PX))
            self.draw_3d(game, view)
            self._anim_view = view
            if redraw:
                self.present(self.compose_3d(game))
        elif redraw:
            self.present()
        self.bgi.s = self.screen
        clock = pygame.time.get_ticks
        target = shown = clock()
        for ms in gen:
            target += max(0, ms)
            now = clock()
            if now < target or now - shown >= 16:
                self.present(self.compose_3d(game) if three_d else None)
                shown = clock()
            pygame.event.pump()                  # keys pressed meanwhile stay queued, like the BIOS buffer
            wait = target - clock()
            if wait > 0:
                pygame.time.wait(wait)
        self.present(self.compose_3d(game) if three_d else None)

    def hand(self, game, scr):
        """The weapon in view (engine.hands), over the view and under the combat log."""
        if not hasattr(self, 'hands'):
            self.hands = Hands(self.pack, self.sprites)
        self.hands.draw(game, scr.subsurface((0, 0, MAP_PX, MAP_PX)), pygame.time.get_ticks())

    def compose_3d(self, game) -> pygame.Surface:
        out = self._compose_3d(game)
        self.hand(game, out)
        return out

    def _compose_3d(self, game) -> pygame.Surface:
        """An animation frame in FPS mode: the 3D view, with what the animation drew on the map moved
        to where it happens: around a creature's square, at that square in the view; around the
        hero, over the whole view; anywhere else (a flash of the screen), as it is."""
        out = self.screen.copy()
        out.blit(self._anim_view, (0, 0))
        area = (0, 0, MAP_PX, MAP_PX)
        drawn, base = self.screen.subsurface(area), self._anim_base.subsurface(area)
        same = pygame.mask.from_threshold(drawn, (0, 0, 0, 255), (1, 1, 1, 255), base)
        same.invert()
        if not same.count():
            return out
        colours = pygame.Surface((MAP_PX, MAP_PX), pygame.SRCALPHA)
        colours.blit(drawn, (0, 0))
        layer = pygame.Surface((MAP_PX, MAP_PX), pygame.SRCALPHA)
        same.to_surface(layer, setsurface=colours, unsetcolor=(0, 0, 0, 0))
        at = self.anchor
        if at is None:
            out.blit(layer, (0, 0))
            return out
        ox, oy = game.world.origin
        ax, ay = (at[0] - ox) * TILE, (at[1] - oy) * TILE
        crop = pygame.Surface((3 * TILE, 3 * TILE), pygame.SRCALPHA)
        crop.fill((0, 0, 0, 0))
        crop.blit(layer, (TILE - ax, TILE - ay))
        p = game.player
        if tuple(at) == (p.X, p.Y):
            out.blit(pygame.transform.scale(crop, (MAP_PX, MAP_PX)), (0, 0))
            return out
        where = self.v3d.project(self.camera(game), at[0] + 0.5, at[1] + 0.5)
        if where is None:
            return out
        k = MAP_PX / view3d.RES
        x, y, size = where[0] * k, where[1] * k, where[2] * k
        n = max(3, int(3 * size))
        big = pygame.transform.scale(crop, (n, n))
        view = out.subsurface(area)
        view.blit(big, (int(x - n / 2), int(y - size / 2 - n / 2)))
        return out

    def wait(self, surface, ms, fast=False):
        """delay(ms) while an original key loop owns the screen: show its surface, then wait."""
        if fast:
            return
        self.screen.blit(surface, (0, 0))
        self.present()
        pygame.event.pump()
        pygame.time.wait(max(0, ms))

    def wait_talk(self, game, text, fast=False):
        """talk()'s getch loop: the message stays in the strip until Space is pressed."""
        if fast:
            return
        from .ui import TalkBox
        box = TalkBox(text)
        clock = pygame.time.Clock()
        while game.running:
            self.draw(game, present=False)
            box.draw(self, self.screen)
            self.present()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    game.running = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                    return
            clock.tick(30)

    # ── frame ─────────────────────────────────────────────────────────────────
    def draw(self, game, present=True, flat=False):
        """flat: the map from above even in FPS mode."""
        self.game = game
        scr = self.screen
        scr.fill((0, 0, 0))
        if game.overlay and game.overlay.covers_map or not game.world.grid:
            if game.overlay:
                game.overlay.draw(self, scr)
            if present:
                self.present()
            return
        three_d = self.in_3d(game) and not flat
        if three_d:
            self.draw_3d(game, scr)
            self.hand(game, scr)
        else:
            self.draw_map(game, scr)
        self.draw_combat_log(game, scr, three_d)
        self.hud.draw(game)
        if self.in_3d(game):
            if getattr(game, 'minimap', True):
                self.map_box(game, scr)
            if not hasattr(self, 'face'):
                self.face = Face(self.pack, self.sprites)
            self.face.draw(game, scr)                    # the hero's bust, right of the coins
        self.draw_message(scr, game)
        if game.overlay:
            game.overlay.draw(self, scr)
        if present:
            self.present()

    def draw_map(self, game, scr):
        """The screen from above, as the original shows it."""
        w, p = game.world, game.player
        ox, oy = w.origin
        for x, y in w.room_tiles():
            self.draw_tile(scr, (x - ox) * TILE, (y - oy) * TILE, w.grid[x][y])
        hx, hy = (p.X - ox) * TILE, (p.Y - oy) * TILE
        self.draw_hero(scr, game, hx, hy)
        t = game.target
        if t is not None and t in w.enemies:
            pygame.draw.rect(scr, EGA[12], ((t.x - ox) * TILE, (t.y - oy) * TILE, TILE, TILE), 1)
        if game.cursor is not None:
            cx, cy = game.cursor
            pygame.draw.rect(scr, EGA[14], ((cx - ox) * TILE, (cy - oy) * TILE, TILE, TILE), 2)

    # ── FPS mode ──────────────────────────────────────────────────────────────
    @staticmethod
    def in_3d(game) -> bool:
        """The 3D view shows unless the game asks for a square on the map (a target, a spell's aim), no
        level is loaded (the title), or a screen covers the map (the bag, a story)."""
        return (getattr(game, 'view3d', False) and game.cursor is None and bool(game.world.grid)
                and not (game.overlay and game.overlay.covers_map))

    def scene3d(self, game) -> view3d.Scene:
        w, pack = game.world, self.pack
        key = (id(w.grid), w.level)
        if getattr(self, '_scene_key', None) != key:
            s = self.sprites
            kinds = {'floor': 'floor', 'wall': 'wall', 'deco': 'extra', 'item': 'object', 'mon': 'enemy'}

            def picture(kind, v):
                return s.gold if kind == 'gold' else s.get(kinds[kind], v)

            def square(x, y):
                if not w.in_map(x, y):
                    return None
                q = w.grid[x][y]
                return q.floor, q.wall, q.item, q.mon, q.gold, q.deco
            items = {v: (r.get('type', ''), r.get('view3d')) for v, r in pack.items.items()}
            scene = view3d.Scene(pack.tiles, items, picture, square, hidden=lambda m: pack.trait(m, 'invisible'))
            meta, dflt = game.events.meta, pack.quest.get('view3d', {})
            scene.sky = meta(w.level, 'SKY_3D', dflt.get('sky', view3d.Scene.sky))
            scene.fog = meta(w.level, 'FOG_3D', dflt.get('fog', scene.sky))
            scene.range = meta(w.level, 'RANGE_3D', dflt.get('range', view3d.Scene.range))
            self._scene, self._scene_key = scene, key
        return self._scene

    def camera(self, game, snap=False):
        """Where the eye is: it glides a step or a quarter turn over STEP_MS, then stays."""
        p = game.player
        goal = (p.X + 0.5, p.Y + 0.5, view3d.facing_angle(game.facing))
        now = pygame.time.get_ticks()
        cam = getattr(self, '_cam', None)
        if cam is None or snap or game.fast:
            cam = self._cam = {'from': goal, 'goal': goal, 't0': now}
        if cam['goal'] != goal:
            here = self._pose(cam, now)
            far = abs(goal[0] - here[0]) + abs(goal[1] - here[1]) > 1.5
            cam.update({'from': goal if far else here, 'goal': goal, 't0': now})
        return self._pose(cam, now)

    @staticmethod
    def _pose(cam, now):
        t = (now - cam['t0']) / STEP_MS
        if t >= 1:
            return cam['goal']            # arrived: exactly the goal (west is +pi there, -pi on the way)
        (x0, y0, a0), (x1, y1, a1) = cam['from'], cam['goal']
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, a0 + da * t

    def gliding(self, game) -> bool:
        """Is the eye still on its way to where the hero now is?"""
        return self.camera(game) != self._cam['goal']

    def draw_3d(self, game, scr, snap=False):
        if not hasattr(self, 'v3d'):
            self.v3d = view3d.View3D()
        frame = self.v3d.render(self.scene3d(game), self.camera(game, snap))
        k = MAP_PX // view3d.RES
        scr.blit(pygame.transform.scale(frame, (MAP_PX, MAP_PX)), (0, 0))
        t = game.target
        if t is not None and t in game.world.enemies:
            r = self.v3d.sprite_rects.get((t.x, t.y))
            if r:
                pygame.draw.rect(scr, EGA[12], (r.x * k, r.y * k, r.w * k, r.h * k), 1)
        # the compass (the screen from above is in the panel's Map box: map_box)
        self.btext(scr, view3d.FACING_NAMES[game.facing % 4], (MAP_PX // 2, 2), 15, style=(8, 1), center=True)

    def map_box(self, game, scr):
        """FPS mode: the panel's Map box shows the current screen from above, with the hero's facing,
        instead of the level map (M switches between them)."""
        n = 100
        w, p, st, h, t = game.world, game.player, game.status, game.player.hero, game.target
        key = (tuple((q.floor, q.wall, q.item, q.mon, q.gold, q.deco) for q in
                     (w.grid[x][y] for x, y in w.room_tiles())), p.X, p.Y, p.hero.type, h.invisible,
               h.poisoned, st.killer, st.powboost, st.Shield, st.fShield, t and (t.x, t.y))
        if key != getattr(self, '_mini_key', None):
            small = pygame.Surface((MAP_PX, MAP_PX))
            self.draw_map(game, small)
            self._mini, self._mini_key = pygame.transform.scale(small, (n, n)), key
        x0, y0 = MAP_BOX
        scr.blit(self._mini, (x0, y0))
        ox, oy = w.origin
        cx = x0 + (p.X - ox) * n // 10 + n // 20
        cy = y0 + (p.Y - oy) * n // 10 + n // 20
        dx, dy = view3d.FACINGS[game.facing % 4]
        pygame.draw.line(scr, EGA[14], (cx, cy), (cx + dx * 7, cy + dy * 7), 2)

    # ── the combat log (Deluxe) ───────────────────────────────────────────────
    LOG_LINES = 6
    FLOAT_MS = 900

    def draw_combat_log(self, game, scr, three_d):
        """The last lines of the combat log over the bottom of the map, and in FPS mode the damage
        numbers rising off the squares that took it."""
        if not getattr(game, 'combat_log', False):
            return
        g = self.bgi
        g.s = scr
        lines = [ln for ln in game.log_lines if ln[2] == game.log_key][-self.LOG_LINES:]
        g.settextstyle(0, 0, 1)
        y = MAP_PX - 4 - 10 * len(lines)
        for text, colour, _ in lines:
            scr.fill((0, 0, 0), (2, y - 1, g.textwidth(text) + 4, 10))
            g.setcolor(colour)
            g.outtextxy(4, y, text)
            y += 10
        if not three_d:                             # the rising numbers are FPS mode's; from above, the log
            game.floaters = [f for f in game.floaters if f.get('key') == game.log_key]
            return
        now = pygame.time.get_ticks()
        p = game.player
        g.settextstyle(0, 0, 2)
        keep, last = [], {}
        for f in game.floaters:
            if f.get('key') != game.log_key:        # a new key: the last action's numbers are done
                continue
            if f['t0'] is None:                     # one after another off the same square
                f['t0'] = max(now, last.get(f['at'], now - 150) + 150)
            last[f['at']] = f['t0']
            age = now - f['t0']
            if age > self.FLOAT_MS:
                continue
            keep.append(f)
            if age < 0:
                continue
            x, y = f['at']
            rise = age * 30 // self.FLOAT_MS
            if (x, y) == (p.X, p.Y):
                sx, sy = MAP_PX // 2, MAP_PX - 60 - rise
            else:
                where = self.v3d.project(self.camera(game), x + 0.5, y + 0.5)
                if where is None:
                    continue
                k = MAP_PX / view3d.RES
                sx, sy = int(where[0] * k), int((where[1] - where[2]) * k) - 8 - rise
            tw = g.textwidth(f['text'])
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):     # a black edge, so it reads on any ground
                g.setcolor(0)
                g.outtextxy(sx - tw // 2 + dx, sy + dy, f['text'])
            g.setcolor(f['colour'])
            g.outtextxy(sx - tw // 2, sy, f['text'])
        game.floaters = keep

    def draw_message(self, scr, game):
        """The bottom strip shows this turn's messages, or the potion belt when there are none."""
        if game.messages:
            self.hud.draw_messages([(m, getattr(m, 'colour', 15)) for m in game.messages])
        else:
            self.hud.draw_belt(game.player, self.pack.extra_potions() if self.pack else None)

    def btext(self, scr, s, pos, colour: int, style=(8, 1), center=False):
        """Text in one of the game's BGI fonts: style = (settextstyle font, size), colour = EGA index."""
        g = self.bgi
        g.s = scr
        g.settextstyle(style[0], 0, style[1])
        g.setcolor(colour)
        x, y = pos
        if center:
            x -= g.textwidth(s) // 2
        g.outtextxy(x, y, s)

    def bwidth(self, s: str, style=(8, 1)) -> int:
        self.bgi.settextstyle(style[0], 0, style[1])
        return self.bgi.textwidth(s)

    def bwrap(self, s: str, width: int, style=(8, 1)) -> list[str]:
        out = []
        for para in s.split('\n'):
            line = ''
            for word in para.split(' '):
                t = (line + ' ' + word).strip()
                if self.bwidth(t, style) > width and line:
                    out.append(line)
                    line = word
                else:
                    line = t
            out.append(line)
        return out

    def present(self, surface=None):
        surface = self.screen if surface is None else surface
        ww, wh = self.window.get_size()
        scale = max(1, min(ww // W, wh // H))
        if ww / W >= 1 and wh / H >= 1 and scale * W <= ww:
            scaled = pygame.transform.scale(surface, (W * scale, H * scale))
        else:
            f = min(ww / W, wh / H)
            scaled = pygame.transform.smoothscale(surface, (int(W * f), int(H * f)))
        self.window.fill((0, 0, 0))
        self.window.blit(scaled, ((ww - scaled.get_width()) // 2, (wh - scaled.get_height()) // 2))
        pygame.display.flip()
