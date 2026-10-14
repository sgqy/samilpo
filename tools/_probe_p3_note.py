"""Phase-3 probe 4: correlate note head[2]/head[3] with MsgHdr fields.

Questions:
  Q1  head[2] distribution and relation to MsgHdr +05/+06/+0A
  Q2  head[3] vs this[0x76] (mark/stem state) and flags (+0x6E)
  Q3  head[2:4] as u16 LE
  Q4  head[10:12] (start time) vs head[8:10]
Usage: python _probe_p3_note.py <dir> [maxfiles]
"""
import struct, sys, os
from collections import Counter, defaultdict

H2 = Counter()
H3 = Counter()
H2_H3 = Counter()
H3_MARK = Counter()
H3_FLAGS = Counter()
H23_U16 = Counter()
H2_SAME_AS = Counter()
TAIL = Counter()
HEAD16 = Counter()

class Fail(Exception): pass

class R:
    def __init__(self, b): self.b, self.p = b, 0
    def take(self, n):
        if n < 0 or self.p + n > len(self.b): raise Fail()
        s = self.b[self.p:self.p+n]; self.p += n; return s

def core(r, t):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<H', h, 4)[0]
    head = r.take(headlen)
    if t == 1 and len(head) == 12:
        H2[head[2]] += 1
        H3[head[3]] += 1
        H2_H3[(head[2], head[3])] += 1
        H3_MARK[(head[3], h[5] >> 4)] += 1
        H3_FLAGS[(head[3], struct.unpack_from('<H', h, 0x0a)[0] & 0x0010)] += 1
        H23_U16[struct.unpack_from('<H', head, 2)[0]] += 1
        H2_SAME_AS[(head[2] == struct.unpack_from('<H', h, 2)[0] & 0xff)] += 1
        TAIL[(head[8:10].hex(), head[10:12].hex())] += 1
        HEAD16[head.hex()] += 1
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
    if struct.unpack_from('<I', d, 0)[0] != 0x58C: return False
    p = 4 + 0x58C
    sl = struct.unpack_from('<h', d, p)[0]; p += 2
    if sl > 1: p += sl
    smc = d[p:p+0x318]
    if smc[:4] != b'SMC\0': return False
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
        return r.p == blen
    except Fail:
        return False

def main():
    root = sys.argv[1]; maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort(); step = max(1, len(files)//maxn); files = files[::step][:maxn]
    ok = sum(walk(f) for f in files)
    print('files ok: %d/%d' % (ok, len(files)))
    print('head[2]      :', H2.most_common(8))
    print('head[3]      :', H3.most_common(8))
    print('(head2,head3):', H2_H3.most_common(8))
    print('(head3, mark):', sorted(H3_MARK.items())[:12])
    print('(head3, flag10):', sorted(H3_FLAGS.items()))
    print('head[2:4] u16:', H23_U16.most_common(8))
    print('head[2]==hdr+2 low byte:', dict(H2_SAME_AS))
    print('head[8:12] pairs:', TAIL.most_common(6))
    print('distinct full 12-byte heads:', len(HEAD16))

if __name__ == '__main__':
    main()
