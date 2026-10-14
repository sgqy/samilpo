"""Phase-3 probe 2: ObjectCore +1 byte, headLen by type, head prefixes.

Questions:
  Q1  ObjectCore disk byte +1: is it correlated with msg type (semantic) or
      uncorrelated (writer leaves uninitialized stack)? -> per-type top values
  Q2  type 0x01 headLen distribution (expect 12)
  Q3  Meas headLen (8/16/28) and its first bytes
  Q4  head first bytes for the high-frequency types (semantic hints)
  Q5  type 0x2c / 0x12 / 0x2e occurrences and heads
Usage: python _probe_p3_heads.py <dir> [maxfiles]
"""
import struct, sys, os
from collections import Counter, defaultdict

B1_BY_TYPE = defaultdict(Counter)
HL_BY_TYPE = defaultdict(Counter)
HEAD_BY_TYPE = defaultdict(Counter)
MEAS_HEAD = Counter()
MEAS_HL = Counter()
ODD6_DELTA = Counter()

class Fail(Exception):
    pass

class R:
    def __init__(self, b):
        self.b, self.p = b, 0
    def take(self, n):
        if n < 0 or self.p + n > len(self.b):
            raise Fail('overrun at +0x%x' % self.p)
        s = self.b[self.p:self.p + n]; self.p += n; return s
    def u8(self): return self.take(1)[0]
    def s16(self): return struct.unpack('<h', self.take(2))[0]
    def u32(self): return struct.unpack('<I', self.take(4))[0]


def core(r, kind):
    h = r.take(12)
    nchild, b1, headlen = h[0], h[1], struct.unpack_from('<H', h, 4)[0]
    f6 = struct.unpack_from('<H', h, 6)[0]
    if kind != 'obj':
        ODD6_DELTA[f6 - headlen] += 1
        B1_BY_TYPE[kind][b1] += 1
        HL_BY_TYPE[kind][headlen] += 1
    head = r.take(headlen)
    if kind in ('0x01', '0x03', '0x09', '0x0a', '0x12', '0x14', '0x18', '0x19', '0x1b', '0x2c', '0x2e', '0x2f', '0x3f', '0x40', '0x49', '0x45'):
        HEAD_BY_TYPE[kind][head[:4].hex()] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]:
            msg(r)
    return head, headlen


def msg(r):
    h = r.take(0x2c)
    t = h[0]
    core(r, '0x%02x' % t)
    if t == 0x45:
        chord(r)


def cstr(r):
    n = struct.unpack('<h', r.take(2))[0]
    return r.take(n)


def chord(r):
    cstr(r)
    n = r.take(1)[0]; r.take(n)
    msg(r); r.take(16)
    if struct.unpack('<h', r.take(2))[0]:
        msg(r)
        for _ in range(3): cstr(r)
        r.take(4 + 2 + 2 + 2)
        nev = struct.unpack('<i', r.take(4))[0]; esz = struct.unpack('<h', r.take(2))[0]
        r.take(nev * esz)
        n2 = struct.unpack('<h', r.take(2))[0]; sz2 = struct.unpack('<h', r.take(2))[0]
        r.take(n2 * sz2)


def meas(r):
    h = r.take(12)
    nchild = h[0]
    headlen = struct.unpack_from('<H', h, 4)[0]
    MEAS_HL[headlen] += 1
    head = r.take(headlen)
    MEAS_HEAD[(headlen, head[:8].hex())] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    r.take(0x60)


def staff(r):
    core(r, 'staff')
    t = r.take(0x70)
    for _ in range(struct.unpack_from('<i', t, 0x6c)[0]):
        meas(r)


def block(r):
    h = r.take(0x1c)
    nst, f2, npts = h[1], struct.unpack_from('<h', h, 2)[0], h[8]
    r.take(5 * nst); r.take(2 * (f2 + 1)); r.take(8 * npts)


def page(r):
    h = r.take(0x18)
    a, b, m = struct.unpack_from('<hhh', h, 0)
    for _ in range(a + b): block(r)
    for _ in range(m): msg(r)


def walk(path):
    d = open(path, 'rb').read()
    if struct.unpack_from('<I', d, 0)[0] != 0x58C: return False
    p = 4 + 0x58C
    sl = struct.unpack_from('<h', d, p)[0]; p += 2
    if sl > 1: p += sl
    smc = d[p:p + 0x318]
    if smc[:4] != b'SMC\0': return False
    p += 0x318 + struct.unpack_from('<I', smc, 0x314)[0]
    p += 2 + struct.unpack_from('<h', d, p)[0]
    p += 0x20
    blen = struct.unpack_from('<I', d, p)[0]; p += 4
    r = R(d[p:p + blen])
    try:
        core(r, 'system')
        n1, n2, x = struct.unpack('<hhI', r.take(8))
        for _ in range(n1 + n2): staff(r)
        hdr = struct.unpack('<5h', r.take(10))
        for _ in range(3): msg(r)
        for _ in range(hdr[0]): page(r)
        return r.p == blen
    except Fail:
        return False


def main():
    root = sys.argv[1]
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort()
    step = max(1, len(files) // maxn)
    files = files[::step][:maxn]
    ok = sum(walk(f) for f in files)
    print('files ok: %d/%d' % (ok, len(files)))
    print('+06-headLen deltas:', dict(ODD6_DELTA))
    print()
    print('b1 by kind (top5, total):')
    for k in sorted(B1_BY_TYPE, key=lambda k: -sum(B1_BY_TYPE[k].values())):
        tot = sum(B1_BY_TYPE[k].values())
        print('  %-8s n=%-7d %s' % (k, tot, B1_BY_TYPE[k].most_common(5)))
    print()
    print('headLen by kind:')
    for k in sorted(HL_BY_TYPE):
        tot = sum(HL_BY_TYPE[k].values())
        print('  %-8s n=%-7d %s' % (k, tot, HL_BY_TYPE[k].most_common(5)))
    print()
    print('Meas headLen:', dict(MEAS_HL))
    print('Meas head (len, first8) top:')
    for (l, hx), n in MEAS_HEAD.most_common(10):
        print('   len=%-3d %s  x%d' % (l, hx, n))
    print()
    print('head first-4-bytes by type (top3):')
    for k in sorted(HEAD_BY_TYPE, key=lambda k: -sum(HEAD_BY_TYPE[k].values())):
        print('  %-8s %s' % (k, HEAD_BY_TYPE[k].most_common(3)))


if __name__ == '__main__':
    main()
