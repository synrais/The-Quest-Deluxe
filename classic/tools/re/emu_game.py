"""Run the original game logic (talk(), deadenemycheck(), ...) in the emulator on a game state we set up.

This extends emu.Emu with:
- the LVP matrix<square>/matrix<int> classes backed by our own memory (map 101x101, room 12x12,
  bag 17x13, book 17x12, carta 12x12, monster and spell tables), including copies passed by value;
- the C library file calls the game uses to read its data files (fopen/fgets/fscanf/fclose), served
  from the decoded files in Python, plus decode2()/code2();
- state helpers for the hero, inventory, skills, status, enemies and positions;
- stubs for things with outside effects (save files, sound, keyboard: getch() returns from a queue).

It exists to check the Quest II event port against the original: set a state, run e.g.
talk(npc), read back the state and the text the game printed.
"""
from __future__ import annotations

import re
import struct

from unicorn.x86_const import UC_X86_REG_SP, UC_X86_REG_SS

import qdis
from emu import Emu, LOADSEG

HEAP = 0xA800                   # our matrices live from linear 0xA8000 up
ROWSEG = 0xFF00                 # fake segment for "row handles" returned by matrix[]
FILESEG = 0xFE00                # fake FILE* handles

HERO = ['mlife', 'life', 'mmana', 'mana', 'bstr', 'bintl', 'bdex', 'bacc', 'dex', 'acc', 'intl', 'str',
        'defense', 'atk', 'rep', 'power', 'warm', 'marm', 'level', 'exper', 'type', 'invisible', 'poisoned']
INV = ['bkey', 'rkey', 'ykey', 'coins', 'rose', 'red', 'purple', 'blue', 'white', 'cyan', 'yellow', 'black']
SKILL = ['amb', 'bar', 'sch', 'mem', 'mar', 'cow', 'hon', 'ras']
STATUS = ['mons', 'ems', 'killer', 'armboost', 'powboost', 'Shield', 'fShield', 'level', 'mission1', 'mission2',
          'saveslot', 'p1', 'p2', 'p3']
ENEMY = ['type', 'x', 'y', 'life', 'mlife', 'atk', 'defense', 'power', 'range', 'warm', 'marm', 'att']
SQUARE = ['floor', 'wall', 'mon', 'item', 'gold', 'deco']

# (global name, rows, cols, element size in words)
MATRICES = {'_map': (101, 101, 6), '_room': (12, 12, 6), '_carta': (12, 12, 1), '_bag': (17, 13, 1),
            '_book': (17, 12, 1), '_store': (12, 12, 1), '_items': (1000, 12, 1), '_prices': (1000, 2, 1),
            '_spellss': (21, 14, 1), '_monsterss': (100, 9, 1)}

# game functions that only draw, animate, or touch files/sound: skipped (they return 0)
SKIP = {'save', 'load2', 'newsave', 'cantsave', 'asound', 'dpotions', 'dpotions2', 'dmoney', 'dcoins', 'stats',
        'dlife', 'dlife2', 'dmana', 'dmana2', 'dkeys', 'dkeys2', 'dmap', 'reput2', 'ampoisoned2', 'honor'}


class GameEmu(Emu):
    def __init__(self, source=None):
        super().__init__(source=source)
        from quest2.formats import DataSource, decode_bytes
        self.src = source or DataSource()
        self._decode = decode_bytes
        self.keys: list[int] = []
        self.files: dict[int, dict] = {}
        self._mat: dict[int, str] = {}            # linear address of a matrix object -> its name
        self._rows: dict[int, tuple] = {}
        self._base: dict[str, int] = {}
        self.texts: list[str] = []
        self.skipped: list[str] = []
        p = HEAP * 16
        for name, (r, c, sz) in MATRICES.items():
            self._base[name] = p
            p += r * c * sz * 2
            p = (p + 15) & ~15
            self._mat[self.lin(self.ds, self.data[name])] = name
        assert p < 0xD0000, hex(p)
        self._install_game_hooks()

    # ── hooks ───────────────────────────────────────────────────────────────
    def _install_game_hooks(self):
        from unicorn import UC_HOOK_CODE
        extra = {}
        for name, (seg, off) in self.addr.items():
            base = name.lstrip('_')
            if re.match(r'@%matrix\$t(6square|i)%@\$bsubs\$x?qi$', name):
                extra[self.lin(seg, off)] = ('msub', None)
            elif re.match(r'@%vector\$t(6square|i)%@\$bsubs\$x?qi$', name):
                extra[self.lin(seg, off)] = ('vsub', None)
            elif re.match(r'@%matrix\$t(6square|i)%@\$bctr\$qmx\d+%matrix', name):
                extra[self.lin(seg, off)] = ('mcopy', None)
            elif re.match(r'@%matrix\$t(6square|i)%@\$bdtr\$qv$', name):
                extra[self.lin(seg, off)] = ('ret', None)
            elif re.match(r'@%matrix\$t(6square|i)%@num(rows|cols)\$xqv$', name):
                extra[self.lin(seg, off)] = ('dims', name)
            elif base in ('fopen', 'fclose', 'fgets', 'fscanf', 'remove'):
                extra[self.lin(seg, off)] = (base, None)
            elif name.startswith('@') and seg - LOADSEG in qdis.GAME_SEGS:
                fn = name[1:].split('$')[0]
                if fn in SKIP or fn in ('decode2', 'code2'):
                    extra[self.lin(seg, off)] = (fn, None)
            elif base in ('getch', 'random', 'rand') and False:
                pass
        # the base class hooks getch; replace its behaviour through self.keys
        self._game_hooked = extra
        for a in extra:
            if a in self._hooked:
                continue
            self.uc.hook_add(UC_HOOK_CODE, self._on_game_call, begin=a, end=a)

    def _on_call(self, uc, address, size, user):
        name = self._hooked[address]
        if name == 'getch':
            self.calls.append(('getch', []))
            self._return(ax=self.keys.pop(0) if self.keys else 32)
            return
        if name == 'outtextxy':
            x, y, off, seg = self._args(4)
            self.texts.append(self.cstr(seg & 0xFFFF, off & 0xFFFF))
        if name.startswith('@%'):
            return self._on_game_call(uc, address, size, user)
        super()._on_call(uc, address, size, user)

    def _on_game_call(self, uc, address, size, user):
        kind, extra = self._game_hooked[address]
        a = self._args
        if kind == 'msub':
            off, seg, i = a(3)
            name = self._mat.get(self.lin(seg & 0xFFFF, off & 0xFFFF))
            if name is None:
                raise RuntimeError(f'unknown matrix at {seg & 0xFFFF:04x}:{off & 0xFFFF:04x}')
            handle = len(self._rows) + 1
            self._rows[handle] = (name, i)
            self._return(ax=handle, dx=ROWSEG)
        elif kind == 'vsub':
            off, seg, j = a(3)
            if seg & 0xFFFF != ROWSEG:
                raise RuntimeError('vector[] on something that is not a matrix row')
            name, i = self._rows.pop(off & 0xFFFF)
            rows, cols, sz = MATRICES[name]
            if not (0 <= i < rows and 0 <= j < cols):
                raise RuntimeError(f'{name}[{i}][{j}] out of range')
            lin = self._base[name] + (i * cols + j) * sz * 2
            self._return(ax=lin & 0xF, dx=lin >> 4)
        elif kind == 'mcopy':
            toff, tseg, soff, sseg = a(4)
            src = self._mat.get(self.lin(sseg & 0xFFFF, soff & 0xFFFF))
            if src is None:
                raise RuntimeError('copy of an unknown matrix')
            self._mat[self.lin(tseg & 0xFFFF, toff & 0xFFFF)] = src
            self._return(ax=toff, dx=tseg)
        elif kind == 'dims':
            off, seg = a(2)
            name = self._mat[self.lin(seg & 0xFFFF, off & 0xFFFF)]
            r, c, _ = MATRICES[name]
            self._return(ax=r if 'rows' in extra else c)
        elif kind == 'ret':
            self._return()
        elif kind == 'decode2':
            off, seg = a(2)
            self._return(ax=off, dx=seg)           # the "decoded copy" is the file itself
        elif kind in ('code2', 'remove'):
            self._return()
        elif kind == 'fopen':
            noff, nseg, moff, mseg = a(4)
            fname = self.cstr(nseg & 0xFFFF, noff & 0xFFFF).split('\\')[-1]
            try:
                text = self._decode(self.src.read(fname))
            except FileNotFoundError:
                self._return(ax=0, dx=0)
                return
            h = len(self.files) + 1
            self.files[h] = {'data': text.encode('latin1').replace(b'\r\n', b'\n'), 'pos': 0}
            self._return(ax=h, dx=FILESEG)
        elif kind == 'fclose':
            self._return()
        elif kind == 'fgets':
            boff, bseg, n, foff, fseg = a(5)
            f = self.files[foff & 0xFFFF]
            d, p = f['data'], f['pos']
            if p >= len(d):
                self._return(ax=0, dx=0)
                return
            e = d.find(b'\n', p)
            e = len(d) if e < 0 else e + 1
            e = min(e, p + n - 1)
            chunk = d[p:e]
            f['pos'] = e
            self.uc.mem_write(self.lin(bseg & 0xFFFF, boff & 0xFFFF), chunk + b'\0')
            self._return(ax=boff, dx=bseg)
        elif kind == 'fscanf':
            foff, fseg, fmoff, fmseg = a(4)
            fmt = self.cstr(fmseg & 0xFFFF, fmoff & 0xFFFF)
            n = self._scanf(self.files[foff & 0xFFFF], fmt)
            self._return(ax=n)
        elif kind in SKIP:
            self.skipped.append(kind)
            self._return()
        else:
            self._return()

    def _scanf(self, f, fmt):
        """The few fscanf formats the game uses: %d, %c, and whitespace."""
        sp = self.uc.reg_read(UC_X86_REG_SP)
        ss = self.uc.reg_read(UC_X86_REG_SS)
        argp = sp + 4 + 8                        # after FILE* and format (far pointers)
        d, p = f['data'], f['pos']
        count = 0
        k = 0
        while k < len(fmt):
            c = fmt[k]
            if c == '%':
                conv = fmt[k + 1]
                k += 2
                off = self.word(ss, argp, signed=False)
                seg = self.word(ss, argp + 2, signed=False)
                argp += 4
                if conv == 'c':
                    if p >= len(d):
                        break
                    self.uc.mem_write(self.lin(seg, off), bytes([d[p]]))
                    p += 1
                elif conv == 'd':
                    while p < len(d) and d[p] in b' \t\r\n':
                        p += 1
                    m = re.match(rb'[-+]?\d+', d[p:])
                    if not m:
                        break
                    self.uc.mem_write(self.lin(seg, off), struct.pack('<h', int(m.group()) & 0xFFFF
                                                                      if int(m.group()) >= 0 else int(m.group())))
                    p += len(m.group())
                count += 1
            elif c in ' \t\n\r':
                while p < len(d) and d[p] in b' \t\r\n':
                    p += 1
                k += 1
            else:
                if p < len(d) and d[p] == ord(c):
                    p += 1
                k += 1
        f['pos'] = p
        return count if count or p < len(d) else -1

    # ── state ───────────────────────────────────────────────────────────────
    def gaddr(self, name):
        return self.lin(self.ds, self.data[name])

    def get_struct(self, name, fields):
        raw = self.uc.mem_read(self.gaddr(name), 2 * len(fields))
        return dict(zip(fields, struct.unpack(f'<{len(fields)}h', raw)))

    def set_struct(self, name, fields, values: dict):
        cur = self.get_struct(name, fields)
        cur.update(values)
        self.uc.mem_write(self.gaddr(name), struct.pack(f'<{len(fields)}h', *[cur[f] for f in fields]))

    def get_word(self, name):
        return struct.unpack('<h', self.uc.mem_read(self.gaddr(name), 2))[0]

    def set_word(self, name, v):
        self.uc.mem_write(self.gaddr(name), struct.pack('<h', v))

    def cell(self, mat, i, j):
        rows, cols, sz = MATRICES[mat]
        return self._base[mat] + (i * cols + j) * sz * 2

    def get_square(self, mat, i, j):
        return dict(zip(SQUARE, struct.unpack('<6h', self.uc.mem_read(self.cell(mat, i, j), 12))))

    def set_square(self, mat, i, j, **kw):
        cur = self.get_square(mat, i, j)
        cur.update(kw)
        self.uc.mem_write(self.cell(mat, i, j), struct.pack('<6h', *[cur[f] for f in SQUARE]))

    def get_int(self, mat, i, j):
        return struct.unpack('<h', self.uc.mem_read(self.cell(mat, i, j), 2))[0]

    def set_int(self, mat, i, j, v):
        self.uc.mem_write(self.cell(mat, i, j), struct.pack('<h', v))

    def enemies(self, n):
        raw = self.uc.mem_read(self.gaddr('_enemies'), 24 * n)
        return [dict(zip(ENEMY, struct.unpack_from('<12h', raw, 24 * k))) for k in range(n)]

    def set_enemies(self, lst):
        for k, e in enumerate(lst):
            self.uc.mem_write(self.gaddr('_enemies') + 24 * k, struct.pack('<12h', *[e.get(f, 0) for f in ENEMY]))

    def load_map(self, grid):
        """grid[x][y] -> quest2.formats.Square, 1-based, into the game's map matrix."""
        buf = bytearray(101 * 101 * 12)
        for x in range(1, 101):
            for y in range(1, 101):
                q = grid[x][y]
                struct.pack_into('<6h', buf, (x * 101 + y) * 12, q.floor, q.wall, q.mon, q.item, q.gold, q.deco)
        self.uc.mem_write(self._base['_map'], bytes(buf))

    def load_room_from_map(self, X, Y):
        """goroom()'s copy: room[1..10][1..10] = the 10x10 screen holding (X, Y)."""
        ox, oy = (X - 1) // 10 * 10, (Y - 1) // 10 * 10
        for i in range(12):
            for j in range(12):
                x, y = ox + i, oy + j
                if 1 <= x <= 100 and 1 <= y <= 100:
                    self.uc.mem_write(self.cell('_room', i, j), bytes(self.uc.mem_read(self.cell('_map', x, y), 12)))
                else:
                    self.uc.mem_write(self.cell('_room', i, j), bytes(12))

    def store_room_to_map(self, X, Y):
        ox, oy = (X - 1) // 10 * 10, (Y - 1) // 10 * 10
        for i in range(1, 11):
            for j in range(1, 11):
                self.uc.mem_write(self.cell('_map', ox + i, oy + j), bytes(self.uc.mem_read(self.cell('_room', i, j), 12)))

    def load_tables(self, data):
        """MONSTERS.DAT / Spells.dat / Items.dat rows into the game's lookup matrices."""
        for i, row in enumerate(data.src.numbers('MONSTERS.DAT')[:100]):
            for j, v in enumerate(row[:9]):
                self.set_int('_monsterss', i, j, v)

    def seed(self, s):
        """Borland's rand() state (the long at DGROUP 'seed')."""
        for name in ('__seed', '_seed', '___seed'):
            if name in self.data:
                self.uc.mem_write(self.gaddr(name), struct.pack('<I', s & 0xFFFFFFFF))
                return
        raise KeyError('seed')
