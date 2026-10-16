"""Test whether ObjectCore `f8` is the chord root index.

`f8` is ObjectCore+0x08 as read on disk.  `docs/unknown-fields.md` records that
for type 0x45 it relates to a memory `obj+0x80` used with an 18-entry spelling
table `C C# Db D D# Eb E F F# Gb G G# Ab A A# Bb B Cb`, whose lookup rule is
`if (9 < idx) octave--` - i.e. the index encodes a pitch class with a spelling.

If `f8` is that index, then a symbol whose FretBoard stores no fingering still
has a recoverable root, and the 16.8% of harmonies that currently emit no
<root> can be fixed.

Tests:
  1. distribution of f8 for symbols WITH a fingering root
  2. how often f8 mod 12 equals the fingering root pitch class
  3. the same for the rootless population: does f8 look like a valid index?
  4. consistency: does every harmony in one file get f8 values that agree with
     the fingering where the fingering exists, and stay in range where it does not?
"""
import argparse
import collections
import io
import json
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_f8.txt'

# The 18-entry spelling table from DAT_101002cc.
SPELL = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb',
         'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B', 'Cb']
SPELL_PC = [0, 1, 1, 2, 2, 3, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11]


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

    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    rooted = []      # (f8, derived, f2, head_len, type_index, root_pc, name)
    rootless = []    # (f8, derived, f2, head_len, type_index, name, info_hex)

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
                    ce = getattr(m, 'chord_extra', None)
                    r = root_from_fret_info(ce.fret_info) if ce else None
                    row = (m.f8, m.derived, m.f2, m.head_len, m.type_index,
                           (ce.name if ce else b''))
                    if r:
                        rooted.append(row + (r['midi'] % 12,))
                    else:
                        rootless.append(row + ((ce.info.hex(' ') if ce else ''),))
        if (i + 1) % 2000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('=' * 78)
    w('SAMPLES')
    w('=' * 78)
    w('rooted   : %d' % len(rooted))
    w('rootless : %d' % len(rootless))

    w('')
    w('=' * 78)
    w('1. f8 DISTRIBUTION FOR METRIC CHORDS (roots that do resolve)')
    w('=' * 78)
    w('f8 values            : %s' % collections.Counter(r[0] for r in rooted).most_common(20))
    w('')
    w('f8 as spelling index, where f8 < 18:')
    sub = [r for r in rooted if r[0] is not None and r[0] < 18]
    w('   count              : %d of %d' % (len(sub), len(rooted)))
    if sub:
        ok = sum(1 for r in sub if SPELL_PC[r[0]] == r[6])
        w('   spelling pc == fingering root pc : %d (%.1f%%)'
          % (ok, 100.0 * ok / len(sub)))
        w('')
        w('   f8 -> (spelling pc, fingering root pc) confusion, top rows:')
        conf = collections.Counter((r[0], SPELL_PC[r[0]], r[6]) for r in sub)
        for (idx, spc, rpc), n in conf.most_common(20):
            w('      f8=%-3d %-3s pc=%-3d root_pc=%-3d n=%d %s'
              % (idx, SPELL[idx], spc, rpc, n, 'OK' if spc == rpc else '<<'))

    w('')
    w('=' * 78)
    w('2. f8 vs the fingering root as a plain pitch class (f8 % 12)')
    w('=' * 78)
    both = [r for r in rooted if r[0] is not None]
    ok = sum(1 for r in both if r[0] % 12 == r[6])
    w('match: %d / %d = %.2f%%' % (ok, len(both), 100.0 * ok / max(len(both), 1)))

    w('')
    w('=' * 78)
    w('3. THE ROOTLESS POPULATION: does f8 look like a root index there?')
    w('=' * 78)
    w('f8 values            : %s' % collections.Counter(r[0] for r in rootless).most_common(20))
    w('f8 mod 12 histogram : %s' % collections.Counter(r[0] % 12 for r in rootless if r[0] is not None).most_common(14))
    inrange = [r for r in rootless if r[0] is not None and r[0] < 18]
    w('f8 < 18              : %d of %d' % (len(inrange), len(rootless)))
    w('')
    w('   if f8 < 18 it names a spelled root:')
    for (idx, n) in collections.Counter(r[0] for r in inrange).most_common(20):
        w('      f8=%-3d -> %-3s (pc %d)   n=%d' % (idx, SPELL[idx], SPELL_PC[idx], n))

    w('')
    w('=' * 78)
    w('4. OTHER CORE FIELDS AGAINST THE ROOT')
    w('=' * 78)
    for fi, label in ((1, 'derived'), (2, 'f2'), (3, 'head_len'), (4, 'type_index')):
        w('  %s' % label)
        w('     rooted   : %s' % collections.Counter(r[fi] for r in rooted).most_common(8))
        w('     rootless : %s' % collections.Counter(r[fi] for r in rootless).most_common(8))

    w('')
    w('=' * 78)
    w('5. CONSISTENCY TEST: f8 in files where SOME chords resolve')
    w('=' * 78)
    # A file where both populations exist is the strongest evidence: the same
    # field must be the same quantity in both.
    for target in ('130RVS-012.smc', '110SSS-001.smc', '130RVS-016.smc'):
        path = None
        for dirpath, _, names in os.walk(SONGS):
            for nm in names:
                if nm.lower() == target.lower():
                    path = os.path.join(dirpath, nm)
        if not path:
            continue
        doc = S.load(path)
        w('')
        w('  %s' % target)
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                for m in walk(meas):
                    if m.type != 0x45:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    r = root_from_fret_info(ce.fret_info) if ce else None
                    w('     m%-4d f8=%-6s f2=%-6d head_len=%-4d derived=%-4d type_index=%-4d '
                      'name=%-10r root=%-4s'
                      % (mi + 1, m.f8, m.f2, m.head_len, m.derived, m.type_index,
                         ((ce.name if ce else b'').decode('latin1')),
                         (r['midi'] % 12) if r else 'NONE'))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
