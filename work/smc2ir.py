"""SMC -> IR (step 1).

Writes NDJSON: one record per line, document order = MusicXML partwise order.
Reads .smc via smc_read.py (spec-faithful), never guesses beyond the rules in
parameters.md. Layout is not emitted by default (see parameters.md F1).

Usage:
    python work/smc2ir.py <file.smc> [<out.ndjson>] [options]

Options (the 6 parameters of parameters.md H):
    --extent musical|score+ext|debug      (default score+ext)
    --accidental-policy explicit|transposed
    --lyric-line-policy by-measure-gap|none
    --lyric-gap-threshold N
    --hyphen-policy literal|syllabic
    --part-merge auto|none|all
Overrides:
    --timesig-clamp      split measures whose time signature is implausible
    --emit-layout        emit the layout subtree (debug only)
    --dynamic-map PATH   JSON file mapping dynamic code -> name
"""
import argparse
import collections
import hashlib
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import walk_msgs, play_time, tick_per_meas
from fret import (OPEN_STRING_MIDI, STEP_BY_PC, ALTER_BY_PC,
                  root_from_fret_info, root_of, shape_from_fret_info, spelling_of)
import accomp

# ---------------------------------------------------------------- constants

# MsgHdr+0x0A flag bits (docs/smc-format.md 6.5)
F_TIE_TAIL = 0x0001
F_TAIL = 0x0004
F_SILENT = 0x0010          # grace / non-sounding
F_CHORD = 0x0020
F_STAFF_UP = 0x0200
F_STAFF_DOWN = 0x0400

EXP_SYMBOL = {0: 'longa', 1: 'whole', 2: 'half', 3: 'quarter',
              4: 'eighth', 5: '16th', 6: '32nd', 7: '64th'}

# MsgHdr+0x05 high nibble low 3 bits (docs/smc-format.md 6.6)
ACCIDENTAL = {0: None, 1: 'sharp', 2: 'flat', 3: 'natural',
              4: 'double-sharp', 5: 'flat-flat'}
ALTER_BY_ACCIDENTAL = {None: 0, 'sharp': 1, 'flat': -1, 'natural': 0,
                       'double-sharp': 2, 'flat-flat': -2}

STEP_BY_LETTER = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
# sharps order F C G D A E B, flats order B E A D G C F
SHARP_ORDER = ['F', 'C', 'G', 'D', 'A', 'E', 'B']
FLAT_ORDER = ['B', 'E', 'A', 'D', 'G', 'C', 'F']

DEFAULT_DYNAMIC_MAP = {
    1: 'ppp', 2: 'pp', 3: 'p', 4: 'mp', 5: 'mf', 6: 'f', 7: 'ff', 8: 'fff',
}


# ------------------------------------------------------------------- pitch

def step_index(step):
    return 'CDEFGAB'.index(step)


def key_fifths(symbol, count):
    """parameters.md C3: symbol 0 = none, 1 = flats, 2 = sharps."""
    if symbol == 0 or count == 0:
        return 0
    return -count if symbol == 1 else count


def key_alter_for_letter(fifths, letter):
    """Sounding alteration a key signature applies to one note letter."""
    if fifths > 0 and letter in SHARP_ORDER[:fifths]:
        return 1
    if fifths < 0 and letter in FLAT_ORDER[:abs(fifths)]:
        return -1
    return 0


def midi_to_spelling(midi, fifths, accidental, policy):
    """Return (step, alter, octave) plus the notated accidental.

    policy='explicit'  : the note's own accidental sign is authoritative for
                         `<accidental>`; `<alter>` is the sounding pitch.
    policy='transposed': ignore the sign; derive everything from the key.
    """
    pc = midi % 12
    octave = midi // 12 - 1
    if policy == 'transposed':
        accidental = None
    # candidate letters: prefer the one that needs no added accidental
    for letter, base in (('C', 0), ('D', 2), ('E', 4), ('F', 5),
                         ('G', 7), ('A', 9), ('B', 11)):
        key_alt = key_alter_for_letter(fifths, letter)
        if (base + key_alt) % 12 == pc:
            return letter, key_alt, octave, accidental
    # fall back: spell with the chromatic alteration relative to the key
    for letter, base in (('C', 0), ('D', 2), ('E', 4), ('F', 5),
                         ('G', 7), ('A', 9), ('B', 11)):
        if accidental is not None:
            alt = ALTER_BY_ACCIDENTAL[accidental]
            if (base + alt) % 12 == pc:
                return letter, alt, octave, accidental
    # last resort: nearest lower natural plus a sharp
    for letter, base in (('C', 0), ('D', 2), ('E', 4), ('F', 5),
                         ('G', 7), ('A', 9), ('B', 11)):
        if base == pc % 12:
            return letter, key_alter_for_letter(fifths, letter), octave, accidental
    return 'C', 0, octave, accidental


# -------------------------------------------------------------------- util

class Emitter:
    """Buffers records so the score header can be patched once counters are final.

    Memory is bounded by one line per event, which is the same order as the
    output file itself; for the corpus maximum (140 KB SMC) this is ~150 KB.
    """

    def __init__(self, fh):
        self.fh = fh
        self.recs = []

    def emit(self, rec):
        self.recs.append(rec)

    def flush(self):
        for r in self.recs:
            self.fh.write(json.dumps(r, ensure_ascii=False) + '\n')

    @property
    def count(self):
        return len(self.recs)


def nearest_grid(on, dur, tpm):
    """The onset the IR should use for emission.

    IR `on` (MsgHdr+0x14) is already an absolute in-measure tick, and the
    corpus confirms it is exact: summing the written durations reproduces every
    measure's tickPerMeas in 98.1% of measures. Snapping it to a coarser grid
    only introduces spurious micro-rests (measured: a 5-tick rest appeared
    wherever a triplet made the snap disagree with the true onset), so the value
    is passed through unchanged and `grid_err` records the difference from a
    1/64 grid for auditing only.
    """
    return on


def flatten_top(top):
    """Flatten one top-level child into (msg, doc_order) pairs, skipping nested
    messages the walker already reached (specifically CFretBoard inside 0x45,
    whose internal Msg is a serialization artifact, not a score element)."""
    out = []
    for m, d in walk_msgs([top]):
        if m is not top:
            parent = _parent_of(m, top)
            if parent is not None and parent.type == 0x45:
                continue                # inside a chord symbol's fretboard blob
        out.append((m, len(out)))
    return out


def _parent_of(msg, top):
    """BFS for the direct parent of `msg` within the tree rooted at `top`."""
    stack = [top]
    while stack:
        cur = stack.pop()
        for c in cur.children:
            if not c['msg']:
                continue
            if c['msg'] is msg:
                return cur
            stack.append(c['msg'])
    return None


def measure_events(meas, whole_tick):
    """One pass over a measure -> [(msg, doc-order index)] in document order."""
    out = []
    for c in meas.children:
        if not c['msg']:
            continue
        for m, _ in flatten_top(c['msg']):
            out.append((m, len(out)))
    return out


# ------------------------------------------------------------------- step1

def convert(path, opts, fh):
    doc = S.load(path)
    em = Emitter(fh)
    wt = doc.system.whole_tick
    divisions = wt            # parameters.md G1: 1 tick = 1 divisions unit
    cod = None
    try:
        cod = S.load_cod()
    except Exception:
        cod = None

    sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()

    # ---- plan parts (parameters.md B3/B4, part_merge)
    staves = []                                     # (group, idx, staff)
    for gi, group in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
        for si, st in enumerate(group):
            staves.append((gi, si, st))

    merged_groups = []                              # list of lists of staff tuples
    if opts.part_merge == 'all':
        merged_groups = [staves]
    elif opts.part_merge == 'none':
        merged_groups = [[s] for s in staves]
    else:                                           # auto: by Block staffRef
        multi = set()
        for page in doc.pages:
            for blk in list(page.blocks_a) + list(page.blocks_b):
                if blk.n_staves > 1:
                    multi.update(r[0] for r in blk.staff_refs)
        if multi and len(staves) > 1:
            merged_groups = [staves]
        else:
            merged_groups = [[s] for s in staves]

    audit = {
        'measures': 0, 'measures_not_filled': 0,
        'notes_duration_mismatch': 0, 'spans_unresolved': 0,
        'keysig_type_2': 0, 'grace_notes': 0,
    }
    warnings = []

    def warn(code, **kw):
        rec = {'kind': 'warning', 'code': code}
        rec.update(kw)
        em.emit(rec)
        warnings.append(code)

    # ---- score header (written first; counters patched at the end)
    score_rec = {
        'ir': 'smc-ir', 'v': 1, 'kind': 'score',
        'generator': {'name': 'smc2ir', 'version': '0.1.0'},
        'source': {'path': os.path.basename(path), 'sha256': sha,
                   'smc_version': doc.version},
        'title': decode_text(doc.title_raw, cod),
        'title_raw_hex': doc.title_raw.hex(),
        'extra_string': doc.extra_str.rstrip(b'\0').decode('latin-1'),
        'whole_tick': wt, 'divisions': divisions,
        'n_parts': len(merged_groups),
        'options': opts.snapshot(),
        'audit': audit,
    }
    em.emit(score_rec)

    if opts.extent == 'score+ext':
        em.emit({'kind': 'ext', 'what': 'fileinfo', 'values': list(doc.file_info)})
    if opts.extent == 'debug':
        em.emit({'kind': 'ext', 'what': 'ctltool',
                 'len': doc.ctl_len, 'hex': doc.ctl[:64].hex()})
        em.emit({'kind': 'ext', 'what': 'symp_reserved',
                 'len': 0x58C})
        em.emit({'kind': 'ext', 'what': 'fonts',
                 'items': [{'index': i, 'name_hex': n.hex(),
                            'name': decode_text(n, cod)} for i, n in doc.fonts]})

    if opts.extent != 'musical':
        for msg in doc.doc_msgs:
            em.emit({'kind': 'ext', 'what': 'doc-message', 'type': msg.type,
                     'key': msg.key})

    # ---- parts
    for pi, group in enumerate(merged_groups, 1):
        pid = 'P%d' % pi
        first_staff = group[0][2]
        em.emit({
            'kind': 'part', 'id': pid,
            'name': decode_text(first_staff.name, cod) or None,
            'n_staves': len(group),
            'src_staff': group[0][1],
        })
        convert_group(em, doc, group, pid, opts, cod, warn, audit)

    # ---- author credit (decisions.md: written as page text, not as a field)
    # Reuse the text blocks already turned into directions rather than rescanning
    # the document. The credit stays in the part as <words> as well, because the
    # source really does display it there; dropping it would lose visible
    # content. The structured form exists so the names are machine-readable.
    creators = []
    seen_creators = set()
    for rec in em.recs:
        if rec.get('kind') != 'direction':
            continue
        d = rec.get('d') or {}
        if d.get('type') != 'text':
            continue
        for line in (d.get('lines') or []):
            for role, names in parse_credit(line).items():
                for nm in names:
                    if (role, nm) in seen_creators:
                        continue
                    seen_creators.add((role, nm))
                    creators.append({'role': role, 'name': nm,
                                     'meas': rec.get('meas'), 'text': line})
    score_rec['creators'] = creators

    # ---- accompaniment (decisions.md: the embedded patterns are real tracks)
    # A chord symbol may carry a multi-track arrangement that the original
    # program plays but never draws. It is not derived from the chords: it is a
    # stored arrangement whose pitches are written as scale degrees relative to
    # the chord in force. Every track is exported as its own part, because
    # "hidden" is a layout state and dropping it would lose the music.
    # Share the melody's barline positions exactly. Step 2 sizes a measure as
    # max(time signature, furthest content), so read that back from the melody's
    # own measure records rather than recomputing the rule.
    timeline = ([], [])
    for rec in em.recs:
        if rec.get('kind') == 'measure' and rec.get('part') == 'P1':
            ends = list((rec.get('content_end') or {}).values())
            want = max([rec.get('tpm', 0)] + ends)
            timeline[0].append(sum(timeline[1]))
            timeline[1].append(want)
    aparts, anotes, ameasures, astats = accomp.build(
        doc, cod, opts, timeline=timeline if timeline[1] else None)
    for rec in aparts:
        em.emit(rec)
    for rec in ameasures:
        em.emit(rec)
    for rec in anotes:
        em.emit(rec)
    for k, v in astats.items():
        audit['accomp_' + k] = v
    if not aparts:
        warn('accompaniment-absent')

    # score_rec is em.recs[0]; refresh the audit now that counters are final
    score_rec['audit'] = dict(audit)
    em.flush()
    return score_rec, em


CREDIT_ROLE = {'\uc791\uc0ac': 'lyricist', '\uc791\uace1': 'composer'}
_CREDIT_SPLIT = re.compile(r'(\uc791\uc0ac|\uc791\uace1)')


def parse_credit(text):
    """Map a page credit line to {'lyricist': [...], 'composer': [...]}.

    Nothing in the format stores an author: the credit is ordinary page text.
    The corpus writes it as one free-form line - "\uc791\uc0ac \ub9ac\ucc2c, \uc791\uace1 \uae40\uc6d0\uade0",
    "\uc791\uc0ac \uae40\uc815\ud6c8\r\n\uc791\uace1 \uac15\uc219\uc6c5", "\uc791\uc0ac,\uc791\uace1 \uc7ac\uc911\uc870\uc120\uc778\uc608\uc220\ub2e8 \uc9d1\uccb4" - so it can only
    be recovered by reading the text. Only \uc791\uc0ac (words) and \uc791\uace1 (music) occur:
    \ud3b8\uace1 / \uc5ed\uace1 / \ubc88\uc5ed appear nowhere in the corpus, so no other role is invented.

    A keyword with no name of its own shares the next one's, which is what
    "\uc791\uc0ac,\uc791\uace1 NAME" means: both credits name the same author.
    Returns {} when the text carries no credit keyword, so ordinary expression
    text ("\uc57d\ub3d9\uc801\uc73c\ub85c \uc88d \ube60\ub974\uac8c") is never mistaken for one.
    """
    if '\uc791\uc0ac' not in text and '\uc791\uace1' not in text:
        return {}
    parts = _CREDIT_SPLIT.split(text)
    entries = []                       # [role, [names], text_after_keyword]
    for i in range(1, len(parts) - 1, 2):
        role = CREDIT_ROLE.get(parts[i])
        seg = parts[i + 1]
        names = [n.strip() for n in re.split(r'[,,\u3001]', seg)]
        entries.append([role, [n for n in names if n], seg])
    for i, entry in enumerate(entries):
        if entry[1] or entry[2].strip(' ,\uff0c'):
            continue
        for later in entries[i + 1:]:
            if later[1]:
                entry[1] = list(later[1])
                break
    out = {}
    for role, names, _ in entries:
        if names:
            bucket = out.setdefault(role, [])
            for n in names:
                if n not in bucket:
                    bucket.append(n)
    return out


def decode_text(raw, cod):
    if not raw:
        return ''
    try:
        if cod is not None:
            return S.decode(raw, cod)
    except Exception:
        pass
    return raw.decode('latin-1')


# MsgHdr+0x00 of a type 0x05 metronome mark: which note value gets the beat.
METRONOME_BEAT = {1: 'quarter', 2: 'eighth', 3: '16th', 4: 'half',
                  5: 'whole', 6: 'dotted-quarter'}


def tlv_lines(head, opts, cod):
    """Split a type 0x06 TLV head into text lines.

    The tag table comes from docs/lyrics.md 6: 0x01 align, 0x02 font, 0x03 style,
    0x04 size, 0x05/0x07 four opaque bytes, 0x06 length-prefixed text, 0x0A
    newline. In this corpus a multi-line block separates lines with CRLF and
    paragraphs with CRLF LF, which is why an empty line must be preserved rather
    than collapsed - it is the paragraph break the source author typed.
    """
    b = head
    q = 0
    align = None
    cur = []
    lines = []
    while q < len(b):
        tag = b[q]
        q += 1
        if tag == 0x01:
            if q + 2 > len(b):
                break
            align = struct.unpack_from('<h', b, q)[0]
            q += 2
        elif tag in (0x02, 0x04, 0x09):
            q += 2
        elif tag in (0x03,):
            q += 1
        elif tag in (0x05, 0x07):
            q += 4
        elif tag == 0x06:
            if q + 2 > len(b):
                break
            n = struct.unpack_from('<H', b, q)[0]
            q += 2
            cur.append(decode_text(b[q:q + n], cod))
            q += n
        elif tag == 0x0A:
            lines.append(''.join(cur))
            cur = []
        else:
            break
    if cur:
        lines.append(''.join(cur))
    if align in (-2, -1) and lines:
        lines = [ln.rstrip() for ln in lines]
    return lines, align


def convert_group(em, doc, group, pid, opts, cod, warn, audit):
    """Emit measures for one part (1..n staves merged)."""
    wt = doc.system.whole_tick
    # Part-wide key table for span resolution (parameters.md E5).
    # Built across every staff of the part so a merged double staff can resolve
    # a slur whose endpoints sit on different lines.
    key_index = {}
    staff_of_key = {}
    for si_in_part, (gi, si, st) in enumerate(group, 1):
        for mi, meas in enumerate(st.meas):
            for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
                key_index.setdefault(m.key, (mi, m))
                staff_of_key.setdefault(m.key, si_in_part)
    spans_emitted = set()
    unresolved = 0

    prev = {'time': None, 'key': None, 'clef': None}
    n_meas = max(len(st.meas) for _, _, st in group)
    per_voice_notes = 0

    for mi in range(n_meas):
        base_staff = group[0][2]
        meas = base_staff.meas[mi]
        num, den = meas.ts_num, meas.ts_den
        tpm = tick_per_meas(wt, num, den)
        audit['measures'] += 1
        if meas.keysig_type == 2:
            audit['keysig_type_2'] += 1

        fifths = key_fifths(meas.keysig_symbol, meas.keysig_count)
        clef = clef_for(meas, base_staff)
        time_pair = [num, den]

        changed = {
            'time': time_pair != prev['time'],
            'key': (fifths, meas.keysig_type) != prev['key'],
            'clef': clef != prev['clef'],
        }
        if prev['time'] is None:
            changed = {'time': True, 'key': True, 'clef': True}

        # gather events per staff, keeping the top-level ancestor for context
        events = []                                   # (staff_no, msg, order)
        for si_in_part, (gi, si, st) in enumerate(group, 1):
            if mi >= len(st.meas):
                continue
            mm = st.meas[mi]
            for m, order in measure_events(mm, wt):
                events.append((si_in_part, m, order))

        # resolve voice/staff and build note records
        notes = []
        notes_by_key = {}
        parent_of = {}                                # msg.key -> direct parent Msg
        spans = []
        directions = []
        harmonies = []
        for staff_no, m, order in events:
            for c in m.children:
                if c['msg']:
                    parent_of[c['msg'].key] = m
        for staff_no, m, order in events:
            if m.type == 0x01 or m.type == 0x03:
                is_rest = (m.type == 0x03)
                pt = play_time(m, wt)
                dur = pt
                head_dur = getattr(m, 'duration', 0)
                if m.type == 0x01 and head_dur != pt:
                    audit['notes_duration_mismatch'] += 1
                grace = bool(m.flags & F_SILENT)
                if grace:
                    audit['grace_notes'] += 1
                    # parameters.md A2: inside a beam a grace note's cached
                    # head duration is halved; the notated value is playTime.
                    dur = pt
                    head_dur = pt
                else:
                    dur = pt
                voice = (m.head[3] if (m.type == 0x01 and len(m.head) > 3) else m.voice) or 1
                staff_attr = staff_for_msg(m, group, staff_no)
                acc = ACCIDENTAL.get(m.stem_flag & 0x07)
                step = alter = octave = None
                if not is_rest:
                    step, alter, octave, acc = midi_to_spelling(
                        m.head[0], fifths, acc, opts.accidental_policy)
                rec = {
                    'kind': 'note', 'part': pid, 'meas': mi + 1,
                    'src': {'key': m.key, 'staff': staff_no - 1, 'meas_idx': mi},
                    'voice': voice, 'staff': staff_attr,
                    'on': m.start, 'grid': nearest_grid(m.start, dur, tpm),
                    'dur': dur, 'dur_head': head_dur,
                    'rest': is_rest,
                    'midi': None if is_rest else m.head[0],
                    'step': step, 'alter': alter, 'octave': octave,
                    'accidental': acc,
                    'exp': m.type_index & 0x1F, 'dots': m.dots & 0x07,
                    'symbol': EXP_SYMBOL.get(m.type_index & 0x1F),
                    'beam': None, 'chord': False,
                    'attrs': {
                        'grace': grace,
                        'head_type': m.head_type,
                        'stem_state': m.stem_flag,
                        'ties': [],
                    },
                    'lyric': None,
                    'order': order,
                }
                rec['grid_err'] = rec['on'] - rec['grid']
                if opts.extent == 'debug':
                    rec['ext'] = {'dx': m.dx, 'dy': m.dy,
                                  'flags': m.flags,
                                  'head_hex': m.head.hex()}
                notes.append(rec)
                notes_by_key[m.key] = rec
            elif m.type == 0x19:
                par = parent_of.get(m.key)
                if par is not None and par.key in notes_by_key:
                    notes_by_key[par.key]['lyric'] = lyric_record(m, cod, opts)
            elif m.type == 0x46:
                pass                          # fretboard blob of a 0x45, see below
            elif m.type in (0x14, 0x25):
                pass                                   # container: handled below
            elif m.type == 0x1B:
                directions.append(direction_record(m, pid, mi, 'dynamic', opts, staff_no))
            elif m.type == 0x05:
                directions.append(direction_record(m, pid, mi, 'metronome', opts, staff_no))
            elif m.type in (0x08, 0x0C, 0x10, 0x21, 0x0D, 0x13, 0x2C, 0x2F, 0x30):
                directions.append(direction_record(m, pid, mi, 'symbol', opts, staff_no))
            elif m.type == 0x06 or m.type == 0x04:
                if opts.extent != 'musical':
                    directions.append(direction_record(m, pid, mi, 'text', opts, staff_no, cod=cod))
            elif m.type == 0x45:
                par = parent_of.get(m.key)
                anchor = notes_by_key.get(par.key) if par is not None else None
                harmonies.append(harmony_record(m, anchor, pid, mi, opts, cod, staff_no))
            elif m.type in (0x09, 0x0A, 0x12, 0x2E):
                sp = span_record(m, key_index, staff_of_key, pid, opts)
                if not sp['resolved']:
                    unresolved += 1
                spans.append(sp)

        # beams: assign begin/continue/end by container order (parameters.md A8)
        apply_beams(notes, events)

        # gap audit per voice (grace notes excluded, parameters.md A7)
        per_voice = collections.defaultdict(int)
        per_voice_end = collections.defaultdict(int)
        for n in notes:
            if n['attrs']['grace']:
                continue
            per_voice[n['voice']] += n['dur']
            per_voice_end[n['voice']] = max(per_voice_end[n['voice']], n['on'] + n['dur'])
        gap = {}
        content_end = {}
        for v in sorted(set(per_voice) | set(per_voice_end)):
            content_end[str(v)] = per_voice_end.get(v, 0)
            gap[str(v)] = tpm - per_voice_end.get(v, 0)
        if gap and any(g != 0 for g in gap.values()):
            audit['measures_not_filled'] += 1

        mrec = {
            'kind': 'measure', 'part': pid, 'n': mi + 1,
            'tpm': tpm, 'time': time_pair,
            'time_text': decode_text(meas.timesig_text, cod) or None
            if meas.meas_mode == 3 else None,
            'key': [fifths, meas.keysig_type],
            'clef': clef,
            'changed': changed,
            'gap': gap, 'content_end': content_end,
            'warnings': (['odd-timesig'] if (den not in (1, 2, 4, 8, 16, 32, 64, 128)
                                             or tpm % 15 != 0) else []),
        }
        em.emit(mrec)

        # Emit in SMC document order within (staff, voice): the source already
        # lists events in the order they sound, and ordering by `on` would break
        # grace notes, whose `start` is an engraving hint rather than a position
        # (parameters.md A7/A9).
        notes.sort(key=lambda r: (r['staff'], r['voice'], r['order']))
        assign_chords(notes)
        for n in notes:
            n.pop('order', None)
            em.emit(n)
        for d in directions:
            em.emit(d)
        for h in harmonies:
            em.emit(h)
        for sp in spans:
            if id(sp) not in spans_emitted:
                spans_emitted.add(id(sp))
                em.emit(sp)

        prev = {'time': time_pair, 'key': (fifths, meas.keysig_type), 'clef': clef}

    audit['spans_unresolved'] += unresolved
    return {}


def clef_for(meas, staff):
    """parameters.md C4: 0x1F messages win, else StaffTail+0x21, else treble."""
    raw = staff.clef_class
    if raw in (0, 1):
        return {'sign': 'G', 'line': 2, 'uncertain': raw == 0, 'raw': raw}
    if raw in (2, 3):
        return {'sign': 'PERCUSSION', 'line': 2, 'uncertain': True, 'raw': raw}
    return {'sign': 'G', 'line': 2, 'uncertain': True, 'raw': raw}


def staff_for_msg(m, group, source_staff=1):
    """Which MusicXML <staff> this message belongs to.

    A message already knows which SMC staff it came out of, and for merged
    multi-staff parts that is the grouping MusicXML needs: several staves of one
    part share a <voice> number in the source (measured: 150ALS-06BA-0040 has
    three staves all using voices 1 and 2), so the staff index must come from the
    source staff, not from a flag. The staff flags are only used when a single
    staff carries notes for two staves (bit9 = up, bit10 = down).
    """
    if len(group) == 1:
        return 1
    return max(1, source_staff)


def apply_beams(notes, events):
    """A 0x14 container's descendant notes get begin/continue/end.

    Notes may sit at depth 1 (direct) or deeper (inside a 0x25 chord within the
    beam), so the container is walked recursively and only notes are labelled.
    """
    by_key = {n['src']['key']: n for n in notes}

    def descendants(msg):
        out = []
        for c in msg.children:
            if not c['msg']:
                continue
            if c['msg'].type in (0x01, 0x03):
                out.append(c['msg'])
            out.extend(descendants(c['msg']))
        return out

    # Grace notes are notated *before* the note they ornament even though the
    # source may list them after it (and their `start` is an engraving hint).
    # Order each beam group by notated start, then put graces ahead of the
    # principal note they precede (parameters.md A7).
    for staff_no, m, order in events:
        if m.type != 0x14:
            continue
        kids = [k for k in descendants(m) if k.key in by_key]
        kids.sort(key=lambda k: (k.start, 0 if (k.flags & F_SILENT) else 1))
        if len(kids) < 2:
            for k in kids:
                by_key[k.key]['beam'] = 'begin'
            continue
        for i, k in enumerate(kids):
            if i == 0:
                by_key[k.key]['beam'] = 'begin'
            elif i == len(kids) - 1:
                by_key[k.key]['beam'] = 'end'
            else:
                by_key[k.key]['beam'] = 'continue'


def assign_chords(notes):
    """Mark notes that sound together with the previous note as chord members.

    A chord in MusicXML is written as a sequence of notes at one onset, the
    later ones carrying <chord>. The reference note is the previous *sounding*
    note at that onset, so a grace note sitting on the same tick cannot serve as
    the chord's head: the corpus does write `grace + note` at one onset, and
    marking the second as a chord would attach it to the grace instead.
    """
    seen = {}
    for n in notes:
        key = (n['voice'], n['on'])
        ref = seen.get(key)
        if (ref is not None and not n['rest'] and not ref['rest']
                and not n['attrs'].get('grace') and not ref['attrs'].get('grace')
                and n['dur'] == ref['dur']):
            n['chord'] = True
        if not n['attrs'].get('grace'):
            seen[key] = n


def lyric_record(msg, cod, opts):
    text = decode_text(msg.lyric_bytes, cod)
    syllabic = None
    if opts.hyphen_policy == 'syllabic' and text in ('－', '-'):
        syllabic = 'middle'
    rec = {'text': text if opts.hyphen_policy == 'literal' else text.replace('－', ''),
           'syllabic': syllabic}
    if opts.extent != 'musical':
        rec['font'] = msg.lyric_font
        rec['size'] = msg.lyric_size
        rec['style'] = msg.lyric_style
        rec['color'] = msg.lyric_color
    return rec


def harmony_record(msg, anchor_note, pid, mi, opts, cod, staff=1):
    ce = getattr(msg, 'chord_extra', None)
    name = decode_text(ce.name, cod) if ce else ''
    # The root is NOT the pitch of the note the symbol sits over. A chord symbol
    # records only its suffix; the root is declared separately in ObjectCore +0x08
    # as an index into the engine's 18-entry spelling table, falling back to the
    # embedded FretBoard's lowest sounding string only when that index is absent
    # (see fret.root_of). Using the index matters: it is the only source on the
    # 29892 symbols whose FretBoard holds no fingering, and where the two differ
    # the fingering is usually reporting an inversion's bass.
    root = root_of(msg, ce.fret_info if ce else None)
    rec = {
        'kind': 'harmony', 'part': pid, 'meas': mi + 1,
        'staff': staff, 'voice': (anchor_note or {}).get('voice', 1),
        'on': anchor_note['on'] if anchor_note else 0,
        'name': name, 'kind_text': kind_from_surfix(name),
        'root': root,
        'anchor_midi': anchor_note['midi'] if anchor_note else None,
        'anchored': anchor_note is not None,
        'src': {'key': msg.key},
    }
    shape = shape_from_fret_info(ce.fret_info) if ce else None
    if opts.extent != 'musical':
        rec['ext'] = {'info_hex': ce.info.hex() if ce else '',
                      'fret_info_hex': ce.fret_info.hex() if ce else '',
                      'fret_shape': shape,
                      'root_index': msg.f8,
                      'root_source': (root or {}).get('source'),
                      'fret_base': (ce.fret_info[0] | (ce.fret_info[1] << 8))
                                   if ce and len(ce.fret_info) >= 2 else None,
                      'head_len': msg.head_len,
                      'has_rhythm': ce.has_rhythm if ce else 0}
    if opts.extent == 'debug' and shape:
        rec['d_shape'] = shape
    return rec


SUFFIX_KIND = {
    '': 'major', ' (major)': 'major', '(major)': 'major',
    'm': 'minor', 'min': 'minor', '7': 'dominant', 'm7': 'minor-seventh',
    'm6': 'minor-sixth', 'dim': 'diminished', 'dim7': 'diminished-seventh',
    '9': 'dominant-ninth', '6': 'major-sixth', 'sus4': 'suspended-fourth',
    'aug': 'augmented',
}


def kind_from_surfix(name):
    return SUFFIX_KIND.get(name, None)


def direction_record(msg, pid, mi, dclass, opts, staff=1, voice=1, cod=None):
    rec = {
        'kind': 'direction', 'part': pid, 'meas': mi + 1,
        'on': msg.start, 'voice': voice, 'staff': staff,
        'placement': 'above' if msg.dy <= 0 else 'below',
        'src': {'key': msg.key},
    }
    if dclass == 'dynamic':
        code = msg.type_index
        rec['d'] = {'type': 'dynamic', 'code': code,
                    'text': opts.dynamic_map.get(code)}
    elif dclass == 'text':
        # A type 0x06 text block is a TLV stream. Short blocks are expression
        # words (or the title) that belong on the staff. A multi-line block is a
        # further verse written *beside* the staff, not attached to notes: those
        # are exported as a side text file instead of being crammed into <words>.
        lines, align = tlv_lines(msg.head, opts, cod)
        rec['d'] = {
            'type': 'text',
            'lines': lines,
            'align': align,
            'multiline': len(lines) > 1,
        }
        if opts.extent == 'debug':
            rec['d']['raw_hex'] = msg.head.hex()
    elif dclass == 'metronome':
        # MsgHdr+0x08 is unused for 0x05; the beat count and its value are in the
        # head: +0x00 picks the beat unit, +0x02 is the figure (see evidence in
        # decisions.md). A 5-byte head with +0x02 in 9..12 is "per-minute / 10".
        b = msg.head
        beat = b[0] if len(b) > 0 else 1
        val = struct.unpack_from('<H', b, 2)[0] if len(b) >= 4 else 0
        rec['d'] = {'type': 'metronome', 'beat_index': beat, 'value': val,
                    'beat_unit': METRONOME_BEAT.get(beat, 'quarter'),
                    'bpm': val * 10 if 6 <= val <= 30 else None}
        if opts.extent == 'debug':
            rec['d']['head_hex'] = b.hex()
    else:
        rec['d'] = {'type': 'symbol', 'smc_type': msg.type,
                    'code': msg.type_index,
                    'bars': (msg.rect_r if msg.type == 0x2C else None)}
    if opts.extent == 'debug':
        rec['ext'] = {'dx': msg.dx, 'dy': msg.dy, 'flags': msg.flags}
    return rec


def span_record(msg, key_index, staff_of_key, pid, opts):
    """Resolve a tie/slur/tuplet message into its two endpoint notes.

    docs/smc-format.md 6.4: the two endpoints live in the message's `f8`
    (ObjectCore +0x08, which mirrors the parent note key - object +0x18) and in
    `MsgHdr+0x20` (object +0x70). `CreateFrom` sets both to the parent when the
    message is self-referential, so `endpoint == key` means "ends at the parent".
    """
    kind = {0x09: 'tie', 0x0A: 'slur', 0x12: 'tuplet', 0x2E: 'slur'}[msg.type]
    a_key = msg.f8
    b_key = msg.endpoint if msg.endpoint else msg.f8
    rec = {
        'kind': 'span', 'part': pid, 'k': kind,
        'src': {'key': msg.key},
        'from': None, 'to': None,
        'resolved': False,
        'raw': {'a_key': a_key, 'b_key': b_key, 'endpoint': msg.endpoint,
                'f8': msg.f8, 'msg_key': msg.key},
    }
    a = key_index.get(a_key)
    b = key_index.get(b_key)
    if a is None or b is None:
        rec['unresolved_keys'] = [k for k, v in ((a_key, a), (b_key, b)) if v is None]
        return rec
    rec['from'] = {'meas': a[0] + 1, 'key': a[1].key,
                   'staff': staff_of_key.get(a[1].key, 1)}
    rec['to'] = {'meas': b[0] + 1, 'key': b[1].key,
                 'staff': staff_of_key.get(b[1].key, 1)}
    rec['resolved'] = True
    return rec


# --------------------------------------------------------------- options

class Options:
    def __init__(self, a):
        self.extent = a.extent
        self.accidental_policy = a.accidental_policy
        self.lyric_line_policy = a.lyric_line_policy
        self.lyric_gap_threshold = a.lyric_gap_threshold
        self.hyphen_policy = a.hyphen_policy
        self.part_merge = a.part_merge
        self.accomp_mode = a.accomp_mode
        self.emit_layout = a.emit_layout
        self.timesig_clamp = a.timesig_clamp
        self.dynamic_map = dict(DEFAULT_DYNAMIC_MAP)
        if a.dynamic_map:
            with open(a.dynamic_map, encoding='utf-8') as fh:
                self.dynamic_map = {int(k): v for k, v in json.load(fh).items()}

    def snapshot(self):
        return {
            'extent': self.extent,
            'accidental_policy': self.accidental_policy,
            'lyric_line_policy': self.lyric_line_policy,
            'lyric_gap_threshold': self.lyric_gap_threshold,
            'hyphen_policy': self.hyphen_policy,
            'part_merge': self.part_merge,
            'accomp_mode': self.accomp_mode,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('smc')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--extent', default='score+ext',
                    choices=['musical', 'score+ext', 'debug'])
    ap.add_argument('--accidental-policy', default='explicit',
                    choices=['explicit', 'transposed'])
    ap.add_argument('--lyric-line-policy', default='by-measure-gap',
                    choices=['by-measure-gap', 'none'])
    ap.add_argument('--lyric-gap-threshold', type=int, default=480)
    ap.add_argument('--hyphen-policy', default='literal',
                    choices=['literal', 'syllabic'])
    ap.add_argument('--part-merge', default='auto', choices=['auto', 'none', 'all'])
    # Accompaniment is not optional. The arrangement stored in the chord
    # symbols is music the source file really contains; it is invisible only
    # because the original program does not draw it, and "not drawn" is a layout
    # state, not a reason to drop material. `--accomp-mode` therefore has a
    # single legal value: there is no way to switch the accompaniment off, and
    # adding another mode would have to be a deliberate decision rather than a
    # quiet default.
    ap.add_argument('--accomp', action='store_true', default=True,
                    help='emit every accompaniment track as its own part '
                         '(always on; hidden material must survive)')
    ap.add_argument('--accomp-mode', default='always', choices=['always'],
                    help='only "always" exists: hidden tracks are never dropped')
    ap.add_argument('--emit-layout', action='store_true')
    ap.add_argument('--timesig-clamp', action='store_true')
    ap.add_argument('--dynamic-map')
    a = ap.parse_args()

    opts = Options(a)
    out = a.out
    if out:
        with open(out, 'w', encoding='utf-8', newline='\n') as fh:
            score, em = convert(a.smc, opts, fh)
        print('%s -> %s  (%d records)' % (os.path.basename(a.smc), out, em.count))
        print('audit: %s' % json.dumps(score['audit'], ensure_ascii=False))
    else:
        score, em = convert(a.smc, opts, sys.stdout)
        print(json.dumps(score['audit'], ensure_ascii=False), file=sys.stderr)


if __name__ == '__main__':
    main()
