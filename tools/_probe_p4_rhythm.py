"""Phase-4 probe B: rhythm data (0x47) and chord head (0x45 headLen 100).

B1) CRtmData layout hypothesis (from ReadFromMem 0x10047720 / WriteToMem 0x10047950):
       +00 u32 totalSize (derived)
       +04 u16 stride (0x10)
       +06 u16 field (obj+8)
       +08 u16 field (obj+0x48)
       +0A u32 eventCount
       +0E u16 eventSize (0x10)
       +10 events[eventCount][eventSize]
       then u16 count2; u16 size2 (6); count2 * 6 bytes
   Check whether totalSize == 0x10 + eventCount*eventSize + 4 + count2*6 (+/- 4).

B2) type 0x45 headLen 100: are individual byte positions stable across files
   (persisted field) or do they look like runtime pointers/residue?

Usage: python _probe_p4_rhythm.py <dir> [maxfiles]
"""
import struct, sys, os
from collections import Counter, defaultdict

B1_OK, B1_OFF = Counter(), Counter()
B1_STRIDE, B1_SIZE2 = Counter(), Counter()
EVSZ, CNT, CNT2 = Counter(), Counter(), Counter()

H100 = []                     # list of 100-byte heads
BYTE_STABLE = defaultdict(Counter)   # offset -> value
DWORD_LO = Counter()          # dwords that look like small ints
PTRLIKE = Counter()           # dwords that look like heap/stack pointers

N = Counter()

class Fail(Exception): pass

class R:
    def __init__(self, b): self.b, self.p = b, 0
    def take(self, n):
        if n < 0 or self.p + n > len(self.b): raise Fail()
        s = self.b[self.p:self.p+n]; self.p += n; return s


def rtmdata(r, where):
    start = r.p
    total = struct.unpack('<I', r.take(4))[0]
    stride = struct.unpack('<H', r.take(2))[0]
    r.take(2); r.take(2)
    cnt = struct.unpack('<I', r.take(4))[0]
    esz = struct.unpack('<H', r.take(2))[0]
    if cnt > 100000 or esz > 4096 or cnt * esz > 1 << 22:
        raise Fail('rtmdata size')
    r.take(cnt * esz)
    c2 = struct.unpack('<H', r.take(2))[0]
    s2 = struct.unpack('<H', r.take(2))[0]
    if c2 > 100000 or s2 > 4096 or c2 * s2 > 1 << 22:
        raise Fail('rtmdata2 size')
    r.take(c2 * s2)
    used = r.p - start
    N['rtm'] += 1
    B1_STRIDE[stride] += 1
    B1_SIZE2[s2] += 1
    EVSZ[esz] += 1
    CNT[min(cnt, 8)] += 1
    CNT2[min(c2, 8)] += 1
    B1_OK[total == used] += 1
    if total != used:
        B1_OFF[total - used] += 1
    return where


def core(r, t):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<H', h, 4)[0]
    head = r.take(headlen)
    if t == 0x45 and headlen == 100:
        N['h100'] += 1
        H100.append(head)
        for i in range(0, 100, 4):
            d = struct.unpack_from('<I', head, i)[0]
            if 0x00010000 <= d <= 0x7FFFFFFF:
                PTRLIKE[(i, hex(d)[:10])] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)
    return head


def msg(r):
    h = r.take(0x2c)
    t = h[0]
    N['msg 0x%02x' % t] += 1
    core(r, t)
    if t == 0x47:
        # 0x47 = CRhythm: Msg(already read as Msg type 0x47 with head) then 3 CStr + RtmData
        pass
    if t == 0x45: chord(r)


def cstr(r):
    n = struct.unpack('<h', r.take(2))[0]
    if n > 4096 or n < 0: raise Fail('cstr')
    return r.take(n)


def chord(r):
    cstr(r)
    n = r.take(1)[0]; r.take(n)
    msg(r)                     # CFretBoard (type 0x46) -> CSMMsg::Read + CFretInfo
    r.take(16)                 # CFretInfo 16 bytes
    hr = struct.unpack('<h', r.take(2))[0]
    if hr:
        # CRhythm::ReadFromMem: Msg + 3 CStr + CRtmData
        N['nested rhythm'] += 1
        msg(r)
        for _ in range(3):
            cstr(r)
        rtmdata(r, 'chord-rhythm')


def rhythm_full(r):
    """0x47 read: Msg + 3 CStr + RtmData."""
    msg(r)
    for _ in range(3):
        cstr(r)
    rtmdata(r, 'rhythm')


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
    root = sys.argv[1]
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort(); step = max(1, len(files)//maxn); files = files[::step][:maxn]
    for f in files:
        walk(f)
    print('counts:', {k: v for k, v in N.items() if '0x' not in str(k)})
    print()
    print('--- B1 CRtmData (nested in 0x45 only so far) ---')
    print('stride(0x10?):', dict(B1_STRIDE))
    print('eventSize    :', dict(EVSZ))
    print('second size  :', dict(B1_SIZE2))
    print('total == used:', dict(B1_OK), 'diff:', dict(B1_OFF.most_common(5)))
    print()
    print('--- B2 type 0x45 headLen 100 ---')
    print('samples:', len(H100))
    if H100:
        n = len(H100)
        stable = []
        for off in range(100):
            vals = Counter(h[off] for h in H100)
            top, cnt = vals.most_common(1)[0]
            if cnt == n:
                stable.append((off, hex(top)))
        print('byte positions constant across ALL samples: %d' % len(stable))
        print('  ', stable[:40])
        print('ptr-like dwords seen (offset, value):', len(PTRLIKE))
        for (i, v), c in PTRLIKE.most_common(6):
            print('    off=%d value=%s x%d' % (i, v, c))
        print('first sample head100:')
        h = H100[0]
        for i in range(0, 100, 10):
            print('    +%02d: %s' % (i, ' '.join('%02x' % b for b in h[i:i+10])))


if __name__ == '__main__':
    main()
