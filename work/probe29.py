"""Look for a chord field the reader might be missing.

Two independent checks on 500KFS-0041:

  A. compare the 0x60-byte measure tail for measures WITH a chord against those
     WITHOUT.  A stored chord indicator would show up as a byte pattern present
     only in the first group.  If the two groups are indistinguishable, the tail
     carries no chord information and a bare measure is genuinely bare.

  B. print the raw tail of the closing measures next to a chord-bearing measure
     and a chord-free one from the middle, so the comparison is inspectable.

  C. list every measure whose note count is 1 (a single whole-measure tone) and
     whether it carries a chord - a bare final tone in a piece that writes chords
     on every other measure is the shape the report describes.
"""
import collections
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SMC = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc'
OUT = r'C:\research\samilpo\work\out_tail_fields.txt'


def walk(node):
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

    with_chord, without = {}, {}
    for mi, meas in enumerate(staff.meas):
        has = any(m.type == 0x45 for m in walk(meas))
        t = bytes(getattr(meas, 'tail_raw', b''))
        (with_chord if has else without)[mi + 1] = t

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('A. MEASURE TAIL (0x60 bytes) - WITH chord vs WITHOUT')
    w('=' * 78)
    w('measures with a chord   : %d' % len(with_chord))
    w('measures without        : %d' % len(without))
    w('tail length             : %d' % (len(next(iter(with_chord.values()))) if with_chord else 0))

    by_off = collections.defaultdict(lambda: [collections.Counter(), collections.Counter()])
    for t in with_chord.values():
        for o, b in enumerate(t):
            by_off[o][0][b] += 1
    for t in without.values():
        for o, b in enumerate(t):
            by_off[o][1][b] += 1

    w('')
    w('byte offsets where the two groups are cleanly separable:')
    found = 0
    for o in range(0x60):
        a, b = by_off[o]
        if not a or not b:
            continue
        sa, sb = set(a), set(b)
        if not (sa & sb):
            found += 1
            w('   +0x%02X  with=%s  without=%s' % (o, dict(a), dict(b)))
    if not found:
        w('   none - no tail byte separates a chord-bearing measure from a bare one,')
        w('          so the tail carries no chord indicator')

    w('')
    w('byte offsets that differ between the group means:')
    for o in range(0x60):
        a, b = by_off[o]
        if not a or not b:
            continue
        ma = sum(k * v for k, v in a.items()) / sum(a.values())
        mb = sum(k * v for k, v in b.items()) / sum(b.values())
        if abs(ma - mb) > 0.4:
            w('   +0x%02X  mean_with=%.2f  mean_without=%.2f' % (o, ma, mb))

    w('')
    w('=' * 78)
    w('B. RAW TAILS')
    w('=' * 78)
    for label, group in (('WITH chord', with_chord), ('WITHOUT chord', without)):
        w('')
        w('  %s:' % label)
        for n in sorted(group)[:3] + sorted(group)[-3:]:
            w('    m%-5d %s' % (n, group[n].hex(' ')))
    w('')
    w('  the closing measures specifically:')
    for n in (106, 107, 108, 109):
        grp = 'chord' if n in with_chord else 'bare '
        t = with_chord.get(n) or without.get(n)
        w('    m%-5d [%s] %s' % (n, grp, t.hex(' ')))

    w('')
    w('=' * 78)
    w('C. SINGLE-NOTE MEASURES')
    w('=' * 78)
    w('  measure  notes  chord?  note(s)')
    for mi, meas in enumerate(staff.meas):
        notes = [m for m in walk(meas) if m.type == 0x01]
        if len(notes) != 1:
            continue
        has = any(m.type == 0x45 for m in walk(meas))
        n = notes[0]
        w('  m%-7d %-5d  %-6s  on=%d dur=%d key=%d'
          % (mi + 1, len(notes), 'yes' if has else 'NO', n.start, n.duration, n.midi_key))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
