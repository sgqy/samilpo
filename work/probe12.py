"""Derive chord roots from FretInfo and check them against the whole file.

The chord message (0x45) carries only a suffix ("m", " (major)", ...). Its
embedded FretBoard (0x46) carries a FretInfo whose +0x02..+0x07 bytes are the
six guitar strings. The sounding bass note - the lowest string that is actually
played - is the chord root, which is how a chord diagram reads.

Standard tuning, index 0 = 6th (lowest) string: E2 A2 D3 G3 B3 E4.
A byte >= 0xFE means the string is not played (the "x" in x02210).
"""
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs

OPEN_STRING_MIDI = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4
STEP_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def chord_from_fret_info(raw):
    """Return (root_step, root_alter, root_octave, bass_midi, shape) or None."""
    if not raw or len(raw) < 16:
        return None
    base = raw[0] | (raw[1] << 8)
    frets = raw[2:8]
    sounding = []          # (string_index, fret, midi)
    for i, f in enumerate(frets):
        if f >= 0xFE:      # muted / not played
            continue
        fret = base + f
        sounding.append((i, fret, OPEN_STRING_MIDI[i] + fret))
    if not sounding:
        return None
    bass = min(sounding, key=lambda t: t[2])
    midi = bass[2]
    pc = midi % 12
    step = STEP_NAMES[pc]
    alter = 1 if '#' in step else 0
    octave = midi // 12 - 1
    shape = ''.join('x' if f >= 0xFE else str(base + f) for f in frets)
    return step.replace('#', ''), alter, octave, midi, shape


def main(path, limit=14):
    doc = S.load(path)
    staves = doc.system.staff1 + doc.system.staff2
    print('staves:', len(staves))
    rows = []
    for si, st in enumerate(staves):
        for mi, meas in enumerate(st.meas, 1):
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type != 0x45:
                        continue
                    ce = m.chord_extra
                    name = ce.name.decode('latin-1') if ce and ce.name else ''
                    got = chord_from_fret_info(ce.fret_info) if ce else None
                    rows.append((mi, name, got, ce.info.hex() if ce else ''))
    print('chords:', len(rows))
    print()
    print('%-4s %-11s %-8s %-6s %-6s %s' % ('meas', 'surfix', 'shape', 'root', 'midi', 'info'))
    for mi, name, got, info in rows[:limit]:
        if got:
            step, alter, octave, midi, shape = got
            root = step + ('#' if alter else '') + str(octave)
        else:
            shape, root, midi = '-', '-', '-'
        print('%-4d %-11r %-8s %-6s %-6s %s' % (mi, name, shape, root, midi, info))
    print()
    hist = {}
    for mi, name, got, info in rows:
        if got:
            key = got[0] + ('#' if got[1] else '')
            hist[key] = hist.get(key, 0) + 1
    print('root pitch-class histogram:', dict(sorted(hist.items(), key=lambda kv: -kv[1])))
    shapes = {}
    for mi, name, got, info in rows:
        if got:
            key = (got[4], name)
            shapes[key] = shapes.get(key, 0) + 1
    print()
    print('distinct (shape, surfix):')
    for (shape, name), n in sorted(shapes.items(), key=lambda kv: -kv[1])[:24]:
        print('   %-8s %-11r %d' % (shape, name, n))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1
         else r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc',
         int(sys.argv[2]) if len(sys.argv) > 2 else 14)
