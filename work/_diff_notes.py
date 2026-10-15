"""Compare emitted MusicXML notes against the IR note stream (work scratch).

For one file and measure, lists IR notes and XML notes side by side, replaying
the XML the way a reader does (backup/forward/grace/chord), and prints the first
divergence so a timing bug can be located exactly.

Usage: python work/_diff_notes.py <file.smc> <meas> [<meas> ...]
"""
import argparse as _ap
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smc2ir
import ir2musicxml
import batch

opts = batch.options()


def main():
    path = sys.argv[1]
    want = [int(x) for x in sys.argv[2:]]
    buf = io.StringIO()
    score, em = smc2ir.convert(path, opts, buf)
    txt = buf.getvalue()
    sc, parts, pm, flat, ev, si = batch.ir_from_text(txt)

    ir_notes = {}
    for line in txt.splitlines():
        r = json.loads(line)
        if r.get('kind') == 'note' and r['meas'] in want:
            ir_notes.setdefault(r['meas'], []).append(r)

    root = ir2musicxml.build(sc, parts, pm, ev, si, 'diff')
    part = root.find('part')
    for meas_el in part.findall('measure'):
        n = int(meas_el.get('number'))
        if n not in want:
            continue
        print('=== measure %d  tpm=%d  content_end=%s  gap=%s'
              % (n, flat[('P1', n)]['tpm'], flat[('P1', n)]['content_end'],
                 flat[('P1', n)]['gap']))
        print('  IR notes (key, on, dur, grace, chord):')
        for r in ir_notes.get(n, []):
            print('    key=%-6d on=%-6d dur=%-6d grace=%-5s chord=%-5s'
                  % (r['src']['key'], r['on'], r['dur'],
                     r['attrs']['grace'], r['chord']))
        print('  XML replay:')
        cur = 0
        for el in meas_el:
            if el.tag == 'note':
                if el.find('grace') is not None:
                    print('    (grace)')
                    continue
                chord = el.find('chord') is not None
                d = int(el.findtext('duration') or 0)
                kind = 'rest' if el.find('rest') is not None else 'note'
                print('    on=%-6d dur=%-6d %-4s chord=%-5s' % (cur, d, kind, chord))
                if not chord:
                    cur += d
            elif el.tag in ('forward', 'backup'):
                d = int(el.findtext('duration') or 0)
                print('    <%s %d>' % (el.tag, d))
                cur += d if el.tag == 'forward' else -d
        print('  final cursor: %d' % cur)


if __name__ == '__main__':
    main()
