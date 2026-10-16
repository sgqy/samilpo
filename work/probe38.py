"""Hunt for the root of a chord symbol that carries no fingering.

`fret_info = 0000 fe fe fe fe fe fe` means no string is played, so the fingering
cannot give a root, yet the program must display "C" / "Dm" - so the root is
stored somewhere else.  This compares rootless symbols against rooted ones from
the same file and looks for the byte that carries it.

Candidates examined:
  * MsgHdr fields (type_index, head_type, f03, f04, scale, style, bracket, dots)
  * the whole 0x45 head, byte by byte, as a rootless-vs-rooted discriminator
  * the known spelling-table index: if the head holds an index into the 18-entry
    table C C# Db D D# Eb E F F# Gb G G# Ab A A# Bb B Cb, it is 0..17 and its
    value must equal the fingering root's pitch class on symbols that have both.
"""
import argparse
import collections
import io
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_root_hunt.txt'


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
    from fret import root_from_fret_info

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    rooted = []      # (path, meas, msg, root_pc, head)
    rootless = []
    for path in files:
        try:
            doc = S.load(path)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                for m in walk(meas):
                    if m.type != 0x45:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    r = root_from_fret_info(ce.fret_info) if ce else None
                    rec = (path, mi + 1, m, m.head)
                    if r:
                        rooted.append((rec, r['midi'] % 12))
                    else:
                        rootless.append(rec)
        if len(rootless) > 4000 and len(rooted) > 4000:
            break

    w('=' * 78)
    w('HEADER FIELD COMPARISON')
    w('=' * 78)
    w('rooted symbols sampled   : %d' % len(rooted))
    w('rootless symbols sampled : %d' % len(rootless))

    def hdr_stats(group, attr):
        return collections.Counter(
            getattr(m, attr) for (_, _, m, _) in group if hasattr(m, attr))

    for attr in ('type_index', 'head_type', 'f03', 'f04', 'scale', 'style',
                 'bracket', 'dots', 'voice', 'stem_flag', 'f2', 'derived',
                 'head_len', 'child_count'):
        a = hdr_stats([r for r, _ in rooted], attr)
        b = hdr_stats(rootless, attr)
        w('')
        w('  %s' % attr)
        w('     rooted   : %s' % a.most_common(8))
        w('     rootless : %s' % b.most_common(8))
        sa, sb = set(a), set(b)
        if sa and sb and not (sa & sb):
            w('     *** fully separable ***')

    w('')
    w('=' * 78)
    w('HEAD BYTE COMPARISON (rooted vs rootless, per offset)')
    w('=' * 78)
    hl_r = collections.Counter(len(h) for (_, _, _, h), _ in rooted)
    hl_z = collections.Counter(len(h) for _, _, _, h in rootless)
    w('head lengths rooted   : %s' % hl_r.most_common(6))
    w('head lengths rootless : %s' % hl_z.most_common(6))

    # Only compare symbols whose head is at least 100 bytes (the full form).
    R = [h for (_, _, _, h), _ in rooted if len(h) >= 0x64]
    Z = [h for _, _, _, h in rootless if len(h) >= 0x64]
    w('comparable pairs: rooted %d, rootless %d' % (len(R), len(Z)))
    if R and Z:
        for o in range(0x64):
            a = collections.Counter(h[o] for h in R)
            b = collections.Counter(h[o] for h in Z)
            sa, sb = set(a), set(b)
            if sa and sb and not (sa & sb):
                w('   +0x%02X  rooted=%s  rootless=%s   *** SEPARABLE ***'
                  % (o, a.most_common(4), b.most_common(4)))
            elif sa and sb:
                ma = sum(k * v for k, v in a.items()) / sum(a.values())
                mb = sum(k * v for k, v in b.items()) / sum(b.values())
                if abs(ma - mb) > 25:
                    w('   +0x%02X  mean rooted=%.1f rootless=%.1f' % (o, ma, mb))

    w('')
    w('=' * 78)
    w('DOES ANY HEAD BYTE EQUAL THE FINGERING ROOT PITCH CLASS?')
    w('=' * 78)
    # For rooted symbols with a full head, check each offset for a value whose
    # relation to the true root PC is constant.
    R2 = [(h, pc) for (_, _, _, h), pc in rooted if len(h) >= 0x64]
    w('samples: %d' % len(R2))
    best = []
    for o in range(0x64):
        vals = [h[o] for h, _ in R2]
        if len(set(vals)) < 2:
            continue
        # is it the pitch class?
        hit = sum(1 for (h, pc) in R2 if h[o] % 12 == pc)
        hit18 = sum(1 for (h, pc) in R2 if h[o] < 18 and ((h[o]) % 12) == pc)
        best.append((hit / len(R2), o, 'mod12', hit))
        best.append((hit18 / len(R2), o, 'idx<18', hit18))
    best.sort(reverse=True)
    w('top offsets whose value tracks the root pitch class:')
    for frac, o, kind, hit in best[:15]:
        w('   +0x%02X  %s  match=%.1f%%  (%d/%d)' % (o, kind, 100 * frac, hit, len(R2)))

    w('')
    w('   direct value histogram at each offset that scored above 30%:')
    seen = set()
    for frac, o, kind, hit in best:
        if frac < 0.30 or o in seen:
            continue
        seen.add(o)
        w('   +0x%02X values: %s' % (o, collections.Counter(h[o] for h, _ in R2).most_common(8)))
        w('        true roots: %s' % collections.Counter(pc for _, pc in R2).most_common(12))

    w('')
    w('=' * 78)
    w('RAW HEADS: one rootless file in full')
    w('=' * 78)
    w('130RVS-016.smc - every 0x45 with its full head')
    for path in files:
        if os.path.basename(path) != '130RVS-016.smc':
            continue
        doc = S.load(path)
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            for mi, meas in enumerate(st.meas):
                for m in walk(meas):
                    if m.type != 0x45:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    w('   m%-4d name=%-8r info=%-12s type_index=%-4d head_type=%-4d f03=%-4d f04=%-4d style=%d'
                      % (mi + 1, (ce.name if ce else b''), (ce.info.hex(' ') if ce else ''),
                         m.type_index, m.head_type, m.f03, m.f04, m.style))
                    h = m.head
                    for i in range(0, len(h), 16):
                        w('        +0x%02X  %s' % (i, h[i:i + 16].hex(' ')))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
