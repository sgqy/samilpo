"""Validate the accompaniment pitch formula against the chord it is attached to.

The formula is transcribed from CRtmData::GetRealMidiKey 0x10047410:

    octave, pc = stored_key // 12, stored_key % 12
    root_pc    = pitch class derived from the chord's FretInfo
    if pc == 0 and octave > 5 and len(info) > 2: pc = info[0] + info[1] - 12 + info[2]
    elif pc == 4: pc = info[0]                     # third
    elif pc == 7: pc = info[0] + info[1]           # fifth
    if root_pc >= 7: octave -= 1                   # == "if (9 < spelling index)"
    midi = pc + root_pc + octave * 12
    if track channel != 9: midi += track transpose

Percussion tracks (MIDI channel 9) are never transformed - the engine checks
`cVar1 != 9` - so their stored keys are raw percussion numbers.

Self-check: every melodic note the pattern produces should be a chord tone of
the chord it sits under (root, third, fifth) or a defined colour tone (7th,
6th) for the richer suffixes. Anything else means the transcription is wrong.
"""
import glob
import os
import sys
from collections import Counter

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs
from smc2ir import root_from_fret_info

ROOT = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_accomp_formula.txt'


def resolve(stored, root_pc, info, channel, transpose):
    """Return the sounding MIDI number, or None for a control event."""
    if stored == 0:
        return None
    if channel == 9:
        return stored
    octave, pc = stored // 12, stored % 12
    if pc == 0 and octave > 5 and len(info) > 2:
        pc = info[0] + info[1] - 12 + info[2]
    elif pc == 4 and len(info) > 0:
        pc = info[0]
    elif pc == 7 and len(info) > 1:
        pc = info[0] + info[1]
    if root_pc >= 7:
        octave -= 1
    return pc + root_pc + octave * 12 + transpose


def main():
    files = sorted(glob.glob(os.path.join(ROOT, '**', '*.smc'), recursive=True))
    n_chords = 0
    n_notes = 0
    n_perc = 0
    n_ctrl = 0
    interval = Counter()
    tones = Counter()
    misses = []
    info_len = Counter()
    trans_hist = Counter()
    chan_hist = Counter()
    per_file_cap = 400

    for p in files:
        if len(misses) > 40 or n_chords > 40000:
            break
        try:
            doc = S.load(p)
        except Exception:
            continue
        this_file = 0
        for st in doc.system.staff1 + doc.system.staff2:
            for meas in st.meas:
                for ch in meas.children:
                    if not ch['msg']:
                        continue
                    for m, _ in walk_msgs([ch['msg']]):
                        if m.type != 0x45:
                            continue
                        ce = m.chord_extra
                        if not (ce and ce.has_rhythm and ce.rhythm):
                            continue
                        r = ce.rhythm
                        root = root_from_fret_info(ce.fret_info)
                        if root is None:
                            continue
                        root_pc = root['midi'] % 12
                        info = ce.info
                        info_len[len(info)] += 1
                        n_chords += 1
                        this_file += 1
                        # track table
                        tr = []
                        for i in range(r.rtm.count2):
                            e = r.rtm.seg2[i * r.rtm.size2:(i + 1) * r.rtm.size2]
                            if len(e) < 6:
                                break
                            tr.append((e[1], int.from_bytes(e[4:6], 'little',
                                                            signed=True)))
                        tones_in_chord = {0, info[0] if info else 4,
                                          (info[0] + info[1]) if len(info) > 1 else 7}
                        for i in range(r.rtm.event_count):
                            b = r.rtm.events[i * r.rtm.event_size:
                                             (i + 1) * r.rtm.event_size]
                            if len(b) < 16:
                                break
                            key, track = b[1], b[3]
                            if key == 0:
                                n_ctrl += 1
                                continue
                            if track >= len(tr):
                                misses.append((p, 'track oob', track, len(tr)))
                                continue
                            chan, trans = tr[track]
                            chan_hist[chan] += 1
                            trans_hist[trans] += 1
                            midi = resolve(key, root_pc, info, chan, trans)
                            if chan == 9:
                                n_perc += 1
                                continue
                            n_notes += 1
                            rel = (midi - root_pc) % 12
                            interval[rel] += 1
                            if rel in tones_in_chord:
                                tones['chord-tone'] += 1
                            else:
                                tones['other (7th/6th/colour)'] += 1
                                if rel not in (10, 11, 9, 2, 5):
                                    misses.append((p, 'rel=%d' % rel, key, chan,
                                                   root_pc, info.hex()))
        if this_file > per_file_cap:
            pass

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('chords with rhythm examined : %d\n' % n_chords)
        f.write('melodic note events resolved: %d\n' % n_notes)
        f.write('percussion events           : %d\n' % n_perc)
        f.write('control events (key==0)     : %d\n' % n_ctrl)
        f.write('\nchannel histogram : %s\n' % dict(sorted(chan_hist.items())))
        f.write('transpose histogram : %s\n' % dict(sorted(trans_hist.items())))
        f.write('info byte-length histogram : %s\n' % dict(sorted(info_len.items())))
        f.write('\nresolved interval above root (semitones -> count):\n')
        for k, v in sorted(interval.items()):
            f.write('   %2d : %6d\n' % (k, v))
        f.write('\nchord-tone classification: %s\n' % dict(tones))
        f.write('\nfirst %d questionable: \n' % min(len(misses), 40))
        for row in misses[:40]:
            f.write('   %s %s\n' % (row[0].split('8000Songs')[-1], row[1:]))
    print('chords=%d melodic=%d perc=%d ctrl=%d' % (n_chords, n_notes, n_perc, n_ctrl))
    print('chord-tone:', dict(tones))
    print('intervals:', dict(sorted(interval.items())))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
