"""Corpus census of page text blocks, to locate credit lines (author, composer).

Nothing in the format stores a composer as a field: the credit is written as
ordinary page text. This collects every type 0x06/0x04 text block, groups the
distinct strings, and separates the ones that look like a credit line so the
converter can map them to <identification><creator> instead of leaving them as
anonymous page text.

Positions are recorded because a credit sits in a characteristic place (near the
top of the first page), which helps confirm an identification.
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs
import smc2ir

ROOT = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_credits.txt'

CREDIT = re.compile(r'작사|작곡|편곡|역곡|번역|역자|채보')
PATTERNS = ('작사', '작곡', '편곡', '역곡', '번역')


class _Opts:
    extent = 'debug'


def main(limit=None):
    cod = None
    try:
        cod = S.load_cod()
    except Exception:
        pass
    files = sorted(glob.glob(os.path.join(ROOT, '**', '*.smc'), recursive=True))
    if limit:
        files = files[:limit]

    text_hist = collections.Counter()
    text_pos = collections.defaultdict(list)
    credit_files = []
    n_files = 0
    n_blocks = 0
    fails = 0

    for p in files:
        try:
            doc = S.load(p)
        except Exception:
            fails += 1
            continue
        n_files += 1
        hits = []
        for st in doc.system.staff1 + doc.system.staff2:
            for mi, meas in enumerate(st.meas, 1):
                for ch in meas.children:
                    if not ch['msg']:
                        continue
                    for m, _ in walk_msgs([ch['msg']]):
                        if m.type not in (0x04, 0x06) or not m.head:
                            continue
                        lines, align = smc2ir.tlv_lines(m.head, _Opts(), cod)
                        if not lines:
                            continue
                        for ln in lines:
                            if not ln:
                                continue
                            n_blocks += 1
                            text_hist[ln] += 1
                            text_pos[ln].append((mi, m.dx, m.dy))
                            if CREDIT.search(ln):
                                hits.append((mi, m.dx, m.dy, ln))
        if hits:
            credit_files.append((p, hits))

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('files scanned        : %d (failures %d)\n' % (n_files, fails))
        f.write('text blocks (lines)  : %d\n' % n_blocks)
        f.write('distinct strings     : %d\n' % len(text_hist))
        f.write('files with a credit  : %d (%.1f%%)\n'
                % (len(credit_files), 100.0 * len(credit_files) / max(n_files, 1)))

        f.write('\nhow often each credit keyword appears:\n')
        for kw in PATTERNS:
            n = sum(v for k, v in text_hist.items() if kw in k)
            f.write('   %-6s %6d strings\n' % (kw, n))

        f.write('\ncredit-looking strings (top 50 by count):\n')
        cred = [(k, v) for k, v in text_hist.items() if CREDIT.search(k)]
        for k, v in sorted(cred, key=lambda kv: -kv[1])[:50]:
            pos = text_pos[k][:3]
            f.write('   %-46r x%-5d at %s\n' % (k, v, pos))

        f.write('\nall distinct strings (top 60, the page-text taxonomy):\n')
        for k, v in text_hist.most_common(60):
            f.write('   %-46r x%-5d at %s\n' % (k, v, text_pos[k][:2]))

        f.write('\nsample credit files:\n')
        for p, hits in credit_files[:25]:
            f.write('   %s\n' % p.split('8000Songs')[-1])
            for mi, dx, dy, ln in hits[:4]:
                f.write('        m%-4d dx=%-5d dy=%-5d %r\n' % (mi, dx, dy, ln))
    print('files=%d blocks=%d credit_files=%d' % (n_files, n_blocks, len(credit_files)))
    print('wrote', OUT)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
