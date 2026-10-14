"""Phase-4 probe A1: lyric head (0x19) trailing bytes.

DrawMsg 0x1009ad00 assembly (evidence):
    PUSH 0x10 / LEA ECX,[EBP-0x20] / CALL memcpy   -> head copied to EBP-0x20
    MOVSX ECX,word[EBP-0x20] -> GetFontName        -> head+0x00 u16 font index
    MOV EAX,[EBP-0x1e]; AND EAX,1/2/4              -> head+0x02 u8 style (bold/italic/underline)
    MOVSX ECX,word[EBP-0x1c]; default 0xd          -> head+0x04 u16 size
    (EBP-0x1a never read)                          -> head+0x06 u16 unused
    MOV EAX,[EBP-0x18]                             -> head+0x08 u32 color
    MOV EAX,[EBP-0x14]; AND EAX,0xff               -> head+0x0C..+0x0F dword, LOW byte = text length
    (EBP-0x13/-0x12/-0x11 never read)              -> head+0x0D..+0x0F high bytes of that dword, unused

Writer EncToSMC_Lyric 0x10025170:
    local_cc=font, local_ca=0(style), local_c8=size, local_c4=0,
    local_c0=CONCAT31(prev,(char)strlen)           -> only low byte of the length dword is set

This probe tests the resulting prediction: head+0x0D/+0x0E/+0x0F are residual bytes
(not independent fields), and head+0x06 is not a stable field.
"""
import struct, sys, os
from collections import Counter

HL = Counter()
TAIL = Counter()          # (b0D,b0E,b0F)
TAIL_ZERO = Counter()     # how often all three are 0
B06 = Counter()
STYLE = Counter()
SIZE = Counter()
FONT = Counter()
CORR = Counter()          # does tail correlate with text length?
LEN = Counter()
N = 0

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_text as T
FWD = T.parse_cod(r'C:\Program Files (x86)\Samilpo 2.0\889F.cod')[0]


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
    if t == 0x19 and headlen >= 0x11:
        global N
        N += 1
        HL[headlen] += 1
        FONT[struct.unpack_from('<H', head, 0)[0]] += 1
        STYLE[head[2]] += 1
        SIZE[struct.unpack_from('<H', head, 4)[0]] += 1
        B06[struct.unpack_from('<H', head, 6)[0]] += 1
        ln = head[0x0C]
        LEN[ln] += 1
        TAIL[(head[0x0D], head[0x0E], head[0x0F])] += 1
        TAIL_ZERO[head[0x0D] or head[0x0E] or head[0x0F]] += 1
        CORR[bool(head[0x0D] or head[0x0E] or head[0x0F]) and headlen == ln + 0x10] += 1
    for _ in range(nchild):
        c = r.take(8)
        if c[4]: msg(r)


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
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    files = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith('.smc'): files.append(os.path.join(dp, f))
    files.sort(); step = max(1, len(files)//maxn); files = files[::step][:maxn]
    for f in files:
        walk(f)
    print('lyric records    :', N)
    print('headLen distinct :', sorted(HL)[:8], '...' if len(HL) > 8 else '')
    print('font index       :', FONT.most_common(8))
    print('head+0x02 style  :', STYLE.most_common(8))
    print('head+0x04 size   :', SIZE.most_common(8))
    print('head+0x06 value  :', B06.most_common(8), 'distinct', len(B06))
    print('text len (b0C)   :', LEN.most_common(6))
    print('tail (b0D,b0E,b0F) top:', TAIL.most_common(8), 'distinct', len(TAIL))
    print('tail all-zero?   :', dict(TAIL_ZERO))
    print('tail nonzero & headLen==len+0x10 :', dict(CORR))


if __name__ == '__main__':
    main()
