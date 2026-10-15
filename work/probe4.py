"""Decode the semantics of note head[2..3] and head+4 duration (work scratch).

Usage:
    python work/probe4.py <file.smc> [more.smc ...] [--limit-n=60]

Prints, for every note message, the raw 12-byte head alongside the derived
notation quantities, so we can test candidate interpretations:
    A) head[2] is literally 0x40 and duration = notated ticks / 2
    B) head[2]+head[3] low bits encode the notated base
    C) duration is a cached/derived value with no stable meaning
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import walk_msgs, play_time, tick_per_meas

CAND_BASE = {'whole': 240, 'half': 120, 'quarter': 60, 'eighth': 30, '16th': 15}


def notes_of(doc):
    for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
        for si, st in enumerate(g):
            for mi, meas in enumerate(st.meas):
                for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                    if m.type == 0x01:
                        yield gi, si, mi, meas, m, d


def main(paths, limit):
    h2 = collections.Counter()
    h23 = collections.Counter()
    ratio = collections.Counter()
    pt_hist = collections.Counter()
    a_ok = b_ok = 0
    n = 0
    samples = []
    for path in paths:
        doc = S.load(path)
        wt = doc.system.whole_tick
        for gi, si, mi, meas, m, d in notes_of(doc):
            n += 1
            pt = play_time(m, wt)
            dur = m.duration
            pt_hist[pt] += 1
            h2[m.head[2]] += 1
            h23[(m.head[2], m.head[3])] += 1
            if pt:
                ratio[dur / pt] += 1
            # candidate A: notated ticks = dur * 2 ? compare against pt
            if dur * 2 == pt:
                a_ok += 1
            if dur == pt:
                b_ok += 1
            if len(samples) < limit:
                samples.append((os.path.basename(path), mi, m, pt))
    print('total notes: %d over %d file(s)' % (n, len(paths)))
    print()
    print('head[2] histogram      : %s' % dict(h2))
    print('(head[2],head[3]) pairs : %s' % dict(sorted(h23.items())))
    print()
    print('duration == playTime   : %d (%.1f%%)' % (b_ok, 100.0 * b_ok / max(n, 1)))
    print('duration*2 == playTime : %d (%.1f%%)' % (a_ok, 100.0 * a_ok / max(n, 1)))
    print()
    print('duration/playTime ratio: %s' % dict(sorted(ratio.items(), key=lambda kv: kv[0])))
    print()
    print('playTime histogram     : %s' % dict(sorted(pt_hist.items())))
    print()
    print('samples (file, meas, raw head, duration, playTime, head[2..3]):')
    for f, mi, m, pt in samples:
        print('  %-18s m%-4d head=%s dur=%-6d pt=%-6d h2=0x%02x h3=0x%02x exp=%d dots=%d' % (
            f, mi, m.head.hex(' '), m.duration, pt, m.head[2], m.head[3],
            m.type_index & 0x1F, m.dots))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    lim = 60
    for a in sys.argv[1:]:
        if a.startswith('--limit-n='):
            lim = int(a.split('=')[1])
    main(args, lim)
