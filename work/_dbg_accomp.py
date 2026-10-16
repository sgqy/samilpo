"""Diagnose the accompaniment regression: which part, which measure, why."""
import sys
import traceback

sys.path.insert(0, r'C:\research\samilpo\work')
import batch
import smc2ir
import ir2musicxml
import verify_musicxml


def one(path):
    opts = batch.options()
    import io
    buf = io.StringIO()
    try:
        score, em = smc2ir.convert(path, opts, buf)
    except Exception:
        print('smc2ir FAILED:')
        traceback.print_exc()
        return
    text = buf.getvalue()
    print('audit:', score['audit'])
    sc, parts, pm, ev, si = ir2musicxml.load_ir(text)
    print('parts:')
    for p in parts:
        print('   %-5s role=%-14s perc=%-6s ch=%-4s prog=%-4s name=%s'
              % (p.get('id'), p.get('role'), p.get('percussion'),
                 p.get('channel'), p.get('program'), p.get('name')))
    try:
        root = ir2musicxml.build(sc, parts, pm, ev, si, 'x')
    except Exception:
        print('build FAILED:')
        traceback.print_exc()
        return
    # Coverage per part
    for p in root.findall('part'):
        pid = p.get('id')
        ms = p.findall('measure')
        recs = {m['n']: m for m in pm.get(pid, [])}
        bad = []
        for m in ms:
            n = int(m.get('number'))
            rec = recs.get(n)
            if rec is None:
                continue
            tpm = rec.get('tpm', 0)
            ends = list((rec.get('content_end') or {}).values())
            want = max([tpm] + ends)
            total = 0
            for el in m:
                if el.tag == 'note':
                    d = el.find('duration')
                    if d is not None:
                        total += int(d.text)
                elif el.tag in ('forward', 'backup'):
                    pass
            # sum notes per voice is what the verifier does; report raw
            if total and abs(total - want) > 0 and n <= 20:
                bad.append((n, total, want))
        if bad:
            print('   part %-5s first coverage mismatches: %s' % (pid, bad[:6]))
    print('verify:', verify_musicxml.check(sc, parts, pm, ev, si)[:6]
          if hasattr(verify_musicxml, 'check') else 'n/a')


if __name__ == '__main__':
    one(sys.argv[1])
