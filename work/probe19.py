"""Standalone check of the accompaniment extractor on one file."""
import collections
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
import accomp


def main(path):
    doc = S.load(path)
    parts, notes, stats = accomp.build(doc, None, None)

    print('stats:', dict(stats))
    print()
    print('parts: %d' % len(parts))
    for p in parts:
        head = '  %-4s %-22s track=%-2s ch=%-2s trans=%-4s%s' % (
            p['id'], p['accomp_style'], p['accomp_track'], p['channel'],
            p['transpose'], ' PERCUSSION' if p['percussion'] else '')
        print(head)

    by = collections.defaultdict(list)
    for n in notes:
        by[n['part']].append(n)
    print()
    for pid in sorted(by):
        ns = by[pid]
        ons = sorted(set((n['meas'], n['on']) for n in ns))
        pitches = sorted(set(n.get('midi') for n in ns if n.get('midi')))
        print('%-4s notes=%-4d measures %d..%d  distinct onsets=%d  midi %s..%s'
              % (pid, len(ns), min(n['meas'] for n in ns),
                 max(n['meas'] for n in ns), len(ons),
                 pitches[0] if pitches else '-', pitches[-1] if pitches else '-'))

    print()
    print('first 4 measures, all parts (meas/on/dur/midi/step):')
    for n in sorted(notes, key=lambda n: (n['meas'], n['on'], n['part']))[:28]:
        print('   m%-4d on=%-5d dur=%-5d %-4s %-5s %s%s%s %s'
              % (n['meas'], n['on'], n['dur'], n['part'],
                 n.get('midi'), n.get('step') or 'drum',
                 n.get('alter') or '', n.get('octave') if n.get('octave') is not None else '',
                 'CHORD' if n.get('chord') else ''))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1
         else r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc')
