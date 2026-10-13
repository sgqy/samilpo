"""Precise CSMLyricMsg (0x19) payload layout probe -> UTF-8 report."""
import sys, os, io, contextlib, struct, collections, random
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
t, _, _, _ = parse_cod(os.path.join(D, '889F.cod')); T = t
out = io.StringIO()
def P(*a): print(*a, file=out)

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')]
random.seed(17)
u16 = collections.defaultdict(collections.Counter)
u8 = collections.defaultdict(collections.Counter)
lenc = collections.Counter()
rows = []
for path in random.sample(files, 120):
    w.heads.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)
    for msghdr, pl in w.heads.get(0x19, []):
        ln = pl[0x0C]
        if len(pl) != 0x10 + ln:
            lenc[(len(pl), 0x10 + ln)] += 1
        else:
            lenc['match'] += 1
        for off in range(0, 0x10, 2):
            u16[off][struct.unpack_from('<H', pl, off)[0]] += 1
        for off in range(0x0D, 0x10):
            u8[off][pl[off]] += 1
        if len(rows) < 40:
            rows.append((os.path.basename(path), pl.hex(' '), decode(pl[0x10:0x10 + ln], T)))

P('records sampled; len(head)==0x10+head[0x0c]:', dict(lenc))
P()
P('u16 at payload offset -> distinct / top values')
for off in range(0, 0x10, 2):
    c = u16[off]
    P('  +0x%02x distinct=%-5d top=%s' % (off, len(c), c.most_common(6)))
P()
P('bytes +0x0D..+0x0F (unused by DrawMsg):')
for off in range(0x0D, 0x10):
    P('  +0x%02x distinct=%d top=%s' % (off, len(u8[off]), u8[off].most_common(6)))
P()
P('samples:')
for f, h, txt in rows:
    P('  %-24s %s  %r' % (f, h, txt))
open(r'C:\research\samilpo\raw\lyric_layout.txt', 'w', encoding='utf-8').write(out.getvalue())
print('ok')
