"""Decode the accompaniment pattern embedded in a chord symbol.

A CChordSymbol may carry a Rhythm (type 0x47) whose RtmData is a small
multi-track arrangement rather than a single line. Container layout comes from
CRtmData::ReadFromMem 0x10047720; record semantics from
CRtmData::ConvertToPlayData 0x100470f0 and CRtmData::ReadRtmData 0x10046210:

  6-byte track entry (the array ConvertToPlayData indexes at +0x34)
      +0x00 ?                  (ReadRtmData takes Staff +0x58)
      +0x01 MIDI channel       (Staff +0x50 & 0x0F; 9 = percussion)
      +0x02 ?                  (Staff +0x18 >> 8)
      +0x03 ?                  (Staff +0x60)
      +0x04 i16 transpose      (Staff +0x4E, added to the resolved key)

  16-byte event
      +0x01 key as semitones above the chord root, resolved by GetRealMidiKey
      +0x02 ?
      +0x03 track index into the entry table
      +0x08 u32 duration in 1024ths of a measure
      +0x0C u16 start in 1024ths of a measure
      +0x0E velocity
      +0x0F overwritten at play time with the track channel

CRtmData::GetRealMidiKey 0x10047410 resolves +0x01 against the chord quality
(root, third, fifth get special treatment via CChordSurfixInfo), which is why a
single stored pattern follows the chord changes. Positions use 1024 units per
measure, so a tick is MulDiv(unit, measure_ticks, 1024).
"""
import struct
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs

OUT = r'C:\research\samilpo\work\out_rtm_0041.txt'


def decode(rtm):
    """Return (tracks, events) in file order."""
    tracks = []
    for i in range(rtm.count2):
        e = rtm.seg2[i * rtm.size2:(i + 1) * rtm.size2]
        if len(e) < 6:
            break
        tracks.append({'b0': e[0], 'channel': e[1], 'b2': e[2], 'b3': e[3],
                       'transpose': struct.unpack_from('<h', e, 4)[0],
                       'raw': e.hex(' ')})
    events = []
    for i in range(rtm.event_count):
        b = rtm.events[i * rtm.event_size:(i + 1) * rtm.event_size]
        if len(b) < 16:
            break
        events.append({'track': b[3], 'key': b[1], 'unk2': b[2],
                       'start': struct.unpack_from('<H', b, 12)[0],
                       'dur': struct.unpack_from('<I', b, 8)[0],
                       'vel': b[14], 'b15': b[15], 'raw': b.hex(' ')})
    return tracks, events


def main(path):
    doc = S.load(path)
    f = open(OUT, 'w', encoding='utf-8')

    def w(*a):
        print(*a, file=f)

    for si, st in enumerate(doc.system.staff1 + doc.system.staff2):
        for mi, meas in enumerate(st.meas, 1):
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type != 0x45:
                        continue
                    ce = m.chord_extra
                    if not (ce and ce.has_rhythm and ce.rhythm):
                        continue
                    r = ce.rhythm
                    tracks, events = decode(r.rtm)
                    limit = r.rtm.a * 1024
                    w('=' * 76)
                    w('measure %d staff %d style=%r name=%r' % (mi, si + 1, r.s1, r.s2))
                    w('measures=%d measLen=%d events=%d stride=%d tracks=%d'
                      % (r.rtm.a, r.rtm.b, r.rtm.event_count, r.rtm.stride, len(tracks)))
                    for i, t in enumerate(tracks):
                        grp = [e for e in events if e['track'] == i]
                        starts = sorted(set(e['start'] for e in grp))
                        keys = sorted(set(e['key'] for e in grp))
                        perc = ' PERCUSSION' if t['channel'] == 9 else ''
                        w('  track %d ch=%-2d trans=%-4d events=%-3d%s'
                          % (i, t['channel'], t['transpose'], len(grp), perc))
                        w('      raw      = %s' % t['raw'])
                        w('      starts   = %s%s' % (starts[:14], ' ...' if len(starts) > 14 else ''))
                        w('      keys     = %s%s' % (keys[:14], ' ...' if len(keys) > 14 else ''))
                        for e in grp[:4]:
                            w('      key=%-3d unk2=%-3d start=%-5d dur=%-5d vel=%-3d b15=%-3d'
                              % (e['key'], e['unk2'], e['start'], e['dur'], e['vel'], e['b15']))
                        oob = [s for s in starts if s >= limit]
                        if oob:
                            w('      OUT OF RANGE (>= %d): %s' % (limit, oob[:8]))
                    outside = [e['start'] for e in events if e['start'] >= limit]
                    w('  all starts inside %d units: %s'
                      % (limit, 'YES' if not outside else 'NO %s' % outside[:8]))
                    w('  distinct track indexes used: %s'
                      % sorted(set(e['track'] for e in events)))
                    w('  track index within table: %s'
                      % all(e['track'] < len(tracks) for e in events))
    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1
         else r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc')
