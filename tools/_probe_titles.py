import struct, sys, os, glob
sys.path.insert(0, r'C:\research\samilpo\tools')
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
tabs = {}
for name in ['889F.cod', 'B0a1.cod', 'Ks.cod', 'F040a.cod', 'F040b.cod', 'F040c.cod']:
    t, _, _ = parse_cod(os.path.join(D, name))
    if t:
        tabs[name] = t[0]
print('tables:', list(tabs))

for f in ['150ALS-03DA-0012.smc', '212OPS-0012.smc', '150ALS-19AA-0529.smc', '150ALS-11TA-0037.smc']:
    p = glob.glob(os.path.join(D, '8000Songs', '**', f), recursive=True)
    if not p:
        print('not found', f); continue
    b = open(p[0], 'rb').read()
    raw = b[0x0e:0x60].split(b'\0')[0]
    print('\n%s  raw=%s' % (f, raw.hex(' ')))
    for name, t in tabs.items():
        print('   %-12s %r' % (name, decode(raw, t, 0)))
