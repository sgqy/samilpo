"""Investigate keysig_type values other than 1 (work scratch).

docs/music-fields.md 1.4 documents only `meas+0x7C == 8` as "no key signature".
The full-corpus census found 929 measures with keysig_type == 2, which the spec
does not describe. This script compares measures by type and prints the raw
MeasTail key-signature neighbourhood so the IR can decide what to do.

Usage: python work/probe8.py [--dir D] [--max N]
"""
import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=SONGS)
    ap.add_argument('--max', type=int, default=0)
    args = ap.parse_args()

    by_type = collections.Counter()
    combo = collections.Counter()
    examples = collections.defaultdict(list)
    affected_files = set()
    for path in files(args.dir, args.max):
        try:
            doc = S.load(path)
        except S.Fail:
            continue
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                for mi, meas in enumerate(st.meas):
                    by_type[meas.keysig_type] += 1
                    combo[(meas.keysig_type, meas.keysig_symbol, meas.keysig_count)] += 1
                    if meas.keysig_type != 1:
                        affected_files.add(os.path.basename(path))
                        if len(examples[meas.keysig_type]) < 6:
                            t = meas.tail_raw
                            examples[meas.keysig_type].append(
                                (os.path.basename(path), mi, t[0x44:0x4E].hex(' '),
                                 t[0x56:0x60].hex(' '), meas.keysig_symbol, meas.keysig_count))
    print('keysig_type histogram : %s' % dict(by_type))
    print('affected files        : %d' % len(affected_files))
    print()
    print('(type, symbol, count) combinations:')
    for k, v in sorted(combo.items()):
        print('   type=%-3d symbol=%-3d count=%-3d  x%d' % (k[0], k[1], k[2], v))
    print()
    for t, rows in sorted(examples.items()):
        print('examples with keysig_type=%d:' % t)
        for name, mi, mid, end, sym, cnt in rows:
            print('   %-18s meas%-5d tail+0x44..0x4D=%s tail+0x56..0x5F=%s sym=%d cnt=%d' % (
                name, mi, mid, end, sym, cnt))


if __name__ == '__main__':
    main()
