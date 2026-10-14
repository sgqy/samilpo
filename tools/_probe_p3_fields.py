"""Phase-3 probe: verify newly recovered SMC fields against real samples.

Checks (each is a falsifiable claim from project/phase3-log.md):
  C1  ObjectCore disk +0x06 == headLen + 12   (CSMObject::Write 0x1007a740)
  C2  ObjectCore disk +0x01 == 0
  C3  type 0x01 head[0] (MIDI key) in 0..127
  C4  type 0x01 head[1] (velocity) in 0..127
  C5  type 0x01 head[4:8] u32 duration, non-zero, monotone values
  C6  Child descriptor byte[4] value distribution (role byte, != 0 => embedded)
  C7  MsgHdr +0x05 low nibble (dot count) distribution
  C8  MsgHdr +0x06 (note head type) distribution
  C9  MsgHdr +0x0A flags: bit2 / bit4 / bit9 / bit10 counts
  C10 Meas tail +0x56 / +0x58 (numerator/denominator) distribution
  C11 Block header: nStaves*5 + 2 + f2*2 + nPts*8 consumed exactly
Usage: python _probe_p3_fields.py <dir> [maxfiles]
"""
import struct, sys, os
from collections import Counter

MSG, OBJ, STAFF, MEAS, BLOCK, PAGE = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
ODD6, ODD1, ODD6_HL12 = Counter(), Counter(), Counter()
KEYRANGE, VELRANGE = Counter(), Counter()
DUR, DUR_BYTES, START = Counter(), Counter(), Counter()
CHILDROLE = Counter()
DOTS, HEADTYPE, DURIDX, FLAGS = Counter(), Counter(), Counter(), Counter()
TSNUM, TSDEN = Counter(), Counter()
MEAS_HEADLEN = Counter()
BLK_OK, BLK_BAD, BLK_N = Counter(), Counter(), Counter()


class Fail(Exception):
    pass


class R:
    def __init__(self, b):
        self.b, self.p = b, 0

    def take(self, n):
        if n < 0 or self.p + n > len(self.b):
            raise Fail('overrun at +0x%x need %d' % (self.p, n))
        s = self.b[self.p:self.p + n]
        self.p += n
        return s

    def u8(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack('<H', self.take(2))[0]

    def s16(self):
        return struct.unpack('<h', self.take(2))[0]

    def u32(self):
        return struct.unpack('<I', self.take(4))[0]


def read_object_core(r, ctx):
    h = r.take(12)
    nchild, b1, f2, headlen, f6, f8 = h[0], h[1], struct.unpack_from('<H', h, 2)[0], \
        struct.unpack_from('<H', h, 4)[0], struct.unpack_from('<H', h, 6)[0], \
        struct.unpack_from('<I', h, 8)[0]
    if ctx == 'msg':
        ODD1[b1] += 1
        ODD6[f6 - headlen] += 1
    head = r.take(headlen)
    for _ in range(nchild):
        c = r.take(8)
        CHILDROLE[c[4]] += 1
        if c[4]:
            read_msg(r)
    return head, headlen


def read_msg(r):
    start = r.p
    h = r.take(0x2c)
    t = h[0]
    MSG[t] += 1
    head, headlen = read_object_core(r, 'msg')
    if t == 0x01 and len(head) >= 12:
        KEYRANGE[head[0] > 127] += 1
        VELRANGE[head[1] > 127] += 1
        DUR[head[4:8].hex()] += 1
        START[head[8:12].hex()] += 1
    DOTS[h[5] & 0x0f] += 1
    HEADTYPE[struct.unpack_from('<H', h, 6)[0]] += 1
    DURIDX[struct.unpack_from('<H', h, 8)[0]] += 1
    fl = struct.unpack_from('<H', h, 0x0a)[0]
    for bit in (2, 3, 4, 8, 9, 10):
        if fl & (1 << bit):
            FLAGS[bit] += 1
    if t == 0x45:
        read_chord_extra(r)


def read_cstring(r):
    n = struct.unpack('<h', r.take(2))[0]
    return r.take(n)


def read_chord_extra(r):
    read_cstring(r)
    n = r.take(1)[0]
    r.take(n)
    read_msg(r)
    r.take(16)
    if struct.unpack('<h', r.take(2))[0]:
        read_msg(r)
        for _ in range(3):
            read_cstring(r)
        r.take(4 + 2 + 2 + 2)
        nev = struct.unpack('<i', r.take(4))[0]
        esz = struct.unpack('<h', r.take(2))[0]
        r.take(nev * esz)
        n2 = struct.unpack('<h', r.take(2))[0]
        sz2 = struct.unpack('<h', r.take(2))[0]
        r.take(n2 * sz2)


def read_meas(r):
    h = r.take(12)
    nchild = h[0]
    MEAS_HEADLEN[h[4]] += 1
    headlen = struct.unpack_from('<H', h, 4)[0]
    r.take(headlen)
    for _ in range(nchild):
        c = r.take(8)
        CHILDROLE[c[4]] += 1
        if c[4]:
            read_msg(r)
    tail = r.take(0x60)
    TSNUM[struct.unpack_from('<h', tail, 0x56)[0]] += 1
    TSDEN[struct.unpack_from('<h', tail, 0x58)[0]] += 1


def read_staff(r):
    read_object_core(r, 'staff')
    t = r.take(0x70)
    nmeas = struct.unpack_from('<i', t, 0x6c)[0]
    for _ in range(nmeas):
        read_meas(r)


def read_block(r):
    h = r.take(0x1c)
    nst, f2, npts = h[1], struct.unpack_from('<h', h, 2)[0], h[8]
    r.take(5 * nst)
    r.take(2 * (f2 + 1))
    r.take(8 * npts)
    BLK_N[(nst, f2, npts)] += 1


def read_page(r):
    h = r.take(0x18)
    a, b, m = struct.unpack_from('<hhh', h, 0)
    for _ in range(a + b):
        read_block(r)
    for _ in range(m):
        read_msg(r)


def walk(path):
    d = open(path, 'rb').read()
    if struct.unpack_from('<I', d, 0)[0] != 0x58C:
        return 'legacy'
    p = 4 + 0x58C
    sl = struct.unpack_from('<h', d, p)[0]
    p += 2
    if sl > 1:
        p += sl
    smc = d[p:p + 0x318]
    if smc[:4] != b'SMC\0':
        return 'nosmc'
    fontlen = struct.unpack_from('<I', smc, 0x314)[0]
    p += 0x318 + fontlen
    ctl = struct.unpack_from('<h', d, p)[0]
    p += 2 + ctl
    p += 0x20
    blen = struct.unpack_from('<I', d, p)[0]
    p += 4
    r = R(d[p:p + blen])
    try:
        read_object_core(r, 'system')
        n1, n2, x = struct.unpack('<hhI', r.take(8))
        for _ in range(n1 + n2):
            read_staff(r)
        hdr = struct.unpack('<5h', r.take(10))
        for _ in range(3):
            read_msg(r)
        for _ in range(hdr[0]):
            read_page(r)
        return 'ok' if r.p == blen else 'partial(0x%x/0x%x)' % (r.p, blen)
    except Fail as e:
        return 'FAIL %s' % e


def main():
    root = sys.argv[1]
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'):
                files.append(os.path.join(dp, f))
    files.sort()
    step = max(1, len(files) // maxn)
    files = files[::step][:maxn]
    res = Counter()
    for f in files:
        res[walk(f)] += 1
    print('files        :', len(files), dict(res))
    print('C1 +06-headLen:', dict(ODD6))
    print('C2 +01 value :', dict(ODD1))
    print('C3 key>127   :', dict(KEYRANGE))
    print('C4 vel>127   :', dict(VELRANGE))
    print('C5 duration distinct:', len(DUR), 'top:', DUR.most_common(12))
    print('   start distinct   :', len(START), 'top:', START.most_common(6))
    print('C6 child byte4:', dict(sorted(CHILDROLE.items())[:12]))
    print('C7 dots      :', dict(sorted(DOTS.items())))
    print('C8 headtype  :', dict(sorted(HEADTYPE.items(), key=lambda kv: -kv[1])[:16]))
    print('C9 dur index :', dict(sorted(DURIDX.items(), key=lambda kv: -kv[1])[:20]))
    print('C9 flags bits:', dict(sorted(FLAGS.items())))
    print('C10 拍号分子 :', dict(sorted(TSNUM.items(), key=lambda kv: -kv[1])[:10]))
    print('C10 拍号分母 :', dict(sorted(TSDEN.items(), key=lambda kv: -kv[1])[:10]))
    print('C11 block (nst,f2,npts):', dict(BLK_N.most_common(10)))
    print('msg types    :', {hex(k): v for k, v in sorted(MSG.items())})
    print('meas headLen :', dict(sorted(MEAS_HEADLEN.items(), key=lambda kv: -kv[1])[:8]))


if __name__ == '__main__':
    main()
