"""Two checks on why a chord could be invisible even though it was emitted.

  1. For 500KFS-0041, every emitted <harmony> must carry a root-step.  A harmony
     whose root could not be read back from the FretBoard would still be counted
     but would render as an empty or suffix-only symbol in a notation program -
     exactly the "chord is missing" report.
  2. Corpus-wide, the number of 0x45 symbols in the source must equal the number
     of harmony records step1 emits.  A shortfall anywhere means the reader skips
     chords, and the last measures of a piece are where a tlv_span or a trailing
     container would hide them.
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
SMC41 = os.path.join(SONGS, '500KFS', '500KFS-0041.smc')
OUT = r'C:\research\samilpo\work\out_harmony_proof.txt'


def walk(node):
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is None:
            continue
        yield m
        for x in walk(m):
            yield x


def source_chords(path):
    import smc_read as S
    doc = S.load(path)
    n = 0
    for st in list(doc.system.staff1) + list(doc.system.staff2):
        for meas in st.meas:
            for m in walk(meas):
                if m.type == 0x45:
                    n += 1
    return n


def main():
    import smc_read as S
    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('1. 500KFS-0041 - is every emitted harmony actually displayable?')
    w('=' * 78)
    root = ET.fromstring(open(os.path.join(HERE, 'out_0041.musicxml'),
                              encoding='utf-8').read().split('\n', 2)[2])
    part = root.find('part')
    bad = []
    total = 0
    for m in part.findall('measure'):
        for h in m.findall('harmony'):
            total += 1
            r = h.find('root')
            step = r.findtext('root-step') if r is not None else None
            kind = h.findtext('kind')
            if not step:
                bad.append((int(m.get('number')), step, kind, ET.tostring(h, encoding='unicode').strip()))
    w('harmonies emitted        : %d' % total)
    w('without a root-step      : %d' % len(bad))
    for n, step, kind, xml in bad:
        w('   m%-5d step=%r kind=%r' % (n, step, kind))
        w('        %s' % xml)
    if not bad:
        w('   none - every harmony carries a root and will render')

    w('')
    w('=' * 78)
    w('2. corpus - source 0x45 count vs harmony records emitted by step1')
    w('=' * 78)
    import smc2ir

    files = []
    for dirpath, _, names in os.walk(SONGS):
        for n in names:
            if n.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, n))
    files.sort()
    w('files found              : %d' % len(files))

    import argparse
    import io
    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)
    cod = S.load_cod()

    mismatch = []
    n_ok = 0
    n_err = 0
    for i, path in enumerate(files):
        try:
            src = source_chords(path)
        except Exception as e:
            n_err += 1
            continue
        try:
            buf = io.StringIO()
            smc2ir.convert(path, opts, buf)
            got = 0
            for line in buf.getvalue().splitlines():
                if '"harmony"' in line:
                    got += 1
        except Exception as e:
            n_err += 1
            mismatch.append((os.path.basename(path), src, 'ERROR %s' % e))
            continue
        if src == got:
            n_ok += 1
        else:
            mismatch.append((os.path.basename(path), src, got))
        if (i + 1) % 1000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('files with equal counts  : %d' % n_ok)
    w('files that differ / error: %d' % len(mismatch))
    for name, src, got in mismatch[:60]:
        w('   %-28s source=%-5s emitted=%s' % (name, src, got))
    if len(mismatch) > 60:
        w('   ... and %d more' % (len(mismatch) - 60))

    w('')
    w('=' * 78)
    w('3. unread body bytes - the one region a trailing chord could hide in')
    w('=' * 78)
    n_short = 0
    worst = []
    for path in files:
        try:
            doc = S.load(path)
        except Exception:
            continue
        left = doc.body_len - doc.body_consumed
        if left != 0:
            n_short += 1
            worst.append((left, os.path.basename(path)))
    worst.sort(reverse=True)
    w('files with bytes left over after parsing: %d' % n_short)
    for left, name in worst[:20]:
        w('   %-28s %d bytes unread' % (name, left))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
