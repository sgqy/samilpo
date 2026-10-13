import struct
P = r'C:\Program Files (x86)\Samilpo 2.0\MusicBook.exe'
d = open(P, 'rb').read()
for i in range(0, len(d) - 4, 4):
    v = struct.unpack_from('<I', d, i)[0]
    if 0x43fc00 <= v < 0x43fd00 or v == 0x43da18:
        s = d[v - 0x400000:v - 0x400000 + 14]
        print('ptr 0x%08x at file 0x%06x rva 0x%06x -> %r' % (v, i, i + 0x400000 - 0, s))
