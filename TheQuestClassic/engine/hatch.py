"""The hatching of a worn armour.

The original draws some pictures (the armours) by filling a shape with BGI's LTBKSLASH pattern (setfillstyle 6), and a fill pattern is anchored to the
screen's corner, not to the shape: the same armour hatched in the backpack and worn on the body shows a different phase of the pattern. The pictures of
the pack are the backpack's drawing, so a worn one is re-hatched here for the place it is drawn at."""
from __future__ import annotations

import pygame

from .bgi import FILL_PATTERNS

PATTERN = FILL_PATTERNS[6]
BAKED = (2, 2)                  # the screen phase (x % 8, y % 8) the pack's pictures were drawn at: the backpack's cells
_cache: dict = {}


def _bit(x: int, y: int, ox: int, oy: int) -> int:
    return (PATTERN[(y + oy) % 8] >> (7 - (x + ox) % 8)) & 1


def _plan(img: pygame.Surface):
    """(pixels that are the hatching, its colour) of a picture, or None when it holds none."""
    w, h = img.get_size()
    px = [[tuple(img.get_at((x, y)))[:3] for y in range(h)] for x in range(w)]
    counts: dict = {}
    for x in range(w):
        for y in range(h):
            counts[px[x][y]] = counts.get(px[x][y], 0) + 1
    ground = max(counts, key=counts.get)
    inside = [(x, y) for x in range(1, w - 1) for y in range(1, h - 1)
              if all(px[x + dx][y + dy] != ground for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
    light = {}
    for x, y in inside:
        if px[x][y] != (0, 0, 0):
            light[px[x][y]] = light.get(px[x][y], 0) + 1
    if len(inside) < 100 or not light:
        return None
    ink = max(light, key=light.get)
    if len(light) > 1:
        return None
    fits = [(x, y) for x, y in inside if (px[x][y] == ink) == bool(_bit(x, y, *BAKED))]
    if len(fits) < 0.9 * len(inside):
        return None                               # not drawn with this pattern: leave it as it is
    # a row or column of the picture's edge outline (black all along) holds black where the pattern is not: those are not hatching
    odd = [p for p in inside if p not in set(fits)]
    rows = {y for y in {p[1] for p in odd} if sum(1 for p in odd if p[1] == y) >= 3}
    cols = {x for x in {p[0] for p in odd} if sum(1 for p in odd if p[0] == x) >= 3}
    return [p for p in fits if p[1] not in rows and p[0] not in cols], ink


def rehatch(img: pygame.Surface, key, at: tuple) -> pygame.Surface:
    """The picture as the original draws it at screen position `at` (its top-left corner): the hatching in that phase."""
    phase = (at[0] % 8, at[1] % 8)
    same = (phase[0] - phase[1]) % 8 == (BAKED[0] - BAKED[1]) % 8           # the pattern repeats along its diagonal
    if same:
        return img
    k = (key, phase)
    if k not in _cache:
        plan = _plan(img)
        if plan is None:
            _cache[k] = img
        else:
            fits, ink = plan
            out = img.copy()
            for x, y in fits:
                out.set_at((x, y), ink if _bit(x, y, *phase) else (0, 0, 0))
            _cache[k] = out
    return _cache[k]
