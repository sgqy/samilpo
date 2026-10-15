"""Dump + measure an .smc file for IR design decisions (work scratch).

Usage:
    python work/probe_smc.py <file.smc> <mode>

Modes:
    summary   file-level facts, per-staff/measure rhythm, voice histogram
    notes     per-measure timeline: every timed msg with start/dur and gaps
    ties      tie/slur endpoint resolution report
    keys      key assignment (note vs lyric) sanity check
    chords    chord symbol / fretboard / rhythm inventory
"""
import collections
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S

T_NAMES = {
    0x01: 'note', 0x03: 'rest', 0x04: 'text.doc', 0x05: 'metronome', 0x06: 'text',
    0x08: 'mark', 0x09: 'tie', 0x0A: 'slur', 0x0C: 'coda', 0x0D: 'rolled',
    0x10: 'pedal', 0x12: 'tuplet.meas', 0x13: 'cresc', 0x14: 'beam',
    0x15: 'keysig', 0x18: 'line', 0x19: 'lyric', 0x1B: 'dynamic', 0x1F: 'clef',
    0x21: 'trill', 0x25: 'chord', 0x26: 'ellipse', 0x27: 'rect', 0x2C: 'longrest',
    0x2E: 'slur.indep', 0x2F: 'breath', 0x30: 'grace', 0x3F: 'doc.3f',
    0x40: 'doc.40', 0x42: 'midi', 0x44: 'curve', 0x45: 'chord.sym', 0x46: 'fret',
    0x47: 'rhythm', 0x49: 'staffname',
}


def tname(t):
    return T_NAMES.get(t, '0x%02x' % t)


def play_time(msg, whole_tick):
    """docs/smc-format.md 6.2 CalcPlayTime for type in {0x01,0x03,0x25}."""
    exp = msg.type_index & 0x1F
    pt = (0x100 >> exp) * whole_tick >> 5
    dots = msg.dots & 0x07
    if dots == 1:
        pt += pt // 2
    elif dots == 2:
        pt += pt // 2 + pt // 4
    f2 = msg.f2
    hi, lo = (f2 >> 8) & 0xFF, f2 & 0xFF
    if hi and lo:
        pt = pt * hi // lo
    return pt


def walk_msgs(msgs):
    """Yield (msg, depth) recursively over embedded children."""
    for m in msgs:
        yield m, 0
        if m.children:
            for sub, d in walk_msgs([c['msg'] for c in m.children if c['msg']]):
                yield sub, d + 1


def all_measure_msgs(staff):
    """(measure_index, msg, depth) for every msg in a staff, incl. nested."""
    for mi, meas in enumerate(staff.meas):
        for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
            yield mi, m, d


def tick_per_meas(whole_tick, num, den):
    return whole_tick * num * 4 // den


# ------------------------------------------------------------------ summary

def cmd_summary(doc):
    sysm = doc.system
    print('file      : %s (%d bytes)' % (doc.path, doc.size))
    print('version   : 0x%04x   extra_str=%r' % (doc.version, doc.extra_str))
    print('title_raw : %r' % doc.title_raw)
    print('body      : @0x%x len=0x%x consumed=0x%x trailer=%d bytes' % (
        doc.body_off, doc.body_len, doc.body_consumed, len(doc.trailer)))
    print('pageCount : %d   doc_fields=%s   doc_msgs=%s' % (
        doc.doc_pages, doc.doc_fields, ['0x%02x' % m.type for m in doc.doc_msgs]))
    print('wholeTick : %d' % sysm.whole_tick)
    print('staves    : staff1=%d staff2=%d' % (sysm.n_staff1, sysm.n_staff2))
    print('fonts     : %s' % [(i, n) for i, n in doc.fonts])

    for gi, group in (('staff1', sysm.staff1), ('staff2', sysm.staff2)):
        for si, st in enumerate(group):
            print('\n%s[%d] name=%r clef_class=%d staff_index=%d n_meas=%d tail_54=0x%x' % (
                gi, si, st.name, st.clef_class, st.staff_index, st.n_meas, st.tail_54))
            types = collections.Counter()
            voices = collections.Counter()
            ts = collections.Counter()
            keysig = collections.Counter()
            for mi, m, d in all_measure_msgs(st):
                types[m.type] += 1
                voices[m.voice] += 1
            for meas in st.meas:
                ts[(meas.ts_num, meas.ts_den)] += 1
                keysig[(meas.keysig_type, meas.keysig_symbol, meas.keysig_count)] += 1
            print('  msg types : %s' % {tname(t): c for t, c in sorted(types.items())})
            print('  voices    : %s' % dict(sorted(voices.items())))
            print('  timesigs  : %s' % dict(ts))
            print('  keysig    : %s' % dict(keysig))
            # measure fill check
            bad = []
            for mi, meas in enumerate(st.meas):
                tpm = tick_per_meas(sysm.whole_tick, meas.ts_num, meas.ts_den)
                ends = []
                for voice in range(9):
                    notes = [m for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']])
                             if m.type in (0x01, 0x03) and m.voice == voice]
                    if not notes:
                        continue
                    # beam groups carry their own start; notes inside inherit
                    e = 0
                    for n in notes:
                        e = max(e, n.start + note_len(n, sysm.whole_tick))
                    ends.append(e)
                if ends and max(ends) != tpm:
                    bad.append((mi, meas.ts_num, meas.ts_den, tpm, max(ends)))
            print('  meas fill : %d/%d measures match tickPerMeas exactly' % (
                len(st.meas) - len(bad), len(st.meas)))
            for row in bad[:12]:
                print('     mismatch meas %d ts=%d/%d tpm=%d content_end=%d' % row)

    print('\npages     : %s' % [
        (i, p.n_a, p.n_b, p.n_msg) for i, p in enumerate(doc.pages)])


def note_len(msg, whole_tick):
    """Effective tick length used for fill checks: beam/chord sum their children."""
    if msg.type in (0x01, 0x03):
        pt = play_time(msg, whole_tick)
        return max(getattr(msg, 'duration', 0), pt)
    if msg.type in (0x14, 0x25):
        return max((note_len(c['msg'], whole_tick) for c in msg.children if c['msg']), default=0)
    return 0


# -------------------------------------------------------------------- notes

def cmd_notes(doc, limit=None):
    sysm = doc.system
    for gi, group in (('staff1', sysm.staff1), ('staff2', sysm.staff2)):
        for si, st in enumerate(group):
            for mi, meas in enumerate(st.meas):
                tpm = tick_per_meas(sysm.whole_tick, meas.ts_num, meas.ts_den)
                rows = []
                for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                    if m.type not in (0x01, 0x03):
                        continue
                    pt = play_time(m, sysm.whole_tick)
                    rows.append((m.voice, m.start, m.duration, pt, tname(m.type),
                                 getattr(m, 'midi_key', None), m.dots, m.type_index & 0x1F,
                                 m.flags, d))
                rows.sort(key=lambda r: (r[0], r[1], r[2]))
                if not rows:
                    continue
                print('--- %s[%d] meas %d  ts=%d/%d tpm=%d  (%d notes)' % (
                    gi, si, mi, meas.ts_num, meas.ts_den, tpm, len(rows)))
                for voice, start, dur, pt, tn, key, dots, exp, flags, d in rows:
                    mark = ''
                    if dur != pt:
                        mark = '  <== duration(%d) != playTime(%d)' % (dur, pt)
                    print('    v%d start=%-5d dur=%-5d pt=%-5d %-5s key=%-4s dots=%d exp=%-2d flags=0x%04x d%d%s' % (
                        voice, start, dur, pt, tn, key, dots, exp, flags, d, mark))
                if limit and mi >= limit:
                    return


# --------------------------------------------------------------------- ties

def cmd_ties(doc):
    sysm = doc.system
    by_key = {}
    for gi, group in (('staff1', sysm.staff1), ('staff2', sysm.staff2)):
        for si, st in enumerate(group):
            for mi, meas in enumerate(st.meas):
                for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                    by_key.setdefault(m.key, []).append((gi, si, mi, tname(m.type), m, d))
    print('distinct keys in measures: %d' % len(by_key))
    print('keys used more than once : %d' % sum(1 for v in by_key.values() if len(v) > 1))
    for t in (0x09, 0x0A, 0x12, 0x2E):
        items = [(gi, si, mi, m, d) for gi, group in (('s1', sysm.staff1), ('s2', sysm.staff2))
                 for si, st in enumerate(group) for mi, meas in enumerate(st.meas)
                 for m, dd in walk_msgs([c['msg'] for c in meas.children if c['msg']])
                 for d in [dd] if m.type == t]
        if not items:
            continue
        print('\n== type 0x%02x (%s): %d' % (t, tname(t), len(items)))
        miss = 0
        for gi, si, mi, m, d in items[:40]:
            a, b = m.endpoint, m.key
            ta = by_key.get(a)
            tb = by_key.get(b)
            if not ta or not tb:
                miss += 1
            print('  meas%-4d d%d key=%-6d ep=%-6d -> endA=%s endB=%s' % (
                mi, d, b, a,
                (ta[0][3] + '@m%d' % ta[0][2] if ta else 'MISSING'),
                (tb[0][3] + '@m%d' % tb[0][2] if tb else 'MISSING')))
        print('  (unresolved endpoints in shown sample: %d/%d)' % (miss, min(40, len(items))))


def cmd_keys(doc):
    sysm = doc.system
    pairs = collections.Counter()
    for gi, group in (('s1', sysm.staff1), ('s2', sysm.staff2)):
        for st in group:
            for meas in st.meas:
                for c in meas.children:
                    if not c['msg']:
                        continue
                    m = c['msg']
                    if m.type == 0x01:
                        lk = [x['msg'].key for x in m.children if x['msg'] and x['msg'].type == 0x19]
                        if lk:
                            pairs[lk[0] - m.key] += 1
                        else:
                            pairs['none'] += 1
    print('lyric_key - note_key : %s' % dict(pairs))


def cmd_chords(doc):
    sysm = doc.system
    names = collections.Counter()
    frets = collections.Counter()
    n45 = n46 = n47 = 0
    headlens = collections.Counter()
    for gi, group in (('s1', sysm.staff1), ('s2', sysm.staff2)):
        for st in group:
            for mi, meas in enumerate(st.meas):
                for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                    if m.type == 0x45:
                        n45 += 1
                        headlens[m.head_len] += 1
                        ce = m.chord_extra
                        names[ce.name] += 1
                        if ce.fret_msg is not None:
                            n46 += 1
                            fi = ce.fret_info
                            frets[(struct_u16(fi, 0), tuple(fi[2:8]), tuple(fi[8:16]))] += 1
                        if ce.has_rhythm:
                            n47 += 1
    import struct as _s
    print('chord symbols(0x45)=%d  fretboards(0x46)=%d  rhythms(0x47)=%d' % (n45, n46, n47))
    print('0x45 headLen: %s' % dict(headlens))
    print('surfix names: %s' % dict(names))
    print('fret variants: %d distinct; sample:' % len(frets))
    for k, v in list(frets.items())[:10]:
        print('   base=%d strings=%s pairs=%s x%d' % (k[0], k[1], k[2], v))


def struct_u16(b, off):
    import struct as _s
    return _s.unpack_from('<H', b, off)[0]


if __name__ == '__main__':
    mode = sys.argv[2] if len(sys.argv) > 2 else 'summary'
    doc = S.load(sys.argv[1])
    {'summary': cmd_summary, 'notes': cmd_notes, 'ties': cmd_ties,
     'keys': cmd_keys, 'chords': cmd_chords}[mode](doc)
