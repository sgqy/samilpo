"""Samilpo Korean code tables (.cod) — decoder for SMC text payloads.

Format (docs/lyrics.md; evidence: engine.dll FUN_100306b0 / FUN_100308c0):
forward table (code -> Unicode), each a "CCodeTable":
    u16 n, u16 lo, u16 hi, then n * ( u16 start, u16 end, u16 data[...] )

This is the single decoder for the whole package; the IR stage, the side-text
export and the standalone text tools all decode through here. The table path
is always caller-resolved (CLI: --cod / --install-dir / SAMILPO_INSTALL) —
there is no machine default to fall back to.
"""

import struct


class CodeTable:
    def __init__(self, n, lo, hi, starts, ends, data):
        self.n, self.lo, self.hi = n, lo, hi
        self.starts, self.ends, self.data = starts, ends, data
        self.stride = hi - lo + 1

    def lookup(self, code):
        """FUN_100308c0. Returns the mapped value, or `code` unchanged when
        unmapped/out of range."""
        if not (self.lo <= (code & 0xFF) <= self.hi):
            return code
        for i in range(self.n):
            if self.starts[i] <= (code & 0xFF00) <= self.ends[i]:
                idx = (((code & 0xFF00) - self.starts[i]) >> 8) * self.stride + (code & 0xFF) - self.lo
                v = self.data[i][idx] if 0 <= idx < len(self.data[i]) else 0
                return v if v else code
        return code


def _read_cod_table(b, p):
    n, lo, hi = struct.unpack_from('<3H', b, p)
    p += 6
    stride = hi - lo + 1
    starts, ends, data = [], [], []
    for _ in range(n):
        s, e = struct.unpack_from('<2H', b, p)
        p += 4
        starts.append(s)
        ends.append(e)
        cnt = (((e - s) >> 8) + 1) * stride
        data.append(list(struct.unpack_from('<%dH' % cnt, b, p)) if cnt else [])
        p += cnt * 2
    return CodeTable(n, lo, hi, starts, ends, data), p


def load_cod(path):
    """Load a code table from an explicit path (caller-resolved)."""
    b = open(path, 'rb').read()
    t, _ = _read_cod_table(b, 0)
    return t


def decode(data, table):
    """Decode a byte string via the table; ASCII passes through, unmapped
    bytes become U+FFFD."""
    out, i = [], 0
    while i < len(data):
        c = data[i]
        if c < 0x80:
            out.append(chr(c))
            i += 1
            continue
        if i + 1 < len(data):
            u = table.lookup((c << 8) | data[i + 1])
            out.append(chr(u) if 0 < u < 0x110000 else '\ufffd')
            i += 2
        else:
            out.append('\ufffd')
            i += 1
    return ''.join(out)
