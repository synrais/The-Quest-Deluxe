"""Little vector icons drawn with pygame (smooth, in any colour) and handed to Tk as PNGs with transparency."""
from __future__ import annotations

import base64
import io
import math
import os

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame  # noqa: E402

pygame.init()
try:
    pygame.display.set_mode((1, 1))        # the dummy driver: no window, but surfaces can convert_alpha()
except pygame.error:
    pass

BIG = 96                      # icons are drawn at this size and scaled down (that is what smooths them)


def _rgb(c):
    if isinstance(c, str):
        c = c.lstrip('#')
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c[:3])


class Pen:
    """Draws in 0..1 coordinates on a BIG x BIG surface."""

    def __init__(self, colour, w=0.09):
        self.s = pygame.Surface((BIG, BIG), pygame.SRCALPHA)
        self.c = _rgb(colour) + (255,)
        self.w = max(2, int(w * BIG))

    def p(self, pt):
        return (pt[0] * BIG, pt[1] * BIG)

    def line(self, a, b, w=None):
        pygame.draw.line(self.s, self.c, self.p(a), self.p(b), int((w or self.w / BIG) * BIG) if w else self.w)
        for q in (a, b):                                      # round ends
            pygame.draw.circle(self.s, self.c, self.p(q), (int(w * BIG) if w else self.w) / 2)

    def lines(self, pts, w=None, closed=False):
        for a, b in zip(pts, pts[1:] + (pts[:1] if closed else [])):
            self.line(a, b, w)

    def poly(self, pts, fill=True):
        pygame.draw.polygon(self.s, self.c, [self.p(q) for q in pts], 0 if fill else self.w)

    def rect(self, x, y, w, h, r=0.0, fill=False):
        pygame.draw.rect(self.s, self.c, (x * BIG, y * BIG, w * BIG, h * BIG), 0 if fill else self.w,
                         border_radius=int(r * BIG))

    def circle(self, cx, cy, r, fill=False):
        pygame.draw.circle(self.s, self.c, self.p((cx, cy)), r * BIG, 0 if fill else self.w)

    def arc(self, cx, cy, r, a0, a1):
        rect = pygame.Rect((cx - r) * BIG, (cy - r) * BIG, 2 * r * BIG, 2 * r * BIG)
        pygame.draw.arc(self.s, self.c, rect, math.radians(a0), math.radians(a1), self.w)


def _home(d):
    d.poly([(0.5, 0.12), (0.95, 0.5), (0.05, 0.5)], True)
    d.rect(0.2, 0.46, 0.6, 0.42, 0.04, True)
    d.c = (0, 0, 0, 0)
    d.rect(0.42, 0.6, 0.16, 0.28, 0.0, True)


def _map(d):
    d.poly([(0.08, 0.2), (0.36, 0.1), (0.64, 0.2), (0.92, 0.1), (0.92, 0.8), (0.64, 0.9), (0.36, 0.8), (0.08, 0.9)], False)
    d.line((0.36, 0.1), (0.36, 0.8))
    d.line((0.64, 0.2), (0.64, 0.9))


def _skull(d):
    d.circle(0.5, 0.42, 0.34, True)
    d.rect(0.3, 0.6, 0.4, 0.28, 0.05, True)
    d.c = (0, 0, 0, 0)
    d.circle(0.37, 0.44, 0.09, True)
    d.circle(0.63, 0.44, 0.09, True)
    d.rect(0.46, 0.62, 0.08, 0.2, 0, True)


def _sword(d):
    d.poly([(0.84, 0.1), (0.9, 0.16), (0.42, 0.64), (0.36, 0.58)], True)
    d.line((0.28, 0.5), (0.5, 0.72), 0.09)
    d.line((0.4, 0.62), (0.16, 0.86), 0.1)
    d.circle(0.12, 0.9, 0.05, True)


def _helmet(d):
    d.arc(0.5, 0.52, 0.38, 0, 180)
    d.line((0.12, 0.52), (0.12, 0.84))
    d.line((0.88, 0.52), (0.88, 0.84))
    d.line((0.12, 0.84), (0.88, 0.84))
    d.line((0.5, 0.18), (0.5, 0.58))
    d.line((0.3, 0.58), (0.7, 0.58))


def _wand(d):
    d.line((0.15, 0.85), (0.62, 0.38), 0.09)
    for a, b in (((0.72, 0.12), (0.72, 0.3)), ((0.63, 0.21), (0.81, 0.21)), ((0.88, 0.5), (0.88, 0.6)),
                 ((0.83, 0.55), (0.93, 0.55)), ((0.42, 0.12), (0.42, 0.2)), ((0.38, 0.16), (0.46, 0.16))):
        d.line(a, b, 0.06)


def _tiles(d):
    d.rect(0.1, 0.1, 0.34, 0.34, 0.04, False)
    d.rect(0.56, 0.1, 0.34, 0.34, 0.04, True)
    d.rect(0.1, 0.56, 0.34, 0.34, 0.04, True)
    d.rect(0.56, 0.56, 0.34, 0.34, 0.04, False)


def _coin(d):
    d.circle(0.5, 0.5, 0.38, False)
    d.line((0.5, 0.28), (0.5, 0.72))
    d.line((0.38, 0.4), (0.62, 0.4), 0.07)
    d.line((0.38, 0.6), (0.62, 0.6), 0.07)


def _book(d):
    d.rect(0.15, 0.12, 0.7, 0.76, 0.05, False)
    d.line((0.15, 0.72), (0.85, 0.72))
    d.line((0.32, 0.3), (0.68, 0.3), 0.07)
    d.line((0.32, 0.46), (0.6, 0.46), 0.07)


def _bolt(d):
    d.poly([(0.58, 0.05), (0.2, 0.56), (0.46, 0.56), (0.38, 0.95), (0.8, 0.4), (0.54, 0.4)], True)


def _check(d):
    d.lines([(0.15, 0.52), (0.4, 0.76), (0.86, 0.24)], 0.12)


def _gear(d):
    d.circle(0.5, 0.5, 0.22, False)
    for i in range(8):
        a = math.radians(i * 45)
        d.line((0.5 + 0.3 * math.cos(a), 0.5 + 0.3 * math.sin(a)), (0.5 + 0.42 * math.cos(a), 0.5 + 0.42 * math.sin(a)), 0.1)
    d.circle(0.5, 0.5, 0.33, False)


def _play(d):
    d.poly([(0.25, 0.12), (0.88, 0.5), (0.25, 0.88)], True)


def _save(d):
    d.rect(0.12, 0.12, 0.76, 0.76, 0.06, False)
    d.rect(0.3, 0.12, 0.4, 0.28, 0.0, False)
    d.rect(0.28, 0.55, 0.44, 0.33, 0.0, False)


def _undo(d):
    d.arc(0.5, 0.6, 0.3, -70, 140)
    d.poly([(0.06, 0.4), (0.4, 0.4), (0.22, 0.64)], True)


def _redo(d):
    d.arc(0.5, 0.6, 0.3, 40, 250)
    d.poly([(0.6, 0.4), (0.94, 0.4), (0.78, 0.64)], True)


def _search(d):
    d.circle(0.42, 0.42, 0.28, False)
    d.line((0.63, 0.63), (0.9, 0.9), 0.11)


def _plus(d):
    d.line((0.5, 0.15), (0.5, 0.85), 0.12)
    d.line((0.15, 0.5), (0.85, 0.5), 0.12)


def _minus(d):
    d.line((0.15, 0.5), (0.85, 0.5), 0.12)


def _trash(d):
    d.line((0.12, 0.25), (0.88, 0.25), 0.09)
    d.line((0.38, 0.12), (0.62, 0.12), 0.09)
    d.poly([(0.22, 0.32), (0.78, 0.32), (0.72, 0.9), (0.28, 0.9)], False)
    d.line((0.42, 0.45), (0.43, 0.76), 0.07)
    d.line((0.58, 0.45), (0.57, 0.76), 0.07)


def _copy(d):
    d.rect(0.1, 0.28, 0.5, 0.62, 0.05, False)
    d.rect(0.4, 0.1, 0.5, 0.62, 0.05, False)


def _sparkle(d):
    d.poly([(0.5, 0.04), (0.6, 0.4), (0.96, 0.5), (0.6, 0.6), (0.5, 0.96), (0.4, 0.6), (0.04, 0.5), (0.4, 0.4)], True)


def _flag(d):
    d.line((0.22, 0.1), (0.22, 0.92), 0.09)
    d.poly([(0.22, 0.14), (0.86, 0.3), (0.22, 0.52)], True)


def _door(d):
    d.rect(0.2, 0.08, 0.6, 0.84, 0.05, False)
    d.circle(0.64, 0.52, 0.05, True)


def _link(d):
    d.rect(0.08, 0.36, 0.48, 0.28, 0.14, False)
    d.rect(0.44, 0.36, 0.48, 0.28, 0.14, False)


def _eye(d):
    d.arc(0.5, 0.85, 0.5, 40, 140)
    d.arc(0.5, 0.15, 0.5, 220, 320)
    d.circle(0.5, 0.5, 0.14, True)


def _lock(d):
    d.rect(0.2, 0.44, 0.6, 0.44, 0.06, True)
    d.arc(0.5, 0.44, 0.22, 0, 180)


def _grid(d):
    d.rect(0.1, 0.1, 0.8, 0.8, 0.03, False)
    for t in (0.37, 0.63):
        d.line((t, 0.1), (t, 0.9), 0.06)
        d.line((0.1, t), (0.9, t), 0.06)


def _brush(d):
    d.line((0.84, 0.14), (0.38, 0.6), 0.12)
    d.poly([(0.34, 0.58), (0.44, 0.68), (0.28, 0.9), (0.1, 0.9), (0.14, 0.72)], True)


def _eraser(d):
    d.poly([(0.1, 0.62), (0.52, 0.12), (0.9, 0.42), (0.52, 0.88), (0.34, 0.88)], False)
    d.line((0.36, 0.36), (0.72, 0.64), 0.07)


def _bucket(d):
    d.poly([(0.14, 0.5), (0.5, 0.14), (0.86, 0.5), (0.5, 0.86)], False)
    d.line((0.5, 0.14), (0.5, 0.04), 0.07)
    d.circle(0.86, 0.76, 0.07, True)


def _rect(d):
    d.rect(0.14, 0.2, 0.72, 0.6, 0.0, False)


def _line(d):
    d.line((0.15, 0.85), (0.85, 0.15), 0.1)


def _picker(d):
    d.line((0.2, 0.8), (0.6, 0.4), 0.1)
    d.line((0.5, 0.3), (0.7, 0.5), 0.14)
    d.line((0.66, 0.34), (0.86, 0.14), 0.1)
    d.circle(0.2, 0.84, 0.05, True)


def _select(d):
    for a, b in (((0.12, 0.12), (0.4, 0.12)), ((0.6, 0.12), (0.88, 0.12)), ((0.88, 0.12), (0.88, 0.4)),
                 ((0.88, 0.6), (0.88, 0.88)), ((0.88, 0.88), (0.6, 0.88)), ((0.4, 0.88), (0.12, 0.88)),
                 ((0.12, 0.88), (0.12, 0.6)), ((0.12, 0.4), (0.12, 0.12))):
        d.line(a, b, 0.08)


def _stamp(d):
    d.rect(0.3, 0.1, 0.4, 0.34, 0.08, True)
    d.rect(0.4, 0.4, 0.2, 0.2, 0.0, True)
    d.rect(0.14, 0.58, 0.72, 0.14, 0.04, True)
    d.line((0.14, 0.88), (0.86, 0.88), 0.08)


def _hand(d):
    d.rect(0.3, 0.38, 0.4, 0.5, 0.12, False)
    for x in (0.34, 0.46, 0.58, 0.7):
        d.line((x, 0.4), (x, 0.14 + abs(x - 0.52) * 0.3), 0.08)


def _zoom(d):
    _search(d)
    d.line((0.3, 0.42), (0.54, 0.42), 0.06)
    d.line((0.42, 0.3), (0.42, 0.54), 0.06)


def _warn(d):
    d.poly([(0.5, 0.1), (0.94, 0.88), (0.06, 0.88)], False)
    d.line((0.5, 0.4), (0.5, 0.62), 0.09)
    d.circle(0.5, 0.76, 0.04, True)


def _info(d):
    d.circle(0.5, 0.5, 0.4, False)
    d.line((0.5, 0.46), (0.5, 0.72), 0.09)
    d.circle(0.5, 0.3, 0.05, True)


def _close(d):
    d.line((0.2, 0.2), (0.8, 0.8), 0.11)
    d.line((0.8, 0.2), (0.2, 0.8), 0.11)


def _right(d):
    d.lines([(0.35, 0.18), (0.68, 0.5), (0.35, 0.82)], 0.11)


def _down(d):
    d.lines([(0.18, 0.35), (0.5, 0.68), (0.82, 0.35)], 0.11)


def _star(d):
    pts = []
    for i in range(10):
        r = 0.46 if i % 2 == 0 else 0.2
        a = math.radians(-90 + i * 36)
        pts.append((0.5 + r * math.cos(a), 0.52 + r * math.sin(a)))
    d.poly(pts, True)


def _heart(d):
    d.circle(0.32, 0.36, 0.2, True)
    d.circle(0.68, 0.36, 0.2, True)
    d.poly([(0.13, 0.44), (0.87, 0.44), (0.5, 0.9)], True)


def _shield(d):
    d.poly([(0.5, 0.08), (0.88, 0.2), (0.84, 0.56), (0.5, 0.92), (0.16, 0.56), (0.12, 0.2)], False)


def _potion(d):
    d.rect(0.4, 0.08, 0.2, 0.2, 0.0, False)
    d.poly([(0.4, 0.28), (0.6, 0.28), (0.86, 0.84), (0.14, 0.84)], False)
    d.line((0.3, 0.62), (0.7, 0.62), 0.07)


def _key(d):
    d.circle(0.3, 0.5, 0.2, False)
    d.line((0.5, 0.5), (0.9, 0.5), 0.09)
    d.line((0.76, 0.5), (0.76, 0.68), 0.08)
    d.line((0.88, 0.5), (0.88, 0.62), 0.08)


def _person(d):
    d.circle(0.5, 0.3, 0.17, True)
    d.arc(0.5, 0.95, 0.36, 0, 180)


def _paint(d):
    d.circle(0.5, 0.5, 0.4, False)
    for cx, cy in ((0.34, 0.38), (0.54, 0.3), (0.68, 0.48), (0.4, 0.62)):
        d.circle(cx, cy, 0.06, True)


def _moon(d):
    d.circle(0.5, 0.5, 0.4, True)
    d.c = (0, 0, 0, 0)
    d.circle(0.68, 0.4, 0.34, True)


def _sun(d):
    d.circle(0.5, 0.5, 0.2, True)
    for i in range(8):
        a = math.radians(i * 45)
        d.line((0.5 + 0.3 * math.cos(a), 0.5 + 0.3 * math.sin(a)), (0.5 + 0.42 * math.cos(a), 0.5 + 0.42 * math.sin(a)), 0.07)


def _scroll(d):
    d.rect(0.2, 0.12, 0.6, 0.76, 0.1, False)
    for y in (0.32, 0.48, 0.64):
        d.line((0.34, y), (0.66, y), 0.06)


def _dice(d):
    d.rect(0.14, 0.14, 0.72, 0.72, 0.12, False)
    for cx, cy in ((0.34, 0.34), (0.66, 0.34), (0.5, 0.5), (0.34, 0.66), (0.66, 0.66)):
        d.circle(cx, cy, 0.06, True)


def _tree(d):
    d.poly([(0.5, 0.06), (0.84, 0.5), (0.16, 0.5)], True)
    d.poly([(0.5, 0.28), (0.9, 0.78), (0.1, 0.78)], True)
    d.rect(0.44, 0.76, 0.12, 0.16, 0.0, True)


def _mountain(d):
    d.lines([(0.06, 0.82), (0.34, 0.2), (0.52, 0.52), (0.64, 0.36), (0.94, 0.82)], 0.08)
    d.line((0.06, 0.82), (0.94, 0.82), 0.08)
    d.lines([(0.28, 0.34), (0.34, 0.42), (0.4, 0.34)], 0.05)


def _oval(d):
    d.circle(0.5, 0.5, 0.34, False)


def _dither(d):
    for i in range(4):
        for j in range(4):
            if (i + j) % 2 == 0:
                d.rect(0.12 + i * 0.19, 0.12 + j * 0.19, 0.17, 0.17, 0.0, True)


def _swap(d):
    d.rect(0.1, 0.1, 0.4, 0.4, 0.0, True)
    d.rect(0.5, 0.5, 0.4, 0.4, 0.0, False)
    d.lines([(0.58, 0.3), (0.74, 0.3), (0.74, 0.42)], 0.06)
    d.lines([(0.42, 0.7), (0.26, 0.7), (0.26, 0.58)], 0.06)


def _mirror(d):
    d.line((0.5, 0.08), (0.5, 0.92), 0.05)
    d.poly([(0.4, 0.2), (0.08, 0.5), (0.4, 0.8)], True)
    d.poly([(0.6, 0.2), (0.92, 0.5), (0.6, 0.8)], False)


def _flip_h(d):
    d.lines([(0.1, 0.5), (0.9, 0.5)], 0.07)
    d.poly([(0.1, 0.5), (0.3, 0.34), (0.3, 0.66)], True)
    d.poly([(0.9, 0.5), (0.7, 0.34), (0.7, 0.66)], True)
    d.line((0.5, 0.14), (0.5, 0.86), 0.04)


def _flip_v(d):
    d.lines([(0.5, 0.1), (0.5, 0.9)], 0.07)
    d.poly([(0.5, 0.1), (0.34, 0.3), (0.66, 0.3)], True)
    d.poly([(0.5, 0.9), (0.34, 0.7), (0.66, 0.7)], True)
    d.line((0.14, 0.5), (0.86, 0.5), 0.04)


def _turn_cw(d):
    d.arc(0.5, 0.5, 0.32, 20, 300)
    d.poly([(0.78, 0.2), (0.9, 0.5), (0.58, 0.44)], True)


def _turn_ccw(d):
    d.arc(0.5, 0.5, 0.32, 240, 520)
    d.poly([(0.22, 0.2), (0.1, 0.5), (0.42, 0.44)], True)


def _cut(d):
    d.line((0.2, 0.1), (0.7, 0.72), 0.07)
    d.line((0.8, 0.1), (0.3, 0.72), 0.07)
    d.circle(0.26, 0.82, 0.1, False)
    d.circle(0.74, 0.82, 0.1, False)


def _paste(d):
    d.rect(0.18, 0.2, 0.64, 0.7, 0.06, False)
    d.rect(0.36, 0.1, 0.28, 0.18, 0.04, True)
    d.line((0.32, 0.5), (0.68, 0.5), 0.06)
    d.line((0.32, 0.68), (0.6, 0.68), 0.06)


def _water(d):
    for y in (0.3, 0.5, 0.7):
        d.lines([(0.1, y), (0.3, y - 0.1), (0.5, y), (0.7, y - 0.1), (0.9, y)], 0.07)


def _cube(d):
    d.poly([(0.5, 0.1), (0.88, 0.3), (0.5, 0.5), (0.12, 0.3)], False)
    d.lines([(0.12, 0.3), (0.12, 0.7), (0.5, 0.9), (0.88, 0.7), (0.88, 0.3)])
    d.line((0.5, 0.5), (0.5, 0.9))


def _fit(d):
    for sx in (0, 1):
        for sy in (0, 1):
            cx, cy = 0.14 + sx * 0.72, 0.14 + sy * 0.72
            dx, dy = (1 if not sx else -1) * 0.2, (1 if not sy else -1) * 0.2
            d.lines([(cx + dx, cy), (cx, cy), (cx, cy + dy)])


def _refresh(d):
    d.arc(0.5, 0.5, 0.34, 40, 330)
    d.poly([(0.78, 0.12), (0.9, 0.44), (0.58, 0.38)], True)


def _list(d):
    for y in (0.25, 0.5, 0.75):
        d.circle(0.18, y, 0.04, True)
        d.line((0.32, y), (0.86, y), 0.07)


def _up(d):
    d.lines([(0.25, 0.62), (0.5, 0.36), (0.75, 0.62)])


def _left(d):
    d.lines([(0.62, 0.25), (0.36, 0.5), (0.62, 0.75)])


def _chart(d):
    d.rect(0.16, 0.5, 0.15, 0.36, 0, True)
    d.rect(0.42, 0.28, 0.15, 0.58, 0, True)
    d.rect(0.68, 0.14, 0.15, 0.72, 0, True)


def _people(d):
    d.circle(0.35, 0.32, 0.14, True)
    d.rect(0.14, 0.52, 0.42, 0.34, 0.12, True)
    d.circle(0.7, 0.38, 0.11, True)
    d.rect(0.58, 0.56, 0.3, 0.3, 0.1, True)


def _pin(d):
    d.circle(0.5, 0.38, 0.24, False)
    d.poly([(0.32, 0.55), (0.5, 0.92), (0.68, 0.55)], True)


def _download(d):
    d.line((0.5, 0.1), (0.5, 0.62))
    d.lines([(0.28, 0.42), (0.5, 0.64), (0.72, 0.42)])
    d.lines([(0.14, 0.7), (0.14, 0.88), (0.86, 0.88), (0.86, 0.7)])


DRAW = {name[1:]: fn for name, fn in globals().items() if name.startswith('_') and callable(fn) and fn.__module__ == __name__
        and name not in ('_rgb',)}

_cache: dict = {}


def surface(name: str, colour, size: int = 20) -> pygame.Surface:
    pen = Pen(colour)
    DRAW[name](pen)
    return pygame.transform.smoothscale(pen.s, (size, size))


def icon(name: str, colour='#e8eaee', size: int = 20):
    """A Tk image of the named icon (cached)."""
    import tkinter as tk
    key = (name, colour, size)
    if key not in _cache:
        s = surface(name, colour, size)
        buf = io.BytesIO()
        pygame.image.save(s, buf, 'x.png')
        _cache[key] = tk.PhotoImage(data=base64.b64encode(buf.getvalue()), format='png')
    return _cache[key]


def clear():
    _cache.clear()
