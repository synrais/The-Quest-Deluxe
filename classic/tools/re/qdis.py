"""Annotated disassembler for TheQuest.exe using its Turbo Debugger symbols.

usage: python dis.py <function-name-substring> [...]   -> writes asm/<name>.asm
       python dis.py --all                             -> every game function
"""
import sys, os, struct, re, bisect
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
sys.path.insert(0, os.path.dirname(__file__))
from tds import TDS

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out', 'asm')
os.makedirs(OUT, exist_ok=True)

t = TDS()
d = t.d
exe = t.exe
BASE = t.image_base
DGROUP = 0x5056
GAME_SEGS = {0x0a45: 'RPG', 0x1987: 'ICONS', 0x2972: 'FUNCS', 0x362f: 'FUNCS2'}

N = t.h['symbols']
syms = []
for i in range(N):
    nm, ty, off, seg, fl = struct.unpack_from('<IIHHH', d, 128 + i * 14)
    syms.append((t.name(nm), ty, off, seg, fl))

# functions: class bits == 0 & has segment; use all globals with name, split by seg
funcs = sorted({(s[3], s[2], s[0]) for s in syms[:t.h['globals']] if s[3] != DGROUP and s[3] < 0x5056 and s[0]})
func_keys = [(f[0], f[1]) for f in funcs]
data_syms = sorted((s[2], s[0]) for s in syms[:t.h['globals']] if s[3] == DGROUP)
data_offs = [x[0] for x in data_syms]

SC = 113948
scopes = [struct.unpack_from('<IHHIHH', d, SC + i * 16) for i in range(t.h['scopes'])]
SEGTAB = 131324
segtab = [struct.unpack_from('<HHHHHHHH', d, SEGTAB + i * 16) for i in range(4)]


def seg_scopes(seg):
    for (mod, cseg, coff, clen, sidx, scnt, cidx, ccnt) in segtab:
        if cseg == seg:
            return scopes[sidx - 1: sidx - 1 + scnt]
    return []


def demangle(n):
    m = re.match(r'@([A-Za-z_0-9]+)\$q(.*)', n)
    if m:
        return m.group(1) + '(' + m.group(2) + ')'
    return n.lstrip('_')


def func_at(seg, off):
    i = bisect.bisect_right(func_keys, (seg, off)) - 1
    if i >= 0 and funcs[i][0] == seg:
        f = funcs[i]
        return f[2] if f[1] == off else f'{f[2]}+{off - f[1]:x}'
    return None


def data_name(off):
    i = bisect.bisect_right(data_offs, off) - 1
    if i >= 0:
        o, n = data_syms[i]
        if off - o < 0x800:
            return n.lstrip('_') + (f'+{off - o}' if off != o else '')
    return None


def ds_string(off):
    p = BASE + DGROUP * 16 + off
    s = exe[p:p + 120]
    z = s.find(b'\0')
    if z >= 2:
        s = s[:z]
        if all(32 <= c < 127 or c in (9, 10, 13) for c in s):
            return s.decode('latin1')
    return None


def locals_for(seg, start, end):
    """map bp offset -> name for scopes inside [start,end)"""
    res = []
    for (idx, cnt, parent, fn, off, ln) in seg_scopes(seg):
        if start <= off < end:
            for k in range(idx - 1, idx - 1 + cnt):
                name, ty, soff, sseg, fl = syms[k]
                cls = fl & 7
                res.append((off, off + ln, cls, soff, name))
    return res


md = Cs(CS_ARCH_X86, CS_MODE_16)
md.detail = False


def disasm(fname):
    idx = [i for i, f in enumerate(funcs) if f[2] == fname]
    if not idx:
        raise SystemExit('no such function ' + fname)
    i = idx[0]
    seg, start, name = funcs[i]
    end = funcs[i + 1][1] if i + 1 < len(funcs) and funcs[i + 1][0] == seg else start + 0x4000
    from lift import fix_fpu   # undo Borland's INT 34h-3Dh floating-point emulator encoding
    code = fix_fpu(exe[BASE + seg * 16 + start: BASE + seg * 16 + end])
    locs = locals_for(seg, start, end)
    lines = [f'; {demangle(name)}   {seg:04x}:{start:04x}-{end:04x}  ({end - start} bytes)',
             '; locals: ' + ', '.join(sorted({f"{n}@{'bp' if c == 2 else 'reg'}{(o - 0x10000) if o > 0x7fff else o:+d}" for (_, _, c, o, n) in locs}))]
    for ins in md.disasm(code, start):
        op = ins.op_str
        note = []
        if ins.mnemonic == 'lcall':
            m = re.match(r'(0x[0-9a-f]+|\d+), (0x[0-9a-f]+|\d+)$', op)
            if m:
                fs, fo = int(m.group(1), 0), int(m.group(2), 0)
                fn = func_at(fs, fo)
                if fn:
                    op = demangle(fn)
        elif ins.mnemonic == 'call' and op.startswith('0x'):
            fn = func_at(seg, int(op, 16) & 0xffff)
            if fn:
                op = demangle(fn)
        # bp locals
        for m in re.finditer(r'\[bp ([+-]) 0x([0-9a-f]+)\]', op):
            v = int(m.group(2), 16) * (1 if m.group(1) == '+' else -1)
            key = v & 0xffff
            for (a, b, c, o, n) in locs:
                if c == 2 and o == key and a <= ins.address < b:
                    note.append(f'{n}')
                    break
            else:
                if v > 0:
                    note.append(f'arg{(v - 6) // 2}')
        # absolute memory [0x1234] -> global
        for m in re.finditer(r'(?<![+-] )\[0x([0-9a-f]+)\]', op):
            dn = data_name(int(m.group(1), 16))
            if dn:
                note.append(dn)
        # immediates that look like strings
        m = re.search(r'(?:^|, )0x([0-9a-f]{3,4})$', op)
        if m and ins.mnemonic in ('mov', 'push'):
            s = ds_string(int(m.group(1), 16))
            if s and len(s) >= 3:
                note.append(repr(s))
        lines.append(f'{ins.address:04x}  {ins.mnemonic:6s} {op}' + ('    ; ' + ', '.join(note) if note else ''))
    base = re.sub(r'[^A-Za-z0-9_]', '_', demangle(name))[:60]
    path = os.path.join(OUT, f'{GAME_SEGS.get(seg, hex(seg))}_{base}.asm')
    open(path, 'w').write('\n'.join(lines) + '\n')
    return path, len(lines)


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--data']:
        for o, n in data_syms:
            if o < 0x3c50:
                print(f'{o:04x} {n}')
        sys.exit()
    if args == ['--list']:
        for seg, off, n in funcs:
            if seg in GAME_SEGS:
                print(f'{seg:04x}:{off:04x} {GAME_SEGS[seg]:6s} {demangle(n)}')
        sys.exit()
    if args == ['--all']:
        targets = [f[2] for f in funcs if f[0] in GAME_SEGS]
    else:
        targets = [f[2] for f in funcs if any(a == f[2] or a == demangle(f[2]).split('(')[0] for a in args)]
    for n in targets:
        p, cnt = disasm(n)
        print(cnt, p)
