"""FPS mode: arrows, bolts and sling stones in flight (Deluxe).

The original draws no flight, only where a shot lands (arhit(), bolthit(), sthit()). In FPS mode the
missile first flies through the view: from the hero to what he shoots at, shrinking with distance (a
miss flies on past it), or from a creature at the hero, growing, and a miss whips past to one side.
Then the original's landing plays as before. Only the picture: the rules and the random numbers don't
know about it.
"""
from __future__ import annotations

import math

import pygame

from .bgi import EGA
from . import view3d

KINDS = {'arhit': 'arrow', 'bolthit': 'bolt', 'sthit': 'stone'}     # by the landing animation
MS_PER_SQUARE = 55
MIN_MS, MAX_MS = 140, 420
HEIGHT = 0.42                     # chest height, in squares (the eye is at 0.5)


def kind_of(anim_name) -> str:
    return KINDS.get(anim_name or '', 'arrow')


def path(frm, to, hit: bool, towards_hero: bool):
    """The flight: a function of t (0-1) giving (x, y, height) on the map, and how long it takes."""
    (x0, y0), (x1, y1) = (frm[0] + 0.5, frm[1] + 0.5), (to[0] + 0.5, to[1] + 0.5)
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    rx, ry = -uy, ux                                         # to the right of the way it flies
    h0, h1 = HEIGHT, HEIGHT
    if towards_hero:
        h1 = 0.5                                             # at the eye
        if hit:
            x1, y1 = x1 - ux * 0.35, y1 - uy * 0.35          # up to the hero's face
        else:
            x1, y1 = x1 + ux * 0.8 - rx * 0.7, y1 + uy * 0.8 - ry * 0.7   # past him, to one side
    else:
        # from the bow: low and to the right of the eye, a little ahead
        x0, y0, h0 = x0 + ux * 0.45 + rx * 0.12, y0 + uy * 0.45 + ry * 0.12, 0.2
        if not hit:
            x1, y1 = x1 + ux * 2.5 + rx * 0.3, y1 + uy * 2.5 + ry * 0.3   # on past it
    arc = 0.08 * math.hypot(x1 - x0, y1 - y0)

    def at(t):
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, h0 + (h1 - h0) * t + arc * 4 * t * (1 - t)
    ms = max(MIN_MS, min(MAX_MS, int(MS_PER_SQUARE * math.hypot(x1 - x0, y1 - y0))))
    return at, ms


def draw(view: pygame.Surface, v3d, cam, kind: str, head, tail):
    """The missile between two points (x, y, height) on the map (head first), in the 400 x 400 view."""
    k = view.get_width() / view3d.RES
    a, b = v3d.project(cam, *head[:2]), v3d.project(cam, *tail[:2])
    if a is None:
        return
    if b is None:
        b = a
    ax, ay = a[0] * k, (a[1] - a[2] * head[2]) * k
    bx, by = b[0] * k, (b[1] - b[2] * tail[2]) * k
    size = a[2] * k                                       # a square's width there, in view pixels
    if kind == 'stone':
        r = max(1, int(size * 0.05))
        pygame.draw.circle(view, EGA[8], (int(ax), int(ay)), r)
        if r > 2:
            pygame.draw.circle(view, EGA[7], (int(ax - r / 3), int(ay - r / 3)), max(1, r // 3))
        return
    width = max(1, int(size * (0.025 if kind == 'arrow' else 0.04)))
    pygame.draw.line(view, EGA[6] if kind == 'arrow' else EGA[8], (bx, by), (ax, ay), width)
    pygame.draw.circle(view, EGA[7], (int(ax), int(ay)), max(1, width))              # the head
    if kind == 'arrow':
        pygame.draw.circle(view, EGA[15], (int(bx), int(by)), max(1, width))         # the feathers
