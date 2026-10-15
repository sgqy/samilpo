"""Focused dumps for IR design questions (work scratch).

Usage:
    python work/probe2.py <file.smc> <mode> [arg]

Modes:
    tree <measIdx>   full nested dump of one measure (staff1[0]) with parents
    depth            parent-type histogram for notes/rests/ties/slurs
    long             every note whose duration != playTime, with context
    conv             layout-relevant conventions: measure 0 pickup, part-spanning
    lyricmap         lyric<->note<->measure mapping incl. text
    endpts           all tie/slur/measTuplet endpoint pairs resolved globally
"""
import collections
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import tname, play_time, walk_msgs, tick_per_meas


def staffs(doc):
    out = []
    for gi, group in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
        for si, st in enumerate(group):
            out.append((gi, si, st))
    return out


def msg_of(c):
    return c['msg'] if c else None


def dump_msg(m, depth, doc, cod=None):
    ind = '  ' * depth
    extra = ''
    if m.type == 0x01:
        extra = ' key=%d vel=%d dur=%d exp=%d dots=%d htype=%d flags=0x%04x start=%d dx=%d dy=%d voice=%d' % (
            m.head[0], m.head[1], m.duration, m.type_index & 0x1F, m.dots,
            m.head_type, m.flags, m.start, m.dx, m.dy, m.voice)
    elif m.type == 0x19:
        txt = S.decode(m.lyric_bytes, cod) if cod else repr(m.lyric_bytes)
        extra = ' text=%r font=%d size=%d style=%d color=0x%06x' % (
            txt, m.lyric_font, m.lyric_size, m.lyric_style, m.lyric_color)
    elif m.type == 0x06:
        extra = ' head=%s' % m.head.hex(' ')
    elif m.type == 0x45:
        extra = ' surfix=%r' % (m.chord_extra.name,)
    elif m.type in (0x09, 0x0A, 0x12):
        extra = ' ep=%d (hdr+0x20)' % m.endpoint
    elif m.type == 0x14:
        extra = ' toilthick=%d playTime=%d' % (m.type_index, play_time(m, 240))
    elif m.type == 0x1F:
        extra = ' clefcode=%d' % m.type_index
    elif m.type == 0x1B:
        extra = ' dyncode=%d' % m.type_index
    print('%s0x%02x %-9s key=%-6d elen=%d head=%d%s' % (
        ind, m.type, tname(m.type), m.key, len(m.children), m.head_len, extra))
    for c in m.children:
        if c['msg']:
            print('%s  (role=%d)' % (ind, c['role']))
            dump_msg(c['msg'], depth + 2, doc, cod)


def cmd_tree(doc, idx):
    cod = S.load_cod()
    gi, si, st = staffs(doc)[0]
    meas = st.meas[int(idx)]
    tpm = tick_per_meas(doc.system.whole_tick, meas.ts_num, meas.ts_den)
    print('meas %s ts=%d/%d tpm=%d nchild=%d refs_only=%d head=%d' % (
        idx, meas.ts_num, meas.ts_den, tpm, meas.child_count, meas.refs_only, meas.head_len))
    for c in meas.children:
        print(' (role=%d key=%d)' % (c['role'], c['key']))
        dump_msg(c['msg'], 1, doc, cod)


def cmd_depth(doc):
    hist = collections.Counter()
    for gi, si, st in staffs(doc):
        for meas in st.meas:
            def rec(m, parent_type, d):
                if m.type in (0x01, 0x03, 0x09, 0x0A, 0x12, 0x19, 0x45, 0x46, 0x47):
                    hist[(tname(m.type), tname(parent_type) if parent_type else 'MEAS', d)] += 1
                for c in m.children:
                    if c['msg']:
                        rec(c['msg'], m.type, d + 1)
            for c in meas.children:
                if c['msg']:
                    rec(c['msg'], None, 0)
    for k, v in sorted(hist.items(), key=lambda kv: (kv[0][0], kv[0][2])):
        print('%-10s parent=%-10s depth=%d  x%d' % (k[0], k[1], k[2], v))


def cmd_long(doc):
    wt = doc.system.whole_tick
    for gi, si, st in staffs(doc):
        for mi, meas in enumerate(st.meas):
            for c in meas.children:
                if not c['msg']:
                    continue
                m = c['msg']
                if m.type == 0x01 and m.duration != play_time(m, wt):
                    print('meas%-4d key=%-6d dur=%-5d pt=%-5d exp=%d dots=%d flags=0x%04x start=%d parent=0x%02x' % (
                        mi, m.key, m.duration, play_time(m, wt), m.type_index & 0x1F,
                        m.dots, m.flags, m.start, m.type))
                    for cc in m.children:
                        print('        child role=%d key=%d type=%s' % (
                            cc['role'], cc['key'], tname(cc['msg'].type) if cc['msg'] else '-'))


def cmd_conv(doc):
    wt = doc.system.whole_tick
    gi, si, st = staffs(doc)[0]
    print('n_meas=%d wholeTick=%d' % (len(st.meas), wt))
    for mi, meas in enumerate(st.meas):
        tpm = tick_per_meas(wt, meas.ts_num, meas.ts_den)
        notes = [m for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']])
                 if m.type in (0x01, 0x03)]
        if not notes:
            print('meas%-4d EMPTY ts=%d/%d' % (mi, meas.ts_num, meas.ts_den))
            continue
        starts = sorted(set(n.start for n in notes))
        first = starts[0]
        ends = max(n.start + max(getattr(n, 'duration', 0), play_time(n, wt)) for n in notes)
        if first != 0 or ends != tpm:
            print('meas%-4d ts=%d/%d tpm=%-5d firstStart=%-4d contentEnd=%-5d n=%d' % (
                mi, meas.ts_num, meas.ts_den, tpm, first, ends, len(notes)))


def cmd_lyricmap(doc):
    cod = S.load_cod()
    sysm = doc.system
    rows = []
    for gi, si, st in staffs(doc):
        for mi, meas in enumerate(st.meas):
            for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                if m.type == 0x19:
                    rows.append((mi, m.key, S.decode(m.lyric_bytes, cod)))
    print('lyric records: %d over %d measures' % (len(rows), len(set(r[0] for r in rows))))
    print(''.join(r[2] for r in rows))
    print()
    for r in rows[:80]:
        print('  m%-4d key=%-6d %r' % r)


def cmd_endpts(doc):
    by_key = {}
    for gi, si, st in staffs(doc):
        for mi, meas in enumerate(st.meas):
            for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                by_key[m.key] = (gi, si, mi, m)
    for t in (0x09, 0x0A, 0x12):
        n = same = diff = dead = 0
        for gi, si, st in staffs(doc):
            for mi, meas in enumerate(st.meas):
                for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                    if m.type != t:
                        continue
                    n += 1
                    a, b = by_key.get(m.endpoint), by_key.get(m.key)
                    if not a or not b:
                        dead += 1
                    elif a[2] == b[2]:
                        same += 1
                    else:
                        diff += 1
        print('0x%02x %-6s total=%-4d same-measure=%-4d cross-measure=%-4d unresolved=%d' % (
            t, tname(t), n, same, diff, dead))


if __name__ == '__main__':
    doc = S.load(sys.argv[1])
    mode = sys.argv[2]
    arg = sys.argv[3] if len(sys.argv) > 3 else None
    fn = {'tree': cmd_tree, 'depth': cmd_depth, 'long': cmd_long, 'conv': cmd_conv,
          'lyricmap': cmd_lyricmap, 'endpts': cmd_endpts}[mode]
    fn(doc, arg) if mode == 'tree' else fn(doc)
