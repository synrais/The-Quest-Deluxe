"""pygame renderer: 640x480 logical screen laid out like the original, scaled to the window."""
from __future__ import annotations

import os
import re

import pygame

from .formats import ROOT
from .world import ROOM
from .bgi import BGI
from .hud import Hud
from . import anim

SPRITES_DIR = os.path.join(ROOT, 'sprites')
W, H = 640, 480
TILE = 40
MAP_PX = ROOM * TILE          # 400

# the EGA palette as the game shows it (see bgi.EGA)
from .bgi import EGA  # noqa: E402

_SPRITE_RE = re.compile(r'^(floor|wall|enemy|object|extra|spell)_(-?\d+)_?(?:\[(.*)\])?$')


class Sprites:
    def __init__(self):
        self.images: dict[tuple[str, int], pygame.Surface] = {}
        self.names: dict[tuple[str, int], str] = {}
        self.hero: dict[str, pygame.Surface] = {}
        self.gold = None
        if not os.path.isdir(SPRITES_DIR):
            return
        for f in os.listdir(SPRITES_DIR):
            if not f.lower().endswith('.png'):
                continue
            stem = f[:-4]
            path = os.path.join(SPRITES_DIR, f)
            m = _SPRITE_RE.match(stem)
            if m:
                key = (m.group(1), int(m.group(2)))
                self.images[key] = pygame.image.load(path).convert_alpha()
                self.names[key] = m.group(3) or stem
            elif stem.startswith('hero_'):
                self.hero[stem[5:]] = pygame.image.load(path).convert_alpha()
            elif stem == 'gold':
                self.gold = pygame.image.load(path).convert_alpha()

    def get(self, kind: str, n: int):
        return self.images.get((kind, n))


class Renderer:
    def __init__(self, window: pygame.Surface, source=None):
        self.window = window
        self.screen = pygame.Surface((W, H))
        self.hud = Hud(self.screen, source)
        self.bgi = BGI(self.screen, source)
        self.bgi._fonts = self.hud.g._fonts
        self.sprites = Sprites()

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
        if q.mon and q.mon != 22:                     # 22 = invisible wraith
            img = s.get('enemy', q.mon)
            if img:
                surf.blit(img, (px, py))
            else:
                pygame.draw.circle(surf, EGA[12] if q.mon > 0 else EGA[11], (px + 20, py + 20), 12)

    def draw_hero(self, scr, game, hx, hy):
        """guy2(), ported call for call (quest2.anim.draw_guy2), at pixel position (hx, hy)."""
        p, st = game.player, game.status
        self.bgi.s = scr
        anim.draw_guy2(self.bgi, hx // TILE + 1, hy // TILE + 1, p.hero.type, p.hero.invisible, p.hero.poisoned,
                       st.killer, st.powboost, st.Shield, st.fShield)

    # ── the original's animations ─────────────────────────────────────────────
    def play(self, game, gen, fast=False, redraw=True):
        """Run an animation generator (quest2.anim) on top of the current frame, blocking, as the
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

    # ── frame ─────────────────────────────────────────────────────────────────
    def draw(self, game):
        self.game = game
        scr = self.screen
        scr.fill((0, 0, 0))
        if game.overlay and game.overlay.covers_map or not game.world.grid:
            if game.overlay:
                game.overlay.draw(self, scr)
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
