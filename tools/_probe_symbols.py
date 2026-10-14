"""Phase-3 probe: 889F mapping of the 0xF0xx code range and symbol-font link.

DrawTextOut renders the engine's music-symbol constants (codeStdHead, codeDot,
codeAcci, codeSlur, ...) as single bytes 0x7F-0xFF through the "KayakumA"
symbol-charset font, which the Windows symbol charset maps to U+F020-U+F0FF.
This probe:
  Q1  which 889F forward codes map into U+F000-U+F0FF (the symbol PUA)
  Q2  whether the corpus text actually uses those codes
  Q3  lists the symbol constant tables read from the engine at 0x10100380
"""
import struct, os, sys
from collections import Counter

COD = r'C:\Program Files (x86)\Samilpo 2.0\889F.cod'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
FONTDIR = r'C:\Program Files (x86)\Samilpo 2.0\Font'

# symbol constant table base observed at 0x10100380 (engine.dll image)
SYM_BASE = 0x10100380
DUMP = bytes.fromhex(
    "3e4445420043050005003d3c2d282900d6d7d8d9d9d9d9d9d9000000e5e4e4e4e4e4e4e4e4"
    "000000dbdbdbdddddddddddd000000dcdcdcdcdcdcdcdcdc000000dbdcdddedfe0e1e2e3e4"
    "e5e6e7e8e9eaebeced4c21000000dbe0e1e2e3e4e5e6e7e8e9eaebeced21cccecfcd72ca"
    "a7cb00000000bfc0c1c2c300000000000000c5c6c7c8c9000000b3b4b5b6b7b8b9babb0000"
    "00989700000000a1a2a3a4a5a6009c9d9e9fa00000999a9b0000a9aaab00a9aaabacadda00"
    "d6d7c4899293949596ee0000bdbe00007f8081828384858687887e00303b3a2b7a772c7b00"
    "ff8e8b4d000000d0d1d2d3d4d500003f46473ecbcb0000494800004344454647414220")


def parse_cod(path):
    b = open(path, 'rb').read()
    p = 0
    n, lo, hi = struct.unpack_from('<3H', b, p); p += 6
    stride = hi - lo + 1
    table = {}
    for _ in range(n):
        s, e = struct.unpack_from('<2H', b, p); p += 4
        cnt = (((e - s) >> 8) + 1) * stride
        for i in range(cnt):
            v = struct.unpack_from('<H', b, p + i * 2)[0]
            if v:
                table[s + (i // stride) * 0x100 + lo + (i % stride)] = v
        p += cnt * 2
    return table


def main():
    fwd = parse_cod(COD)
    sym = {c: u for c, u in fwd.items() if 0xF000 <= u <= 0xF0FF}
    print('Q1 889F codes mapping into U+F000..F0FF: %d' % len(sym))
    for c in sorted(sym)[:40]:
        print('   0x%04x -> U+%04X' % (c, sym[c]))
    print('   code range: 0x%04x..0x%04x' % (min(sym), max(sym)) if sym else '   none')
    print()
    print('Q2 corpus text use of those codes:')
    used = Counter()
    n = 0
    for dp, _, fn in os.walk(SONGS):
        for f in fn:
            if not f.lower().endswith('.smc'):
                continue
            n += 1
            if n > 400:
                break
            d = open(os.path.join(dp, f), 'rb').read()
            for code in sym:
                if d.find(bytes([code >> 8, code & 0xFF])) >= 0:
                    used[code] += 1
        if n > 400:
            break
    print('   scanned %d files; codes found: %s' % (n, dict(sorted(used.items()))[:12] if used else 'none'))
    print()
    print('Q3 symbol constant table (engine image 0x10100380..):')
    names = [
        ('0x10100390', 'codeStdHead', 9), ('0x10100399', '?', 3),
        ('0x101003a4', 'codeCrossHead', 1), ('0x101003aa', '?', 1),
        ('0x101003b7', 'codeSlashHead', 1), ('0x101003c0', 'codeBoxHead', 1),
        ('0x101003c6', 'codeDot', 1),
    ]
    for addr, label, count in names:
        off = int(addr, 16) - SYM_BASE
        vals = DUMP[off:off + count]
        print('   %s %-14s %s' % (addr, label, ' '.join('%02x' % v for v in vals)))
    # scan all single-byte constants in the dump with their addresses
    print()
    print('   single-byte constants 0x7F..0xFF in the table (address: value):')
    for i, v in enumerate(DUMP):
        if 0x7F <= v <= 0xFF and (i == 0 or DUMP[i - 1] != v or True):
            print('     0x%08x = 0x%02x' % (SYM_BASE + i, v))


if __name__ == '__main__':
    main()
