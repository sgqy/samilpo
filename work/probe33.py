"""Residual-risk checks behind the three reports.

  A. 8059 harmony records have no anchor note (4.53%). Their onset falls back to
     0, so the first thing to prove is that they still carry a root - a rootless
     harmony renders as a bare suffix and looks like a missing chord. Prints how
     many are rootless and what their onsets look like.

  B. Where a measure writes no chord symbol, the accompaniment still sounds the
     chord already in force. That is why 500KFS-0041's closing measures carry
     sounding A-minor harmony with no printed symbol. Confirms the carry-forward
     rule and shows whether a chord is ever absent entirely (nothing in force),
     which would be a genuine gap in the resolution.
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SMC41 = os.path.join(r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS',
                     '500KFS-0041.smc')
OUT = r'C:\research\samilpo\work\out_residual.txt'


def main():
    import smc_read as S
    import smc2ir
    import accomp

    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('A. UNANCHORED HARMONIES - do they still carry a root?')
    w('=' * 78)
    buf = io.StringIO()
    smc2ir.convert(SMC41, opts, buf)
    rs = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    har = [r for r in rs if r.get('kind') == 'harmony']
    un = [r for r in har if not r.get('anchored')]
    w('500KFS-0041 harmonies        : %d' % len(har))
    w('   without an anchor note   : %d' % len(un))
    w('   of those, with a root    : %d' % sum(1 for r in un if r.get('root')))
    w('   of those, rootless       : %d' % sum(1 for r in un if not r.get('root')))
    w('   onsets seen             : %s' % sorted({r['on'] for r in un}))
    for r in un[:8]:
        w('      m%-4d on=%-5d name=%-10r root=%s anchor_midi=%s'
          % (r['meas'], r['on'], r['name'], r['root'], r.get('anchor_midi')))

    w('')
    w('=' * 78)
    w('B. ACCOMPANIMENT CHORD CARRY-FORWARD')
    w('=' * 78)
    doc = S.load(SMC41)
    cod = S.load_cod()
    parts, notes, measures, stats = accomp.build(doc, cod, opts)
    w('stats                    : %s' % stats)
    # which measures hold a printed chord, and which do not
    printed = {r['meas'] for r in har}
    allm = sorted({n['meas'] for n in notes})
    w('measures with a printed chord : %d' % len(printed))
    w('measures with accomp notes    : %d' % len(allm))
    bare = [m for m in allm if m not in printed]
    w('measures sounding with NO printed chord : %d' % len(bare))
    w('   %s' % bare[:40])
    w('')
    w('the closing measures, as the accompaniment emits them:')
    for n in notes:
        if n.get('meas', 0) >= 107:
            w('   m%-4d %-4s voice=%s on=%-5d dur=%-5d midi=%-4s %s%s'
              % (n['meas'], n['part'], n['voice'], n['on'], n['dur'], n['midi'],
                 n['step'] or '', n['octave'] if n['octave'] is not None else ''))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
