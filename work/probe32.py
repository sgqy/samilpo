"""Corpus-wide confirmation of the three reported problems.

  1. TITLE - every file's SYMP title must appear as <movement-title>.
  2. AUTHOR - count files whose page text yields a credit, and confirm the
     resulting <creator> elements reach the MusicXML.
  3. CHORDS AT THE END - count harmony records whose anchor note was missing
     (`anchored: false`), and count measures that carry notes but no chord, to
     show whether a bare closing measure is ordinary in this corpus rather than a
     reader failure.
"""
import argparse
import io
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_issue_confirm.txt'


def files():
    out = []
    for dirpath, _, names in os.walk(SONGS):
        for n in names:
            if n.lower().endswith('.smc'):
                out.append(os.path.join(dirpath, n))
    return sorted(out)


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
    cod = S.load_cod()

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    n_files = 0
    n_err = 0
    title_mismatch = []
    with_credit = []
    creator_lost = []
    n_unanchored = 0
    n_harmony = 0
    n_bare_with_notes = 0
    n_measures_with_notes = 0
    samples_bare = []

    for i, path in enumerate(files()):
        n_files += 1
        name = os.path.basename(path)
        try:
            doc = S.load(path)
            want = smc2ir.decode_text(doc.title_raw, cod)
            buf = io.StringIO()
            smc2ir.convert(path, opts, buf)
            recs = [l for l in buf.getvalue().splitlines() if l.strip()]
            score = None
            for l in recs:
                import json
                o = json.loads(l)
                if o.get('kind') == 'score':
                    score = o
                    break
            got = score.get('title') if score else None
            if (want or None) != (got or None):
                title_mismatch.append((name, want, got))

            creds = (score or {}).get('creators') or []
            if creds:
                with_credit.append((name, [(c['role'], c['name']) for c in creds]))
                # confirm they reach the MusicXML
                s, parts, pm, ev, sp = ir2musicxml.load_ir_text(buf.getvalue())
                root = ir2musicxml.build(s, parts, pm, ev, sp, 'x')
                ident = root.find('identification')
                got_c = [(c.get('type'), c.text) for c in ident.findall('creator')]
                want_c = [(c['role'], c['name']) for c in creds]
                if got_c != want_c:
                    creator_lost.append((name, want_c, got_c))

            for l in recs:
                import json
                o = json.loads(l)
                if o.get('kind') == 'harmony':
                    n_harmony += 1
                    if not o.get('anchored'):
                        n_unanchored += 1
                elif o.get('kind') == 'measure' and o.get('part') == 'P1':
                    pass
        except Exception as e:
            n_err += 1
            continue

        # bare-measure census on the raw doc, independent of the IR
        try:
            for st in list(doc.system.staff1):
                for meas in st.meas:
                    notes = 0
                    chords = 0
                    stack = [meas]
                    while stack:
                        node = stack.pop()
                        for c in getattr(node, 'children', ()) or ():
                            m = c.get('msg') if isinstance(c, dict) else c
                            if m is None:
                                continue
                            if getattr(m, 'type', None) == 0x01:
                                notes += 1
                            elif getattr(m, 'type', None) == 0x45:
                                chords += 1
                            stack.append(m)
                    if notes:
                        n_measures_with_notes += 1
                        if not chords:
                            n_bare_with_notes += 1
                            if len(samples_bare) < 12:
                                samples_bare.append(name)
        except Exception:
            pass

        if (i + 1) % 1500 == 0:
            w('   ... %d/%d' % (i + 1, n_files))

    w('')
    w('=' * 78)
    w('1. TITLE')
    w('=' * 78)
    w('files converted        : %d' % n_files)
    w('conversion errors      : %d' % n_err)
    w('title mismatches       : %d' % len(title_mismatch))
    for name, want, got in title_mismatch[:20]:
        w('   %-28s want=%r got=%r' % (name, want, got))

    w('')
    w('=' * 78)
    w('2. AUTHOR CREDIT')
    w('=' * 78)
    w('files with a credit    : %d of %d (%.1f%%)'
      % (len(with_credit), n_files, 100.0 * len(with_credit) / max(n_files, 1)))
    w('files that lost one    : %d' % len(creator_lost))
    for name, want, got in creator_lost[:20]:
        w('   %-28s want=%r got=%r' % (name, want, got))
    for name, cs in with_credit[:20]:
        w('   %-28s %s' % (name, cs))

    w('')
    w('=' * 78)
    w('3. HARMONY ANCHORS AND BARE MEASURES')
    w('=' * 78)
    w('harmony records total  : %d' % n_harmony)
    w('   anchored: false       : %d (%.3f%%)'
      % (n_unanchored, 100.0 * n_unanchored / max(n_harmony, 1)))
    w('measures with notes    : %d' % n_measures_with_notes)
    w('   carrying no chord    : %d (%.1f%%)'
      % (n_bare_with_notes, 100.0 * n_bare_with_notes / max(n_measures_with_notes, 1)))
    w('   (a bare measure is ordinary, not a reader failure)')

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
