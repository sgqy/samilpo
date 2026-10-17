"""Per-file index usage and in-order mark sequences.

Bowing marks alternate down/up along a passage; articulation marks cluster on
selected notes.  Printing the ordered sequence of one index against the notes it
sits on separates the two.
"""
import collections
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'

MARKTB = [0x00, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x62, 0x56, 0x57, 0x58, 0x59, 0x5c,
          0x65, 0x55, 0x4e, 0x2b, 0x2c, 0x5a, 0x5b, 0x51, 0x52, 0x50, 0x4f, 0x54,
          0x53, 0x73, 0x75, 0x74, 0x76, 0x63, 0x64, 0x7d, 0x7c, 0x77, 0x79, 0x78,
          0x68, 0x70, 0x6f, 0x71, 0x7a, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0x4b,
          0x4a, 0xa9, 0xaa]


def iter_all(doc):
    stack = [(doc.system, 'system')]
    for pg in doc.pages:
        stack.append((pg, 'page'))
    while stack:
        node, kind = stack.pop()
        for c in getattr(node, 'children', ()) or ():
            m = c.get('msg') if isinstance(c, dict) else c
            if m is None:
                continue
            yield m, kind
            ck = {1: 'note', 3: 'rest', 0x14: 'beam', 0x25: 'chord',
                  0x45: 'chordSym'}.get(m.type, 'msg%02x' % m.type)
            stack.append((m, ck))
        for st in list(getattr(node, 'staff1', []) or []) + list(getattr(node, 'staff2', []) or []):
            stack.append((st, 'staff'))
        for mm in getattr(node, 'meas', []) or []:
            stack.append((mm, 'meas'))


def main():
    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    per_file = collections.defaultdict(collections.Counter)
    files_per_idx = collections.defaultdict(set)
    rows = []

    for p in files:
        try:
            doc = S.load(p)
        except Exception:
            continue
        seq = []
        for m, ck in iter_all(doc):
            if m.type != 0x08:
                continue
            per_file[os.path.basename(p)][m.head_type] += 1
            files_per_idx[m.head_type].add(os.path.basename(p))
            seq.append((m.head_type, ck, m.dx, m.dy, m.start, m.voice))
        if seq:
            rows.append((os.path.basename(p), seq))

    print('files per index:')
    for idx in sorted(files_per_idx):
        print('  idx %2d 0x%02x  %4d files' % (idx, MARKTB[idx], len(files_per_idx[idx])))

    print('\nfiles with the most distinct indices:')
    ranked = sorted(rows, key=lambda r: -len({s[0] for s in r[1]}))
    for name, seq in ranked[:6]:
        print('  %-28s marks=%-4d indices=%s' % (
            name, len(seq), sorted({s[0] for s in seq})))
        print('     seq:', ' '.join('%d%s' % (s[0], 'n' if s[1] == 'note' else 'm') for s in seq[:40]))

    print('\nsequence of idx 11 vs 1 (bowing test) in the two richest files:')
    for name, seq in ranked[:12]:
        sub = [s for s in seq if s[0] in (1, 11)]
        if len(sub) >= 6:
            print('  %-28s %s' % (name, ' '.join(str(s[0]) for s in sub[:40])))


main()
