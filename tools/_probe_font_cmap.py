"""Phase-3 probe: minimal TrueType cmap reader (no third-party deps).

Answers the phase-2 open question: do the 889F-code codepoints that the
table leaves unmapped correspond to real glyphs in the bundled Wk*.ttf
fonts (private-use or symbol glyphs), or to nothing?

Also reports which fonts the app references (from the SMC font table) and
whether each has a cmap entry for the 889F code space.

Usage: python _probe_font_cmap.py
"""
import struct, os, sys

FONTDIR = r'C:\Program Files (x86)\Samilpo 2.0\Font'
CODDIR = r'C:\Program Files (x86)\Samilpo 2.0'

# 889F forward-table codepoints used by the corpus (sampled ranges from docs/encoding.md)
PROBE_CODES = [0x8a7d, 0x9660, 0x8cda, 0x9299, 0x8eae, 0x965b, 0x8a4c, 0x889f,
               0xf041, 0xf040, 0xf300, 0xe0a1, 0x9f9f, 0x8800]


def read_cmap_lookup(path):
    b = open(path, 'rb').read()
    if b[:4] not in (b'\x00\x01\x00\x00', b'true', b'ttcf'):
        return None
    numTables = struct.unpack_from('>H', b, 4)[0]
    cmap_off = None
    for i in range(numTables):
        o = 12 + i * 16
        tag = b[o:o + 4]
        off = struct.unpack_from('>I', b, o + 8)[0]
        if tag == b'cmap':
            cmap_off = off
    if cmap_off is None:
        return None
    n = struct.unpack_from('>H', b, cmap_off + 2)[0]
    best = None
    for i in range(n):
        o = cmap_off + 4 + i * 8
        pid, eid, sub = struct.unpack_from('>HHI', b, o)
        # prefer (3,1) BMP, then (3,10), then (3,0) symbol, then (0,x)
        rank = {(3, 1): 0, (3, 10): 1, (3, 0): 2}.get((pid, eid), 3)
        if best is None or rank < best[0]:
            best = (rank, sub, pid, eid)
    if best is None:
        return None
    rank, sub, pid, eid = best
    so = cmap_off + sub
    fmt = struct.unpack_from('>H', b, so)[0]
    if fmt not in (4, 12, 6, 0):
        return {'format': fmt, 'pid': pid, 'eid': eid, 'lookup': lambda c: None}
    if fmt == 4:
        segX2 = struct.unpack_from('>H', b, so + 6)[0]
        seg = segX2 // 2
        ends = struct.unpack_from('>%dH' % seg, b, so + 14)
        starts = struct.unpack_from('>%dH' % seg, b, so + 16 + segX2)
        deltas = struct.unpack_from('>%dh' % seg, b, so + 16 + segX2 * 2)
        rangeOffBase = so + 16 + segX2 * 3
        rangeOffs = struct.unpack_from('>%dH' % seg, b, rangeOffBase)

        def lookup4(c):
            if c > 0xFFFF:
                return 0
            for i in range(seg):
                if starts[i] <= c <= ends[i]:
                    if rangeOffs[i] == 0:
                        return (c + deltas[i]) & 0xFFFF
                    gi = rangeOffBase + i * 2 + rangeOffs[i] + (c - starts[i]) * 2
                    g = struct.unpack_from('>H', b, gi)[0]
                    return 0 if g == 0 else (g + deltas[i]) & 0xFFFF
            return 0
        return {'format': 4, 'pid': pid, 'eid': eid, 'segments': seg, 'lookup': lookup4}
    # format 12
    ngroups = struct.unpack_from('>I', b, so + 12)[0]
    groups = [struct.unpack_from('>III', b, so + 16 + i * 12) for i in range(ngroups)]

    def lookup12(c):
        for s, e, g in groups:
            if s <= c <= e:
                return g + (c - s)
        return 0
    return {'format': 12, 'pid': pid, 'eid': eid, 'ngroups': ngroups, 'lookup': lookup12}


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
    print('== fonts in install dir ==')
    for f in sorted(os.listdir(FONTDIR)):
        if f.lower().endswith(('.ttf', '.ttc')):
            full = os.path.join(FONTDIR, f)
            info = read_cmap_lookup(full)
            if info is None:
                print('%-16s no cmap' % f)
            else:
                print('%-16s cmap fmt=%d (pid=%d,eid=%d) %s' % (
                    f, info['format'], info['pid'], info['eid'],
                    'segments=%d' % info['segments'] if 'segments' in info else
                    'groups=%d' % info['ngroups'] if 'ngroups' in info else ''))
    print()
    print('== 889F codepoints vs font cmaps ==')
    fwd = parse_cod(os.path.join(CODDIR, '889F.cod')) if os.path.exists(os.path.join(CODDIR, '889F.cod')) else {}
    print('889F forward mapped entries:', len(fwd))
    for name in sorted(os.listdir(FONTDIR)):
        if not name.lower().endswith(('.ttf', '.ttc')):
            continue
        info = read_cmap_lookup(os.path.join(FONTDIR, name))
        if info is None:
            continue
        hits, misses = [], []
        for c in PROBE_CODES:
            u = fwd.get(c)
            target = u if u is not None else c
            g = info['lookup'](target)
            (hits if g else misses).append((hex(c), hex(target), g))
        print('%-16s hits=%d misses=%d' % (name, len(hits), len(misses)))
        if misses:
            print('    miss:', misses[:6])
    # Statistics: how many 889F-mapped codepoints resolve to a glyph in wkgothic.ttf
    print()
    for name in ('wkgothic.ttf', 'WKLGM.TTF', 'KAYAKUMA.TTF'):
        p = os.path.join(FONTDIR, name)
        if not os.path.exists(p):
            continue
        info = read_cmap_lookup(p)
        if info is None:
            continue
        tot = hit = 0
        for c, u in fwd.items():
            tot += 1
            if info['lookup'](u):
                hit += 1
        print('%s: %d/%d 889F->Unicode codepoints have a glyph (%.1f%%)' %
              (name, hit, tot, 100.0 * hit / max(tot, 1)))


if __name__ == '__main__':
    main()
