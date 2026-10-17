"""Print exact font-space geometry for every MarkTB glyph used by the corpus.

Wedge-shaped glyphs are simple polygons, so the raw points identify the shape
(V / ^ / > / <) unambiguously: font y grows upward.
"""
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen

FONT = r'C:\Program Files (x86)\Samilpo 2.0\Font\KAYAKUMA.TTF'

MARKTB = [0x00, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x62, 0x56, 0x57, 0x58, 0x59, 0x5c,
          0x65, 0x55, 0x4e, 0x2b, 0x2c, 0x5a, 0x5b, 0x51, 0x52, 0x50, 0x4f, 0x54,
          0x53, 0x73, 0x75, 0x74, 0x76, 0x63, 0x64, 0x7d, 0x7c, 0x77, 0x79, 0x78,
          0x68, 0x70, 0x6f, 0x71, 0x7a, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0x4b,
          0x4a, 0xa9, 0xaa]

USED = [1, 8, 10, 11, 13, 14, 16, 25, 29, 30, 33, 35, 43, 45]


def main():
    font = TTFont(FONT, lazy=True)
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    for idx in (USED if len(sys.argv) < 2 else [int(a, 0) for a in sys.argv[1:]]):
        g = MARKTB[idx]
        name = cmap.get(0xF000 | g)
        pen = RecordingPen()
        if name:
            gs[name].draw(pen)
        print('\nMarkTB[%d] byte 0x%02X U+F0%02X glyph=%r' % (idx, g, g, name))
        npts_total = 0
        for ci, (op, args) in enumerate([]):
            pass
        # replay segments explicitly so we see the control points
        contour = 0
        for op, args in pen.value:
            if op == 'moveTo':
                print('  contour %d: M %s' % (contour, _fmt(args)))
            elif op == 'lineTo':
                print('              L %s' % _fmt(args))
            elif op == 'qCurveTo':
                print('              Q %s' % _fmt(args))
            elif op == 'curveTo':
                print('              C %s' % _fmt(args))
            elif op == 'closePath':
                print('              Z')
                contour += 1
        try:
            adv = font['hmtx'][name]
        except Exception:
            adv = None
        print('  advance/lsb:', adv)


def _fmt(args):
    try:
        return ' '.join('(%.0f,%.0f)' % (p[0], p[1]) for p in args if p is not None)
    except TypeError:
        return repr(args)


main()
