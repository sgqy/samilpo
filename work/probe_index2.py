"""Probe 2: apply the closed SSIF record grammar to all four index files."""
import struct, os

BASE = r'A:\samilpo-res\Samilpo 2.0\IndexFiles'


def parse(path):
    data = open(path, 'rb').read()
    magic = data[:4]
    ver = struct.unpack_from('<H', data, 4)[0]
    count = struct.unpack_from('<I', data, 6)[0]
    p = 10

    def u16():
        nonlocal p
        v = struct.unpack_from('<H', data, p)[0]; p += 2; return v

    def u32():
        nonlocal p
        v = struct.unpack_from('<I', data, p)[0]; p += 4; return v

    def u8():
        nonlocal p
        v = data[p]; p += 1; return v

    def raw(n):
        nonlocal p
        b = data[p:p + n]; p += n; return b

    def wide():
        n = u16(); return raw(n * 2).decode('utf-16-le', errors='replace')

    def item():
        return (u16(), u16(), u32(), wide(), u16())

    def group():
        name = wide(); n = u16(); items = [item() for _ in range(n)]
        m = u16(); vals = [u16() for _ in range(m)]
        return {'name': name, 'items': items, 'vals': vals}

    recs = []
    for _ in range(count):
        b0, b1 = u8(), u8()
        g0 = group(); blob = raw(u16())
        g1, g2, g3, g4 = group(), group(), group(), group()
        tail = u16()
        recs.append((b0, b1, g0, blob, g1, g2, g3, g4, tail))
    return magic, ver, count, len(data) - p, recs


for f in ('SamIlPo.idx', 'Score.sci', 'CREATOR.CRI', 'SPEECH.OTX'):
    try:
        magic, ver, count, resid, recs = parse(os.path.join(BASE, f))
        r = recs[0]
        print('%-13s magic=%r ver=%04x n=%-5d resid=%d' % (f, magic, ver, count, resid))
        print('   rec0: g0=%r g1=%r g2=%r g3=%r g4=%r tail=%d blob=%r' % (
            r[2]['name'], r[4]['name'], r[5]['name'], r[6]['name'], r[7]['name'], r[8], r[3][:24]))
        print('   rec0 g0.items=%r vals=%r' % (r[2]['items'][:2], r[2]['vals'][:6]))
    except Exception as e:
        print('%-13s FAIL: %r' % (f, e))
