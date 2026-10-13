import struct, sys
sys.path.insert(0, r'C:\research\samilpo\tools')
from smc_text import read_table

for name in ['889F.cod', 'B0a1.cod', 'Ks.cod', 'F040a.cod', 'F040.cod']:
    p = r'C:\Program Files (x86)\Samilpo 2.0\%s' % name
    b = open(p, 'rb').read()
    print('==', name, len(b))
    off = 0
    k = 0
    while off + 6 <= len(b) and k < 6:
        n, lo, hi = struct.unpack_from('<3H', b, off)
        print('  @0x%06x n=%d lo=0x%02x hi=0x%02x' % (off, n, lo, hi))
        if n > 64:
            print('   implausible n; raw:', b[off:off + 16].hex(' ')); break
        try:
            t, nxt = read_table(b, off)
        except struct.error as e:
            print('   read failed:', e); break
        print('   -> next 0x%06x (size %d) ranges=%s' % (nxt, nxt - off,
              [(hex(s), hex(e), len(d)) for s, e, d in zip(t.starts, t.ends, t.data)]))
        if nxt <= off:
            break
        off = nxt; k += 1
