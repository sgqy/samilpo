"""Locate chord symbols that persist the 100-byte runtime head, then find which
head offset carries the chord root.

CRtmData::GetRealMidiKey 0x10047410 reads `*(short *)(chord + 0x80)` and indexes
DAT_101002cc with it; that table's value is the pitch class the accompaniment is
transposed onto (index 13 -> 9, i.e. A, which is what 500KFS-0041's Am needs).
The +0x80 field is a runtime field: it is absent from the MsgHdr disk layout
table in smc-format.md 6.1, so it is not one of the persisted header bytes.

smc-format.md 6.9 says type 0x45 head length is either 0 or 100, the 100-byte
form being a persisted runtime struct. Chords in 500KFS-0041 all have headLen 0,
so +0x80 cannot be read from them. This probe finds the files that DO carry a
100-byte head and, by grouping on the fret-derived root, isolates which head
offsets vary with the root instead of being constant runtime junk.

Output is written as UTF-8 and meant to be read with the read tool.
"""
import glob
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs
from smc2ir import root_from_fret_info, shape_from_fret_info

ROOT = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_chord_head.txt'
WANT = 600          # stop once this many 100-byte heads have been collected


def chords_of(doc):
    for st in doc.system.staff1 + doc.system.staff2:
        for meas in st.meas:
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type == 0x45:
                        yield m


def main():
    files = sorted(glob.glob(os.path.join(ROOT, '**', '*.smc'), recursive=True))
    len_hist = Counter()
    samples = []                      # (path, shape, suffix, rootpc, head)
    files_with = []
    scanned = 0

    for p in files:
        if len(samples) >= WANT:
            break
        try:
            doc = S.load(p)
        except Exception:
            continue
        scanned += 1
        n100 = 0
        for m in chords_of(doc):
            ce = getattr(m, 'chord_extra', None)
            if ce is None:
                continue
            len_hist[m.head_len] += 1
            if m.head_len != 100:
                continue
            n100 += 1
            r = root_from_fret_info(ce.fret_info)
            samples.append((p, shape_from_fret_info(ce.fret_info),
                            ce.name.decode('latin-1'),
                            (r['step'], r['alter']) if r else None,
                            m.head))
        if n100:
            files_with.append((p, n100))

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('files scanned        : %d\n' % scanned)
        f.write('headLen histogram    : %s\n' % dict(sorted(len_hist.items())))
        f.write('files with headLen100: %d\n' % len(files_with))
        f.write('100-byte heads found : %d (stopped at %d)\n' % (len(samples), WANT))

        f.write('\nfirst 40 files carrying a 100-byte head\n')
        for p, n in files_with[:40]:
            f.write('   %-48s %d\n' % (p.split('8000Songs')[-1], n))

        if not samples:
            f.write('\nNo 100-byte heads found in the scanned range.\n')
            return

        # Which offsets are constant (runtime junk) versus which move with root?
        n = 100
        varying = [i for i in range(n)
                   if len(set(s[4][i] for s in samples)) > 1]
        f.write('\nconstant offsets : %d of %d\n' % (n - len(varying), n))
        f.write('varying offsets  : %s\n' % varying)

        # The root drive: group values at each varying offset by root pitch class.
        by_root = defaultdict(lambda: defaultdict(Counter))
        for p, shape, sfx, rootpc, head in samples:
            if rootpc is None:
                continue
            for i in varying:
                by_root[i][rootpc][head[i]] += 1
        f.write('\noffsets whose byte is a function of the ROOT alone (one value per root):\n')
        found = []
        for i in varying:
            per = by_root[i]
            if len(per) < 2:
                continue
            if all(len(v) == 1 for v in per.values()):
                mapping = {str(k): list(v)[0] for k, v in sorted(per.items())}
                found.append((i, mapping))
                f.write('   head[0x%02X] -> %s\n' % (i, mapping))
        if not found:
            f.write('   (none - the root is not stored as a single plain byte)\n')

        f.write('\nsamples (first 60), grouped by shape and suffix:\n')
        shown = Counter()
        for p, shape, sfx, rootpc, head in samples:
            k = (shape, sfx, rootpc)
            if shown[k] >= 1:
                continue
            shown[k] += 1
            f.write('   %-9s %-11r root=%-6s %s\n'
                    % (shape, sfx, rootpc, head.hex(' ')))
            f.write('      from %s\n' % p.split('8000Songs')[-1])
            if sum(shown.values()) >= 60:
                break
        f.write('\ndistinct (shape, suffix, root) triples: %d\n' % len(shown))
    print('scanned=%d heads100=%d files_with=%d' % (scanned, len(samples), len(files_with)))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
