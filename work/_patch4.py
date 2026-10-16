import io

# ===================== smc2ir.py =====================
p = r'C:\research\samilpo\work\smc2ir.py'
t = io.open(p, encoding='utf-8').read()

if '\nimport re\n' not in t:
    old = 'import os\nimport struct\n'
    assert old in t
    t = t.replace(old, 'import os\nimport re\nimport struct\n', 1)

# ---- parse_credit, placed with the other text helpers
anchor = 'def decode_text(raw, cod):'
assert anchor in t
credit_fn = '''CREDIT_ROLE = {'\\uc791\\uc0ac': 'lyricist', '\\uc791\\uace1': 'composer'}
_CREDIT_SPLIT = re.compile(r'(\\uc791\\uc0ac|\\uc791\\uace1)')


def parse_credit(text):
    """Map a page credit line to {'lyricist': [...], 'composer': [...]}.

    Nothing in the format stores an author: the credit is ordinary page text.
    The corpus writes it as one free-form line - "\\uc791\\uc0ac \\ub9ac\\ucc2c, \\uc791\\uace1 \\uae40\\uc6d0\\uade0",
    "\\uc791\\uc0ac \\uae40\\uc815\\ud6c8\\r\\n\\uc791\\uace1 \\uac15\\uc219\\uc6c5", "\\uc791\\uc0ac,\\uc791\\uace1 \\uc7ac\\uc911\\uc870\\uc120\\uc778\\uc608\\uc220\\ub2e8 \\uc9d1\\uccb4" - so it can only
    be recovered by reading the text. Only \\uc791\\uc0ac (words) and \\uc791\\uace1 (music) occur:
    \\ud3b8\\uace1 / \\uc5ed\\uace1 / \\ubc88\\uc5ed appear nowhere in the corpus, so no other role is invented.

    A keyword with no name of its own shares the next one's, which is what
    "\\uc791\\uc0ac,\\uc791\\uace1 NAME" means: both credits name the same author.
    Returns {} when the text carries no credit keyword, so ordinary expression
    text ("\\uc57d\\ub3d9\\uc801\\uc73c\\ub85c \\uc88d \\ube60\\ub974\\uac8c") is never mistaken for one.
    """
    if '\\uc791\\uc0ac' not in text and '\\uc791\\uace1' not in text:
        return {}
    parts = _CREDIT_SPLIT.split(text)
    entries = []                       # [role, [names], text_after_keyword]
    for i in range(1, len(parts) - 1, 2):
        role = CREDIT_ROLE.get(parts[i])
        seg = parts[i + 1]
        names = [n.strip() for n in re.split(r'[,,\\u3001]', seg)]
        entries.append([role, [n for n in names if n], seg])
    for i, entry in enumerate(entries):
        if entry[1] or entry[2].strip(' ,\\uff0c'):
            continue
        for later in entries[i + 1:]:
            if later[1]:
                entry[1] = list(later[1])
                break
    out = {}
    for role, names, _ in entries:
        if names:
            bucket = out.setdefault(role, [])
            for n in names:
                if n not in bucket:
                    bucket.append(n)
    return out


'''
t = t.replace(anchor, credit_fn + anchor, 1)

# ---- collect credits from the text directions already gathered
old = """    # ---- accompaniment (decisions.md: the embedded patterns are real tracks)"""
new = """    # ---- author credit (decisions.md: written as page text, not as a field)
    # Reuse the text blocks already turned into directions rather than rescanning
    # the document. The credit stays in the part as <words> as well, because the
    # source really does display it there; dropping it would lose visible
    # content. The structured form exists so the names are machine-readable.
    creators = []
    seen_creators = set()
    for rec in em.recs:
        if rec.get('kind') != 'direction':
            continue
        d = rec.get('d') or {}
        if d.get('type') != 'text':
            continue
        for line in (d.get('lines') or []):
            for role, names in parse_credit(line).items():
                for nm in names:
                    if (role, nm) in seen_creators:
                        continue
                    seen_creators.add((role, nm))
                    creators.append({'role': role, 'name': nm,
                                     'meas': rec.get('meas'), 'text': line})
    score_rec['creators'] = creators

    # ---- accompaniment (decisions.md: the embedded patterns are real tracks)"""
assert old in t
t = t.replace(old, new, 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(t)
print('smc2ir.py patched')

# ===================== ir2musicxml.py =====================
p2 = r'C:\research\samilpo\work\ir2musicxml.py'
x = io.open(p2, encoding='utf-8').read()

old = """    ident = sub(root, 'identification')
    sub(ident, 'encoding').append(_software(software))"""
new = """    ident = sub(root, 'identification')
    sub(ident, 'encoding').append(_software(software))
    # The author credit has no field of its own in the source; it is recovered
    # from the page text (see smc2ir.parse_credit). MusicXML keeps it here so the
    # names survive as data, in source order, instead of only as drawn text.
    for c in (score.get('creators') or []):
        if c.get('name'):
            sub(ident, 'creator', c['name'], type=c.get('role') or 'other')"""
assert old in x
x = x.replace(old, new, 1)

io.open(p2, 'w', encoding='utf-8', newline='\n').write(x)
print('ir2musicxml.py patched')
