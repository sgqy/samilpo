"""Lyric decode validation, written to UTF-8 for accurate inspection."""
import sys, os, io, contextlib, glob, struct, collections
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
t, _, _ = parse_cod(os.path.join(D, '889F.cod')); T = t[0]
out = io.StringIO()
def P(*a): print(*a, file=out)

p = glob.glob(os.path.join(D, '8000Songs', '**', '150ALS-03DA-0012.smc'), recursive=True)[0]
w.heads.clear()
with contextlib.redirect_stdout(io.StringIO()):
    w.main(p)
hs = w.heads.get(0x19, [])
P('file', os.path.basename(p), 'lyric records', len(hs))
seq = []
unmapped = collections.Counter()
for msghdr, payload in hs:
    ln = payload[0x0C]
    txt = payload[0x10:0x10 + ln]
    s = decode(txt, T, 0)
    seq.append(s)
    i = 0
    while i < len(txt):
        if txt[i] < 0x80:
            i += 1
        else:
            code = (txt[i] << 8) | (txt[i + 1] if i + 1 < len(txt) else 0)
            v = T.lookup(code)
            if v == code:
                unmapped[code] += 1
            i += 2
P('sequence:'); P('  ' + '|'.join(seq))
P('joined: ' + ''.join(seq))
P('unmapped codes (lookup returned the input):', {hex(k): v for k, v in unmapped.most_common()})
P()
# what do those codes "mean" in the table
for code, n in unmapped.most_common(12):
    P('   %04x x%d -> table value %04x' % (code, n, T.lookup(code)))
open(r'C:\research\samilpo\raw\lyric_probe.txt', 'w', encoding='utf-8').write(out.getvalue())
print('ok')
