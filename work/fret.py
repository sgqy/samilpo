"""Guitar fretboard interpretation, shared by chord symbols and accompaniment.

A chord symbol (type 0x45) stores only a suffix - "m", " (major)", "7". The root
is written elsewhere, in one of two places:

  * **ObjectCore `+0x08` (`f8`) is the declared root**, as an index into an
    18-entry spelling table (`DAT_101002cc`). It is the primary source: it agrees
    with the fingering below on 96.2% of the 148017 symbols that have a shape,
    and it exists on every symbol - including the 29892 whose FretBoard is empty,
    where there is no shape to read. Where the two disagree the fingering is
    usually naming an inversion's bass as the root: of the decided disagreements,
    the dominant gap is a fifth (the bass is the 5th of the declared root), and
    scoring both candidates against the shape's own pitch classes favours `f8`
    65.7% of the time.
  * The **FretBoard (type 0x46)** embedded in the same message records which fret
    each string is pressed at. Reading the shape as a chord diagram does, the
    lowest sounding string gives a root - reliable for root-position shapes, but
    it reports the bass of an inversion instead. It is the fallback, used only
    when `f8` is out of range (734 symbols carry a pointer there rather than an
    index).

FretInfo layout (smc-format.md 6.8, CFretInfo::ReadFromMem 0x1002dc70):

    +0x00 u16    baseFret
    +0x02 [u8;6] fret per string, lowest first; >= 0xFE means not played
    +0x08 [u8;8] four (start, end) pairs

Standard tuning, lowest string first: E2 A2 D3 G3 B3 E4.
"""

# MIDI numbers of the six open strings, 6th (lowest) first.
OPEN_STRING_MIDI = (40, 45, 50, 55, 59, 64)

# Sharp spelling, indexed by pitch class. The corpus keys are routinely written
# with sharps (the reference piece is in F# minor), so sharp spelling keeps the
# chord roots consistent with the key signature instead of mixing the two.
STEP_BY_PC = ('C', 'C', 'D', 'D', 'E', 'F', 'F', 'G', 'G', 'A', 'A', 'B')
ALTER_BY_PC = (0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0)

# The 18-entry root spelling table the engine indexes with ObjectCore +0x08
# (DAT_101002cc). Both enharmonic spellings are present and the source picks one,
# so the spelling is carried through rather than recomputed from the pitch class -
# a chord written Ab stays Ab instead of becoming G#.
ROOT_TABLE = (
    ('C', 0), ('C', 1), ('D', -1), ('D', 0), ('D', 1), ('E', -1),
    ('E', 0), ('F', 0), ('F', 1), ('G', -1), ('G', 0), ('G', 1),
    ('A', -1), ('A', 0), ('A', 1), ('B', -1), ('B', 0), ('C', -1),
)

ROOT_TABLE_LIMIT = len(ROOT_TABLE)

# `f8` is a flag word with the root index in its low byte, not a bare index: 734
# symbols carry values like 0x100005, 0xB0000, 0x110006 whose low byte is the root
# and whose upper bits are flags (every observed flagged value has an upper part
# that is a multiple of 0x100, and none occupies the 18..65535 gap). Masking is
# therefore safe, and for a flagged value the reading is confirmed by the score's
# own melody: 67.9% of melody notes in those measures are chord tones of it,
# against ~50% for every alternative reading, and 85.9% of the opening note.
ROOT_INDEX_MASK = 0xFF

NOT_PLAYED = 0xFE


def root_from_index(idx):
    """Decode ObjectCore `f8` into {step, alter, midi} without an octave.

    Returns None when the masked value is not a valid index. An invalid index is
    not a root: the caller falls back to the fingering instead of trusting it.
    """
    if idx is None or idx < 0:
        return None
    idx &= ROOT_INDEX_MASK
    if idx >= ROOT_TABLE_LIMIT:
        return None
    step, alter = ROOT_TABLE[idx]
    base = STEP_BY_PC.index(step)
    return {'step': step, 'alter': alter, 'octave': None,
            'midi': None, 'pc': (base + alter) % 12}


def shape_from_fret_info(raw):
    """Render the six strings as a chord diagram does, e.g. "x02210"."""
    if not raw or len(raw) < 8:
        return None
    base = raw[0] | (raw[1] << 8)
    return ''.join('x' if f >= NOT_PLAYED else str(base + f) for f in raw[2:8])


def root_from_fret_info(raw):
    """Derive the chord root from a FretInfo as {step, alter, octave, midi}."""
    if not raw or len(raw) < 8:
        return None
    base = raw[0] | (raw[1] << 8)
    sounding = [OPEN_STRING_MIDI[i] + base + f
                for i, f in enumerate(raw[2:8]) if f < NOT_PLAYED]
    if not sounding:
        return None
    midi = min(sounding)
    return spelling_of(midi) | {'midi': midi}


def root_of(msg, fret_info):
    """The chord root of a type 0x45 symbol: declared index first, shape second.

    `f8` is the source's own root and is present even when no fingering is stored,
    which is what makes the chord symbol displayable at all; the fingering only
    supplies a bass note. Returns {step, alter, octave, midi, source} or None.
    """
    declared = root_from_index(getattr(msg, 'f8', None))
    if declared is not None:
        out = dict(declared)
        out['source'] = 'index'
        # Keep the sounding octave when a shape exists, so the register of the
        # chord is not lost; the octave is not part of the chord's identity.
        shape = root_from_fret_info(fret_info)
        if shape is not None and shape['midi'] % 12 == declared['pc']:
            out['octave'] = shape['octave']
        return out
    shape = root_from_fret_info(fret_info)
    if shape is None:
        return None
    return dict(shape) | {'source': 'fret'}


def spelling_of(midi):
    """Pitch spelling for a MIDI number, without the sounding octave offset."""
    pc = midi % 12
    return {'step': STEP_BY_PC[pc], 'alter': ALTER_BY_PC[pc],
            'octave': midi // 12 - 1}

