import io
import re

p = r'C:\research\samilpo\work\out_batch_all.txt'
raw = open(p, 'rb').read()
for enc in ('utf-16', 'utf-8', 'cp949'):
    try:
        t = raw.decode(enc)
        print('decoded as', enc)
        break
    except Exception:
        continue

lines = t.splitlines()
print('total lines:', len(lines))
print()
print('--- header ---')
for ln in lines[:6]:
    print(ln)
print()
print('--- smc2ir.ValueError detail lines ---')
n = 0
for ln in lines:
    if 'smc2ir' in ln and ('Error' in ln or 'error' in ln):
        print('   ', ln.strip()[:220])
        n += 1
        if n >= 12:
            break
print()
print('--- distinct error kinds ---')
kinds = {}
for ln in lines:
    m = re.search(r'\[(smc2ir|verify|ir2musicxml|verify_musicxml)\]\s*(.*)', ln)
    if m:
        msg = m.group(2)
        key = (m.group(1), re.sub(r'\d+', 'N', msg)[:60])
        kinds[key] = kinds.get(key, 0) + 1
for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])[:14]:
    print('   %-14s %-62s %d' % (k[0], k[1], v))
