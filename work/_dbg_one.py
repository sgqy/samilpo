"""Debug one file's measure structure end to end (work scratch).

Usage: python work/_dbg_one.py <file.smc> <meas> [<meas> ...]
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
import verify_musicxml

ns = _ap.Namespace(extent='score+ext', accidental_policy='explicit',
                   lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                   hyphen_policy='literal', part_merge='auto',
                   emit_layout=False, timesig_clamp=False, dynamic_map=None)
opts = smc2ir.Options(ns)


def main():
    path = sys.argv[1]
    want = set(int(x) for x in sys.argv[2:])
    buf = io.StringIO()
    score, em = smc2ir.convert(path, opts, buf)
    text = buf.getvalue()
    sc, parts, pm, ev, si = ir2musicxml.load_ir_text(text)
    for pid, ml in pm.items():
        for r in ml:
            if r['n'] in want:
                print('measure %d tpm=%d gap=%s content_end=%s warnings=%s' % (
                    r['n'], r['tpm'], r['gap'], r['content_end'], r['warnings']))
    for line in text.splitlines():
        r = json.loads(line)
        if r.get('kind') == 'note' and r.get('meas') in want:
            print('  note meas=%d key=%-5d on=%-5d grid=%-5d dur=%-5d grace=%-5s'
                  % (r['meas'], r['src']['key'], r['on'], r['grid'], r['dur'],
                     r['attrs']['grace']))
    flat = {}
    for pid, ml in pm.items():
        for rec in ml:
            flat[(pid, rec['n'])] = rec
    root = ir2musicxml.build(sc, parts, pm, ev, si, 'dbg')
    for part in root.findall('part'):
        for m in part.findall('measure'):
            if int(m.get('number')) in want:
                print('--- XML measure', m.get('number'))
                for el in m:
                    if el.tag == 'note':
                        print('   note dur=%s type=%s rest=%s grace=%s chord=%s voice=%s' % (
                            el.findtext('duration'), el.findtext('type'),
                            el.find('rest') is not None, el.find('grace') is not None,
                            el.find('chord') is not None, el.findtext('voice')))
                    elif el.tag in ('backup', 'forward'):
                        print('   %s %s' % (el.tag, el.findtext('duration')))
                    else:
                        print('  ', el.tag)


if __name__ == '__main__':
    main()
