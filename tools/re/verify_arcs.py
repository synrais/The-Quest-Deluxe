"""Check quest2/bgi.py's thick (3-pixel) arcs against the Borland graphics kernel in the exe.

EGAVGA.BGI does not draw arcs: its ARC entry is an "emulate" slot, which the kernel patches with a
far call into its own code (at __GRP_ovr + 0x20, offset 0x348 there; function 0x14 goes to 0x79b).
This runs that kernel code in Unicorn with the real driver replaced by a stub. The stub records the
1-pixel lines (VECT, function 0x0c) the kernel asks for and sends the functions EGAVGA.BGI leaves to
the kernel back to it, as the patched slot does. Those lines are drawn and compared, pixel for
pixel, with BGI.ellipse() at thickness 3.

    python verify_arcs.py             # full circles r = 0..69 and 200 random arcs
    python verify_arcs.py --cases 20
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
                               UC_X86_REG_SI, UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_DS,
                               UC_X86_REG_SS, UC_X86_REG_SP)

import qdis                                         # noqa: E402

GRSEG = 0x461f                                      # the graphics library segment
KERNEL = 0x2210                                     # kernel pseudo-driver, right after __GRP_ovr
EMULATE = 0x348                                     # what the kernel patches into the driver
ARC = 0x79b                                         # its emulated ARC
DRIVER_EMULATES = (0x0e, 0x10, 0x14, 0x16, 0x18, 0x2a)   # EGAVGA.BGI table entries pointing at the slot
K, STUB, SS, BUF = 0x2000, 0x3000, 0x4000, 0x5000


def kernel_arc(code, start, end, rx, ry, cx, cy, thick=3):
    """The 1-pixel lines the kernel sends to the driver for ellipse(cx, cy, start, end, rx, ry)."""
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 0x100000)
    uc.mem_write(K * 16, code)
    uc.mem_write(STUB * 16, b'\xcb')                                   # retf
    uc.mem_write(K * 16 + 0xfff0, b'\xf4')                             # hlt: the end
    uc.mem_write(K * 16 + 0x70, struct.pack('<HH', 0, STUB))           # the driver's entry
    uc.mem_write(K * 16 + 0x300, struct.pack('<hh', cx, cy))           # current position
    uc.mem_write(K * 16 + 0x9e, bytes([0, thick]))                     # line style, thickness
    uc.mem_write(K * 16 + 0x7d, struct.pack('<hh', 639, 479))          # max x, y
    uc.mem_write(K * 16 + 0x84, struct.pack('<6h', 0, 0, 0, 0, 639, 479))   # viewport
    uc.mem_write(K * 16 + 0x4af, struct.pack('<HHH', 0x2000 // 6, 2, BUF))  # polygon buffer
    lines = []

    def driver(uc, addr, size, ud):
        reg = uc.reg_read
        si = reg(UC_X86_REG_SI)
        if si in DRIVER_EMULATES:
            uc.reg_write(UC_X86_REG_CS, K)
            uc.reg_write(UC_X86_REG_IP, EMULATE)
        elif si == 0x0c:
            s = [v - 0x10000 if v > 0x7fff else v for v in
                 (reg(UC_X86_REG_AX), reg(UC_X86_REG_BX), reg(UC_X86_REG_CX), reg(UC_X86_REG_DX))]
            lines.append(tuple(s))
    uc.hook_add(UC_HOOK_CODE, driver, begin=STUB * 16, end=STUB * 16)
    for r, v in ((UC_X86_REG_AX, start), (UC_X86_REG_BX, end), (UC_X86_REG_CX, rx), (UC_X86_REG_DX, ry),
                 (UC_X86_REG_SS, SS), (UC_X86_REG_SP, 0xffee), (UC_X86_REG_DS, K), (UC_X86_REG_CS, K)):
        uc.reg_write(r, v & 0xffff)
    uc.mem_write(SS * 16 + 0xffee, struct.pack('<H', 0xfff0))         # near return to the hlt
    uc.emu_start(K * 16 + ARC, 0, count=5_000_000)
    return lines


def main():
    n = int(sys.argv[sys.argv.index('--cases') + 1]) if '--cases' in sys.argv else 200
    pygame.init()
    from quest2.bgi import BGI
    from quest2.formats import DataSource
    base = qdis.BASE + GRSEG * 16
    code = qdis.exe[base + KERNEL: base + 0x3b80]
    rnd = random.Random(1)
    cases = [(0, 360, r, r) for r in range(70)]
    cases += [(rnd.randrange(360), rnd.randrange(400), rnd.randrange(1, 80), rnd.randrange(1, 80)) for _ in range(n)]
    bad = 0
    for start, end, rx, ry in cases:
        a = pygame.Surface((640, 480))
        g = BGI(a, DataSource())
        g.setcolor(15)
        for x1, y1, x2, y2 in kernel_arc(code, start, end, rx, ry, 320, 240):
            g.line(x1, y1, x2, y2)
        b = pygame.Surface((640, 480))
        h = BGI(b, DataSource())
        h.setcolor(15)
        h.setlinestyle(0, 1, 3)
        h.ellipse(320, 240, start, end, rx, ry)
        if pygame.image.tobytes(a, 'RGB') != pygame.image.tobytes(b, 'RGB'):
            bad += 1
            print(f'   differs: ellipse(320, 240, {start}, {end}, {rx}, {ry})')
    print(f'{len(cases) - bad} of {len(cases)} thick arcs identical to the kernel\'s')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
