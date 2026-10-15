"""SMC reader (work scratch) -- spec-faithful, read-only.

Implements docs/smc-format.md framing and yields a Python object tree.
Deliberately duplicates tools/smc_walk.py logic but *keeps* every field the IR
step needs (MsgHdr fields, head bytes, children with role, tails) instead of
only validating the byte layout.

Not a deliverable: this is converter scaffolding under work/.
"""
import struct
from types import SimpleNamespace

INSTALL = r'C:\Program Files (x86)\Samilpo 2.0'
DEFAULT_COD = INSTALL + r'\889F.cod'


class Fail(Exception):
    pass


class Reader:
    def __init__(self, b, base=0):
        self.b, self.p, self.base = b, 0, base

    def take(self, n):
        if n < 0:
            raise Fail('negative take %d at +0x%x' % (n, self.p))
        if self.p + n > len(self.b):
            raise Fail('overrun at +0x%x need %d have %d' % (self.p, n, len(self.b) - self.p))
        s = self.b[self.p:self.p + n]
        self.p += n
        return s

    def u8(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack('<H', self.take(2))[0]

    def i16(self):
        return struct.unpack('<h', self.take(2))[0]

    def u32(self):
        return struct.unpack('<I', self.take(4))[0]

    def i32(self):
        return struct.unpack('<i', self.take(4))[0]

    def cstr(self):
        n = self.i16()
        if n < 0:
            n = 0
        return self.take(n)


# ---------------------------------------------------------------- document

class Doc:
    pass


def load(path):
    """Parse an .smc file into a Doc. Raises Fail on structural trouble."""
    data = open(path, 'rb').read()
    d = Doc()
    d.path = path
    d.size = len(data)
    d.hdr_len = struct.unpack_from('<I', data, 0)[0]
    if d.hdr_len != 0x58C:
        raise Fail('hdrLen=0x%x (legacy path not modelled)' % d.hdr_len)
    # SYMP block base = 0x004, so its internal +0x00/+0x04/+0x08/+0x0A land here.
    d.symp_self_len = struct.unpack_from('<I', data, 0x004)[0]
    d.magic = data[0x008:0x00C]
    d.version = struct.unpack_from('<h', data, 0x00C)[0]
    d.title_raw = data[0x00E:0x004 + 0x58C].split(b'\0')[0]
    if d.symp_self_len != 0x58C:
        raise Fail('SYMP self length 0x%x' % d.symp_self_len)
    if d.magic != b'SYMP':
        raise Fail('SYMP magic %r' % d.magic)
    p = 4 + 0x58C
    sl = struct.unpack_from('<h', data, p)[0]
    p += 2
    d.extra_str = b''
    if sl > 1:
        d.extra_str = data[p:p + sl]
        p += sl
    smc = data[p:p + 0x318]
    if smc[:4] != b'SMC\0':
        raise Fail('SMC magic %r' % smc[:4])
    d.font_buf_len = struct.unpack_from('<I', smc, 0x314)[0]
    p += 0x318
    d.font_buf = data[p:p + d.font_buf_len]
    d.fonts = parse_font_table(d.font_buf)
    p += d.font_buf_len
    ctl_len = struct.unpack_from('<h', data, p)[0]
    d.ctl_len = ctl_len
    d.ctl = data[p + 2:p + 2 + ctl_len]
    p += 2 + ctl_len
    d.file_info = struct.unpack_from('<12h2I', data, p)
    p += 0x20
    body_len = struct.unpack_from('<I', data, p)[0]
    p += 4
    d.body_len = body_len
    if p + body_len > len(data):
        raise Fail('body 0x%x exceeds file' % body_len)
    d.body_off = p
    d.trailer = data[p + body_len:]
    r = Reader(data[p:p + body_len])
    d.system = read_system(r)
    d.doc_pages = r.i16()
    d.doc_fields = (r.i16(), r.i16(), r.i16(), r.i16())
    d.doc_msgs = [read_msg(r, 0) for _ in range(3)]
    d.pages = [read_page(r, 0) for _ in range(d.doc_pages)]
    d.body_consumed = r.p
    return d


def parse_font_table(buf):
    """FontRecord := u8 index, u8 nameLen, name[nameLen]."""
    out, p = [], 0
    while p + 2 <= len(buf):
        idx, n = buf[p], buf[p + 1]
        if p + 2 + n > len(buf):
            break
        out.append((idx, buf[p + 2:p + 2 + n]))
        p += 2 + n
    return out


# ------------------------------------------------------------------ objects

class Msg:
    def __repr__(self):
        return '<Msg t=0x%02x key=%d v=%d start=%d ch=%d>' % (
            self.type, self.key, self.voice, self.start, len(self.children))


def read_object_core(r, obj):
    h = r.take(12)
    obj.child_count = h[0]
    obj.reserved_byte = h[1]
    obj.f2 = struct.unpack_from('<H', h, 2)[0]
    obj.head_len = struct.unpack_from('<h', h, 4)[0]
    obj.derived = struct.unpack_from('<H', h, 6)[0]
    obj.f8 = struct.unpack_from('<I', h, 8)[0]
    obj.head = r.take(max(obj.head_len, 0))
    obj.children = []
    for _ in range(obj.child_count):
        c = r.take(8)
        key, role = struct.unpack_from('<I', c, 0)[0], c[4]
        child = {'key': key, 'role': role, 'pad': c[5:8]}
        if role:
            child['msg'] = read_msg(r, 0)
            obj.children.append(child)
        else:
            child['msg'] = None
            obj.refs_only = getattr(obj, 'refs_only', 0) + 1
            # Meas drops role==0 refs; other containers keep the descriptor
            if obj.kind != 'meas':
                obj.children.append(child)
    return obj


def _msg_from_hdr(r, hdr):
    m = Msg()
    m.hdr = hdr
    m.type = hdr[0]
    m.bracket = (hdr[0x01] >> 4) & 0xF
    m.voice = hdr[0x01] & 0xF
    m.scale = hdr[0x02]
    m.f03 = hdr[0x03]
    m.f04 = hdr[0x04]
    m.stem_flag = (hdr[0x05] >> 4) & 0xF
    m.dots = hdr[0x05] & 0xF
    m.head_type = struct.unpack_from('<h', hdr, 0x06)[0]
    m.type_index = struct.unpack_from('<h', hdr, 0x08)[0]
    m.flags = struct.unpack_from('<h', hdr, 0x0A)[0]
    m.cache_rect = struct.unpack_from('<4h', hdr, 0x0C)
    m.start = struct.unpack_from('<h', hdr, 0x14)[0]
    m.dx = struct.unpack_from('<h', hdr, 0x16)[0]
    m.dy = struct.unpack_from('<h', hdr, 0x18)[0]
    m.rect_l = struct.unpack_from('<h', hdr, 0x1A)[0]
    m.rect_r = struct.unpack_from('<h', hdr, 0x1C)[0]
    m.endpoint = struct.unpack_from('<I', hdr, 0x20)[0]
    m.key = struct.unpack_from('<I', hdr, 0x24)[0]
    m.style = struct.unpack_from('<I', hdr, 0x28)[0]
    return m


def read_msg(r, depth):
    off = r.p
    hdr = r.take(0x2C)
    m = _msg_from_hdr(r, hdr)
    m.off = off
    m.kind = 'msg'
    read_object_core(r, m)
    if m.head_len != len(m.head):
        m.head_len_declared = m.head_len
    if m.type == 0x01 and len(m.head) != 12:
        m.head = (m.head + b'\0' * 12)[:12]
    if m.type == 0x45:
        m.chord_extra = read_chord_extra(r, depth)
    else:
        m.chord_extra = None
    # message-level attributes derived from head / hdr
    if m.type == 0x01 and len(m.head) >= 12:
        m.midi_key = m.head[0]
        m.velocity = m.head[1]
        m.head_reserved = m.head[2]
        m.head_voice = m.head[3]
        m.duration = struct.unpack_from('<I', m.head, 4)[0]
        m.head_start = struct.unpack_from('<I', m.head, 8)[0]
    elif m.type == 0x19:
        m.lyric_head_short = len(m.head) < 0x10
        m.lyric_font = struct.unpack_from('<H', m.head, 0)[0] if len(m.head) >= 2 else 0
        m.lyric_style = m.head[2] if len(m.head) >= 3 else 0
        m.lyric_size = struct.unpack_from('<H', m.head, 4)[0] if len(m.head) >= 6 else 0
        m.lyric_color = struct.unpack_from('<I', m.head, 8)[0] if len(m.head) >= 12 else 0
        n = m.head[0x0C] if len(m.head) >= 0x0D else 0
        m.lyric_bytes = m.head[0x10:0x10 + n]
    return m


def read_chord_extra(r, depth):
    ce = SimpleNamespace()
    ce.name = r.cstr()                       # CChordSurfix::ReadFromMem 0x10008b40
    n = r.u8()
    ce.info = r.take(n)
    ce.fret_msg = read_msg(r, depth)          # CFretBoard 蜀・ｵ・Msg (type 0x46)
    ce.fret_info = r.take(16)                 # CFretInfo::ReadFromMem 0x1002dc70
    ce.has_rhythm = r.i16()
    ce.rhythm = None
    if ce.has_rhythm:
        ce.rhythm = read_rhythm(r, depth)
    return ce


def read_rhythm(r, depth):
    ry = SimpleNamespace()
    ry.msg = read_msg(r, depth)
    ry.s1, ry.s2, ry.s3 = r.cstr(), r.cstr(), r.cstr()
    ry.rtm = read_rtmdata(r)
    return ry


def read_rtmdata(r):
    d = SimpleNamespace()
    start = r.p
    d.total_size = r.u32()
    d.stride = r.u16()
    d.a = r.u16()
    d.b = r.u16()
    d.event_count = r.u32()
    d.event_size = r.u16()
    d.events = r.take(d.event_count * d.event_size)
    d.count2 = r.u16()
    d.size2 = r.u16()
    d.seg2 = r.take(d.count2 * d.size2)
    d.consumed = r.p - start
    return d


# ------------------------------------------------------------- containers

def read_meas(r, depth):
    m = Msg()  # reuse shape: containers carry the same header tail
    m.kind = 'meas'
    h = r.take(12)
    m.child_count = h[0]
    m.reserved_byte = h[1]
    m.f2 = struct.unpack_from('<H', h, 2)[0]
    m.head_len = struct.unpack_from('<h', h, 4)[0]
    m.derived = struct.unpack_from('<H', h, 6)[0]
    m.f8 = struct.unpack_from('<I', h, 8)[0]
    m.head = r.take(max(m.head_len, 0))
    m.children = []
    m.refs_only = 0
    for _ in range(m.child_count):
        c = r.take(8)
        key, role = struct.unpack_from('<I', c, 0)[0], c[4]
        if role:
            m.children.append({'key': key, 'role': role, 'pad': c[5:8], 'msg': read_msg(r, depth + 1)})
        else:
            m.refs_only += 1      # CSMMeas::Read drops these
    m.tail_raw = r.take(0x60)
    t = m.tail_raw
    m.meas_mode = t[0x00]
    m.timesig_text = t[0x13:0x13 + 0x10].split(b'\0')[0]
    m.text2 = t[0x33:0x33 + 0x10].split(b'\0')[0]
    m.keysig_type = t[0x46]
    m.keysig_flags_raw = t[0x48]
    m.tail_52 = struct.unpack_from('<h', t, 0x52)[0]
    m.ts_num = struct.unpack_from('<h', t, 0x56)[0]
    m.ts_den = struct.unpack_from('<h', t, 0x58)[0]
    m.keysig_symbol = t[0x5A]
    m.keysig_count = t[0x5C]
    m.tail_5e = struct.unpack_from('<H', t, 0x5E)[0]
    if m.ts_num == 0 or m.ts_den == 0:
        m.ts_num, m.ts_den = 4, 4
    m.kind = 'meas'
    return m


def read_staff(r, depth):
    s = Msg()
    s.kind = 'staff'
    h = r.take(12)
    s.child_count = h[0]
    s.reserved_byte = h[1]
    s.f2 = struct.unpack_from('<H', h, 2)[0]
    s.head_len = struct.unpack_from('<h', h, 4)[0]
    s.derived = struct.unpack_from('<H', h, 6)[0]
    s.f8 = struct.unpack_from('<I', h, 8)[0]
    s.head = r.take(max(s.head_len, 0))
    s.children = []
    for _ in range(s.child_count):
        c = r.take(8)
        key, role = struct.unpack_from('<I', c, 0)[0], c[4]
        if role:
            s.children.append({'key': key, 'role': role, 'pad': c[5:8], 'msg': read_msg(r, depth + 1)})
    t = r.take(0x70)
    s.tail_raw = t
    s.name = t[0x00:0x20].split(b'\0')[0]
    s.staff_index = t[0x20]
    s.clef_class = t[0x21]
    s.staff_flags = t[0x22]
    s.keysig_a = t[0x23:0x2B]
    s.keysig_b = t[0x33:0x3B]
    s.keysig_c = t[0x3B:0x43]
    s.keysig_d = t[0x43:0x4B]
    s.tail_4b = t[0x4B]
    s.tail_4c = t[0x4C:0x4F]
    s.tail_54 = struct.unpack_from('<H', t, 0x54)[0]
    s.n_meas = struct.unpack_from('<i', t, 0x6C)[0]
    s.meas = [read_meas(r, depth + 1) for _ in range(s.n_meas)]
    return s


def read_system(r):
    s = Msg()
    s.kind = 'system'
    h = r.take(12)
    s.child_count = h[0]
    s.reserved_byte = h[1]
    s.f2 = struct.unpack_from('<H', h, 2)[0]
    s.head_len = struct.unpack_from('<h', h, 4)[0]
    s.derived = struct.unpack_from('<H', h, 6)[0]
    s.f8 = struct.unpack_from('<I', h, 8)[0]
    s.head = r.take(max(s.head_len, 0))
    s.children = []
    for _ in range(s.child_count):
        c = r.take(8)
        key, role = struct.unpack_from('<I', c, 0)[0], c[4]
        if role:
            s.children.append({'key': key, 'role': role, 'pad': c[5:8], 'msg': read_msg(r, 2)})
    s.n_staff1 = r.i16()
    s.n_staff2 = r.i16()
    s.whole_tick = r.u32()
    s.staff1 = [read_staff(r, 1) for _ in range(s.n_staff1)]
    s.staff2 = [read_staff(r, 2) for _ in range(s.n_staff2)]
    return s


def read_block(r):
    b = SimpleNamespace()
    h = r.take(0x1C)
    b.type = h[0]
    b.n_staves = h[1]
    b.f2 = struct.unpack_from('<h', h, 2)[0]
    b.start_meas = struct.unpack_from('<h', h, 4)[0]
    b.n_pts = h[8]
    b.rect = struct.unpack_from('<4i', h, 0x0C)
    b.staff_refs = []
    for _ in range(b.n_staves):
        t = r.take(5)
        b.staff_refs.append((t[0], struct.unpack_from('<H', t, 1)[0], struct.unpack_from('<H', t, 3)[0]))
    b.meas_x = list(struct.unpack_from('<%dH' % (b.f2 + 1), r.take(2 * (b.f2 + 1))))
    b.points = [struct.unpack('<2i', r.take(8)) for _ in range(b.n_pts)]
    return b


def read_page(r, depth):
    p = SimpleNamespace()
    h = r.take(0x18)
    p.n_a, p.n_b, p.n_msg = struct.unpack_from('<3h', h, 0)
    p.rect = struct.unpack_from('<4i', h, 8)
    p.blocks_a = [read_block(r) for _ in range(p.n_a)]
    p.blocks_b = [read_block(r) for _ in range(p.n_b)]
    p.msgs = [read_msg(r, depth + 1) for _ in range(p.n_msg)]
    return p


# ------------------------------------------------------------------- text

class CodeTable:
    def __init__(self, n, lo, hi, starts, ends, data):
        self.n, self.lo, self.hi = n, lo, hi
        self.starts, self.ends, self.data = starts, ends, data
        self.stride = hi - lo + 1

    def lookup(self, code):
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


def load_cod(path=DEFAULT_COD):
    b = open(path, 'rb').read()
    t, _ = _read_cod_table(b, 0)
    return t


def decode(data, table):
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
