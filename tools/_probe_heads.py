"""Dump 0x06 and 0x19 heads with 889F decoding, to a UTF-8 file (read-only)."""
import sys, os, io, contextlib, struct, collections
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
t889, _, _ = parse_cod(os.path.join(D, '889F.cod'))
T = t889[0]
out = io.StringIO()
def P(*a): print(*a, file=out)

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')][:400]
shown = collections.Counter()
for path in files:
    w.heads.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)
    for t in (0x19, 0x06, 0x49, 0x47):
        for hd, h in w.heads.get(t, []):
            if shown[t] >= 4:
                continue
            shown[t] += 1
            P('=== type 0x%02x  %s  head(%d)=%s' % (t, os.path.basename(path), len(h), h.hex(' ')))
            P('    ascii-ish:', ''.join(chr(c) if 32 <= c < 127 else '.' for c in h))
            # try every even offset as text start, decode rest
            for st in range(0, len(h) - 1, 1):
                s = decode(h[st:], T, 0)
                if any(0xAC00 <= ord(c) <= 0xD7A3 for c in s):
                    P('    text@%d: %r' % (st, s))
            # try u16 length prefix interpretations
            for st in range(0, len(h) - 3):
                ln = struct.unpack_from('<H', h, st)[0]
                if 2 <= ln <= 60 and st + 2 + ln <= len(h) and ln % 2 == 0:
                    s = decode(h[st + 2:st + 2 + ln], T, 0)
                    if any(0xAC00 <= ord(c) <= 0xD7A3 for c in s):
                        P('    lenpfx@%d ln=%d: %r' % (st, ln, s))
open(r'C:\research\samilpo\raw\head_dump.txt', 'w', encoding='utf-8').write(out.getvalue())
print('ok', dict(shown))
