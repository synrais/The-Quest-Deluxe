"""Parser for the Borland Turbo Debugger (TDS v4.01) info appended to TheQuest.exe.

The exe ships with its full debug symbols: every function, global, local
variable, struct type/field and source line.  This module reads the tables.
"""
import struct, os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
GAME_EXE = os.path.join(PROJECT, 'packs', 'TheQuest', 'TheQuest.exe')

HDR_FMT = '<HHIIIIIIIIIIIIIIIBHHBH'


def load_exe(path=None) -> bytes:
    """TheQuest.exe bytes: an explicit path, else the original's, in packs/TheQuest."""
    with open(path if path and os.path.exists(path) else GAME_EXE, 'rb') as fh:
        return fh.read()


class TDS:
    def __init__(self, path=None):
        self.exe = load_exe(path)
        b = self.exe
        cblp, cp = struct.unpack_from('<HH', b, 2)
        self.hdr_paras = struct.unpack_from('<H', b, 8)[0]
        self.image_base = self.hdr_paras * 16
        self.image_end = (cp - 1) * 512 + (cblp or 512)
        d = b[self.image_end:]
        self.d = d
        (magic, ver, names_size, n_names, n_types, n_members, n_symbols, n_globals,
         n_modules, n_locals, n_scopes, n_lines, n_sources, n_segments, n_corr,
         image_size, hook, pflags, strseg, data_count, filler, ext) = struct.unpack_from(HDR_FMT, d, 0)
        assert magic == 0x52FB, hex(magic)
        self.h = dict(ver=hex(ver), names_size=names_size, names=n_names, types=n_types,
                      members=n_members, symbols=n_symbols, globals=n_globals, modules=n_modules,
                      locals=n_locals, scopes=n_scopes, lines=n_lines, sources=n_sources,
                      segments=n_segments, corr=n_corr, image_size=image_size, ext=ext)
        p = struct.calcsize(HDR_FMT) + ext
        # names pool is at the very end
        pool = d[len(d) - names_size:]
        self.names = [''] + [s.decode('latin1') for s in pool.split(b'\0')[:n_names]]

        def table(count, fmt):
            nonlocal p
            sz = struct.calcsize(fmt)
            rows = [struct.unpack_from(fmt, d, p + i * sz) for i in range(count)]
            p += count * sz
            return rows

        self.symbols = table(n_symbols, '<HHHHB')
        self.modules = table(n_modules, '<HBBHHHHHH')
        self.sources = table(n_sources, '<HI')
        self.lines = table(n_lines, '<HH')
        self.scopes = table(n_scopes, '<HHHHHH')
        self.segments = table(n_segments, '<HHHHHHHH')
        self.corr = table(n_corr, '<HHHH')
        self.types_start = p
        self.types_end = len(d) - names_size

    def name(self, i):
        return self.names[i] if 0 <= i < len(self.names) else f'?{i}'

    def sym(self, i):
        idx, typ, off, seg, flags = self.symbols[i]
        return dict(name=self.name(idx), type=typ, off=off, seg=seg, cls=flags & 7, flags=flags)


if __name__ == '__main__':
    t = TDS()
    print(t.h)
    print(t.d[:128].hex(' '))
    print('types region', t.types_start, t.types_end, t.types_end - t.types_start)
    for m in t.modules:
        print('module', t.name(m[0]), m)
    for s in t.sources:
        print('source', t.name(s[0]))
    for s in t.segments:
        print('segment', s)
    for i in range(0, 40):
        print(t.sym(i))
