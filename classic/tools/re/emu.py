"""Run the game's own drawing code in an x86 emulator (Unicorn) and capture what it draws.

TheQuest.exe draws every sprite with Borland BGI calls. This loads the exe image (with its
relocations), runs a chosen game function, and intercepts every call into the BGI library and a few
runtime helpers (delay, sound). The BGI calls are replayed on a pygame surface through
engine/bgi.py, so getpixel() sees real pixels. Everything else (the game's own code, the LVP
matrix/vector classes, rand()) runs natively.

    from emu import Emu
    e = Emu()
    surf, calls = e.draw_tile(floor=1)            # clean2() on one square
    surf, calls = e.call('grass', 1, 1)           # any game function by name

`pip install unicorn capstone pygame` is needed.
"""
from __future__ import annotations

import os
import struct
import sys

from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR, UcError
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_DX, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES,
                               UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_BP, UC_X86_REG_IP)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import qdis                                         # noqa: E402  (symbols, image)
from tds import load_exe                            # noqa: E402

LOADSEG = 0x1000              # where the image is loaded
STACKSEG = 0xE000             # our own stack
SQUARESEG = 0xD000            # fake map squares handed out by the matrix/vector subscripts
SENTINEL = (0xF000, 0x0000)   # return address that ends a call

# BGI and runtime functions we implement instead of running (name without the leading _)
INTERCEPT = {
    'setcolor', 'setbkcolor', 'setfillstyle', 'setfillpattern', 'setlinestyle', 'setwritemode',
    'settextstyle', 'settextjustify', 'moveto', 'moverel', 'lineto', 'linerel', 'line', 'rectangle',
    'bar', 'bar3d', 'circle', 'arc', 'ellipse', 'fillellipse', 'sector', 'pieslice', 'floodfill',
    'putpixel', 'getpixel', 'drawpoly', 'fillpoly', 'outtextxy', 'outtext', 'getx', 'gety',
    'getcolor', 'getmaxx', 'getmaxy', 'getbkcolor', 'cleardevice', 'setviewport', 'textwidth',
    'textheight', 'delay', 'sound', 'nosound', 'getch', 'kbhit', 'setpalette', 'setrgbpalette',
    'setaspectratio', 'getaspectratio', 'setactivepage', 'setvisualpage', 'clearviewport',
}


class Emu:
    def __init__(self, surface=None, source=None):
        import pygame
        from engine.bgi import BGI
        from engine.formats import DataSource
        self.pygame = pygame
        if surface is None:
            surface = pygame.Surface((640, 480))
        self.surface = surface
        self.g = BGI(surface, source or DataSource())
        exe = load_exe()
        hdr = struct.unpack_from('<14H', exe, 0)
        nrel, hdr_paras, reloff = hdr[3], hdr[4], hdr[12]
        image = bytearray(exe[hdr_paras * 16:qdis.t.image_end])
        for k in range(nrel):
            off, seg = struct.unpack_from('<HH', exe, reloff + 4 * k)
            p = seg * 16 + off
            v, = struct.unpack_from('<H', image, p)
            struct.pack_into('<H', image, p, (v + LOADSEG) & 0xFFFF)
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_16)
        uc.mem_map(0, 0x100000)
        uc.mem_write(LOADSEG * 16, bytes(image))
        uc.mem_write(SENTINEL[0] * 16 + SENTINEL[1], b'\xf4')     # hlt
        self.addr = {}
        for name, ty, off, seg, fl in qdis.syms[:qdis.t.h['globals']]:
            if name and seg < qdis.DGROUP:
                self.addr.setdefault(name, ((seg + LOADSEG) & 0xFFFF, off))
        self.data = {name: off for name, ty, off, seg, fl in qdis.syms[:qdis.t.h['globals']]
                     if name and seg == qdis.DGROUP}
        self.ds = qdis.DGROUP + LOADSEG
        self.calls: list = []
        self.square = [0] * 6
        self.unknown: set = set()
        self._install_hooks()

    # ── memory helpers ──────────────────────────────────────────────────────
    def lin(self, seg, off):
        return (seg * 16 + off) & 0xFFFFF

    def word(self, seg, off, signed=True):
        v, = struct.unpack('<h' if signed else '<H', self.uc.mem_read(self.lin(seg, off), 2))
        return v

    def cstr(self, seg, off):
        b = bytes(self.uc.mem_read(self.lin(seg, off), 200))
        return b[:b.index(0)].decode('latin1') if 0 in b else b.decode('latin1')

    def set_global(self, name, value):
        off = self.data[name]
        self.uc.mem_write(self.lin(self.ds, off), struct.pack('<h', value))

    # ── hooks ───────────────────────────────────────────────────────────────
    def _install_hooks(self):
        uc = self.uc
        self._hooked = {}
        for name, (seg, off) in self.addr.items():
            base = name.lstrip('_')
            if name.startswith('_') and base in INTERCEPT:
                self._hooked[self.lin(seg, off)] = base
            elif name in ('@%matrix$t6square%@$bsubs$qi', '@%vector$t6square%@$bsubs$qi'):
                self._hooked[self.lin(seg, off)] = name
        for a in self._hooked:
            uc.hook_add(UC_HOOK_CODE, self._on_call, begin=a, end=a)
        uc.hook_add(UC_HOOK_INTR, self._on_int)

    def _args(self, n):
        sp = self.uc.reg_read(UC_X86_REG_SP)
        ss = self.uc.reg_read(UC_X86_REG_SS)
        return [self.word(ss, sp + 4 + 2 * k) for k in range(n)]

    def _return(self, ax=0, dx=0):
        uc = self.uc
        sp = uc.reg_read(UC_X86_REG_SP)
        ss = uc.reg_read(UC_X86_REG_SS)
        ip = self.word(ss, sp, signed=False)
        cs = self.word(ss, sp + 2, signed=False)
        uc.reg_write(UC_X86_REG_SP, sp + 4)
        uc.reg_write(UC_X86_REG_AX, ax & 0xFFFF)
        uc.reg_write(UC_X86_REG_DX, dx & 0xFFFF)
        uc.reg_write(UC_X86_REG_CS, cs)
        uc.reg_write(UC_X86_REG_IP, ip)

    def _on_call(self, uc, address, size, user):
        name = self._hooked[address]
        g = self.g
        a = self._args
        ret = 0
        if name.startswith('@%matrix'):
            this_off, this_seg, i = a(3)
            self._row = i
            self._return(ax=i, dx=0)             # the "row" is just its index
            return
        if name.startswith('@%vector'):
            self._return(ax=0, dx=SQUARESEG)     # every square is our one fake square
            return
        if name in ('setcolor', 'setbkcolor', 'setwritemode', 'delay', 'sound'):
            args = a(1)
            if name == 'setcolor':
                g.setcolor(args[0] & 15)
        elif name == 'setfillstyle':
            args = a(2)
            g.setfillstyle(args[0], args[1] & 15)
        elif name == 'setfillpattern':
            off, seg, c = a(3)
            args = [list(self.uc.mem_read(self.lin(seg & 0xFFFF, off & 0xFFFF), 8)), c]
            g.setfillpattern(args[0], c & 15)
        elif name == 'setlinestyle':
            args = a(3)
            g.setlinestyle(*args)
        elif name == 'settextstyle':
            args = a(3)
            g.settextstyle(*args)
        elif name == 'settextjustify':
            args = a(2)
        elif name in ('moveto', 'moverel', 'lineto', 'linerel'):
            args = a(2)
            getattr(g, name)(*args)
        elif name in ('line', 'rectangle', 'bar'):
            args = a(4)
            getattr(g, name)(*args)
        elif name == 'bar3d':
            args = a(6)
            g.bar3d(*args)
        elif name == 'circle':
            args = a(3)
            g.circle(*args)
        elif name == 'arc':
            args = a(5)
            g.arc(*args)
        elif name in ('ellipse', 'sector'):
            args = a(6)
            getattr(g, name)(*args)
        elif name == 'pieslice':
            args = a(5)
            g.pieslice(*args)
        elif name == 'fillellipse':
            args = a(4)
            g.fillellipse(*args)
        elif name == 'floodfill':
            args = a(3)
            g.floodfill(*args)
        elif name == 'putpixel':
            args = a(3)
            g.putpixel(args[0], args[1], args[2] & 15)
        elif name == 'getpixel':
            args = a(2)
            ret = g.getpixel(*args)
        elif name in ('drawpoly', 'fillpoly'):
            n, off, seg = a(3)
            pts = [struct.unpack('<hh', self.uc.mem_read(self.lin(seg & 0xFFFF, (off & 0xFFFF) + 4 * k), 4))
                   for k in range(n)]
            args = [n, pts]
            getattr(g, name)(pts)
        elif name == 'outtextxy':
            x, y, off, seg = a(4)
            args = [x, y, self.cstr(seg & 0xFFFF, off & 0xFFFF)]
            g.outtextxy(*args)
        elif name == 'outtext':
            off, seg = a(2)
            args = [self.cstr(seg & 0xFFFF, off & 0xFFFF)]
            g.outtext(args[0])
        elif name in ('getmaxx',):
            args, ret = [], 639
        elif name in ('getmaxy',):
            args, ret = [], 479
        elif name == 'getcolor':
            args, ret = [], g.color
        elif name == 'getx':
            args, ret = [], g.cp[0]
        elif name == 'gety':
            args, ret = [], g.cp[1]
        elif name == 'getch':
            args, ret = [], 13
        else:
            args = []
        self.calls.append((name, args))
        self._return(ax=ret)

    def _on_int(self, uc, intno, user):
        """Borland's x87 emulator calls (INT 34h-3Dh): patch them into real FPU opcodes and re-run,
        exactly as the runtime's own fix-up does when a coprocessor is present."""
        cs = uc.reg_read(UC_X86_REG_CS)
        ip = uc.reg_read(UC_X86_REG_IP)
        at = self.lin(cs, ip - 2)
        if 0x34 <= intno <= 0x3B:
            uc.mem_write(at, bytes([0x9B, 0xD8 + intno - 0x34]))
        elif intno == 0x3C:
            x = uc.mem_read(at + 2, 1)[0]
            seg = {0x00: 0x26, 0x40: 0x2E, 0x80: 0x36, 0xC0: 0x3E}[x & 0xC0]
            uc.mem_write(at, bytes([0x9B, seg, 0xD8 | (x & 7)]))
        elif intno == 0x3D:
            uc.mem_write(at, bytes([0x90, 0x9B]))
        else:
            self.unknown.add(f'int {intno:#x}')
            return
        uc.reg_write(UC_X86_REG_IP, ip - 2)

    # ── running ─────────────────────────────────────────────────────────────
    def find(self, fname: str):
        """A game function by its plain name (e.g. 'grass'), from the mangled symbol table."""
        for name, (seg, off) in self.addr.items():
            base = name[1:].split('$')[0] if name.startswith('@') else name.lstrip('_')
            if base == fname and seg - LOADSEG in qdis.GAME_SEGS:
                return seg, off
        raise KeyError(fname)

    def call(self, fname: str, *args, limit=2_000_000):
        """Call a game function with word arguments; returns (surface, recorded calls)."""
        seg, off = self.find(fname) if isinstance(fname, str) else fname
        uc = self.uc
        sp = 0xFFF0
        words = [a & 0xFFFF for a in args]
        stack = struct.pack(f'<{2 + len(words)}H', SENTINEL[1], SENTINEL[0], *words)
        sp -= len(stack)
        uc.mem_write(self.lin(STACKSEG, sp), stack)
        uc.reg_write(UC_X86_REG_SS, STACKSEG)
        uc.reg_write(UC_X86_REG_SP, sp)
        uc.reg_write(UC_X86_REG_BP, 0)
        uc.reg_write(UC_X86_REG_DS, self.ds)
        uc.reg_write(UC_X86_REG_ES, self.ds)
        uc.reg_write(UC_X86_REG_CS, seg)
        self.calls = []
        try:
            uc.emu_start(self.lin(seg, off), self.lin(*SENTINEL), count=limit)
        except UcError as err:
            cs = uc.reg_read(UC_X86_REG_CS)
            ip = uc.reg_read(UC_X86_REG_IP)
            raise RuntimeError(f'{fname}: {err} at {cs:04x}:{ip:04x} '
                               f'({qdis.func_at(cs - LOADSEG, ip)})') from None
        return self.surface, self.calls

    def draw_tile(self, i=1, ii=1, floor=0, wall=0, mon=0, item=0, gold=0, deco=0):
        """clean2(i, ii, room) with room[i][ii] = the given square."""
        sq = struct.pack('<6h', floor, wall, mon, item, gold, deco)
        self.uc.mem_write(self.lin(SQUARESEG, 0), sq)
        return self.call('clean2', i, ii, 0, 0)
