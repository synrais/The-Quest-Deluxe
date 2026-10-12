"""Differential test: one whole turn of the game (a key, the hero's move or blow, then every creature's turn) in the original,
running in the emulator (main2() itself), against the port, on the screens of the last level and its boss fights.

What main2() does in a turn is what a person sees: the hero acts, creatures move, fight and cast, the dead fall, scenes play.
Both start from one state (hero, creatures, map squares, story counters, random seed) and are given the same key. Compared afterwards:
the hero (life, mana, experience, reputation, square, poison), the story counters, every creature (type, square, life, attack
state, and its numbers), every square of the screen, the messages printed, and the random number state: it is only the same when
both rolled exactly as many dice, in the same order.

usage: python verify_turns.py [--cases N] [--seed S] [--m2 K] [--only 45,44] [--keys 3] [--case ...]
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

import emu_game  # noqa: E402

emu_game.MATRICES['_items'] = (1000, 13, 1)         # Items.dat has 13 columns

from emu_game import GameEmu, HERO, INV, SKILL, STATUS  # noqa: E402
from verify_events import HERO_F, ST_F  # noqa: E402

SEED_AT = 0x2834                # DS offset of the C library's rand() state (a long)
KEYS = {'Left': [0, 75], 'Right': [0, 77], 'Up': [0, 72], 'Down': [0, 80], 'space': [32], 'Return': [13]}
PYGAME = {'Left': pygame.K_LEFT, 'Right': pygame.K_RIGHT, 'Up': pygame.K_UP, 'Down': pygame.K_DOWN, 'space': pygame.K_SPACE,
          'Return': pygame.K_RETURN}
for _n in range(1, 9):                                  # 1 to 8: the potions
    KEYS[str(_n)] = [ord(str(_n))]
    PYGAME[str(_n)] = getattr(pygame, f'K_{_n}')
NOT_RANDOM = ()
POTIONS = ('rose', 'red', 'purple', 'blue', 'yellow', 'white', 'cyan', 'black')
ENEMY_F = ('type', 'x', 'y', 'life', 'mlife', 'atk', 'defense', 'power', 'range', 'warm', 'marm', 'att')


class TurnEmu(GameEmu):
    """The emulator that runs main2() until it asks for the next key after the one it was given."""

    def __init__(self):
        super().__init__()
        from unicorn import UC_HOOK_CODE
        self.ticks = 0
        self.waits = []
        from unicorn.x86_const import UC_X86_REG_FPCW
        self.uc.reg_write(UC_X86_REG_FPCW, 0x037F)               # every x87 exception masked (an unmasked one made 'wait' spin for ever)
        self.died = False
        seg, off = self.addr['_clock']
        at = self.lin(seg, off)
        self._hooked[at] = 'clock'                         # the timer the key loop uses to slow a held key down: time passes between keys
        self.uc.hook_add(UC_HOOK_CODE, self._on_call, begin=at, end=at)
        seg, off = self.addr['_pow']                       # this emulator's x87 gets pow() with a fractional power wrong (sqrt(13) comes out 0):
        at = self.lin(seg, off)                            # a real x87 gives the right answer, so it is done here and put on the x87 stack by a two-instruction stub
        self._hooked[at] = 'pow'
        self.uc.hook_add(UC_HOOK_CODE, self._on_call, begin=at, end=at)
        self.uc.mem_write(0xF1000, bytes([0x2E, 0xDD, 0x06, 0x10, 0x00, 0xCB]))          # fld qword ptr cs:[0010h] ; retf

    def _on_call(self, uc, address, size, user):
        if self._hooked.get(address) == 'pow':
            import math
            from unicorn.x86_const import UC_X86_REG_SP, UC_X86_REG_SS, UC_X86_REG_CS, UC_X86_REG_IP
            sp, ss = uc.reg_read(UC_X86_REG_SP), uc.reg_read(UC_X86_REG_SS)
            x, y = struct.unpack('<dd', bytes(uc.mem_read(self.lin(ss, sp + 4), 16)))
            try:
                r = math.pow(x, y)
            except (ValueError, OverflowError):
                r = 0.0
            uc.mem_write(0xF1010, struct.pack('<d', r))
            uc.reg_write(UC_X86_REG_CS, 0xF100)
            uc.reg_write(UC_X86_REG_IP, 0)                 # the stub loads it and returns to the caller
            return
        if self._hooked.get(address) == 'clock':
            self.ticks += 5000
            self._return(ax=self.ticks & 0xFFFF, dx=self.ticks >> 16)
            return
        self._on_call2(uc, address, size, user)

    def _on_int(self, uc, intno, user):
        """The x87 fix-ups of emu.py, then the patched bytes are made to take effect: the translation of the old ones is thrown away."""
        from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_IP
        at = self.lin(uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP) - 2)
        if intno == 0x3E:                                      # the emulator library's padding: INT 3Eh and the byte after it do nothing
            uc.mem_write(at, bytes([0x90, 0x90, 0x90]))
            uc.reg_write(UC_X86_REG_IP, uc.reg_read(UC_X86_REG_IP) - 2)
            uc.ctl_remove_cache(at, at + 8)
            return
        super()._on_int(uc, intno, user)
        try:
            uc.ctl_remove_cache(at, at + 8)
        except Exception:                                      # noqa: BLE001 - an older unicorn: nothing to throw away
            pass

    def _caller(self):
        from unicorn.x86_const import UC_X86_REG_SP, UC_X86_REG_SS
        import qdis
        from emu import LOADSEG
        sp, ss = self.uc.reg_read(UC_X86_REG_SP), self.uc.reg_read(UC_X86_REG_SS)
        ip, cs = self.word(ss, sp, signed=False), self.word(ss, sp + 2, signed=False)
        return str(qdis.func_at(cs - LOADSEG, ip))

    def _on_call2(self, uc, address, size, user):
        if self._hooked[address] == 'getch':
            self.calls.append(('getch', []))
            who = self._caller()
            if who.startswith('@main2'):                       # the key loop: the turn is over when it asks again
                if not self.keys:
                    self.stopped = True
                    uc.emu_stop()
                    return
                self._return(ax=self.keys.pop(0))
                return
            if who.startswith(('@story', '@credits', '@newmap', '@title', '@mastermind', '@loadscreen', '@creation')):      # the game is over (or a level changes): story pages
                self.ended = True
                self.stopped = True
                uc.emu_stop()
                return
            if who.startswith(('@death', '@load', '@dying', '@quit')):          # the hero died: nothing more is compared
                self.died = True
                self.stopped = True
                uc.emu_stop()
                return
            self.waits.append(who)                              # a message or a question in the middle of the turn
            self._return(ax=110 if who.startswith('@save') else 32)        # Space for a message, N for "Want to save?"
            return
        super()._on_call(uc, address, size, user)


def load_tables(emu, data):
    emu.load_tables(data)
    for r, row in enumerate(data.items[:1000]):
        for c, v in enumerate(row[:13]):
            emu.set_int('_items', r, c, v)
    for r, row in enumerate(data.prices[:1000]):
        for c, v in enumerate(row[:2]):
            emu.set_int('_prices', r, c, v)
    for r, row in enumerate(data.spells[:21]):
        for c, v in enumerate(row[:14]):
            emu.set_int('_spellss', r, c, v)


def seed_of(emu):
    return struct.unpack('<I', emu.uc.mem_read(emu.lin(emu.ds, SEED_AT), 4))[0]


def set_seed(emu, s):
    emu.uc.mem_write(emu.lin(emu.ds, SEED_AT), struct.pack('<I', s & 0xFFFFFFFF))


def setup(emu, g, level, grid0, hero, state, seed, only=None, edits=None):
    """The same situation in both."""
    from engine import rules
    hx, hy = hero
    g.overlay = None
    g.target = None
    g.messages = []
    w, p = g.world, g.player
    w.level = level
    g.status.level = level
    w.grid = copy.deepcopy(grid0)
    p.X, p.Y = hx, hy
    w.visited = set()
    w.enter_room(p, g.status)
    g.events.on_enter_room()
    if only is not None:
        for e in list(w.enemies):
            if e.type not in only:
                w.sq(e.x, e.y).mon = 0
                w.enemies.remove(e)
    for e in w.enemies:
        for f, v in (edits or {}).get(e.type, {}).items():
            setattr(e, f, v)
    ens = w.enemies
    g.status.mons = len(ens)
    g.count_hostiles()                                       # (main2() counts them again before every key)
    g.status.mission1, g.status.mission2 = state['m1'], state['m2']
    h = p.hero
    h.life, h.mlife, h.mana, h.mmana = state['life'], state['life'], 50, 50
    h.bstr, h.bintl, h.bdex, h.bacc = state['str'], 20, state['dex'], state['acc']
    h.level, h.exper, h.rep, h.poisoned, h.invisible = 10, 30000, state.get('rep', 0), 0, -1
    for f in ('amb', 'bar', 'sch', 'mem', 'mar', 'cow', 'hon', 'ras'):       # no skills and no faults, as the emulator's hero has
        setattr(p.skill, f, 0)
    gear = state.get('gear', {})
    for slot, cell in (('weapon', (12, 4)), ('offhand', (16, 4)), ('helmet', (14, 2)), ('armor', (14, 4)), ('amulet', (14, 6))):
        p.bag[cell] = gear.get(slot, 0)
    for name in POTIONS:
        setattr(p.inv, name, state.get('potions', {}).get(name, 0))
    rules.status_update(p, g.status, g.items)
    g.talk_log = []
    ox, oy = w.origin
    emu.load_map(grid0)
    emu.load_room_from_map(hx, hy)
    # the room as it is now (the port's screen), not as the map has it
    for i in range(1, 11):
        for j in range(1, 11):
            q = w.grid[ox + i - 1][oy + j - 1]
            emu.set_square('_room', i, j, floor=q.floor, wall=q.wall, mon=q.mon, item=q.item, gold=q.gold, deco=q.deco)
    emu.set_word('_X', hx)
    emu.set_word('_Y', hy)
    emu.set_word('_ax', hx - ox + 1)
    emu.set_word('_ay', hy - oy + 1)
    emu.set_word('_otarw', -1)
    emu.set_word('_leaving', 0)
    emu.set_word('_moved', 1)
    emu.set_struct('_st', ST_F, {'mons': len(ens), 'ems': 0, 'level': level, 'mission1': state['m1'], 'mission2': state['m2'],
                                 'Shield': 0, 'fShield': 0, 'armboost': 0, 'powboost': 0, 'killer': 0})
    emu.set_struct('_hero', HERO_F, {f: getattr(h, f) for f in HERO_F if hasattr(h, f)})
    emu.set_struct('_skill', ['amb', 'bar', 'sch', 'mem', 'mar', 'cow', 'hon', 'ras'], {})
    emu.set_enemies([dict(type=e.type, x=e.x - ox + 1, y=e.y - oy + 1, life=e.life, mlife=e.mlife, atk=e.atk, defense=e.defense,
                          power=e.power, range=e.range, warm=e.warm, marm=e.marm, att=e.att) for e in ens])
    for c in range(12, 17):
        for r in range(0, 13):
            emu.set_int('_bag', c, r, p.bag.get((c, r), 0))
    emu.set_struct('_inv', INV, {name: getattr(p.inv, name) for name in INV if hasattr(p.inv, name)})
    set_seed(emu, seed)
    rules.srand(seed)
    emu.texts = []


def look(emu, g, level):
    """What both can be compared on."""
    w, p = g.world, g.player
    ox, oy = w.origin
    st = emu.get_struct('_st', ST_F)
    hero = emu.get_struct('_hero', HERO_F)
    n = st['mons']
    theirs = {
        'hero': (hero['life'], hero['mana'], hero['exper'], hero['rep'], hero['poisoned'], emu.get_word('_X'), emu.get_word('_Y')),
        'story': (st['mission1'], st['mission2'], st['mons']),
        'enemies': [tuple(e[f] for f in ('type', 'x', 'y', 'life', 'atk', 'power', 'range', 'warm', 'marm', 'att')) for e in emu.enemies(n)],
        'seed': seed_of(emu),
        'texts': [t for t in emu.texts if t[:1] in ('\xff', '\n') or t.startswith(' "')],           # what talk() printed (not the strip's questions and death lines)
    }
    mine = {
        'hero': (p.hero.life, p.hero.mana, p.hero.exper, p.hero.rep, p.hero.poisoned, p.X, p.Y),
        'story': (g.status.mission1, g.status.mission2, len(w.enemies)),
        'enemies': [(e.type, e.x - ox + 1, e.y - oy + 1, e.life, e.atk, e.power, e.range, e.warm, e.marm, e.att) for e in w.enemies],
        'seed': __import__('engine.rules', fromlist=['_seed'])._seed[0],
        'texts': [s for t in g.talk_log if t for s in (t[0], t[1]) if s],
    }
    squares = []
    for i in range(1, 11):
        for j in range(1, 11):
            a = emu.get_square('_room', i, j)
            q = w.grid[ox + i - 1][oy + j - 1]
            b = {f: getattr(q, f) for f in ('floor', 'wall', 'mon', 'item', 'gold', 'deco')}
            if a != b:
                squares.append(f'room({i},{j}): original {a} port {b}')
    return theirs, mine, squares


def turn(emu, g, key):
    """The key in both."""
    emu.keys = list(KEYS[key])
    emu.stopped = False
    emu.died = False
    emu.ended = False
    emu.set_word('_moved', 2)                          # main2() then starts with moved = 0: it does not run the end-of-turn upkeep (poison, timers) before the key, as a continuing game would not
    emu.call('main2', limit=30_000_000)
    if not emu.stopped:
        raise RuntimeError('main2 did not come back to wait for a key within the instruction limit (it was asking for keys in: %s)' % sorted(set(emu.waits[-20:])))
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=PYGAME[key], unicode='', mod=0))
    # (a message waits for Space in the original; the port's fast mode does not wait)


def compare(emu, g, level):
    if emu.ended:                                      # the original went on to the story pages (the quest is won, or a level changes): the port must be showing its own
        return [] if (g.overlay is not None or g.world.level != level) else ['the original went to the story pages, the port did not']
    if emu.died:                                       # the hero fell: both must have, and that is all that is compared
        return [] if g.player.hero.life < 1 else ['the original killed the hero, the port did not']
    theirs, mine, squares = look(emu, g, level)
    diffs = []
    for k in ('hero', 'story', 'enemies', 'seed', 'texts'):
        if theirs[k] != mine[k]:
            diffs.append(f'{k}: original {theirs[k]} port {mine[k]}')
    return diffs + squares[:4]


def run_case(emu, g, level, grid0, hero, state, seed, keys, only=None, edits=None):
    setup(emu, g, level, grid0, hero, state, seed, only, edits)
    out = []
    for n, key in enumerate(keys):
        before = seed_of(emu)
        turn(emu, g, key)
        d = compare(emu, g, level)
        if not d and (emu.ended or emu.died):
            break                                         # the hero fell or the quest ended: nothing more to press
        if d:
            out.append(f'key {n + 1} ({key}) from seed {before}: ' + '; '.join(d[:5]))
            break
    return out


def main(cases, rng_seed, m2s, only, nkeys):
    pygame.init()
    win = pygame.display.set_mode((640, 480))
    from engine.game import Game
    from engine.formats import GameData
    data = GameData.load()
    g = Game(win, data)
    g.overlay = None
    rng = pyrandom.Random(rng_seed)
    grid0 = data.load_level(7)
    free = [(x, y) for x in range(71, 81) for y in range(1, 11) if grid0[x][y].wall == 0 and grid0[x][y].mon == 0]
    total = bad = 0
    for c in range(cases):
        hero = rng.choice(free)
        state = dict(m1=0, m2=rng.choice(m2s), life=rng.choice([300, 600, 900]), str=rng.choice([40, 80]), dex=rng.choice([30, 60]),
                     acc=rng.choice([30, 60]), rep=0)
        seed = rng.randint(1, 0xFFFFFFFF)
        keys = [rng.choice([k for k in KEYS if k not in NOT_RANDOM]) for _ in range(nkeys)]
        edits = {}
        if rng.random() < 0.5:
            edits[45] = {'life': rng.choice([1, 30, 39, 40, 80])}
        try:
            g = Game(win, data)                                   # a new game and a new emulator for each case: nothing is left over from the one before
            g.overlay = None
            emu = TurnEmu()
            load_tables(emu, data)
            diffs = run_case(emu, g, 7, grid0, hero, state, seed, keys, only, edits)
        except Exception as err:          # noqa: BLE001
            import traceback
            diffs = [f'error: {type(err).__name__}: {err}', traceback.format_exc()[-700:]]
        total += 1
        if diffs:
            bad += 1
            print(f'hero {hero} state {state} edits {edits} keys {keys} seed {seed}')
            for d in diffs:
                print('    ', d)
    print(f'{total - bad} of {total} turns identical')
    return bad


def main_levels(levels, cases, rng_seed, nkeys):
    """Random screens of the given levels with creatures on them, a random hero (gear, potions, numbers) on a free square, random keys."""
    pygame.init()
    win = pygame.display.set_mode((640, 480))
    from engine.game import Game
    from engine.formats import GameData
    data = GameData.load()
    g = Game(win, data)
    g.overlay = None
    rng = pyrandom.Random(rng_seed)
    weapons = [0, 201, 205, 213, 214, 216, 230, 231, 232, 233]
    offhands = [0, 0, 301, 303, 625, 640, 650, 665, 675]
    total = bad = 0
    for level in levels:
        grid0 = data.load_level(level)
        screens = sorted({((x - 1) // 10, (y - 1) // 10) for x in range(1, 101) for y in range(1, 101) if grid0[x][y].mon != 0})
        for c in range(cases):
            sx, sy = rng.choice(screens)
            free = [(x, y) for x in range(sx * 10 + 1, sx * 10 + 11) for y in range(sy * 10 + 1, sy * 10 + 11)
                    if grid0[x][y].wall == 0 and grid0[x][y].mon == 0]
            if not free:
                continue
            hero = rng.choice(free)
            state = dict(m1=rng.randint(0, 4), m2=rng.randint(0, 7), life=rng.choice([40, 120, 300, 600]), str=rng.choice([20, 40, 80]),
                         dex=rng.choice([10, 30, 60]), acc=rng.choice([10, 30, 60]), rep=rng.randint(-5, 7),
                         gear=dict(weapon=rng.choice(weapons), offhand=rng.choice(offhands), helmet=rng.choice([0, 402, 405]),
                                   armor=rng.choice([0, 101, 108, 112]), amulet=rng.choice([0, 0, 501, 503, 505])),
                         potions={name: rng.choice([0, 0, 1, 2]) for name in POTIONS})
            seed = rng.randint(1, 0xFFFFFFFF)
            keys = [rng.choice([k for k in KEYS if k not in NOT_RANDOM]) for _ in range(nkeys)]
            try:
                g = Game(win, data)                                   # a new game and a new emulator for each case: nothing is left over from the one before
                g.overlay = None
                emu = TurnEmu()
                load_tables(emu, data)
                diffs = run_case(emu, g, level, grid0, hero, state, seed, keys)
            except Exception as err:          # noqa: BLE001
                import traceback
                diffs = [f'error: {type(err).__name__}: {err}', traceback.format_exc()[-600:]]
            total += 1
            if diffs:
                bad += 1
                print(f'level {level} hero {hero} state {state} keys {keys} seed {seed}')
                for d in diffs:
                    print('    ', d)
    print(f'{total - bad} of {total} turns identical')
    return bad


if __name__ == '__main__':
    args = sys.argv[1:]
    opt = lambda name, default: type(default)(args[args.index(name) + 1]) if name in args else default       # noqa: E731
    only = [int(v) for v in args[args.index('--only') + 1].split(',')] if '--only' in args else None
    m2s = [int(v) for v in args[args.index('--m2') + 1].split(',')] if '--m2' in args else [2, 3, 4, 5, 6]
    if '--levels' in args:
        sys.exit(1 if main_levels([int(v) for v in args[args.index('--levels') + 1].split(',')], opt('--cases', 20), opt('--seed', 1), opt('--keys', 3)) else 0)
    sys.exit(1 if main(opt('--cases', 20), opt('--seed', 1), m2s, only, opt('--keys', 3)) else 0)
