"""In-process orchestration shared by both score modes.

``convert_file``    one .smc -> IR text -> MusicXML (+ side text, + optional
                    IR/MusicXML verification). Replaces the subprocess chain of
                    work/smc_convert.py.
``convert_corpus``  an install directory -> every .smc under 8000Songs, with
                    per-file verification and a failure/warning summary.
                    Replaces the regression loop of work/batch.py (including
                    its stale hardcoded corpus path).

Both modes share one code path; the only differences are input discovery and
reporting granularity. Everything runs in one process — no per-file interpreter
startup, which is what made the old 8451-file batch slow to start.
"""

import collections
import glob
import io
import json
import os
import traceback

from . import __version__
from . import marks, side_text, to_ir, to_musicxml
from . import verify as verify_mod


def make_opts(ns):
    """Build to_ir.Options from an argparse namespace (or any object carrying
    the same attributes). ``ns.cod`` is the resolved code-table path or None."""
    return to_ir.Options(ns)


def ir_to_xml(ir_text, software, namespaced=False):
    """IR text -> serialized MusicXML text."""
    score, parts, part_measures, events, span_index = to_musicxml.load_ir_text(ir_text)
    root = to_musicxml.build(score, parts, part_measures, events, span_index, software)
    return to_musicxml.serialize(root, namespaced=namespaced)


def sounding_note_counts(ir_text):
    """{(part, meas): count of sounding notes} — the verifier's IR view."""
    counts = collections.Counter()
    for line in ir_text.splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r['kind'] == 'note' and not r.get('rest') and not r['attrs'].get('grace'):
            counts[(r['part'], r['meas'])] += 1
    return counts


def _measure_view(ir_text):
    """{(part, n): measure record} — the keyed view the verifier needs."""
    _score, _parts, part_measures, _events, _span_index = to_musicxml.load_ir_text(ir_text)
    flat = {}
    for pid, mlist in part_measures.items():
        for rec in mlist:
            flat[(pid, rec['n'])] = rec
    return flat


def convert_file(smc_path, out_dir, opts, software=None, namespaced=False,
                 side=True, check=False):
    """Convert one file; write its products; return a summary dict.

    Always writes <stem>.ndjson and <stem>.musicxml; writes <stem>.txt when
    the source carries multi-line side text (verses written beside the staff).
    ``check`` runs the IR/MusicXML invariant verifier on the serialized output.
    Raises on failure — the batch loop decides the per-file policy.
    """
    if software is None:
        software = 'smctools ' + __version__
    stem = os.path.splitext(os.path.basename(smc_path))[0]
    os.makedirs(out_dir, exist_ok=True)
    ir_path = os.path.join(out_dir, stem + '.ndjson')
    xml_path = os.path.join(out_dir, stem + '.musicxml')

    buf = io.StringIO()
    score, em = to_ir.convert(smc_path, opts, buf)
    ir_text = buf.getvalue()
    xml_text = ir_to_xml(ir_text, software, namespaced)
    mark_warnings = to_musicxml.take_mark_warnings()

    with open(ir_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(ir_text)
    with open(xml_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(xml_text)

    txt_path = None
    if side:
        blocks = side_text.collect_from_text(ir_text)
        if blocks:
            chunks = side_text.render(blocks, 60)
            lines = []
            for pid, mnum, body in chunks:
                lines.append('[%s measure %d]' % (pid, mnum))
                lines.extend(body)
                lines.append('')
            txt_path = os.path.join(out_dir, stem + '.txt')
            with open(txt_path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write('\n'.join(lines).rstrip('\n') + '\n')

    problems = None
    if check:
        root = to_musicxml.parse(xml_text)
        problems = verify_mod.check(score, _measure_view(ir_text), root,
                                    ir_note_counts=sounding_note_counts(ir_text))
    return {'smc': smc_path, 'ir': ir_path, 'xml': xml_path, 'txt': txt_path,
            'records': em.count, 'audit': score['audit'],
            'mark_warnings': mark_warnings, 'problems': problems}


def convert_corpus(install_dir, out_dir, opts, software=None, namespaced=False,
                   side=True, check=True, limit=0, log=None):
    """Convert every .smc under <install>/8000Songs into out_dir/<subset>/.

    One broken file never aborts the run: failures are collected per stage and
    reported with one example each (the work/batch.py policy). Returns a
    summary dict; ``log(path, summary)`` is called per successful file.
    """
    if software is None:
        software = 'smctools ' + __version__
    songs_dir = os.path.join(install_dir, '8000Songs')
    files = sorted(glob.glob(os.path.join(songs_dir, '**', '*.smc'), recursive=True))
    if limit:
        files = files[:limit]

    ok = 0
    fails = collections.Counter()
    examples = []
    warn_codes = collections.Counter()
    totals = collections.Counter()
    for path in files:
        rel = os.path.relpath(path, songs_dir)
        subset = os.path.dirname(rel)                     # 100SONG .. 500KFS
        target = os.path.join(out_dir, subset) if subset else out_dir
        try:
            s = convert_file(path, target, opts, software=software,
                             namespaced=namespaced, side=side, check=check)
        except Exception as e:
            fails['convert.%s' % type(e).__name__] += 1
            examples.append((os.path.basename(path), 'convert',
                             traceback.format_exc().strip().splitlines()[-1]))
            continue
        ok += 1
        totals['records'] += s['records']
        for w in s['mark_warnings']:
            warn_codes[w['code']] += 1
        if s['problems']:
            fails['musicxml-unsound'] += 1
            if len(examples) < 20:
                examples.append((os.path.basename(path), 'verify',
                                 '; '.join(s['problems'][:2])))
        if log:
            log(path, s)

    return {'total': len(files), 'ok': ok, 'fails': fails, 'examples': examples,
            'warn_codes': warn_codes, 'totals': totals}


def print_corpus_summary(s):
    """Human-readable batch summary (stdout)."""
    print('converted: %d / %d   (musicxml failed checks: %d)' % (
        s['ok'], s['total'], s['fails'].get('musicxml-unsound', 0)))
    for k, v in s['fails'].most_common():
        print('   FAIL %-40s %d' % (k, v))
    for name, stage, why in s['examples'][:15]:
        print('      %s [%s] %s' % (name, stage, why[:120]))
    if s['warn_codes']:
        print('unknown type 0x08 mark indices (kept as words):')
        for code, n in sorted(s['warn_codes'].items()):
            print('   MarkTB[%d] glyph U+%04X  x%d' % (
                code, marks.MARKTB_GLYPH.get(code, 0), n))
    print('totals:')
    for k in sorted(s['totals']):
        print('   %-32s %d' % (k, s['totals'][k]))
