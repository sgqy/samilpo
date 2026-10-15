"""Batch regression: SMC -> IR -> MusicXML for a whole corpus (work scratch).

Runs the full pipeline in-process for every file and validates the MusicXML
against the IR that produced it. Nothing is written to disk unless --out is
given, in which case the first --keep files are also saved for manual review.

Usage:
    python work/batch.py [--dir D] [--max N] [--out DIR] [--keep N]
"""
import argparse
import collections
import glob
import io
import json
import os
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import argparse as _ap
import smc2ir
import ir2musicxml
import verify_musicxml

DEFAULT_DIR = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def options():
    ns = _ap.Namespace(extent='score+ext', accidental_policy='explicit',
                       lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                       hyphen_policy='literal', part_merge='auto',
                       emit_layout=False, timesig_clamp=False, dynamic_map=None)
    return smc2ir.Options(ns)


def ir_from_text(text):
    """Parse IR text in memory, returning both the per-part structure `build`
    needs and the (part, n) keyed view the verifier needs."""
    score, parts, part_measures, events, span_index = ir2musicxml.load_ir_text(text)
    flat = {}
    for pid, mlist in part_measures.items():
        for rec in mlist:
            flat[(pid, rec['n'])] = rec
    return score, parts, part_measures, flat, events, span_index


def text_records(text):
    for line in text.splitlines():
        if line.strip():
            yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DEFAULT_DIR)
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--out')
    ap.add_argument('--keep', type=int, default=3)
    a = ap.parse_args()

    opts = options()
    ok = 0
    fail = collections.Counter()
    examples = []
    totals = collections.Counter()
    kept = 0
    xml_fail = 0

    for path in files(a.dir, a.max):
        name = os.path.basename(path)
        try:
            buf = io.StringIO()
            score, em = smc2ir.convert(path, opts, buf)
            ir_text = buf.getvalue()
        except Exception as e:
            fail['smc2ir.%s' % type(e).__name__] += 1
            examples.append((name, 'smc2ir', traceback.format_exc().strip().splitlines()[-1]))
            continue

        try:
            _score, parts, part_measures, measures, events, span_index = ir_from_text(ir_text)
            root = ir2musicxml.build(_score, parts, part_measures, events,
                                     span_index, 'batch')
            xml_text = ir2musicxml.serialize(root)
            # Re-parse the serialized text: this both validates well-formedness
            # and gives the verifier the same tree a consumer would read.
            root = ir2musicxml.parse(xml_text)
        except Exception as e:
            fail['ir2musicxml.%s' % type(e).__name__] += 1
            examples.append((name, 'ir2musicxml',
                             traceback.format_exc().strip().splitlines()[-1]))
            continue

        counts = collections.Counter()
        for rec in text_records(ir_text):
            if (rec['kind'] == 'note' and not rec.get('rest')
                    and not rec['attrs'].get('grace')):
                counts[(rec['part'], rec['meas'])] += 1

        try:
            if os.environ.get('BATCH_DEBUG'):
                print('DBG root=%r parts=%d measures=%d pm_type=%s' % (
                    root.tag, len(root.findall('part')), len(measures), type(measures).__name__))
            problems = verify_musicxml.check(_score, measures, root,
                                             ir_note_counts=counts)
        except Exception as e:
            fail['verify.%s' % type(e).__name__] += 1
            examples.append((name, 'verify',
                             traceback.format_exc().strip().splitlines()[-1]))
            continue
        if problems:
            xml_fail += 1
            fail['musicxml-unsound'] += 1
            if len(examples) < 20:
                examples.append((name, 'verify', '; '.join(problems[:2])))
        else:
            ok += 1

        totals['records'] += em.count
        for k, v in score['audit'].items():
            totals['audit.' + k] = totals.get('audit.' + k, 0) + v

        if a.out and kept < a.keep:
            os.makedirs(a.out, exist_ok=True)
            base = os.path.join(a.out, os.path.splitext(name)[0])
            open(base + '.ndjson', 'w', encoding='utf-8', newline='\n').write(ir_text)
            open(base + '.musicxml', 'w', encoding='utf-8', newline='\n').write(xml_text)
            kept += 1

    total = ok + sum(fail.values())
    print('sound: %d / %d   (musicxml failed checks: %d)' % (ok, total, xml_fail))
    for k, v in fail.most_common():
        print('   FAIL %-40s %d' % (k, v))
    for name, stage, why in examples[:15]:
        print('      %s [%s] %s' % (name, stage, why[:120]))
    print()
    print('totals:')
    for k in sorted(totals):
        print('   %-32s %d' % (k, totals[k]))


if __name__ == '__main__':
    main()
