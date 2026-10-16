"""Validate the low-byte root reading with the accompaniment bass as arbiter.

The chord-tone test was inconclusive: a triad covers 6 of 12 pitch classes, so
chance alone is ~50% and 53.47% is not evidence.

The bass is a sharper test.  In this corpus the accompaniment's lowest sounding
voice states the chord root - for 500KFS-0041's Am bars the Contrabass plays
A1/E2 and the Vibraphone A3, i.e. pitch classes {9, 4} over root A.  So for a
measure whose only chord symbol has an out-of-range `f8`:

    is the bass pitch class equal to the low-byte root?

Baseline for a random 1-in-12 guess is 8.33%.  Also scores the alternatives, so
the comparison is like-for-like:

  * low byte of f8
  * the whole f8 mod 12
  * the highest byte of f8 mod 12
  * a deterministic pseudo-random pitch class (control)
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_bass_arbiter.txt'

BASE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SPELL = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb',
         'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B', 'Cb']


def pc_of_index(i):
    s = SPELL[i % 18]
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
    import accomp

    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)
    cod = S.load_cod()

    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    # collect files that carry out-of-range symbols, with the measure numbers
    by_file = collections.defaultdict(set)
    raw = collections.defaultdict(dict)
    for i, p in enumerate(files):
        try:
            doc = S.load(p)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                for m in walk(meas):
                    if m.type == 0x45 and m.f8 is not None and m.f8 >= 18:
                        by_file[p].add(mi + 1)
                        raw[p].setdefault(mi + 1, m.f8)
        if (i + 1) % 2000 == 0:
            print('   ... %d/%d' % (i + 1, len(files)))

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('BASS ARBITER')
    w('=' * 78)
    w('files with out-of-range symbols : %d' % len(by_file))

    score = collections.Counter()
    tot = 0
    per_file = []
    for p, measures in by_file.items():
        try:
            doc = S.load(p)
            parts, notes, ms, stats = accomp.build(doc, cod, opts)
        except Exception:
            continue
        # bass pitch classes per measure = lowest midi per (measure) across tracks
        bass = {}
        for n in notes:
            mi = n.get('meas')
            if mi not in measures:
                continue
            midi = n.get('midi')
            if midi is None:
                continue
            if mi not in bass or midi < bass[mi]:
                bass[mi] = midi
        hit_low = hit_all = hit_high = hit_ctrl = 0
        n_here = 0
        for mi, midi in bass.items():
            v = raw[p][mi]
            pc = midi % 12
            n_here += 1
            tot += 1
            if pc_of_index(v & 0xFF) == pc:
                hit_low += 1
                score['low'] += 1
            if pc_of_index(v % 18) == pc:
                score['allmod'] += 1
            if pc_of_index((v >> 8) % 18) == pc:
                score['high'] += 1
            if pc_of_index((v * 7 + 3) % 18) == pc:
                score['control'] += 1
        if n_here:
            per_file.append((os.path.basename(p), n_here, hit_low))

    w('measures scored                 : %d' % tot)
    w('')
    w('%-28s %8s %10s' % ('candidate root', 'hits', 'share'))
    for who in ('low', 'allmod', 'high', 'control'):
        w('%-28s %8d %9.2f%%'
          % (who, score[who], 100.0 * score[who] / max(tot, 1)))
    w('%-28s %8s %9.2f%%' % ('chance (1 of 12)', '-', 100.0 / 12))

    w('')
    w('per-file detail (measures scored, bass matched the low byte):')
    for name, n_here, hit in sorted(per_file, key=lambda r: -r[1])[:30]:
        w('   %-28s n=%-4d hit=%-4d %.0f%%'
          % (name, n_here, hit, 100.0 * hit / max(n_here, 1)))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
