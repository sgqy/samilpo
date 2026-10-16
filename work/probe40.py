"""Decode the text near rootless chord symbols, and profile the files they live in.

The rootless-heavy files (130RVS-016/13/18/20/23/24...) are a distinct population.
Two things to check before concluding the root is unrecoverable:

  A. Are the roots written as ordinary text there?  Decode the measure text with
     the real code table and look at it.
  B. Is the rootless condition a property of the file family (a songbook whose
     chords are not symbols) or spread evenly?
"""
import argparse
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_rootless_text.txt'


def walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        for c in getattr(n, 'children', ()) or ():
            m = c.get('msg') if isinstance(c, dict) else c
            if m is None:
                continue
            yield m
            stack.append(m)


def main():
    import smc_read as S
    import smc2ir
    from fret import root_from_fret_info

    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)
    cod = S.load_cod()

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('A. TEXT IN ROOTLESS-HEAVY FILES')
    w('=' * 78)
    targets = ['130RVS-016.smc', '130RVS-012.smc', '130RVS-013.smc',
               '130RVS-020.smc', '130RVS-024.smc', '130RVS-066.smc']
    for t in targets:
        path = None
        for dirpath, _, names in os.walk(SONGS):
            for nm in names:
                if nm.lower() == t.lower():
                    path = os.path.join(dirpath, nm)
        if not path:
            continue
        doc = S.load(path)
        w('')
        w('%s   (title=%r)' % (t, smc2ir.decode_text(doc.title_raw, cod)))
        n_ch = 0
        n_root = 0
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                texts = []
                chords = []
                for m in walk(meas):
                    if m.type in (0x06, 0x04):
                        try:
                            lines, _ = smc2ir.tlv_lines(m.head, opts, cod)
                        except Exception:
                            lines = []
                        if lines:
                            texts.append((m.type, lines))
                    elif m.type == 0x45:
                        chords.append(m)
                for m in chords:
                    n_ch += 1
                    ce = getattr(m, 'chord_extra', None)
                    if ce and root_from_fret_info(ce.fret_info):
                        n_root += 1
                if mi < 8 and (texts or chords):
                    w('   m%-4d' % (mi + 1))
                    for ty, lines in texts:
                        w('        text(0x%02X) %r' % (ty, lines))
                    for m in chords:
                        ce = getattr(m, 'chord_extra', None)
                        r = root_from_fret_info(ce.fret_info) if ce else None
                        w('        chord name=%-10r info=%-12s root=%s'
                          % ((ce.name if ce else b''), (ce.info.hex(' ') if ce else ''), r))
        w('   total chords=%d  with root=%d' % (n_ch, n_root))

    w('')
    w('=' * 78)
    w('B. IS ROOTLESS A FILE-FAMILY PROPERTY?')
    w('=' * 78)
    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    fam_tot = collections.Counter()
    fam_null = collections.Counter()
    fam_files = collections.Counter()
    null_files = collections.Counter()
    for i, path in enumerate(files):
        try:
            buf = io.StringIO()
            smc2ir.convert(path, opts, buf)
        except Exception:
            continue
        # family = the top-level songbook directory
        rel = os.path.relpath(path, SONGS)
        fam = rel.split(os.sep)[0]
        fam_files[fam] += 1
        c = z = 0
        for line in buf.getvalue().splitlines():
            if '"harmony"' not in line:
                continue
            o = json.loads(line)
            c += 1
            if not o.get('root'):
                z += 1
        fam_tot[fam] += c
        fam_null[fam] += z
        if z:
            null_files[fam] += 1
        if (i + 1) % 2000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('%-24s %8s %8s %8s %10s %10s' % ('family', 'files', 'withnul', 'chords', 'null', 'null%'))
    for fam in sorted(fam_tot, key=lambda x: -fam_null[x]):
        c = fam_tot[fam]
        z = fam_null[fam]
        w('%-24s %8d %8d %8d %10d %9.2f%%'
          % (fam, fam_files[fam], null_files[fam], c, z, 100.0 * z / max(c, 1)))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
