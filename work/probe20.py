"""Dump the control records (stored key 0) of each accompaniment style.

ConvertToPlayData keeps two kinds of 16-byte record: notes, and records whose
stored key is 0 that carry a raw MIDI message in bytes +8..+0xB. ReadRtmData
emits those same messages at the head of each track, which is how a track
declares its bank and program. Recovering them gives each accompanied track an
instrument name instead of a bare number.

MIDI message layout in +8..+0xB:
    0xB0|ch  cc  val   control change  (cc 0 / 32 = bank select MSB / LSB)
    0xC0|ch  prog  --  program change
    0x90|ch  key  vel  note on
    0x80|ch  key  vel  note off
"""
import glob
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs

OUT = r'C:\research\samilpo\work\out_accomp_ctrl.txt'
ROOT = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def msgs_of(rtm):
    out = []
    for i in range(rtm.event_count):
        b = rtm.events[i * rtm.event_size:(i + 1) * rtm.event_size]
        if len(b) < 16:
            break
        out.append((b[1], b[3], b[8], b[9], b[10], b[11]))
    return out


def main():
    files = sorted(glob.glob(os.path.join(ROOT, '**', '*.smc'), recursive=True))
    status = Counter()
    last_cc = defaultdict(dict)     # (style) -> {(ch, track): {cc: val}}
    programs = defaultdict(Counter)  # (style, track, ch) -> Counter(program)
    banks = defaultdict(Counter)
    scanned = 0

    for p in files:
        if scanned >= 120:
            break
        try:
            doc = S.load(p)
        except Exception:
            continue
        scanned += 1
        for st in doc.system.staff1 + doc.system.staff2:
            for meas in st.meas:
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
                        label = (r.s2 or r.s1 or b'?').decode('latin-1')
                        for track in range(16):
                            for key, tr, s, d1, d2, _u in msgs_of(r.rtm):
                                if key != 0 or tr != track:
                                    continue
                                st_hi = s & 0xF0
                                chan = s & 0x0F
                                status[st_hi] += 1
                                if st_hi == 0xB0:
                                    last_cc[label].setdefault(tr, {})[d1] = d2
                                elif st_hi == 0xC0:
                                    programs[(label, tr, chan)][d1] += 1
                        for tr in range(16):
                            cc = last_cc[label].get(tr)
                            if cc:
                                banks[(label, tr)][(cc.get(0), cc.get(32))] += 1

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('files scanned: %d\n' % scanned)
        f.write('\nstatus-byte histogram (high nibble): %s\n'
                % {hex(k): v for k, v in sorted(status.items())})
        f.write('\nbank select seen per (style, track):\n')
        for k, v in sorted(banks.items()):
            f.write('   %-18s tr%-2d %s\n' % (k[0], k[1], dict(v)))
        f.write('\nprogram change per (style, track, channel):\n')
        for k, v in sorted(programs.items()):
            f.write('   %-18s tr%-2d ch%-2d %s\n' % (k[0], k[1], k[2], dict(v)))
    print('scanned=%d' % scanned)
    print('status:', {hex(k): v for k, v in sorted(status.items())})
    print('programs:', len(programs), 'banks:', len(banks))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
