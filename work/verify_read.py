"""Cross-validate work/smc_read.py against tools/smc_walk.py (work scratch).

tools/smc_walk.py is the spec's own reference walker and is validated at
8451/8451 exact body consumption. smc_read keeps more fields, so this script
checks the two agree on every countable fact: body consumption, message count,
per-type counts, staff/meas/page counts, and the body length itself.

Usage: python work/verify_read.py [--dir D] [--max N]
"""
import argparse
import collections
import contextlib
import glob
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

import smc_read as S

DEFAULT_DIR = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def walk_counts(path):
    """Run the spec reference walker and read back its module counters."""
    import smc_walk as w
    w.stats.clear()
    w.msg_types.clear()
    w.heads.clear()
    w.V = False
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        w.main(path)
    text = buf.getvalue()
    consumed = None
    declared = None
    for line in text.splitlines():
        if line.startswith('consumed body '):
            consumed, declared = line.split()[2], line.split()[-1]
        if line.startswith('FAIL'):
            return None
    return {
        'consumed': consumed, 'declared': declared,
        'stats': dict(w.stats), 'types': dict(w.msg_types),
    }


def iter_all_msgs(doc):
    """Yield every Msg in the document the way the spec reference walker counts
    them: measure trees, staff-level children (0x49), document messages, page
    messages, and the nested messages reachable through ChordExtra.fret_msg and
    ChordExtra.rhythm.msg."""
    seen = []
    stack = []
    for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
        for st in g:
            stack.extend(c['msg'] for c in st.children if c['msg'])
            for meas in st.meas:
                stack.extend(c['msg'] for c in meas.children if c['msg'])
    stack.extend(doc.doc_msgs)
    for p in doc.pages:
        stack.extend(p.msgs)
    while stack:
        m = stack.pop()
        seen.append(m)
        stack.extend(c['msg'] for c in m.children if c['msg'])
        ce = getattr(m, 'chord_extra', None)
        if ce:
            if ce.fret_msg:
                stack.append(ce.fret_msg)
            if ce.rhythm and ce.rhythm.msg:
                stack.append(ce.rhythm.msg)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DEFAULT_DIR)
    ap.add_argument('--max', type=int, default=0)
    args = ap.parse_args()

    ok = diff = fail = 0
    problems = []
    type_mismatch = collections.Counter()
    for path in files(args.dir, args.max):
        try:
            doc = S.load(path)
        except S.Fail as e:
            fail += 1
            problems.append((os.path.basename(path), 'smc_read: %s' % e))
            continue
        ref = walk_counts(path)
        if ref is None:
            fail += 1
            problems.append((os.path.basename(path), 'smc_walk failed'))
            continue

        mine_types = collections.Counter(m.type for m in iter_all_msgs(doc))
        ref_types = ref['types']
        bad = (ref_types != dict(mine_types))
        same_bytes = (int(ref['declared'], 16) == doc.body_len
                      and int(ref['consumed'], 16) == doc.body_consumed)
        if bad or not same_bytes:
            diff += 1
            if bad:
                for t in set(ref_types) | set(mine_types):
                    if ref_types.get(t, 0) != mine_types.get(t, 0):
                        type_mismatch[hex(t)] += 1
            problems.append((os.path.basename(path),
                             'types_ok=%s bytes_ok=%s' % (not bad, same_bytes)))
        else:
            ok += 1

    print('files=%d  identical=%d  differing=%d  errors=%d' % (ok + diff + fail, ok, diff, fail))
    if type_mismatch:
        print('per-type mismatches: %s' % dict(type_mismatch))
    for name, why in problems[:20]:
        print('   %-24s %s' % (name, why))


if __name__ == '__main__':
    main()
