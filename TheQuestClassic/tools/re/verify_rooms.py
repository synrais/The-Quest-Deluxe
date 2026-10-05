"""Differential test: leaving one screen and arriving on the next (goroom2 + enemycheck) in the original, running in the
emulator, against the port's World.leave_room() + enter_room().

Random screens of every level; the live screen differs from the map as it was on arrival (creatures walked about, loot
dropped, a door opened), the hero steps across a random edge. Compared afterwards: every map square (what was written
back for the screen left), and the creature list of the screen arrived on.

usage: python verify_rooms.py [level ...] [--cases N]
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

SQ = ('floor', 'wall', 'mon', 'item', 'gold', 'deco')


def run_case(emu, g, level, grid0, screen, rng, ems):
    from engine import rules
    sx, sy = screen
    ox, oy = sx * 10, sy * 10                       # absolute x = ox + room index
    live = copy.deepcopy(grid0)                     # the live screen: creatures have walked about, loot has dropped
    cells = [(x, y) for x in range(ox + 1, ox + 11) for y in range(oy + 1, oy + 11)]
    for x, y in cells:
        q = live[x][y]
        if q.mon > 0 and rng.random() < 0.7:
            free = [(a, b) for a, b in cells if live[a][b].wall == 0 and live[a][b].mon == 0 and live[a][b].item != 999]
            if free:
                a, b = rng.choice(free)
                live[a][b].mon, q.mon = q.mon, 0
    for x, y in rng.sample(cells, 5):
        if live[x][y].wall == 0 and live[x][y].mon == 0:
            live[x][y].mon = rng.choice([1, 2, 3, 5, -3, 23, -101])         # more creatures, allies, a revealed wraith
    for x, y in rng.sample(cells, 6):
        if live[x][y].wall == 0:
            live[x][y].gold = rng.choice([0, 0, 9, 40])
            live[x][y].item = rng.choice([0, 0, 1, 2, 101])
    for x, y in rng.sample(cells, 3):
        live[x][y].deco = 1                                                  # an opened door
    # the hero steps across an edge of the screen: east, west, south or north (not out of the map)
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    rng.shuffle(dirs)
    for dx, dy in dirs:
        old = (ox + (10 if dx > 0 else 1 if dx < 0 else rng.randint(1, 10)),
               oy + (10 if dy > 0 else 1 if dy < 0 else rng.randint(1, 10)))
        new = (old[0] + dx, old[1] + dy)
        if 1 <= new[0] <= 100 and 1 <= new[1] <= 100 and grid0[new[0]][new[1]].wall == 0:
            break
    else:
        return None
    lax, lay = old[0] - ox, old[1] - oy
    nox, noy = (new[0] - 1) // 10 * 10, (new[1] - 1) // 10 * 10
    ax, ay = new[0] - nox, new[1] - noy
    seed = rng.randint(0, 0xFFFF)
    # the arrival values of the screen, as the port's event layer keeps them (the loot rule needs them)
    arrival = {(x, y): {f: getattr(grid0[x][y], f) for f in SQ} for x, y in cells}
    # ── the port ──
    w = g.world
    w.level = level
    w.grid = copy.deepcopy(live)
    w.origin = (ox + 1, oy + 1)
    p = g.player
    p.X, p.Y = old
    g.status.ems = ems
    rules.srand(seed)
    w.leave_room(ems, arrival if ems else None)
    p.X, p.Y = new
    w.enter_room(p, g.status)
    # ── the original ──
    emu.load_map(grid0)
    emu.uc.mem_write(emu.cell('_room', 0, 0), bytes(12 * 12 * 12))
    for i in range(1, 11):
        for j in range(1, 11):
            q = live[ox + i][oy + j]
            emu.set_square('_room', i, j, **{f: getattr(q, f) for f in SQ})
            emu.set_square('_map', ox + i, oy + j, **{f: getattr(grid0[ox + i][oy + j], f) for f in SQ})
    emu.set_word('_X', new[0])
    emu.set_word('_Y', new[1])
    emu.set_word('_ax', lax + dx)                   # (main2 has stepped: ax, ay are 0 or 11 for a step off the screen)
    emu.set_word('_ay', lay + dy)
    emu.set_word('_turns', 3)
    emu.set_word('_leaving', 0)
    emu.set_struct('_st', ST_F, {'mons': 0, 'ems': ems, 'level': level, 'Shield': 0, 'fShield': 0})
    emu.set_struct('_hero', HERO_F, {'rep': 0, 'invisible': -1})
    emu.call(emu.addr['_srand'], seed & 0xFFFF)
    emu.call('goroom', lax, lay)
    from unicorn.x86_const import UC_X86_REG_AX
    count = emu.uc.reg_read(UC_X86_REG_AX)                # (main2: st.mons = the count goroom returns, in AX)
    diffs = []
    for x in range(1, 101):
        for y in range(1, 101):
            a = emu.get_square('_map', x, y)
            q = w.grid[x][y]
            b = {f: getattr(q, f) for f in SQ}
            if a != b:
                diffs.append(f'map({x},{y}): original {a} port {b}')
    n = count & 0xFFFF
    orig = [(e['type'], e['x'], e['y']) for e in emu.enemies(n)]
    mine = [(e.type, e.x - nox, e.y - noy) for e in w.enemies]
    if orig != mine:
        diffs.append(f'creatures on the new screen: original {orig} port {mine}')
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
    rng = pyrandom.Random(11)
    total = bad = 0
    for level in levels:
        grid0 = data.load_level(level)
        screens = sorted({((x - 1) // 10, (y - 1) // 10) for x in range(1, 101) for y in range(1, 101)
                          if grid0[x][y].mon != 0})
        for c in range(cases):
            screen = rng.choice(screens)
            ems = rng.choice([0, 0, 2])
            try:
                diffs = run_case(emu, g, level, grid0, screen, rng, ems)
            except Exception as err:          # noqa: BLE001
                import traceback
                diffs = [f'error: {type(err).__name__}: {err}', traceback.format_exc()[-700:]]
            if diffs is None:
                continue
            total += 1
            if diffs:
                bad += 1
                print(f'level {level} screen {screen} ems {ems}')
                for d in diffs[:6]:
                    print('    ', d)
    print(f'{total - bad} of {total} checks identical')
    return bad


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    n = 30
    if '--cases' in sys.argv:
        n = int(sys.argv[sys.argv.index('--cases') + 1])
        args = [a for a in args if a != str(n)]
    sys.exit(1 if main([int(a) for a in args] or list(range(1, 8)), n) else 0)
