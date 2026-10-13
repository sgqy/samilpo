"""Empirically validate the CSMLyricMsg (0x19) head layout across many records."""
import sys, os, io, contextlib, struct, collections, random
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
t, _, _ = parse_cod(os.path.join(D, '889F.cod')); T = t[0]

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')]
random.seed(3)
sample = random.sample(files, 150)

stat = collections.Counter()
vals = collections.defaultdict(collections.Counter)
korean_ok = 0
korean_bad = 0
examples = []
for path in sample:
    w.heads.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)
    for hd, h in w.heads.get(0x19, []):
        hl = len(h)
        if hl < 0x10:
            stat['too_short'] += 1
            continue
        stat['n'] += 1
        # hypothesis: text length byte at +0x0C, text at +0x10
        ln = h[0x0C]
        vals['len_matches_0c'][1 if hl - 0x10 == ln else 0] += 1
        vals['font'][struct.unpack_from('<H', h, 0)[0]] += 1
        vals['flags'][h[2]] += 1
        vals['byte3'][h[3]] += 1
        vals['height'][struct.unpack_from('<H', h, 4)[0]] += 1
        vals['resv_0a'][struct.unpack_from('<H', h, 0x0A)[0]] += 1
        vals['lenword_hi'][struct.unpack_from('<H', h, 0x0E)[0]] += 1
        txt = h[0x10:0x10 + ln]
        s = decode(txt, T, 0)
        kr = sum(1 for c in s if 0xAC00 <= ord(c) <= 0xD7A3)
        if txt and kr * 2 >= len([c for c in s if not c.isspace()]) * 1:
            korean_ok += 1
        else:
            korean_bad += 1
            if len(examples) < 8:
                examples.append((os.path.basename(path), h.hex(' '), repr(s)))

print('records', stat)
print('len==headLen-0x10 at +0x0C:', dict(vals['len_matches_0c']))
for k in ['font', 'flags', 'byte3', 'height', 'resv_0a', 'lenword_hi']:
    top = vals[k].most_common(6)
    print('%-10s top: %s   distinct=%d' % (k, top, len(vals[k])))
print('korean ok/bad:', korean_ok, korean_bad)
for e in examples:
    print('BAD', e)
