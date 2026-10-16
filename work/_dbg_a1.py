import collections
import io
import json
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import batch
import smc2ir

P = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc'
opts = batch.options()
buf = io.StringIO()
score, em = smc2ir.convert(P, opts, buf)

recs = [json.loads(l) for l in buf.getvalue().splitlines()]
timeline = []
for r in recs:
    if r.get('kind') == 'measure' and r.get('part') == 'P1':
        ends = list((r.get('content_end') or {}).values())
        want = max([r.get('tpm', 0)] + ends)
        timeline.append((r['n'], r.get('tpm'), want))

print('melody timeline (n, tpm, realised):')
for row in timeline[:6]:
    print('   ', row)
print()

print('A1 notes, measures 1-3 (on, dur, tie_start, tie_stop, midi):')
rows = [r for r in recs if r.get('kind') == 'note' and r.get('part') == 'A1'
        and r.get('meas') in (1, 2, 3)]
rows.sort(key=lambda r: (r['meas'], r['on']))
for r in rows:
    print('   m%-3d on=%-5d dur=%-5d ts=%-6s tp=%-6s midi=%s'
          % (r['meas'], r['on'], r['dur'], r.get('tie_start'),
             r.get('tie_stop'), r.get('midi')))
print()
for m in (1, 2, 3):
    tot = sum(r['dur'] for r in rows if r['meas'] == m and not r.get('chord'))
    print('  measure %d total non-chord dur = %d' % (m, tot))
