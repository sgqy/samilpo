"""Phase-3 probe 3: per-field structure of the 12-byte note head, Meas head,
staff-name (0x49) head, text (0x06) head prefix, dynamic (0x1b) head.

Usage: python _probe_p3_heads2.py <dir> [maxfiles]
"""
import struct, sys, os
from collections import Counter, defaultdict

N2, N3, N8 = Counter(), Counter(), Counter()
NOTE_FULL = Counter()
MEAS_H8 = Counter()
MEAS_SEQ = []
S49 = Counter()
S06 = Counter()
S1B = Counter()
S08 = Counter()
S09, S0A, S12, S14 = Counter(), Counter(), Counter(), Counter()
S1B_HL = Counter()
MEAS_CORE = Counter()

class Fail(Exception):
    pass

class R:
    def __init__(self, b):
        self.b, self.p = b, 0
    def take(self, n):
        if n < 0 or self.p + n > len(self.b):
            raise Fail('overrun')
        s = self.b[self.p:self.p + n]; self.p += n; return s
    def s16(self): return struct.unpack('<h', self.take(2))[0]
    def u16(self): return struct.unpack('<H', self.take(2))[0]
    def u32(self): return struct.unpack('<I', self.take(4))[0]


def core(r, kind, want_head=False):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<H', h, 4)[0]
    head = r.take(headlen)
    if want_head:
        if kind == '0x01' and len(head) == 12:
            NOTE_FULL[head.hex()] += 1
            N2[head[2]] += 1
            N3[head[3]] += 1
            N8[head[8:12].hex()] += 1
        elif kind == '0x49':
            S49[head.hex()] += 1
        elif kind == '0x06':
            S06[head[:12].hex()] += 1
        elif kind == '0x1b':
            S1B[head.hex()] += 1
            S1B_HL[headlen] += 1
        elif kind == '0x08':
            S08[head.hex()] += 1
        elif kind == '0x09':
            S09[head.hex()] += 1
        elif kind == '0x0a':
            S0A[head.hex()] += 1
        elif kind == '0x12':
            S12[head.hex()] += 1
        elif kind == '0x14':
            S14[head.hex()] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]:
            msg(r)
    return head


def msg(r):
    h = r.take(0x2c)
    t = '0x%02x' % h[0]
    core(r, t, True)
    if h[0] == 0x45:
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
        r.take(10)
        nev = struct.unpack('<i', r.take(4))[0]; esz = struct.unpack('<h', r.take(2))[0]
        r.take(nev * esz)
        n2 = struct.unpack('<h', r.take(2))[0]; sz2 = struct.unpack('<h', r.take(2))[0]
        r.take(n2 * sz2)


def meas(r, seq):
    h = r.take(12)
    nchild = h[0]
    headlen = struct.unpack_from('<H', h, 4)[0]
    MEAS_CORE[(headlen, struct.unpack_from('<H', h, 2)[0], struct.unpack_from('<I', h, 8)[0])] += 1
    head = r.take(headlen)
    if headlen == 8:
        MEAS_H8[head.hex()] += 1
        seq.append(struct.unpack_from('<H', head, 0)[0])
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    r.take(0x60)


def staff(r):
    core(r, 'staff')
    t = r.take(0x70)
    seq = []
    for _ in range(struct.unpack_from('<i', t, 0x6c)[0]):
        meas(r, seq)
    MEAS_SEQ.append(seq)


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
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort()
    step = max(1, len(files) // maxn)
    files = files[::step][:maxn]
    ok = sum(walk(f) for f in files)
    print('files ok: %d/%d' % (ok, len(files)))
    print()
    print('note head[2] :', N2.most_common(8))
    print('note head[3] :', N3.most_common(8))
    print('note head[8:12]:', N8.most_common(6))
    print('note full head (top5):')
    for h, n in NOTE_FULL.most_common(5):
        print('   %s  x%d' % (' '.join(h[i:i+2] for i in range(0, 24, 2)), n))
    print('note distinct full heads:', len(NOTE_FULL))
    print()
    print('Meas core (headLen, f2, f8) top:', MEAS_CORE.most_common(6))
    print('Meas head (len8) top:')
    for h, n in MEAS_H8.most_common(6):
        print('   %s  x%d' % (' '.join(h[i:i+2] for i in range(0, 16, 2)), n))
    print('Meas head[0:2] sequence per staff (first 4 staffs):')
    for s in MEAS_SEQ[:4]:
        print('  ', s[:24])
    print()
    print('0x49 staff-name head top:', S49.most_common(6), 'distinct', len(S49))
    print('0x06 head first12 top:', S06.most_common(6), 'distinct', len(S06))
    print('0x1b head top:', S1B.most_common(6), 'headLen', dict(S1B_HL))
    print('0x08 head top:', S08.most_common(4))
    print('0x09 head top:', S09.most_common(3))
    print('0x0a head top:', S0A.most_common(3))
    print('0x12 head top:', S12.most_common(3))
    print('0x14 head top:', S14.most_common(3))


if __name__ == '__main__':
    main()
