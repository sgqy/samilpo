import io
import json
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import batch
import smc2ir
import ir2musicxml

P = sys.argv[1]
TARGET = int(sys.argv[2])

opts = batch.options()
buf = io.StringIO()
score, em = smc2ir.convert(P, opts, buf)
recs = [json.loads(l) for l in buf.getvalue().splitlines()]

mel = {r['n']: r for r in recs
       if r.get('kind') == 'measure' and r.get('part') == 'P1'}
m = mel[TARGET]
print('melody measure %d:' % TARGET)
print('   tpm=%s content_end=%s -> want=%d'
      % (m.get('tpm'), m.get('content_end'),
         max([m.get('tpm', 0)] + list((m.get('content_end') or {}).values()))))

# What lengths did the accompaniment measures get?
for pid in sorted(set(r['part'] for r in recs
                      if r.get('kind') == 'measure' and r.get('part') != 'P1')):
    for r in recs:
        if (r.get('kind') == 'measure' and r.get('part') == pid
                and r.get('n') == TARGET):
            print('   %s tpm=%s' % (pid, r.get('tpm')))
            break
    break

# Melody notes in this measure
print()
print('melody notes in measure %d:' % TARGET)
ns = sorted([r for r in recs if r.get('kind') == 'note'
             and r.get('part') == 'P1' and r.get('meas') == TARGET],
            key=lambda r: (r['on'], r.get('voice', 1)))
for r in ns:
    print('   voice=%s on=%-5d dur=%-5d end=%-5d %s'
          % (r.get('voice'), r['on'], r['dur'], r['on'] + r['dur'],
             r.get('step') or 'drum'))

# Now check the rendered XML for which part overruns
sc, parts, pm, ev, si = ir2musicxml.load_ir_text(buf.getvalue())
root = ir2musicxml.build(sc, parts, pm, ev, si, 'x')
print()
for p in root.findall('part'):
    pid = p.get('id')
    recs_m = {r['n']: r for r in pm.get(pid, [])}
    for me in p.findall('measure'):
        n = int(me.get('number'))
        if n != TARGET:
            continue
        rec = recs_m.get(n)
        want = ir2musicxml.measure_length(rec) if rec else 0
        furthest = 0
        cursor = 0
        for el in me:
            if el.tag == 'note':
                if el.find('grace') is None and el.find('chord') is None:
                    cursor += int(el.findtext('duration') or 0)
                furthest = max(furthest, cursor)
            elif el.tag == 'forward':
                cursor += int(el.findtext('duration') or 0)
                furthest = max(furthest, cursor)
            elif el.tag == 'backup':
                cursor -= int(el.findtext('duration') or 0)
        flag = '  <== OVERRUN' if furthest != want else ''
        print('part %-5s measure %-4d furthest=%-6d want=%-6d%s'
              % (pid, n, furthest, want, flag))
