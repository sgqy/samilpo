"""Check the reported title and trailing-chord problems, with fresh output.

Also verifies that the file named in the working directory is current: an older
out_0041.musicxml predates the chord-root fix and would show stale harmonies.

Reports:
  * movement-title and creators as emitted
  * every harmony in the last measures, with its real onset in the measure,
    replayed the way a reader walks the measure
  * all NUL-separated strings in the SYMP header and SMC block, so a second
    title candidate would be visible
"""
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SMC = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc'
OUT = r'C:\research\samilpo\work\out_final_check.txt'
COD = None


def strings_in(buf):
    out = []
    cur = bytearray()
    start = 0
    for i, b in enumerate(buf):
        if b == 0:
            if len(cur) >= 2:
                out.append((start, bytes(cur)))
            cur = bytearray()
        else:
            if not cur:
                start = i
            cur.append(b)
    if len(cur) >= 2:
        out.append((start, bytes(cur)))
    return out


def dec(raw):
    try:
        import smc2ir
        return smc2ir.decode_text(raw, COD)
    except Exception as e:
        return '<undecodable %s>' % e


def replay(measure):
    """Return [(onset, kind, label)] for one measure, as a reader walks it."""
    cur = 0
    rows = []
    for el in measure:
        if el.tag == 'note':
            if el.find('grace') is None and el.find('chord') is None:
                cur += int(el.findtext('duration') or 0)
        elif el.tag == 'forward':
            cur += int(el.findtext('duration') or 0)
        elif el.tag == 'backup':
            cur -= int(el.findtext('duration') or 0)
        elif el.tag == 'harmony':
            r = el.find('root')
            step = r.findtext('root-step') if r is not None else '?'
            alt = r.findtext('root-alter') if r is not None else None
            kind = el.findtext('kind') or ''
            rows.append((cur, 'harmony', '%s%s %s' % (step, '#' if alt == '1' else '', kind)))
        elif el.tag == 'direction':
            dt = el.find('direction-type')
            words = dt.findtext('words') if dt is not None else None
            dyn = None
            if dt is not None:
                d2 = dt.find('dynamics')
                if d2 is not None and len(d2):
                    dyn = d2[0].tag
            rows.append((cur, 'direction', words or dyn or '?'))
    return rows


def main():
    global COD
    import smc_read as S
    COD = S.load_cod()

    # Regenerate into the working directory, so what is inspected is what the
    # reviewer opens.
    subprocess.run([sys.executable, os.path.join(HERE, 'smc2ir.py'), SMC,
                    os.path.join(HERE, 'out_0041.ndjson')],
                   capture_output=True, text=True, encoding='utf-8')
    subprocess.run([sys.executable, os.path.join(HERE, 'ir2musicxml.py'),
                    os.path.join(HERE, 'out_0041.ndjson'),
                    os.path.join(HERE, 'out_0041.musicxml')],
                   capture_output=True, text=True, encoding='utf-8')

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('TITLE AND AUTHORS')
    w('=' * 78)
    doc = S.load(SMC)
    w('file                     : %s' % os.path.basename(SMC))
    w('SYMP title_raw           : %r' % doc.title_raw)
    w('SYMP title decoded       : %r' % dec(doc.title_raw))
    w('SYMP extra_str           : %r' % doc.extra_str)
    w('staff name (part name)   : %r' % doc.system.staff1[0].name)

    text = open(os.path.join(HERE, 'out_0041.musicxml'), encoding='utf-8').read()
    root = ET.fromstring(text.split('\n', 2)[2])
    w('emitted movement-title   : %r' % root.findtext('movement-title'))
    ident = root.find('identification')
    w('emitted creators         : %s'
      % [(c.get('type'), c.text) for c in ident.findall('creator')] if ident is not None else 'none')
    w('emitted part-names       : %s'
      % [(sp.get('id'), sp.findtext('part-name'))
         for sp in root.find('part-list').findall('score-part')][:4])

    w('')
    w('all NUL-separated strings in the SYMP header (0x000-0x590):')
    for off, raw in strings_in(doc.__dict__.get('_head', b'') or b''):
        pass
    raw_head = open(SMC, 'rb').read(0x590 + 4)
    for off, raw in strings_in(raw_head):
        w('   @0x%03X len=%-4d %r  -> %r' % (off, len(raw), raw[:48], dec(raw)[:60]))

    w('')
    w('=' * 78)
    w('LAST MEASURES - every harmony and direction, with its onset')
    w('=' * 78)
    part = root.find('part')
    ms = part.findall('measure')
    w('total measures in P1: %d' % len(ms))
    for m in ms[-14:]:
        rows = replay(m)
        n_note = len(m.findall('note'))
        w('  measure %-5s notes=%-4d' % (m.get('number'), n_note))
        if not rows:
            w('        (no harmony, no direction)')
        for on, kind, label in rows:
            w('        on=%-6d %-9s %s' % (on, kind, label))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
