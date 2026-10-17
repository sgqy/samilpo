"""Census of type 0x08 (DrawMark) across the corpus -- whole tree.

DrawMark (0x10065570) draws ONE character:
    glyph = MarkTB[ MsgHdr+0x06 (obj+0x5C) ].byte0
at (obj+0x50 X, obj+0x52 Y).  So MsgHdr+0x06 is the mark table index.
"""
import collections
import os
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S

SONGS = r'C:\Program Files (x86)\Samilpo\2.0'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def walk(node):
    """Yield every Msg reachable from node (containers included)."""
    stack = [node]
    while stack:
        n = stack.pop()
        for c in getattr(n, 'children', ()) or ():
            m = c.get('msg') if isinstance(c, dict) else c
            if m is None:
                continue
            if getattr(m, 'kind', None) == 'msg':
                yield m
            stack.append(m)
        for st in list(getattr(n, 'staff1', []) or []) + list(getattr(n, 'staff2', []) or []):
            stack.append(st)
        for mm in getattr(n, 'meas', []) or []:
            stack.append(mm)
        for pg in getattr(n, 'pages', []) or []:
            stack.append(pg)
        for blk in (list(getattr(n, 'blocks_a', []) or []) + list(getattr(n, 'blocks_b', []) or [])):
            pass


def main():
    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    n_files = 0
    n_mark = 0
    idx = collections.Counter()
    headlen = collections.Counter()
    headbytes = collections.Counter()
    tyidx = collections.Counter()
    flags = collections.Counter()
    parent = collections.Counter()
    voice = collections.Counter()
    per_file = collections.Counter()
    dxdy = collections.Counter()

    for p in files:
        try:
            doc = S.load(p)
        except Exception as e:
            print('FAIL', p, e)
            continue
        n_files += 1
        k = 0
        roots = [doc.system] + doc.pages
        for r in roots:
            for m in walk(r):
                if m.type != 0x08:
                    continue
                k += 1
                n_mark += 1
                idx[m.head_type] += 1
                headlen[len(m.head)] += 1
                headbytes[m.head.hex(' ')] += 1
                tyidx[m.type_index] += 1
                flags[m.flags] += 1
                voice[m.voice] += 1
                dxdy[(m.dx, m.dy)] += 1
        if k:
            per_file[k] += 1

    print('files', n_files, 'marks', n_mark, 'files with marks', len(per_file))
    print('\nmarks per file:', sorted(per_file.items()))
    print('\nMsgHdr+0x06 (mark index) = MarkTB index:')
    for k, v in sorted(idx.items()):
        print('  %6d  %d' % (k, v))
    print('\nheadLen:', sorted(headlen.items()))
    print('\nMsgHdr+0x08 (type_index):', sorted(tyidx.items()))
    print('\nflags:', sorted(flags.items()))
    print('\nvoice:', sorted(voice.items()))
    print('\ndx,dy top:', sorted(dxdy.items(), key=lambda x: -x[1])[:20])
    print('\nhead bytes:')
    for k, v in headbytes.most_common(40):
        print('  %-48s %d' % (k, v))


main()
