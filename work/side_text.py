"""Export IR side text (further lyric verses) to a plain text file.

Why this exists
---------------
Some scores write verses 2 and 3 as a multi-line text block placed *beside* the
staff rather than as lyric records attached to notes. Those blocks arrive in the
IR as direction records whose `d.type` is "text" with `multiline` set.

MusicXML has no place for them: `<words>` would pile the whole verse onto one
tick and lose the line structure, and `<lyric>` requires a note to hang on. So
they are written to a plain text file next to the score, which is what the source
itself is showing the reader. Line breaks inside a paragraph are re-wrapped to a
fixed width; blank lines, which the author used to separate verses, are kept.

Usage:
    python work/side_text.py <file.ndjson> <out.txt> [--width 60]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir2musicxml


def collect(path):
    """Return [(part, meas, [lines])] for every multi-line text block, in order."""
    return collect_from_text(open(path, encoding='utf-8').read())


def collect_from_text(text):
    """Same as collect(), for IR already in memory."""
    out = []
    score, parts, part_measures, events, span_index = ir2musicxml.load_ir_text(text)
    for (pid, mnum), evs in sorted(events.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        for e in evs:
            if e.get('kind') != 'direction':
                continue
            d = e.get('d') or {}
            if d.get('type') == 'text' and d.get('multiline'):
                out.append((pid, mnum, d.get('lines') or []))
    return out


def split_paragraphs(lines):
    """Group lines into paragraphs, keeping the author's blank-line breaks."""
    paras = []
    cur = []
    for ln in lines:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    return paras


def wrap(text, width):
    """Wrap one line to `width` display columns, breaking at spaces.

    Korean has no inter-word spaces in every case, so a line longer than `width`
    with no space is left intact rather than cut mid-syllable: cutting would
    invent a word break the source does not have.
    """
    if len(text) <= width:
        return [text]
    words = text.split(' ')
    out = []
    cur = ''
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += ' ' + w
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def render(blocks, width):
    chunks = []
    for pid, mnum, lines in blocks:
        paras = split_paragraphs(lines)
        body = []
        for para in paras:
            for ln in para:
                body.extend(wrap(ln, width))
            body.append('')
        while body and not body[-1]:
            body.pop()
        chunks.append((pid, mnum, body))
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ir')
    ap.add_argument('out')
    ap.add_argument('--width', type=int, default=60)
    ap.add_argument('--header', action='store_true',
                    help='prefix each block with its part and measure')
    a = ap.parse_args()

    blocks = collect(a.ir)
    if not blocks:
        print('%s: no multi-line side text' % os.path.basename(a.ir))
        return 1

    chunks = render(blocks, a.width)
    out = []
    for pid, mnum, body in chunks:
        if a.header:
            out.append('[%s measure %d]' % (pid, mnum))
        out.extend(body)
        out.append('')
    text = '\n'.join(out).rstrip('\n') + '\n'

    if a.out == '-':
        sys.stdout.write(text)
    else:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        print('%s -> %s (%d blocks, %d lines)' %
              (os.path.basename(a.ir), a.out, len(chunks), text.count('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
