"""Check engine/savefile.py against the exe's own save() and load2().

For many random game states:
  - save(): the state is put into the emulated game and the original save() runs; the text it
    fprintf()s must equal savefile.to_text() for the same state, character for character;
  - load2(): the original reads that text back into its globals, and savefile.from_text() must
    read the same values.
Also: SAVE01.DAT here (a save made by the original) must survive from_bytes() -> to_bytes()
unchanged.

    python verify_saves.py            # 40 random states
    python verify_saves.py --cases 5
"""
from __future__ import annotations

import os
import random
import struct
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import port                                         # noqa: E402,F401  (QUEST_ENGINE=deluxe checks Deluxe)

import pygame                                       # noqa: E402

from emu import STACKSEG                            # noqa: E402
from emu_game import GameEmu, HERO, INV, SKILL, STATUS, ENEMY, FILESEG   # noqa: E402

from engine import savefile                         # noqa: E402

WRITESEG = 0xFD00                                   # fake FILE* handles for files opened for writing
SQ_ORDER = ['floor', 'wall', 'item', 'mon', 'gold', 'deco']       # the order save() prints a square in


class SaveEmu(GameEmu):
    """GameEmu that can also write files: fopen(..., "w"), fprintf, remove, rename, code()."""

    def __init__(self):
        super().__init__()
        from unicorn import UC_HOOK_CODE
        self.written: dict[str, str] = {}
        self._wfiles: dict[int, list] = {}
        self.serve: dict[str, str] = {}              # file name -> decoded text, for load2()
        for name, (seg, off) in self.addr.items():
            base = name.lstrip('_')
            if base in ('fprintf', 'rename', 'rewind'):
                a = self.lin(seg, off)
                self._game_hooked[a] = (base, None)
                self.uc.hook_add(UC_HOOK_CODE, self._on_game_call, begin=a, end=a)
            elif name.startswith('@') and name[1:].split('$')[0] == 'code':
                a = self.lin(seg, off)
                self._game_hooked[a] = ('code', None)
                self.uc.hook_add(UC_HOOK_CODE, self._on_game_call, begin=a, end=a)

    def _on_game_call(self, uc, address, size, user):
        kind, _ = self._game_hooked[address]
        a = self._args
        if kind in ('save', 'load2'):                 # GameEmu skips these; here they are the test
            return
        if kind == 'fopen':
            noff, nseg, moff, mseg = a(4)
            fname = self.cstr(nseg & 0xFFFF, noff & 0xFFFF).split('\\')[-1].lower()
            mode = self.cstr(mseg & 0xFFFF, moff & 0xFFFF)
            if 'w' in mode:
                h = len(self._wfiles) + 1
                self._wfiles[h] = [fname, []]
                self._return(ax=h, dx=WRITESEG)
                return
            if fname in self.serve:
                h = len(self.files) + 1
                self.files[h] = {'data': self.serve[fname].encode('latin1'), 'pos': 0}
                self._return(ax=h, dx=FILESEG)
                return
        if kind == 'fclose':
            off, seg = a(2)
            if seg & 0xFFFF == WRITESEG:
                fname, parts = self._wfiles[off & 0xFFFF]
                self.written[fname] = ''.join(parts)
            self._return()
            return
        if kind == 'fprintf':
            self._fprintf()
            return
        if kind in ('rename', 'code', 'rewind'):
            self._return()
            return
        return super()._on_game_call(uc, address, size, user)

    def _fprintf(self):
        from unicorn.x86_const import UC_X86_REG_SP, UC_X86_REG_SS
        sp = self.uc.reg_read(UC_X86_REG_SP)
        ss = self.uc.reg_read(UC_X86_REG_SS)
        foff = self.word(ss, sp + 4, signed=False)
        fmt = self.cstr(self.word(ss, sp + 10, signed=False), self.word(ss, sp + 8, signed=False))
        argp = sp + 12
        out, k = [], 0
        while k < len(fmt):
            c = fmt[k]
            if c == '%':
                conv = fmt[k + 1]
                v = self.word(ss, argp)
                argp += 2
                out.append(str(v) if conv == 'd' else chr(v & 0xFF))
                k += 2
            else:
                out.append(c)
                k += 1
        self._wfiles[foff][1].append(''.join(out))
        self._return()


# ── a random state, in the original's terms ─────────────────────────────────────
def random_state(rng: random.Random, grid) -> savefile.SaveData:
    d = savefile.SaveData()
    r = lambda: rng.randint(-300, 3000)
    d.hero = {f: r() for f in HERO}
    d.hero['type'] = rng.randint(1, 4)
    d.hero['level'] = rng.randint(1, 30)
    d.inv = {f: rng.randint(0, 900) for f in INV}
    d.skill = {f: rng.randint(0, 3) for f in SKILL}
    d.st = {f: rng.randint(-2, 40) for f in STATUS}
    d.X, d.Y = rng.randint(1, 100), rng.randint(1, 100)
    d.ax, d.ay = (d.X - 1) % 10 + 1, (d.Y - 1) % 10 + 1
    for x in range(1, 101):
        for y in range(1, 101):
            q = grid[x][y]
            d.map[(x, y)] = (q.floor, q.wall, q.item, q.mon, q.gold, q.deco)
    for _ in range(300):
        d.map[(rng.randint(1, 100), rng.randint(1, 100))] = tuple(rng.randint(-120, 1000) for _ in range(6))
    for i in range(1, 11):
        for ii in range(1, 11):
            d.room[(i, ii)] = tuple(rng.randint(-120, 1000) for _ in range(6))
    d.enemies = [{f: rng.randint(-120, 300) for f in ENEMY} for _ in range(100)]
    d.bag = {c: rng.choice([0, 0, rng.randint(1, 700)]) for c in savefile.BAG_CELLS}
    d.book = {c: rng.randint(0, 20) for c in savefile.BOOK_CELLS}
    d.spells = [0] + [rng.randint(0, 5) for _ in range(20)]
    d.carta = {(i, ii): rng.randint(0, 1) for i in range(1, 11) for ii in range(1, 11)}
    d.fkey = [0] + [rng.randint(0, 20) for _ in range(9)]
    return d


def put_state(emu: SaveEmu, d: savefile.SaveData):
    from engine.formats import Square
    grid = [[Square() for _ in range(101)] for _ in range(101)]
    for (x, y), t in d.map.items():
        grid[x][y] = Square(**dict(zip(SQ_ORDER, t)))
    emu.load_map(grid)
    for (i, ii), t in d.room.items():
        emu.set_square('_room', i, ii, **dict(zip(SQ_ORDER, t)))
    emu.set_enemies(d.enemies)
    for (i, ii), v in d.bag.items():
        emu.set_int('_bag', i, ii, v)
    for (i, ii), v in d.book.items():
        emu.set_int('_book', i, ii, v)
    for (i, ii), v in d.carta.items():
        emu.set_int('_carta', i, ii, v)
    for k in range(21):
        emu.uc.mem_write(emu.gaddr('_spells') + 2 * k, struct.pack('<h', d.spells[k]))
    for k in range(10):
        emu.uc.mem_write(emu.gaddr('_fkey') + 2 * k, struct.pack('<h', d.fkey[k]))
    emu.set_struct('_hero', HERO, d.hero)
    emu.set_struct('_inv', INV, d.inv)
    emu.set_struct('_skill', SKILL, d.skill)
    emu.set_struct('_st', STATUS, d.st)
    for name, v in (('_X', d.X), ('_Y', d.Y), ('_ax', d.ax), ('_ay', d.ay)):
        emu.set_word(name, v)


def far(emu, name):
    return [emu.data[name], emu.ds]


def run_save(emu: SaveEmu, d: savefile.SaveData) -> str:
    """save(0, X, fkey, st, skill, Y, ax, ay, map, room, carta, enemies, bag, book, spells, hero, inv)
    with the stack laid out by the argument offsets in its debug info."""
    put_state(emu, d)
    words = [0] * 90
    at = lambda off: (off - 6) // 2

    def put(off, vals):
        words[at(off):at(off) + len(vals)] = vals
    put(6, [0])                                       # type 0: the silent save newgame() makes
    put(8, [d.X])
    put(10, far(emu, '_fkey'))
    put(14, [d.st[f] for f in STATUS])
    put(42, [d.skill[f] for f in SKILL])
    put(58, [d.Y, d.ax, d.ay])
    put(64, far(emu, '_map'))
    put(88, far(emu, '_enemies'))
    put(112, far(emu, '_spells'))
    put(116, [d.hero[f] for f in HERO])
    put(162, [d.inv[f] for f in INV])
    sp_entry = 0xFFF0 - 4 - 2 * len(words)
    for off, mat in ((68, '_room'), (78, '_carta'), (92, '_bag'), (102, '_book')):
        emu._mat[emu.lin(STACKSEG, sp_entry + 4 + off - 6)] = mat      # by-value matrix copies
    emu.written = {}
    emu.call('save', *words)
    return emu.written.get('delete.dat')


def run_load(emu: SaveEmu, text: str, slot: int) -> dict:
    """load2() on the text, then the globals it filled in."""
    blank = savefile.SaveData(hero={f: 0 for f in HERO}, inv={f: 0 for f in INV}, skill={f: 0 for f in SKILL},
                              st={f: 0 for f in STATUS}, enemies=[{f: 0 for f in ENEMY}] * 100)
    put_state(emu, blank)
    emu.set_struct('_st', STATUS, {'saveslot': slot})
    emu.serve = {f'save{slot:02d}.dat': text}
    args = []
    for name in ('_X', '_Y', '_ax', '_ay', '_map', '_room', '_carta', '_enemies', '_bag', '_book', '_spells',
                 '_hero', '_inv', '_fkey', '_skill', '_st'):
        args += far(emu, name)
    emu.call('load2', *args)
    got = {'hero': emu.get_struct('_hero', HERO), 'inv': emu.get_struct('_inv', INV),
           'skill': emu.get_struct('_skill', SKILL), 'st': emu.get_struct('_st', STATUS),
           'pos': tuple(emu.get_word(n) for n in ('_X', '_Y', '_ax', '_ay')), 'enemies': emu.enemies(100),
           'bag': {c: emu.get_int('_bag', *c) for c in savefile.BAG_CELLS},
           'book': {c: emu.get_int('_book', *c) for c in savefile.BOOK_CELLS},
           'carta': {(i, ii): emu.get_int('_carta', i, ii) for i in range(1, 11) for ii in range(1, 11)},
           'spells': [struct.unpack('<h', emu.uc.mem_read(emu.gaddr('_spells') + 2 * k, 2))[0] for k in range(21)],
           'fkey': [struct.unpack('<h', emu.uc.mem_read(emu.gaddr('_fkey') + 2 * k, 2))[0] for k in range(10)],
           'room': {(i, ii): tuple(emu.get_square('_room', i, ii)[f] for f in SQ_ORDER)
                    for i in range(1, 11) for ii in range(1, 11)},
           'map': {(x, y): tuple(emu.get_square('_map', x, y)[f] for f in SQ_ORDER)
                   for x in range(1, 101) for y in range(1, 101)}}
    return got


def compare_load(got: dict, d: savefile.SaveData, want_st_slot: int) -> list[str]:
    diffs = []
    for part, fields, mine in (('hero', HERO, d.hero), ('inv', INV, d.inv), ('skill', SKILL, d.skill),
                               ('st', STATUS, d.st)):
        for f in fields:
            if part == 'hero' and f not in savefile.HERO_SAVED + ['level', 'type', 'invisible', 'poisoned']:
                continue
            if part == 'st' and f == 'saveslot':
                if got['st'][f] != want_st_slot:
                    diffs.append(f'st.saveslot {got["st"][f]}')
                continue
            if got[part][f] != mine.get(f, 0):
                diffs.append(f'{part}.{f}: original {got[part][f]} port {mine.get(f, 0)}')
    if got['pos'] != (d.X, d.Y, d.ax, d.ay):
        diffs.append(f'position {got["pos"]} vs {(d.X, d.Y, d.ax, d.ay)}')
    if got['enemies'] != d.enemies:
        diffs.append('enemies differ')
    for part in ('bag', 'book', 'carta', 'room', 'map'):
        mine = getattr(d, part)
        bad = [k for k in got[part] if got[part][k] != mine.get(k, got[part][k] if part == 'map' else 0)]
        if bad:
            diffs.append(f'{part} differs at {bad[:3]}')
    for part in ('spells', 'fkey'):
        if got[part][1:] != getattr(d, part)[1:]:
            diffs.append(f'{part}: original {got[part]} port {getattr(d, part)}')
    return diffs


def main():
    pygame.init()
    n = int(sys.argv[sys.argv.index('--cases') + 1]) if '--cases' in sys.argv else 40
    from engine.formats import GameData
    data = GameData.load()
    emu = SaveEmu()
    rng = random.Random(7)
    ok_save = ok_load = 0
    for case in range(n):
        grid = data.load_level(rng.randint(1, 7))
        d = random_state(rng, grid)
        exe_text = run_save(emu, d)
        mine = savefile.to_text(d)
        if exe_text == mine:
            ok_save += 1
        else:
            k = next((i for i in range(min(len(exe_text or ''), len(mine))) if exe_text[i] != mine[i]), None)
            print(f'case {case}: save text differs at char {k}:\n  exe  {exe_text[k - 60:k + 40]!r}\n'
                  f'  port {mine[k - 60:k + 40]!r}' if exe_text else f'case {case}: the exe wrote nothing')
        slot = rng.randint(1, 20)
        got = run_load(emu, mine, slot)
        back = savefile.from_text(mine)
        diffs = compare_load(got, back, slot)
        if diffs:
            print(f'case {case}: load2 differs: {diffs[:5]}')
        else:
            ok_load += 1
    raw = open(os.path.join(HERE, 'SAVE01.DAT'), 'rb').read()
    same = savefile.to_bytes(savefile.from_bytes(raw)) == raw
    print(f'{ok_save} of {n} saves identical to the original save()')
    print(f'{ok_load} of {n} loads identical to the original load2()')
    print(f'SAVE01.DAT round trip: {"identical" if same else "DIFFERENT"}')
    return 0 if ok_save == ok_load == n and same else 1


if __name__ == '__main__':
    sys.exit(main())
