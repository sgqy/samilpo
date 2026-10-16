import io
import json
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import batch
import smc2ir
import accomp

P = sys.argv[1]
opts = batch.options()
buf = io.StringIO()
score, em = smc2ir.convert(P, opts, buf)
recs = [json.loads(l) for l in buf.getvalue().splitlines()]

mel = [r for r in recs if r.get('kind') == 'measure' and r.get('part') == 'P1']
print('melody measures:', len(mel))

start = 0
for r in mel:
    ends = list((r.get('content_end') or {}).values())
    want = max([r.get('tpm', 0)] + ends)
    if 14 <= r['n'] <= 19:
        print('  n=%-4d tpm=%-6d content_end=%-22s want=%-6d start=%-6d limit=%d'
              % (r['n'], r.get('tpm'), r.get('content_end'), want, start,
                 start + want))
    start += want
print('total ticks from timeline:', start)

# What the source actually says
import smc_read as S
doc = S.load(P)
st = doc.system.staff1[0]
print()
print('source measures 14..19:')
t = 0
for i, meas in enumerate(st.meas, 1):
    mt = accomp.measure_ticks(meas.ts_num, meas.ts_den)
    if 14 <= i <= 19:
        print('  m%-4d ts=%d/%d nominal=%-6d' % (i, meas.ts_num, meas.ts_den, mt))
    t += mt
print('total nominal ticks:', t)

# The accompaniment's own view
print()
markers = []
for r in recs:
    if r.get('kind') == 'harmony':
        pass
parts, notes, measures, stats = accomp.build(doc, None, opts)
print('accomp parts:', len(parts), 'notes:', len(notes), 'stats:', dict(stats))
