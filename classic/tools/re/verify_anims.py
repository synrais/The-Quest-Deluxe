"""Check the Quest II port of the original's animations (engine/anim.py) against TheQuest.exe.

Each animation (aflame(), ahit(), asskeleton(), death2() ...) is run twice with the same arguments and
the same rand() seed: once in the emulator, as the original code, and once as the port. Both record
every BGI call, asound() tone, delay() and nosound(), plus the clean2()/guy2() redraws the original
makes. The two call lists must be identical, argument for argument.

    python verify_anims.py              # every animation, many argument sets
    python verify_anims.py aflame -v    # one animation, printing both traces
"""
from __future__ import annotations

import os
import struct
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import port                                         # noqa: E402,F401  (QUEST_ENGINE=deluxe checks Deluxe)

import pygame                                       # noqa: E402

from emu_game import GameEmu                        # noqa: E402

# calls the port records too; state queries (getx, getmaxx, textwidth ...) are left out
TRACED = {'setcolor', 'setfillstyle', 'setlinestyle', 'settextstyle', 'moveto', 'lineto', 'line', 'linerel',
          'rectangle', 'bar', 'bar3d', 'circle', 'arc', 'ellipse', 'fillellipse', 'sector', 'pieslice',
          'floodfill', 'putpixel', 'getpixel', 'drawpoly', 'fillpoly', 'outtextxy', 'outtext', 'delay',
          'nosound', 'cleardevice', 'asound', 'clean2', 'guy2'}


class AnimEmu(GameEmu):
    """GameEmu that also records asound() and stubs clean2()/guy2() (they redraw from game state)."""

    STUBS = {'asound': 1, 'clean2': 2, 'guy2': 2}
    RUN = {'ampoisoned2', 'reput2', 'honor', 'cantsave', 'noarrows2'}
    unstub: set = set()

    def __init__(self):
        super().__init__()
        from unicorn import UC_HOOK_CODE
        for name, (seg, off) in self.addr.items():
            if name.startswith('@') and name[1:].split('$')[0] in self.STUBS:
                a = self.lin(seg, off)
                if a not in self._game_hooked:
                    self.uc.hook_add(UC_HOOK_CODE, self._on_game_call, begin=a, end=a)
                self._game_hooked[a] = ('stub', name[1:].split('$')[0])
            elif name.startswith('@') and name[1:].split('$')[0] in self.RUN:
                self._game_hooked[self.lin(seg, off)] = ('run', None)

    def _on_game_call(self, uc, address, size, user):
        kind, fn = self._game_hooked[address]
        if kind == 'run':                      # GameEmu skips it; here it is what we test
            return
        if kind == 'stub' and fn in self.unstub:
            return
        if kind == 'stub':
            self.calls.append((fn, self._args(self.STUBS[fn])))
            self._return()
            return
        return super()._on_game_call(uc, address, size, user)

    def trace(self, fname, *args, seed=1):
        self.call(self.addr['_srand'], seed & 0xFFFF)
        _, calls = self.call(fname, *args)
        return [(n, list(a)) for n, a in calls if n in TRACED]


class Recorder:
    """Stands in for engine.anim's screen: records calls in the emulator's format."""

    def __init__(self, bgi):
        self.g = bgi
        self.calls = []

    def __getattr__(self, name):
        fn = getattr(self.g, name)

        def rec(*args):
            if name in TRACED:
                self.calls.append((name, [a if not isinstance(a, list) else a for a in args]))
            return fn(*args)
        return rec


class TraceHost:
    """anim.Host that records tones and redraws next to the BGI calls."""

    def __init__(self, rec):
        self.g = rec
        self.calls = rec.calls

    def asound(self, f):
        self.calls.append(('asound', [f]))

    def nosound(self):
        self.calls.append(('nosound', []))

    def clean2(self, x, y):
        self.calls.append(('clean2', [x, y]))

    def guy2(self, x, y):
        self.calls.append(('guy2', [x, y]))

    def move_hero(self, x, y):
        pass


def port_trace(fname, *args, seed=1):
    from engine import anim, rules
    from engine.bgi import BGI
    rec = Recorder(BGI(pygame.Surface((640, 480))))
    host = TraceHost(rec)
    rules.srand(seed & 0xFFFF)
    for ms in getattr(anim, fname)(host, *args):
        if not isinstance(ms, anim.Pace):          # the port's own pacing, not a delay() of the original
            rec.calls.append(('delay', [ms]))
    return rec.calls


SCRATCH = 0x0100          # ints the pointer arguments point at, in the emulator's stack segment


def exe_trace(emu, fname, args, seed):
    """Run the original. A few take references and by-value structs; build those arguments."""
    from emu import STACKSEG
    ptr = []

    def ref(k, v):
        emu.uc.mem_write(emu.lin(STACKSEG, SCRATCH + 2 * k), struct.pack('<h', v))
        return [SCRATCH + 2 * k, STACKSEG]
    st, hero = [0] * 14, [0] * 23
    if fname == 'teleporter1':                  # (int &X, int &Y, level, ax, ay)
        x, y = args
        ptr = ref(0, 50) + ref(1, 50) + [5, x, y]
    elif fname == 'ateleport':                  # (i, ii, &ax, &ay, &X, &Y, room, st, hero)
        x, y, ax, ay = args
        ptr = [x, y] + ref(0, ax) + ref(1, ay) + ref(2, 50) + ref(3, 50) + [0, 0] + st + hero
    elif fname == 'guy2':                       # (i, ii, statuss st, heroo hero)
        x, y, t, inv, poi, kil, pow_, sh, fsh = args
        st = [0, 0, kil, 0, pow_, sh, fsh] + [0] * 7
        hero[20], hero[21], hero[22] = t, inv, poi
        ptr = [x, y] + st + hero
    elif fname == 'alightning':                 # (i, ii, who, room, st, hero)
        ptr = list(args) + [0, 0] + st + hero
    else:
        ptr = list(args)
    return emu.trace(fname, *ptr, seed=seed)


def norm(calls):
    out = []
    for n, a in calls:
        a = list(a)
        if n in ('setcolor', 'asound', 'delay'):
            a = [v & 0xFFFF if n != 'setcolor' else v & 15 for v in a]
            if n == 'delay':
                a = [a[0] - 0x10000 if a[0] >= 0x8000 else a[0]]
        if n == 'setfillstyle':
            a = [a[0], a[1] & 15]
        if n == 'putpixel':
            a = [a[0], a[1], a[2] & 15]
        if n == 'drawpoly' or n == 'fillpoly':
            a = [[tuple(p) for p in a[-1]]]
        out.append((n, a))
    return out


# (animation, list of argument tuples); positions are 1-based screen squares
def cases():
    sq = [(1, 1), (5, 5), (10, 10), (3, 8), (10, 1)]
    c = {}
    for f in ('dcast2', 'aheal', 'aheal2', 'arestore', 'aicering', 'ablackward', 'ainvisibility', 'athunder',
              'astoneknight', 'aearthq', 'acure', 'teleporter2', 'adeaths', 'adarkhour', 'asscorpion'):
        c[f] = list(sq)
    for f in ('afireball', 'aflame', 'agflame', 'ainferno', 'sthit', 'arhit', 'bolthit'):
        c[f] = [(x, y, w) for x, y in sq for w in (0, 1)]
    c['ahit'] = [(x, y, where, t) for x, y in sq for where in (1, 2, 3, 4) for t in (1, 2)]
    c['bhit'] = [(x, y, where) for x, y in sq for where in (1, 2, 3, 4, 5, 6)]
    c['bhit2'] = [(x, y, where) for x, y in sq for where in (1, 2, 3, 4, 5)]
    c['adrain'] = [(x, y, w) for x, y in sq for w in (1, 2, 3, 4)]
    c['ashield'] = [(x, y, t) for x, y in sq for t in (1, 2)]
    c['asskeleton'] = [(x, y, w) for x, y in sq for w in (1, 2, 3)]
    c['adeteriorate'] = [(x, y, d) for x, y in sq for d in (40, 7, 1)]
    c['teleporter1'] = list(sq)
    c['ateleport'] = [(x, y, ax, ay) for x, y in sq for ax, ay in ((1, 1), (7, 4))]
    c['alightning'] = [(x, y, w) for x, y in sq for w in (0, 1)]
    c['alevelup'] = [()]
    c['guy2'] = [(x, y, t, inv, poi, kil, pw, sh, fs) for x, y in sq[:2] for t in (1, 2, 3, 4)
                 for inv, poi, kil, pw, sh, fs in ((-1, 0, 0, 0, 0, 0), (-1, 1, 1, 0, 1, 0), (5, 0, 1, 0, 0, 1),
                                                   (0, 1, 0, 3, 0, 0), (-1, 0, 0, 3, 1, 1))]
    c['reput2'] = [(1,), (-1,), (3,), (-3,)]
    for f in ('honor', 'cantsave', 'noarrows2'):
        c[f] = [()]
    for f in ('song_key', 'song_jazz', 'song_bevcop'):
        c[f] = [()]
    c['ampoisoned2'] = [(1,), (0,)]
    c['dying2'] = [()]
    c['death2'] = [()] * 6
    return c


def main():
    pygame.init()
    only = [a for a in sys.argv[1:] if not a.startswith('-')]
    verbose = '-v' in sys.argv
    emu = AnimEmu()
    total = bad = 0
    for fname, arglist in cases().items():
        if only and fname not in only:
            continue
        nbad = 0
        emu.unstub = {'guy2'} if fname == 'guy2' else set()     # guy2 itself runs; elsewhere it's a stub
        for k, args in enumerate(arglist):
            seed = 1000 + 77 * k
            want = norm(exe_trace(emu, fname, args, seed))
            try:
                got = norm(port_trace(fname, *args, seed=seed))
            except Exception as err:                       # noqa: BLE001
                got = [('error', [repr(err)])]
            total += 1
            if want != got:
                bad += 1
                nbad += 1
                if nbad == 1 or verbose:
                    print(f'{fname}{args}: DIFFERENT')
                    for i in range(max(len(want), len(got))):
                        w = want[i] if i < len(want) else None
                        g = got[i] if i < len(got) else None
                        if w != g or verbose:
                            print(f'   {i:3d} exe {w}\n       port {g}')
                            if not verbose:
                                break
            elif verbose:
                for w in want:
                    print('   ', w)
        print(f'{fname:14s} {len(arglist) - nbad}/{len(arglist)} identical')
    print(f'\n{total - bad} of {total} animation runs identical to the original')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
