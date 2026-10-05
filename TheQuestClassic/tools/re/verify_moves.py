"""Differential test: the creatures' turn (monsmove: chase, fight, wander) in the original, running in the emulator, against
the port's ai.monsmove(), on random screens of every level with the hero on a random square, for several turns in a row.
Compared after every turn: where every creature stands, its life, and the screen's creature squares.

usage: python verify_moves.py [level ...] [--cases N]
"""
from __future__ import annotations

import copy
import os
import random as pyrandom
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import port                                         # noqa: E402,F401

import pygame  # noqa: E402

from verify_events import HERO_F, ST_F  # noqa: E402


def run_case(emu, g, level, grid0, hero, seed, turns, invisible):
    from engine import rules, ai
    hx, hy = hero
    w, p = g.world, g.player
    w.level = level
    g.status.level = level
    w.grid = copy.deepcopy(grid0)
    p.X, p.Y = hx, hy
    p.hero.invisible = invisible
    p.hero.rep = 0
    w.visited = set()
    w.enter_room(p, g.status)
    g.events.on_enter_room()
    ox, oy = w.origin
    ens = w.enemies
    emu.load_map(grid0)
    emu.load_room_from_map(hx, hy)
    emu.set_word('_X', hx)
    emu.set_word('_Y', hy)
    emu.set_word('_ax', hx - ox + 1)
    emu.set_word('_ay', hy - oy + 1)
    emu.set_word('_leaving', 0)
    emu.set_struct('_st', ST_F, {'mons': len(ens), 'ems': 0, 'level': level, 'Shield': 0, 'fShield': 0})
    emu.set_struct('_hero', HERO_F, {'rep': 0, 'invisible': invisible, 'life': 50, 'mlife': 50, 'warm': 0, 'marm': 0})
    p.hero.life = p.hero.mlife = 50
    emu.set_enemies([dict(type=e.type, x=e.x - ox + 1, y=e.y - oy + 1, life=e.life, mlife=e.mlife, atk=e.atk,
                          defense=e.defense, power=e.power, range=e.range, warm=e.warm, marm=e.marm, att=e.att)
                     for e in ens])
    emu.call(emu.addr['_srand'], seed & 0xFFFF)
    rules.srand(seed & 0xFFFF)
    diffs = []
    for turn in range(turns):
        for k in range(100):
            emu.uc.mem_write(emu.gaddr('_move') + 2 * k, b'\0\0')
        for e in ens:
            e.moved = False
        emu.call('monsmove')
        ai.monsmove(g)
        n = len(ens)
        orig = [(e['type'], e['x'], e['y'], e['life']) for e in emu.enemies(n)]
        mine = [(e.type, e.x - ox + 1, e.y - oy + 1, e.life) for e in ens]
        if orig != mine:
            diffs.append(f'turn {turn + 1}: original {orig} port {mine}')
            break
    return diffs


def main(levels, cases):
    pygame.init()
    win = pygame.display.set_mode((640, 480))
    from emu_game import GameEmu
    from engine.game import Game
    from engine.formats import GameData
    data = GameData.load()
    g = Game(win, data)
    g.overlay = None
    emu = GameEmu()
    emu.load_tables(data)
    rng = pyrandom.Random(5)
    total = bad = 0
    for level in levels:
        grid0 = data.load_level(level)
        screens = sorted({((x - 1) // 10, (y - 1) // 10) for x in range(1, 101) for y in range(1, 101)
                          if grid0[x][y].mon != 0})
        for c in range(cases):
            sx, sy = rng.choice(screens)
            free = [(x, y) for x in range(sx * 10 + 1, sx * 10 + 11) for y in range(sy * 10 + 1, sy * 10 + 11)
                    if grid0[x][y].wall == 0 and grid0[x][y].mon == 0]
            if not free:
                continue
            hero = rng.choice(free)
            seed = rng.randint(0, 0xFFFF)
            invisible = rng.choice([-1, -1, -1, 5])
            try:
                diffs = run_case(emu, g, level, grid0, hero, seed, 6, invisible)
            except Exception as err:          # noqa: BLE001
                import traceback
                diffs = [f'error: {type(err).__name__}: {err}', traceback.format_exc()[-700:]]
            total += 1
            if diffs:
                bad += 1
                print(f'level {level} hero {hero} invisible {invisible} seed {seed}')
                for d in diffs[:4]:
                    print('    ', d)
    print(f'{total - bad} of {total} checks identical')
    return bad


def one(level, x, y, seed, invisible, turns=1):
    """Run a single case (to look into a difference): python verify_moves.py --case LEVEL X Y SEED INVISIBLE"""
    pygame.init()
    win = pygame.display.set_mode((640, 480))
    from emu_game import GameEmu
    from engine.game import Game
    from engine.formats import GameData
    data = GameData.load()
    g = Game(win, data)
    g.overlay = None
    emu = GameEmu()
    emu.load_tables(data)
    grid0 = data.load_level(level)
    for d in run_case(emu, g, level, grid0, (x, y), seed, turns, invisible):
        print(d)
    return emu, g


if __name__ == '__main__' and '--case' in sys.argv:
    a = sys.argv[sys.argv.index('--case') + 1:]
    one(*[int(v) for v in a[:5]])
    sys.exit(0)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    n = 30
    if '--cases' in sys.argv:
        n = int(sys.argv[sys.argv.index('--cases') + 1])
        args = [a for a in args if a != str(n)]
    sys.exit(1 if main([int(a) for a in args] or list(range(1, 8)), n) else 0)
