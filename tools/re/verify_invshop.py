"""Check quest2/invshop.py (the inventory and shop pages) against the exe's own inventory() and
peddler().

For many random bags, heroes and shops, both are fed the same key presses (getch()). They must make
the same BGI calls, tones and delays in the same order, draw the same items in the same cells
(bagdraw() is compared by its arguments and the item there), drop the same items (put3()), return
the same key, and leave the bag, gold and potions the same.

    python verify_invshop.py              # 60 random sessions of each
    python verify_invshop.py --cases 5 -v
"""
from __future__ import annotations

import copy
import os
import random
import struct
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import pygame                                       # noqa: E402

import emu_game                                     # noqa: E402

emu_game.MATRICES['_items'] = (1000, 13, 1)         # Items.dat has 13 columns
emu_game.MATRICES['_store'] = (17, 13, 1)           # the store uses the bag's cells [12..15][2..11]

from emu import STACKSEG                            # noqa: E402
from emu_game import GameEmu, HERO, INV, SKILL, STATUS          # noqa: E402
from verify_anims import TRACED, Recorder           # noqa: E402

UP, DOWN, LEFT, RIGHT = [0, 72], [0, 80], [0, 75], [0, 77]


class ShopEmu(GameEmu):
    STUBS = {'asound': 1, 'bagdraw': 3, 'put3': 5}

    def __init__(self):
        super().__init__()
        from unicorn import UC_HOOK_CODE
        for name, (seg, off) in self.addr.items():
            if name.startswith('@') and name[1:].split('$')[0] in self.STUBS:
                a = self.lin(seg, off)
                if a not in self._game_hooked:
                    self.uc.hook_add(UC_HOOK_CODE, self._on_game_call, begin=a, end=a)
                self._game_hooked[a] = ('stub', name[1:].split('$')[0])

    def _on_game_call(self, uc, address, size, user):
        kind, fn = self._game_hooked[address]
        if kind == 'stub':
            args = self._args(self.STUBS[fn])
            if fn == 'bagdraw':
                i, ii, a = args
                args = [i, ii, a, self.get_int('_store' if a == 2 else '_bag', i, ii)]
            self.calls.append((fn, args))
            self._return()
            return
        if kind == 'fscanf':
            # the C library sets the FILE's end-of-file flag (32 in the flags word at offset 2) when a
            # read runs out of data; peddler() stops on it
            foff = self._args(1)[0] & 0xFFFF
            f = self.files.get(foff)
            super()._on_game_call(uc, address, size, user)
            from unicorn.x86_const import UC_X86_REG_AX
            if f is not None and (uc.reg_read(UC_X86_REG_AX) & 0xFFFF) == 0xFFFF:
                self.uc.mem_write(self.lin(emu_game.FILESEG, foff + 2), struct.pack('<H', 32))
            return
        if kind == 'fopen':
            super()._on_game_call(uc, address, size, user)
            from unicorn.x86_const import UC_X86_REG_AX
            h = uc.reg_read(UC_X86_REG_AX) & 0xFFFF
            if h:
                self.uc.mem_write(self.lin(emu_game.FILESEG, h + 2), struct.pack('<H', 0))
            return
        return super()._on_game_call(uc, address, size, user)


def load_tables(emu, data):
    for r, row in enumerate(data.items[:1000]):
        for c, v in enumerate(row[:13]):
            emu.set_int('_items', r, c, v)
    for r, row in enumerate(data.prices[:1000]):
        for c, v in enumerate(row[:2]):
            emu.set_int('_prices', r, c, v)


def far(emu, name):
    return [emu.data[name], emu.ds]


def exe_run(emu, fn, s):
    """inventory(mode, bag, store, hero, skill, inv, ax, ay, st, room, items, prices) or
    peddler(X, Y, bag, store, hero, skill, inv, st, items, prices), laid out from the debug info."""
    for c in range(12, 17):
        for r in range(0, 13):
            emu.set_int('_bag', c, r, s['bag'].get((c, r), 0))
            emu.set_int('_store', c, r, s['store'].get((c, r), 0) if fn == 'inventory' else 0)
    emu.set_struct('_inv', INV, s['inv'])
    words = [0] * 69
    at = lambda off: (off - 6) // 2

    def put(off, vals):
        words[at(off):at(off) + len(vals)] = vals
    if fn == 'inventory':
        layout = {'bag': 8, 'store': 12, 'hero': 22, 'skill': 68, 'inv': 84, 'st': 92, 'room': 120,
                  'items': 124, 'prices': 134}
        put(6, [s['mode']])
        put(88, [s['ax'], s['ay']])
        put(layout['room'], far(emu, '_room'))
    else:
        layout = {'bag': 10, 'store': 14, 'hero': 24, 'skill': 70, 'inv': 86, 'st': 90, 'items': 118,
                  'prices': 128}
        put(6, [s['X'], s['Y']])
    put(layout['bag'], far(emu, '_bag'))
    put(layout['inv'], far(emu, '_inv'))
    put(layout['hero'], [s['hero'][f] for f in HERO])
    put(layout['skill'], [s['skill'][f] for f in SKILL])
    put(layout['st'], [s['st'][f] for f in STATUS])
    n = (layout['prices'] + 10 - 6) // 2
    words = words[:n]
    sp_entry = 0xFFF0 - 4 - 2 * len(words)
    for key, mat in (('store', '_store'), ('items', '_items'), ('prices', '_prices')):
        emu._mat[emu.lin(STACKSEG, sp_entry + 4 + layout[key] - 6)] = mat
    emu.keys = list(s['keys'])
    target = next(v for k, v in emu.addr.items() if k.startswith(f'@{fn}$q') and 'matrix' in k)
    _, calls = emu.call(target, *words, limit=20_000_000)
    trace = [(n, list(a)) for n, a in calls if n in TRACED | {'bagdraw', 'put3'}]
    bag = {(c, r): emu.get_int('_bag', c, r) for c in range(12, 17) for r in range(0, 13)}
    return trace, {k: v for k, v in bag.items() if v}, emu.get_struct('_inv', INV)


class PortHost:
    def __init__(self, rec, s, data):
        from quest2 import rules
        from quest2.state import Hero, Skills, Inventory, Status, Player
        self.g = rec
        self.calls = rec.calls
        self.bag = {k: v for k, v in s['bag'].items() if v}
        self.store = dict(s['store'])
        self.inv = Inventory(**s['inv'])
        self.skill = Skills(**s['skill'])
        self.hero = Hero(**s['hero'])
        self.st = Status(**s['st'])
        self.level = s['st']['level']
        self.ax, self.ay = s.get('ax', 0), s.get('ay', 0)
        self._items = rules.ItemTable(data.items)
        self._prices = {r[0]: r[1] for r in data.prices if len(r) > 1}
        self._rules, self._player = rules, Player

    def tell(self, it, col):
        return self._items.tell(it, col)

    def price(self, it):
        return self._prices.get(it, 0)

    def recompute(self):
        p = self._player(hero=self.hero, skill=self.skill, inv=self.inv)
        p.bag = self.bag
        self._rules.status_update(p, self.st, self._items)

    def asound(self, f):
        self.calls.append(('asound', [f]))

    def nosound(self):
        self.calls.append(('nosound', []))

    def bagdraw(self, i, ii, a):
        self.calls.append(('bagdraw', [i, ii, a, (self.store if a == 2 else self.bag).get((i, ii), 0)]))

    def put3(self, it):
        self.calls.append(('put3', [self.ax, self.ay, self.ax, self.ay, it]))


def port_run(fn, s, data):
    from quest2 import invshop
    from quest2.bgi import BGI
    rec = Recorder(BGI(pygame.Surface((640, 480))))
    h = PortHost(rec, s, data)
    h.recompute()
    gen = invshop.inventory(h, s['mode']) if fn == 'inventory' else invshop.peddler(h)
    keys = list(s['keys'])
    ret = None
    try:
        v = next(gen)
        while True:
            if v is None:
                rec.calls.append(('getch', []))
                v = gen.send(keys.pop(0) if keys else 32)
            else:
                rec.calls.append(('delay', [v]))
                v = next(gen)
    except StopIteration as stop:
        ret = stop.value
    bag = {k: v for k, v in h.bag.items() if v and 12 <= k[0] <= 16}
    return rec.calls, bag, {f: getattr(h.inv, f) for f in INV}, ret


def norm(calls):
    from verify_anims import norm as n
    return n([(k, a) for k, a in calls if k != 'getch'])


ITEMS = [101, 102, 104, 107, 111, 114, 201, 202, 205, 208, 211, 212, 216, 219, 222, 230, 231, 232, 233, 301, 302,
         304, 305, 306, 401, 403, 406, 408, 501, 502, 503, 504, 507, 511, 9, 11, 16, 907, 605, 620, 603, 633, 640,
         645, 661, 675]


def random_state(rng, fn, data):
    hero = {f: 0 for f in HERO}
    hero.update(mlife=50, life=40, mmana=20, mana=10, bstr=rng.randint(5, 30), bintl=rng.randint(5, 30),
                bdex=rng.randint(5, 20), bacc=rng.randint(5, 20), type=rng.randint(1, 4), invisible=-1)
    skill = {f: 0 for f in SKILL}
    skill.update(amb=rng.randint(0, 1), bar=rng.randint(0, 1), mar=rng.randint(0, 1))
    st = {f: 0 for f in STATUS}
    st.update(level=rng.randint(1, 7), powboost=rng.choice([0, 0, 3]), armboost=0)
    inv = {f: rng.randint(0, 3) for f in INV}
    inv['coins'] = rng.choice([0, 30, 250, 1500, 9000])
    bag = {}
    for cell in ((14, 2), (14, 4), (12, 4), (16, 4), (14, 6)):
        if rng.random() < 0.6:
            bag[cell] = rng.choice(ITEMS)
    for c in range(12, 16):
        for r in range(8, 12):
            if rng.random() < 0.55:
                bag[(c, r)] = rng.choice(ITEMS)
    keys = []
    for _ in range(rng.randint(3, 25)):
        keys += rng.choice([UP, DOWN, LEFT, RIGHT, UP, DOWN, LEFT, RIGHT, [13], [13], [8], [ord('x')], [0]])
    if fn == 'inventory':
        mode = rng.choice([1, 2])
        keys += rng.choice([[27], [ord('i')]] + ([[ord('b')]] if mode == 2 else []))
        return dict(mode=mode, hero=hero, skill=skill, st=st, inv=inv, bag=bag, store={}, keys=keys,
                    ax=rng.randint(1, 10), ay=rng.randint(1, 10))
    shops = [(lvl, (x, y)) for lvl in range(1, 8) for x in range(1, 11) for y in range(1, 11)]
    lvl, (sx, sy) = rng.choice([s for s in shops if shop_file(data, s[0], s[1])] or shops)
    st['level'] = lvl
    keys += rng.choice([[27], [ord('s')], [ord('i')]])
    return dict(hero=hero, skill=skill, st=st, inv=inv, bag=bag, store=shop_stock(data, lvl, sx, sy), keys=keys,
                X=(sx - 1) * 10 + rng.randint(1, 10), Y=(sy - 1) * 10 + rng.randint(1, 10))


SHOP_SCREENS = {1: {(3, 2): 1, (6, 7): 2}, 2: {(7, 1): 1, (8, 1): 2, (6, 1): 3}, 3: {(7, 5): 1, (6, 5): 2},
                4: {(5, 9): 1, (4, 9): 2, (6, 3): 2, (6, 5): 3}, 5: {(4, 10): 1, (3, 10): 2, (9, 4): 2},
                6: {(6, 2): 1, (9, 2): 2}, 7: {(3, 9): 1, (5, 9): 2}}


def shop_file(data, lvl, screen):
    return SHOP_SCREENS.get(lvl, {}).get(screen)


def shop_stock(data, lvl, sx, sy):
    n = shop_file(data, lvl, (sx, sy))
    store = {}
    if n:
        nums = [v for row in data.shop(lvl, n) for v in row][:40]
        for k, v in enumerate(nums):
            store[(12 + k % 4, 2 + k // 4)] = v
    return store


def main():
    pygame.init()
    n = int(sys.argv[sys.argv.index('--cases') + 1]) if '--cases' in sys.argv else 60
    verbose = '-v' in sys.argv
    only = [a for a in sys.argv[1:] if a in ('inventory', 'peddler')]
    from quest2.formats import GameData
    data = GameData.load()
    emu = ShopEmu()
    load_tables(emu, data)
    rng = random.Random(3)
    total = bad = 0
    for fn in only or ('inventory', 'peddler'):
        ok = 0
        for case in range(n):
            s = random_state(rng, fn, data)
            h = PortHost(Recorder(None), s, data)      # the hero as statusupdate() left it
            h.recompute()
            s['hero'] = {f: getattr(h.hero, f) for f in HERO}
            want, wbag, winv = exe_run(emu, fn, copy.deepcopy(s))
            got, gbag, ginv, ret = port_run(fn, copy.deepcopy(s), data)
            want, got = norm(want), norm(got)
            diffs = []
            if want != got:
                k = next((i for i in range(min(len(want), len(got))) if want[i] != got[i]), min(len(want), len(got)))
                diffs.append(f'call {k}: exe {want[k] if k < len(want) else None} port {got[k] if k < len(got) else None}')
            if wbag != gbag:
                diffs.append(f'bag: exe {sorted(wbag.items())} port {sorted(gbag.items())}')
            if winv != ginv:
                diffs.append(f'inv: exe {winv} port {ginv}')
            total += 1
            if diffs:
                bad += 1
                if bad <= 6 or verbose:
                    print(f'{fn} case {case}: keys {s["keys"]} bag {s["bag"]}')
                    for d in diffs:
                        print('   ', d)
            else:
                ok += 1
        print(f'{fn}: {ok} of {n} sessions identical to the original')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
