"""Make sprites/bag/: the pictures the original draws for items in the bag and the shop.

These are not the map pictures: bagdraw() calls bigger, separate drawing routines (with the count for
ammunition). For every item this runs the exe's own dempty() + bagdraw() on one backpack cell in
the emulator and saves the 40x40 cell, grey background and all, exactly as the game shows it. Items
whose drawing reaches outside the cell are reported.

    python bag_icons.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import pygame                                       # noqa: E402

import emu_game                                     # noqa: E402

emu_game.MATRICES['_store'] = (17, 13, 1)
from emu import STACKSEG                            # noqa: E402
from emu_game import GameEmu                        # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'sprites', 'bag')
CELL = pygame.Rect(450, 290, 40, 40)                # backpack cell (12, 8)


def main():
    pygame.init()
    from quest2.formats import GameData
    data = GameData.load()
    items = sorted({r[0] for r in data.items if r} | set(range(1, 10)) | {11, 16, 17, 907} | set(range(601, 681)))
    emu = GameEmu()
    dempty = next(v for k, v in emu.addr.items() if k.startswith('@dempty$q'))
    bagdraw = next(v for k, v in emu.addr.items() if k.startswith('@bagdraw$q'))
    os.makedirs(OUT, exist_ok=True)
    spill = []
    for it in items:
        a = 2 if it < 9 else 1
        emu.surface.fill((0, 0, 0))
        emu.set_int('_bag', 12, 8, it)
        emu.set_int('_store', 12, 8, it)
        emu.call(dempty, 12, 8, 20, 10)
        words = [12, 8, a] + [0] * 10
        sp_entry = 0xFFF0 - 4 - 2 * len(words)
        emu._mat[emu.lin(STACKSEG, sp_entry + 4 + 12 - 6)] = '_bag'
        emu._mat[emu.lin(STACKSEG, sp_entry + 4 + 22 - 6)] = '_store'
        emu.call(bagdraw, *words)
        outside = pygame.mask.from_threshold(emu.surface, (0, 0, 0), (1, 1, 1, 255))
        outside.invert()
        outside.erase(pygame.mask.Mask(CELL.size, fill=True), CELL.topleft)
        if outside.count():
            spill.append((it, outside.get_bounding_rects()))
        pygame.image.save(emu.surface.subsurface(CELL).copy(), os.path.join(OUT, f'bag_{it}.png'))
    print(f'{len(items)} item pictures written to {OUT}')
    for it, rects in spill:
        print(f'   item {it} draws outside its cell: {rects}')


if __name__ == '__main__':
    main()
