"""Dump every type 0x08 mark in one file, with its measure/note context."""
import sys
sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S

MARKTB = {
    0: 0x00, 1: 0x5d, 2: 0x5e, 3: 0x5f, 4: 0x60, 5: 0x61, 6: 0x62, 7: 0x56,
    8: 0x57, 9: 0x58, 10: 0x59, 11: 0x5c, 12: 0x65, 13: 0x55, 14: 0x4e,
    15: 0x2b, 16: 0x2c, 17: 0x5a, 18: 0x5b, 19: 0x51, 20: 0x52, 21: 0x50,
    22: 0x4f, 23: 0x54, 24: 0x53, 25: 0x73, 26: 0x75, 27: 0x74, 28: 0x76,
    29: 0x63, 30: 0x64, 31: 0x7d, 32: 0x7c, 33: 0x77, 34: 0x79, 35: 0x78,
    36: 0x68, 37: 0x70, 38: 0x6f, 39: 0x71, 40: 0x7a, 41: 0xd0, 42: 0xd1,
    43: 0xd2, 44: 0xd3, 45: 0xd4, 46: 0xd5, 47: 0x4b, 48: 0x4a, 49: 0xa9,
    50: 0xaa,
}


def marks(node, path):
    """Yield (path, msg) for every msg, tracking container path."""
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is None:
            continue
        yield path, m
        for x in marks(m, path + [m]):
            yield x


def main():
    path = sys.argv[1]
    doc = S.load(path)
    for si, st in enumerate(list(doc.system.staff1) + list(doc.system.staff2)):
        for mi, meas in enumerate(st.meas):
            events = []
            for parent_path, m in marks(meas, []):
                if m.type == 0x08:
                    events.append(('MARK', m))
                elif m.type == 0x01:
                    events.append(('note', m))
            if not events:
                continue
            print('--- staff %d meas %d  ts %d/%d' % (si, mi, meas.ts_num, meas.ts_den))
            for kind, m in events:
                if kind == 'MARK':
                    idx = m.head_type
                    print('   MARK idx=%2d glyph=0x%02x voice=%d start=%d dx=%d dy=%d key=0x%x '
                          'rect=%s' % (idx, MARKTB.get(idx, -1), m.voice, m.start, m.dx, m.dy, m.key,
                                       (m.rect_l, m.rect_r)))
                else:
                    print('     note key=%d start=%d dur=%d voice=%d' % (
                        getattr(m, 'midi_key', -1), m.start, getattr(m, 'duration', -1), m.voice))


main()
