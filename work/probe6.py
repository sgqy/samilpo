"""Check suspicious measures found by the census (work scratch).

Usage: python work/probe6.py [--dir D] [--max N]

Reports:
  * measures whose (num,den) is musically implausible, with raw tail bytes
  * measures whose notated content does not sum to tickPerMeas
  * lyric records whose headLen != 0x10 + bytelen
"""
import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import walk_msgs, play_time, tick_per_meas

DEFAULT_DIR = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
GOOD_DEN = {1, 2, 4, 8, 16, 32, 64, 128}


def files(d, maxn):
    """"Recursively collect *.smc under d."""

    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DEFAULT_DIR)
    ap.add_argument('--max', type=int, default=200)
    args = ap.parse_args()

    odd_ts = []
    odd_sum = []
    bad_lyric = []
    ts_by_numden = collections.Counter()
    for path in files(args.dir, args.max):
        name = os.path.basename(path)
        try:
            doc = S.load(path)
        except S.Fail:
            continue
        wt = doc.system.whole_tick
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for si, st in enumerate(g):
                for mi, meas in enumerate(st.meas):
                    ts_by_numden[(meas.ts_num, meas.ts_den)] += 1
                    tpm = tick_per_meas(wt, meas.ts_num, meas.ts_den)
                    if meas.ts_den not in GOOD_DEN or tpm <= 0 or tpm % 60 != 0:
                        odd_ts.append((name, stats_of(meas), tpm, meas.tail_raw.hex(' ')))
                    s = 0
                    sp = 0
                    for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                        if m.type in (0x01, 0x03) and not (m.flags & 0x10):
                            s += getattr(m, 'duration', 0) or play_time(m, wt)
                            sp += play_time(m, wt)
                    if s and s != tpm:
                        odd_sum.append((name, mi, meas.ts_num, meas.ts_den, tpm, s, sp))
                    for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                        if m.type == 0x19:
                            nb = m.head[0x0C] if len(m.head) >= 0x0D else 0
                            if m.head_len != 0x10 + nb:
                                bad_lyric.append((name, mi, m.key, m.head_len, nb, m.head.hex(' ')))

    print('timesig census (num,den):')
    for k, v in sorted(ts_by_numden.items()):
        print('   %-10s %d' % ('%d/%d' % k, v))
    print()
    print('suspicious timesig measures (%d):' % len(odd_ts))
    for name, st, tpm, tail in odd_ts[:20]:
        print('   %-18s %s tpm=%d' % (name, st, tpm))
        print('        tail=%s' % tail)
    print()
    print('measures whose notated sum != tickPerMeas (%d):' % len(odd_sum))
    both = sum(1 for r in odd_sum if r[6] == r[4])
    print('   (of these, playTime-sum == tickPerMeas in %d cases)' % both)
    for row in odd_sum[:40]:
        print('   %-18s meas%-4d ts=%d/%d tpm=%-6d durSum=%-6d ptSum=%-6d' % row)
    print()
    print('lyric records with headLen != 0x10+bytelen (%d):' % len(bad_lyric))
    for row in bad_lyric[:20]:
        print('   %-18s meas%-4d key=%-6d headLen=%-4d bytelen=%-3d head=%s' % row)


def stats_of(meas):
    return 'meas ts=%d/%d w=%d tail0=0x%02x text=%r' % (
        meas.ts_num, meas.ts_den, meas.tail_5e, meas.meas_mode, meas.timesig_text)


if __name__ == '__main__':
    main()
