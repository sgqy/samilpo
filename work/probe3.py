"""Timing-model checks for IR design (work scratch).

Usage: python work/probe3.py <file.smc> [more.smc ...]

Answers three questions the IR spec has to settle:
  1. Is note head `duration` a notated length or a playback length?
  2. Does `MsgHdr+0x14` start plus notated length tile the measure exactly?
  3. Are grace notes / flag-bit4 notes present and how do they sit on the grid?
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import walk_msgs, play_time, tick_per_meas

GRACE = 0x0010      # MsgHdr+0x0A bit4: silent / grace (docs/smc-format.md 6.5)


def head_dur(m):
    """Note head duration if present, else 0. Rests carry head_len 0."""
    return getattr(m, 'duration', 0)


def timed_pt(m, wt):
    return play_time(m, wt)


def notes(doc):
    for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
        for si, st in enumerate(g):
            for mi, meas in enumerate(st.meas):
                for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                    if m.type in (0x01, 0x03):
                        yield gi, si, mi, meas, m, d


def main(paths):
    ratio_all = collections.Counter()
    grid_bad = []
    grace = 0
    total = 0
    for path in paths:
        doc = S.load(path)
        wt = doc.system.whole_tick
        name = os.path.basename(path)
        per_meas_bad = 0
        for gi, si, mi, meas, m, d in notes(doc):
            total += 1
            pt = play_time(m, wt)
            dur = head_dur(m)
            if m.type == 0x03:
                ratio_all['rest(head_len=0)'] += 1
            elif dur == pt:
                ratio_all['exact'] += 1
            elif pt and dur % pt == 0:
                ratio_all['x%g' % (dur / pt)] += 1
            else:
                ratio_all['other'] += 1
            if m.flags & GRACE:
                grace += 1
        # tiling check: per measure, per voice, notated lengths must sum to tpm
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for si, st in enumerate(g):
                for mi, meas in enumerate(st.meas):
                    tpm = tick_per_meas(wt, meas.ts_num, meas.ts_den)
                    per_voice = collections.defaultdict(int)
                    for m, dd in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                        if m.type in (0x01, 0x03) and not (m.flags & GRACE):
                            per_voice[m.voice] += head_dur(m) or play_time(m, wt)
                    for v, s in per_voice.items():
                        if s != tpm:
                            per_meas_bad += 1
                            grid_bad.append((name, mi, v, meas.ts_num, meas.ts_den, tpm, s))
        print('%-18s measures_with_non_tiling_voice=%d  (of %d measures)' % (
            name, per_meas_bad, len(doc.system.staff1[0].meas) if doc.system.staff1 else 0))
    print()
    print('duration/playTime over %d timed msgs: %s' % (total, dict(ratio_all)))
    print('grace/silent (flags&0x10) notes: %d' % grace)
    print()
    print('measure tiling mismatches (duration sum per voice vs tickPerMeas):')
    for row in grid_bad[:40]:
        print('   %-18s meas%-4d v%d ts=%d/%d tpm=%-5d sum=%-6d' % row)
    if len(grid_bad) > 40:
        print('   ... %d more' % (len(grid_bad) - 40))


if __name__ == '__main__':
    main(sys.argv[1:])
