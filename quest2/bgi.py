"""A small Borland BGI emulation on a pygame surface.

The original game draws everything (HUD, text, screens) with BGI calls in 640x480x16 EGA/VGA.
This module reproduces the calls the game uses so the HUD can be ported call-for-call:
colours, lines (1 or 3 px), rectangles, bars, circles, arcs, ellipses, flood fill, and text in
the stroked .CHR fonts shipped in TheQuest.zip (bgi/*.CHR) plus the 8x8 ROM font.
"""
from __future__ import annotations

import math
import os
import struct

import pygame

# The 16 colours exactly as the game shows them: the VGA DAC's 6-bit levels 0/21/42/63, shifted left
# two bits (0, 84, 168, 252), which is what DOSBox screenshots of the original contain.
EGA = [(0, 0, 0), (0, 0, 168), (0, 168, 0), (0, 168, 168), (168, 0, 0), (168, 0, 168), (168, 84, 0),
       (168, 168, 168), (84, 84, 84), (84, 84, 252), (84, 252, 84), (84, 252, 252), (252, 84, 84),
       (252, 84, 252), (252, 252, 84), (252, 252, 252)]

# settextstyle() font numbers -> .CHR files (font 0 is the 8x8 bitmap font)
FONT_FILES = {1: 'TRIP.CHR', 2: 'LITT.CHR', 3: 'SANS.CHR', 4: 'GOTH.CHR', 5: 'SCRI.CHR',
              6: 'SIMP.CHR', 7: 'TSCR.CHR', 8: 'LCOM.CHR', 9: 'EURO.CHR', 10: 'BOLD.CHR'}
# Borland's stroked-font size table: charsize n scales by MUL[n] / DIV[n] (4 = the font's own size)
MUL = [1, 3, 2, 3, 1, 4, 5, 2, 5, 3, 4]
DIV = [1, 5, 3, 4, 1, 3, 3, 1, 2, 1, 1]

# setfillstyle() patterns (rows of 8 pixels, MSB = left). 6 (LTBKSLASH) is the game's hatched frame.
FILL_PATTERNS = {
    1: [0xFF] * 8,
    2: [0xFF, 0xFF, 0, 0, 0, 0, 0, 0],
    3: [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80],
    4: [0xE0, 0xC1, 0x83, 0x07, 0x0E, 0x1C, 0x38, 0x70],
    5: [0xF0, 0x78, 0x3C, 0x1E, 0x0F, 0x87, 0xC3, 0xE1],
    6: [0xA5, 0xD2, 0x69, 0xB4, 0x5A, 0x2D, 0x96, 0x4B],
    7: [0xFF, 0x88, 0x88, 0x88, 0xFF, 0x88, 0x88, 0x88],
    8: [0x81, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x81],
    9: [0xCC, 0x33, 0xCC, 0x33, 0xCC, 0x33, 0xCC, 0x33],
    10: [0x80, 0x00, 0x08, 0x00, 0x80, 0x00, 0x08, 0x00],
    11: [0x88, 0x00, 0x22, 0x00, 0x88, 0x00, 0x22, 0x00],
}

_TEXT_CACHE: dict = {}

FONT8X8 = os.path.join(os.path.dirname(__file__), 'content', 'font8x8.bin')


def bresenham(x1, y1, x2, y2):
    """Line pixels as the BGI driver plots them: from the upper end to the lower end, walking the
    major axis and stepping the minor axis on exact ties. Checked against the original's grass,
    shrubs and mana-triangle pixels."""
    if y1 > y2 or (y1 == y2 and x1 > x2):
        x1, y1, x2, y2 = x2, y2, x1, y1
    dx, dy = abs(x2 - x1), y2 - y1
    sx = 1 if x2 >= x1 else -1
    pts = []
    if dy > dx:
        err, x = 0, x1
        for y in range(y1, y2 + 1):
            pts.append((x, y))
            err += dx
            if 2 * err >= dy:
                x += sx
                err -= dy
    else:
        err, y = 0, y1
        for k in range(dx + 1):
            pts.append((x1 + sx * k, y))
            err += dy
            if dx and 2 * err >= dx:
                y += 1
                err -= dx
    return pts


class StrokeFont:
    """A Borland .CHR stroked font: per-glyph pen strokes on a grid with y pointing up."""

    def __init__(self, raw: bytes):
        head = raw.index(b'\x1a') + 1
        hsize = struct.unpack_from('<H', raw, head)[0]
        d = hsize
        if raw[d] != ord('+'):
            raise ValueError('not a stroked font')
        nchars, = struct.unpack_from('<H', raw, d + 1)
        self.first = raw[d + 4]
        stroke_off, = struct.unpack_from('<H', raw, d + 5)
        self.org_to_cap, self.org_to_base, self.org_to_dec = struct.unpack_from('<bbb', raw, d + 8)
        offs = struct.unpack_from(f'<{nchars}H', raw, d + 16)
        self.widths = raw[d + 16 + 2 * nchars: d + 16 + 3 * nchars]
        self.glyphs = []
        base = d + stroke_off
        for o in offs:
            p, strokes = base + o, []
            while True:
                b1, b2 = raw[p], raw[p + 1]
                p += 2
                op = ((b1 >> 7) << 1) | (b2 >> 7)
                if op == 0:
                    break
                x = b1 & 0x7F
                y = b2 & 0x7F
                x = x - 128 if x & 0x40 else x
                y = y - 128 if y & 0x40 else y
                strokes.append((op, x, y))
            self.glyphs.append(strokes)

    def glyph(self, ch: str):
        i = ord(ch) - self.first
        if 0 <= i < len(self.glyphs):
            return self.glyphs[i], self.widths[i]
        return [], 0


class BGI:
    """Draws on a 640x480 surface using BGI semantics and the EGA palette."""

    def __init__(self, surface: pygame.Surface, source=None):
        self.s = surface
        self.color = 15
        self.fill = (1, 15)            # (pattern, colour)
        self.thick = 1
        self.text_style = (0, 0, 1)    # (font, direction, size)
        self.cp = (0, 0)               # current position (moveto/outtext)
        self._fonts: dict[int, StrokeFont | None] = {}
        self._source = source
        try:
            with open(FONT8X8, 'rb') as fh:
                self._rom = fh.read()
        except OSError:
            self._rom = None

    # ── state ───────────────────────────────────────────────────────────────
    def setcolor(self, c):
        self.color = c

    def setfillstyle(self, pattern, c):
        self.fill = (pattern, c)

    def setfillpattern(self, rows, c):
        """USER_FILL (12): an 8x8 pattern supplied by the program."""
        self.user_pattern = list(rows)
        self.fill = (12, c)

    def setlinestyle(self, style, pattern, thickness):
        self.thick = thickness

    def settextstyle(self, font, direction, size):
        self.text_style = (font, direction, size)

    def moveto(self, x, y):
        self.cp = (x, y)

    def moverel(self, dx, dy):
        self.cp = (self.cp[0] + dx, self.cp[1] + dy)

    def lineto(self, x, y):
        self.line(self.cp[0], self.cp[1], x, y)
        self.cp = (x, y)

    def linerel(self, dx, dy):
        self.lineto(self.cp[0] + dx, self.cp[1] + dy)

    @property
    def rgb(self):
        return EGA[self.color]

    # ── primitives ──────────────────────────────────────────────────────────
    def getpixel(self, x, y) -> int:
        if 0 <= x < self.s.get_width() and 0 <= y < self.s.get_height():
            c = tuple(self.s.get_at((x, y)))[:3]
            return EGA.index(c) if c in EGA else 0
        return 0

    def putpixel(self, x, y, c):
        if 0 <= x < self.s.get_width() and 0 <= y < self.s.get_height():
            self.s.set_at((x, y), EGA[c])

    def line(self, x1, y1, x2, y2):
        pts = bresenham(x1, y1, x2, y2)
        col = self.rgb
        if self.thick >= 3:
            # BGI thick lines are three parallel 1-pixel lines, offset across the line
            dx, dy = (0, 1) if abs(x2 - x1) >= abs(y2 - y1) else (1, 0)
            for d in (-1, 0, 1):
                for x, y in pts:
                    self._set(x + d * dx, y + d * dy, col)
        else:
            for x, y in pts:
                self._set(x, y, col)

    def _set(self, x, y, col):
        if 0 <= x < self.s.get_width() and 0 <= y < self.s.get_height():
            self.s.set_at((x, y), col)

    def rectangle(self, x1, y1, x2, y2):
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        pygame.draw.rect(self.s, self.rgb, (x1, y1, x2 - x1 + 1, y2 - y1 + 1), 1)

    def bar(self, x1, y1, x2, y2):
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        pattern, c = self.fill
        rect = pygame.Rect(x1, y1, x2 - x1 + 1, y2 - y1 + 1)
        if pattern == 1:
            self.s.fill(EGA[c], rect)
        elif pattern == 0:
            self.s.fill(EGA[0], rect)
        else:
            self._pattern_fill(rect, pattern, c)

    def _pattern_rows(self):
        pattern = self.fill[0]
        if pattern == 12:
            return getattr(self, 'user_pattern', FILL_PATTERNS[1])
        if pattern == 0:
            return [0] * 8
        return FILL_PATTERNS.get(pattern, FILL_PATTERNS[1])

    def _fill_colour(self, x, y):
        """The colour a fill puts at (x, y): the fill colour where the pattern bit is set, else black."""
        if self._pattern_rows()[y % 8] & (0x80 >> (x % 8)):
            return EGA[self.fill[1]]
        return EGA[0]

    def _pattern_fill(self, rect, pattern, c):
        """Borland's 8x8 fill patterns, anchored to the screen (x % 8, y % 8)."""
        for y in range(rect.top, rect.bottom):
            for x in range(rect.left, rect.right):
                self.s.set_at((x, y), self._fill_colour(x, y))

    def _fill_points(self, pts):
        for x, y in pts:
            if 0 <= x < self.s.get_width() and 0 <= y < self.s.get_height():
                self.s.set_at((x, y), self._fill_colour(x, y))

    def bar3d(self, x1, y1, x2, y2, depth, top):
        self.bar(x1, y1, x2, y2)
        self.rectangle(x1, y1, x2, y2)
        if depth:
            self.line(x2, y2, x2 + depth, y2 - depth)
            self.line(x2 + depth, y2 - depth, x2 + depth, y1 - depth)
            if top:
                self.line(x1, y1, x1 + depth, y1 - depth)
                self.line(x1 + depth, y1 - depth, x2 + depth, y1 - depth)
                self.line(x2, y1, x2 + depth, y1 - depth)

    def drawpoly(self, pts):
        for a, b in zip(pts, pts[1:]):
            self.line(*a, *b)

    def fillpoly(self, pts):
        """Scan-convert the polygon (even-odd), fill with the fill style, then outline it."""
        if pts[0] != pts[-1]:
            pts = list(pts) + [pts[0]]
        ys = [p[1] for p in pts]
        inside = []
        for y in range(min(ys), max(ys) + 1):
            xs = []
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                if ya == yb:
                    continue
                if min(ya, yb) <= y < max(ya, yb):
                    xs.append(xa + (y - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                inside.extend((x, y) for x in range(int(math.ceil(a)), int(math.floor(b)) + 1))
        self._fill_points(inside)
        self.drawpoly(pts)

    def circle(self, x, y, r):
        self.arc(x, y, 0, 360, r)

    def arc(self, x, y, start, end, r):
        self.ellipse(x, y, start, end, r, r)

    def ellipse(self, x, y, start, end, rx, ry):
        """Outline of an elliptical arc; angles in degrees, counter-clockwise, 0 = right."""
        col = self.rgb
        if self.thick >= 3:
            for p in self._thick_arc(x, y, start, end, rx, ry):
                self._set(*p, col)
            return
        for px, py in self._arc_points(x, y, start, end, rx, ry):
            self._set(px, py, col)

    def _thick_arc(self, x, y, start, end, rx, ry):
        """3-pixel curves, approximated with a 3x3 brush. Borland's own result is a pixel narrower
        and slightly lopsided (compare the keys in the DOSBox screenshots); not matched yet."""
        pts = set()
        for px, py in self._arc_points(x, y, start, end, rx, ry):
            pts.update((px + a, py + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
        return pts
        for px, py in self._arc_points(x, y, start, end, rx, ry):
            if mode == 'square':
                pts.update((px + a, py + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
            elif mode == 'plus':
                pts.update(((px, py), (px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)))
            elif mode in ('hv', 'vh'):
                # widen across the curve: horizontally where it is steep, vertically where it is flat
                steep = abs(px - x) * (ry * ry) > abs(py - y) * (rx * rx)
                if (mode == 'hv') == steep:
                    pts.update(((px - 1, py), (px, py), (px + 1, py)))
                else:
                    pts.update(((px, py - 1), (px, py), (px, py + 1)))
        return pts

    @staticmethod
    def _quadrant(rx, ry):
        """One quadrant of a midpoint ellipse (x, y >= 0, y up); matches the original's circles."""
        pts = []
        if rx == 0 or ry == 0:
            return [(k, 0) for k in range(rx + 1)] + [(0, k) for k in range(ry + 1)]
        rx2, ry2 = rx * rx, ry * ry
        x, y = 0, ry
        dx, dy = 0, 2 * rx2 * y
        d1 = ry2 - rx2 * ry + rx2 / 2          # rx2/2 (not the textbook /4) matches the game
        while dx < dy:
            pts.append((x, y))
            x += 1
            dx += 2 * ry2
            if d1 < 0:
                d1 += dx + ry2
            else:
                y -= 1
                dy -= 2 * rx2
                d1 += dx - dy + ry2
        d2 = ry2 * (x + 0.5) ** 2 + rx2 * (y - 1) ** 2 - rx2 * ry2
        while y >= 0:
            pts.append((x, y))
            y -= 1
            dy -= 2 * rx2
            if d2 > 0:
                d2 += rx2 - dy
            else:
                x += 1
                dx += 2 * ry2
                d2 += dx - dy + rx2
        return pts

    @classmethod
    def _arc_points(cls, x, y, start, end, rx, ry):
        """Pixels of the ellipse whose angle lies in [start, end] (degrees, counter-clockwise)."""
        start %= 360
        end = end % 360 if end % 360 or end == 0 else 360
        full = (end - start) % 360 == 0 and end != start or (start == 0 and end in (0, 360) and True)
        seen, pts = set(), []
        for qx, qy in cls._quadrant(rx, ry):
            for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
                ex, ey = sx * qx, sy * qy
                p = (x + ex, y - ey)
                if p in seen:
                    continue
                ang = math.degrees(math.atan2(ey * rx, ex * ry)) % 360 if (ex or ey) else 0
                if full or cls._in_arc(ang, start, end):
                    seen.add(p)
                    pts.append(p)
        return pts

    @staticmethod
    def _in_arc(ang, start, end):
        """Is angle `ang` (0..360) on the arc from start to end? 0 and 360 are the same direction."""
        eps = 1e-9
        if start <= end:
            return start - eps <= ang <= end + eps or (end >= 360 - eps and ang <= eps)
        return ang >= start - eps or ang <= end + eps

    def fillellipse(self, x, y, rx, ry):
        self.sector(x, y, 0, 360, rx, ry, outline_edges=False)

    def pieslice(self, x, y, start, end, r):
        self.sector(x, y, start, end, r, r)

    def sector(self, x, y, start, end, rx, ry, outline_edges=True):
        """A filled elliptical wedge (fillellipse when it is the whole ellipse), outlined in the
        current colour."""
        whole = not outline_edges
        rim = self._arc_points(x, y, 0 if whole else start, 360 if whole else end, rx, ry)
        rows: dict[int, list[int]] = {}
        for px, py in self._arc_points(x, y, 0, 360, rx, ry):
            rows.setdefault(py, []).append(px)
        inside = []
        for py, xs in rows.items():
            for px in range(min(xs), max(xs) + 1):
                if whole:
                    inside.append((px, py))
                else:
                    ang = math.degrees(math.atan2((y - py) * rx, (px - x) * ry)) % 360 if (px, py) != (x, y) else start
                    if self._in_arc(ang, start % 360, end % 360 if end % 360 else 360):
                        inside.append((px, py))
        self._fill_points(inside)
        col = self.rgb
        for p in rim:
            self._set(*p, col)
        if outline_edges and (end - start) % 360:
            a0, a1 = math.radians(start), math.radians(end)
            self.line(x, y, x + int(round(rx * math.cos(a0))), y - int(round(ry * math.sin(a0))))
            self.line(x, y, x + int(round(rx * math.cos(a1))), y - int(round(ry * math.sin(a1))))

    def floodfill(self, x, y, border):
        """Fill the 4-connected region around (x, y) bounded by the border colour."""
        w, h = self.s.get_size()
        b = self.s.map_rgb(EGA[border])
        px = pygame.PixelArray(self.s)
        try:
            if px[x, y] == b:
                return
            stack, seen = [(x, y)], set()
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in seen or not (0 <= cx < w and 0 <= cy < h) or px[cx, cy] == b:
                    continue
                seen.add((cx, cy))
                stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
            for p in seen:
                px[p] = self.s.map_rgb(self._fill_colour(*p))
        finally:
            del px

    # ── text ────────────────────────────────────────────────────────────────
    def font(self, n) -> StrokeFont | None:
        if n not in self._fonts:
            self._fonts[n] = None
            if self._source is not None and n in FONT_FILES:
                try:
                    self._fonts[n] = StrokeFont(self._source.read(FONT_FILES[n]))
                except (FileNotFoundError, ValueError):
                    pass
        return self._fonts[n]

    def scale(self):
        size = max(1, min(10, self.text_style[2]))
        return MUL[size] / DIV[size]

    def textwidth(self, s: str) -> int:
        font_no, _, size = self.text_style
        f = self.font(font_no) if font_no else None
        if f is None:
            return 8 * size * len(s)
        return sum(self._scaled(f.glyph(c)[1]) for c in s)

    def textheight(self, s: str = 'H') -> int:
        font_no, _, size = self.text_style
        f = self.font(font_no) if font_no else None
        if f is None:
            return 8 * size
        return int((f.org_to_cap - f.org_to_dec) * self.scale())

    def outtext(self, s: str):
        x, y = self.cp
        self.outtextxy(x, y, s)
        self.cp = (x + self.textwidth(s), y)

    def outtextxy(self, x, y, s: str):
        """Left/top justified text, as the game always uses. Rendered strings are cached."""
        if not s:
            return
        font_no, _, size = self.text_style
        key = (font_no, size, self.color, s)
        hit = _TEXT_CACHE.get(key)
        if hit is None:
            hit = _TEXT_CACHE[key] = self._render_text(s)
            if len(_TEXT_CACHE) > 4000:
                _TEXT_CACHE.clear()
        surf, dx, dy = hit
        if surf is not None:
            self.s.blit(surf, (x + dx, y + dy))

    def _scaled(self, v):
        """A font coordinate scaled by the charsize the way Borland does it: integer multiply and
        divide, truncating toward zero. (Verified pixel-exact against the character sheet screenshot.)"""
        size = max(1, min(10, self.text_style[2]))
        q = abs(v) * MUL[size] // DIV[size]
        return q if v >= 0 else -q

    def _render_text(self, s: str):
        font_no, _, size = self.text_style
        f = self.font(font_no) if font_no else None
        pts = []
        if f is None:
            if not self._rom:
                return None, 0, 0
            for i, ch in enumerate(s):
                c = ord(ch) & 0xFF
                for row in range(8):
                    bits = self._rom[c * 8 + row]
                    for col_i in range(8):
                        if bits & (0x80 >> col_i):
                            for sy in range(size):
                                for sx in range(size):
                                    pts.append(((i * 8 + col_i) * size + sx, row * size + sy))
        else:
            base = self._scaled(f.org_to_cap - f.org_to_dec)   # TOP_TEXT: cap height + descent below y
            pen = 0
            for ch in s:
                strokes, width = f.glyph(ch)
                last = None
                for op, gx, gy in strokes:
                    p = (pen + self._scaled(gx), base - self._scaled(gy))
                    if op == 3 and last is not None:
                        pts.extend(bresenham(*last, *p))
                    last = p
                pen += self._scaled(width)
        if not pts:
            return None, 0, 0
        x0 = min(p[0] for p in pts)
        y0 = min(p[1] for p in pts)
        w = max(p[0] for p in pts) - x0 + 1
        h = max(p[1] for p in pts) - y0 + 1
        surf = pygame.Surface((w, h))
        key = (1, 2, 3) if self.rgb != (1, 2, 3) else (4, 5, 6)
        surf.fill(key)
        surf.set_colorkey(key)
        col = self.rgb
        for px, py in pts:
            surf.set_at((px - x0, py - y0), col)
        return surf, x0, y0
