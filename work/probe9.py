"""Check whether tick durations are always multiples of the notation grid.

whole_tick = 240 implies a 1/64 grid of 15 ticks, so a well-formed note should
have a duration divisible by 15. Non-multiples point at either a different tick
base or a source irregularity, and they are what makes `_exp_for` fail.

Usage: python work/probe9.py [--dir D] [--max N]
"""
import argparse
import collections
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smc_read as S
from probe_smc import walk_msgs, play_time

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=SONGS)
    ap.add_argument('--max', type=int, default=0)
    args = ap.parse_args()

    whole = collections.Counter()
    dur_mod = collections.Counter()
    pt_mod = collections.Counter()
    onset_mod = collections.Counter()
    files_with_bad = set()
    examples = collections.defaultdict(list)
    n = 0
    for path in files(args.dir, args.max):
        try:
            doc = S.load(path)
        except S.Fail:
            continue
        wt = doc.system.whole_tick
        whole[wt] += 1
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                for meas in st.meas:
                    for c in meas.children:
                        if not c['msg']:
                            continue
                        for m, d in walk_msgs([c['msg']]):
                            if m.type != 0x01:
                                continue
                            n += 1
                            dur = getattr(m, 'duration', 0)
                            pt = play_time(m, wt)
                            dur_mod[dur % 15] += 1
                            pt_mod[pt % 15] += 1
                            onset_mod[m.start % 15] += 1
                            if dur % 15:
                                files_with_bad.add(os.path.basename(path))
                                if len(examples['dur'] if False else examples[str(dur % 15)]) < 3:
                                    examples[str(dur % 15)].append(
                                        (os.path.basename(path), meas.ts_num, meas.ts_den,
                                         m.key, dur, pt, m.start, m.dots,
                                         m.type_index & 0x1F, m.flags))
    print('files=%d notes=%d whole_tick=%s' % (len(files_with_bad), n, dict(whole)))
    print('duration %% 15 histogram : %s' % dict(sorted(dur_mod.items())))
    print('playTime %% 15 histogram : %s' % dict(sorted(pt_mod.items())))
    print('onset    %% 15 histogram : %s' % dict(sorted(onset_mod.items())))
    print()
    print('examples of non-multiple durations:')
    for k, rows in sorted(examples.items()):
        for r in rows:
            print('   rem=%-3s %-18s ts=%d/%d key=%-5d dur=%-5d pt=%-5d start=%-5d dots=%d exp=%d flags=0x%04x' % (
                (k,) + r))


if __name__ == '__main__':
    main()
