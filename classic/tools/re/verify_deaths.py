"""Differential test: the engine's deadenemycheck() port (combat.check_dead + common.qs + level scripts)
against the original running in the emulator.

Random screens from every level, with random creatures dead, a random killer (the hero or a creature),
random quest counters and hero positions (including the scripted trigger squares). Compared afterwards:
messages printed, experience, gold on the ground, items dropped, bodies, reputation, poison, m1/m2,
the hero's square, every map square and the creature list.

usage: python verify_deaths.py [level ...] [--cases N]
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
import port                                         # noqa: E402,F401  (QUEST_ENGINE=deluxe checks Deluxe)

import pygame  # noqa: E402

from verify_events import HERO_F, INV_F, ST_F  # noqa: E402

# squares where the per-turn checks start conversations, to make sure they are exercised
HOTSPOTS = {1: [(85, 95)], 2: [(5, 75)], 3: [(5, 75)], 4: [(75, 5)], 6: [(75, 55)],
            7: [(90, 67), (10, 46), (80, 6)]}


def run_case(emu, g, level, grid0, hero, state, dead, killer, seed):
    from engine import rules
    hx, hy = hero
    g.world.level = level
    g.status.level = level
    g.world.grid = copy.deepcopy(grid0)
    p = g.player
    p.X, p.Y = hx, hy
    g.world.visited = set()
    g.world.enter_room(p, g.status)
    g.events.on_enter_room()
    ens = g.world.enemies
    for k, (life, att) in dead.items():
        if k < len(ens):
            ens[k].life, ens[k].att = life, att
    g.status.mission1, g.status.mission2 = state['m1'], state['m2']
    p.hero.rep, p.hero.exper, p.hero.poisoned = state['rep'], 500, 0
    p.hero.life = p.hero.mlife = 50
    p.skill.hon = state['hon']
    g.talk_log = []
    ox, oy = g.world.origin
    emu.load_map(grid0)
    emu.load_room_from_map(hx, hy)
    emu.set_word('_X', hx)
    emu.set_word('_Y', hy)
    emu.set_word('_ax', hx - ox + 1)
    emu.set_word('_ay', hy - oy + 1)
    emu.set_word('_otarw', -1)
    emu.set_word('_leaving', 0)
    emu.set_struct('_st', ST_F, {'mons': len(ens), 'ems': 0, 'level': level, 'mission1': state['m1'],
                                 'mission2': state['m2'], 'Shield': 0, 'fShield': 0})
    emu.set_struct('_hero', HERO_F, {'rep': state['rep'], 'exper': 500, 'poisoned': 0, 'life': 50, 'mlife': 50,
                                     'invisible': -1, 'warm': 0, 'marm': 0})
    emu.set_struct('_skill', ['amb', 'bar', 'sch', 'mem', 'mar', 'cow', 'hon', 'ras'], {'hon': state['hon']})
    emu.set_enemies([dict(type=e.type, x=e.x - ox + 1, y=e.y - oy + 1, life=e.life, mlife=e.mlife, atk=e.atk,
                          defense=e.defense, power=e.power, range=e.range, warm=e.warm, marm=e.marm, att=e.att)
                     for e in ens])
    for k in range(100):
        emu.uc.mem_write(emu.gaddr('_move') + 2 * k, b'\0\0')
    emu.call(emu.addr['_srand'], seed & 0xFFFF)
    rules.srand(seed & 0xFFFF)
    emu.texts = []
    att_enemy = ens[killer] if 0 <= killer < len(ens) else None
    emu.call('deadenemycheck', killer if att_enemy is not None else -1)
    g.combat.check_dead(att_enemy)
    diffs = []
    mine = []
    for t in g.talk_log:
        if t:
            mine += [t[0], t[1]]
    theirs = [t for t in emu.texts]
    if mine != theirs:
        diffs.append(f'messages: original {theirs!r} port {mine!r}')
    st = emu.get_struct('_st', ST_F)
    if (st['mission1'], st['mission2']) != (g.status.mission1, g.status.mission2):
        diffs.append(f"m1/m2: original {st['mission1'], st['mission2']} port {g.status.mission1, g.status.mission2}")
    h = emu.get_struct('_hero', HERO_F)
    for f, mine_v in (('rep', p.hero.rep), ('exper', p.hero.exper), ('poisoned', p.hero.poisoned),
                      ('life', p.hero.life)):
        if h[f] != mine_v:
            diffs.append(f'{f}: original {h[f]} port {mine_v}')
    hon = emu.get_struct('_skill', ['amb', 'bar', 'sch', 'mem', 'mar', 'cow', 'hon', 'ras'])['hon']
    if hon != p.skill.hon:
        diffs.append(f'honor: original {hon} port {p.skill.hon}')
    ex, ey = emu.get_word('_X'), emu.get_word('_Y')
    if (ex, ey) != (p.X, p.Y):
        diffs.append(f'hero: original {(ex, ey)} port {(p.X, p.Y)}')
    emu.store_room_to_map(hx, hy)
    for x in range(1, 101):
        for y in range(1, 101):
            a = emu.get_square('_map', x, y)
            q = g.world.grid[x][y]
            b = {f: getattr(q, f) for f in ('floor', 'wall', 'mon', 'item', 'gold', 'deco')}
            if a != b:
                diffs.append(f'map({x},{y}): original {a} port {b}')
    n = st['mons']
    orig_en = [(e['type'], e['x'], e['y'], e['life'], e['att']) for e in emu.enemies(n)]
    port_en = [(e.type, e.x - ox + 1, e.y - oy + 1, e.life, e.att) for e in g.world.enemies]
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
    rng = pyrandom.Random(7)
    total = bad = 0
    for level in levels:
        grid0 = data.load_level(level)
        screens = sorted({((x - 1) // 10, (y - 1) // 10) for x in range(1, 101) for y in range(1, 101)
                          if grid0[x][y].mon != 0})
        for c in range(cases):
            if level in HOTSPOTS and rng.random() < 0.3:
                hero = rng.choice(HOTSPOTS[level])
            else:
                sx, sy = rng.choice(screens)
                free = [(x, y) for x in range(sx * 10 + 1, sx * 10 + 11) for y in range(sy * 10 + 1, sy * 10 + 11)
                        if grid0[x][y].wall == 0 and grid0[x][y].mon == 0]
                if not free:
                    continue
                hero = rng.choice(free)
            ox, oy = (hero[0] - 1) // 10 * 10, (hero[1] - 1) // 10 * 10
            n = sum(1 for x in range(ox + 1, ox + 11) for y in range(oy + 1, oy + 11) if grid0[x][y].mon != 0)
            if n == 0:
                continue
            dead = {k: (rng.choice([0, -3, 0, 5, 30]), rng.choice([9, 9, -1, 8, -5])) for k in range(n)
                    if rng.random() < 0.6}
            killer = rng.choice([-1, -1, -1, rng.randrange(n)])
            state = dict(m1=rng.randint(0, 4), m2=rng.randint(0, 7), rep=rng.randint(-5, 7), hon=rng.choice([0, 1, 2]))
            seed = rng.randint(0, 0xFFFF)
            try:
                diffs = run_case(emu, g, level, grid0, hero, state, dead, killer, seed)
            except Exception as err:          # noqa: BLE001
                import traceback
                diffs = [f'error: {type(err).__name__}: {err}', traceback.format_exc()[-600:]]
            total += 1
            if diffs:
                bad += 1
                print(f'level {level} hero {hero} killer {killer} dead {dead} state {state}')
                for d in diffs[:6]:
                    print('    ', d)
    print(f'{total - bad} of {total} checks identical')
    return bad


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    n = 40
    if '--cases' in sys.argv:
        n = int(sys.argv[sys.argv.index('--cases') + 1])
        args = [a for a in args if a != str(n)]
    sys.exit(1 if main([int(a) for a in args] or list(range(1, 8)), n) else 0)
