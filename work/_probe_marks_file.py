"""Marks in one file, grouped by mark index, with measure numbers."""
import collections
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S

MARKTB = [0x00, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x62, 0x56, 0x57, 0x58, 0x59, 0x5c,
          0x65, 0x55, 0x4e, 0x2b, 0x2c, 0x5a, 0x5b, 0x51, 0x52, 0x50, 0x4f, 0x54,
          0x53, 0x73, 0x75, 0x74, 0x76, 0x63, 0x64, 0x7d, 0x7c, 0x77, 0x79, 0x78,
          0x68, 0x70, 0x6f, 0x71, 0x7a, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0x4b,
          0x4a, 0xa9, 0xaa]


def direct(node):
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is not None:
            yield m


def all_notes(node):
    stack = [node]
    while stack:
        n = stack.pop()
        for m in direct(n):
            if m.type == 0x01:
                yield m
            stack.append(m)


def main():
    path = sys.argv[1]
    doc = S.load(path)
    for si, st in enumerate(list(doc.system.staff1) + list(doc.system.staff2)):
        print('== staff %d: %d measures' % (si, len(st.meas)))
        for mi, meas in enumerate(st.meas):
            mark_at_meas = [m for m in direct(meas) if m.type == 0x08]
            for m in mark_at_meas:
                print('  meas %3d  MEAS-LEVEL  idx=%2d glyph=0x%02x start=%d dx=%d dy=%d voice=%d' % (
                    mi, m.head_type, MARKTB[m.head_type], m.start, m.dx, m.dy, m.voice))
            for note in direct(meas):
                if note.type != 0x01:
                    continue
                for sub in direct(note):
                    if sub.type == 0x08:
                        print('  meas %3d  on note key=%3d start=%4d dur=%4d  idx=%2d glyph=0x%02x dx=%d dy=%d voice=%d' % (
                            mi, note.midi_key, note.start, note.duration,
                            sub.head_type, MARKTB[sub.head_type], sub.dx, sub.dy, sub.voice))


main()
