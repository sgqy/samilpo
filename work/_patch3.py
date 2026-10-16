import io

# ---- smc2ir.py -----------------------------------------------------------
p = r'C:\research\samilpo\work\smc2ir.py'
t = io.open(p, encoding='utf-8').read()

# Options: drop the mode, keep an explicit always-on switch under the new name.
old = """        self.part_merge = a.part_merge
        self.accompaniment = a.accompaniment
        self.emit_layout = a.emit_layout"""
new = """        self.part_merge = a.part_merge
        self.emit_layout = a.emit_layout"""
assert old in t
t = t.replace(old, new, 1)

old = """            'part_merge': self.part_merge,
            'accompaniment': self.accompaniment,
        }"""
new = """            'part_merge': self.part_merge,
        }"""
assert old in t
t = t.replace(old, new, 1)

old = """    ap.add_argument('--accompaniment', default='separate',
                    choices=['separate', 'none'],
                    help='export the arrangement stored in chord symbols as '
                         'separate parts (default) or omit it')"""
new = """    # Accompaniment is not optional. The arrangement stored in the chord
    # symbols is music the source file really contains; it is only invisible
    # because the original program does not draw it, and "not drawn" is a layout
    # state, not a reason to drop material. There is therefore no way to turn it
    # off, and no mode to choose: every track comes out as its own part.
    ap.add_argument('--accomp', action='store_true', default=True,
                    help='emit every accompaniment track as its own part '
                         '(always on; hidden material must survive)')"""
assert old in t
t = t.replace(old, new, 1)

# convert(): always build, never conditional.
old = """    if opts.accompaniment != 'none':
        # Share the melody's barline positions exactly. Step 2 sizes a measure
        # as max(time signature, furthest content), so read that back from the
        # melody's own measure records rather than recomputing the rule.
        timeline = ([], [])
        for rec in em.recs:
            if rec.get('kind') == 'measure' and rec.get('part') == 'P1':
                ends = list((rec.get('content_end') or {}).values())
                want = max([rec.get('tpm', 0)] + ends)
                timeline[0].append(sum(timeline[1]))
                timeline[1].append(want)
        aparts, anotes, ameasures, astats = accomp.build(
            doc, cod, opts, timeline=timeline if timeline[1] else None)
        if opts.accompaniment == 'separate' or aparts:
            for rec in aparts:
                em.emit(rec)
            for rec in ameasures:
                em.emit(rec)
            for rec in anotes:
                em.emit(rec)
        for k, v in astats.items():
            audit['accomp_' + k] = v
        if not aparts:
            warn('accompaniment-absent')"""
new = """    # Share the melody's barline positions exactly. Step 2 sizes a measure as
    # max(time signature, furthest content), so read that back from the melody's
    # own measure records rather than recomputing the rule.
    timeline = ([], [])
    for rec in em.recs:
        if rec.get('kind') == 'measure' and rec.get('part') == 'P1':
            ends = list((rec.get('content_end') or {}).values())
            want = max([rec.get('tpm', 0)] + ends)
            timeline[0].append(sum(timeline[1]))
            timeline[1].append(want)
    aparts, anotes, ameasures, astats = accomp.build(
        doc, cod, opts, timeline=timeline if timeline[1] else None)
    for rec in aparts:
        em.emit(rec)
    for rec in ameasures:
        em.emit(rec)
    for rec in anotes:
        em.emit(rec)
    for k, v in astats.items():
        audit['accomp_' + k] = v
    if not aparts:
        warn('accompaniment-absent')"""
assert old in t
t = t.replace(old, new, 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(t)
print('smc2ir.py patched')

# ---- batch.py ------------------------------------------------------------
p2 = r'C:\research\samilpo\work\batch.py'
b = io.open(p2, encoding='utf-8').read()
old = """                       hyphen_policy='literal', part_merge='auto',
                       accompaniment='separate',
                       emit_layout=False"""
new = """                       hyphen_policy='literal', part_merge='auto',
                       emit_layout=False"""
assert old in b
b = b.replace(old, new, 1)
io.open(p2, 'w', encoding='utf-8', newline='\n').write(b)
print('batch.py patched')
