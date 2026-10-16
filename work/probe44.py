"""Arbitrate f8 vs the fingering using the chord shape's pitch-class set.

`f8` (ObjectCore+0x08) indexes an 18-entry spelling table and agrees with the
fingering-derived root in 96.2% of 148017 symbols.  Deciding which is the root
matters because f8 covers the 29892 symbols whose FretBoard is empty.

The arbiter does not guess. The name suffix gives the chord quality (`m`, `7`,
`(major)`, `m7`, `9`, ...), which determines the set of pitch classes the chord
may contain. The fingering gives every sounding pitch of the shape. So for each
disagreement both candidate roots are scored by how many of the shape's pitch
classes the resulting chord can explain:

    f8 root + quality   vs   fingering root + quality

A shape is a real chord of one of them; the one that explains the shape is right.
Where the fingering root wins, using f8 would be a regression; where f8 wins, the
fingering was reading an inversion's bass as the root.
"""
import collections
import os
import re
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_shape_arbiter.txt'

SPELL = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb',
         'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B', 'Cb']
SPELL_PC = [0, 1, 1, 2, 2, 3, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11]

# Quality -> intervals above the root. Derived from the suffix the source stores;
# only the qualities that actually occur are listed, the rest stay unknown and
# are skipped rather than guessed.
QUALITY = {
    '': (0, 4, 7),
    'major': (0, 4, 7),
    'minor': (0, 3, 7),
    'dominant': (0, 4, 7, 10),
    'minor-seventh': (0, 3, 7, 10),
    'major-seventh': (0, 4, 7, 11),
    'minor-sixth': (0, 3, 7, 9),
    'major-sixth': (0, 4, 7, 9),
    'dominant-ninth': (0, 4, 7, 10, 2),
    'dominant-ninth-': (0, 4, 7, 10, 2),
    'suspended-fourth': (0, 5, 7),
    'suspended-second': (0, 2, 7),
    'diminished': (0, 3, 6),
    'augmented': (0, 4, 8),
    'minor-ninth': (0, 3, 7, 10, 2),
    'major-ninth': (0, 4, 7, 11, 2),
    'half-diminished': (0, 3, 6, 10),
    'diminished-seventh': (0, 3, 6, 9),
}

NOT_PLAYED = 0xFE
OPEN = (40, 45, 50, 55, 59, 64)


def walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        for c in getattr(n, 'children', ()) or ():
            m = c.get('msg') if isinstance(c, dict) else c
            if m is None:
                continue
            yield m
            stack.append(m)


def shape_pcs(raw):
    """Pitch classes of every sounding string in the shape."""
    if not raw or len(raw) < 8:
        return []
    base = raw[0] | (raw[1] << 8)
    out = []
    for i, fr in enumerate(raw[2:8]):
        if fr >= NOT_PLAYED:
            continue
        out.append((OPEN[i] + base + fr) % 12)
    return out


def main():
    import smc_read as S
    import smc2ir
    from fret import root_from_fret_info

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    f8_wins = 0
    fr_wins = 0
    both = 0
    neither = 0
    unknown_q = 0
    examples = collections.defaultdict(list)
    gap_by_winner = collections.defaultdict(collections.Counter)

    for i, path in enumerate(files):
        try:
            doc = S.load(path)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for meas in st.meas:
                for m in walk(meas):
                    if m.type != 0x45 or m.f8 is None or m.f8 >= 18:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    if not ce:
                        continue
                    fr = root_from_fret_info(ce.fret_info)
                    if not fr:
                        continue
                    f8pc = SPELL_PC[m.f8]
                    frpc = fr['midi'] % 12
                    if f8pc == frpc:
                        continue
                    name = (ce.name or b'').decode('latin1')
                    kind = smc2ir.kind_from_surfix(name)
                    iv = QUALITY.get(kind)
                    if not iv:
                        unknown_q += 1
                        continue
                    pcs = shape_pcs(ce.fret_info)
                    if not pcs:
                        continue
                    set_f8 = {(f8pc + k) % 12 for k in iv}
                    set_fr = {(frpc + k) % 12 for k in iv}
                    nf8 = sum(1 for p in pcs if p in set_f8)
                    nfr = sum(1 for p in pcs if p in set_fr)
                    gap = (frpc - f8pc) % 12
                    if nf8 > nfr:
                        f8_wins += 1
                        gap_by_winner['f8'][gap] += 1
                        if len(examples['f8']) < 12:
                            examples['f8'].append((os.path.basename(path), m.f8,
                                                   SPELL[m.f8], f8pc, fr['step'], frpc,
                                                   name, kind, nf8, nfr, len(pcs)))
                    elif nfr > nf8:
                        fr_wins += 1
                        gap_by_winner['fret'][gap] += 1
                        if len(examples['fret']) < 12:
                            examples['fret'].append((os.path.basename(path), m.f8,
                                                     SPELL[m.f8], f8pc, fr['step'], frpc,
                                                     name, kind, nf8, nfr, len(pcs)))
                    elif nf8 == nfr and nf8 == len(pcs):
                        both += 1
                    else:
                        neither += 1
        if (i + 1) % 2000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('=' * 78)
    w('DECIDED DISAGREEMENTS (only pairs where the quality is known)')
    w('=' * 78)
    w('f8 root explains the shape better : %d' % f8_wins)
    w('fingering explains it better      : %d' % fr_wins)
    w('both explain every shape tone     : %d  (undecided, not a conflict)' % both)
    w('neither explains it fully         : %d' % neither)
    w('skipped, unlisted quality         : %d' % unknown_q)
    tot = f8_wins + fr_wins
    if tot:
        w('')
        w('   among decided cases f8 is right %.1f%% of the time'
          % (100.0 * f8_wins / tot))

    w('')
    w('gap (fingering pc - f8 pc) by winner:')
    for who in ('f8', 'fret'):
        w('   %s: %s' % (who, sorted(gap_by_winner[who].items())))

    for who in ('f8', 'fret'):
        w('')
        w('=' * 78)
        w('EXAMPLES WHERE %s IS RIGHT' % who.upper())
        w('=' * 78)
        w('%-26s %-6s %-6s %-6s %-14s %-20s %s'
          % ('file', 'f8', 'f8pc', 'fretpc', 'name', 'kind', 'score f8/fret (shape tones)'))
        for (name, f8, sp, apc, step, bpc, nm_, kind, nf8, nfr, nsh) in examples[who]:
            w('%-26s %-6d %-6d %-6d %-14r %-20s %d/%d (of %d)'
              % (name, f8, apc, bpc, nm_, kind, nf8, nfr, nsh))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
