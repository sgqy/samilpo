"""Phase-3 probe: dump KAYAKUMA.TTF cmap segments and name table.

DrawNote 0x1004ec70 selects the font face "KayakumA" for note glyphs, so the
music symbols (codeStdHead / codeDot / codeShortLine / codeAcci / CodeDyn /
codePedal / ...) must resolve within this font. This probe reports the cmap
mapping ranges and the font's name table so the glyph source can be pinned.
"""
import struct, os, sys

FONT = r'C:\Program Files (x86)\Samilpo 2.0\Font\KAYAKUMA.TTF'


def walk(b):
    numTables = struct.unpack_from('>H', b, 4)[0]
    tabs = {}
    for i in range(numTables):
        o = 12 + i * 16
        tag = b[o:o + 4].decode('latin1')
        off, ln = struct.unpack_from('>II', b, o + 8)
        tabs[tag] = (off, ln)
    return tabs


def name_strings(b, tabs):
    if 'name' not in tabs:
        return {}
    o, _ = tabs['name']
    fmt, count, strOff = struct.unpack_from('>HHH', b, o)
    out = {}
    for i in range(count):
        p = o + 6 + i * 12
        pid, eid, lid, nid, ln, off = struct.unpack_from('>HHHHHH', b, p)
        s = b[o + strOff + off:o + strOff + off + ln]
        try:
            s = s.decode('utf-16-be') if pid == 3 else s.decode('latin1')
        except Exception:
            continue
        if nid in (1, 2, 4, 6):
            out.setdefault(nid, []).append((pid, eid, lid, s))
    return out


def main():
    b = open(FONT, 'rb').read()
    tabs = walk(b)
    print('+= tables:', sorted(tabs))
    for nid, label in ((1, 'family'), (2, 'style'), (4, 'full'), (6, 'psname')):
        for rec in name_strings(b, tabs).get(nid, [])[:4]:
            print('  name[%d] %s: %r' % (nid, label, rec[3]))
    o, _ = tabs['cmap']
    n = struct.unpack_from('>H', b, o + 2)[0]
    print('+= cmap subtables:')
    for i in range(n):
        p = o + 4 + i * 8
        pid, eid, sub = struct.unpack_from('>HHI', b, p)
        so = o + sub
        fmt = struct.unpack_from('>H', b, so)[0]
        print('   (pid=%d,eid=%d) format=%d' % (pid, eid, fmt))
        if fmt == 4:
            segX2 = struct.unpack_from('>H', b, so + 6)[0]
            seg = segX2 // 2
            ends = struct.unpack_from('>%dH' % seg, b, so + 14)
            starts = struct.unpack_from('>%dH' % seg, b, so + 16 + segX2)
            print('     segments (%d):' % seg)
            for s, e in zip(starts, ends):
                if s == 0xFFFF and e == 0xFFFF:
                    continue
                print('       0x%04x - 0x%04x  (%d chars)' % (s, e, e - s + 1))
    # glyph count
    if 'maxp' in tabs:
        mo, _ = tabs['maxp']
        print('+= numGlyphs:', struct.unpack_from('>H', b, mo + 4)[0])
    # post table: does it contain glyph names?
    if 'post' in tabs:
        po, _ = tabs['post']
        ver = struct.unpack_from('>I', b, po)[0]
        print('+= post version: 0x%08x' % ver)


if __name__ == '__main__':
    main()
