"""Dump one accompaniment track's events in raw order, with byte context.

The point is to find out what the decoder is silently discarding: how many
events have a zero stored key, what MIDI status each carries, and how the
remaining ones map onto measures. Written as UTF-8 for the read tool.
"""
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs

OUT = r'C:\research\samilpo\work\out_track0.txt'


def main(path):
    doc = S.load(path)
    f = open(OUT, 'w', encoding='utf-8')

    def w(*a):
        print(*a, file=f)

    for st in doc.system.staff1 + doc.system.staff2:
        for mi, meas in enumerate(st.meas, 1):
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type != 0x45:
                        continue
                    ce = getattr(m, 'chord_extra', None)
                    if not (ce and ce.has_rhythm and ce.rhythm):
                        continue
                    r = ce.rhythm
                    rtm = r.rtm
                    label = (r.s2 or r.s1 or b'?').decode('latin-1')
                    w('=' * 76)
                    w('measure %d  style=%s  tracks=%d events=%d period=%d'
                      % (mi, label, rtm.count2, rtm.event_count, rtm.a))
                    tracks = []
                    for i in range(rtm.count2):
                        e = rtm.seg2[i * rtm.size2:(i + 1) * rtm.size2]
                        tracks.append((e[1], int.from_bytes(e[4:6], 'little',
                                                           signed=True)))

                    rows = []
                    for i in range(rtm.event_count):
                        b = rtm.events[i * rtm.event_size:
                                       (i + 1) * rtm.event_size]
                        rows.append(b)

                    for ti in range(rtm.count2):
                        sel = [b for b in rows if b[3] == ti]
                        keys = [b[1] for b in sel]
                        nz = [k for k in keys if k]
                        w('')
                        w('  track %d ch=%d trans=%d events=%d  key==0:%d  key!=0:%d'
                          % (ti, tracks[ti][0], tracks[ti][1], len(sel),
                             len(sel) - len(nz), len(nz)))
                        if nz:
                            w('     nonzero keys sorted: %s' % sorted(set(nz)))
                            w('     nonzero key min/max: %d/%d'
                              % (min(nz), max(nz)))
                        status = {}
                        for b in sel:
                            if b[1] == 0:
                                s = b[8] & 0xF0
                                status[s] = status.get(s, 0) + 1
                        if status:
                            w('     key==0 MIDI status: %s'
                              % {hex(k): v for k, v in sorted(status.items())})
                        w('     first 10 raw events:')
                        for b in sel[:10]:
                            w('        key=%-3d tr=%-2d dur=%-6d start=%-5d '
                              'msg=%s vel=%-3d b15=%d'
                              % (b[1], b[3],
                                 int.from_bytes(b[8:12], 'little'),
                                 int.from_bytes(b[12:14], 'little'),
                                 b[8:12].hex(' '), b[14], b[15]))

                    # Are the nonzero keys inside what a measure slice can hold?
                    limit = rtm.a * 1024
                    starts = sorted(set(int.from_bytes(b[12:14], 'little')
                                        for b in rows))
                    w('')
                    w('  all starts: min=%d max=%d  slice limit=%d  beyond: %d'
                      % (starts[0], starts[-1], limit,
                         sum(1 for s in starts if s >= limit)))
                    w('  events beyond slice limit: %d of %d'
                      % (sum(1 for b in rows
                             if int.from_bytes(b[12:14], 'little') >= limit),
                         len(rows)))
    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1
         else r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc')
