"""Samilpo index files (IndexFiles/*.*) — record parser.

Container (evidence: MusicBook.exe FUN_00414AA0 dispatch + FUN_004168E0/004165E0
loaders; 2026-11-07):

    char  magic[4]        'SSIF' Score.sci / 'SCIF' CREATOR.CRI / 'SOTF' SPEECH.OTX
    u16   version         0x0200
    u32   count
    count x record

record (virtual Read FUN_00413030, object size 0x1B8):

    u8  f0; u8 f1                       (observed 0,0)
    group g0                            (FUN_00412C30 -> FUN_004052D0)
    blob  u16 nbytes; nbytes raw        (FUN_00401580; SSIF: 0x01 0x00 + ASCII path)
    group g1; group g2; group g3; group g4
    u16   tail                          (SSIF: song year, 0xFFFF unknown; the last
                                         SCIF record omits it)

group (FUN_004052D0):

    wstr  name                          (FUN_00401B70: u16 nchars + nchars*2 UTF-16LE)
    u16   n; n x item                   (FUN_00402100)
    u16   m; m x u16

item (FUN_00402100): u16 a; u16 b; u32 c; wstr s; u16 d

Known semantics (Score.sci, 8449 records, exact file consumption): g0.name =
song title, g1.name = lyricist (작사), g2.name = composer (작곡), tail = year
(0xFFFF unknown), blob = 0x01 0x00 + relative path of the .smc.
SamIlPo.idx (SHIF, loader FUN_00411210) uses a different record layout — not
yet derived (see project/research-state.md).
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
        return {'a': self.u16(), 'b': self.u16(), 'c': self.u32(),
                's': self.wide(), 'd': self.u16()}

    def group(self):
        name = self.wide()
        n = self.u16()
        items = [self.item() for _ in range(n)]
        m = self.u16()
        vals = [self.u16() for _ in range(m)]
        return {'name': name, 'items': items, 'vals': vals}

    def tail_or_none(self):
        if self.p + 2 > len(self.data):
            return None
        return self.u16()

    def record(self, last=False):
        f0, f1 = self.u8(), self.u8()
        g0 = self.group()
        bl = self.blob(self.u16())
        g1 = self.group(); g2 = self.group(); g3 = self.group(); g4 = self.group()
        tail = self.u16() if not last else self.tail_or_none()
        return {'f0': f0, 'f1': f1, 'g0': g0, 'blob': bl,
                'g1': g1, 'g2': g2, 'g3': g3, 'g4': g4, 'tail': tail}

    def try_record(self):
        """Best-effort record for a possibly truncated last entry: every field
        becomes None once the file runs out. Returns (rec, complete)."""
        rec = {'f0': None, 'f1': None, 'g0': None, 'blob': None,
               'g1': None, 'g2': None, 'g3': None, 'g4': None, 'tail': None}
        try:
            rec['f0'], rec['f1'] = self.u8(), self.u8()
            rec['g0'] = self.group()
            rec['blob'] = self.blob(self.u16())
            rec['g1'] = self.group(); rec['g2'] = self.group()
            rec['g3'] = self.group(); rec['g4'] = self.group()
            rec['tail'] = self.tail_or_none()
            return rec, True
        except Fail:
            return rec, False


def parse(path, expect_magic=None):
    """Parse one index file. Returns (info, records); info carries magic,
    version, count and the residual byte count (0 = exact consumption)."""
    data = open(path, 'rb').read()
    if len(data) < 10:
        raise Fail('file too short')
    magic = data[:4]
    if expect_magic is not None and magic != expect_magic:
        raise Fail('magic %r != %r' % (magic, expect_magic))
    version = struct.unpack_from('<H', data, 4)[0]
    count = struct.unpack_from('<I', data, 6)[0]

    r = _Reader(data, 10)
    recs = []
    for i in range(count):
        last = i == count - 1
        try:
            if last:
                rec, complete = r.try_record()
                rec['truncated'] = not complete
            else:
                rec = r.record()
                rec['truncated'] = False
        except Fail as e:
            raise Fail('record %d at 0x%x: %s' % (i, r.p, e)) from None
        recs.append(rec)
    return {'magic': magic.decode('latin-1'), 'version': version,
            'count': count, 'residual': len(data) - r.p}, recs
