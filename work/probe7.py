"""Measure the specific numbers cited in work/decisions.md (work scratch).

Usage: python work/probe7.py [--dir D] [--max N] [--subset NAME]

Reports:
  0x45 headLen distribution, 0x47 rhythm count, 0x25 chord count, 0x2C longrest
  headLen, duplicated keys, per-file tiling/overflow tallies, and the note
  parent-type histogram -- the figures the design docs quote.
"""
import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import walk_msgs, play_time, tick_per_meas, tname

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    """"Recursively collect *.smc under d."""

    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=SONGS)
    ap.add_argument('--max', type=int, default=0)
    args = ap.parse_args()

    h45 = collections.Counter()
    h2c = collections.Counter()
    h0c = collections.Counter()
    parent = collections.Counter()
    dup = 0
    over = 0
    under = 0
    meas_total = 0
    fcount = 0
    n45 = nem = n26 = 0
    for path in files(args.dir, args.max):
        fcount += 1
        try:
            doc = S.load(path)
        except S.Fail as e:
            print('FAIL %s %s' % (path, e))
            continue
        wt = doc.system.whole_tick
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                keys_seen = set()
                for mi, meas in enumerate(st.meas):
                    meas_total += 1
                    tpm = tick_per_meas(wt, meas.ts_num, meas.ts_den)
                    s = 0
                    for c in meas.children:
                        if not c['msg']:
                            continue
                        for m, d in walk_msgs([c['msg']]):
                            if m.key in keys_seen:
                                dup += 1
                            keys_seen.add(m.key)
                            if m.type == 0x45:
                                n45 += 1
                                h45[m.head_len] += 1
                            if m.type == 0x2C:
                                h2c[m.head_len] += 1
                            if m.type == 0x0C:
                                h0c[m.head_len] += 1
                            if m.type == 0x01:
                                nem += 1
                            if m.type == 0x26:
                                n26 += 1
                            if m.type in (0x01, 0x03) and not (m.flags & 0x10):
                                s += play_time(m, wt)
                    if s > tpm:
                        over += 1
                    elif s and s < tpm:
                        under += 1
        # parent histogram for 0x45
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                for meas in st.meas:
                    for c in meas.children:
                        if not c['msg']:
                            continue
                        def rec(m, pt):
                            if m.type == 0x45:
                                parent[tname(pt) if pt else 'MEAS'] += 1
                            for cc in m.children:
                                if cc['msg']:
                                    rec(cc['msg'], m.type)
                        rec(c['msg'], None)

    print('files=%d  measures=%d' % (fcount, meas_total))
    print('0x45 chord symbols=%d  headLen=%s' % (n45, dict(h45)))
    print('0x45 parent type=%s' % dict(parent))
    print('0x2C longrest=%d headLen=%s' % (sum(h2c.values()), dict(h2c)))
    print('0x0C coda=%d headLen=%s' % (sum(h0c.values()), dict(h0c)))
    print('0x26 ellipse=%d   notes=%d' % (n26, nem))
    print('duplicate keys within a staff: %d' % dup)
    print('measure with notated sum > tpm: %d ; < tpm (non-empty): %d' % (over, under))


if __name__ == '__main__':
    main()
