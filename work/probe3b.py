"""Explain the non-tiling measures found by probe3 (work scratch).

Usage: python work/probe3b.py <file.smc> <measIdx> [<measIdx> ...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import walk_msgs, play_time, tick_per_meas

GRACE = 0x0010


def main(path, idxs):
    doc = S.load(path)
    wt = doc.system.whole_tick
    st = doc.system.staff1[0]
    # global key -> (measure, type) map for endpoint resolution
    by_key = {}
    for mi, meas in enumerate(st.meas):
        for m, d in walk_msgs([c['msg'] for c in meas.children if c['msg']]):
            by_key[m.key] = (mi, m)

    for idx in idxs:
        idx = int(idx)
        meas = st.meas[idx]
        tpm = tick_per_meas(wt, meas.ts_num, meas.ts_den)
        print('=== meas %d ts=%d/%d tpm=%d ===' % (idx, meas.ts_num, meas.ts_den, tpm))
        for c in meas.children:
            m = c['msg']
            if not m:
                print('  (role=0 ref key=%d)' % c['key'])
                continue
            if m.type in (0x01, 0x03, 0x14, 0x25):
                def show(x, ind):
                    dur = getattr(x, 'duration', 0)
                    pt = play_time(x, wt)
                    flags = x.flags
                    tags = []
                    if flags & 0x0001:
                        tags.append('TIE-CONT')
                    if flags & 0x0002:
                        tags.append('flag2')
                    if flags & 0x0010:
                        tags.append('grace/silent')
                    if flags & 0x0004:
                        tags.append('tail')
                    if flags & 0x0200:
                        tags.append('staff-up')
                    if flags & 0x0400:
                        tags.append('staff-down')
                    print('%s0x%02x key=%-6d pitch=%-4s dur=%-6d pt=%-6d exp=%-2d dots=%d start=%-5d v%d flags=0x%04x %s' % (
                        ind, x.type, x.key, getattr(x, 'midi_key', '-'), dur, pt,
                        x.type_index & 0x1F, x.dots, x.start, x.voice, flags, ','.join(tags)))
                show(m, '  ')
                for cc in m.children:
                    if cc['msg'] and cc['msg'].type in (0x01, 0x03):
                        show(cc['msg'], '      ')
                    elif cc['msg']:
                        extra = ''
                        if cc['msg'].type in (0x09, 0x0A, 0x12):
                            tgt = by_key.get(cc['msg'].endpoint)
                            extra = ' -> key %d @meas %s' % (
                                cc['msg'].endpoint, tgt[0] if tgt else 'MISSING')
                        print('      child 0x%02x key=%d role=%d%s' % (
                            cc['msg'].type, cc['msg'].key, cc['role'], extra))
            else:
                print('  0x%02x key=%d' % (m.type, m.key))
        # neighbours for context
        for nb in (idx - 1, idx + 1):
            if 0 <= nb < len(st.meas):
                mm = st.meas[nb]
                print('  -- neighbour meas %d ts=%d/%d' % (nb, mm.ts_num, mm.ts_den))
                for m, d in walk_msgs([c['msg'] for c in mm.children if c['msg']]):
                    if m.type == 0x01:
                        print('       key=%-6d pitch=%-3d dur=%-6d pt=%-5d start=%-5d flags=0x%04x' % (
                            m.key, m.head[0], m.duration, play_time(m, wt), m.start, m.flags))
        print()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
