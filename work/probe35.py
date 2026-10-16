"""Final confirmation of the reviewer-facing smoke samples.

Reads each generated MusicXML and reports exactly the three things that were
reported wrong: the title, the author credit, and the chords - with the closing
measures shown so the absence of a symbol in the source's last two measures is
visible rather than merely asserted.
"""
import os
import sys
import xml.etree.ElementTree as ET

HERE = r'C:\research\samilpo\work\smoke'
OUT = r'C:\research\samilpo\work\out_smoke_confirm.txt'

PITCH = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def main():
    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    for name in ('500KFS-0041', '110SSS-001'):
        p = os.path.join(HERE, name + '.musicxml')
        raw = open(p, 'rb').read()
        text = raw.decode('utf-8-sig')
        root = ET.fromstring(text[text.index('<score-partwise'):])
        ident = root.find('identification')
        pl = root.find('part-list')
        sps = pl.findall('score-part')

        w('=' * 78)
        w('%s.musicxml' % name)
        w('=' * 78)
        w('  bytes            : %d' % len(raw))
        w('  UTF-8 BOM        : %s' % (raw[:3] == b'\xef\xbb\xbf'))
        w('  movement-title   : %r' % root.findtext('movement-title'))
        w('  creators         : %s'
          % [(c.get('type'), c.text) for c in (ident.findall('creator') if ident is not None else [])])
        w('  parts            : %d' % len(sps))
        for sp in sps[:4]:
            w('      %-4s %s' % (sp.get('id'), sp.findtext('part-name')))
        if len(sps) > 4:
            w('      ... and %d more' % (len(sps) - 4))

        p1 = root.find('part')
        ms = p1.findall('measure')
        har = sum(len(m.findall('harmony')) for m in ms)
        w('  P1 measures      : %d' % len(ms))
        w('  P1 harmonies     : %d' % har)

        w('  first 7 measures (ground truth: Am Dm Em F Dm Em Am):')
        for m in ms[:7]:
            hs = []
            for h in m.findall('harmony'):
                r = h.find('root')
                step = r.findtext('root-step') if r is not None else '?'
                alt = r.findtext('root-alter') if r is not None else None
                hs.append('%s%s %s' % (step, '#' if alt and alt != '0' else '',
                                       h.findtext('kind') or ''))
            w('      m%-4s %s' % (m.get('number'), ', '.join(hs) or '(none)'))

        w('  last 4 measures:')
        for m in ms[-4:]:
            hs = []
            for h in m.findall('harmony'):
                r = h.find('root')
                step = r.findtext('root-step') if r is not None else '?'
                hs.append('%s %s' % (step, h.findtext('kind') or ''))
            w('      m%-4s %s' % (m.get('number'), ', '.join(hs) or '(no chord symbol in source)'))
        w('')

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
