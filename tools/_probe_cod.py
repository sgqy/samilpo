import struct, sys
d = open(r'C:\Program Files (x86)\Samilpo 2.0\MusicBook.exe', 'rb').read()
pe = struct.unpack_from('<I', d, 0x3c)[0]
nsec = struct.unpack_from('<H', d, pe + 6)[0]
opt = pe + 24; optsz = struct.unpack_from('<H', d, pe + 20)[0]
so = opt + optsz
segs = []
for i in range(nsec):
    n, vs, va, rs, ra = struct.unpack_from('<8sIIII', d, so + i * 40)
    segs.append((n.rstrip(b'\0').decode(), va, rs, ra))
    print(n.rstrip(b'\0').decode(), hex(va), hex(ra), hex(rs))

def r2o(va):
    for n, v, s, r in segs:
        if v <= va < v + s:
            return va - v + r
    return None

for label, va in [('KorCode.cod str', 0x43da18), ('\\KS.cod', 0x43fc74)]:
    o = r2o(va - 0x400000)
    print('---', label, hex(va), 'file off', hex(o) if o else None)
    if o:
        for x in range(max(0, o - 0x40), o + 0x50, 16):
            print('%06x' % x, d[x:x + 16].hex(' '), ''.join(chr(c) if 32 <= c < 127 else '.' for c in d[x:x + 16]))
