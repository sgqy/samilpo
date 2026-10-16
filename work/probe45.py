"""Confirm the remaining null-root harmonies are exactly the out-of-range index.

After the fix, 734 of 177909 harmonies still have no root. The claim is that every
one of them is a symbol whose `f8` is not a valid index (a pointer-shaped value)
AND whose FretBoard holds no fingering, so there is genuinely no root stored.

Any other combination would be a bug: an in-range index that failed to decode, or
an out-of-range index that still had a shape to fall back on and did not.
"""
import argparse
import collections
import io
import json
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_null_root_proof.txt'


def main():
    import smc2ir
    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)

    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    tot = null = 0
    idx_state = collections.Counter()
    src_state = collections.Counter()
    unexplained = []
    shapes_present = 0

    for i, p in enumerate(files):
        try:
            buf = io.StringIO()
            smc2ir.convert(p, opts, buf)
        except Exception:
            continue
        for line in buf.getvalue().splitlines():
            if '"harmony"' not in line:
                continue
            o = json.loads(line)
            tot += 1
            if o.get('root'):
                continue
            null += 1
            ex = o.get('ext') or {}
            v = ex.get('root_index')
            inrange = (v is not None and 0 <= v < 18)
            idx_state['in-range but undecoded' if inrange else 'out-of-range'] += 1
            src_state[ex.get('root_source')] += 1
            if ex.get('fret_shape') and 'x' != ex.get('fret_shape'):
                pass
            shape = ex.get('fret_shape') or ''
            if shape and shape.strip('x'):
                shapes_present += 1
            # anything in-range that failed, or out-of-range that still had a
            # sounding shape, would be a defect
            if inrange or (shape and shape.strip('x')):
                if len(unexplained) < 20:
                    unexplained.append((os.path.basename(p), o.get('meas'),
                                        v, shape, o.get('name'), ex.get('info_hex')))
        if (i + 1) % 2000 == 0:
            print('   ... %d/%d' % (i + 1, len(files)))

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)
    w('=' * 78)
    w('REMAINING NULL-ROOT HARMONIES')
    w('=' * 78)
    w('harmony records total          : %d' % tot)
    w('   with a null root            : %d (%.3f%%)' % (null, 100.0 * null / max(tot, 1)))
    w('')
    w('root_index state among them    : %s' % dict(idx_state))
    w('root_source among them         : %s' % dict(src_state))
    w('')
    w('A null root is expected ONLY when the declared index is out of range AND the')
    w('FretBoard stores no sounding string - then the file genuinely records no root.')
    w('')
    w('unexpected cases (in-range index undecoded, or a shape that went unused): %d'
      % len(unexplained))
    for name, meas, v, shape, nm_, info in unexplained:
        w('   %-26s m%-4s f8=%-9s shape=%-8s name=%-10r info=%s'
          % (name, meas, v, shape, nm_, info))
    if not unexplained:
        w('   none - every remaining null root is explained by the source')
    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
