"""Two final checks.

  A. NO MEASURES LOST AT THE END. The page/layout structure records how many
     measures the document has (block.f2 = last measure index, start_meas = first).
     If the layout says 109 and the reader produced 109, nothing was truncated.
     A layout that says more than the reader produced would mean the tail of the
     score is being skipped - the one way chords at the end could really be lost.

  B. THE AUTHOR CREDIT IS VISIBLE. It is kept as <creator> for the metadata, but
     the source draws it on the page, so it must also appear as <words> in the
     part. Confirms both forms are present for a file that has a credit.
"""
import argparse
import io
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_final_checks.txt'


def load_doc(path):
    import smc_read as S
    return S.load(path)


def main():
    import smc_read as S
    import smc2ir
    import ir2musicxml

    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('A. MEASURE COUNT - what the layout declares vs what the reader produced')
    w('=' * 78)
    rows = []
    for dirpath, _, names in os.walk(SONGS):
        for n in names:
            if n.lower().endswith('.smc'):
                rows.append(os.path.join(dirpath, n))
    rows.sort()

    n_checked = 0
    short = []
    for path in rows:
        try:
            doc = load_doc(path)
        except Exception:
            continue
        declared = 0
        for page in doc.pages:
            for b in list(getattr(page, 'blocks_a', ()) or ()) + \
                     list(getattr(page, 'blocks_b', ()) or ()):
                # f2 counts the measures the block draws, start_meas is 0-based
                last = getattr(b, 'start_meas', 0) + (getattr(b, 'f2', 0) or 0)
                declared = max(declared, last)
        if not declared:
            continue
        n_checked += 1
        produced = max((len(st.meas) for st in list(doc.system.staff1) + list(doc.system.staff2)),
                       default=0)
        if produced < declared:
            short.append((os.path.basename(path), declared, produced))
    w('files with a layout measure count : %d' % n_checked)
    w('files where the reader produced fewer measures than the layout declares : %d'
      % len(short))
    for name, dec, got in short[:30]:
        w('   %-28s layout=%-5d reader=%-5d  SHORT BY %d' % (name, dec, got, dec - got))

    w('')
    w('500KFS-0041 specifically:')
    doc = load_doc(os.path.join(SONGS, '500KFS', '500KFS-0041.smc'))
    for pi, page in enumerate(doc.pages):
        for b in list(getattr(page, 'blocks_a', ()) or ()) + \
                 list(getattr(page, 'blocks_b', ()) or ()):
            w('   page %d block start_meas=%-5d f2=%-5d -> measures %d..%d'
              % (pi, b.start_meas, b.f2, b.start_meas + 1, b.start_meas + b.f2))
    w('   reader produced: %d measures' % len(doc.system.staff1[0].meas))

    w('')
    w('=' * 78)
    w('B. AUTHOR CREDIT - both the metadata form and the drawn text')
    w('=' * 78)
    for base in ('110SSS-001', '500KFS-0041'):
        matches = []
        for dirpath, _, names in os.walk(SONGS):
            for n in names:
                if n.lower() == base.lower() + '.smc':
                    matches.append(os.path.join(dirpath, n))
        if not matches:
            continue
        path = matches[0]
        buf = io.StringIO()
        smc2ir.convert(path, opts, buf)
        score, parts, pm, ev, sp = ir2musicxml.load_ir_text(buf.getvalue())
        root = ir2musicxml.build(score, parts, pm, ev, sp, 'x')
        ident = root.find('identification')
        creds = [(c.get('type'), c.text) for c in (ident.findall('creator') if ident is not None else [])]
        words = sorted({d.findtext('direction-type/words')
                        for m in root.iter('measure')
                        for d in m.findall('direction')
                        if d.findtext('direction-type/words')})
        w('%s' % base)
        w('   <creator> elements : %s' % creds)
        w('   <words> in score   : %s' % words)
        w('   credit also drawn  : %s'
          % ('yes - it appears as words above' if any('작' in (x or '') for x in words) else 'NO'))
        w('')

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
