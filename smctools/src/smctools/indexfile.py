"""Samilpo index files (IndexFiles/*.*) — record parsers.

All layouts derived from MusicBook.exe (REA/Ghidra, 2026-11-07); the loader
dispatch is FUN_00414AA0. Exact file consumption verified per format.

Container (all): magic[4] + u16 version (0x0200) + u32 count + payload.

* SSIF (Score.sci, loader FUN_004168E0): count x record, record = virtual Read
  FUN_00413030 (object 0x1B8):
      u8 f0; u8 f1
      group g0
      blob  u16 nbytes; nbytes raw          (FUN_00401580; 0x01 0x00 + path)
      group g1; g2; g3; g4
      u16   tail                            (song year; 0xFFFF unknown)
  Semantics (8449 records, 0 residual): g0.name = title (UTF-16), g1.name =
  lyricist, g2.name = composer.

* SCIF (CREATOR.CRI, loader FUN_004165E0): count x record, Read FUN_004132F0
  (object 0xC4):
      u8 f0; u8 f1
      group g0                              (creator name)
      blob  u16 nbytes; nbytes raw          (0x01 0x00 + IMAGE\\...jpg path)
      group g1                              (bio text with CR LF)
  No trailing u16; the last record may omit nothing else.

* SHIF (SamIlPo.idx, loader FUN_00411210): a tree serialized in DFS order.
  FUN_00410FA0 reads one node:
      u16 flag                              (+0x08)
      u16 child_count                       (+0x20; FUN_004111F0 reads it)
      group                                 (+0x24, FUN_004052D0: name/items/vals)
      u16 n; n x variant                    (+0x74, FUN_00412890 -> FUN_00412530)
  variant (FUN_00412530): u8 type; u8 pad; u16 n;
      type 0     -> n*2 bytes UTF-16LE
      type 1/2/3 -> u32
      type 4/5   -> n bytes ANSI
  The loader reads the root node, then FUN_00411550 walks children
  recursively until the running counter reaches `count` (the root counts as
  node 1). Group/item readers are shared with SSIF (FUN_004052D0 etc.).

Group (FUN_004052D0): wstr name (FUN_00401B70: u16 nchars + nchars*2
UTF-16LE); u16 n; n x item (FUN_00402100: u16 a; u16 b; u32 c; wstr s; u16 d);
u16 m; m x u16.
"""

import struct


class Fail(Exception):
    pass


class _Reader:
    def __init__(self, data, p):
        self.data, self.p = data, p

    def u8(self):
        if self.p + 1 > len(self.data):
            raise Fail('eof at 0x%x' % self.p)
        v = self.data[self.p]; self.p += 1; return v

    def u16(self):
        if self.p + 2 > len(self.data):
            raise Fail('eof at 0x%x' % self.p)
        v = struct.unpack_from('<H', self.data, self.p)[0]; self.p += 2; return v

    def u32(self):
        if self.p + 4 > len(self.data):
            raise Fail('eof at 0x%x' % self.p)
        v = struct.unpack_from('<I', self.data, self.p)[0]; self.p += 4; return v

    def blob(self, n):
        if self.p + n > len(self.data):
            raise Fail('eof at 0x%x' % self.p)
        b = self.data[self.p:self.p + n]; self.p += n; return b

    def wide(self):
        n = self.u16()
        return self.blob(n * 2).decode('utf-16-le', errors='replace')

    def item(self):
        """FUN_00402100: u16 a; u16 b; u32 c; blob (FUN_00401580: u16 nbytes +
        nbytes raw — NOT the wide reader); u16 d."""
        return {'a': self.u16(), 'b': self.u16(), 'c': self.u32(),
                's': self.blob(self.u16()), 'd': self.u16()}

    def group(self):
        name = self.wide()
        n = self.u16()
        items = [self.item() for _ in range(n)]
        m = self.u16()
        vals = [self.u16() for _ in range(m)]
        return {'name': name, 'items': items, 'vals': vals}

    def variant(self):
        """FUN_00412530: typed value."""
        typ = self.u8()
        self.u8()                                # pad
        n = self.u16()
        if typ == 0:
            return {'type': typ, 'value': self.blob(n * 2).decode('utf-16-le',
                                                                 errors='replace')}
        if typ in (1, 2, 3):
            return {'type': typ, 'value': self.u32()}
        if typ in (4, 5):
            return {'type': typ, 'value': self.blob(n)}
        raise Fail('variant type %d at 0x%x' % (typ, self.p))

    def _tail_or_none(self):
        if self.p + 2 > len(self.data):
            return None
        return self.u16()


def _parse_container(path, expect_magic):
    data = open(path, 'rb').read()
    if len(data) < 10:
        raise Fail('file too short')
    magic = data[:4]
    if expect_magic is not None and magic != expect_magic:
        raise Fail('magic %r != %r' % (magic, expect_magic))
    version = struct.unpack_from('<H', data, 4)[0]
    count = struct.unpack_from('<I', data, 6)[0]
    return data, magic.decode('latin-1'), version, count


def _group(r):
    return r.group()


def parse_ssif(path, expect_magic=b'SSIF'):
    """Score.sci (or a same-record-class container, e.g. SPEECH.OTX)."""
    data, magic, version, count = _parse_container(path, expect_magic)
    r = _Reader(data, 10)

    def record(last):
        f0, f1 = r.u8(), r.u8()
        g0 = r.group()
        bl = r.blob(r.u16())
        g1 = r.group(); g2 = r.group(); g3 = r.group(); g4 = r.group()
        tail = r._tail_or_none() if last else r.u16()
        return {'f0': f0, 'f1': f1, 'g0': g0, 'blob': bl,
                'g1': g1, 'g2': g2, 'g3': g3, 'g4': g4, 'tail': tail}

    recs = [record(i == count - 1) for i in range(count)]
    return _info(magic, version, count, r), recs


def parse_scif(path):
    """CREATOR.CRI. Returns (info, records). Read FUN_004132F0: base group,
    blob, one group — no trailing u16, no extra groups."""
    data, magic, version, count = _parse_container(path, b'SCIF')
    r = _Reader(data, 10)

    def record():
        f0, f1 = r.u8(), r.u8()
        g0 = r.group()
        bl = r.blob(r.u16())
        g1 = r.group()
        return {'f0': f0, 'f1': f1, 'g0': g0, 'blob': bl, 'g1': g1}

    recs = [record() for _ in range(count)]
    return _info(magic, version, count, r), recs


def parse_shif(path):
    """SamIlPo.idx. Returns (info, nodes) — nodes in DFS order with their
    depth; the first node is the tree root."""
    data, magic, version, count = _parse_container(path, b'SHIF')
    r = _Reader(data, 10)

    def node():
        return {'flag': r.u16(), 'child_count': r.u16(),
                'group': r.group(),
                'variants': [r.variant() for _ in range(r.u16())]}

    root = node()
    nodes = [(root, 0)]
    st = {'n': 1, 'total': count}

    def walk(child_count, depth):
        idx = 0
        while idx < child_count:
            nd = node()
            st['n'] += 1
            nodes.append((nd, depth))
            if st['n'] >= st['total']:
                return
            walk(nd['child_count'], depth + 1)
            idx += 1

    walk(root['child_count'], 1)
    return _info(magic, version, count, r), nodes


def _info(magic, version, count, r):
    return {'magic': magic, 'version': version, 'count': count,
            'residual': len(r.data) - r.p}
