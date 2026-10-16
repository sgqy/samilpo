import sys
sys.path.insert(0, r'C:\research\samilpo\work')
import batch, smc2ir, ir2musicxml

P = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc'
opts = batch.options()
import io
buf = io.StringIO()
score, em = smc2ir.convert(P, opts, buf)
text = buf.getvalue()
sc, parts, pm, ev, si = ir2musicxml.load_ir_text(text)
root = ir2musicxml.build(sc, parts, pm, ev, si, 'x')

for p in root.findall('part'):
    pid = p.get('id')
    recs = {m['n']: m for m in pm.get(pid, [])}
    for m in p.findall('measure'):
        n = int(m.get('number'))
        rec = recs.get(n)
        if rec is None:
            continue
        want = ir2musicxml.measure_length(rec)
        furthest = 0
        cursor = 0
        for el in m:
            if el.tag == 'note':
                if el.find('grace') is None and el.find('chord') is None:
                    cursor += int(el.findtext('duration') or 0)
                furthest = max(furthest, cursor)
            elif el.tag == 'forward':
                cursor += int(el.findtext('duration') or 0)
                furthest = max(furthest, cursor)
            elif el.tag == 'backup':
                cursor -= int(el.findtext('duration') or 0)
        if furthest != want:
            print('part %-5s m%-4d furthest=%-6d want=%-6d tpm=%-6d'
                  % (pid, n, furthest, want, rec.get('tpm')))
            # show the notes of this measure
            for el in m.findall('note'):
                d = el.findtext('duration')
                on = el.find('rest') is not None and 'REST' or (
                    (el.findtext('pitch/step') or 'drum'))
                print('        dur=%-6s %s%s' % (d, on,
                      ' CHORD' if el.find('chord') is not None else ''))
            if n > 45:
                break
    print('---')
