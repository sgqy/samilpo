import struct, sys, os
sys.path.insert(0, r'C:\research\samilpo\tools')
from smc_text import parse_cod, read_table, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
files = ['889F.cod', 'B0a1.cod', 'Ks.cod', 'F040.cod', 'F040a.cod', 'F040b.cod', 'F040c.cod', 'KorCode.cod']
for name in files:
    p = os.path.join(D, name)
    b = open(p, 'rb').read()
    print('== %-14s %d bytes' % (name, len(b)))
    n, lo, hi = struct.unpack_from('<3H', b, 0)
    print('   header: n=%d lo=0x%02x hi=0x%02x' % (n, lo, hi))
    if n <= 32:
        t, nx = read_table(b, 0)
        print('   fwd->0x%x ranges=%s' % (nx, [(hex(s), hex(e), len(d)) for s, e, d in zip(t.starts, t.ends, t.data)]))
    # search for another plausible table header (n in 1..8, lo<hi) after the first
    cands = []
    for off in range(0, len(b) - 6, 2):
        n2, l2, h2 = struct.unpack_from('<3H', b, off)
        if 1 <= n2 <= 8 and 0x20 <= l2 <= 0xff and l2 < h2 <= 0xffff and h2 - l2 < 0x100:
            cands.append(off)
    print('   plausible table headers at', [hex(c) for c in cands[:8]])

print()
print('--- decode test: sample title bytes from MusicBook 8000Songs ---')
sample = bytes.fromhex('8a7d96a72089cf8bb5')
sd = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
import glob
for name in files:
    p = os.path.join(D, name)
    tables, used, size = parse_cod(p)
    if not tables:
        print('%-14s (no forward table parsed)' % name); continue
    t = tables[0]
    print('%-14s %r' % (name, decode(sample, t, 0)))
