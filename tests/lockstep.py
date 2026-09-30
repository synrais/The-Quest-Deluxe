"""Deluxe playing the Quest I pack must play exactly like the classic port.

Both engines run side by side with the same random seed. Each run starts a game (a new hero of
a random class on a random level and screen, or the title's New Game), then presses the same
random keys in both. After every key the two screens must be identical pixel for pixel, and so
must the game state: hero, inventory, skills, status, bag, spells, the whole map and the
creatures. The first difference stops the run and is reported with the keys that led to it.

    python tests/lockstep.py                 # 40 runs of 300 keys
    python tests/lockstep.py --runs 5 --keys 100 --seed 7
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
from dataclasses import asdict

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import pygame  # noqa: E402


def load_edition(alias: str, folder: str):
    """Both editions call their code engine/: import each under its own name, so they can run side by
    side (the engines import their own modules relatively, so any name works)."""
    import importlib.util
    package_dir = os.path.join(REPO, folder, 'engine')
    spec = importlib.util.spec_from_file_location(alias, os.path.join(package_dir, '__init__.py'),
                                                  submodule_search_locations=[package_dir])
    module = sys.modules[alias] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


load_edition('classic', 'classic')             # classic.game, classic.rules ...: The Quest, the faithful port
load_edition('deluxe', 'TheQuestDeluxe')       # deluxe.game, deluxe.rules ...: The Quest Deluxe

pygame.init()
pygame.display.set_mode((640, 480))

import classic.game as classic  # noqa: E402
import classic.rules as classic_rules  # noqa: E402
import deluxe.game as deluxe  # noqa: E402
import deluxe.rules as deluxe_rules  # noqa: E402
from classic.savefile import Slots as ClassicSlots  # noqa: E402
from deluxe.savefile import Slots as DeluxeSlots  # noqa: E402

K = pygame
MOVES = [K.K_LEFT, K.K_RIGHT, K.K_UP, K.K_DOWN]
OTHER = [K.K_RETURN, K.K_SPACE, K.K_TAB, K.K_s, K.K_i, K.K_c, K.K_k, K.K_y, K.K_n, K.K_ESCAPE,
         K.K_b, K.K_v, K.K_l] + [K.K_1 + n for n in range(8)] + [K.K_F1 + n for n in range(9)]


def pick_key(rnd: random.Random) -> int:
    return rnd.choice(MOVES) if rnd.random() < 0.7 else rnd.choice(OTHER)


def state(g) -> dict:
    """Everything that must match, as plain values."""
    p, w = g.player, g.world
    grid = tuple((q.floor, q.wall, q.mon, q.item, q.gold, q.deco)
                 for col in w.grid for q in col) if w.grid else ()
    return {
        'hero': asdict(p.hero), 'inv': asdict(p.inv), 'skill': asdict(p.skill),
        'status': asdict(g.status), 'bag': sorted(p.bag.items()), 'spells': list(p.spells),
        'book': list(p.book), 'fkey': list(p.fkey), 'pos': (p.X, p.Y), 'level': w.level,
        'visited': sorted(w.visited), 'origin': w.origin, 'grid': hash(grid),
        'enemies': [asdict(e) for e in w.enemies],
        'overlay': type(g.overlay).__name__, 'messages': [str(m) for m in g.messages],
        'talk': list(g.talk_log), 'running': g.running, 'target': None if g.target is None else (g.target.x, g.target.y),
    }


def frame(g) -> bytes:
    g.renderer.draw(g)
    return pygame.image.tobytes(g.renderer.screen, 'RGB')


def diff(a: dict, b: dict) -> str:
    for k in a:
        if a[k] != b.get(k):
            return f'{k}: classic {a[k]!r:.300}\n            deluxe  {b.get(k)!r:.300}'
    return ''


class Pair:
    def __init__(self, seed: int):
        self.tmp = tempfile.mkdtemp()
        classic_rules.srand(seed)
        deluxe_rules.srand(seed)
        self.c = classic.Game(pygame.Surface((640, 480)))
        self.d = deluxe.Game(pygame.Surface((640, 480)))
        self.c.slots = ClassicSlots(os.path.join(self.tmp, 'c'))
        self.d.slots = DeluxeSlots(os.path.join(self.tmp, 'd'))

    def both(self, fn):
        fn(self.c)
        fn(self.d)

    def key(self, k: int) -> str:
        """Press k in both; a crash is reported (the same crash in both is still a crash)."""
        ev = pygame.event.Event(pygame.KEYDOWN, key=k, unicode='')
        out = []
        for name, g in (('classic', self.c), ('deluxe', self.d)):
            try:
                g.handle(ev)
            except Exception as e:                 # noqa: BLE001
                import traceback
                tb = traceback.extract_tb(e.__traceback__)[-1]
                out.append(f'{name} crashed: {type(e).__name__}: {e} ({os.path.basename(tb.filename)}:{tb.lineno})')
        return '; '.join(out)

    def check(self) -> str:
        a, b = state(self.c), state(self.d)
        why = diff(a, b)
        if why:
            return why
        if frame(self.c) != frame(self.d):
            return 'the screens differ'
        return ''


def setup(pair: Pair, rnd: random.Random) -> str:
    """Start the run: the title's New Game, or a hero dropped on a random level and screen."""
    if rnd.random() < 0.15:
        pair.key(K.K_RETURN)
        return 'title: New Game'
    cls, skill, fault = rnd.randint(1, 4), rnd.randint(0, 5), rnd.randint(0, 3)
    level = rnd.randint(1, 7)
    x, y = rnd.randint(1, 100), rnd.randint(1, 100)
    rich = rnd.random() < 0.5
    hurt = rnd.random()

    def go(g):
        g.overlay = None
        g.start_level = level
        g.player = g.player.__class__()
        g.start_new(cls, skill, fault)
        g.overlay = None
        g.goto_level(level)
        w = g.world
        if w.sq(x, y).wall == 0 and w.sq(x, y).mon == 0:
            w.leave_room()
            g.player.X, g.player.Y = x, y
            w.enter_room(g.player, g.status)
            g.count_hostiles()
            g.events.on_enter_room()
        if rich:                                  # strong enough to see more of the game
            h = g.player.hero
            h.mlife, h.mmana = 400, 200
            h.life, h.mana = max(1, int(400 * hurt)), int(200 * hurt)
            h.bintl = h.bstr = 40
            g.player.spells = [0] + [1] * 20
            g.player.book = list(range(1, 21))
            for f in ('rose', 'red', 'purple', 'blue', 'yellow', 'white', 'cyan', 'black'):
                setattr(g.player.inv, f, 3)
        g.messages = []
    pair.both(go)
    return f'class {cls} skill {skill} fault {fault} level {level} at ({x}, {y}){" rich" if rich else ""}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=40)
    ap.add_argument('--keys', type=int, default=300)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    bad = 0
    for run in range(a.runs):
        seed = a.seed * 1000 + run
        rnd = random.Random(seed)
        pair = Pair(seed)
        how = setup(pair, rnd)
        why = pair.check()
        keys = []
        for _ in range(a.keys):
            if why or not pair.c.running:
                break
            k = pick_key(rnd)
            keys.append(pygame.key.name(k))
            why = pair.key(k) or pair.check()
        if why:
            bad += 1
            print(f'run {run} (seed {seed}, {how}): differs after {len(keys)} keys')
            print(f'   last keys: {" ".join(keys[-15:])}')
            print(f'   {why}')
    print(f'{a.runs - bad} of {a.runs} runs identical ({a.keys} keys each)')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
