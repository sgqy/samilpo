"""Cross-tabulate type 0x08 mark index against musical context.

Questions this answers, per mark index:
  * is it attached to a measure or to a note?
  * does it land on the LAST note of its measure (fermata) or the first (accent)?
  * what is its dy sign (above/below the staff)?
  * does it coincide with a barline / the final measure?
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


def direct(node):
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is not None:
            yield m


def notes_in(meas):
    """All note msgs under a measure, in file order, with their depth."""
    out = []
    stack = [(meas, 0)]
    while stack:
        n, d = stack.pop()
        for m in direct(n):
            if m.type == 0x01:
                out.append((m, d))
            stack.append((m, d + 1))
    return out


def main():
    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    # per index stats
    owner = collections.defaultdict(collections.Counter)
    dypos = collections.defaultdict(collections.Counter)
    posfrac = collections.defaultdict(list)     # relative position in the bar 0..1
    atmeasend = collections.defaultdict(collections.Counter)
    lastmeas = collections.defaultdict(collections.Counter)
    near_final = collections.defaultdict(collections.Counter)
    startv = collections.defaultdict(collections.Counter)
    voice = collections.defaultdict(collections.Counter)
    per_index_total = collections.Counter()
    contexts = collections.defaultdict(list)

    for p in files:
        try:
            doc = S.load(p)
        except Exception:
            continue
        for st in list(doc.system.staff1) + list(doc.system.staff2):
            nm = len(st.meas)
            for mi, meas in enumerate(st.meas):
                notes = notes_in(meas)
                nstarts = [n.start for n, _ in notes]
                span = max(nstarts) if nstarts else 0
                whole = 0
                for m in direct(meas):
                    pass
                # marks directly under the measure
                for m in direct(meas):
                    if m.type != 0x08:
                        continue
                    idx = m.head_type
                    per_index_total[idx] += 1
                    owner[idx]['meas'] += 1
                    dypos[idx]['down' if m.dy < 0 else ('up' if m.dy > 0 else 'zero')] += 1
                    startv[idx][m.start] += 1
                    voice[idx][m.voice] += 1
                    lastmeas[idx]['last' if mi == nm - 1 else 'other'] += 1
                    if nstarts:
                        # x position vs note starts: which note is it over?
                        frac = m.dx / max(max(m.dx for m in direct(meas) if True), 1) if False else None
                        # distance to each note's dx
                        best, bd = None, 10 ** 9
                        for n, _ in notes:
                            d = abs(n.dx - m.dx)
                            if d < bd:
                                best, bd = n, d
                        if best is not None:
                            near_final[idx]['end' if best.start >= span else 'mid'] += 1
                    contexts[idx].append(('meas', mi, nm, m.dx, m.dy))
                # marks under notes
                for n, _ in notes:
                    for m in direct(n):
                        if m.type != 0x08:
                            continue
                        idx = m.head_type
                        per_index_total[idx] += 1
                        owner[idx]['note'] += 1
                        dypos[idx]['down' if m.dy < 0 else ('up' if m.dy > 0 else 'zero')] += 1
                        startv[idx][m.start] += 1
                        voice[idx][m.voice] += 1
                        lastmeas[idx]['last' if mi == nm - 1 else 'other'] += 1
                        near_final[idx]['end' if n.start >= span else 'mid'] += 1
                        contexts[idx].append(('note', mi, nm, n.start, n.duration, m.dx, m.dy))
                for m in direct(meas):
                    if m.type == 0x03:
                        for sub in direct(m):
                            if sub.type == 0x08:
                                idx = sub.head_type
                                per_index_total[idx] += 1
                                owner[idx]['rest'] += 1
                                dypos[idx]['down' if sub.dy < 0 else ('up' if sub.dy > 0 else 'zero')] += 1
                                contexts[idx].append(('rest', mi, nm, sub.dx, sub.dy))

    print('%-4s %-12s %-6s %-8s %-6s %-20s %s' % (
        'idx', 'glyph', 'total', 'owner', 'dy', 'position', 'last-meas'))
    for idx in sorted(per_index_total):
        print('%-4d 0x%02x %-5d %-11s %-6s %-8s %-6s %-20s %s' % (
            idx, MARKTB[idx], per_index_total[idx],
            dict(owner[idx]), '',
            dict(dypos[idx]), '',
            dict(near_final[idx]), dict(lastmeas[idx])))

    print('\n=== detail: dy and start per index ===')
    for idx in sorted(per_index_total):
        print('idx %2d 0x%02x  total %d' % (idx, MARKTB[idx], per_index_total[idx]))
        print('   owner   ', dict(owner[idx]))
        print('   dy      ', dict(dypos[idx]))
        print('   start   ', dict(startv[idx]))
        print('   voice   ', dict(voice[idx]))
        print('   position', dict(near_final[idx]))
        print('   lastmeas', dict(lastmeas[idx]))
        print('   samples ', contexts[idx][:8])


main()
