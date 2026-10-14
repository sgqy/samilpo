"""Phase-3 probe: messages whose headLen is unusual (0x0a headLen 18, 0x19 headLen 0).

The full census reports:
  0x0a headLens=[0, 18]
  0x19 headLens=[0, 17, 18, 19, 20, 21]
  0x12 headLens=[0]
  0x2e headLens=[0]
This probe dumps those heads and their MsgHdr context to decide whether they
are real fields or parse artefacts.
"""
import struct, sys, os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_text as T

CODDIR = r'C:\Program Files (x86)\Samilpo 2.0'
FWD = T.parse_cod(os.path.join(CODDIR, '889F.cod'))[0]

CTX = defaultdict(Counter)     # (type, headLen) -> MsgHdr +20/+24 context
HEAD = defaultdict(Counter)
COUNT = Counter()


class Fail(Exception): pass

class R:
    def __init__(self, b): self.b, self.p = b, 0
    def take(self, n):
        if n < 0 or self.p + n > len(self.b): raise Fail()
        s = self.b[self.p:self.p+n]; self.p += n; return s


def core(r, t, role):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<H', h, 4)[0]
    head = r.take(headlen)
    if t in (0x0a, 0x09, 0x12, 0x2e) and headlen:
        HEAD['0x%02x' % t][head.hex(' ')] += 1
        COUNT['0x%02x/len%d' % (t, headlen)] += 1
        CTX['0x%02x' % t][(hex(hexlen(t, headlen)), role)] += 0
    if t == 0x19 and headlen == 0:
        COUNT['0x19/len0'] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    return head


def hexlen(t, headlen):
    return headlen


def msg(r):
    h = r.take(0x2c)
    t = h[0]
    COUNT['type 0x%02x' % t] += 1
    if t in (0x0a, 0x09, 0x12, 0x2e):
        key20 = struct.unpack_from('<I', h, 0x20)[0]
        key24 = struct.unpack_from('<I', h, 0x24)[0]
        CTX['0x%02x' % t][('k20_zero', key20 == 0)] += 1
        CTX['0x%02x' % t][('k24_zero', key24 == 0)] += 1
    core(r, t, 0)
    if t == 0x45: chord(r)


def cstr(r):
    n = struct.unpack('<h', r.take(2))[0]; return r.take(n)


def chord(r):
    cstr(r); n = r.take(1)[0]; r.take(n)
    msg(r); r.take(16)
    if struct.unpack('<h', r.take(2))[0]:
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
    core(r, 5, 0)
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
        core(r, 0, 0)
        n1, n2, x = struct.unpack('<hhI', r.take(8))
        for _ in range(n1+n2): staff(r)
        hdr = struct.unpack('<5h', r.take(10))
        for _ in range(3): msg(r)
        for _ in range(hdr[0]): page(r)
    except Fail:
        pass


def main():
    root = sys.argv[1]
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort()
    # scan the whole corpus but only gather the rare cases
    for i, f in enumerate(files):
        walk(f)
        if (i + 1) % 2000 == 0:
            print('  ...%d' % (i+1), flush=True)
    print()
    print('counts of interest:', {k: v for k, v in COUNT.items() if '/' in k})
    print()
    for t in ('0x0a', '0x09', '0x12', '0x2e'):
        print('%s heads (non-empty): %d distinct' % (t, len(HEAD[t])))
        for h, n in HEAD[t].most_common(4):
            print('    %s  x%d' % (h, n))
        if CTX[t]:
            print('    ctx:', dict(CTX[t].most_common(6)))


if __name__ == '__main__':
    main()
