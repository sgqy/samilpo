"""Is a rootless chord symbol really rootless, and what does the output emit?

Three questions:

  A. OUTPUT. What does the current writer produce for a harmony record whose
     `root` is null? MusicXML requires a `<root>` or `<function>` inside
     `<harmony>`, so a bare `<kind>` is invalid and a notation program may draw
     nothing - which would look exactly like "the chord is missing".

  B. NEARBY TEXT. Some files write a chord as ordinary text instead of a chord
     object. If a rootless symbol sits beside a text block, the root may be
     there as text rather than in the symbol.

  C. A SEPARATE 0x46. smc2ir skips type 0x46 as "the fretboard blob of a 0x45".
     If a rootless 0x45 has a sibling 0x46, the root may live there.
"""
import argparse
import collections
import io
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_rootless_emit.txt'


def walk(node):
    """Yield (msg, parent) for every message under a container."""
    stack = [node]
    while stack:
        n = stack.pop()
        for c in getattr(n, 'children', ()) or ():
            m = c.get('msg') if isinstance(c, dict) else c
            if m is None:
                continue
            yield m, n
            stack.append(m)


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

    # ---------- A. what the writer emits for a null root
    w('=' * 78)
    w('A. EMITTED XML FOR A ROOTLESS HARMONY')
    w('=' * 78)
    for base in ('130RVS-016', '110SSS-001'):
        path = None
        for dirpath, _, names in os.walk(SONGS):
            for nm in names:
                if nm.lower() == base.lower() + '.smc':
                    path = os.path.join(dirpath, nm)
        if not path:
            continue
        buf = io.StringIO()
        smc2ir.convert(path, opts, buf)
        score, parts, pm, ev, sp = ir2musicxml.load_ir_text(buf.getvalue())
        root = ir2musicxml.build(score, parts, pm, ev, sp, 'x')
        p1 = root.find('part')
        w('file %s' % base)
        shown = 0
        total = 0
        bad = 0
        for m in p1.findall('measure'):
            for h in m.findall('harmony'):
                total += 1
                has_root = h.find('root') is not None
                has_fn = h.find('function') is not None
                if not (has_root or has_fn):
                    bad += 1
                    if shown < 6:
                        shown += 1
                        w('   measure %s: %s'
                          % (m.get('number'), ET.tostring(h, encoding='unicode').strip()))
        w('   harmonies=%d  without root or function=%d  <- invalid MusicXML'
          % (total, bad))
        w('')

    # ---------- B. text beside rootless symbols, and C. sibling 0x46
    w('=' * 78)
    w('B/C. ROOTLESS SYMBOLS vs NEARBY TEXT AND SIBLING 0x46')
    w('=' * 78)
    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    n_rootless = 0
    n_with_text = 0
    n_with_046 = 0
    txt_types = collections.Counter()
    sibling_types = collections.Counter()
    examples = []

    for path in files:
        try:
            doc = S.load(path)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                # text messages anywhere in this measure
                texts = []
                for m, _ in walk(meas):
                    if m.type in (0x06, 0x04):
                        texts.append(m)
                chords = [(m, p) for m, p in walk(meas) if m.type == 0x45]
                for m, par in chords:
                    ce = getattr(m, 'chord_extra', None)
                    fi = ce.fret_info if ce else b''
                    if not ce:
                        continue
                    try:
                        from fret import root_from_fret_info
                        r = root_from_fret_info(fi)
                    except Exception:
                        r = None
                    if r:
                        continue
                    n_rootless += 1
                    # a rootless symbol sitting in a measure that has text
                    if texts:
                        n_with_text += 1
                        for t in texts:
                            txt_types[t.type] += 1
                        if len(examples) < 8:
                            try:
                                lines, _ = smc2ir.tlv_lines(texts[0].head, opts, None)
                            except Exception:
                                lines = []
                            examples.append((os.path.basename(path), mi + 1,
                                             (ce.name or b'').decode('latin1'),
                                             lines))
                    # any sibling message of type 0x46 under the same parent
                    for c in getattr(par, 'children', ()) or ():
                        sm = c.get('msg') if isinstance(c, dict) else c
                        if sm is not None and sm.type == 0x46:
                            n_with_046 += 1
                            sibling_types[0x46] += 1
                            break

    w('rootless symbols                    : %d' % n_rootless)
    w('   in a measure that also has text  : %d (%.1f%%)'
      % (n_with_text, 100.0 * n_with_text / max(n_rootless, 1)))
    w('   with a sibling 0x46              : %d' % n_with_046)
    w('   text message types seen          : %s' % txt_types.most_common())
    w('')
    w('   examples of a rootless symbol in a measure with text:')
    for name, mi, nm_, lines in examples:
        w('      %-24s m%-4d name=%-8r text=%r' % (name, mi, nm_, lines))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
