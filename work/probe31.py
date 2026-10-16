"""Dump title, creators and file header bytes for a few samples, to a UTF-8 file.

The console cannot show Korean, so this writes results out and they are read back
with the file reader.  Also prints the first four bytes of each MusicXML, because
a UTF-8 BOM ahead of the XML declaration is a common cause of a notation program
showing a garbled or missing title.
"""
import io
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_title_credits.txt'

SAMPLES = [
    os.path.join(SONGS, '500KFS', '500KFS-0041.smc'),
    os.path.join(SONGS, '100SONG', '110SSS', '110SSS-001.smc'),
]


def find_any(n):
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                yield os.path.join(dirpath, nm)
    return


def main():
    import smc_read as S
    import smc2ir
    import argparse

    cod = S.load_cod()

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)

    w('=' * 78)
    w('SYMP HEADER TITLE (the canonical title field)')
    w('=' * 78)
    for smc in SAMPLES:
        doc = S.load(smc)
        w('%-16s title_raw=%r' % (os.path.basename(smc), doc.title_raw))
        w('%-16s decoded  =%r' % ('', smc2ir.decode_text(doc.title_raw, cod)))
        w('%-16s extra_str=%r' % ('', doc.extra_str))

    w('')
    w('=' * 78)
    w('GENERATED MUSICXML - title, creators, first bytes')
    w('=' * 78)
    for smc in SAMPLES:
        base = os.path.splitext(os.path.basename(smc))[0]
        nd = os.path.join(HERE, 'out_%s.ndjson' % base)
        mx = os.path.join(HERE, 'out_%s.musicxml' % base)
        buf = io.StringIO()
        smc2ir.convert(smc, opts, buf)
        with open(nd, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(buf.getvalue())
        import ir2musicxml
        score, parts, part_measures, events, spans = ir2musicxml.load_ir_text(buf.getvalue())
        root = ir2musicxml.build(score, parts, part_measures, events, spans,
                                 'smc2ir/ir2musicxml 0.1.0')
        with open(mx, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(ir2musicxml.serialize(root))

        raw = open(mx, 'rb').read()
        text = raw.decode('utf-8-sig')
        root = ET.fromstring(text[text.index('<score-partwise'):])
        ident = root.find('identification')
        creators = [(c.get('type'), c.text) for c in (ident.findall('creator') if ident is not None else [])]
        w('%-16s file=%s' % (base, os.path.basename(mx)))
        w('%-16s first4=%r  bom=%s' % ('', raw[:4], raw[:3] == b'\xef\xbb\xbf'))
        w('%-16s title=%r' % ('', root.findtext('movement-title')))
        w('%-16s creators=%r' % ('', creators))
        pl = root.find('part-list')
        w('%-16s parts=%d' % ('', len(pl.findall('score-part'))))
        w('')

    w('=' * 78)
    w('CREDIT TEXT PRESENCE ACROSS THE CORPUS')
    w('=' * 78)
    n = 0
    with_credit = []
    for p in find_any(None):
        n += 1
        try:
            doc = S.load(p)
        except Exception:
            continue
        texts = []
        for page in doc.pages:
            pass
        if getattr(doc, 'doc_pages', 0) is None:
            continue
        # reuse the IR-side credit parse over the doc's page text blocks
        for blk in side_text_blocks(doc, cod):
            cr = smc2ir.parse_credit(blk)
            if cr:
                with_credit.append((os.path.basename(p), blk, cr))
                break
    w('files scanned        : %d' % n)
    w('files with a credit  : %d' % len(with_credit))
    for name, blk, cr in with_credit[:12]:
        w('   %-24s %-30r %r' % (name, blk[:28], cr))

    f.close()
    print('wrote', OUT)


def side_text_blocks(doc, cod):
    """Every page text block string of a Doc, in page order."""
    import smc_read as S
    out = []

    def walk(node):
        for c in getattr(node, 'children', ()) or ():
            m = c.get('msg') if isinstance(c, dict) else c
            if m is None:
                continue
            yield m
            for x in walk(m):
                yield x

    for page in doc.pages:
        for m in walk(page):
            if m.type in (0x04, 0x06):
                for attr in ('text_bytes', 'lyric_bytes', 'bytes'):
                    b = getattr(m, attr, None)
                    if b:
                        out.append(S.decode(b, cod))
                        break
    return out


if __name__ == '__main__':
    main()
