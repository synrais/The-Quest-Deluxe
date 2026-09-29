"""pygame renderer: 640x480 logical screen laid out like the original, scaled to the window."""
from __future__ import annotations

import os

import pygame

from .world import ROOM
from .bgi import BGI
from .hud import Hud
from . import anim

W, H = 640, 480
TILE = 40
MAP_PX = ROOM * TILE          # 400

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
        """guy2(), ported call for call (deluxe.anim.draw_guy2), at pixel position (hx, hy)."""
        p, st = game.player, game.status
        self.bgi.s = scr
        anim.draw_guy2(self.bgi, hx // TILE + 1, hy // TILE + 1, p.hero.type, p.hero.invisible, p.hero.poisoned,
                       st.killer, st.powboost, st.Shield, st.fShield,
                       look=self.pack.classes.get(p.hero.type, {}).get('look'))

    # ── the original's animations ─────────────────────────────────────────────
    def play(self, game, gen, fast=False, redraw=True):
        """Run an animation generator (deluxe.anim) on top of the current frame, blocking, as the
        original does. Each yielded value is a delay() in ms; time is kept exactly, and frames are
        only shown when there's time (or at least every 1/60 s)."""
        if fast:
            for _ in gen:
                pass
            return
        if redraw:
            self.draw(game)
        self.bgi.s = self.screen
        clock = pygame.time.get_ticks
        target = shown = clock()
        for ms in gen:
            target += max(0, ms)
            now = clock()
            if now < target or now - shown >= 16:
                self.present()
                shown = clock()
            pygame.event.pump()                  # keys pressed meanwhile stay queued, like the BIOS buffer
            wait = target - clock()
            if wait > 0:
                pygame.time.wait(wait)
        self.present()

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
    def draw(self, game, present=True):
        self.game = game
        scr = self.screen
        scr.fill((0, 0, 0))
        if game.overlay and game.overlay.covers_map or not game.world.grid:
            if game.overlay:
                game.overlay.draw(self, scr)
            if present:
                self.present()
            return
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

        self.hud.draw(game)
        self.draw_message(scr, game)
        if game.overlay:
            game.overlay.draw(self, scr)
        if present:
            self.present()

    def draw_message(self, scr, game):
        """The bottom strip shows this turn's messages, or the potion belt when there are none."""
        if game.messages:
            self.hud.draw_messages([(m, getattr(m, 'colour', 15)) for m in game.messages])
        else:
            self.hud.draw_belt(game.player.inv)

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

    def present(self):
        ww, wh = self.window.get_size()
        scale = max(1, min(ww // W, wh // H))
        if ww / W >= 1 and wh / H >= 1 and scale * W <= ww:
            scaled = pygame.transform.scale(self.screen, (W * scale, H * scale))
        else:
            f = min(ww / W, wh / H)
            scaled = pygame.transform.smoothscale(self.screen, (int(W * f), int(H * f)))
        self.window.fill((0, 0, 0))
        self.window.blit(scaled, ((ww - scaled.get_width()) // 2, (wh - scaled.get_height()) // 2))
        pygame.display.flip()
