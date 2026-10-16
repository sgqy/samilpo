"""Does `type_index` give the root of a chord symbol?

Hypothesis: `type_index` on a 0x45 is a 0-based scale degree within the measure's
key signature, so

    root_pc = (tonic_pc + SCALE[type_index]) % 12

That would supply a root for the 29892 symbols whose FretBoard holds no fingering,
and it is testable against the 148017 symbols where the fingering already gives a
root.

Reports, for major and minor keys separately:
  * how often the predicted pitch class equals the fingering root
  * which degree table fits best (major / natural minor / chromatic)
  * the confusion between predicted degree and the chord's own third, to rule out
    the possibility that type_index is a degree of the chord rather than of the key
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
OUT = r'C:\research\samilpo\work\out_type_index.txt'

MAJOR = [0, 2, 4, 5, 7, 9, 11]
NAT_MINOR = [0, 2, 3, 5, 7, 8, 10]
HARM_MINOR = [0, 2, 3, 5, 7, 8, 11]
CHROMATIC = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# key_fifths -> tonic pc (major) ; smc2ir.key_fifths maps symbol/count to fifths
FIFTH_TO_TONIC_MAJOR = {0: 0, 1: 7, 2: 2, 3: 9, 4: 4, 5: 11, 6: 6,
                        -1: 5, -2: 10, -3: 3, -4: 8, -5: 1, -6: 6}
FIFTH_TO_TONIC_MINOR = {0: 9, 1: 4, 2: 11, 3: 6, 4: 1, 5: 8, 6: 3,
                        -1: 2, -2: 7, -3: 0, -4: 5, -5: 10, -6: 3}


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

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    cases = []      # (fifths, keysig_type, type_index, root_pc, name)
    n_rootless_ti = collections.Counter()

    for i, path in enumerate(files):
        try:
            doc = S.load(path)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                fifths = smc2ir.key_fifths(meas.keysig_symbol, meas.keysig_count)
                for m in walk(meas):
                    if m.type != 0x45:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    r = root_from_fret_info(ce.fret_info) if ce else None
                    if r:
                        cases.append((fifths, meas.keysig_type, m.type_index,
                                      r['midi'] % 12, ce.name if ce else b''))
                    else:
                        n_rootless_ti[m.type_index] += 1
        if (i + 1) % 2000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('=' * 78)
    w('SAMPLES')
    w('=' * 78)
    w('symbols with a fingering root : %d' % len(cases))
    w('type_index distribution among the rootless : %s' % n_rootless_ti.most_common())

    w('')
    w('=' * 78)
    w('PREDICTION ACCURACY: root_pc == (tonic + SCALE[type_index]) % 12')
    w('=' * 78)

    def score(scale, tonic_fn, label):
        ok = 0
        tot = 0
        for fifths, ktype, ti, rpc, name in cases:
            if ti is None or not (0 <= ti < len(scale)):
                continue
            if ktype == 2:
                continue
            tonic = tonic_fn(fifths)
            if tonic is None:
                continue
            tot += 1
            if (tonic + scale[ti]) % 12 == rpc:
                ok += 1
        return label, ok, tot

    for scale, sname in ((MAJOR, 'major'), (NAT_MINOR, 'nat-minor'),
                         (HARM_MINOR, 'harm-minor'), (CHROMATIC, 'chromatic')):
        for tfn, tname in ((lambda x: FIFTH_TO_TONIC_MAJOR.get(x), 'major-key'),
                           (lambda x: FIFTH_TO_TONIC_MINOR.get(x), 'minor-key')):
            label, ok, tot = score(scale, tfn, '%s / %s' % (sname, tname))
            w('   %-24s %7d / %-7d = %6.2f%%'
              % (label, ok, tot, 100.0 * ok / max(tot, 1)))

    w('')
    w('=' * 78)
    w('CONTROL: does type_index instead index the CHORD\'s own degree?')
    w('=' * 78)
    w('   interval (root_pc - key_tonic) vs type_index, for major key & ktype==1:')
    grid = collections.defaultdict(collections.Counter)
    for fifths, ktype, ti, rpc, name in cases:
        if ktype == 2:
            continue
        tonic = FIFTH_TO_TONIC_MAJOR.get(fifths)
        if tonic is None or ti is None:
            continue
        grid[ti][(rpc - tonic) % 12] += 1
    for ti in sorted(grid):
        tot = sum(grid[ti].values())
        top = grid[ti].most_common(3)
        w('   type_index=%-3d n=%-7d top intervals %s'
          % (ti, tot, [(k, '%.0f%%' % (100.0 * v / tot)) for k, v in top]))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
