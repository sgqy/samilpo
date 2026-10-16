"""Closing- measures audit: what the accompaniment plays where the score is bare.

The report was "two chords missing at the end". probe26/probe28/probe29 proved the
score writes no chord symbol in m108/m109 and that the reader drops none anywhere.
That leaves one reading of the report: the accompaniment tracks keep sounding a
harmony there, so a listener-visible chord exists that no printed symbol declares.

This prints, for the closing measures:
  * the emitted harmony, if any;
  * the sounding pitches of the score part;
  * the sounding pitches of every accompaniment track, grouped by part, which is
    the chord actually heard.

Also re-checks the opening progression against the known ground truth
Am Dm Em F Dm Em Am.
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
OUT = r'C:\research\samilpo\work\out_closing.txt'
XML = os.path.join(HERE, 'out_0041.musicxml')

PITCH = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def midi_of(n):
    st = n.findtext('pitch/step')
    if st is None:
        return None
    alt = int(n.findtext('pitch/alter') or 0)
    oc = int(n.findtext('pitch/octave') or 4)
    return PITCH[st] + alt + 12 * (oc + 1)


def measure_view(m):
    """Return (harmonies, [(onset, midi or None)]) walking a measure."""
    cur = 0
    har = []
    notes = []
    for el in m:
        if el.tag == 'note':
            if el.find('grace') is not None:
                continue
            if el.find('chord') is None:
                cur += int(el.findtext('duration') or 0)
            if el.find('rest') is not None:
                notes.append((cur, None))
            else:
                notes.append((cur, midi_of(el)))
        elif el.tag == 'forward':
            cur += int(el.findtext('duration') or 0)
        elif el.tag == 'backup':
            cur -= int(el.findtext('duration') or 0)
        elif el.tag == 'harmony':
            r = el.find('root')
            step = r.findtext('root-step') if r is not None else '?'
            alt = r.findtext('root-alter') if r is not None else None
            har.append('%s%s %s' % (step, '#' if alt and alt != '0' else '',
                                    el.findtext('kind') or ''))
    return har, notes


def main():
    raw = open(XML, 'rb').read()
    t = raw.decode('utf-8-sig', errors='replace')
    t = t[t.index('<score-partwise'):]
    root = ET.fromstring(t)

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    names = {}
    for sp in root.find('part-list').findall('score-part'):
        names[sp.get('id')] = sp.findtext('part-name')

    w('=' * 78)
    w('OPENING - ground truth is Am Dm Em F Dm Em Am')
    w('=' * 78)
    p1 = root.find('part')
    for m in p1.findall('measure')[:7]:
        har, notes = measure_view(m)
        w('  m%-4s harmonies=%-28s sounding=%s'
          % (m.get('number'), ', '.join(har) or '-',
             ' '.join(str(n) for _, n in notes)))

    w('')
    w('=' * 78)
    w('CLOSING - the score part vs what each accompaniment part sounds')
    w('=' * 78)
    parts = {}
    for p in root.findall('part'):
        parts[p.get('id')] = {int(m.get('number')): m for m in p.findall('measure')}

    for n in range(100, 110):
        har, notes = measure_view(parts['P1'][n])
        w('')
        w('measure %d' % n)
        w('   P1 harmony   : %s' % (', '.join(har) or '(none)'))
        w('   P1 sounds    : %s' % ' '.join(str(x) for _, x in notes))
        for pid in sorted(parts):
            if pid == 'P1' or n not in parts[pid]:
                continue
            _, ns = measure_view(parts[pid][n])
            pitches = sorted({x for _, x in ns if x is not None})
            if not pitches:
                continue
            # name the sounding set as an interval set above its own lowest note
            lo = pitches[0]
            w('   %-4s %-26s n=%-3d midi=%-28s intervals=%s'
              % (pid, names.get(pid, '')[:26], len(ns),
                 ','.join(str(x) for x in pitches),
                 ','.join(str(x - lo) for x in pitches)))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
