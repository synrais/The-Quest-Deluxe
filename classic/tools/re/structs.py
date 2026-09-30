import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from tds import TDS
t = TDS()
d = t.d
TYPES = 132078
MEMBERS = 146430
NT, NM = 1196, 1239


def trec(i):  # 1-based type index
    o = TYPES + (i - 1) * 12
    r = d[o:o + 12]
    tid = r[0]
    name = struct.unpack_from('<I', r, 1)[0]
    size = struct.unpack_from('<H', r, 5)[0]
    return tid, t.name(name), size, r


def mrec(i):  # 1-based member index
    o = MEMBERS + (i - 1) * 9
    fl = d[o]
    name, typ = struct.unpack_from('<II', d, o + 1)
    return fl, t.name(name), typ


def tname(i, depth=0):
    tid, nm, size, r = trec(i)
    if nm:
        return nm
    if depth > 3:
        return f't{i}'
    sub = struct.unpack_from('<H', r, 8)[0]
    kinds = {0x04: 'char', 0x05: 'int', 0x06: 'long', 0x08: 'uchar', 0x09: 'uint', 0x0a: 'ulong'}
    if tid in kinds:
        return kinds[tid]
    if tid == 0x16 or tid == 0x1a:   # array
        return f'{tname(sub, depth + 1)}[{size}B]'
    return f'tid{tid:02x}(size{size},sub{sub})'


if __name__ == '__main__':
    for i in range(1, 12):
        print(i, trec(i)[:3], trec(i)[3].hex(' '))
    for want in ('heroo', 'inve', 'monsters', 'skills', 'statuss', 'square'):
        for i in range(1, NT + 1):
            tid, nm, size, r = trec(i)
            if nm == want and tid == 0x1e:
                m0 = struct.unpack_from('<H', r, 8)[0]
                print(f'\nstruct {nm} (type {i}, {size} bytes, members from {m0})')
                j = m0
                while j <= NM:
                    fl, mn, mt = mrec(j)
                    print(f'   [{j}] fl={fl:02x} {mn:20s} type={mt} {tname(mt) if 0 < mt <= NT else ""}')
                    if fl & 0x40 or j - m0 > 60:
                        break
                    j += 1
                break
