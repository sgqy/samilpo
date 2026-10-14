"""Phase-3 probe: type 0x45 (chord symbol) head contents.

Census shows type 0x45 headLen in {0, 100}; 0x45 heads starting with byte
pairs that look like 889F text. Decode them and the ChordExtra surfix name.
"""
import struct, sys, os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_text as T

CODDIR = r'C:\Program Files (x86)\Samilpo 2.0'
FWD = None


class Fail(Exception): pass

class R:
    def __init__(self, b): self.b, self.p = b, 0
    def take(self, n):
        if n < 0 or self.p + n > len(self.b): raise Fail()
        s = self.b[self.p:self.p+n]; self.p += n; return s

HL = Counter()
H45 = Counter()
SURFIX = Counter()
RHY = Counter()


def core(r, t):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<H', h, 4)[0]
    if t == 0x45:
        HL[headlen] += 1
    head = r.take(headlen)
    if t == 0x45 and headlen == 100:
        H45[T.decode(head, FWD)] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    return head


def msg(r):
    h = r.take(0x2c)
    core(r, h[0])
    if h[0] == 0x45: chord(r)


def cstr(r):
    n = struct.unpack('<h', r.take(2))[0]; return r.take(n)


def chord(r):
    name = cstr(r)
    if name:
        SURFIX[T.decode(name, FWD)] += 1
    n = r.take(1)[0]; r.take(n)
    msg(r); r.take(16)
    hr = struct.unpack('<h', r.take(2))[0]
    RHY[hr != 0] += 1
    if hr:
        msg(r)
        for _ in range(3): cstr(r)
        r.take(10)
        nev = struct.unpack('<i', r.take(4))[0]; esz = struct.unpack('<h', r.take(2))[0]
        r.take(nev*esz)
        n2 = struct.unpack('<h', r.take(2))[0]; sz2 = struct.unpack('<h', r.take(2))[0]
        r.take(n2*sz2)


def meas(r):
    h = r.take(12); nchild = h[0]; headlen = struct.unpack_from('<H', h, 4)[0]
    r.take(headlen)
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    r.take(0x60)


def staff(r):
    core(r, 5)
    t = r.take(0x70)
    for _ in range(struct.unpack_from('<i', t, 0x6c)[0]): meas(r)


def block(r):
    h = r.take(0x1c)
    nst, f2, npts = h[1], struct.unpack_from('<h', h, 2)[0], h[8]
    r.take(5*nst); r.take(2*(f2+1)); r.take(8*npts)


def page(r):
    h = r.take(0x18)
    a, b, m = struct.unpack_from('<hhh', h, 0)
    for _ in range(a+b): block(r)
    for _ in range(m): msg(r)


def walk(path):
    d = open(path, 'rb').read()
    if struct.unpack_from('<I', d, 0)[0] != 0x58C: return
    p = 4 + 0x58C
    sl = struct.unpack_from('<h', d, p)[0]; p += 2
    if sl > 1: p += sl
    smc = d[p:p+0x318]
    if smc[:4] != b'SMC\0': return
    p += 0x318 + struct.unpack_from('<I', smc, 0x314)[0]
    p += 2 + struct.unpack_from('<h', d, p)[0]
    p += 0x20
    blen = struct.unpack_from('<I', d, p)[0]; p += 4
    r = R(d[p:p+blen])
    try:
        core(r, 0)
        n1, n2, x = struct.unpack('<hhI', r.take(8))
        for _ in range(n1+n2): staff(r)
        hdr = struct.unpack('<5h', r.take(10))
        for _ in range(3): msg(r)
        for _ in range(hdr[0]): page(r)
    except Fail:
        pass


def main():
    global FWD
    root = sys.argv[1]
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    FWD = T.parse_cod(os.path.join(CODDIR, '889F.cod'))[0]
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort(); step = max(1, len(files)//maxn); files = files[::step][:maxn]
    for f in files:
        walk(f)
    print('0x45 headLen:', dict(HL))
    print('rhythm present:', dict(RHY))
    print()
    print('0x45 head (len 100) decoded, top 25:')
    for s, n in H45.most_common(25):
        print('   %-20r x%d' % (s, n))
    print()
    print('ChordExtra surfix name, top 25:')
    for s, n in SURFIX.most_common(25):
        print('   %-20r x%d' % (s, n))


if __name__ == '__main__':
    main()
