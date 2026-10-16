"""Settle the low-byte root with the melody's chord-tone agreement.

The bass test gave 14.72% against an 8.33% chance baseline - suggestive, but with
only 632 measures it is not decisive.

There is a much larger sample available.  The score's own melody was checked
earlier against the chord symbols and 99.1% of 55820 accompaniment-resolved notes
landed on a chord tone - but that used the fingering root.  The same test can be
run on the 734 disputed symbols using the melody notes of their own measures:

    for each out-of-range symbol, take every melody note sounding in that measure
    and ask whether it is a chord tone of each candidate root

Chance is again ~50% for a triad, so the comparison is between candidates, not
against zero.  The candidates are the low byte, the whole value mod 18, the high
byte, and a control.  Whichever explains the melody's own notes best is the root
the engine used, because the melody was written to the harmony.

A second, sharper statistic is included: the melody's FIRST note of the measure,
which in this corpus is overwhelmingly a chord tone (often the root or third).
Chance there is 50% for a triad too, but the candidates differ far more sharply.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_melody_arbiter.txt'

BASE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SPELL = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb',
         'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B', 'Cb']
TRIAD = {0, 3, 4, 7, 10, 11}


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

    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    cand = collections.Counter()
    tot_notes = 0
    tot_first = 0
    first_cand = collections.Counter()
    files_used = 0

    for i, p in enumerate(files):
        try:
            doc = S.load(p)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                disputed = None
                melody = []
                for m in walk(meas):
                    if m.type == 0x45 and m.f8 is not None and m.f8 >= 18:
                        disputed = m.f8
                    elif m.type == 0x01 and getattr(m, 'midi_key', None) is not None:
                        melody.append((m.start, m.midi_key))
                if disputed is None or not melody:
                    continue
                files_used += 1
                roots = {
                    'low': pc_of_index(disputed & 0xFF),
                    'allmod': pc_of_index(disputed % 18),
                    'high': pc_of_index((disputed >> 8) % 18),
                    'control': pc_of_index((disputed * 7 + 3) % 18),
                }
                for _, key in melody:
                    pc = key % 12
                    for who, r in roots.items():
                        if (pc - r) % 12 in TRIAD:
                            cand[who] += 1
                    tot_notes += 1
                melody.sort()
                fpc = melody[0][1] % 12
                for who, r in roots.items():
                    if (fpc - r) % 12 in TRIAD:
                        first_cand[who] += 1
                tot_first += 1
        if (i + 1) % 2000 == 0:
            print('   ... %d/%d' % (i + 1, len(files)))

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)
    w('=' * 78)
    w('MELODY ARBITER for the out-of-range symbols')
    w('=' * 78)
    w('measures examined        : %d' % files_used)
    w('melody notes scored      : %d' % tot_notes)
    w('')
    w('share of ALL melody notes that are chord tones of each candidate root:')
    for who in ('low', 'allmod', 'high', 'control'):
        w('   %-10s %7d / %-7d = %6.2f%%'
          % (who, cand[who], tot_notes, 100.0 * cand[who] / max(tot_notes, 1)))
    w('   %-10s %7s            %6.2f%%   (chance for a triad)'
      % ('chance', '-', 100.0 * 6 / 12))
    w('')
    w('share of the FIRST melody note of the measure that is a chord tone:')
    for who in ('low', 'allmod', 'high', 'control'):
        w('   %-10s %7d / %-7d = %6.2f%%'
          % (who, first_cand[who], tot_first, 100.0 * first_cand[who] / max(tot_first, 1)))

    best = max(cand, key=lambda k: cand[k])
    bestf = max(first_cand, key=lambda k: first_cand[k])
    w('')
    w('best on all melody notes : %s' % best)
    w('best on the first note   : %s' % bestf)
    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
