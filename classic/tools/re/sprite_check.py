"""Compare the ripped sprites in sprites/ with what TheQuest.exe itself draws.

Each sprite is drawn by running the game's own code in the emulator (emu.py): clean2() for map
squares, guy2() for the heroes and the spell-book icon functions for spells. The result is compared
pixel by pixel with the PNG:

  wrong colour      both drawn, different colours
  missing           the game draws the pixel but the PNG has it transparent
  extra             the PNG has a pixel where the game draws nothing (leftover background)

usage: python sprite_check.py [name-filter]  -> out/sprites/report.txt and a side-by-side PNG per sprite
"""
from __future__ import annotations

import os
import re
import struct
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
SPRITES = os.path.join(PROJECT, 'sprites')
OUT = os.path.join(HERE, 'out', 'sprites')
UNTOUCHED = (1, 2, 3)          # not an EGA colour: marks pixels the game never drew

SPELL_FUNCS = {1: 'heal', 2: 'flame', 3: 'teleport', 4: 'shield', 5: 'icering', 6: 'blackward',
               7: 'invisibility', 8: 'sskeleton', 9: 'inferno', 10: 'restore', 11: 'drain', 12: 'thunder',
               13: 'fshield', 14: 'deteriorate', 15: 'sstoneknight', 16: 'earthq', 17: 'cure',
               18: 'sscorpion', 19: 'deaths', 20: 'darkhour'}
CLASS = {'Knight': 1, 'Mage': 2, 'Rogue': 3, 'Monk': 4}
NAME_RE = re.compile(r'^(floor|wall|enemy|object|extra|spell)_(-?\d+)')


def original(emu, kind, n):
    """(surface, x, y) of the game's own drawing for this sprite, on an UNTOUCHED background."""
    emu.surface.fill(UNTOUCHED)
    if kind == 'spell':
        emu.call(SPELL_FUNCS[n], 13, 2)          # spell book, left column, first row
        return emu.surface, 440, 45
    if kind == 'hero':
        status = [0] * 14
        hero = [0] * 23
        hero[20] = CLASS[n]                      # heroo.type
        hero[21] = -1                            # heroo.invisible
        emu.call('guy2', 2, 2, *status, *hero)
        return emu.surface, 40, 40
    field = {'floor': 'floor', 'wall': 'wall', 'enemy': 'mon', 'object': 'item', 'extra': 'deco',
             'gold': 'gold'}[kind]
    emu.draw_tile(2, 2, **{field: n})
    return emu.surface, 40, 40


def compare(orig, ox, oy, png):
    """Counts and a per-pixel status grid for the 40x40 tile."""
    counts = {'same': 0, 'wrong colour': 0, 'missing': 0, 'extra': 0}
    grid = []
    for y in range(40):
        row = []
        for x in range(40):
            o = tuple(orig.get_at((ox + x, oy + y)))[:3]
            r, g, b, a = png.get_at((x, y)) if x < png.get_width() and y < png.get_height() else (0, 0, 0, 0)
            drawn, have = o != UNTOUCHED, a > 0
            if drawn and have:
                st = 'same' if (r, g, b) == o else 'wrong colour'
            elif drawn:
                st = 'missing'
            elif have:
                st = 'extra'
            else:
                st = None
            if st:
                counts[st] += 1
            row.append(st)
        grid.append(row)
    return counts, grid


def side_by_side(orig, ox, oy, png, grid, path):
    z = 8
    out = pygame.Surface((40 * z * 3 + 20, 40 * z))
    out.fill((40, 40, 40))
    tile = pygame.Surface((40, 40))
    tile.fill((255, 0, 255))
    for y in range(40):
        for x in range(40):
            c = tuple(orig.get_at((ox + x, oy + y)))[:3]
            if c != UNTOUCHED:
                tile.set_at((x, y), c)
    out.blit(pygame.transform.scale(tile, (40 * z, 40 * z)), (0, 0))
    mine = pygame.Surface((40, 40))
    mine.fill((255, 0, 255))
    mine.blit(png, (0, 0))
    out.blit(pygame.transform.scale(mine, (40 * z, 40 * z)), (40 * z + 10, 0))
    diff = pygame.Surface((40, 40))
    colours = {'same': (60, 60, 60), 'wrong colour': (255, 255, 0), 'missing': (255, 0, 0), 'extra': (0, 160, 255)}
    diff.fill((0, 0, 0))
    for y in range(40):
        for x in range(40):
            if grid[y][x]:
                diff.set_at((x, y), colours[grid[y][x]])
    out.blit(pygame.transform.scale(diff, (40 * z, 40 * z)), (80 * z + 20, 0))
    pygame.image.save(out, path)


def main(filt=''):
    pygame.init()
    pygame.display.set_mode((640, 480))
    sys.path.insert(0, HERE)
    from emu import Emu
    emu = Emu()
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for f in sorted(os.listdir(SPRITES)):
        if not f.lower().endswith('.png') or filt not in f:
            continue
        stem = f[:-4]
        m = NAME_RE.match(stem)
        if m:
            kind, n = m.group(1), int(m.group(2))
        elif stem.startswith('hero_'):
            kind, n = 'hero', stem[5:]
        elif stem == 'gold':
            kind, n = 'gold', 1
        else:
            rows.append((stem, 'skipped: not a known sprite name'))
            continue
        png = pygame.image.load(os.path.join(SPRITES, f)).convert_alpha()
        try:
            orig, ox, oy = original(emu, kind, n)
        except Exception as err:            # noqa: BLE001 - report and carry on
            rows.append((stem, f'could not draw: {err}'))
            continue
        counts, grid = compare(orig, ox, oy, png)
        bad = counts['wrong colour'] + counts['missing'] + counts['extra']
        shift = ''
        if bad:
            # a sprite cut from the screen on a different grid is the right picture, just moved
            def cost(d):
                c = compare(orig, ox + d[0], oy + d[1], png)[0]
                return c['wrong colour'] + c['missing'] + c['extra']
            best = min(((dx, dy) for dx in range(-4, 5) for dy in range(-4, 5)), key=cost)
            b2 = cost(best)
            if best != (0, 0) and b2 < bad:
                shift = f'  [picture offset by {best[0]:+d},{best[1]:+d} px; with that offset {b2} px differ]'
        verdict = 'EXACT' if bad == 0 else f"{bad} px differ ({counts['wrong colour']} wrong colour, " \
                                            f"{counts['missing']} missing, {counts['extra']} extra)"
        verdict += shift
        if png.get_size() != (40, 40):
            verdict += f'  [PNG is {png.get_width()}x{png.get_height()}]'
        rows.append((stem, verdict))
        if bad:
            side_by_side(orig, ox, oy, png, grid, os.path.join(OUT, re.sub(r'[\[\]]', '', stem) + '.png'))
    with open(os.path.join(OUT, 'report.txt'), 'w', encoding='utf-8') as fh:
        for stem, v in rows:
            fh.write(f'{stem:45s} {v}\n')
    for stem, v in rows:
        print(f'{stem:45s} {v}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '')
