"""Scan message heads of every type for Korean-decodable text (read-only)."""
import sys, os, io, contextlib, collections, struct
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
ROOT = os.path.join(D, '8000Songs')
t889, _, _ = parse_cod(os.path.join(D, '889F.cod'))
T = t889[0]

def kr(s):
    cs = [c for c in s if not c.isspace()]
    return sum(1 for c in cs if 0xAC00 <= ord(c) <= 0xD7A3) / len(cs) if cs else 0.0

import random
files = [os.path.join(dp, f) for dp, _, fs in os.walk(ROOT) for f in fs if f.endswith('.smc')]
random.seed(7); sample = random.sample(files, 300)
agg = collections.defaultdict(lambda: collections.Counter())
examples = {}
for path in sample:
    w.heads.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)
    for t, hs in w.heads.items():
        for hd, h in hs:
            if len(h) < 4:
                continue
            best = 0.0; bests = ''
            for start in range(0, min(len(h), 8)):
                if (len(h) - start) < 4:
                    continue
                s = decode(h[start:], T, 0)
                v = kr(s)
                if v > best:
                    best, bests = v, s
            if best > 0.8:
                agg[t]['korean'] += 1
                examples.setdefault(t, h.hex(' ') + ' -> ' + bests)
            else:
                agg[t]['other'] += 1
for t in sorted(agg):
    print('type 0x%02x  %s   ex: %s' % (t, dict(agg[t]), examples.get(t, '')))
