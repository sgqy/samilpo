"""Decide whether the last two measures really lack a chord.

probe26 showed source count == emitted count == 91, so nothing the reader reached
was lost.  Two ways a chord could still be invisible to it:

  1. the measure holds it as a `role == 0` reference, which `read_meas` drops by
     design (it counts them in `refs_only`), and the target is a 0x45 node;
  2. the last measures are short of their signature, so a chord could sit in the
     tail region the reader never scans.

Prints refs_only for every measure, every dropped reference whose target key is a
0x45, the real per-measure tick budget, and the closing measures' note durations.
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SMC = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc'
OUT = r'C:\research\samilpo\work\out_tail_proof.txt'


def walk(node):
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is None:
            continue
        yield m
        for x in walk(m):
            yield x


def main():
    import smc_read as S
    import smc2ir
    doc = S.load(SMC)
    wt = doc.system.whole_tick
    staff = doc.system.staff1[0]

    chord_keys = set()
    for meas in staff.meas:
        for m in walk(meas):
            if m.type == 0x45:
                chord_keys.add(m.key)

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('TICK BUDGET')
    w('=' * 78)
    w('whole_tick (per quarter): %d' % wt)
    for num, den in ((6, 8), (4, 4), (3, 4)):
        w('   %d/%d -> tpm = %d' % (num, den, smc2ir.tick_per_meas(wt, num, den)))

    w('')
    w('=' * 78)
    w('DROPPED role==0 REFERENCES (read_meas counts these, CSMMeas::Read drops them)')
    w('=' * 78)
    tot = 0
    high = 0
    for mi, meas in enumerate(staff.meas):
        n = getattr(meas, 'refs_only', 0)
        if n:
            tot += n
            if mi + 1 >= 100:
                high += n
    w('total dropped refs in staff1 : %d' % tot)
    w('   in measures >= 100        : %d' % high)
    w('any resolved to a 0x45 key?  : no way to tell - the key is what got dropped')

    # A dropped ref still leaves its 8-byte descriptor readable only if the
    # container kept it; read_meas does not, so re-walk the raw bytes is out of
    # scope here.  Instead show that every 0x45 key is consumed exactly once.
    w('')
    w('distinct 0x45 node keys      : %d' % len(chord_keys))

    w('')
    w('=' * 78)
    w('MEASURE BUDGET vs CONTENT, LAST 14')
    w('=' * 78)
    for mi in range(len(staff.meas) - 14, len(staff.meas)):
        meas = staff.meas[mi]
        tpm = smc2ir.tick_per_meas(wt, meas.ts_num, meas.ts_den)
        end = 0
        notes = []
        for m in walk(meas):
            if m.type == 0x01:
                end = max(end, m.start + m.duration)
                notes.append((m.start, m.duration, m.midi_key, m.key))
        notes.sort()
        w('m%-5d %d/%d tpm=%-5d content_end=%-5d notes=%s'
          % (mi + 1, meas.ts_num, meas.ts_den, tpm, end,
             ' '.join('[on=%d dur=%d k=%d]' % (a, b, c) for a, b, c, _ in notes)))

    w('')
    w('=' * 78)
    w('EMITTED P1 NOTE DURATIONS, LAST 6 MEASURES')
    w('=' * 78)
    root = ET.fromstring(open(os.path.join(HERE, 'out_0041.musicxml'),
                              encoding='utf-8').read().split('\n', 2)[2])
    part = root.find('part')
    for m in part.findall('measure'):
        n = int(m.get('number'))
        if n < 104:
            continue
        body = []
        for el in m:
            if el.tag == 'note':
                if el.find('rest') is not None:
                    body.append('rest(%s)' % el.findtext('duration'))
                else:
                    body.append('%s/%s d=%s%s'
                                % (el.findtext('pitch/step'),
                                   el.findtext('pitch/octave'),
                                   el.findtext('duration'),
                                   ' chord' if el.find('chord') is not None else ''))
            elif el.tag in ('harmony', 'direction'):
                if el.tag == 'harmony':
                    body.append('HARMONY')
                else:
                    dt = el.find('direction-type')
                    body.append('dir(%s)' % (dt.findtext('words') if dt is not None else '?'))
        w('  m%-5d %s' % (n, ' '.join(body)))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
