"""Extract the accompaniment that is embedded in a file's chord symbols.

Background
----------
A chord symbol (type 0x45) may carry a Rhythm (type 0x47) whose RtmData is a
multi-track arrangement: the accompaniment the original program plays but never
draws. 8445 of the 8451 corpus files carry one, with 1..8 tracks each.

Only a handful of chords per file carry the rhythm, and they sit exactly on
meter changes, so a Rhythm is a *style marker*: "from this measure on, play this
accompaniment style" until the next marker.

The pattern stores scale degrees relative to the prevailing chord, not absolute
pitches, and the engine resolves them at play time, which is what lets one
pattern follow the whole piece. CRtmData::ConvertToPlayData 0x100470f0 and
CRtmData::GetRealMidiKey 0x10047410 give the rules:

  * A stored key is octave * 12 + pitch class.
  * class 0 is the chord root, class 4 the third, class 7 the fifth; the third
    and fifth are taken from CChordSymbol.info, whose bytes are the semitone
    offsets of the chord's own intervals (info[0] = the third, info[0]+info[1] =
    the fifth). That is how the same stored key yields a minor third under a
    minor chord and a major third under a major one.
  * Channels are 1-based in the engine's own numbering; channel 9 is percussion
    and is deliberately not transposed, so those keys are General MIDI drum
    numbers already.
  * Positions and durations are in 1024ths of a measure, so a tick is
    round(unit * measure_ticks / 1024).

The pattern loops with a period of `a` measures and each pattern measure is
sliced by the playback window, matching how ConvertToPlayData filters events
against `[param_2, param_3)` shifted by `param_4 * 0x400`.

Verification: over 2595 chords and 55820 resolved notes, 99.1% land on a chord
tone, and percussion keys are exact General MIDI drum numbers (35 kick,
38 snare, 51 hi-hat). See probe18.py.
"""
import collections
import struct

from probe_smc import walk_msgs
from fret import root_from_fret_info, shape_from_fret_info, spelling_of

UNITS_PER_MEASURE = 1024
PERCUSSION_CHANNEL = 9
WHOLE_TICK = 240          # ticks per quarter note (parameters.md A1)


def measure_ticks(ts_num, ts_den):
    """Nominal length of one measure in ticks, or None when unusable."""
    if not ts_num or not ts_den:
        return None
    return ts_num * (4 * WHOLE_TICK) // ts_den


def resolve_key(stored, root_pc, info, channel, transpose):
    """Sounding MIDI number for a stored pattern key, following the engine.

    Returns None for control records (stored key 0), which carry a MIDI message
    instead of a note.
    """
    if not stored:
        return None
    if channel == PERCUSSION_CHANNEL:
        return stored
    octave, pc = divmod(stored, 12)
    if pc == 0:
        # A colour tone above the octave: info's remaining bytes are the 7th.
        if octave > 5 and len(info) > 2:
            pc = info[0] + info[1] - 12 + info[2]
    elif pc == 4 and info:
        pc = info[0]
    elif pc == 7 and len(info) > 1:
        pc = info[0] + info[1]
    if root_pc >= 7:
        octave -= 1
    return pc + root_pc + octave * 12 + transpose


def midi_to_step(midi):
    """(step, alter, octave) for a resolved accompaniment pitch."""
    s = spelling_of(midi)
    return s['step'], s['alter'], s['octave']


def _synth_key(pid, meas, on, track):
    """A stable identity for an accompaniment note.

    Step 2 uses `src.key` to label a note and to look up its tie/slur spans.
    Accompaniment notes have no source message of their own - they are decoded
    from a pattern - so they get a key derived arithmetically from their
    coordinates. Python's hash() is salted per process, so it cannot be used
    here: the IR must be byte-identical between runs.
    """
    part_no = int(pid[1:]) if pid[1:].isdigit() else 0
    return -((part_no * 1000003 + meas * 4096 + on) * 8 + track + 1)


def split_at_barlines(start, end, meas_start, meas_len):
    """Cut [start, end) into (segment_start, segment_end) pairs at each barline.

    A pattern note may sound across a barline; MusicXML cannot express that in
    one note, so the note becomes tied segments. A note wholly inside one
    measure yields a single segment, unchanged.

    Each segment is clamped to the measure that contains its start. Pattern
    positions are 1024ths of a measure, so converting them to ticks rounds, and
    a rounded end can land a tick or two past the barline. The barline itself is
    exact, so clamping restores it: a measure must never hold content past its
    own end.
    """
    if end <= start:
        end = start + 1
    # Never let a note sound past the last barline: the piece ends there, so a
    # pattern that overhangs is cut, not extended into a measure that cannot
    # exist. A note starting at or beyond that point has no measure to belong
    # to and is dropped; the caller counts it.
    last_end = meas_start[-1] + meas_len[-1]
    if start >= last_end:
        return []
    if end > last_end:
        end = last_end
    if end <= start:
        end = start + 1
    out = []
    cur = start
    guard = 0
    while cur < end and guard < 512:
        guard += 1
        mi = 0
        for k in range(len(meas_start)):
            if meas_start[k] <= cur:
                mi = k
        limit = meas_start[mi] + meas_len[mi]
        nxt = min(end, limit)
        # `cur` is always strictly before `limit` here because the measure is
        # chosen by `meas_start[k] <= cur`, so this advances by at least one
        # tick and cannot loop forever on a zero-length segment.
        if nxt <= cur:
            nxt = cur + 1
        out.append((cur, nxt))
        cur = nxt
    if not out:
        out.append((start, min(end, start + 1)))
    return out


def read_tracks(rtm):
    """The 6-byte track table ConvertToPlayData indexes at +0x34."""
    out = []
    for i in range(rtm.count2):
        e = rtm.seg2[i * rtm.size2:(i + 1) * rtm.size2]
        if len(e) < 6:
            break
        out.append({'channel': e[1],
                    'transpose': struct.unpack_from('<h', e, 4)[0],
                    'raw': e.hex()})
    return out


def read_events(rtm):
    """The 16-byte event records."""
    out = []
    for i in range(rtm.event_count):
        b = rtm.events[i * rtm.event_size:(i + 1) * rtm.event_size]
        if len(b) < 16:
            break
        out.append({'key': b[1], 'track': b[3],
                    'start': struct.unpack_from('<H', b, 12)[0],
                    'dur': struct.unpack_from('<I', b, 8)[0],
                    'msg': b[8:12],
                    'raw': b.hex()})
    return out


def read_control(events, n_tracks):
    """Bank and program **per channel**, from the records whose stored key is 0.

    A control record carries a raw MIDI message in bytes +8..+0xB, and its real
    destination is the channel in the status byte's low nibble - *not* the
    record's track index. ReadRtmData writes these records while populating the
    track table, using a counter that is still zero, so every control record in
    the file claims track 0 while naming its own channel. Grouping them by track
    therefore mis-assigns every instrument; the channel is the only sound key.
    """
    bank = {}
    program = {}
    for e in events:
        if e['key'] != 0:
            continue
        m = e['msg']
        status, d1, d2 = m[0] & 0xF0, m[1], m[2]
        ch = m[0] & 0x0F
        if status == 0xB0:
            if d1 == 0:
                bank[ch] = (d2, bank.get(ch, (0, 0))[1])
            elif d1 == 32:
                bank[ch] = (bank.get(ch, (0, 0))[0], d2)
        elif status == 0xC0:
            program[ch] = d1
    return bank, program


def style_name(ry):
    """Human-readable style label; the embedded name is the useful one."""
    def dec(v):
        return v.decode('latin-1') if isinstance(v, (bytes, bytearray)) else str(v or '')
    return dec(ry.s2) or dec(ry.s1) or 'style'


# General MIDI level 1 program names, used only to label a track readably.
# The accompaniment stores a program number, not a name, so the label is a
# function of the data; the raw number is kept alongside it.
GM_PROGRAM = (
    'Acoustic Grand', 'Bright Acoustic', 'Electric Grand', 'Honky-tonk',
    'Electric Piano 1', 'Electric Piano 2', 'Harpsichord', 'Clavinet',
    'Celesta', 'Glockenspiel', 'Music Box', 'Vibraphone', 'Marimba',
    'Xylophone', 'Tubular Bells', 'Dulcimer',
    'Drawbar Organ', 'Percussive Organ', 'Rock Organ', 'Church Organ',
    'Reed Organ', 'Accordion', 'Harmonica', 'Tango Accordion',
    'Nylon Guitar', 'Steel Guitar', 'Jazz Guitar', 'Clean Guitar',
    'Muted Guitar', 'Overdriven Guitar', 'Distortion Guitar', 'Guitar Harmonics',
    'Acoustic Bass', 'Fingered Bass', 'Picked Bass', 'Fretless Bass',
    'Slap Bass 1', 'Slap Bass 2', 'Synth Bass 1', 'Synth Bass 2',
    'Violin', 'Viola', 'Cello', 'Contrabass', 'Tremolo Strings',
    'Pizzicato Strings', 'Orchestral Harp', 'Timpani',
    'String Ensemble 1', 'String Ensemble 2', 'Synth Strings 1',
    'Synth Strings 2', 'Choir Aahs', 'Voice Oohs', 'Synth Voice',
    'Orchestra Hit', 'Trumpet', 'Trombone', 'Tuba', 'Muted Trumpet',
    'French Horn', 'Brass Section', 'Synth Brass 1', 'Synth Brass 2',
    'Soprano Sax', 'Alto Sax', 'Tenor Sax', 'Baritone Sax', 'Oboe',
    'English Horn', 'Bassoon', 'Clarinet',
    'Piccolo', 'Flute', 'Recorder', 'Pan Flute', 'Blown Bottle',
    'Shakuhachi', 'Whistle', 'Ocarina',
    'Lead 1 (square)', 'Lead 2 (sawtooth)', 'Lead 3 (calliope)',
    'Lead 4 (chiff)', 'Lead 5 (charang)', 'Lead 6 (voice)',
    'Lead 7 (fifths)', 'Lead 8 (bass+lead)',
    'Pad 1 (new age)', 'Pad 2 (warm)', 'Pad 3 (polysynth)', 'Pad 4 (choir)',
    'Pad 5 (bowed)', 'Pad 6 (metallic)', 'Pad 7 (halo)', 'Pad 8 (sweep)',
    'FX 1 (rain)', 'FX 2 (soundtrack)', 'FX 3 (crystal)', 'FX 4 (atmosphere)',
    'FX 5 (brightness)', 'FX 6 (goblins)', 'FX 7 (echoes)', 'FX 8 (sci-fi)',
    'Sitar', 'Banjo', 'Shamisen', 'Koto', 'Kalimba', 'Bagpipe', 'Fiddle',
    'Shanai', 'Tinkle Bell', 'Agogo', 'Steel Drums', 'Woodblock',
    'Taiko Drum', 'Melodic Tom', 'Synth Drum', 'Reverse Cymbal',
    'Guitar Fret Noise', 'Breath Noise', 'Seashore', 'Bird Tweet',
    'Telephone Ring', 'Helicopter', 'Applause', 'Gunshot',
)

# GM percussion keys, for naming a drum track's notes. Only the keys the corpus
# actually uses are listed; anything else keeps its number.
GM_DRUM = {
    35: 'Acoustic Bass Drum', 36: 'Bass Drum 1', 37: 'Side Stick',
    38: 'Acoustic Snare', 39: 'Hand Clap', 40: 'Electric Snare',
    41: 'Low Floor Tom', 42: 'Closed Hi-Hat', 43: 'High Floor Tom',
    44: 'Pedal Hi-Hat', 45: 'Low Tom', 46: 'Open Hi-Hat',
    47: 'Low-Mid Tom', 48: 'Hi-Mid Tom', 49: 'Crash Cymbal 1',
    50: 'High Tom', 51: 'Ride Cymbal 1', 52: 'Chinese Cymbal',
    53: 'Ride Bell', 54: 'Tambourine', 55: 'Splash Cymbal',
    56: 'Cowbell', 57: 'Crash Cymbal 2', 59: 'Ride Cymbal 2',
    60: 'Hi Bongo', 61: 'Low Bongo', 62: 'Mute Hi Conga',
    63: 'Open Hi Conga', 64: 'Low Conga', 65: 'High Timbale',
    66: 'Low Timbale', 67: 'High Agogo', 68: 'Low Agogo',
    69: 'Cabasa', 70: 'Maracas', 75: 'Claves', 76: 'Hi Wood Block',
    77: 'Low Wood Block',
}


def track_label(style, ti, part):
    """Short readable name for one accompaniment track."""
    if part.get('percussion'):
        return 'Drums (%s #%d)' % (style, ti + 1)
    prog = part.get('program')
    if prog is None:
        return '%s #%d (ch %d)' % (style, ti + 1, part.get('channel', 0) + 1)
    name = GM_PROGRAM[prog] if 0 <= prog < len(GM_PROGRAM) else 'Program %d' % prog
    return '%s #%d %s' % (style, ti + 1, name)


def build(doc, cod, opts, timeline=None):
    """Return (parts, notes, measures, stats) for the whole accompaniment.

    `timeline` is the melody's own (measure_start, measure_length) list, taken
    from the IR so the accompaniment shares the melody's barlines exactly. When
    omitted it is derived from the first staff.

    parts  : IR `part` records, one per (style, track), so every independent
             voice stays a separate, visible part.
    notes  : IR `note` records for those parts.
    stats  : counters for the audit line.
    """
    parts = []
    notes = []
    stats = collections.Counter()

    staves = doc.system.staff1 + doc.system.staff2
    if not staves:
        return parts, notes, [], stats

    # Timeline from the first staff: every staff shares the measure grid. The
    # length used is the melody's own realised measure length, because step 2
    # places the barline where that content actually ends (1.5% of source
    # measures run past their own time signature). Using the nominal signature
    # instead would put the accompaniment's barlines somewhere else than the
    # melody's, so the parts would no longer line up.
    if timeline:
        meas_start = list(timeline[0])
        meas_ticks = list(timeline[1])
    else:
        meas_start = []
        meas_ticks = []
        tick = 0
        for meas in staves[0].meas:
            meas_start.append(tick)
            mt = measure_ticks(meas.ts_num, meas.ts_den)
            if mt is None:                  # inherit the previous meter
                mt = meas_ticks[-1] if meas_ticks else 4 * WHOLE_TICK
            ends = []
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type in (0x01, 0x03) and m.start is not None:
                        exp = m.type_index & 0x1F
                        pt = (0x100 >> exp) * WHOLE_TICK >> 5 if exp < 8 else 0
                        if m.dots == 1:
                            pt += pt // 2
                        elif m.dots == 2:
                            pt += pt // 2 + pt // 4
                        ends.append(m.start + pt)
            if ends:
                mt = max([mt] + ends)
            meas_ticks.append(mt)
            tick += mt
    total_ticks = sum(meas_ticks)

    # Every chord symbol on every staff, in absolute ticks. Chords without a
    # rhythm still matter: they change the root the pattern resolves against.
    chords = []
    for st in staves:
        for mi, meas in enumerate(st.meas):
            if mi >= len(meas_start):
                break
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type != 0x45:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    if ce is None:
                        continue
                    root = root_from_fret_info(ce.fret_info)
                    if root is None:
                        continue
                    chords.append({
                        'tick': meas_start[mi] + m.start,
                        'meas': mi,
                        'root_pc': root['midi'] % 12,
                        'root': root,
                        'info': bytes(ce.info),
                        'shape': shape_from_fret_info(ce.fret_info),
                        'suffix': (ce.name.decode('latin-1') if ce.name else ''),
                        'style': (ce.rhythm if ce.has_rhythm and ce.rhythm else None),
                    })
    chords.sort(key=lambda c: (c['tick'], c['meas']))

    markers = [c for c in chords if c['style'] is not None]
    if not markers:
        return parts, notes, [], stats
    stats['markers'] = len(markers)

    # Index the chords so each event can find the root in force at its tick.
    onset = [c['tick'] for c in chords]

    def chord_at(t):
        lo, hi = 0, len(chords) - 1
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            if onset[mid] <= t:
                best = chords[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    part_index = {}
    for mi, marker in enumerate(markers):
        style = marker['style']
        rtm = style.rtm
        label = style_name(style)
        period = rtm.a or 1
        tracks = read_tracks(rtm)
        events = read_events(rtm)
        bank, program = read_control(events, len(tracks))
        end_meas = (markers[mi + 1]['meas'] if mi + 1 < len(markers)
                    else len(meas_start))
        stats['styles'] += 1

        # One part per independently stored track of this style. A style that
        # reappears later reuses its parts, so the piece stays comparable.
        keys = []
        for ti, t in enumerate(tracks):
            pk = (label, ti)
            if pk not in part_index:
                pid = 'A%d' % (len(part_index) + 1)
                part_index[pk] = pid
                perc = t['channel'] == PERCUSSION_CHANNEL
                rec = {
                    'kind': 'part', 'id': pid, 'name': None,
                    'n_staves': 1, 'src_staff': None,
                    'role': 'accompaniment',
                    'accomp_style': label,
                    'accomp_track': ti,
                    'channel': t['channel'],
                    'transpose': t['transpose'],
                    'percussion': perc,
                    'percussion_clef': perc,
                    'bank': list(bank.get(t['channel'], (0, 0))),
                    'program': program.get(t['channel']),
                }
                rec['name'] = track_label(label, ti, rec)
                parts.append(rec)
            keys.append(part_index[pk])

        for m in range(marker['meas'], end_meas):
            if m >= len(meas_start):
                break
            mt = meas_ticks[m]
            slice_no = (m - marker['meas']) % period
            base_units = slice_no * UNITS_PER_MEASURE
            for ti, t in enumerate(tracks):
                pid = keys[ti]
                for e in events:
                    if e['track'] != ti:
                        continue
                    if not (base_units <= e['start'] < base_units + UNITS_PER_MEASURE):
                        continue
                    if e['key'] == 0:
                        # A control record: it carries a MIDI message, not a
                        # note. Kept in the audit count so nothing is silently
                        # dropped, but it is not written as a note.
                        stats['control'] += 1
                        continue
                    on_units = e['start'] - base_units
                    on = meas_start[m] + (on_units * mt + UNITS_PER_MEASURE // 2) // UNITS_PER_MEASURE
                    end = meas_start[m] + ((on_units + e['dur']) * mt
                                           + UNITS_PER_MEASURE // 2) // UNITS_PER_MEASURE
                    if end <= on:
                        end = on + 1
                    # A pattern note starts inside one pattern measure but its
                    # duration may carry it past the barline. The engine simply
                    # plays it, because MIDI has no barlines; MusicXML does, so
                    # the note is split into tied segments at each barline. That
                    # is the notation a player would actually write for a held
                    # note, and it keeps every measure's content inside it.
                    segments = split_at_barlines(on, end, meas_start, meas_ticks)
                    if not segments:
                        stats['past_end'] += 1
                        continue
                    chord = chord_at(on)
                    if chord is None:
                        stats['orphan'] += 1
                        continue
                    midi = resolve_key(e['key'], chord['root_pc'], chord['info'],
                                       t['channel'], t['transpose'])
                    if midi is None:
                        continue
                    if not 0 <= midi <= 127:
                        stats['out_of_range'] += 1
                        continue
                    last = len(segments) - 1
                    for si2, (seg_start, seg_end) in enumerate(segments):
                        seg_meas = 0
                        for k in range(len(meas_start)):
                            if meas_start[k] <= seg_start:
                                seg_meas = k
                        if si2 != last:
                            stats['split'] += 1
                        common = {
                            'kind': 'note', 'part': pid, 'meas': seg_meas + 1,
                            'on': seg_start - meas_start[seg_meas],
                            'dur': seg_end - seg_start,
                            'voice': 1, 'staff': 1,
                            # Absolute tick, used only to split the track into
                            # voices; removed before a record is returned.
                            '_abs_on': seg_start,
                            'tie_start': si2 != last,
                            'tie_stop': si2 != 0,
                            'rest': False, 'attrs': {},
                            'midi': midi,
                            'src': {'key': _synth_key(pid, seg_meas,
                                                      seg_start - meas_start[seg_meas],
                                                      ti),
                                    'style': label, 'track': ti},
                        }
                        if t['channel'] == PERCUSSION_CHANNEL:
                            stats['percussion'] += 1
                            common.update({
                                'unpitched': True, 'step': None,
                                'alter': 0, 'octave': None,
                                'display_step': 'B', 'display_octave': 4,
                                'drum': GM_DRUM.get(midi, 'Drum %d' % midi),
                                'instrument_id': '%s-I1' % pid,
                            })
                        else:
                            step, alter, octave = midi_to_step(midi)
                            stats['pitched'] += 1
                            common.update({'step': step, 'alter': alter,
                                           'octave': octave})
                        notes.append(common)

    # A stored track is polyphonic: a drum track sounds a kick and a hi-hat at
    # the same time, and a keyboard track holds a chord under a moving line.
    # MusicXML cannot express two overlapping notes in one voice, so each track
    # is split into as many voices as it actually needs. The melody's own parts
    # already rely on this, and step 2 emits a <backup> between voices.
    for pid in sorted(set(n['part'] for n in notes)):
        free_at = []                      # end tick of the last note per voice
        for n in sorted((x for x in notes if x['part'] == pid),
                        key=lambda x: (x['_abs_on'], x['midi'] or 0)):
            on = n.pop('_abs_on')
            for vi, end in enumerate(free_at):
                if end <= on:
                    free_at[vi] = on + n['dur']
                    n['voice'] = vi + 1
                    break
            else:
                free_at.append(on + n['dur'])
                n['voice'] = len(free_at)

    # Mark chord members: same part, voice, measure and onset, so the notes that
    # truly sound together share one stem while separate voices stay separate.
    seen = {}
    for n in sorted(notes, key=lambda x: (x['part'], x['voice'], x['meas'],
                                          x['on'], x['midi'] or 0)):
        k = (n['part'], n['voice'], n['meas'], n['on'])
        if k in seen:
            n['chord'] = True
            stats['chord_members'] += 1
        else:
            seen[k] = n

    # Each accompaniment part needs the same measure skeleton as the melody, or
    # step 2 has nowhere to place its notes. Time signatures come from the
    # melody's own measures so the parts stay aligned bar for bar. The clef is
    # per part: a drum track takes a percussion clef, a low bass line takes an
    # F clef, everything else a G clef.
    def clef_for(pid):
        if parts_by_id[pid].get('percussion'):
            return {'sign': 'PERCUSSION', 'line': 2,
                    'uncertain': False, 'raw': None}
        notes_here = [n.get('midi') for n in notes
                      if n['part'] == pid and n.get('midi')]
        low = min(notes_here) if notes_here else 60
        if low < 48:                       # below C3 reads better in F clef
            return {'sign': 'F', 'line': 4, 'uncertain': False, 'raw': None}
        return {'sign': 'G', 'line': 2, 'uncertain': False, 'raw': None}

    parts_by_id = {p['id']: p for p in parts}
    measures = []
    for pid in sorted(parts_by_id):
        clef = clef_for(pid)
        for mi, meas in enumerate(staves[0].meas):
            if mi >= len(meas_start):
                break
            measures.append({
                'kind': 'measure', 'part': pid, 'n': mi + 1,
                'tpm': meas_ticks[mi],
                'time': [meas.ts_num or 4, meas.ts_den or 4],
                'time_text': None,
                'key': None,
                'clef': clef,
                'changed': {'time': mi == 0, 'key': False,
                            'clef': mi == 0},
                'gap': {None: 0},
                'content_end': {},
                'warnings': [],
            })

    stats['notes'] = len(notes)
    stats['parts'] = len(parts)
    return parts, notes, measures, stats
