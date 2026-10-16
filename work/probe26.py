"""Count source chord symbols (type 0x45) against emitted <harmony> elements.

The "two chords missing at the end" report needs a source-versus-output count,
not a look at the tail alone: a reader that drops any chord anywhere would show
up as a total mismatch, while a difference confined to the tail is a genuine
absence in the file.  Prints every 0x45 with its measure and anchor, then the
per-measure comparison wherever the two sides disagree.

Also lists measures whose sounded content runs past their own signature, since a
chord anchored in that overrun region is the one place a reader could lose it.
"""
import os
import struct
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SMC = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc'
OUT = r'C:\research\samilpo\work\out_chord_census.txt'


def walk(node):
    """Yield every Msg under a measure, not the measure container itself."""
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is None:
            continue
        yield m
        for x in walk(m):
            yield x


def main():
    import smc_read as S
    doc = S.load(SMC)
    staff = doc.system.staff1[0]

    rows = []                      # (meas_no, anchor_start, chord_key, name_len)
    for mi, meas in enumerate(staff.meas):
        for m in walk(meas):
            if m.type == 0x45:
                ce = getattr(m, 'chord_extra', None)
                rows.append((mi + 1, getattr(m, 'start', 0), m.key,
                             len(ce.name) if ce else -1))

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('SOURCE CHORD SYMBOLS (type 0x45) in staff1')
    w('=' * 78)
    w('file                 : %s' % os.path.basename(SMC))
    w('count in source      : %d' % len(rows))
    w('measures with a chord: %d' % len({r[0] for r in rows}))
    w('total measures       : %d' % len(staff.meas))

    missing = [i + 1 for i in range(len(staff.meas))
               if (i + 1) not in {r[0] for r in rows}]
    w('measures WITHOUT one : %d' % len(missing))
    w('   %s' % missing)

    w('')
    w('every 0x45 in order (measure, anchor start, node key, name bytes):')
    for mi, start, key, nlen in rows:
        w('   m%-5d anchor_start=%-6d key=%-6d name_bytes=%d'
          % (mi, start, key, nlen))

    root = ET.fromstring(open(os.path.join(HERE, 'out_0041.musicxml'),
                              encoding='utf-8').read().split('\n', 2)[2])
    part = root.find('part')
    emitted = {}
    for m in part.findall('measure'):
        n = int(m.get('number'))
        c = len(m.findall('harmony'))
        if c:
            emitted[n] = c

    w('')
    w('=' * 78)
    w('EMITTED HARMONIES (P1)')
    w('=' * 78)
    w('count in output      : %d' % sum(emitted.values()))
    w('measures with one    : %d' % len(emitted))

    src = {}
    for mi, start, key, nlen in rows:
        src[mi] = src.get(mi, 0) + 1

    w('')
    w('per-measure comparison (only where the two disagree):')
    diffs = 0
    for n in sorted(set(src) | set(emitted)):
        a, b = src.get(n, 0), emitted.get(n, 0)
        if a != b:
            diffs += 1
            w('   m%-5d source=%-3d emitted=%-3d' % (n, a, b))
    if not diffs:
        w('   none - every chord symbol in the source reached the output')

    w('')
    w('=' * 78)
    w('MEASURES WHOSE SOUNDED CONTENT RUNS PAST THEIR SIGNATURE')
    w('=' * 78)
    over = []
    for mi, meas in enumerate(staff.meas):
        end = 0
        for m in walk(meas):
            if m.type == 0x01:
                end = max(end, m.start + m.duration)
        tpm = doc.system.whole_tick * meas.ts_num // meas.ts_den
        if end > tpm:
            over.append((mi + 1, tpm, end))
    w('overrunning measures : %d' % len(over))
    for n, tpm, end in over[-16:]:
        w('   m%-5d signature=%-6d content_end=%-6d chord=%s'
          % (n, tpm, end, src.get(n, 0)))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
