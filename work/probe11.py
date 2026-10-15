"""Find where extra lyric verses live (work scratch).

Some scores carry more than one verse. This script counts, per file, how many
lyric records there are and how they cluster, and lists files whose text blocks
(0x06 TLV) contain long Korean runs that look like a second or third verse
written beside the staff rather than attached to notes.

Usage: python work/probe11.py [--dir D] [--max N] [--min-len 30]
"""
import argparse
import collections
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smc_read as S
from probe_smc import walk_msgs

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def tlv_texts(head, cod):
    """Extract text payloads from a type 0x06 TLV head."""
    b = head
    q = 0
    out = []
    while q + 1 < len(b):
        tag = b[q]
        q += 1
        if tag in (0x01, 0x02, 0x04, 0x09):
            q += 2
        elif tag in (0x03, 0x05, 0x07):
            q += {0x03: 1, 0x05: 4, 0x07: 4}[tag]
        elif tag == 0x06:
            if q + 2 > len(b):
                break
            n = int.from_bytes(b[q:q + 2], 'little')
            q += 2
            out.append(S.decode(b[q:q + n], cod))
            q += n
        elif tag == 0x0A:
            out.append('\n')
        else:
            break
    return ''.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=SONGS)
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--min-len', type=int, default=30)
    args = ap.parse_args()

    cod = S.load_cod()
    files_with_long = []
    lyric_hist = collections.Counter()
    n_lit = 0
    n_page_msg = 0
    for path in files(args.dir, args.max):
        try:
            doc = S.load(path)
        except S.Fail:
            continue
        n_lit += 1
        per_file_lyrics = 0
        long_texts = []
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                for mi, meas in enumerate(st.meas):
                    for c in meas.children:
                        if not c['msg']:
                            continue
                        for m, d in walk_msgs([c['msg']]):
                            if m.type == 0x19:
                                per_file_lyrics += 1
                            elif m.type == 0x06:
                                t = tlv_texts(m.head, cod)
                                if len(t) >= args.min_len:
                                    long_texts.append((mi, t))
        for p in doc.pages:
            if p.n_msg:
                n_page_msg += 1
        lyric_hist[per_file_lyrics] += 1
        if long_texts:
            files_with_long.append((os.path.basename(path), long_texts))

    print('files=%d  files with page-level msgs=%d' % (n_lit, n_page_msg))
    print()
    print('text blocks with >= %d chars: %d files' % (args.min_len, len(files_with_long)))
    for name, rows in files_with_long[:25]:
        for mi, t in rows[:3]:
            print('   %-24s m%-4d %r' % (name, mi, t[:90]))
    print()
    print('lyric-count distribution (top):', lyric_hist.most_common(8))


if __name__ == '__main__':
    main()
