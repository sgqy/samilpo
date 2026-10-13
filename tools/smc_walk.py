"""Phase-1 SMC structural walker (read-only).

Implements ONLY the layout recovered from static analysis of MusicBook.exe
FUN_00424670 and engine.dll CSMDoc::Load and its sub-readers. Field semantics
are mostly unknown; this script validates that the recovered framing consumes
the sample file exactly. See smc-format.md.

Usage: python smc_walk.py <file.smc> [-v]
"""
import struct, sys
from collections import Counter

class Fail(Exception):
    pass

class R:
    def __init__(self, b, base):
        self.b, self.p, self.base = b, 0, base
    def take(self, n):
        if self.p + n > len(self.b):
            raise Fail('overrun at body+0x%x need %d' % (self.p, n))
        s = self.b[self.p:self.p + n]; self.p += n; return s

V = False
stats = Counter()
msg_types = Counter()
heads = {}   # msg type -> [(0x2c header, head payload)]

def log(depth, s):
    if V:
        print('  ' * depth + s)

def read_object_core(r, depth, kind, embedded_only):
    h = r.take(12)
    nchild, f2, headlen, f8 = h[0], struct.unpack_from('<H', h, 2)[0], struct.unpack_from('<h', h, 4)[0], struct.unpack_from('<I', h, 8)[0]
    head = r.take(max(headlen, 0))
    log(depth, '%s obj nchild=%d f2=0x%x headlen=%d f8=0x%x' % (kind, nchild, f2, headlen, f8))
    for i in range(nchild):
        c = r.take(8)
        key, emb = struct.unpack_from('<I', c, 0)[0], c[4]
        if emb:
            read_msg(r, depth + 1)
        else:
            stats['child_ref'] += 1
    return head

def read_msg(r, depth):
    start = r.p
    h = r.take(0x2c)
    t = h[0]
    msg_types[t] += 1
    stats['msg'] += 1
    log(depth, 'MSG @body+0x%x type=0x%02x key=0x%x' % (start, t, struct.unpack_from('<I', h, 0x24)[0]))
    read_msg_head = read_object_core(r, depth, 'msg', False)
    heads.setdefault(t, []).append((h, read_msg_head))
    log(depth + 1, 'hdr=%s head=%s' % (h.hex(' '), read_msg_head.hex(' ')))
    if t == 0x45:
        read_chord_extra(r, depth + 1, start)

def read_cstring(r):
    n = struct.unpack('<h', r.take(2))[0]
    return r.take(n)

def read_chord_extra(r, depth, start):
    # CChordSymbol::ReadFromMem (0x1000bdb0)
    stats['chord'] += 1
    name = read_cstring(r)                      # CChordSurfix::ReadFromMem 0x10008b40
    n = r.take(1)[0]; info = r.take(n)
    log(depth, 'CHORD surfix=%r info=%s' % (name, info.hex()))
    read_msg(r, depth)                          # assumed CFretBoard::ReadFromMem 0x1002cfd0
    r.take(16)                                  # CFretInfo::ReadFromMem 0x1002dc70
    has_rtm = struct.unpack('<h', r.take(2))[0]
    if has_rtm:
        # CRhythm::ReadFromMem 0x10045c40: Msg + 3 CStrings + CRtmData (0x10047720)
        stats['rhythm'] += 1
        read_msg(r, depth)
        s = [read_cstring(r) for _ in range(3)]
        log(depth, 'RHYTHM strings=%r' % s)
        r.take(4 + 2 + 2 + 2)
        nev = struct.unpack('<i', r.take(4))[0]; esz = struct.unpack('<h', r.take(2))[0]
        r.take(nev * esz)
        n2 = struct.unpack('<h', r.take(2))[0]; sz2 = struct.unpack('<h', r.take(2))[0]
        r.take(n2 * sz2)

def read_meas(r, depth):
    stats['meas'] += 1
    read_object_core(r, depth, 'meas', True)
    r.take(0x60)

def read_staff(r, depth):
    stats['staff'] += 1
    read_object_core(r, depth, 'staff', False)
    t = r.take(0x70)
    name = t[:0x20].split(b'\0')[0]
    nmeas = struct.unpack_from('<i', t, 0x6c)[0]
    log(depth, 'STAFF name=%r nmeas=%d' % (name, nmeas))
    for _ in range(nmeas):
        read_meas(r, depth + 1)

def read_system(r):
    read_object_core(r, 0, 'system', False)
    n1, n2, x = struct.unpack('<hhI', r.take(8))
    log(0, 'SYSTEM staves=%d staves2=%d u32=0x%x' % (n1, n2, x))
    for _ in range(n1):
        read_staff(r, 1)
    for _ in range(n2):
        read_staff(r, 1)

def read_block(r, depth):
    stats['block'] += 1
    h = r.take(0x1c)
    btype, nst, n2, n4, npt = h[0], h[1], struct.unpack_from('<h', h, 2)[0], struct.unpack_from('<h', h, 4)[0], h[8]
    log(depth, 'BLOCK type=%d nstaves=%d f2=%d f4=%d npts=%d rect=%s' % (btype, nst, n2, n4, npt, struct.unpack_from('<4i', h, 0xc)))
    r.take(5 * nst)
    r.take(2 * (n2 + 1))
    r.take(8 * npt)

def read_page(r, depth):
    stats['page'] += 1
    h = r.take(0x18)
    a, b, m = struct.unpack_from('<hhh', h, 0)
    log(depth, 'PAGE blocksA=%d blocksB=%d msgs=%d rect=%s' % (a, b, m, struct.unpack_from('<4i', h, 8)))
    for _ in range(a): read_block(r, depth + 1)
    for _ in range(b): read_block(r, depth + 1)
    for _ in range(m): read_msg(r, depth + 1)

def main(path):
    d = open(path, 'rb').read()
    p = 0
    hlen = struct.unpack_from('<I', d, 0)[0]
    print('header_len=0x%x' % hlen)
    if hlen == 0x58C:
        print('magic=%r version=0x%04x' % (d[8:12], struct.unpack_from('<h', d, 0x0C)[0]))
        p = 4 + 0x58C
        sl = struct.unpack_from('<h', d, p)[0]; p += 2
        if sl > 1:
            print('str@0x%x=%r' % (p, d[p:p + sl])); p += sl
    else:
        print('legacy header path (FUN_00425090) not modelled'); return
    smc = d[p:p + 0x318]
    assert smc[:4] == b'SMC\0', smc[:4]
    fontlen = struct.unpack_from('<I', smc, 0x314)[0]
    print('SMC block @0x%x font_buf_len=%d' % (p, fontlen)); p += 0x318
    p += fontlen
    ctl = struct.unpack_from('<h', d, p)[0]
    print('CtrlTool @0x%x len=0x%x' % (p, ctl)); p += 2 + ctl
    print('FileInfo @0x%x %s' % (p, struct.unpack_from('<12h2I', d, p))); p += 0x20
    blen = struct.unpack_from('<I', d, p)[0]; p += 4
    print('Body @0x%x len=0x%x end=0x%x filesize=0x%x' % (p, blen, p + blen, len(d)))
    r = R(d[p:p + blen], p)
    try:
        read_system(r)
        hdr = struct.unpack('<5h', r.take(10))
        print('doc fields after system: pages=%d others=%s' % (hdr[0], hdr[1:]))
        for _ in range(3): read_msg(r, 0)
        for _ in range(hdr[0]): read_page(r, 0)
        print('consumed body 0x%x / 0x%x' % (r.p, blen))
    except Fail as e:
        print('FAIL:', e, 'consumed 0x%x' % r.p)
    print('stats', dict(stats))
    print('msg types', {hex(k): v for k, v in sorted(msg_types.items())})
    tail = d[p + blen:]
    print('trailer after body (%d bytes): %s' % (len(tail), tail[:32].hex(' ')))

if __name__ == '__main__':
    V = '-v' in sys.argv
    main(sys.argv[1])
