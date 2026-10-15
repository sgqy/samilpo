"""Classify unresolved span endpoints across the corpus (work scratch).

smc2ir reports a span as unresolved when either endpoint key is absent from the
part's key table. This script groups the failures so the cause can be told
apart: a key that is 0 (deliberately cleared by CSMSystem::Read), a key from
another staff or part, a key outside any measure, or a genuinely dangling
reference.

Usage: python work/probe10.py [--dir D] [--max N]
"""
import argparse
import collections
import glob
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import batch
import smc2ir
import smc_read as S
from probe_smc import walk_msgs

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=SONGS)
    ap.add_argument('--max', type=int, default=0)
    args = ap.parse_args()

    opts = batch.options()
    reasons = collections.Counter()
    per_file = collections.Counter()
    examples = collections.defaultdict(list)
    n_span = n_bad = 0
    for path in files(args.dir, args.max):
        buf = io.StringIO()
        try:
            smc2ir.convert(path, opts, buf)
        except Exception:
            continue
        for line in buf.getvalue().splitlines():
            r = __import__('json').loads(line)
            if r.get('kind') != 'span':
                continue
            n_span += 1
            if r['resolved']:
                continue
            n_bad += 1
            a, b = r['raw']['a_key'], r['raw']['b_key']
            if a == 0 and b == 0:
                kind = 'both keys 0'
            elif a == 0 or b == 0:
                kind = 'one key 0'
            elif a == 0xFFFFFFFF or b == 0xFFFFFFFF or a > 0xFFFFFF00 or b > 0xFFFFFF00:
                kind = 'negative/high key'
            else:
                kind = 'key not in part'
            reasons[(r['k'], kind)] += 1
            per_file[os.path.basename(path)] += 1
            if len(examples[kind]) < 3:
                examples[kind].append((os.path.basename(path), r['k'], a, b))
    print('spans=%d unresolved=%d (%.2f%%)' % (n_span, n_bad, 100.0 * n_bad / max(n_span, 1)))
    print('by kind and cause:')
    for k, v in sorted(reasons.items()):
        print('   %-12s %-20s %d' % (k[0], k[1], v))
    print()
    print('files affected: %d' % len(per_file))
    for f, c in per_file.most_common(10):
        print('   %-26s %d' % (f, c))
    print()
    for kind, rows in examples.items():
        for f, k, a, b in rows:
            print('   %-20s %-26s %-6s a=%-12s b=%s' % (kind, f, k, a, b))


if __name__ == '__main__':
    main()
