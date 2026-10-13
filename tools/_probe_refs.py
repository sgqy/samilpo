import struct, sys
paths = [r'C:\Program Files (x86)\Samilpo 2.0\MusicBook.exe', r'C:\Program Files (x86)\Samilpo 2.0\engine.dll']
vas = {0x43da18: 'KorCode.cod', 0x43fc74: '\\KS.cod', 0x43fc7c: '\\B0A1.cod', 0x43fc88: '\\889F.cod',
       0x43fc94: '\\F040b.cod', 0x43fca0: '\\F040a.cod', 0x43da05: '%s\\%s'}
for P in paths:
    d = open(P, 'rb').read()
    print('==', P, len(d))
    for va, name in vas.items():
        pats = [b'\x68' + struct.pack('<I', va),          # push imm32
                struct.pack('<I', va),                    # any dword
                struct.pack('<I', va)[:3]]                # 3-byte tail
        for pi, pat in enumerate(pats):
            start = 0
            hits = []
            while True:
                i = d.find(pat, start)
                if i < 0: break
                hits.append(i); start = i + 1
                if len(hits) > 6: break
            if hits:
                print('  %-16s pat%d at %s' % (name, pi, [hex(h) for h in hits[:6]]))
