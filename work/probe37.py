"""Why 16.8% of chord symbols have no derivable root.

`fret_info = 0000 fe fe fe fe fe fe 00*8` means "no string played", i.e. the
symbol has no stored fingering, so reading the shape gives no root.  These are
also the symbols with an empty `name`, so the source stores a chord whose suffix
is default (major) and whose root is nowhere in the fingering.

Tests, in order of what would settle it:

  A. For symbols WITH a fingering, how often does the anchored note's pitch class
     equal the fingering's root?  If that holds strongly, the melody note at the
     symbol is the root and can serve as the fallback.
  B. For symbols WITHOUT a fingering, what does the numbered/spelling field
     (`info`) look like, and is there any other byte in the 0x45 head that varies
     with something root-like?
  C. Do these symbols carry the embedded rhythm marker?  A symbol with neither a
     name nor a fingering may be a pure accompaniment style marker rather than a
     real chord, in which case emitting a bare "<kind>major</kind>" is wrong and
     it should be treated differently.
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
OUT = r'C:\research\samilpo\work\out_root_why.txt'


def walk(node):
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is None:
            continue
        yield m
        for x in walk(m):
            yield x


def main():
    import smc_read as S
    import smc2ir
    from fret import root_from_fret_info

    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    # ---- scan the IR: root known/unknown, anchor pc, name, rhythm presence
    known = []          # (root_pc, anchor_pc, name)
    unknown = []        # dict
    for i, path in enumerate(files):
        try:
            buf = io.StringIO()
            smc2ir.convert(path, opts, buf)
        except Exception:
            continue
        for line in buf.getvalue().splitlines():
            if '"harmony"' not in line:
                continue
            o = json.loads(line)
            am = o.get('anchor_midi')
            apc = (am % 12) if am is not None else None
            r = o.get('root')
            if r and r.get('midi') is not None:
                known.append((r['midi'] % 12, apc, o.get('name') or ''))
            else:
                unknown.append((os.path.basename(path), o, apc))
        if (i + 1) % 2000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('=' * 78)
    w('A. symbols WITH a fingering: is the anchored note the root?')
    w('=' * 78)
    both = [(r, a) for r, a, _ in known if a is not None]
    w('symbols with a root       : %d' % len(known))
    w('   also anchored          : %d' % len(both))
    agree = sum(1 for r, a in both if r == a)
    w('   anchor pc == root pc   : %d (%.1f%%)' % (agree, 100.0 * agree / max(len(both), 1)))
    agreed = sum(1 for r, a, _ in known if a is not None and r == a)
    w('   -> anchor is the root in %.1f%% of cases, so it is NOT a safe fallback'
      % (100.0 * agreed / max(len(both), 1)))
    d = collections.Counter((a - r) % 12 for r, a in both)
    w('   interval anchor-root histogram: %s' % d.most_common(12))

    w('')
    w('=' * 78)
    w('B. symbols WITHOUT a fingering')
    w('=' * 78)
    w('count                     : %d' % len(unknown))
    w('   anchored               : %d' % sum(1 for _, o, a in unknown if o.get('anchored')))
    w('   anchor pc histogram    : %s'
      % collections.Counter(a for _, _, a in unknown if a is not None).most_common())
    w('   name histogram         : %s'
      % collections.Counter(o.get('name') or '' for _, o, _ in unknown).most_common(10))
    w('   kind_text histogram    : %s'
      % collections.Counter(o.get('kind_text') or '' for _, o, _ in unknown).most_common(10))
    w('   has_rhythm histogram   : %s'
      % collections.Counter((o.get('ext') or {}).get('has_rhythm') for _, o, _ in unknown).most_common())
    w('   info_hex               : %s'
      % collections.Counter((o.get('ext') or {}).get('info_hex') or '' for _, o, _ in unknown).most_common(10))
    w('   fret_base              : %s'
      % collections.Counter((o.get('ext') or {}).get('fret_base') for _, o, _ in unknown).most_common())

    w('')
    w('   how many of each come from a file that ALSO has a rhythm marker:')
    # a file-level view: do these symbols ride along with accompaniment styles?
    counts = collections.Counter()
    for name, o, a in unknown:
        counts[name] += 1
    w('   files containing them  : %d' % len(counts))
    w('   top files              : %s' % counts.most_common(12))

    w('')
    w('   first 25 in detail:')
    for name, o, a in unknown[:25]:
        ext = o.get('ext') or {}
        w('      %-24s m%-4s on=%-5d name=%-12r kind=%-8r anchor=%-5s info=%-20s fret=%s rhy=%s'
          % (name, o.get('meas'), o.get('on'), o.get('name') or '',
             o.get('kind_text') or '', a, ext.get('info_hex') or '',
             ext.get('fret_base'), ext.get('has_rhythm')))

    w('')
    w('=' * 78)
    w('C. same symbols, with the raw 0x45 head and its rhythm attachment')
    w('=' * 78)
    # re-read a few source files and dump the node
    shown = 0
    for path in files:
        base = os.path.basename(path)
        if base not in ('130RVS-012.smc', '130RVS-016.smc', '130RVS-008.smc'):
            continue
        doc = S.load(path)
        w('')
        w('  %s' % base)
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                for m in walk(meas):
                    if m.type != 0x45:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    rr = root_from_fret_info(ce.fret_info) if ce else None
                    w('    m%-4d key=%-5d head_len=%-4d head=%s'
                      % (mi + 1, m.key, m.head_len, m.head[:32].hex(' ')))
                    w('           name=%-14r info=%-26s fret_info=%s'
                      % ((ce.name if ce else b''), (ce.info.hex(' ') if ce else ''),
                         (ce.fret_info.hex(' ') if ce else '')))
                    w('           root=%s has_rhythm=%s fretboard=%s'
                      % (rr, ce.has_rhythm if ce else None,
                         bool(getattr(ce, 'fretboard', None))))
                    shown += 1
        if shown > 40:
            break

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
