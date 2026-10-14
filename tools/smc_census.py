"""Phase-3 full-corpus census: message type frequencies and field distributions.

Walks every .smc under the given root with the recovered framing and reports:
  * message type histogram (all files)
  * head length histogram per type
  * note head field distributions (key/velocity/duration/dots/headtype)
  * measure time signature distribution
  * block geometry histogram
  * framing success rate and exact-consumption check
"""
import struct, sys, os
from collections import Counter, defaultdict

MSG = Counter()
HL = defaultdict(Counter)
KEY = Counter()
VEL = Counter()
DUR = Counter()
DOTS = Counter()
HTYPE = Counter()
DURIDX = Counter()
TSN, TSD = Counter(), Counter()
BLK = Counter()
OK, BAD, LEGACY = Counter(), Counter(), Counter()
HEADHASH = defaultdict(Counter)

class Fail(Exception):
    pass

class R:
    def __init__(self, b): self.b, self.p = b, 0
    def take(self, n):
        if n < 0 or self.p + n > len(self.b): raise Fail()
        s = self.b[self.p:self.p+n]; self.p += n; return s


def core(r, t):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<H', h, 4)[0]
    HL[t][headlen] += 1
    head = r.take(headlen)
    if t == 1 and len(head) == 12:
        KEY[head[0]] += 1
        VEL[head[1]] += 1
        DUR[struct.unpack_from('<I', head, 4)[0]] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    return head


def msg(r):
    h = r.take(0x2c)
    t = h[0]
    MSG[t] += 1
    DOTS[h[5] & 0x0f] += 1
    HTYPE[struct.unpack_from('<H', h, 6)[0]] += 1
    DURIDX[struct.unpack_from('<H', h, 8)[0]] += 1
    core(r, t)
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
        r.take(nev * esz)
        n2 = struct.unpack('<h', r.take(2))[0]; sz2 = struct.unpack('<h', r.take(2))[0]
        r.take(n2 * sz2)


def meas(r):
    h = r.take(12); nchild = h[0]
    headlen = struct.unpack_from('<H', h, 4)[0]
    r.take(headlen)
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    tail = r.take(0x60)
    TSN[struct.unpack_from('<h', tail, 0x56)[0]] += 1
    TSD[struct.unpack_from('<h', tail, 0x58)[0]] += 1


def staff(r):
    core(r, 5)
    t = r.take(0x70)
    for _ in range(struct.unpack_from('<i', t, 0x6c)[0]): meas(r)


def block(r):
    h = r.take(0x1c)
    nst, f2, npts = h[1], struct.unpack_from('<h', h, 2)[0], h[8]
    BLK[(nst, f2, npts)] += 1
    r.take(5*nst); r.take(2*(f2+1)); r.take(8*npts)


def page(r):
    h = r.take(0x18)
    a, b, m = struct.unpack_from('<hhh', h, 0)
    for _ in range(a+b): block(r)
    for _ in range(m): msg(r)


def walk(path):
    d = open(path, 'rb').read()
    if struct.unpack_from('<I', d, 0)[0] != 0x58C:
        LEGACY['n'] += 1
        return
    p = 4 + 0x58C
    sl = struct.unpack_from('<h', d, p)[0]; p += 2
    if sl > 1: p += sl
    smc = d[p:p+0x318]
    if smc[:4] != b'SMC\0':
        BAD['nosmc'] += 1
        return
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
        if r.p == blen and len(d) == p + blen + 4:
            OK['n'] += 1
        else:
            BAD['size'] += 1
    except Fail:
        BAD['walk'] += 1


def main():
    root = sys.argv[1]
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort()
    for i, f in enumerate(files):
        walk(f)
        if (i + 1) % 1000 == 0:
            print('  ... %d/%d' % (i + 1, len(files)), flush=True)
    print('files: %d  ok=%d  bad=%s  legacy=%d' % (len(files), OK['n'], dict(BAD), LEGACY['n']))
    print()
    print('== message types (all files) ==')
    for t, n in sorted(MSG.items(), key=lambda kv: -kv[1]):
        print('  0x%02x  %8d   headLens=%s' % (
            t, n, sorted(HL['0x%02x' % t] if False else HL[t])[:6] if HL[t] else '-'))
    print()
    print('== note head = 0x01 ==')
    print('  headLen:', dict(HL[1]))
    print('  key   min/max: %d/%d  distinct=%d' % (min(KEY), max(KEY), len(KEY)))
    print('  vel   min/max: %d/%d  distinct=%d  top=%s' % (min(VEL), max(VEL), len(VEL), VEL.most_common(5)))
    print('  dur   top:', DUR.most_common(12))
    print()
    print('== MsgHdr fields ==')
    print('  dots   :', dict(sorted(DOTS.items())))
    print('  headType top:', HTYPE.most_common(14))
    print('  durIndex top:', DURIDX.most_common(16))
    print()
    print('== measure ==')
    print('  拍号分子:', dict(sorted(TSN.items(), key=lambda kv: -kv[1])[:12]))
    print('  拍号分母:', dict(sorted(TSD.items(), key=lambda kv: -kv[1])[:8]))
    print()
    print('== block (nStaves, f2, nPts) top ==')
    print(' ', BLK.most_common(12))


if __name__ == '__main__':
    main()
