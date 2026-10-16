import io
import json
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import batch
import smc2ir

P = sys.argv[1]
TARGET = int(sys.argv[2])

opts = batch.options()
buf = io.StringIO()
score, em = smc2ir.convert(P, opts, buf)
recs = [json.loads(l) for l in buf.getvalue().splitlines()]

for pid in ('A1', 'A2', 'A3', 'A5'):
    ns = sorted([r for r in recs if r.get('kind') == 'note'
                 and r.get('part') == pid and r.get('meas') == TARGET],
                key=lambda r: (r.get('voice', 1), r['on'], r.get('midi') or 0))
    print('=== %s measure %d : %d notes' % (pid, TARGET, len(ns)))
    for r in ns:
        print('   v%-3s on=%-5d dur=%-5d end=%-5d %-4s ts=%-6s tp=%-6s %s'
              % (r.get('voice'), r['on'], r['dur'], r['on'] + r['dur'],
                 r.get('midi'), r.get('tie_start'), r.get('tie_stop'),
                 'CHORD' if r.get('chord') else ''))
    # per voice totals
    tot = {}
    for r in ns:
        if not r.get('chord'):
            tot[r.get('voice')] = tot.get(r.get('voice'), 0) + r['dur']
    print('   per-voice non-chord totals: %s' % tot)
    print()
