"""Minimal read-only PE32 import/export dumper (no third-party deps).
Usage: python pe_dump.py <file> [imports|exports]
"""
import struct, sys

def load(path):
    data = open(path, 'rb').read()
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    nsec = struct.unpack_from('<H', data, pe + 6)[0]
    optsz = struct.unpack_from('<H', data, pe + 20)[0]
    opt = pe + 24
    base = struct.unpack_from('<I', data, opt + 28)[0]
    dd = opt + 96
    secs = []
    so = opt + optsz
    for i in range(nsec):
        name, vs, va, rs, ra = struct.unpack_from('<8sIIII', data, so + i * 40)
        secs.append((name.rstrip(b'\0').decode(), va, max(vs, rs), ra))
    def r2o(rva):
        for n, va, sz, ra in secs:
            if va <= rva < va + sz:
                return rva - va + ra
        raise ValueError(hex(rva))
    def cstr(off):
        e = data.index(b'\0', off)
        return data[off:e].decode('latin1')
    return data, base, dd, r2o, cstr, secs

def exports(path):
    data, base, dd, r2o, cstr, _ = load(path)
    rva, size = struct.unpack_from('<II', data, dd)
    o = r2o(rva)
    (_, _, _, _, nm, obase, nfunc, nnames, afunc, anames, aord) = struct.unpack_from('<IIHHIIIIIII', data, o)
    funcs = [struct.unpack_from('<I', data, r2o(afunc) + 4 * i)[0] for i in range(nfunc)]
    names = {}
    for i in range(nnames):
        n = struct.unpack_from('<I', data, r2o(anames) + 4 * i)[0]
        ordi = struct.unpack_from('<H', data, r2o(aord) + 2 * i)[0]
        names[ordi] = cstr(r2o(n))
    for i, f in enumerate(funcs):
        if f:
            print('%d\t0x%08x\t%s' % (i + obase, base + f, names.get(i, '')))

def imports(path):
    data, base, dd, r2o, cstr, _ = load(path)
    rva, size = struct.unpack_from('<II', data, dd + 8)
    o = r2o(rva)
    while True:
        oft, ts, fc, name, ft = struct.unpack_from('<IIIII', data, o)
        if not name:
            break
        dll = cstr(r2o(name))
        thunk = oft or ft
        i = 0
        while True:
            t = struct.unpack_from('<I', data, r2o(thunk) + 4 * i)[0]
            if not t:
                break
            iat = base + ft + 4 * i
            if t & 0x80000000:
                print('%s\t0x%08x\tord#%d' % (dll, iat, t & 0xFFFF))
            else:
                print('%s\t0x%08x\t%s' % (dll, iat, cstr(r2o(t) + 2)))
            i += 1
        o += 20

if __name__ == '__main__':
    {'imports': imports, 'exports': exports}[sys.argv[2]](sys.argv[1])
