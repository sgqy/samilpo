"""Dump every type 0x06 / 0x04 text block of one file, in document order.

Author/composer credit has no field of its own: it is written as ordinary text
on the page, so it can only be recovered by reading the text blocks. This lists
them all with their measure and position so nothing is missed.
"""
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs
import smc2ir

OUT = r'C:\research\samilpo\work\out_textblocks.txt'


def main(paths):
    cod = None
    try:
        cod = S.load_cod()
    except Exception:
        pass
    f = open(OUT, 'w', encoding='utf-8')

    def w(*a):
        print(*a, file=f)

    for path in paths:
        doc = S.load(path)
        w('=' * 76)
        w(path)
        w('title_raw  : %r' % doc.title_raw)
        w('decoded    : %r' % smc2ir.decode_text(doc.title_raw, cod))
        w('extra_str  : %r' % doc.extra_str)
        w('file_info  : %s' % (doc.file_info,))
        w('')
        w('document-level messages:')
        for m in doc.doc_msgs:
            w('   type=0x%02x head_len=%d head=%s'
              % (m.type, m.head_len, (m.head or b'').hex(' ')[:100]))
            if m.type in (0x04, 0x06) and m.head:
                lines, align = smc2ir.tlv_lines(m.head, _Opts(), cod)
                w('      tlv -> %r align=%s' % (lines, align))
        w('')
        w('text blocks on the page:')
        for st in doc.system.staff1 + doc.system.staff2:
            for mi, meas in enumerate(st.meas, 1):
                for ch in meas.children:
                    if not ch['msg']:
                        continue
                    for m, _ in walk_msgs([ch['msg']]):
                        if m.type not in (0x04, 0x06):
                            continue
                        lines, align = smc2ir.tlv_lines(m.head, _Opts(), cod)
                        w('   m%-4d type=0x%02x on=%-5s dx=%-5s dy=%-5s align=%-3s %r'
                          % (mi, m.type, m.start, m.dx, m.dy, align, lines))
        w('')
    f.close()
    print('wrote', OUT)


class _Opts:
    extent = 'debug'


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        args = [r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\100SONG\110SSS\110SSS-001.smc',
                r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc']
    main(args)
