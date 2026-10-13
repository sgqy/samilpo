"""Experimental Samilpo Korean code-table (.cod) decoder and SMC text extractor.

Format evidence
---------------
* Loader  : engine.dll FUN_100306b0  (per code id 1..6, open CKCConv::Open 0x10030b10)
* Lookup  : engine.dll FUN_100308c0  (used by CKCConv::ToUnicode 0x100303d0)
* Use     : engine.dll MyDrawTextOutW 0x10096530 converts SMC text with code id 1 (889F)
Code ids  : 0 Unicode, 1 889F Code, 2 B0A1 Code, 3 F040(95), 4 F040(98), 5 F040(MAC), 6 B0A1(KS)
            (engine.dll CKCConv::GetCodeName 0x10030c80)

File layout: forward table (code -> Unicode) then reverse table (Unicode -> code),
each a "CCodeTable":
    u16 n, u16 lo, u16 hi, then n * ( u16 start, u16 end, u16 data[(((end-start)>>8)+1)*(hi-lo+1)] )

Usage
-----
  python smc_text.py tables <file.cod>...        # dump table structure
  python smc_text.py dec <889F.cod> <hexbytes>   # decode a byte string
  python smc_text.py titles <song.smc> [<cod>]   # decode the title field
  python smc_text.py lyrics <song.smc> [<cod>]   # decode lyric (0x19) records
  python smc_text.py all                         # dump every .cod in the install dir
"""
import struct, sys, os

DEFAULT_COD = r'C:\Program Files (x86)\Samilpo 2.0\889F.cod'
INSTALL = r'C:\Program Files (x86)\Samilpo 2.0'


class CodeTable:
    """engine.dll CCodeTable as loaded by FUN_100306b0."""
    def __init__(self, n, lo, hi, starts, ends, data):
        self.n, self.lo, self.hi = n, lo, hi
        self.starts, self.ends, self.data = starts, ends, data
        self.stride = hi - lo + 1

    def lookup(self, code):
        """FUN_100308c0. Returns the mapped value, or `code` unchanged when unmapped/out of range."""
        if not (self.lo <= (code & 0xff) <= self.hi):
            return code
        for i in range(self.n):
            if self.starts[i] <= (code & 0xff00) <= self.ends[i]:
                idx = (((code & 0xff00) - self.starts[i]) >> 8) * self.stride + (code & 0xff) - self.lo
                v = self.data[i][idx] if 0 <= idx < len(self.data[i]) else 0
                return v if v else code
        return code

    def __repr__(self):
        return 'CodeTable(n=%d, lo=0x%02x, hi=0x%02x, step=%d, ranges=%s)' % (
            self.n, self.lo, self.hi, self.stride,
            [(hex(s), hex(e), len(d)) for s, e, d in zip(self.starts, self.ends, self.data)])


def read_table(b, p):
    n, lo, hi = struct.unpack_from('<3H', b, p); p += 6
    stride = hi - lo + 1
    starts, ends, data = [], [], []
    for _ in range(n):
        s, e = struct.unpack_from('<2H', b, p); p += 4
        starts.append(s); ends.append(e)
        cnt = (((e - s) >> 8) + 1) * stride
        data.append(list(struct.unpack_from('<%dH' % cnt, b, p)) if cnt else [])
        p += cnt * 2
    return CodeTable(n, lo, hi, starts, ends, data), p


def parse_cod(path):
    """Return (forward_table, reverse_table_or_None, consumed, size)."""
    b = open(path, 'rb').read()
    tables, p = [], 0
    while p + 6 <= len(b):
        try:
            t, p2 = read_table(b, p)
        except struct.error:
            break
        if p2 > len(b):
            break
        tables.append(t); p = p2
    fwd, rev = (tables + [None, None])[:2]
    return fwd, rev, p, len(b)


def decode(data, table, strict=False):
    """Decode an 889F-coded byte string using a forward table."""
    out, i = [], 0
    while i < len(data):
        c = data[i]
        if c < 0x80:                      # ToUnicode: single byte passes through
            out.append(chr(c)); i += 1; continue
        if i + 1 < len(data):
            code = (c << 8) | data[i + 1]
            u = table.lookup(code)
            if u == code and strict:
                out.append('\ufffd')
            else:
                out.append(chr(u) if 0 < u < 0x110000 else '\ufffd')
            i += 2
        else:
            out.append('\ufffd'); i += 1
    return ''.join(out)


def _load(cod):
    fwd, rev, used, size = parse_cod(cod)
    if fwd is None:
        raise SystemExit('no forward table in %s' % cod)
    return fwd

def cmd_tables(paths):
    for name in paths:
        fwd, rev, used, size = parse_cod(name)
        print('%s size=%d consumed=%d' % (name, size, used))
        print('  forward:', fwd)
        print('  reverse:', rev)


def cmd_dec(cod, hexstr):
    t = _load(cod)
    print(repr(decode(bytes.fromhex(hexstr), t)))


def _smc_title(data):
    n = struct.unpack_from('<h', data, 0x590)[0]
    return data[0x0e:0x60].split(b'\0')[0]


def cmd_titles(smc, cod=DEFAULT_COD):
    t = _load(cod)
    print(decode(_smc_title(open(smc, 'rb').read()), t))


def cmd_lyrics(smc, cod=DEFAULT_COD):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import io, contextlib, smc_walk as w
    t = _load(cod)
    w.heads.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(smc)
    seq = []
    for msghdr, payload in w.heads.get(0x19, []):
        ln = payload[0x0C]
        seq.append(decode(payload[0x10:0x10 + ln], t))
    print('lyric records:', len(seq))
    print(''.join(seq))
    print(' | '.join(seq))


def cmd_all():
    for f in sorted(os.listdir(INSTALL)):
        if f.lower().endswith(('.cod', '.kbd')):
            fwd, rev, used, size = parse_cod(os.path.join(INSTALL, f))
            print('%-16s size=%-7d consumed=%-7d tables=%s' % (
                f, size, used, [x is not None for x in (fwd, rev)]))


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'tables':
        cmd_tables(sys.argv[2:])
    elif c == 'dec':
        cmd_dec(sys.argv[2], sys.argv[3])
    elif c == 'titles':
        cmd_titles(*sys.argv[2:])
    elif c == 'lyrics':
        cmd_lyrics(*sys.argv[2:])
    elif c == 'all':
        cmd_all()
    else:
        print(__doc__)
