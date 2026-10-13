"""Validate the 889F.cod decoder against real SMC text (read-only).

Uses the phase-1 walker to collect per-type message heads, then decodes
candidate text fields with each .cod forward table and reports which one
yields coherent Korean.
"""
import sys, os, io, contextlib, collections, struct
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
ROOT = os.path.join(D, '8000Songs')
tabs = {}
for name in ['889F.cod', 'B0a1.cod', 'Ks.cod', 'F040a.cod']:
    t, _, _ = parse_cod(os.path.join(D, name))
    if t:
        tabs[name] = t[0]

def ok_korean(s):
    """Fraction of non-space chars that are Hangul syllables."""
    cs = [c for c in s if not c.isspace()]
    if not cs:
        return 0.0
    return sum(1 for c in cs if 0xAC00 <= ord(c) <= 0xD7A3) / len(cs)

files = [os.path.join(dp, f) for dp, _, fs in os.walk(ROOT) for f in fs if f.endswith('.smc')]
print('files', len(files))
stats = collections.Counter()
ex = {}
for i, path in enumerate(files):
    w.heads.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)
    data = open(path, 'rb').read()
    n = struct.unpack_from('<h', data, 0x590)[0]
    title = data[0x0e:0x60].split(b'\0')[0]
    # titles
    scores = {k: ok_korean(decode(title, t, 0)) for k, t in tabs.items()}
    best = max(scores, key=scores.get)
    stats['title_best_' + best] += 1
    if scores['889F.cod'] > 0.9:
        stats['title_889F_good'] += 1
    # type 0x06 heads (text boxes): 24-byte meta + u16 len + text
    for hd, h in w.heads.get(0x06, []):
        if len(hd) >= 26:
            ln = struct.unpack_from('<H', hd, 22)[0]
            txt = hd[24:24 + ln]
            if txt:
                s = decode(txt, tabs['889F.cod'], 0)
                if ok_korean(s) > 0.8:
                    stats['head06_korean'] += 1
                    ex.setdefault('0x06', (os.path.basename(path), s))
                else:
                    stats['head06_other'] += 1
    # type 0x19 heads (suspected lyrics)
    for hd, h in w.heads.get(0x19, []):
        if len(hd) == 18:
            for off in (12, 14, 16):
                txt = hd[off:]
                if txt and len(txt) % 2 == 0:
                    s = decode(txt, tabs['889F.cod'], 0)
                    if ok_korean(s) > 0.8:
                        stats['head19_korean@%d' % off] += 1
                        ex.setdefault('0x19@%d' % off, (os.path.basename(path), s))
print(dict(stats))
for k, v in ex.items():
    print(k, v)
