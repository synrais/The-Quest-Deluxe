"""Differential test: the ported level scripts against the original talk() running in the emulator.

For every talking NPC on a level, and many random game states (quest counters, reputation, gold, bag
contents, visited screens, random seed), both the original and the port handle the same conversation.
Everything they leave behind is compared: the message printed, m1/m2, reputation, gold, the hero's
square, the bag, every map square and the creature list.

usage: python verify_events.py [level ...] [--cases N]
"""
from __future__ import annotations

import copy
import os
import random as pyrandom
import struct
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import port                                         # noqa: E402,F401  (QUEST_ENGINE=deluxe checks Deluxe)

import pygame  # noqa: E402

ST_F = ['mons', 'ems', 'killer', 'armboost', 'powboost', 'Shield', 'fShield', 'level', 'mission1', 'mission2',
        'saveslot', 'p1', 'p2', 'p3']
HERO_F = ['mlife', 'life', 'mmana', 'mana', 'bstr', 'bintl', 'bdex', 'bacc', 'dex', 'acc', 'intl', 'str', 'defense',
          'atk', 'rep', 'power', 'warm', 'marm', 'level', 'exper', 'type', 'invisible', 'poisoned']
INV_F = ['bkey', 'rkey', 'ykey', 'coins', 'rose', 'red', 'purple', 'blue', 'white', 'cyan', 'yellow', 'black']
QUEST_ITEMS = [907, 11, 507, 9, 16, 17, 211, 505, 501, 205, 6, 2, 12, 13, 14, 5, 114, 508, 511]
DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
# talk(n) calls made by deadenemycheck() on each level
SCRIPTED = {1: [3], 2: [8], 3: [15], 4: [15], 5: [], 6: [34, 35, 36], 7: [41, 43, 45, -15]}


def enemies_for_screen(g):
    """The engine's creature list for the current screen, as enemycheck() builds it."""
    return [(e.type, e.x, e.y, e.life, e.mlife, e.atk, e.defense, e.power, e.range, e.warm, e.marm, e.att)
            for e in g.world.enemies]


def run_case(emu, g, level, grid0, npc_pos, hero_pos, state, seed, npc=None):
    from engine import rules
    from engine.formats import Square
    (nx, ny), (hx, hy) = npc_pos, hero_pos
    # ── engine ──
    g.world.level = level
    g.status.level = level
    g.world.grid = copy.deepcopy(grid0)
    p = g.player
    p.X, p.Y = hx, hy
    g.world.visited = set(state['visited'])
    g.world.enter_room(p, g.status)
    g.events.on_enter_room()
    g.status.mission1, g.status.mission2 = state['m1'], state['m2']
    g.status.ems = state['ems']
    p.hero.rep = state['rep']
    p.inv.coins = state['coins']
    p.bag = dict(state['bag'])
    g.talk_log = []
    ox, oy = g.world.origin
    ens = list(g.world.enemies)
    # ── original ──
    emu.load_map(grid0)
    emu.load_room_from_map(hx, hy)
    for x in range(12):
        for y in range(12):
            emu.set_int('_carta', x, y, 0)
    for sx, sy in state['visited']:
        emu.set_int('_carta', sx + 1, sy + 1, 1)
    for col in range(17):
        for row in range(13):
            emu.set_int('_bag', col, row, state['bag'].get((col, row), 0))
    emu.set_word('_X', nx)
    emu.set_word('_Y', ny)
    emu.set_word('_ax', hx - ox + 1)
    emu.set_word('_ay', hy - oy + 1)
    emu.set_struct('_st', ['mons', 'ems', 'killer', 'armboost', 'powboost', 'Shield', 'fShield', 'level',
                           'mission1', 'mission2', 'saveslot', 'p1', 'p2', 'p3'],
                   {'mons': len(ens), 'ems': state['ems'], 'level': level, 'mission1': state['m1'],
                    'mission2': state['m2']})
    emu.set_struct('_hero', ['mlife', 'life', 'mmana', 'mana', 'bstr', 'bintl', 'bdex', 'bacc', 'dex', 'acc',
                             'intl', 'str', 'defense', 'atk', 'rep', 'power', 'warm', 'marm', 'level', 'exper',
                             'type', 'invisible', 'poisoned'], {'rep': state['rep'], 'invisible': -1})
    emu.set_struct('_inv', ['bkey', 'rkey', 'ykey', 'coins', 'rose', 'red', 'purple', 'blue', 'white', 'cyan',
                            'yellow', 'black'], {'coins': state['coins']})
    emu.set_enemies([dict(type=e.type, x=e.x - ox + 1, y=e.y - oy + 1, life=e.life, mlife=e.mlife, atk=e.atk,
                          defense=e.defense, power=e.power, range=e.range, warm=e.warm, marm=e.marm, att=e.att)
                     for e in ens])
    for k in range(100):
        emu.uc.mem_write(emu.gaddr('_move') + 2 * k, b'\0\0')
    # ── run both from the same random seed ──
    emu.call(emu.addr['_srand'], seed & 0xFFFF)
    rules.srand(seed & 0xFFFF)
    emu.texts = []
    if npc is None:
        npc = grid0[nx][ny].mon
    emu.call('talk', npc)
    if npc_pos == hero_pos:
        g.events.talk(npc)
    else:
        g.events.talk(npc, nx, ny)
    # ── compare ──
    diffs = []
    text = g.talk_log[-1] if g.talk_log else None
    mine = (text[0], text[1]) if text else None
    theirs = tuple(emu.texts[-2:]) if len(emu.texts) >= 2 else None
    if mine != theirs:
        diffs.append(f'message: original {theirs!r} port {mine!r}')
    st = emu.get_struct('_st', ['mons', 'ems', 'killer', 'armboost', 'powboost', 'Shield', 'fShield', 'level',
                                'mission1', 'mission2', 'saveslot', 'p1', 'p2', 'p3'])
    if (st['mission1'], st['mission2']) != (g.status.mission1, g.status.mission2):
        diffs.append(f"m1/m2: original {st['mission1'], st['mission2']} port {g.status.mission1, g.status.mission2}")
    h = emu.get_struct('_hero', ['mlife', 'life', 'mmana', 'mana', 'bstr', 'bintl', 'bdex', 'bacc', 'dex', 'acc',
                                 'intl', 'str', 'defense', 'atk', 'rep'])
    if h['rep'] != p.hero.rep:
        diffs.append(f"rep: original {h['rep']} port {p.hero.rep}")
    inv = emu.get_struct('_inv', ['bkey', 'rkey', 'ykey', 'coins'])
    if inv['coins'] != p.inv.coins:
        diffs.append(f"coins: original {inv['coins']} port {p.inv.coins}")
    ex, ey = emu.get_word('_X') - (nx - hx), emu.get_word('_Y') - (ny - hy)
    if (ex, ey) != (p.X, p.Y):
        diffs.append(f'hero: original {(ex, ey)} port {(p.X, p.Y)}')
    for col in range(12, 17):
        for row in range(1, 13):
            a, b = emu.get_int('_bag', col, row), p.bag.get((col, row), 0)
            if a != b:
                diffs.append(f'bag[{col}][{row}]: original {a} port {b}')
    emu.store_room_to_map(hx, hy)
    for x in range(1, 101):
        for y in range(1, 101):
            a = emu.get_square('_map', x, y)
            q = g.world.grid[x][y]
            b = {f: getattr(q, f) for f in ('floor', 'wall', 'mon', 'item', 'gold', 'deco')}
            if a != b:
                diffs.append(f'map({x},{y}): original {a} port {b}')
    n = st['mons']
    orig_en = [(e['type'], e['x'], e['y'], e['life'], e['mlife'], e['atk'], e['defense'], e['power'], e['range'],
                e['warm'], e['marm'], e['att']) for e in emu.enemies(n)]
    port_en = [(e.type, e.x - ox + 1, e.y - oy + 1, e.life, e.mlife, e.atk, e.defense, e.power, e.range, e.warm,
                e.marm, e.att) for e in g.world.enemies]
    if orig_en != port_en:
        diffs.append(f'enemies: original {orig_en} port {port_en}')
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
    rng = pyrandom.Random(1)
    total = bad = 0
    for level in levels:
        grid0 = data.load_level(level)
        npcs = [(x, y) for x in range(1, 101) for y in range(1, 101) if -100 < grid0[x][y].mon <= -6]
        for nx, ny in npcs:
            spots = []
            for dx, dy in DIRS:
                hx, hy = nx - dx, ny - dy
                if 1 <= hx <= 100 and 1 <= hy <= 100 and (hx - 1) // 10 == (nx - 1) // 10 \
                        and (hy - 1) // 10 == (ny - 1) // 10 and grid0[hx][hy].wall == 0 and grid0[hx][hy].mon == 0:
                    spots.append((hx, hy))
            if not spots:
                continue
            for c in range(cases):
                bag = {}
                for it in rng.sample(QUEST_ITEMS, rng.randint(0, 4)):
                    bag[(rng.randint(12, 15), rng.choice([2, 4, 6, 8, 9, 10, 11]))] = it
                if rng.random() < 0.2:
                    for col in range(12, 16):
                        for row in range(8, 12):
                            bag.setdefault((col, row), 201)
                state = dict(m1=rng.choice([0, 1, 2, 3, 10, 11]), m2=rng.choice([0, 1, 2, 3]),
                             rep=rng.randint(-4, 7), coins=rng.choice([0, 49, 50, 500]), ems=rng.randint(0, 2),
                             visited={(rng.randint(0, 9), rng.randint(0, 9)) for _ in range(rng.randint(0, 12))},
                             bag=bag)
                if rng.random() < 0.5:
                    state['visited'].add((4, 0))
                hero = rng.choice(spots)
                seed = rng.randint(0, 0xFFFF)
                try:
                    diffs = run_case(emu, g, level, grid0, (nx, ny), hero, state, seed)
                except Exception as err:          # noqa: BLE001
                    diffs = [f'error: {type(err).__name__}: {err}']
                total += 1
                if diffs:
                    bad += 1
                    print(f'level {level} NPC {grid0[nx][ny].mon} at {(nx, ny)}, hero {hero}, state '
                          f"m1={state['m1']} m2={state['m2']} rep={state['rep']} coins={state['coins']} "
                          f"bag={state['bag']}")
                    for d in diffs[:6]:
                        print('    ', d)
        # scripted conversations started by deadenemycheck(): talk(n) with (X, Y) = the hero's square
        for npc in SCRIPTED.get(level, []):
            for c in range(cases * 4):
                boss = [(x, y) for x in range(1, 101) for y in range(1, 101) if grid0[x][y].mon == abs(npc)]
                if boss and rng.random() < 0.7:
                    bx, by = rng.choice(boss)
                    ox, oy = (bx - 1) // 10 * 10, (by - 1) // 10 * 10
                    free = [(x, y) for x in range(ox + 1, ox + 11) for y in range(oy + 1, oy + 11)
                            if grid0[x][y].wall == 0 and grid0[x][y].mon == 0]
                    hero = rng.choice(free) if free else (bx, by)
                else:
                    hero = (rng.randint(1, 100), rng.randint(1, 100))
                state = dict(m1=rng.randint(0, 7), m2=rng.randint(0, 7), rep=rng.randint(-4, 7),
                             coins=rng.choice([0, 500]), ems=rng.randint(0, 2), visited=set(), bag={})
                seed = rng.randint(0, 0xFFFF)
                try:
                    diffs = run_case(emu, g, level, grid0, hero, hero, state, seed, npc=npc)
                except Exception as err:          # noqa: BLE001
                    diffs = [f'error: {type(err).__name__}: {err}']
                total += 1
                if diffs:
                    bad += 1
                    print(f"level {level} scripted talk({npc}), hero {hero}, m1={state['m1']} m2={state['m2']}")
                    for d in diffs[:6]:
                        print('    ', d)
    print(f'{total - bad} of {total} conversations identical')
    return bad


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    n = 6
    if '--cases' in sys.argv:
        n = int(sys.argv[sys.argv.index('--cases') + 1])
        args = [a for a in args if a != str(n)]
    sys.exit(1 if main([int(a) for a in args] or list(range(1, 8)), n) else 0)
