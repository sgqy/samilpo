"""IR (NDJSON) -> MusicXML (step 2).

Consumes only the IR: no SMC access, no engine knowledge. Emits MusicXML 4.0
partwise. Layout is never emitted (parameters.md F1): no <print>, no page or
system breaks, no absolute coordinates.

Usage:
    python work/ir2musicxml.py <file.ndjson> [<out.musicxml>] [--software NAME]
"""
import argparse
import collections
import io
import json
import os
import sys
import xml.etree.ElementTree as ET

DOCTYPE = ('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 '
           'Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">')

SCORE_NS_INLINE = False      # keep the common no-namespace form; see --namespaced

# IR `exp` -> MusicXML <type>; dots are separate.
TYPE_NAME = {0: 'long', 1: 'whole', 2: 'half', 3: 'quarter', 4: 'eighth',
             5: '16th', 6: '32nd', 7: '64th'}

# accidental sign -> MusicXML <accidental> text
ACC_TEXT = {'sharp': 'sharp', 'flat': 'flat', 'natural': 'natural',
            'double-sharp': 'double-sharp', 'flat-flat': 'flat-flat'}


def sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag)
    for k, v in attrs.items():
        if v is not None:
            el.set(k, str(v))
    if text is not None:
        el.text = str(text)
    return el


# ------------------------------------------------------------------ loading

def load_ir(path):
    return load_ir_lines(open(path, encoding='utf-8'), origin=path)


def load_ir_text(text, origin='<memory>'):
    return load_ir_lines(io.StringIO(text), origin=origin)


def load_ir_lines(line_iter, origin='<memory>'):
    """Parse NDJSON IR into (score, parts, part_measures, events_of, span_index).

    Spans are indexed globally so a tie/slur whose endpoints sit in different
    measures can be attached from either end. `events_of` holds measure-local
    events (notes, directions, harmonies) in emission order.
    """
    score = None
    parts = []
    part_measures = collections.OrderedDict()
    events_of = {}
    spans = []
    for line_no, line in enumerate(line_iter, 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise SystemExit('%s:%d: bad JSON: %s' % (origin, line_no, e))
        k = rec.get('kind')
        if k == 'score':
            score = rec
        elif k == 'part':
            parts.append({'id': rec['id'], 'name': rec.get('name'),
                          'n_staves': rec.get('n_staves', 1)})
        elif k == 'measure':
            part_measures.setdefault(rec['part'], []).append(rec)
            events_of.setdefault((rec['part'], rec['n']), [])
        elif k == 'span':
            spans.append(rec)
        elif k in ('note', 'direction', 'harmony'):
            events_of.setdefault((rec['part'], rec['meas']), []).append(rec)
        # 'warning', 'ext' and '#' are ignored by design
    if score is None:
        raise SystemExit('%s: no score record' % origin)

    # span lookup, per kind and direction:
    #   (part, meas, key, kind) -> {'start': n, 'stop': n}
    span_index = collections.defaultdict(lambda: {'start': 0, 'stop': 0})
    for sp in spans:
        if not sp.get('resolved'):
            continue
        part, kind = sp['part'], sp['k']
        f, t = sp.get('from'), sp.get('to')
        if f:
            span_index[(part, f['meas'], f['key'], kind)]['start'] += 1
        if t:
            span_index[(part, t['meas'], t['key'], kind)]['stop'] += 1
    return score, parts, part_measures, events_of, span_index


# ------------------------------------------------------------------ writing

def build(score, parts, part_measures, events_of, span_index, software):
    div = score.get('divisions', 240)
    root = ET.Element('score-partwise', {'version': '4.0'})
    sub(root, 'movement-title', score.get('title') or None)
    ident = sub(root, 'identification')
    sub(ident, 'encoding').append(_software(software))
    src = score.get('source', {})
    if src.get('path'):
        sub(sub(ident, 'miscellaneous'), 'miscellaneous-field',
            src['path'], name='smc-source')

    part_list = sub(root, 'part-list')
    for p in parts:
        sp = sub(part_list, 'score-part', id=p['id'])
        sub(sp, 'part-name', p.get('name') or 'Music')

    for p in parts:
        write_part(root, p, part_measures.get(p['id'], []), events_of,
                   span_index, div)
    return root


def _software(name):
    el = ET.Element('software')
    el.text = name
    return el


def measure_length(mrec):
    """The tick length this measure must occupy.

    Normally its own time signature. When the source writes content past its own
    signature (recorded in the IR as a negative `gap`) the barline is placed
    where the content actually ends, so the emitted music is not silently
    rewritten; the IR audit retains the discrepancy.
    """
    tpm = mrec.get('tpm', 0)
    ends = list((mrec.get('content_end') or {}).values())
    return max([tpm] + ends)


def write_part(root, part, measures, events_of, span_index, div):
    """Emit one <part>.

    Each measure is emitted at the length the source itself occupies: the
    maximum of its time signature and its actual content (parameters.md A4/A6).
    """
    pel = sub(root, 'part', id=part['id'])
    n_staves = part.get('n_staves', 1)
    issues = []
    for idx, m in enumerate(measures):
        mel = sub(pel, 'measure', number=m['n'])
        write_attributes(mel, m, pel, idx == 0, n_staves, div)
        ev = events_of.get((part['id'], m['n']), [])
        mi = write_measure_body(mel, m, ev, part['id'], span_index, div, n_staves)
        issues.extend(mi)
    return issues


def write_attributes(measure_el, m, part_el, first, n_staves, div):
    changed = m.get('changed', {})
    if not first and not any(changed.get(k) for k in ('time', 'key', 'clef')):
        return
    at = sub(measure_el, 'attributes')
    # Order follows the MusicXML DTD sequence: divisions, key, time, staves, clef.
    if first:
        sub(at, 'divisions', div)
    if changed.get('key', first):
        fifths = (m.get('key') or [0, 1])[0]
        k = sub(at, 'key')
        sub(k, 'fifths', fifths)
        sub(k, 'mode', 'major' if fifths >= 0 else 'minor')
    if changed.get('time', first):
        beats, beat_type = m.get('time', [4, 4])
        t = sub(at, 'time')
        if m.get('time_text'):
            t.set('data-smc-text', m['time_text'])
        sub(t, 'beats', beats)
        sub(t, 'beat-type', beat_type)
    if n_staves > 1:
        sub(at, 'staves', n_staves)
    if changed.get('clef', first):
        clef = m.get('clef') or {}
        c = sub(at, 'clef')
        sign = clef.get('sign') or 'G'
        sub(c, 'sign', 'percussion' if sign == 'PERCUSSION' else sign)
        sub(c, 'line', clef.get('line', 2))
        if clef.get('octave_change'):
            sub(c, 'clef-octave-change', clef['octave_change'])
        if clef.get('uncertain'):
            c.set('data-smc-uncertain', 'true')


def order_voice(vnotes):
    """Order one voice's notes the way MusicXML must present them.

    Two facts from the corpus drive this:

    * principals are not always in onset order in the source document
      (500KFS-0089 measure 5 lists onsets 0, 180, 360, 240), and MusicXML
      positions are derived by summation, so they must be sorted by onset;
    * a grace note carries an engraving hint rather than a position and is
      written *before* the note it ornaments, even when the source lists it
      after (500KFS-0011 measure 12 lists grace(0), principal(0), grace(25),
      grace(84)).

    So principals are sorted by onset, and each grace is attached to the next
    principal in document order (the last principal when no principal follows),
    then emitted immediately before it in document order.
    """
    principals = [n for n in vnotes if not n['attrs'].get('grace')]
    graces = [n for n in vnotes if n['attrs'].get('grace')]
    principals.sort(key=lambda r: r['on'])

    if not graces:
        return principals
    if not principals:
        return graces

    # Attach each grace to the next principal in *document* order (the last
    # principal when none follows), then emit it before that principal. Identity
    # is by position in the input list: comparing the dicts by value would match
    # two identical rests or two equal notes.
    positions = list(enumerate(vnotes))
    doc_index = {id(n): i for i, n in positions}
    attached = collections.defaultdict(list)
    principals_in_doc_order = [n for _, n in positions if not n['attrs'].get('grace')]
    for _, g in positions:
        if not g['attrs'].get('grace'):
            continue
        after = [n for n in principals_in_doc_order if doc_index[id(n)] > doc_index[id(g)]]
        target = after[0] if after else principals_in_doc_order[-1]
        attached[id(target)].append(g)

    out = []
    for p in principals:
        out.extend(attached.get(id(p), ()))
        out.append(p)
    return out


def write_measure_body(measure_el, mrec, events, pid, span_index, div, n_staves):
    """Emit one measure. Returns the issue list.

    Voices are emitted in (staff, voice) order and padded with a forward so the
    next backup starts from a known tick.
    """
    notes = [e for e in events if e['kind'] == 'note']
    mnum = mrec['n']
    tpm = measure_length(mrec)
    issues = []

    def spans_of(key, kind):
        return span_index.get((pid, mnum, key, kind), {})

    by_voice = collections.OrderedDict()
    for n in notes:
        by_voice.setdefault((n.get('staff', 1), n['voice']), []).append(n)

    # Directions and harmonies are placed in the voice stream that is already at
    # their onset, so MusicXML's additive time model stays intact.
    dirs_at = collections.defaultdict(list)
    for e in events:
        if e['kind'] == 'direction':
            key = (e.get('staff', 1), e.get('voice', 1))
            dirs_at[key].append(('direction', e))
        elif e['kind'] == 'harmony':
            key = (e.get('staff', 1), e.get('voice', 1))
            dirs_at[key].append(('harmony', e))

    if not by_voice and not dirs_at:
        write_empty_measure(measure_el, mrec, div)
        return issues

    ordered = sorted(by_voice.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    for i, ((staff, voice), vnotes) in enumerate(ordered):
        if i > 0:
            # Each voice is padded to the barline, so the reader's cursor sits at
            # the measure length when the next voice begins: rewind it fully.
            b = sub(measure_el, 'backup')
            b.append(_dur(tpm))
        cursor, issued = write_voice(measure_el, mrec, staff, voice,
                                     order_voice(vnotes), spans_of, div, n_staves,
                                     dirs_at.pop((staff, voice), None))
        issues.extend(issued)
        if cursor < tpm:
            f = sub(measure_el, 'forward')
            f.append(_dur(tpm - cursor))

    # Anything whose voice never appeared still has to be emitted, or the tempo
    # marking and the chord symbols would silently vanish.
    leftover = [x for group in dirs_at.values() for x in group]
    if leftover:
        if ordered:
            b = sub(measure_el, 'backup')
            b.append(_dur(tpm))
        write_directions_and_harmonies(measure_el, leftover, div)
    return issues


def _dur(ticks):
    """divisions == whole_tick means one tick IS one divisions unit (parameters.md G1)."""
    el = ET.Element('duration')
    el.text = str(int(round(ticks)))
    return el


def write_empty_measure(measure_el, mrec, div):
    n = sub(measure_el, 'note')
    sub(n, 'rest', measure='yes')
    sub(n, 'duration', mrec.get('tpm', 0))
    sub(n, 'voice', 1)


def plan_voice(vnotes, tpm):
    """Turn IR notes into the events one measure needs.

    The rule is *fidelity*, because IR onsets and durations are exact:

      A4  a gap between onsets becomes a rest, so the voice reproduces the
          source's own absolute onsets rather than re-deriving them;
      A6  notes are NOT cut at the barline. IR durations are exact, and cutting
          would either invent a tie the source never wrote or move later onsets.
          Where the source means a tie it says so with a 0x09 message, already
          resolved into `span`.

    Consequently a measure whose source content runs past its own time signature
    (measured: 1.5% of measures, recorded in the IR as a negative `gap`) is
    emitted at that true extent; the caller widens the barline accordingly and
    the IR audit keeps the record. This is deliberate: the alternative silently
    rewrites the score to fit a signature the source itself did not honour.

    Returns (events, issues).
    """
    events = []
    issues = []
    cursor = 0
    for n in vnotes:
        if n['attrs'].get('grace'):
            events.append({'kind': 'note', 'n': n, 'on': None, 'dur': 0,
                           'tie_start': False, 'tie_stop': False})
            continue
        on = n['grid'] if n.get('grid') is not None else n['on']
        if on > cursor:
            events.append({'kind': 'rest', 'n': None, 'on': cursor,
                           'dur': on - cursor, 'tie_start': False, 'tie_stop': False})
        elif on < cursor:
            issues.append('overlap key=%s on=%d cursor=%d' %
                          (n['src']['key'], on, cursor))
        events.append({'kind': 'note', 'n': n, 'on': on, 'dur': n['dur'],
                       'tie_start': False, 'tie_stop': False})
        cursor = on + n['dur']
        if cursor > tpm:
            issues.append('overrun key=%s on=%d end=%d tpm=%d' %
                          (n['src']['key'], on, cursor, tpm))
    return events, issues


def _plain_exp(dur, whole_tick=240):
    """(exp, dots) when `dur` is an undotted, single- or double-dotted note
    value, else None. This is the search MusicXML itself requires."""
    for exp in range(0, 8):
        base = (0x100 >> exp) * whole_tick >> 5
        if dur == base:
            return exp, 0
        if dur == base + base // 2:
            return exp, 1
        if dur == base + base // 2 + base // 4:
            return exp, 2
    return None


def _exp_for(dur, whole_tick=240):
    """Exponent of the plain (undotted) note value for `dur`, or None."""
    for exp in range(0, 8):
        if dur == (0x100 >> exp) * whole_tick >> 5:
            return exp
    return None

def _notate(dur, whole_tick=240, max_terms=16):
    """Express a tick length as MusicXML notation.

    Returns (exp, dots, actual, normal):
      exp             exponent selecting the note value (None when nothing fits)
      dots            0, 1 or 2 augmentation dots
      actual, normal  time-modification for a tuplet (None when not needed)

    Search order: an exact plain or dotted value first, then the smallest tuplet
    ratio against any nominal value. The corpus needs both: 90 ticks is a dotted
    16th, while 40 ticks is an eighth-note triplet (3 in the time of 2).
    """
    plain = _plain_exp(dur, whole_tick)
    if plain is not None:
        return plain[0], plain[1], None, None
    exp, actual, normal = _exp_and_ratio(dur, whole_tick, max_terms)
    if exp is None:
        return None, 0, None, None
    return exp, 0, actual, normal


def _exp_and_ratio(dur, whole_tick=240, max_terms=16):
    """Best (exp, actual, normal) for a duration using a tuplet.

    A tuplet note carries its nominal type plus <time-modification>. The corpus
    contains exactly this: 40 and 135 ticks are not reachable from plain note
    values, but are exact small ratios against one.

    Returns (exp, actual, normal), with the ratio reduced; exp is None when no
    ratio with small terms exists.
    """
    best = None
    for exp in range(0, 8):
        base = (0x100 >> exp) * whole_tick >> 5
        for dots, (num, den) in ((0, (1, 1)), (1, (3, 2)), (2, (7, 4))):
            if (base * num) % den:
                continue
            nominal = base * num // den
            if not nominal:
                continue
            g = _gcd(nominal, dur)
            actual, normal = nominal // g, dur // g
            if actual == 1 or normal == 1 or actual > max_terms or normal > max_terms:
                continue
            score = (actual + normal, exp, dots)
            if best is None or score < best[0]:
                best = (score, exp, actual, normal)
    if best is None:
        return None, None, None
    return best[1], best[2], best[3]


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def write_directions_and_harmonies(measure_el, items, div):
    """Emit <direction> and <harmony> elements for one measure.

    Both are placed at their tick with a preceding <forward> so MusicXML's
    additive time model stays consistent. They carry no duration, so they do not
    advance the cursor beyond their onset.
    """
    cursor = 0
    for kind, e in sorted(items, key=lambda x: x[1].get('on', 0)):
        on = e.get('on', 0)
        if on > cursor:
            f = sub(measure_el, 'forward')
            f.append(_dur(on - cursor))
            cursor = on
        if kind == 'harmony':
            write_harmony(measure_el, e)
        else:
            write_direction(measure_el, e)


def write_direction(measure_el, e):
    d = e.get('d') or {}
    dt = d.get('type')
    if dt == 'text' and d.get('multiline'):
        # A multi-line block is a later verse written beside the staff, not a
        # marking on it. It is routed to the side text file (see side_text.py)
        # rather than into <words>, which would place the whole verse at one
        # tick and lose the line structure.
        return
    el = sub(measure_el, 'direction', placement=e.get('placement', 'above'))
    body = sub(el, 'direction-type')
    if dt == 'dynamic':
        dyn = sub(body, 'dynamics')
        name = d.get('text')
        if name:
            sub(dyn, name)
        else:
            # Code with no entry in the mapping table: keep the mark's identity
            # rather than dropping the sign, so nothing is silently lost.
            sub(dyn, 'other-dynamics', 'smc%d' % d.get('code', 0))
    elif dt == 'text':
        lines = d.get('lines') or []
        words = ' '.join(ln for ln in lines if ln)
        if words:
            sub(body, 'words', words)
    elif dt == 'metronome':
        m = sub(body, 'metronome')
        sub(m, 'beat-unit', d.get('beat_unit') or 'quarter')
        if d.get('bpm'):
            sub(m, 'per-minute', d['bpm'])
            sub(el, 'sound', tempo=str(d['bpm']))
    else:
        # Marks with no MusicXML counterpart (breath, coda, long rest, ...) are
        # kept as words so the information survives into the product.
        label = d.get('smc') or ('smc-type-%s' % d.get('smc_type'))
        sub(body, 'words', label)


def write_harmony(measure_el, e):
    el = sub(measure_el, 'harmony')
    root = e.get('root')
    if root:
        r = sub(el, 'root')
        sub(r, 'root-step', root['step'])
        if root.get('alter'):
            sub(r, 'root-alter', root['alter'])
        if root.get('octave') is not None:
            # The octave is not part of the chord name, but the IR derived the
            # spelling from a sounding pitch; recording it keeps the harmonic
            # content distinguishable when the same symbol is played in two
            # registers.
            sub(r, 'root-octave', root['octave'])
    kind = e.get('kind_text')
    k = sub(el, 'kind')
    if kind:
        k.text = kind
    elif e.get('name'):
        # Unrecognised suffix: MusicXML allows free text here, which is more
        # faithful than forcing it into a wrong enumerated kind.
        k.text = 'other'
        k.set('text', e['name'].strip() or 'unknown')
    else:
        k.text = 'major'


def smc_text_payload(d):
    """Decode a 0x06 TLV head kept in the IR as raw hex.

    Returns (words, tempo_or_None). An expression such as '약동적으로 좀 빠르게'
    is a text direction and yields words only; the numeric tempo in this corpus
    comes from the metronome mark (type 0x05), not from the text.
    """
    raw = d.get('raw_hex')
    if raw:
        try:
            return _tlv_words(bytes.fromhex(raw), _load_cod()), None
        except Exception:
            pass
    return (d.get('words') or '', None)


def _tlv_words(b, cod=None):
    """Concatenate the text payloads of a type 0x06 TLV head.

    Tag table: 0x01 i16 align, 0x02 u16 font, 0x03 u8 style, 0x04 u16 size,
    0x05 and 0x07 four bytes, 0x06 u16 length + text, 0x0A newline.
    """
    q = 0
    out = []
    while q + 1 < len(b):
        tag = b[q]
        q += 1
        if tag in (0x01, 0x02, 0x04, 0x09):
            q += 2
        elif tag in (0x03, 0x05, 0x07):
            q += {0x03: 1, 0x05: 4, 0x07: 4}[tag]
        elif tag == 0x06:
            if q + 2 > len(b):
                break
            n = int.from_bytes(b[q:q + 2], 'little')
            q += 2
            seg = b[q:q + n]
            q += n
            if cod is not None:
                try:
                    import smc_read as S
                    out.append(S.decode(seg, cod))
                    continue
                except Exception:
                    pass
            out.append(seg.decode('latin-1'))
        elif tag == 0x0A:
            out.append(' ')
        else:
            break
    return ''.join(out).strip()


_COD = None


def _load_cod():
    global _COD
    if _COD is None:
        try:
            import smc_read as S
            _COD = S.load_cod()
        except Exception:
            _COD = False
    return _COD or None


def write_voice(el, mrec, staff, voice, vnotes, spans_of, div, n_staves,
                markings=None):
    """Emit one voice stream; return (tick reached, issues).

    `markings` are the direction/harmony records for this voice. They are
    interleaved at their own onset, before the note that starts there, so a
    tempo marking or chord symbol lands on the beat it belongs to.
    """
    tpm = measure_length(mrec)
    events, issues = plan_voice(vnotes, tpm)
    pending = collections.defaultdict(list)
    for kind, e in (markings or []):
        pending[e.get('on', 0)].append((kind, e))
    cursor = 0
    for ev in events:
        n = ev['n']
        # A rest planned by A4 has no IR note behind it, so its own grace flag
        # cannot be consulted; only real notes can carry one.
        grace_here = bool(n and n['attrs'].get('grace'))
        if not grace_here:
            at = ev['on'] if ev['on'] is not None else cursor
            # Everything whose onset has been reached is emitted before this
            # note, so a tempo marking or chord symbol lands on its beat.
            ready = sorted(k for k in pending if k <= at)
            for k in ready:
                if k > cursor:
                    f = sub(el, 'forward')
                    f.append(_dur(k - cursor))
                    cursor = k
                write_markings(el, pending.pop(k))
        note_el = sub(el, 'note')
        if ev['kind'] == 'rest':
            sub(note_el, 'rest')
            sub(note_el, 'duration', ev['dur'])
            sub(note_el, 'voice', voice)
            t = TYPE_NAME.get(_exp_for(ev['dur']))
            if t:
                sub(note_el, 'type', t)
            cursor = ev['on'] + ev['dur']
            continue
        if n.get('chord') and not n['attrs'].get('grace'):
            sub(note_el, 'chord')
        if n['attrs'].get('grace'):
            sub(note_el, 'grace')
        if n.get('rest'):
            sub(note_el, 'rest')
        else:
            pitch = sub(note_el, 'pitch')
            sub(pitch, 'step', n['step'] or 'C')
            if n.get('alter'):
                sub(pitch, 'alter', n['alter'])
            sub(pitch, 'octave', n['octave'] if n.get('octave') is not None else 4)
        grace = n['attrs'].get('grace')
        if not grace:
            sub(note_el, 'duration', ev['dur'])
        tie_sp = spans_of(n['src']['key'], 'tie')
        tie_start = tie_sp.get('start', 0) > 0 or ev.get('tie_start')
        tie_stop = tie_sp.get('stop', 0) > 0 or ev.get('tie_stop')
        if tie_start:
            sub(note_el, 'tie', type='start')
        if tie_stop:
            sub(note_el, 'tie', type='stop')
        sub(note_el, 'voice', voice)
        full = n.get('dur')
        actual = normal = None
        if grace:
            exp, dots = n.get('exp'), n.get('dots') or 0
        elif ev['dur'] == full and _plain_exp(full) == n.get('exp'):
            # Whole note, and the notated type matches its length: keep the
            # dots and beam the IR carried.
            exp = n.get('exp')
            dots = n.get('dots') or 0
        else:
            # A split half, or a length whose notated form is a dotted/tuplet
            # value: derive type, dots and any time-modification from the length.
            exp, dots, actual, normal = _notate(ev['dur'])
        t = TYPE_NAME.get(exp)
        if t:
            sub(note_el, 'type', t)
        if actual and normal and actual != normal:
            tm = sub(note_el, 'time-modification')
            sub(tm, 'actual-notes', actual)
            sub(tm, 'normal-notes', normal)
        elif not grace and exp is None:
            # A5: no note value and no small tuplet ratio expresses this tick
            # count. Keep the exact duration (consumers honour it) and record
            # the inexactness instead of silently rounding.
            note_el.set('data-smc-inexact-duration', str(ev['dur']))
        for _ in range(dots):
            sub(note_el, 'dot')
        if n.get('accidental') and ACC_TEXT.get(n['accidental']):
            sub(note_el, 'accidental', ACC_TEXT[n['accidental']])
        if n_staves > 1:
            sub(note_el, 'staff', n.get('staff', 1))
        beam = n.get('beam')
        if beam and ev['kind'] == 'note' and ev['dur'] == n.get('dur'):
            sub(note_el, 'beam', beam, number='1')
        slur_sp = spans_of(n['src']['key'], 'slur')
        n_start = slur_sp.get('start', 0) if ev['kind'] == 'note' else 0
        n_stop = slur_sp.get('stop', 0) if ev['kind'] == 'note' else 0
        # <tied> and <slur> both belong inside <notations>; the <tie> element
        # above is the separate sounding-tie marker.
        nots = None
        if tie_start or tie_stop or n_start or n_stop:
            nots = sub(note_el, 'notations')
        if tie_start:
            sub(nots, 'tied', type='start')
        if tie_stop:
            sub(nots, 'tied', type='stop')
        for i in range(n_start):
            nots.append(_slur('start', i + 1))
        for i in range(n_stop):
            nots.append(_slur('stop', i + 1))
        ly = n.get('lyric')
        if ly and ly.get('text') is not None:
            lyr = sub(note_el, 'lyric')
            if ly.get('syllabic'):
                sub(lyr, 'syllabic', ly['syllabic'])
            sub(lyr, 'text', ly['text'])
        if not grace:
            cursor = ev['on'] + ev['dur']
    # any marking still pending (its onset is at or past the last note) is
    # emitted at the end of the stream rather than dropped
    for k in sorted(pending):
        if k > cursor:
            f = sub(el, 'forward')
            f.append(_dur(k - cursor))
            cursor = k
        write_markings(el, pending[k])
    return cursor, issues


def write_markings(el, items):
    for kind, e in items:
        if kind == 'harmony':
            write_harmony(el, e)
        else:
            write_direction(el, e)


def _slur(kind, number=1):
    el = ET.Element('slur')
    el.set('type', kind)
    el.set('number', str(number))
    return el


# ------------------------------------------------------------------- output

def parse(text):
    """Parse our own serialized MusicXML text back into an ElementTree.

    Splits off the XML declaration and DOCTYPE by looking for the first '<'
    that begins the root element rather than by counting lines, so the result
    does not depend on how many blank lines the serializer emitted.
    """
    body = text
    if body.startswith('<?xml'):
        body = body.split('?>', 1)[1]
    body = body.lstrip('\n')
    if body.startswith('<!DOCTYPE'):
        body = body.split('>', 1)[1]
    return ET.fromstring(body.lstrip('\n'))


def serialize(root, namespaced=False, indent=True):
    if indent:
        ET.indent(root, space='  ')
    body = ET.tostring(root, encoding='unicode')
    if namespaced:
        body = ('<score-partwise xmlns="http://www.musicxml.org/ns/partwise" '
                'version="4.0">' + body.split('>', 1)[1])
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + DOCTYPE + '\n' + body + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ir')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--software', default='smc2ir/ir2musicxml 0.1.0')
    ap.add_argument('--namespaced', action='store_true')
    a = ap.parse_args()

    score, parts, part_measures, events_of, span_index = load_ir(a.ir)
    root = build(score, parts, part_measures, events_of, span_index, a.software)
    text = serialize(root, namespaced=a.namespaced)
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        print('%s -> %s  (%d bytes)' % (os.path.basename(a.ir), a.out, len(text)))
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
