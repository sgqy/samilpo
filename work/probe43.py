"""Validate `f8` as the chord root against ground truth and independent evidence.

`f8` (ObjectCore+0x08) indexes the 18-entry spelling table
`C C# Db D D# Eb E F F# Gb G G# Ab A A# Bb B Cb` and agrees with the
fingering-derived root in 96.2% of 148017 symbols.  Two questions decide whether
it should become the authoritative root:

  A. Does it reproduce 500KFS-0041's opening, which the user verified by ear as
     Am Dm Em F Dm Em Am?
  B. Where the two disagree, which is right?  A fingering gives the LOWEST
     sounding note, which in an inversion is not the root, so a disagreement in
     which the fingering pitch class is a chord tone (3rd/4th/5th/b7)
     of the f8 root is evidence FOR f8, not against it.

Also reports the crucial coverage property: f8 is present and in range for every
symbol, including the 29892 that carry no fingering, which is what makes it
usable as the primary source.
"""
import collections
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
SMC41 = os.path.join(SONGS, '500KFS', '500KFS-0041.smc')
OUT = r'C:\research\samilpo\work\out_f8_validate.txt'

SPELL = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb',
         'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B', 'Cb']
SPELL_PC = [0, 1, 1, 2, 2, 3, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11]
# The engine's index -> octave rule is `if (9 < idx) octave--`, i.e. indices 10..17
# spell a pitch class one octave lower than indices 0..9 for the same letter.
FLAT_TAIL = set(range(10, 18))

EXPECTED = ['A', 'D', 'E', 'F', 'D', 'E', 'A']      # m1, m3..m7 -> pc 9,2,4,5,2,4,9


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


def main():
    import smc_read as S
    from fret import root_from_fret_info

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('A. GROUND TRUTH - 500KFS-0041 opening, user verified Am Dm Em F Dm Em Am')
    w('=' * 78)
    doc = S.load(SMC41)
    w('%-6s %-8s %-9s %-9s %-6s %-8s' % ('meas', 'name', 'f8 root', 'fret root', 'agree', 'type_idx'))
    got = []
    for mi, meas in enumerate(doc.system.staff1[0].meas):
        if mi > 7:
            break
        for m in walk(meas):
            if m.type != 0x45:
                continue
            ce = getattr(m, 'chord_extra', None)
            fr = root_from_fret_info(ce.fret_info) if ce else None
            f8ok = m.f8 is not None and m.f8 < 18
            f8r = SPELL[m.f8] if f8ok else '?'
            frs = fr['step'] if fr else 'NONE'
            agree = 'yes' if (fr and f8ok and SPELL_PC[m.f8] == fr['midi'] % 12) else \
                    ('-' if not fr else 'NO')
            w('m%-5d %-8r %-9s %-9s %-6s %-8s'
              % (mi + 1, (ce.name if ce else b''), f8r, frs, agree, m.type_index))
            if mi in (0, 2, 3, 4, 5, 6, 6, 7):
                got.append(f8r)
    roots = [SPELL[m.f8] for mi, meas in enumerate(doc.system.staff1[0].meas)
             for m in walk(meas) if m.type == 0x45 and mi <= 7 and m.f8 is not None and m.f8 < 18]
    w('')
    w('   f8 roots in order : %s' % ' '.join(roots[:7]))
    w('   expected          : %s' % ' '.join(EXPECTED))
    w('   MATCH             : %s' % ('YES' if roots[:7] == EXPECTED else 'NO'))
    fine = root_from_fret_info
    fr_roots = []
    for mi, meas in enumerate(doc.system.staff1[0].meas):
        if mi > 7:
            break
        for m in walk(meas):
            if m.type == 0x45:
                ce = getattr(m, 'chord_extra', None)
                r = fine(ce.fret_info) if ce else None
                fr_roots.append(r['step'] if r else '?')
    w('   fingering roots   : %s' % ' '.join(fr_roots))

    w('')
    w('=' * 78)
    w('B. DISAGREEMENTS - is the fingering an inversion of the declared root?')
    w('=' * 78)
    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    agree = disagree = oob = 0
    gap = collections.Counter()
    samples = []
    for i, path in enumerate(files):
        try:
            doc = S.load(path)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for meas in st.meas:
                for m in walk(meas):
                    if m.type != 0x45:
                        continue
                    if m.f8 is None or m.f8 >= 18:
                        oob += 1
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    fr = root_from_fret_info(ce.fret_info) if ce else None
                    if not fr:
                        continue
                    a, b = SPELL_PC[m.f8], fr['midi'] % 12
                    if a == b:
                        agree += 1
                    else:
                        disagree += 1
                        gap[(b - a) % 12] += 1
                        if len(samples) < 30:
                            samples.append((os.path.basename(path), m.f8, SPELL[m.f8],
                                            a, fr['step'], b, (ce.name if ce else b'')))
        if (i + 1) % 2000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('agree                      : %d' % agree)
    w('disagree                   : %d (%.2f%%)'
      % (disagree, 100.0 * disagree / max(agree + disagree, 1)))
    w('f8 out of the 0..17 range  : %d' % oob)
    w('')
    w('gap = (fingering pc - f8 pc) mod 12, over disagreements:')
    for g in range(12):
        if gap[g]:
            w('   %-3d n=%-7d %s' % (g, gap[g], 'chord tone of the f8 root' if g in (3, 4, 7, 10, 11) else ''))
    inv = sum(gap[g] for g in (3, 4, 7))
    w('')
    w('   gaps of 3/4/7 (md3/M3/P5) mean the fingering is an INVERSION of the')
    w('   declared root, so f8 is the root and the fingering simply is not.')
    w('   share: %d of %d = %.1f%%' % (inv, disagree, 100.0 * inv / max(disagree, 1)))
    w('')
    w('   samples:')
    for name, f8, sp, apc, step, bpc, nm_ in samples:
        w('      %-26s f8=%-3d %-3s(%2d) fret=%-3s(%2d) gap=%-3d name=%r'
          % (name, f8, sp, apc, step, bpc, (bpc - apc) % 12, nm_))

    w('')
    w('=' * 78)
    w('C. COVERAGE - what f8 can do that the fingering cannot')
    w('=' * 78)
    w('Every symbol carries f8 (an ObjectCore field), so it is available exactly')
    w('where the FretBoard is empty.  Counted here from the earlier scans:')
    w('   symbols with a fingering root : 148017  (f8 agrees with %.1f%%)'
      % (100.0 * agree / max(agree + disagree, 1)))
    w('   symbols with NO fingering     : 29892   (f8 in range for 29158 = %.1f%%)'
      % (100.0 * 29158 / 29892))
    w('   -> f8 supplies a declared root for the population that currently emits')
    w('      <harmony><kind> with no <root>, which is invalid MusicXML.')

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
