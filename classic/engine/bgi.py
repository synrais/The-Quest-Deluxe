"""A small Borland BGI emulation on a pygame surface.

The original game draws everything (HUD, text, screens) with BGI calls in 640x480x16 EGA/VGA.
This module reproduces the calls the game uses so the HUD can be ported call-for-call:
colours, lines (1 or 3 px), rectangles, bars, circles, arcs, ellipses, flood fill, and text in
the stroked .CHR fonts the original ships (packs/TheQuest/bgi/*.CHR) plus the 8x8 ROM font.

EGAVGA.BGI draws only pixels, lines and bars itself; arcs, ellipses, sectors, polygons and bar3d
are drawn by the Borland kernel inside the exe, and so is the line clipping and the 3-pixel
thickness. Those parts are ports of the kernel code (tools/re/verify_bgi.py checks them).
"""
from __future__ import annotations

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
    2: [0xFF, 0xFF, 0, 0, 0xFF, 0xFF, 0, 0],       # LINE_FILL: EGAVGA.BGI's table (2 rows on, 2 off)
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


# The Borland kernel's sine table for its emulated arcs: sin(0..90 degrees) * 32768, rounded down
_SIN = (
    0, 571, 1143, 1714, 2285, 2855, 3425, 3993, 4560, 5126, 5690, 6252, 6812, 7371, 7927, 8480,
    9032, 9580, 10125, 10668, 11207, 11743, 12275, 12803, 13327, 13848, 14364, 14876, 15383, 15886,
    16384, 16876, 17364, 17846, 18323, 18794, 19260, 19720, 20173, 20621, 21062, 21497, 21926,
    22347, 22762, 23170, 23571, 23964, 24351, 24730, 25101, 25465, 25821, 26169, 26509, 26841,
    27165, 27481, 27788, 28087, 28377, 28659, 28932, 29196, 29451, 29697, 29935, 30163, 30381,
    30591, 30791, 30982, 31164, 31336, 31498, 31651, 31794, 31928, 32051, 32165, 32270, 32364,
    32449, 32523, 32588, 32643, 32688, 32723, 32748, 32763, 32768,
)


def _bgi_sin(a: int) -> int:
    """sin(a degrees) as the kernel's 16.16 fixed-point value."""
    neg = a < 0
    a = abs(a) % 360
    if a > 180:
        a -= 180
        neg = not neg
    if a > 90:
        a = 180 - a
    v = _SIN[a] * 2
    return -v if neg else v


def _fix_mul(v: int, r: int) -> int:
    """The integer part of a 16.16 value times r (rounded down, as the kernel's 32-bit multiply)."""
    return (v * r) >> 16


def _arc_end(angle: int, rx: int, ry: int) -> tuple[int, int]:
    """Where the kernel puts the point at `angle` degrees on an ellipse (offset from the centre)."""
    return _fix_mul(_bgi_sin(angle + 90), rx), -_fix_mul(_bgi_sin(angle), ry)


def _pseudo_angle(x: int, y: int) -> int:
    """The kernel's cheap stand-in for the angle of (x, y) (y down), used to clip arcs: it rises
    counter-clockwise from 0 degrees, one quadrant per 2000."""
    up = -y
    if x >= 0:
        return up - x if up >= 0 else x + 6000 + up
    return -x + 2000 - up if up >= 0 else x + 4000 - up


def _ellipse_steps(rx: int, ry: int):
    """The (x, y) steps of the kernel's integer midpoint ellipse for one quadrant (x, y >= 0, y
    measured down), scaled by 100 * max(rx, ry)^2; None if its 32-bit sums would overflow."""
    rx, ry = rx or 1, ry or 1
    s = max(rx, ry) ** 2 * 100
    p, q = s // rx // rx, s // ry // ry
    if s >= 1 << 32 or q * ry * ry >= 1 << 32:
        return None
    d, t, acc = q * ry * ry - s, 2 * q * ry, 0
    i, j = 0, ry
    out = []
    while True:                         # the flat part: step x, sometimes y
        out.append((i, j))
        u, v = acc + p, t - q
        if 2 * d + 2 * u >= v:
            j -= 1
            d -= v
            t = v - q
        i += 1
        d += u
        acc = u + p
        if acc >= t:
            break
    while j >= 0:                       # the steep part: step y, sometimes x
        out.append((i, j))
        u, v = acc + p, t - q
        if (u >> 1) + d <= v:
            i += 1
            d += u
            acc = u + p
        j -= 1
        d -= v
        t = v - q
    return out


def kernel_ellipse(cx: int, cy: int, start: int, end: int, rx: int, ry: int) -> list:
    """The pixels of a 1-pixel arc exactly as the Borland kernel (its emulated ARC) plots them,
    clipped to the arc with _pseudo_angle. A sweep of under 2 degrees, or a short one that starts
    and ends on the same pixel, plots only the end point; a zero sweep plots nothing."""
    sweep = (end - start) & 0xFFFF
    if sweep == 0:
        return []
    ps, pe = _arc_end(start, rx, ry), _arc_end(end, rx, ry)
    if sweep < (350 if ps == pe else 2):
        return [(cx + pe[0], cy + pe[1])]
    a, b = _pseudo_angle(*ps), _pseudo_angle(*pe)
    wrap = b <= a
    out = []
    for i, j in _ellipse_steps(rx, ry) or ():
        for sx, sy in ((i, j), (-i, j), (i, -j), (-i, -j)):
            k = _pseudo_angle(sx, sy)
            if (k >= a or k <= b) if wrap else a <= k <= b:
                out.append((cx + sx, cy + sy))
    return out


MAXX, MAXY = 639, 479                   # the kernel clips to the screen (the game sets no viewport)


def _outcode(x, y):
    return (1 if x < 0 else 2 if x > MAXX else 0) + (4 if y < 0 else 8 if y > MAXY else 0)


def _trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _clip_line(x1, y1, x2, y2):
    """The kernel's Cohen-Sutherland clip: the ends of the visible part, or None. The slope is
    taken once from the whole line, and each step moves the outside end onto one edge, with the
    intersection rounded toward zero."""
    if 0 <= x1 <= MAXX and 0 <= y1 <= MAXY and 0 <= x2 <= MAXX and 0 <= y2 <= MAXY:
        return x1, y1, x2, y2
    dx, dy = x2 - x1, y2 - y1
    if not (-0x8000 <= dx < 0x8000 and -0x8000 <= dy < 0x8000):
        return None
    while True:
        c1, c2 = _outcode(x1, y1), _outcode(x2, y2)
        if not c1 | c2:
            return x1, y1, x2, y2
        if c1 & c2:
            return None
        swapped = not c1
        if swapped:
            x1, y1, x2, y2 = x2, y2, x1, y1
        if dx == 0:
            y1 = min(max(y1, 0), MAXY)
        elif dy == 0:
            x1 = min(max(x1, 0), MAXX)
        elif x1 < 0 or x1 > MAXX:
            edge = 0 if x1 < 0 else MAXX
            y1 += _trunc_div((edge - x1) * dy, dx)
            x1 = edge
        else:
            edge = 0 if y1 < 0 else MAXY
            x1 += _trunc_div((edge - y1) * dx, dy)
            y1 = edge
        if swapped:
            x1, y1, x2, y2 = x2, y2, x1, y1


SEP, END = 'sep', 'end'                 # the kernel's 0x8001 / 0x8000 markers in its polygon buffer


class _PolyBuffer:
    """The kernel's polygon buffer while it collects points: a repeat of the first point is
    dropped while it is the only one; coming back to the first point closes the path (a SEP
    follows) and the next point starts anew."""

    def __init__(self):
        self.buf, self.first, self.count = [], None, 0

    def add(self, p):
        p = tuple(p)
        if self.count == 0:
            self.first, self.count = p, 1
            self.buf.append(p)
        elif p == self.first:
            if self.count > 1:
                self.buf.extend((p, SEP))
                self.count = 0
        else:
            self.buf.append(p)
            self.count += 1

    def restart(self, p):
        """Add p as the start of a fresh path (the kernel zeroes its count first)."""
        self.count = 0
        self.add(p)


def _poly_buffer(points, close=False) -> list:
    """The buffer for a polyline, ending in END. fillpoly() adds the very first point again, as
    the start of a fresh path, which gives the closing edge."""
    pb = _PolyBuffer()
    for p in points:
        pb.add(p)
    if close and pb.buf:
        pb.restart(pb.buf[0])
    return pb.buf + [END]


def _buffer_edges(buf):
    """The segments the kernel draws (and fills between) from a polygon buffer."""
    edges, prev, k = [], buf[0], 1
    if prev in (SEP, END):
        return edges
    while k < len(buf):
        item = buf[k]
        if item == END:
            break
        if item == SEP:
            k += 1
            if buf[k] in (SEP, END):
                break
            prev = buf[k]
        else:
            edges.append((prev, item))
            prev = item
        k += 1
    return edges


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
        col = self.rgb
        if self.thick >= 3:
            # the kernel draws thick lines as three 1-pixel lines, offset across the line
            dx, dy = (0, 1) if abs(x2 - x1) >= abs(y2 - y1) else (1, 0)
            for d in (0, -1, 1):
                self._line1(x1 + d * dx, y1 + d * dy, x2 + d * dx, y2 + d * dy, col)
        else:
            self._line1(x1, y1, x2, y2, col)

    def _line1(self, x1, y1, x2, y2, col):
        """A 1-pixel line, clipped to the screen first as the kernel does (the driver then draws
        the clipped line, whose pixels can differ from the part of the whole line on screen)."""
        ends = _clip_line(x1, y1, x2, y2)
        if ends:
            for x, y in bresenham(*ends):
                self._set(x, y, col)

    def _set(self, x, y, col):
        if 0 <= x < self.s.get_width() and 0 <= y < self.s.get_height():
            self.s.set_at((x, y), col)

    def rectangle(self, x1, y1, x2, y2):
        """graphics.lib draws it as four line() calls, so it takes the line thickness."""
        self.line(x1, y1, x2, y1)
        self.line(x2, y1, x2, y2)
        self.line(x2, y2, x1, y2)
        self.line(x1, y2, x1, y1)

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

    def bar3d(self, x1, y1, x2, y2, depth, top):
        """As the Borland kernel draws it: the fill inside the front face only, the face outlined,
        and the side (and the top, if asked) raised by depth * 3 / 4."""
        if x1 & 0xFFFF >= x2 & 0xFFFF:          # graphics.lib orders the corners (unsigned)
            x1, x2 = x2, x1
        if y1 & 0xFFFF >= y2 & 0xFFFF:
            y1, y2 = y2, y1
        self.bar(min(x1, x2) + 1, min(y1, y2) + 1, max(x1, x2) - 1, max(y1, y2) - 1)
        self.line(x1, y2, x1, y1)
        self.line(x1, y1, x2, y1)
        self.line(x2, y1, x2, y2)
        self.line(x2, y2, x1, y2)
        if depth:
            dy = (depth & 0xFFFF) * 3 % 0x10000 >> 2
            self.line(x2, y2, x2 + depth, y2 - dy)
            self.line(x2 + depth, y2 - dy, x2 + depth, y1 - dy)
            if top & 0xFF:
                self.line(x2 + depth, y1 - dy, x1 + depth, y1 - dy)
                self.line(x1 + depth, y1 - dy, x1, y1)
                self.line(x2, y1, x2 + depth, y1 - dy)

    def drawpoly(self, pts):
        for (x1, y1), (x2, y2) in _buffer_edges(_poly_buffer(pts)):
            self.line(x1, y1, x2, y2)

    def fillpoly(self, pts):
        """The kernel's scan-line fill, then the outline."""
        buf = _poly_buffer(pts, close=True)
        self._fill_buffer(buf)
        for (x1, y1), (x2, y2) in _buffer_edges(buf):
            self.line(x1, y1, x2, y2)

    def _fill_buffer(self, buf):
        """The kernel's scan-line fill of a polygon buffer (at least 4 entries, END included).
        Rows run from the lowest y up to (not including) the highest; each edge counts on rows
        min(y) <= row < max(y), crossing at the x rounded toward zero; the crossings are sorted
        and filled in pairs with bar()."""
        ys = [p[1] for p in buf if p not in (SEP, END)]
        if len(buf) < 4 or not ys:
            return
        edges = _buffer_edges(buf)
        for row in range(min(ys), max(max(ys), min(ys) + 1)):
            xs = []
            for (xa, ya), (xb, yb) in edges:
                if min(ya, yb) <= row < max(ya, yb):
                    if yb < ya:
                        xa, ya, xb, yb = xb, yb, xa, ya
                    xs.append(xa + _trunc_div((row - ya) * (xb - xa), yb - ya))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                self.bar(a, row, b, row)

    def circle(self, x, y, r):
        self.arc(x, y, 0, 360, r)

    def arc(self, x, y, start, end, r):
        self.ellipse(x, y, start, end, r, r)

    def ellipse(self, x, y, start, end, rx, ry):
        """Outline of an elliptical arc; angles in degrees, counter-clockwise, 0 = right."""
        col = self.rgb
        if int(start) & 0xFFFF == 0xFFFF:       # the kernel takes start -1 as a getarccoords() query
            return
        if self.thick >= 3:
            self._thick_arc(x, y, start, end, rx, ry)
            return
        for px, py in kernel_ellipse(x, y, int(start), int(end), rx, ry):
            self._set(px, py, col)

    def _thick_arc(self, x, y, start, end, rx, ry):
        """3-pixel curves the way the Borland kernel draws them (its emulated ARC, not the driver):
        one point per degree from its fixed-point sine table, collected like a polygon and joined
        by thick line segments. Repeated points still make a zero-length segment, which paints
        three pixels across. Collecting drops a repeat of the first point while it is the only
        one, and coming back to the first point closes the path; the next point starts anew."""
        start, end = int(start), int(end)
        if start & 0xFFFF >= end & 0xFFFF:  # an unsigned compare: negative angles count as large
            end += 360
        pts = []
        for a in range(start, max(end, start) + 1):     # the loop runs at least once
            ex, ey = _arc_end(a, rx, ry)
            pts.append((x + ex, y + ey))
        for (x1, y1), (x2, y2) in _buffer_edges(_poly_buffer(pts)):
            self.line(x1, y1, x2, y2)

    def fillellipse(self, x, y, rx, ry):
        """The kernel fills a bar across each row the ellipse steps reach, then outlines it with
        an ARC (so a thick line style gives a thick rim)."""
        for i, j in _ellipse_steps(rx, ry) or ():
            self.bar(x - i, y + j, x + i, y + j)
            self.bar(x - i, y - j, x + i, y - j)
        self.ellipse(x, y, 0, 360, rx, ry)

    def pieslice(self, x, y, start, end, r):
        self.sector(x, y, start, end, r, r)

    def sector(self, x, y, start, end, rx, ry):
        """A filled elliptical wedge as the Borland kernel draws it. The angles are taken mod 360
        (unsigned, an end of 360 kept) and put in increasing order, so start > end draws the
        wedge from end to start. It goes a quadrant at a time: the arc pixels in that quadrant,
        collected as a polygon with the centre, are filled with fillpoly()'s scan-line rule and
        the arc alone is outlined. Then the two radii are drawn, to where the first quadrant
        started and to where the last one ended."""
        a, b = (int(start) & 0xFFFF) % 360, int(end) & 0xFFFF
        if b != 360:
            b %= 360
        if a >= b:
            a, b = b, a
        first_start = last_end = None
        while True:
            q, last = a // 90, min(b // 90, 3)
            seg_end = b if q == last else (q + 1) * 90
            if seg_end == a:
                first_start = first_start or (0, 0)     # the kernel keeps its zeroed points
            else:
                last_end = _arc_end(seg_end, rx, ry)
                pb = _PolyBuffer()
                for p in kernel_ellipse(x, y, a, seg_end, rx, ry):
                    pb.add(p)
                pb.add((x, y))
                pb.restart(pb.buf[0])
                buf = pb.buf + [END]
                self._fill_buffer(buf)
                if len(buf) >= 3:                       # the outline leaves out the last three
                    for (x1, y1), (x2, y2) in _buffer_edges(buf[:-3] + [END]):
                        self.line(x1, y1, x2, y2)
                first_start = first_start or _arc_end(a, rx, ry)
            if q == last:
                break
            a = seg_end
        last_end = last_end or (0, 0)
        self.line(x, y, x + first_start[0], y + first_start[1])
        self.line(x, y, x + last_end[0], y + last_end[1])

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
        surf, dx, dy, segments = hit
        if surf is None:
            return
        w, h = self.s.get_size()
        if segments and not (0 <= x + dx and 0 <= y + dy and x + dx + surf.get_width() <= w
                             and y + dy + surf.get_height() <= h):
            # partly off the screen: the kernel clips every pen stroke before drawing it
            for (x1, y1), (x2, y2) in segments:
                self._line1(x + x1, y + y1, x + x2, y + y2, self.rgb)
            return
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
        pts, segments = [], []
        if f is None:
            if not self._rom:
                return None, 0, 0, None
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
                        segments.append((last, p))
                    last = p
                pen += self._scaled(width)
        if not pts:
            return None, 0, 0, None
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
        return surf, x0, y0, segments
