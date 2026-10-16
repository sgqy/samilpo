"""Investigate the reported title/author and trailing-chord problems.

Two questions from the review:

  1. The title is wrong and the author must be kept.  Where does a title live,
     and is there anything besides title_raw?  What does the part name become?

  2. Two chords seem missing at the end.  Are they genuinely absent from the
     source, or is the reader missing them?

Also dumps the last measures' entire child tree, so nothing is skipped.
"""
import sys

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S
import smc2ir
from probe_smc import walk_msgs

OUT = r'C:\research\samilpo\work\out_title_end.txt'


class _O:
    extent = 'debug'


def dump(path, f):
    doc = S.load(path)
    cod = S.load_cod()
    w = lambda *a: print(*a, file=f)
    w('=' * 78)
    w(path)
    w('title_raw       : %r' % doc.title_raw)
    w('title decoded   : %r' % smc2ir.decode_text(doc.title_raw, cod))
    w('extra_str       : %r' % doc.extra_str)
    w('file_info       : %s' % (doc.file_info,))
    w('doc_fields      : %s' % (doc.doc_fields,))
    w('n_staff1/2      : %d / %d' % (doc.system.n_staff1, doc.system.n_staff2))
    for grp, name in ((doc.system.staff1, 'staff1'), (doc.system.staff2, 'staff2')):
        for si, st in enumerate(grp):
            w('  %s[%d] name raw=%r decoded=%r head_len=%s'
              % (name, si, st.name, smc2ir.decode_text(st.name, cod), st.head_len))
    w('')
    w('page-text blocks (all of them):')
    for st in doc.system.staff1 + doc.system.staff2:
        for mi, meas in enumerate(st.meas, 1):
            for ch in meas.children:
                if not ch['msg']:
                    continue
                for m, _ in walk_msgs([ch['msg']]):
                    if m.type in (0x04, 0x06):
                        lines, align = smc2ir.tlv_lines(m.head, _O(), cod)
                        w('   m%-4d type=0x%02x dy=%-5s %r'
                          % (mi, m.type, m.dy, lines))

    st = (doc.system.staff1 + doc.system.staff2)[0]
    n = len(st.meas)
    w('')
    w('LAST 6 MEASURES - full child tree (n=%d):' % n)
    for mi in range(max(1, n - 5), n + 1):
        meas = st.meas[mi - 1]
        w('  measure %d  ts=%d/%d  child_count=%d  refs_only=%d'
          % (mi, meas.ts_num, meas.ts_den, meas.child_count, meas.refs_only))
        for ch in meas.children:
            m = ch['msg']
            if m is None:
                w('     key=%-6s role=%s  (reference only, no embedded msg)'
                  % (ch['key'], ch['role']))
                continue
            extra = ''
            if m.type == 0x45:
                ce = getattr(m, 'chord_extra', None)
                if ce:
                    extra = ' shape=%s name=%r info=%s has_rhythm=%s' % (
                        smc2ir.shape_from_fret_info(ce.fret_info),
                        ce.name, ce.info.hex(), ce.has_rhythm)
            w('     key=%-6s role=%s type=0x%02x start=%-5s head_type=%-3s '
              'type_idx=%-3s%s'
              % (ch['key'], ch['role'], m.type, m.start, m.head_type,
                 m.type_index, extra))
            for sub in (m.children or []):
                w('         child key=%-6s type=0x%02x start=%-5s'
                  % (sub['key'], sub['msg'].type if sub['msg'] else -1,
                     sub['msg'].start if sub['msg'] else -1))


def main():
    paths = sys.argv[1:] or [
        r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc']
    with open(OUT, 'w', encoding='utf-8') as f:
        for p in paths:
            dump(p, f)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
