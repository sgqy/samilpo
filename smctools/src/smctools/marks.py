"""MarkTB (type 0x08 single-character marks) — single source of truth.

Three tables that used to live in two places each (the questionnaire generator
held the glyph table, the XML converter held the mapping) are merged here:

* ``MARKTB``       the 51-entry glyph table exported at engine.dll 0x1010059C
                   (STMARK.code, one font byte per entry; renders as
                   U+F000+code in KAYAKUMA.TTF).
* ``MARK_XML``     MusicXML <notations> emission for the 12 corpus indices with
                   a human-confirmed meaning (questionnaire 2026-11-07; rating
                   [H]; docs/music-fields.md §8, docs/smc-format.md §6.13b).
* ``MARK_WORDS``   time-signature digit glyphs ("2"/"4"): the signature itself
                   is carried by <time>, so the drawn digit survives as words.
"""

# STMARK.code per index 0..50 (work/make_mark_questionnaire.py corpus probe,
# verified against engine.dll 0x1010059C).
MARKTB = [0x00, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x62, 0x56, 0x57, 0x58, 0x59, 0x5c,
          0x65, 0x55, 0x4e, 0x2b, 0x2c, 0x5a, 0x5b, 0x51, 0x52, 0x50, 0x4f, 0x54,
          0x53, 0x73, 0x75, 0x74, 0x76, 0x63, 0x64, 0x7d, 0x7c, 0x77, 0x79, 0x78,
          0x68, 0x70, 0x6f, 0x71, 0x7a, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0x4b,
          0x4a, 0xa9, 0xaa]

# index -> U+F0NN code point actually drawn by DrawMark's DrawTextOut.
MARKTB_GLYPH = {i: 0xF000 | c for i, c in enumerate(MARKTB)}

# Confirmed mapping: MarkTB index -> [(group, element, attrs)]; group None
# places the element directly under <notations> (fermata). See the reference
# imagery in work/mark-xml-reference.html.
MARK_XML = {
    1:  [('technical', 'up-bow', None)],
    11: [('technical', 'up-bow', None)],
    8:  [('articulations', 'accent', None), ('articulations', 'tenuto', None)],
    10: [('articulations', 'accent', None), ('articulations', 'staccato', None)],
    13: [('articulations', 'accent', None)],
    14: [('articulations', 'staccato', None)],
    16: [('articulations', 'tenuto', None)],
    25: [('ornaments', 'trill-mark', None)],
    29: [(None, 'fermata', {'type': 'upright'})],
    30: [(None, 'fermata', {'type': 'inverted'})],
    33: [('ornaments', 'inverted-mordent', None)],
    35: [('ornaments', 'shake', None)],
}

MARK_WORDS = {43: '2', 45: '4'}
