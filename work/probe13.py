"""Hunt for a second, possibly hidden, instrumental track in one .smc.

"Hidden" in the original UI means it is not laid out, not that it is absent from
the file. So this probe looks for data that exists but nothing references:

  1. every Staff object in the System, and how many measures/notes it holds
  2. Blocks (layout rows) and their staffRef - a staff no Block references is
     never drawn, which is exactly a hidden track
  3. Msg flag bits (MsgHdr+0x0A, see smc-format.md 6.5) on notes
  4. MIDI-bearing messages (0x42 DrawMidiShortMsg), which would be a real
     second track
  5. the three document-level messages
  6. rhythm-style references hanging off chord symbols, and whether the file
     they name exists on disk
"""
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs

INSTALL = r'C:\Program Files (x86)\Samilpo 2.0'


def describe_staff(st, label):
    notes = 0
    lyrics = 0
    chords = 0
    spans = 0
    kinds = Counter()
    for meas in st.meas:
        for ch in meas.children:
            if not ch['msg']:
                continue
            for m, _ in walk_msgs([ch['msg']]):
                kinds[m.type] += 1
                if m.type == 0x01:
                    notes += 1
                elif m.type == 0x19:
                    lyrics += 1
                elif m.type == 0x45:
                    chords += 1
    total = sum(kinds.values())
    print('  %-10s n_meas=%-4d notes=%-5d lyrics=%-5d chords=%-5d msgs=%d'
          % (label, len(st.meas), notes, lyrics, chords, total))
    if total == 0:
        print('             (EMPTY - holds no messages at all)')
    return notes, total, kinds


def main(path):
    doc = S.load(path)
    print('=' * 78)
    print(path)
    print('=' * 78)

    staffs = doc.system.staff1 + doc.system.staff2
    print('\n[1] Staff objects: %d' % len(staffs))
    grand = Counter()
    for i, st in enumerate(doc.system.staff1):
        n, t, k = describe_staff(st, 'staff1[%d]' % i)
        grand += k
    for i, st in enumerate(doc.system.staff2):
        n, t, k = describe_staff(st, 'staff2[%d]' % i)
        grand += k
    print('  whole-file message mix:', {hex(k): v for k, v in sorted(grand.items())})

    print('\n[2] System structure:')
    for attr in ('n_page', 'pages', 'name'):
        if hasattr(doc.system, attr):
            v = getattr(doc.system, attr)
            print('   system.%s = %r' % (attr, v if not isinstance(v, list) else '<%d>' % len(v)))

    # Blocks: layout rows. A staff that no Block references is never drawn.
    blocks = getattr(doc, 'blocks', None)
    staff_refs = Counter()
    if blocks:
        print('\n   Blocks: %d' % len(blocks))
        for b in blocks:
            ref = getattr(b, 'staff_ref', None) or getattr(b, 'staffRef', None)
            staff_refs[ref] += 1
            print('     block staffRef=%r measX=%r n=%r' % (
                ref, getattr(b, 'meas_x', None), getattr(b, 'n', None)))
    else:
        print('\n   (no Blocks exposed by the reader)')

    print('\n[3] MIDI-bearing messages (would be a real 2nd track):')
    print('   0x42 count =', grand.get(0x42, 0))

    print('\n[4] Document-level messages:')
    for m in getattr(doc, 'doc_msgs', []) or []:
        print('   type=0x%02x key=%s head_len=%s head=%s' % (
            m.type, m.key, m.head_len, (m.head.hex()[:64] if m.head else '')))

    print('\n[5] Chord rhythm-style references (external accompaniment styles):')
    refs = []
    for st in staffs:
        for meas in st.meas:
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type != 0x45:
                        continue
                    ce = m.chord_extra
                    if ce and ce.has_rhythm and ce.rhythm:
                        r = ce.rhythm
                        refs.append((r.s1, r.s2, r.s3,
                                     r.rtm.event_count if r.rtm else 0))
    seen = set()
    for s1, s2, s3, ne in refs:
        key = (s1, s2, s3)
        if key in seen:
            continue
        seen.add(key)
        rel = s3.decode('latin-1') if isinstance(s3, bytes) else str(s3)
        cand = os.path.join(INSTALL, '8000Songs', rel.replace('/', os.sep))
        alt = os.path.join(INSTALL, rel.replace('/', os.sep))
        print('   style=%r name=%r' % (s1, s2))
        print('     path=%r events=%d' % (rel, ne))
        print('     exists under 8000Songs: %s' % os.path.exists(cand))
        print('     exists under install   : %s' % os.path.exists(alt))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1
         else r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc')
