"""Do the out-of-range `f8` values carry the root index in their low byte?

734 symbols still have no root.  All of them have `f8` shaped like
`(high << 8) | low`, e.g. 0x100005, 0xB0000, 0x110006, and the high part is always
a multiple of 0x100.  If the low byte is the root index, the gap closes entirely.

Evidence gathered:
  1. every out-of-range value's low byte, and its high part
  2. a control: on the in-range values the low byte IS `f8`, so the same reading
     must reproduce the known 96.2% agreement with the fingering
  3. an independent arbiter, since the fingering is itself suspect on inversions:
     the accompaniment writes each pitch as a scale degree above the chord root,
     so under the correct root its notes land on chord tones.  Scores the share of
     accompaniment notes that are chord tones of each candidate root.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_lowbyte.txt'

BASE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SPELL = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb',
         'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B', 'Cb']
TRIAD = {0, 3, 4, 7, 10, 11}       # chord tones by interval above the root


def pc_of_index(i):
    s = SPELL[i]
    a = 1 if len(s) > 1 and s[1] == '#' else (-1 if len(s) > 1 and s[1] == 'b' else 0)
    return (BASE[s[0]] + a) % 12


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

    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)

    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    oob = []
    inr_agree = inr_dis = 0
    for i, p in enumerate(files):
        try:
            doc = S.load(p)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                for m in walk(meas):
                    if m.type != 0x45 or m.f8 is None:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    if m.f8 < 18:
                        # control: low byte == f8 here
                        fr = root_from_fret_info(ce.fret_info) if ce else None
                        if fr:
                            if pc_of_index(m.f8 & 0xFF) == fr['midi'] % 12:
                                inr_agree += 1
                            else:
                                inr_dis += 1
                    else:
                        oob.append((p, mi + 1, m, ce))
        if (i + 1) % 2000 == 0:
            print('   ... %d/%d' % (i + 1, len(files)))

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('1. OUT-OF-RANGE f8 VALUES')
    w('=' * 78)
    w('out-of-range count       : %d' % len(oob))
    lows = collections.Counter(v.f8 & 0xFF for _, _, v, _ in oob)
    his = collections.Counter(v.f8 >> 8 for _, _, v, _ in oob)
    w('low byte range           : %d..%d' % (min(lows), max(lows)))
    w('all low bytes < 18       : %s' % all(k < 18 for k in lows))
    w('low byte counts          : %s' % sorted(lows.items()))
    w('distinct high parts      : %d' % len(his))
    w('high parts (as hex)      : %s' % sorted('0x%X' % k for k in his)[:20])

    w('')
    w('=' * 78)
    w('2. CONTROL - the same reading on the in-range population')
    w('=' * 78)
    w('low byte vs fingering root : agree %d / disagree %d = %.2f%%'
      % (inr_agree, inr_dis, 100.0 * inr_agree / max(inr_agree + inr_dis, 1)))
    w('(must reproduce the 96.2%% already measured, since the low byte is f8 there)')

    w('')
    w('=' * 78)
    w('3. ARBITER - accompaniment chord tones under each candidate root')
    w('=' * 78)
    import accomp
    cod = S.load_cod()

    # measure -> candidate roots, per file that has out-of-range symbols
    by_file = collections.defaultdict(dict)
    for p, mi, msg, ce in oob:
        fr = root_from_fret_info(ce.fret_info) if ce else None
        by_file[p][mi] = {
            'low': pc_of_index(msg.f8 & 0xFF),
            'fret': (fr['midi'] % 12) if fr else None,
        }

    n_files = 0
    n_notes = 0
    stat = {'low': [0, 0], 'fret': [0, 0]}
    for p, mapp in by_file.items():
        try:
            doc = S.load(p)
            parts, notes, measures, stats = accomp.build(doc, cod, opts)
        except Exception:
            continue
        n_files += 1
        for n in notes:
            mi = n.get('meas')
            if mi not in mapp:
                continue
            midi = n.get('midi')
            if midi is None:
                continue
            pc = midi % 12
            for who in ('low', 'fret'):
                root = mapp[mi][who]
                if root is None:
                    continue
                stat[who][1] += 1
                if (pc - root) % 12 in TRIAD:
                    stat[who][0] += 1
            n_notes += 1
        if n_files >= 500:
            break

    w('files scored             : %d' % n_files)
    w('accompaniment notes      : %d' % n_notes)
    for who, label in (('low', 'low-byte root'), ('fret', 'fingering root')):
        hit, tot = stat[who]
        w('   %-16s chord-tone hits %d / %d = %.2f%%'
          % (label, hit, tot, 100.0 * hit / max(tot, 1)))
    w('')
    w('A higher hit rate means the root transposes the accompaniment onto chord')
    w('tones more often, which is what the engine itself did when it played it.')

    w('')
    w('=' * 78)
    w('CONCLUSION')
    w('=' * 78)
    if all(k < 18 for k in lows):
        w('Every out-of-range f8 has a low byte in 0..17 with a high part that is a')
        w('multiple of 0x100, so f8 is (tag << 8) | root_index.  Reading the low')
        w('byte when the whole value is not a valid index yields a root for all')
        w('%d symbols that would otherwise emit <harmony> with no <root>.' % len(oob))
    else:
        w('Not every low byte is a valid index, so the reading is unsafe for some')
        w('symbols; those must keep an explicit unknown root.')
    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
