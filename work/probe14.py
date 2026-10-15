"""Structural audit of one .smc: find material that exists but is never laid out.

"Hidden" means "not drawn", not "absent". So this walks every container that can
hold musical material and reports what each one holds:

  1. a section map of the file, so nothing is left unaccounted for
  2. the trailer after the body
  3. CSMCtrlTool
  4. System children (objects hanging off the system itself)
  5. every Page: its Blocks and its own message list
  6. every Staff and its measures

A page message list is a real candidate: CSMPage::Read stores n_msg messages on
each page, and the drawing path does not print them, so anything musical in there
is material the UI never shows.
"""
import sys
from collections import Counter

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
from probe_smc import walk_msgs

OUT = r'C:\research\samilpo\work\out_struct_0041.txt'


def main(path):
    doc = S.load(path)
    f = open(OUT, 'w', encoding='utf-8')
    def w(*a):
        print(*a, file=f)

    w('=' * 78)
    w(path)
    w('=' * 78)
    w('file size        : %d' % doc.size)
    w('hdr_len          : 0x%x' % doc.hdr_len)
    w('magic/version    : %r %d' % (doc.magic, doc.version))
    w('title            : %r' % doc.title_raw)
    w('extra_str        : %r' % doc.extra_str)
    w('font_buf_len     : %d' % doc.font_buf_len)
    w('fonts            : %d' % len(doc.fonts))
    w('ctl_len          : %d' % doc.ctl_len)
    w('file_info        : %s' % (doc.file_info,))
    w('body_off/len     : %d / %d' % (doc.body_off, doc.body_len))
    w('body_consumed    : %d  (%s)' % (
        doc.body_consumed,
        'EXACT' if doc.body_consumed == doc.body_len else 'MISMATCH'))
    w('trailer_len      : %d' % len(doc.trailer))
    w('doc_pages        : %d' % doc.doc_pages)
    w('doc_fields       : %s' % (doc.doc_fields,))
    w('system n_staff1  : %d' % doc.system.n_staff1)
    w('system n_staff2  : %d' % doc.system.n_staff2)
    w('system whole_tick: %d' % doc.system.whole_tick)
    w('system child_cnt : %d' % doc.system.child_count)
    w('system head_len  : %d' % doc.system.head_len)

    w('')
    w('--- trailer ---')
    w(doc.trailer.hex(' ') if doc.trailer else '(empty)')
    w('trailer as text : %r' % doc.trailer[:200])

    w('')
    w('--- CSMCtrlTool ---')
    w('len=%d' % len(doc.ctl))
    w(doc.ctl[:256].hex(' '))
    w('as text: %r' % doc.ctl[:200])

    w('')
    w('--- System children ---')
    if not doc.system.children:
        w('(none)')
    for c in doc.system.children:
        m = c.get('msg')
        w('key=%-6s role=%s type=%s' % (c.get('key'), c.get('role'),
                                        ('0x%02x' % m.type) if m else None))

    w('')
    w('--- System head ---')
    w('head_len=%d head=%s' % (len(doc.system.head or b''),
                               (doc.system.head or b'').hex(' ')))

    w('')
    w('--- document-level messages ---')
    for m in doc.doc_msgs:
        w('type=0x%02x key=%s child=%d head_len=%d head=%s' % (
            m.type, m.key, len(m.children or []), m.head_len,
            (m.head or b'').hex(' ')[:80]))

    w('')
    w('--- pages ---')
    for pi, p in enumerate(doc.pages):
        w('page[%d] n_a=%d n_b=%d n_msg=%d rect=%s' % (
            pi, p.n_a, p.n_b, p.n_msg, p.rect))
        kinds = Counter()
        for m in p.msgs:
            for mm, _ in walk_msgs([m]):
                kinds[mm.type] += 1
        w('   page msgs by type: %s' % ({hex(k): v for k, v in sorted(kinds.items())}))
        for bi, b in enumerate(p.blocks_a + p.blocks_b):
            w('   block[%d] type=%s n_staves=%s start_meas=%s measX_n=%s staff_refs=%s'
              % (bi, b.type, b.n_staves, b.start_meas, b.f2 + 1, b.staff_refs))

    w('')
    w('--- staves ---')
    for grp, staves in (('staff1', doc.system.staff1), ('staff2', doc.system.staff2)):
        for si, st in enumerate(staves):
            kinds = Counter()
            for meas in st.meas:
                for ch in meas.children:
                    if not ch['msg']:
                        continue
                    for mm, _ in walk_msgs([ch['msg']]):
                        kinds[mm.type] += 1
            w('%s[%d] n_meas=%d head_len=%d kinds=%s' % (
                grp, si, len(st.meas), st.head_len,
                {hex(k): v for k, v in sorted(kinds.items())}))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1
         else r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc')
