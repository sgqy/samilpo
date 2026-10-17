"""Readable contact sheet of MarkTB, a few glyphs per sheet.

Usage: python _probe_sheet.py <out.png> <idx>[,<idx>...]
Each cell is labelled with the table index, the font byte and the outline bbox.
"""
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from PIL import Image, ImageDraw

FONT = r'C:\Program Files (x86)\Samilpo 2.0\Font\KAYAKUMA.TTF'

MARKTB = [0x00, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x62, 0x56, 0x57, 0x58, 0x59, 0x5c,
          0x65, 0x55, 0x4e, 0x2b, 0x2c, 0x5a, 0x5b, 0x51, 0x52, 0x50, 0x4f, 0x54,
          0x53, 0x73, 0x75, 0x74, 0x76, 0x63, 0x64, 0x7d, 0x7c, 0x77, 0x79, 0x78,
          0x68, 0x70, 0x6f, 0x71, 0x7a, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0x4b,
          0x4a, 0xa9, 0xaa]


def contours_of(pen_value, steps=20):
    out, cur, start = [], [], None

    def quad(p0, c, p1):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p1[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p1[1])
                for t in (i / steps for i in range(1, steps + 1))]

    for op, args in pen_value:
        if op == 'moveTo':
            if cur:
                out.append(cur)
            cur = [args[0]]
            start = args[0]
        elif op == 'lineTo':
            cur.append(args[0])
        elif op == 'qCurveTo':
            pts = list(args)
            if pts[-1] is None:
                pts[-1] = start
            offs, endpt = pts[:-1], pts[-1]
            for i in range(len(offs) - 1):
                c, nxt = offs[i], offs[i + 1]
                cur.extend(quad(cur[-1], c, ((c[0] + nxt[0]) / 2, (c[1] + nxt[1]) / 2)))
            if offs:
                cur.extend(quad(cur[-1], offs[-1], endpt))
            else:
                cur.append(endpt)
        elif op == 'curveTo':
            pts = list(args)
            p0, c1, c2, p1 = cur[-1], pts[-3], pts[-2], pts[-1]
            for i in range(1, steps + 1):
                t = i / steps
                mt = 1 - t
                cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p1[0],
                            mt ** 3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p1[1]))
        elif op == 'closePath':
            if cur:
                out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [c for c in out if len(c) > 2]


def main():
    out = sys.argv[1]
    idxs = [int(a, 0) for a in sys.argv[2].split(',')]
    font = TTFont(FONT, lazy=True)
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    CW, CH = 300, 340
    cols = min(4, len(idxs))
    rows = (len(idxs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * CW, rows * CH), (240, 240, 240))
    dr = ImageDraw.Draw(sheet)
    for k, idx in enumerate(idxs):
        g = MARKTB[idx]
        name = cmap.get(0xF000 | g) if g else None
        cx, cy = (k % cols) * CW, (k // cols) * CH
        info = '-'
        if name:
            pen = RecordingPen()
            gs[name].draw(pen)
            cs = contours_of(pen.value)
            if cs:
                xs = [p[0] for c in cs for p in c]
                ys = [p[1] for c in cs for p in c]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                dx, dy = (x1 - x0) or 1.0, (y1 - y0) or 1.0
                pad = 22
                sc = min((CW - 2 * pad) / dx, (CH - 40 - 2 * pad) / dy)
                mask = Image.new('L', (CW, CH), 0)
                for c in cs:
                    tmp = Image.new('L', (CW, CH), 0)
                    td = ImageDraw.Draw(tmp)
                    pts = [(pad + (p[0] - x0) * sc, CH - 40 - pad - (p[1] - y0) * sc) for p in c]
                    td.polygon(pts, fill=255)
                    mask = Image.frombytes('L', (CW, CH),
                                           bytes(a ^ b for a, b in zip(mask.tobytes(), tmp.tobytes())))
                sheet.paste(Image.new('RGB', (CW, CH), 'black'), (cx, cy), mask)
                info = 'bbox %dx%d  contours %d' % (dx, dy, len(cs))
        dr.rectangle([cx, cy, cx + CW - 1, cy + CH - 1], outline=(180, 180, 180))
        dr.text((cx + 6, cy + CH - 32), 'MarkTB[%d]  0x%02X  U+F0%02X' % (idx, g, g), fill=(0, 0, 0))
        dr.text((cx + 6, cy + CH - 18), info, fill=(0, 90, 170))
    sheet.save(out)
    print('wrote', out, sheet.size)


main()
