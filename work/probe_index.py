"""Probe: parse Score.sci (SSIF) record layout, require exact file consumption.

REA anchors (MusicBook.exe):
  container : magic[4]=='SSIF' (strcmp), u16 version==0x200, u32 count
  records   : sequential, read order per FUN_00413030 =
      base  FUN_00412c30 : u8, u8, group(FUN_004052d0)
      then  FUN_00401580 : u16 nbytes + nbytes raw (ANSI path)
      then  group x4 (FUN_004052d0 at +0x74/+0xC4/+0x114/+0x164)
      then  u16
  group     FUN_004052d0 : ???(FUN_00401b70) , u16 n, n*item(FUN_00402100),
                           u16 m, m*u16
Record objects are 0x1B8 bytes; group objects 0x50 apart.
"""
import struct, sys, collections

path = sys.argv[1] if len(sys.argv) > 1 else r'A:\samilpo-res\Samilpo 2.0\IndexFiles\Score.sci'
data = open(path, 'rb').read()
magic, ver, count = data[:4], struct.unpack_from('<H', data, 4)[0], struct.unpack_from('<I', data, 6)[0]
print('magic=%r ver=0x%04x count=%d filesize=%d' % (magic, ver, count, len(data)))

p = 10


def u16():
    global p
    v = struct.unpack_from('<H', data, p)[0]; p += 2
    return v


def u32():
    global p
    v = struct.unpack_from('<I', data, p)[0]; p += 4
    return v


def u8():
    global p
    v = data[p]; p += 1
    return v


def raw(n):
    global p
    b = data[p:p + n]; p += n
    return b


def wide():
    n = u16()
    s = raw(n * 2).decode('utf-16-le', errors='replace')
    return s


def ansi():
    n = u16()
    return raw(n).decode('latin-1')


def group():
    """FUN_004052d0: wstr name; u16 n * item; u16 m * u16."""
    name = wide()
    items = []
    n = u16()
    for _ in range(n):
        # FUN_00402100: u16, u16, u32, wstr, u16
        items.append((u16(), u16(), u32(), wide(), u16()))
    vals = []
    m = u16()
    for _ in range(m):
        vals.append(u16())
    return {'name': name, 'items': items, 'vals': vals}


recs = []
try:
    for i in range(count):
        p0 = p
        b0, b1 = u8(), u8()
        g0 = group()
        s = ansi()                       # FUN_00401580 byte string (path?)
        g1, g2, g3, g4 = group(), group(), group(), group()
        tail = u16()
        recs.append((b0, b1, g0, s, g1, g2, g3, g4, tail))
        if i < 3:
            print('rec%d @0x%x-0x%x b0=%d path=%r' % (i, p0, p, b0, s[:44]))
            print('   g0=%r' % (g0,))
            print('   g1=%r' % (g1,))
            print('   g2=%r g3=%r g4=%r tail=%d' % (g2, g3, g4, tail))
except Exception as e:
    print('FAIL at record %d, file offset 0x%x: %r' % (len(recs), p, e))
    print('next bytes:', data[p:p + 48].hex(' '))
    # 手工检查最后一条记录区域
    start = p
    print('--- tail region (last 200 bytes) ---')
    print(data[-200:].hex(' '))
    sys.exit(1)

print('consumed: %d / %d bytes (residual %d)' % (p, len(data), len(data) - p))
print('rec0:', recs[0][0], recs[0][1], recs[0][3][:50])
print('rec0 g0:', recs[0][2])
print('rec0 g1:', recs[0][4])
print('rec0 tail:', recs[0][8])
print('last path:', recs[-1][3])
b0s = collections.Counter(r[0] for r in recs)
print('b0 histogram:', dict(b0s))
