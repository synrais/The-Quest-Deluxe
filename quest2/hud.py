"""The right-hand panel and bottom strip, ported call-for-call from the original:
stats() (frame), dlife2() (life orb), dmana2() (mana triangle), dcoins()/dmoney() (gold),
dkeys2() (keys), dmap() (automap) and dpotions2() (potion belt).

Everything is drawn with the BGI emulation in bgi.py, so shapes, colours and fonts match
TheQuest.exe. The slow parts are cached and only redrawn when what they show changes.
"""
from __future__ import annotations

import math

import pygame

from .bgi import BGI

# dcoins(): five stacks of ten coins, each a black-outlined rectangle flood-filled yellow.
# Recovered by tracing the function's BGI calls: (x1, y1, x2, y2, seed_x, seed_y).
COIN_STACKS = [
    [(454, 170, 464, 173, 456, 171), (456, 170, 466, 167, 457, 168), (455, 167, 465, 164, 456, 165),
     (453, 164, 463, 161, 457, 162), (454, 161, 464, 158, 456, 159), (456, 158, 466, 155, 457, 156),
     (457, 155, 467, 152, 459, 153), (458, 152, 468, 149, 459, 150), (456, 149, 466, 146, 457, 147),
     (455, 146, 465, 143, 457, 145)],
    [(475, 170, 485, 173, 476, 171), (476, 170, 486, 167, 480, 168), (477, 167, 487, 164, 480, 165),
     (475, 164, 485, 161, 476, 162), (475, 161, 485, 158, 476, 159), (475, 158, 485, 155, 476, 156),
     (474, 155, 484, 152, 476, 153), (474, 152, 484, 149, 477, 150), (475, 149, 485, 146, 477, 147),
     (474, 146, 484, 143, 477, 145)],
    [(495, 170, 505, 173, 496, 171), (495, 170, 505, 167, 497, 168), (495, 167, 505, 164, 498, 165),
     (494, 164, 504, 161, 497, 162), (493, 161, 503, 158, 498, 159), (494, 158, 504, 155, 497, 156),
     (495, 155, 505, 152, 497, 153), (496, 152, 506, 149, 497, 150), (495, 149, 505, 146, 497, 147),
     (495, 146, 505, 143, 497, 145)],
    [(515, 170, 525, 173, 516, 171), (515, 170, 525, 167, 517, 168), (514, 167, 524, 164, 518, 165),
     (515, 164, 525, 161, 517, 162), (515, 161, 525, 158, 518, 159), (515, 158, 525, 155, 517, 156),
     (515, 155, 525, 152, 517, 153), (516, 152, 526, 149, 518, 150), (515, 149, 525, 146, 517, 147),
     (515, 146, 525, 143, 518, 145)],
    [(535, 170, 545, 173, 536, 171), (535, 170, 545, 167, 537, 168), (535, 167, 545, 164, 538, 165),
     (535, 164, 545, 161, 537, 162), (535, 161, 545, 158, 538, 159), (535, 158, 545, 155, 537, 156),
     (535, 155, 545, 152, 537, 153), (535, 152, 545, 149, 538, 150), (535, 149, 545, 146, 537, 147),
     (535, 146, 545, 143, 538, 145)],
]

# dkeys2(): (inventory field, colour when held, x offset, y offset). Grey (8) when missing.
KEYS = [('bkey', 1, -30, -15), ('rkey', 4, 42, -40), ('ykey', 14, 116, -15)]

# dpotions2(): liquid colour for potions 1-8, and which labels are drawn in black.
POTION_COLOURS = [12, 4, 5, 1, 14, 15, 3, 0]
DARK_LABELS = (5, 6, 7)


class Hud:
    def __init__(self, screen: pygame.Surface, source):
        self.screen = screen
        self.panel = pygame.Surface(screen.get_size())
        self.g = BGI(self.panel, source)
        self._panel_key = None
        self._map_key = None
        self._map = pygame.Surface((100, 100))
        self._belt_key = None
        self._belt = pygame.Surface((640, 70))

    # ── panel ───────────────────────────────────────────────────────────────
    def draw(self, game):
        key = self.panel_key(game)
        if key != self._panel_key:
            self._panel_key = key
            self.redraw_panel(game)
        self.screen.blit(self.panel, (400, 0), pygame.Rect(400, 0, 240, 411))
        self.screen.blit(self.panel, (0, 400), pygame.Rect(0, 400, 400, 11))

    def panel_key(self, game):
        p, h, w = game.player, game.player.hero, game.world
        return (h.life, h.mlife, h.mana, h.mmana, p.inv.coins, p.inv.bkey, p.inv.rkey, p.inv.ykey,
                w.level, w.origin, len(w.visited), getattr(w, 'map_version', 0))

    def redraw_panel(self, game):
        """stats(): clear the panel, hatch the frame, then draw every gauge."""
        g, p = self.g, game.player
        g.setcolor(8)
        g.settextstyle(1, 0, 3)
        g.setfillstyle(1, 0)
        g.bar(411, 0, 640, 500)
        g.setfillstyle(6, 15)
        g.bar(400, 0, 410, 399)
        g.bar(0, 400, 650, 410)
        self.dlife(p.hero)
        self.dmana(p.hero)
        self.dcoins()
        self.dmoney(p.inv.coins)
        g.setcolor(15)
        g.outtextxy(513, 240, 'Map')        # still in dmoney()'s font (3, 0, 1), as in the original
        self.dkeys(p.inv)
        self.dmap(game)

    def dlife(self, h):
        """dlife2(): a red orb, blacked out from the top in 6-pixel bands as life drops."""
        g = self.g
        g.setcolor(4)
        g.setfillstyle(1, 4)
        g.fillellipse(470, 65, 50, 50)
        g.setcolor(0)
        g.setfillstyle(1, 0)
        frac = h.life / h.mlife if h.mlife else 0
        for i in range(100):
            if 1 - i * 0.01 > frac:
                g.bar(420, 15 + i, 520, 20 + i)
        g.setcolor(15)
        g.circle(470, 65, 50)
        g.line(427, 90, 431, 90)
        g.line(513, 90, 509, 90)
        g.setfillstyle(1, 4)
        if h.life > -5:
            g.bar(464, 114, 476, 114)

    def dmana(self, h):
        """dmana2(): the triangle is filled blue, then the empty share of its *area* is cut
        off the top in black. The pink edge is only a flood-fill boundary; it ends up white."""
        g = self.g
        g.setfillstyle(1, 0)
        g.bar(530, 15, 630, 115)
        g.setcolor(1)
        g.setfillstyle(1, 1)
        g.line(530, 115, 630, 115)
        g.line(630, 115, 580, 15)
        g.line(580, 15, 530, 115)
        g.floodfill(580, 80, 1)
        area = int(h.mana / h.mmana * 5000) if h.mmana else 0
        if area not in (0, 5000):
            empty = 5000 - area
            d = 100 / math.sqrt(5000 / empty)            # height of the black top triangle
            g.setcolor(13)
            g.line(int(580 - d / 2), int(15 + d), int(580 + d / 2), int(15 + d))
            g.line(530, 115, 630, 115)
            g.line(630, 115, 580, 15)
            g.line(580, 15, 530, 115)
            g.setfillstyle(1, 0)
            g.floodfill(580, 16, 13)
            g.setcolor(1)
            g.line(int(580 - d / 2), int(15 + d), int(580 + d / 2), int(15 + d))
        g.setcolor(15)
        if area == 0:
            g.setfillstyle(1, 0)
            g.bar(530, 15, 630, 115)
        g.line(530, 115, 630, 115)
        g.line(630, 115, 580, 15)
        g.line(580, 15, 530, 115)

    def dcoins(self):
        g = self.g
        g.setcolor(5)
        g.setfillstyle(1, 5)
        g.bar(450, 139, 550, 177)
        for stack in COIN_STACKS:
            g.setcolor(0)
            g.setfillstyle(1, 14)
            for x1, y1, x2, y2, sx, sy in stack:
                g.rectangle(x1, y1, x2, y2)
                g.floodfill(sx, sy, 0)

    def dmoney(self, coins: int):
        g = self.g
        g.setcolor(0)
        g.setfillstyle(1, 0)
        g.bar(555, 145, 640, 170)
        g.setcolor(15)
        g.moveto(560, 145)
        g.settextstyle(3, 0, 1)
        g.outtext(str(coins))

    def dkeys(self, inv):
        """dkeys2(): three keys drawn with 3-pixel lines, coloured only when held."""
        g = self.g
        g.setlinestyle(0, 1, 3)
        for field, colour, x, y in KEYS:
            g.setcolor(colour if getattr(inv, field) == 1 else 8)
            g.circle(x + 460, y + 240, 11)
            g.line(x + 471, y + 240, x + 516, y + 240)
            g.line(x + 516, y + 240, x + 516, y + 250)
            g.line(x + 516, y + 250, x + 501, y + 250)
            g.line(x + 501, y + 250, x + 501, y + 240)
        g.setlinestyle(0, 1, 1)

    def dmap(self, game):
        """dmap(): a brown frame and one pixel per map tile. Unvisited screens are grey and the
        current screen carries a 4x4 yellow marker in its middle."""
        g = self.g
        g.setfillstyle(1, 6)
        g.bar(479, 273, 581, 275)
        g.bar(479, 376, 581, 378)
        g.bar(580, 273, 582, 378)
        g.bar(477, 273, 479, 378)
        g.setcolor(15)
        g.rectangle(477, 273, 582, 378)
        w = game.world
        key = (w.level, w.origin, len(w.visited), getattr(w, 'map_version', 0))
        if key != self._map_key:
            self._map_key = key
            self.render_map(w)
        self.panel.blit(self._map, (480, 276))

    def render_map(self, w):
        from .bgi import EGA
        px = pygame.PixelArray(self._map)
        cur = ((w.origin[0] - 1) // 10, (w.origin[1] - 1) // 10)
        colours = [self._map.map_rgb(c) for c in EGA]
        for i in range(1, 101):
            for ii in range(1, 101):
                q = w.grid[i][ii]
                col = 2
                if q.wall == 2:
                    col = 1
                if q.floor == 2 or (q.wall == 5 and w.level == 5):
                    col = 8
                if q.floor in (7, 8):
                    col = 6
                if q.wall == 3:
                    col = 10
                if q.wall == 4 or 9 < q.wall < 15 or q.floor in (6, 4) or q.wall == -1:
                    col = 0
                screen = ((i - 1) // 10, (ii - 1) // 10)
                if screen not in w.visited and screen != cur:
                    col = 8
                if screen == cur and 3 < i % 10 < 8 and 3 < ii % 10 < 8:
                    col = 14
                px[i - 1, ii - 1] = colours[col]
        del px

    # ── bottom strip ────────────────────────────────────────────────────────
    def draw_belt(self, inv):
        """dpotions2(): eight potion bottles with their number inside and the count beside."""
        from .state import POTION_FIELDS
        counts = tuple(getattr(inv, POTION_FIELDS[n]) for n in range(1, 9))
        if counts != self._belt_key:
            self._belt_key = counts
            surf = pygame.Surface((640, 480))
            g = BGI(surf, self.g._source)
            g._fonts = self.g._fonts
            g.setfillstyle(1, 0)
            g.bar(0, 411, 640, 500)
            for n in range(1, 9):
                bx, y = 80 * n - 68, 420
                g.setcolor(15)
                g.arc(bx + 20, y + 30, 180, 0, 7)
                g.line(bx + 13, y + 30, bx + 13, y + 20)
                g.line(bx + 27, y + 30, bx + 27, y + 20)
                g.arc(bx + 13, y + 14, 270, 360, 5)
                g.arc(bx + 27, y + 14, 180, 270, 5)
                g.line(bx + 18, y + 14, bx + 18, y + 12)
                g.line(bx + 22, y + 14, bx + 22, y + 12)
                g.setfillstyle(1, POTION_COLOURS[n - 1])
                g.ellipse(bx + 20, y + 12, 0, 180, 2, 1)
                g.floodfill(bx + 20, y + 20, 15)
                g.setfillstyle(1, 6)
                g.setcolor(6)
                g.bar(bx + 19, y + 10, bx + 21, y + 13)
                g.setcolor(15)
                g.ellipse(bx + 20, y + 12, 180, 360, 2, 1)
                if n in DARK_LABELS:
                    g.setcolor(0)
                g.settextstyle(0, 0, 1)
                g.outtextxy(80 * n - 51, 443, str(n))
            g.setcolor(15)
            g.settextstyle(7, 0, 2)
            for n in range(1, 9):
                g.outtextxy(80 * n - 37, 440, str(counts[n - 1]))
            self._belt.blit(surf, (0, 0), pygame.Rect(0, 410, 640, 70))
        self.screen.blit(self._belt, (0, 410))

    def draw_messages(self, lines):
        """Messages go where the belt is, in the game's message font (settextstyle(7,0,2) at 9,413)."""
        g = BGI(self.screen, self.g._source)
        g._fonts = self.g._fonts
        g.setfillstyle(1, 0)
        g.bar(0, 411, 640, 480)
        g.settextstyle(7, 0, 2)
        y = 413
        for text, colour in lines[-3:]:
            g.setcolor(colour)
            g.outtextxy(9, y, text)
            y += 22
