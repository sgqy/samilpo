"""Corpus-wide census of the accompaniment embedded in chord symbols.

Counts, per file: chord symbols carrying a Rhythm, the distinct styles named,
the number of tracks, and whether any track is percussion (MIDI channel 9).
This is the "hidden" material: present in the file, never drawn on the page.
"""
import glob
import os
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs

ROOT = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_rtm_corpus.txt'


def scan(path):
    """Return (n_chords, n_with_rhythm, [(style, name, n_tracks, n_perc, ev)]) ."""
    doc = S.load(path)
    n_chords = 0
    found = []
    for st in doc.system.staff1 + doc.system.staff2:
        for meas in st.meas:
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type != 0x45:
                        continue
                    n_chords += 1
                    ce = m.chord_extra
                    if not (ce and ce.has_rhythm and ce.rhythm):
                        continue
                    r = ce.rhythm
                    chan = [r.rtm.seg2[i * r.rtm.size2 + 1]
                            for i in range(r.rtm.count2)
                            if (i + 1) * r.rtm.size2 <= len(r.rtm.seg2)]
                    found.append((r.s1.decode('latin-1'), r.s2.decode('latin-1'),
                                  r.rtm.count2, sum(1 for c in chan if c == 9),
                                  r.rtm.event_count, r.rtm.a, r.rtm.b))
    return n_chords, found


def main():
    files = sorted(glob.glob(os.path.join(ROOT, '**', '*.smc'), recursive=True))
    n_files = 0
    with_rtm = []
    styles = Counter()
    track_hist = Counter()
    perc_hist = Counter()
    total_chords = 0
    total_with = 0
    fails = []

    for p in files:
        try:
            n_chords, found = scan(p)
        except Exception as e:
            fails.append((p, repr(e)))
            continue
        n_files += 1
        total_chords += n_chords
        if found:
            total_with += len(found)
            with_rtm.append((p, n_chords, found))
            for s1, s2, nt, np_, ev, a, b in found:
                styles[(s1, s2)] += 1
                track_hist[nt] += 1
                perc_hist[np_] += 1

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('files scanned            : %d\n' % n_files)
        f.write('parse failures           : %d\n' % len(fails))
        f.write('chord symbols total      : %d\n' % total_chords)
        f.write('chords carrying a rhythm : %d\n' % total_with)
        f.write('files with any rhythm    : %d\n' % len(with_rtm))
        f.write('\ntrack-count histogram (tracks -> chords): %s\n'
                % dict(sorted(track_hist.items())))
        f.write('percussion-track histogram (n -> chords): %s\n'
                % dict(sorted(perc_hist.items())))
        f.write('\ndistinct styles (style, name -> chords):\n')
        for (s1, s2), n in styles.most_common(40):
            f.write('   %-12s %-24s %d\n' % (s1, s2, n))
        f.write('\nfiles:\n')
        for p, n_chords, found in with_rtm[:60]:
            rel = p.split('8000Songs')[-1]
            desc = ', '.join('%s/%s(%dt,%dp,%de)' % (a, b, c, d, e)
                             for a, b, c, d, e, _, _ in found[:3])
            f.write('   %-46s chords=%-4d %s\n' % (rel, n_chords, desc))
        if len(with_rtm) > 60:
            f.write('   ... and %d more files\n' % (len(with_rtm) - 60))
        if fails:
            f.write('\nparse failures:\n')
            for p, e in fails[:20]:
                f.write('   %s %s\n' % (p.split('8000Songs')[-1], e))

    print('files=%d chords=%d with_rhythm=%d files_with=%d'
          % (n_files, total_chords, total_with, len(with_rtm)))
    print('tracks:', dict(sorted(track_hist.items())))
    print('perc :', dict(sorted(perc_hist.items())))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
