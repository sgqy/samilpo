"""Where do type 0x08 marks live?  Report container kind and context, corpus-wide."""
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


def visit(node, kind, depth, out):
    """Yield (container_kind, container, depth, msg) for direct children."""
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is None:
            continue
        out.append((kind, node, depth, c.get('role') if isinstance(c, dict) else None, m))


def main():
    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    by_container = collections.Counter()
    by_idx_container = collections.Counter()
    for p in files:
        try:
            doc = S.load(p)
        except Exception:
            continue
        stack = [(doc.system, 'system', 0)]
        # pages are separate roots
        for pg in doc.pages:
            stack.append((pg, 'page', 0))
        while stack:
            node, kind, depth = stack.pop()
            kids = []
            visit(node, kind, depth, kids)
            for ck, cnode, cd, role, m in kids:
                by_container[(kind, m.type)] += 1
                if m.type == 0x08:
                    by_idx_container[(kind, m.head_type)] += 1
                childkind = {
                    1: 'note', 3: 'rest', 0x14: 'beam', 0x25: 'chord', 0x45: 'chordSym',
                }.get(m.type, 'msg0x%02x' % m.type)
                stack.append((m, childkind, depth + 1))
            for st in list(getattr(node, 'staff1', []) or []) + list(getattr(node, 'staff2', []) or []):
                stack.append((st, 'staff', depth + 1))
            for mm in getattr(node, 'meas', []) or []:
                stack.append((mm, 'meas', depth + 1))

    print('=== all msgs by (container kind, type) ===')
    for (k, t), n in sorted(by_container.items()):
        if t == 0x08:
            print('  %-10s type 0x%02x  %d' % (k, t, n))
    print('\n=== marks by (container kind, mark index) ===')
    for (k, i), n in sorted(by_idx_container.items()):
        print('  %-10s idx %2d glyph 0x%02x  %d' % (k, i, MARKTB[i] if i < len(MARKTB) else -1, n))


main()
