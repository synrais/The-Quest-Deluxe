"""Naive pattern lifter: TheQuest.exe (Borland C++ 3.1, unoptimised) -> pseudo-C with gotos.

usage: python lift.py <func> [...] | --all      -> writes pc/<SEG>_<func>.c
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import qdis
from qdis import t, exe, BASE, funcs, GAME_SEGS, demangle, func_at, ds_string, locals_for, md

OUT = os.path.join(qdis.HERE, 'out', 'pc')
os.makedirs(OUT, exist_ok=True)

SQUARE = {0: 'floor', 2: 'wall', 4: 'mon', 6: 'item', 8: 'gold', 10: 'deco'}
HERO = 'mlife life mmana mana bstr bintl bdex bacc dex acc intl str def atk rep power warm marm level exper type invisible poisoned'.split()
INV = 'bkey rkey ykey coins rose red purple blue white cyan yellow black'.split()
ST = 'mons ems killer armboost powboost Shield fShield level mission1 mission2 saveslot p1 p2 p3'.split()
SKILL = 'amb bar sch mem mar cow hon ras'.split()
MON = 'type x y life mlife atk def power range warm marm att'.split()
MATRICES = {0xe8: ('map', 'sq'), 0xf2: ('room', 'sq'), 0xfc: ('carta', 'int'), 0x14e: ('bag', 'int'),
            0x15a: ('store', 'int'), 0x166: ('book', 'int'), 0x172: ('items', 'int'), 0x17e: ('prices', 'int'),
            0x18a: ('spellss', 'int'), 0x196: ('monsterss', 'int')}
STRUCTS = [(0x108, 'hero', HERO), (0x136, 'inv', INV), (0x1b6, 'st', ST), (0x1a6, 'skill', SKILL)]
SIMPLE = {0x1a2: 'turns', 0x1a4: 'lvup', 0x1d2: 'moved', 0x1d4: 'otarw', 0x31e0: 'ax_', 0x31e2: 'ay_',
          0x3b44: 'X', 0x3b46: 'Y', 0x3c4e: 'leaving', 0x90: 'Xx', 0x92: 'Yy', 0x94: 'StL', 0xe6: 'me'}
LIB = {  # seg 0 runtime helpers seen a lot
}


def gname(off):
    if off in SIMPLE:
        return SIMPLE[off]
    for base, nm, fields in STRUCTS:
        if base <= off < base + 2 * len(fields):
            k = (off - base) // 2
            return f'{nm}.{fields[k]}' + ('' if (off - base) % 2 == 0 else '+1')
    if 0x31e4 <= off < 0x3b44:
        k, r = divmod(off - 0x31e4, 24)
        return f'enemies[{k}].{MON[r // 2]}'
    if 0x3b48 <= off < 0x3c10:
        return f'move[{(off - 0x3b48) // 2}]'
    if 0x3c10 <= off < 0x3c24:
        return f'fkey[{(off - 0x3c10) // 2}]'
    if 0x3c24 <= off < 0x3c4e:
        return f'spells[{(off - 0x3c24) // 2}]'
    for mo, (nm, _) in MATRICES.items():
        if off == mo:
            return nm
    dn = qdis.data_name(off)
    return dn or f'DS[{off:#x}]'


def fix_fpu(code):
    """Undo Borland's x87 emulator encoding (INT 34h-3Dh) so the bytes decode as real FPU ops.
    Lengths are preserved so addresses stay valid."""
    b = bytearray(code)
    i = 0
    while i < len(b) - 1:
        if b[i] == 0xCD and 0x34 <= b[i + 1] <= 0x3B:
            b[i] = 0x9B                       # fwait
            b[i + 1] = 0xD8 + (b[i + 1] - 0x34)  # ESC opcode
            i += 2
        elif b[i] == 0xCD and b[i + 1] == 0x3C and i + 2 < len(b):
            # segment-override form: CD 3C xx modrm -> prefix ESC modrm
            x = b[i + 2]
            seg = {0x00: 0x26, 0x40: 0x2E, 0x80: 0x36, 0xC0: 0x3E}.get(x & 0xC0, 0x26)
            b[i] = 0x9B
            b[i + 1] = seg
            b[i + 2] = x | 0xC0 if (x | 0xC0) >= 0xD8 else 0xD8 | (x & 7)
            i += 3
        elif b[i] == 0xCD and b[i + 1] == 0x3D:
            b[i], b[i + 1] = 0x90, 0x9B          # nop; fwait
            i += 2
        else:
            i += 1
    return bytes(b)


JCC = {'je': '==', 'jne': '!=', 'jl': '<', 'jge': '>=', 'jg': '>', 'jle': '<=', 'jb': '<u', 'jae': '>=u',
       'ja': '>u', 'jbe': '<=u'}


class Lifter:
    def __init__(self, name):
        i = [k for k, f in enumerate(funcs) if f[2] == name][0]
        self.seg, self.start, self.name = funcs[i]
        self.end = funcs[i + 1][1] if i + 1 < len(funcs) and funcs[i + 1][0] == self.seg else self.start + 0x4000
        code = fix_fpu(exe[BASE + self.seg * 16 + self.start: BASE + self.seg * 16 + self.end])
        self.ins = list(md.disasm(code, self.start))
        self.locs = locals_for(self.seg, self.start, self.end)
        self.targets = set()
        for x in self.ins:
            if x.mnemonic.startswith('j') and x.op_str.startswith('0x'):
                self.targets.add(int(x.op_str, 16) & 0xffff)

    def local(self, v, addr):
        key = v & 0xffff
        for (a, b, c, o, n) in self.locs:
            if c == 2 and o == key and a <= addr < b:
                return n
        if v > 0:
            return f'arg{(v - 6) // 2}'
        return f'bp{v:+#x}'

    def reglocal(self, reg, addr):
        regs = {'si': 6, 'di': 7}
        for (a, b, c, o, n) in self.locs:
            if c == 4 and o == regs.get(reg) and a <= addr < b:
                return n
        return None

    def mem(self, op, addr):
        op = re.sub(r'^(?:(?:byte|word|dword|qword|tbyte|xword) )?ptr ', '', op)
        m = re.fullmatch(r'\[bp ([+-]) 0x([0-9a-f]+)\]', op)
        if m:
            return self.local(int(m.group(2), 16) * (1 if m.group(1) == '+' else -1), addr)
        m = re.fullmatch(r'\[0x([0-9a-f]+)\]', op)
        if m:
            return gname(int(m.group(1), 16))
        m = re.fullmatch(r'\[(bx|si|di) \+ 0x([0-9a-f]+)\]', op)
        if m:
            r, n = m.group(1), int(m.group(2), 16)
            idx = self.regs.get(r) or self.reglocal(r, addr) or r
            mm = re.fullmatch(r'\((.*) \* 24\)', idx)
            if mm and 0x31e4 <= n < 0x3b44:
                k, rem = divmod(n - 0x31e4, 24)
                return f'enemies[{mm.group(1)}{"+" + str(k) if k else ""}].{MON[rem // 2]}'
            mm = re.fullmatch(r'\((.*) (?:<< 1|\* 2)\)', idx)
            g = gname(n)
            if mm:
                base = re.sub(r'\[\d+\]', '', g)
                if '[' not in g:
                    return f'{g}[{mm.group(1)}]'
                start = int(re.search(r'\[(\d+)\]', g).group(1))
                return f'{base.split(".")[0]}[{mm.group(1)}{"+" + str(start) if start else ""}]' + ('.' + g.split('.')[1] if '.' in g else '')
            return f'{g}{{{idx}}}'
        m = re.fullmatch(r'es:\[bx(?: \+ 0x([0-9a-f]+)| \+ (\d+))?\]', op)
        if m:
            off = int(m.group(1) or m.group(2) or '0', 16 if m.group(1) else 10)
            base = self.esbx
            if base and base.endswith('#sq'):
                return base[:-3] + '.' + SQUARE.get(off, f'+{off}')
            if base and base.endswith('#int'):
                return base[:-4] + (f'+{off}' if off else '')
            if base and base.endswith('#?'):
                return base[:-2] + '.' + SQUARE.get(off, f'+{off}')
            if base and re.fullmatch(r'[A-Za-z_]\w*', base):
                return f'*{base}' if off == 0 else f'{base}->[{off}]'
            return f'({base or "es:bx"})[{off}]'
        return None

    def val(self, op, addr):
        op = op.strip()
        if op in self.regs:
            return self.regs[op]
        if op in ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'al', 'ah', 'bl', 'cl', 'dl'):
            nm = self.reglocal(op, addr)
            return nm or op
        m = self.mem(op, addr)
        if m:
            return m
        if re.fullmatch(r'-?0x[0-9a-f]+|-?\d+', op):
            v = int(op, 0)
            if v > 0x7fff:
                v -= 0x10000
            return str(v)
        return op

    def run(self):
        out = [f'// {demangle(self.name)}   {self.seg:04x}:{self.start:04x}  ({self.end - self.start} bytes)']
        self.regs, self.stack, self.esbx, self.fp = {}, [], None, []
        cmp = None
        ins = self.ins
        k = 0
        while k < len(ins):
            x = ins[k]
            a, mn, op = x.address, x.mnemonic, x.op_str
            ops = [o.strip() for o in op.split(',')] if op else []
            if a in self.targets:
                out.append(f'L{a:04x}:')
                self.regs, self.esbx = {}, None
            emit = None
            if mn in ('push',):
                if ops[0] in ('ds', 'cs', 'ss'):
                    self.stack.append('@' + ops[0])
                else:
                    self.stack.append(self.val(ops[0], a))
            elif mn in ('pop',):
                v = self.stack.pop() if self.stack else '?'
                if ops and ops[0] in ('ax', 'bx', 'cx', 'dx'):
                    self.regs[ops[0]] = v
            elif mn in ('call', 'lcall'):
                if mn == 'lcall':
                    mm = re.match(r'(0x[0-9a-f]+|\d+), (0x[0-9a-f]+|\d+)$', op)
                    fn = func_at(int(mm.group(1), 0), int(mm.group(2), 0)) if mm else None
                else:
                    fn = func_at(self.seg, int(op, 16) & 0xffff) if op.startswith('0x') else None
                if mn == 'call' and self.stack and self.stack[-1] == '@cs':
                    self.stack.pop()
                nbytes = 0
                if k + 1 < len(ins) and ins[k + 1].mnemonic == 'add' and ins[k + 1].op_str.startswith('sp, '):
                    nbytes = int(ins[k + 1].op_str[4:], 0)
                    k += 1
                raw = []
                for _ in range(nbytes // 2):
                    raw.append(self.stack.pop() if self.stack else '?')
                # merge far pointers (seg, off) -> &thing
                args = []
                j = 0
                while j < len(raw):
                    if j + 1 < len(raw) and re.fullmatch(r'arg\d+|bp[+-]0x[0-9a-f]+', raw[j + 1]) and re.fullmatch(r'[A-Za-z_]\w*', raw[j]) and not raw[j].startswith(('arg', 'ret_')):
                        args.append(raw[j] + '#?')   # far pointer param (off, seg)
                        j += 2
                    elif j + 1 < len(raw) and raw[j + 1] == f'hi({raw[j]})':
                        args.append(raw[j])
                        j += 2
                    elif j + 1 < len(raw) and raw[j + 1] in ('@ds', '@ss'):
                        o = raw[j]
                        if raw[j + 1] == '@ds' and re.fullmatch(r'-?\d+', o):
                            v = int(o) & 0xffff
                            s = ds_string(v)
                            if v in MATRICES:
                                o = MATRICES[v][0] + '#' + MATRICES[v][1]
                            elif s is not None and len(s) >= 2:
                                o = repr(s)
                            else:
                                o = '&' + gname(v)
                        args.append(o)
                        j += 2
                    else:
                        args.append(raw[j])
                        j += 1
                fname = demangle(fn) if fn else f'sub_{op}'
                short = fname.split('(')[0]
                if short in ('LXMUL@', 'LXLSH@'):
                    if short == 'LXLSH@':
                        cl = self.regs.get('cl', '?')
                        self.pending_rand = str(2 ** int(cl)) if re.fullmatch(r'\d+', cl) else f'1<<{cl}'
                    else:
                        self.pending_rand = self.regs.get('ax', '?')
                    self.regs['ax'] = self.regs['dx:ax'] = 'lmul'
                    k += 1
                    continue
                if short in ('LDIV@', 'LUDIV@', 'LMOD@', 'LUMOD@'):
                    for _ in range(4):
                        if self.stack:
                            self.stack.pop()
                    n = getattr(self, 'pending_rand', '?')
                    self.regs['ax'] = self.regs['dx:ax'] = f'random({n})'
                    self.regs['dx'] = f'hi(random({n}))'
                    k += 1
                    continue
                if short == 'rand' and nbytes == 0:
                    k += 1
                    continue
                if 'matrix' in fname and 'bsubs' in fname and len(args) >= 2:
                    res = f'{args[0].split("#")[0]}[{args[1]}]#' + (args[0].split('#')[1] if '#' in args[0] else '?')
                elif 'vector' in fname and 'bsubs' in fname and len(args) >= 2:
                    base = args[0]
                    kind = base.split('#')[-1] if '#' in base else '?'
                    res = f'{base.split("#")[0]}[{args[1]}]#{kind}'
                else:
                    res = f'{short}({", ".join(args)})'
                    emit = res
                    res = f'ret_{short}'
                self.regs['ax'] = res
                self.regs['dx:ax'] = res
                self.regs['dx'] = 'hi(' + res + ')'
            elif mn == 'add' and ops and ops[0] == 'sp':
                for _ in range(int(ops[1], 0) // 2):
                    if self.stack:
                        self.stack.pop()
            elif mn == 'sub' and ops and ops[0] == 'sp':
                pass
            elif mn == 'mov' and len(ops) == 2:
                dst, src = ops
                if dst == 'es' and src == 'dx':
                    pass
                elif dst == 'bx' and src == 'ax' and self.regs.get('ax', '').count('#'):
                    self.esbx = self.regs['ax']
                    self.regs['bx'] = self.regs['ax']
                elif dst in ('ax', 'bx', 'cx', 'dx', 'al', 'ah', 'bl', 'cl', 'dl', 'es') and not self.reglocal(dst, a):
                    v = self.val(src, a)
                    self.regs[dst] = v
                    if dst == 'al':
                        self.regs['ax'] = v
                else:
                    emit = f'{self.val(dst, a)} = {self.val(src, a)}'
                    if dst in ('si', 'di'):
                        self.regs.pop(dst, None)
            elif mn == 'xchg' and ops == ['bx', 'ax']:
                ax, bx = self.regs.get('ax', 'ax'), self.regs.get('bx', 'bx')
                self.regs['ax'], self.regs['bx'] = bx, ax
                if '#' in ax:
                    self.esbx = ax
            elif mn in ('cwde', 'cwd', 'cdq', 'cbw', 'nop', 'leave', 'retf', 'ret', 'push', 'enter'):
                if mn in ('retf', 'ret'):
                    emit = f'return {self.regs.get("ax", "")}'.rstrip()
            elif mn == 'lea' and len(ops) == 2:
                self.regs[ops[0]] = '&' + (self.mem(ops[1], a) or ops[1])
            elif mn == 'les' and len(ops) == 2:
                self.esbx = self.mem(ops[1], a)
                self.regs['bx'] = self.esbx
            elif mn in ('cmp', 'test', 'or') and len(ops) == 2:
                if mn == 'or' and ops[0] == ops[1]:
                    cmp = (self.val(ops[0], a), '0')
                elif mn == 'or':
                    emit = f'{self.val(ops[0], a)} |= {self.val(ops[1], a)}'
                    cmp = (self.val(ops[0], a), '0')
                elif mn == 'test':
                    cmp = (f'{self.val(ops[0], a)} & {self.val(ops[1], a)}', '0')
                else:
                    cmp = (self.val(ops[0], a), self.val(ops[1], a))
            elif mn in JCC:
                tgt = int(op, 16) & 0xffff
                if cmp:
                    emit = f'if ({cmp[0]} {JCC[mn]} {cmp[1]}) goto L{tgt:04x}'
                else:
                    emit = f'if (?{mn}) goto L{tgt:04x}'
            elif mn == 'jmp' and op.startswith('0x'):
                emit = f'goto L{int(op, 16) & 0xffff:04x}'
            elif mn in ('inc', 'dec') and len(ops) == 1:
                tgt = ops[0]
                if tgt in ('ax', 'bx', 'cx', 'dx') and not self.reglocal(tgt, a):
                    self.regs[tgt] = f'({self.val(tgt, a)} {"+" if mn == "inc" else "-"} 1)'
                else:
                    emit = f'{self.val(tgt, a)}{"++" if mn == "inc" else "--"}'
            elif mn in ('add', 'sub', 'imul', 'and', 'xor', 'shl', 'sar', 'shr', 'adc', 'sbb', 'neg', 'not', 'idiv', 'div') and ops:
                opch = {'add': '+', 'sub': '-', 'imul': '*', 'and': '&', 'xor': '^', 'shl': '<<', 'sar': '>>', 'shr': '>>',
                        'adc': '+c+', 'sbb': '-b-', 'idiv': '/', 'div': '/'}.get(mn, mn)
                if mn == 'imul' and len(ops) == 1:
                    self.regs['ax'] = f'({self.regs.get("ax", "ax")} * {self.val(ops[0], a)})'
                elif mn in ('idiv', 'div'):
                    q = self.regs.get('ax', 'ax')
                    dv = self.val(ops[0], a)
                    self.regs['ax'] = f'({q} / {dv})'
                    self.regs['dx'] = f'({q} % {dv})'
                elif mn in ('neg', 'not'):
                    tgt = ops[0]
                    if tgt in ('ax', 'bx', 'dx', 'cx'):
                        self.regs[tgt] = f'{"-" if mn == "neg" else "~"}{self.val(tgt, a)}'
                    else:
                        emit = f'{self.val(tgt, a)} = {"-" if mn == "neg" else "~"}{self.val(tgt, a)}'
                elif mn == 'xor' and ops[0] == ops[1]:
                    if ops[0] in ('si', 'di') and self.reglocal(ops[0], a):
                        emit = f'{self.reglocal(ops[0], a)} = 0'
                    else:
                        self.regs[ops[0]] = '0'
                else:
                    tgt = ops[0]
                    src = self.val(ops[1], a) if len(ops) > 1 else '?'
                    if len(ops) == 3:
                        self.regs[tgt] = f'({self.val(ops[1], a)} * {self.val(ops[2], a)})'
                    elif tgt in ('ax', 'bx', 'cx', 'dx', 'al', 'dl') and not self.reglocal(tgt, a):
                        self.regs[tgt] = f'({self.val(tgt, a)} {opch} {src})'
                    else:
                        emit = f'{self.val(tgt, a)} {opch}= {src}'
                cmp = None
            elif mn == 'rcl' and ops == ['dx', '1']:
                self.pending_rand = '2'
            elif mn in ('fld', 'fild') and ops:
                self.fp.append(self.val(ops[0], a) if not ops[0].startswith('st') else self.fp[-1] if self.fp else 'st')
            elif mn in ('fld1', 'fldz'):
                self.fp.append('1' if mn == 'fld1' else '0')
            elif mn in ('fadd', 'fsub', 'fmul', 'fdiv', 'fsubr', 'fdivr', 'fiadd', 'fisub', 'fimul', 'fidiv',
                        'faddp', 'fsubp', 'fmulp', 'fdivp', 'fsubrp', 'fdivrp'):
                o = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/'}[re.sub(r'^fi?|r?p?$', '', mn)[:3]]
                rev = 'r' in mn[3:]
                if not ops or ops[0].startswith('st'):
                    b_ = self.fp.pop() if self.fp else 'st0'
                    a_ = self.fp.pop() if self.fp else 'st1'
                else:
                    b_ = self.val(ops[-1], a)
                    a_ = self.fp.pop() if self.fp else 'st0'
                self.fp.append(f'({b_} {o} {a_})' if rev else f'({a_} {o} {b_})')
            elif mn in ('fstp', 'fistp', 'fst', 'fist') and ops:
                v = (self.fp.pop() if mn.endswith('p') else self.fp[-1]) if self.fp else 'st0'
                if not ops[0].startswith('st'):
                    emit = f'{self.val(ops[0], a)} = {v}'
            elif mn in ('fcomp', 'fcompp', 'fcom', 'ficomp', 'ficom'):
                rhs = self.val(ops[0], a) if ops and not ops[0].startswith('st') else (self.fp.pop() if self.fp else 'st1')
                lhs = self.fp.pop() if self.fp else 'st0'
                self.fcmp = (lhs, rhs)
            elif mn in ('fnstsw', 'fstsw', 'wait', 'fwait', 'sahf'):
                if mn == 'sahf' and getattr(self, 'fcmp', None):
                    cmp = self.fcmp
            elif mn in ('fsqrt', 'fabs', 'fchs', 'frndint'):
                if self.fp:
                    self.fp[-1] = f'{mn[1:]}({self.fp[-1]})'
            elif mn == 'fxch':
                if len(self.fp) >= 2:
                    self.fp[-1], self.fp[-2] = self.fp[-2], self.fp[-1]
            else:
                emit = f'__asm {mn} {op}'
            if emit:
                out.append('    ' + emit + ';')
            k += 1
        return '\n'.join(out) + '\n'


def lift(name):
    L = Lifter(name)
    base = re.sub(r'[^A-Za-z0-9_]', '_', demangle(name))[:60]
    path = os.path.join(OUT, f'{GAME_SEGS.get(L.seg, hex(L.seg))}_{base}.c')
    txt = L.run()
    open(path, 'w').write(txt)
    return path, txt.count('\n')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--all']:
        targets = [f[2] for f in funcs if f[0] in GAME_SEGS and f[0] != 0x1987]
    else:
        targets = [f[2] for f in funcs if any(x == f[2] or x == demangle(f[2]).split('(')[0] for x in args)]
    for n in targets:
        try:
            p, c = lift(n)
            print(c, os.path.basename(p))
        except Exception as e:
            print('FAIL', n, e)
