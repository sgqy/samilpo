import struct, sys, os, glob, io
sys.path.insert(0, r'C:\research\samilpo\tools')
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
out = io.StringIO()
def P(*a):
    print(*a, file=out)

tables = {}
for name in ['889F.cod', 'B0a1.cod', 'Ks.cod', 'F040a.cod']:
    t, _, _ = parse_cod(os.path.join(D, name))
    tables[name] = t[0]

for f in ['150ALS-03DA-0012.smc', '212OPS-0012.smc']:
    p = glob.glob(os.path.join(D, '8000Songs', '**', f), recursive=True)
    b = open(p[0], 'rb').read()
    raw = b[0x0e:0x60].split(b'\0')[0]
    P('== %s' % f)
    P('   raw %s' % raw.hex(' '))
    i = 0
    pairs = []
    while i < len(raw):
        c = raw[i]
        if c < 0x80:
            pairs.append('%02x -> ASCII %r' % (c, chr(c))); i += 1
        else:
            code = (c << 8) | (raw[i + 1] if i + 1 < len(raw) else 0)
            vals = {n: t.lookup(code) for n, t in tables.items()}
            pairs.append('%04x -> ' % code + ' '.join('%s:%04x%s' % (n.split('.')[0][:4], v, chr(v) if 32 <= v < 0xD800 or 0xE000 <= v else '')
                                                       for n, v in vals.items()))
            i += 2
    for s in pairs:
        P('   ', s)
    for n, t in tables.items():
        P('   %-9s decode=%r' % (n, decode(raw, t, 0)))

open(r'C:\research\samilpo\raw\title_probe.txt', 'w', encoding='utf-8').write(out.getvalue())
print('written')
