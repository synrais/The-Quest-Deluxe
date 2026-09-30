"""Check quest2/bgi.py's shapes against the Borland graphics kernel inside TheQuest.exe.

EGAVGA.BGI draws only pixels, lines and bars. Everything else is done by the kernel: the
pseudo-driver the library calls (right after __GRP_ovr) clips lines, draws thick lines as three
thin ones, and the driver's "emulate" slots are patched with a far call back into the kernel
(offset 0x348 there), which draws arcs, ellipses, sectors, polygons and bar3d. This runs that
kernel code in Unicorn with a recording stand-in for the driver, replays what the driver was asked
to draw (pixels, 1-pixel lines, bars, colours, fill styles) with bgi.py's own primitives, and
compares the picture, pixel for pixel, with bgi.py drawing the same call.

    python verify_bgi.py              # every shape, random cases
    python verify_bgi.py --cases 20   # fewer cases per shape
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

import pygame                                       # noqa: E402
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE       # noqa: E402
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,   # noqa: E402
                               UC_X86_REG_SI, UC_X86_REG_ES, UC_X86_REG_CS, UC_X86_REG_IP,
                               UC_X86_REG_DS, UC_X86_REG_SS, UC_X86_REG_SP)

import qdis                                         # noqa: E402

GRSEG = 0x461f                  # the graphics library segment
KERNEL = 0x2210                 # the kernel pseudo-driver, right after __GRP_ovr
KERNEL_END = 0x3b80             # the next segment
EMULATE = 0x348                 # what the kernel patches into the driver's emulate slots
DRIVER_EMULATES = (0x0e, 0x10, 0x14, 0x16, 0x18, 0x2a)   # EGAVGA.BGI entries that are that slot
K, DRV, SS, BUF, PTS = 0x2000, 0x3000, 0x4000, 0x5000, 0x6000
REGS = dict(ax=UC_X86_REG_AX, bx=UC_X86_REG_BX, cx=UC_X86_REG_CX, dx=UC_X86_REG_DX,
            si=UC_X86_REG_SI, es=UC_X86_REG_ES)


def s16(v):
    return v - 0x10000 if v > 0x7fff else v


class Kernel:
    """The kernel with a recording driver. Methods named like graphics.lib's functions make the
    same pseudo-driver calls the library does."""

    def __init__(self, code):
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_16)
        uc.mem_map(0, 0x100000)
        uc.mem_write(K * 16, code)
        uc.mem_write(DRV * 16, b'\xcb' * 0x40)                          # every driver entry: retf
        uc.mem_write(DRV * 16 + 0x100, b''.join(struct.pack('<H', 0x20 + k) for k in range(8)))
        uc.mem_write(K * 16 + 0xfff0, b'\xf4')
        uc.mem_write(K * 16 + 0x70, struct.pack('<HH', 0, DRV))          # the driver's entry
        uc.mem_write(K * 16 + 0x7d, struct.pack('<hh', 639, 479))        # max x, y
        uc.mem_write(K * 16 + 0x84, struct.pack('<6h', 0, 0, 0, 0, 639, 479))   # viewport
        uc.mem_write(K * 16 + 0x4af, struct.pack('<HHH', 0x2000 // 6, 2, BUF))  # polygon buffer
        self.prims = []
        self.colour, self.fill_colour = 15, 15
        uc.hook_add(UC_HOOK_CODE, self._driver, begin=DRV * 16, end=DRV * 16)

    def _driver(self, uc, addr, size, ud):
        r = {k: uc.reg_read(v) for k, v in REGS.items()}
        si = r['si']
        if si in DRIVER_EMULATES:
            uc.reg_write(UC_X86_REG_CS, K)
            uc.reg_write(UC_X86_REG_IP, EMULATE)
            return
        if si == 0x32:                          # BITMAPUTIL: a table of near entry points
            uc.reg_write(UC_X86_REG_ES, DRV)
            uc.reg_write(UC_X86_REG_BX, 0x100)
        if si == 0x24:                          # user fill pattern at es:bx
            self.prims.append(('user', list(uc.mem_read(r['es'] * 16 + r['bx'], 8))))
            return
        self.prims.append((si, s16(r['ax']), s16(r['bx']), s16(r['cx']), s16(r['dx'])))

    def call(self, si, ax=0, bx=0, cx=0, dx=0, es=0):
        uc = self.uc
        for k, v in dict(ax=ax, bx=bx, cx=cx, dx=dx, si=si, es=es).items():
            uc.reg_write(REGS[k], v & 0xffff)
        for reg, v in ((UC_X86_REG_SS, SS), (UC_X86_REG_SP, 0xffec), (UC_X86_REG_DS, K), (UC_X86_REG_CS, K)):
            uc.reg_write(reg, v)
        uc.mem_write(SS * 16 + 0xffec, struct.pack('<HH', 0xfff0, K))    # far return to the hlt
        uc.emu_start(K * 16, K * 16 + 0xfff0, count=10_000_000)

    # graphics.lib
    def setcolor(self, c):
        self.colour = c
        self.call(0x1e, ax=(self.fill_colour << 8) | c)

    def setfillstyle(self, pattern, c):
        self.fill_colour = c
        self.call(0x1e, ax=(c << 8) | self.colour)
        self.call(0x20, ax=(pattern << 8) | pattern)

    def setlinestyle(self, style, pattern, thickness):
        self.call(0x22, ax=style, bx=pattern, cx=thickness)

    def line(self, x1, y1, x2, y2):
        self.call(0x0c, x1, y1, x2, y2)

    def rectangle(self, l, t, r, b):
        self.line(l, t, r, t)
        self.line(r, t, r, b)
        self.line(r, b, l, b)
        self.line(l, b, l, t)

    def bar(self, x1, y1, x2, y2):
        self.call(0x12, x1, y1, x2, y2)

    def bar3d(self, l, t, r, b, depth, top):
        ax, cx = (l, r) if l & 0xffff < r & 0xffff else (r, l)
        bx, dx = (t, b) if t & 0xffff >= b & 0xffff else (b, t)
        self.call(8, ax, bx)
        self.call(0x10, cx, dx, depth, top & 0xff)

    def ellipse(self, x, y, start, end, rx, ry):
        self.call(8, x, y)
        self.call(0x14, start, end, rx, ry)

    def fillellipse(self, x, y, rx, ry):
        self.call(8, x, y)
        self.call(0x18, rx, ry)
        self.call(0x14, 0, 360, rx, ry)

    def sector(self, x, y, start, end, rx, ry):
        self.call(8, x, y)
        self.call(0x16, start, end, rx, ry)

    def _poly(self, mode, pts):
        self.uc.mem_write(PTS * 16, b''.join(struct.pack('<hh', *p) for p in pts))
        self.call(0x0e, ax=mode, cx=len(pts), es=PTS)

    def drawpoly(self, pts):
        self._poly(6, pts)

    def fillpoly(self, pts):
        self._poly(7, pts)


def replay(prims):
    """Draw what the driver was asked for, with bgi.py's pixel, line and bar."""
    from quest2.bgi import BGI
    from quest2.formats import DataSource
    s = pygame.Surface((640, 480))
    g = BGI(s, DataSource())
    for p in prims:
        if p[0] == 'user':
            g.setfillpattern(p[1], g.fill[1])
            continue
        si, ax, bx, cx, dx = p
        if si == 0x1e:
            g.color, g.fill = ax & 0xff, (g.fill[0], (ax >> 8) & 0xff)
        elif si == 0x20:
            g.fill = (ax & 0xff, g.fill[1])
        elif si == 0x0c:
            g.line(ax, bx, cx, dx)              # the driver ignores thickness (the kernel does it)
        elif si == 0x12:
            g.bar(ax, bx, cx, dx)
        elif si == 0x30:
            g.putpixel(ax, bx, dx & 0xff)
    return s


def cases(rnd, n):
    """(name, function drawing on a BGI or a Kernel) pairs."""
    def coord(lo=-100, hi=740):
        return rnd.randrange(lo, hi)

    def angle():
        return rnd.choice((rnd.randrange(-400, 800), rnd.randrange(360), 0, 90, 180, 270, 360))

    def style(g, th, pat, c=5):
        g.setlinestyle(0, 1, th)
        g.setfillstyle(pat, c)

    out = []
    for _ in range(n):
        th, pat = rnd.choice((1, 3)), rnd.randrange(12)
        x, y = rnd.randrange(0, 640), rnd.randrange(0, 480)
        rx, ry = rnd.randrange(0, 80), rnd.randrange(0, 80)
        st, en = angle(), angle()
        a = [coord(), coord(-100, 580), coord(), coord(-100, 580)]
        if rnd.random() < .2:
            a[2] = a[0]
        k = rnd.randrange(2, 8)
        pts = [(rnd.randrange(-50, 400), rnd.randrange(-50, 400)) for _ in range(k)]
        if rnd.random() < .5:
            pts.append(pts[0])
        if rnd.random() < .2:
            pts.insert(rnd.randrange(len(pts)), pts[rnd.randrange(len(pts))])
        depth, top = rnd.choice((0, 1, 3, 10, 40)), rnd.randrange(2)
        out += [
            ('line', lambda g, a=a, th=th: (style(g, th, 1), g.line(*a))),
            ('rectangle', lambda g, a=a, th=th: (style(g, th, 1), g.rectangle(*a))),
            ('bar', lambda g, a=a, pat=pat: (style(g, 1, pat), g.bar(*a))),
            ('bar3d', lambda g, a=a, th=th, pat=pat, d=depth, t=top: (style(g, th, pat), g.bar3d(*a, d, t))),
            ('ellipse', lambda g, v=(x, y, st, en, rx, ry), th=th: (style(g, th, 1), g.ellipse(*v))),
            ('fillellipse', lambda g, v=(x, y, rx, ry), th=th, pat=pat: (style(g, th, pat), g.fillellipse(*v))),
            ('sector', lambda g, v=(x, y, st, en, rx, ry), th=th, pat=pat: (style(g, th, pat), g.sector(*v))),
            ('drawpoly', lambda g, p=pts, th=th: (style(g, th, 1), g.drawpoly(p))),
            ('fillpoly', lambda g, p=pts, th=th, pat=pat: (style(g, th, pat), g.fillpoly(p))),
        ]
    return out


def main():
    n = int(sys.argv[sys.argv.index('--cases') + 1]) if '--cases' in sys.argv else 100
    pygame.init()
    from quest2.bgi import BGI
    from quest2.formats import DataSource
    base = qdis.BASE + GRSEG * 16
    code = qdis.exe[base + KERNEL: base + KERNEL_END]
    total, bad = {}, {}
    for name, draw in cases(random.Random(1), n):
        k = Kernel(code)
        k.setcolor(15)
        k.setfillstyle(1, 15)
        k.prims = [p for p in k.prims if p[0] in (0x1e, 0x20)]
        draw(k)
        theirs = replay(k.prims)
        mine = pygame.Surface((640, 480))
        g = BGI(mine, DataSource())
        g.setcolor(15)
        g.setfillstyle(1, 15)
        draw(g)
        total[name] = total.get(name, 0) + 1
        if pygame.image.tobytes(theirs, 'RGB') != pygame.image.tobytes(mine, 'RGB'):
            bad[name] = bad.get(name, 0) + 1
    for name in total:
        print(f'{name:12s} {total[name] - bad.get(name, 0)}/{total[name]} identical to the kernel')
    print(f'\n{sum(total.values()) - sum(bad.values())} of {sum(total.values())} shapes identical')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
