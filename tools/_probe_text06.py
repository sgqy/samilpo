"""Validate the CSMTextMsg (0x06) TLV head grammar and decode its text."""
import sys, os, io, contextlib, struct, collections, random
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
t, _, _ = parse_cod(os.path.join(D, '889F.cod')); T = t[0]

# tag -> payload size after the tag byte (from CSMTextMsg::DrawMsg 0x100c2f70)
SIZE = {0x01: 2, 0x02: 2, 0x03: 1, 0x04: 2, 0x05: 4, 0x07: 4, 0x09: 2, 0x0A: 0, 0x0B: 4, 0x0C: 4}

def parse_tlv(h):
    """Returns (fields, texts) or raises ValueError."""
    p, fields, texts = 0, [], []
    while p < len(h):
        tag = h[p]; p += 1
        if tag == 0x06:
            if p + 2 > len(h):
                raise ValueError('trunc len')
            n = struct.unpack_from('<H', h, p)[0]; p += 2
            texts.append(h[p:p + n]); p += n
        elif tag in SIZE:
            n = SIZE[tag]
            if p + n > len(h):
                raise ValueError('trunc tag %02x' % tag)
            fields.append((tag, h[p:p + n])); p += n
        else:
            raise ValueError('unknown tag %02x' % tag)
    return fields, texts

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')]
random.seed(13)
ok = bad = 0
tags = collections.Counter()
align = collections.Counter()
texts_dec = 0
kr_ok = 0
reasons = collections.Counter()
samples = []
for path in random.sample(files, 400):
    w.heads.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)
    for hd, h in w.heads.get(0x06, []):
        try:
            f, ts = parse_tlv(h)
            ok += 1
        except ValueError as e:
            bad += 1; reasons[str(e)] += 1
            if len(samples) < 6:
                samples.append((os.path.basename(path), h.hex(' ')))
            continue
        for tg, v in f:
            tags[tg] += 1
        for tg, v in f:
            if tg == 0x01:
                align[struct.unpack('<h', v)[0]] += 1
        for tx in ts:
            texts_dec += 1
            s = decode(tx, T, 0)
            cs = [c for c in s if not c.isspace()]
            if cs and sum(1 for c in cs if 0xAC00 <= ord(c) <= 0xD7A3) / len(cs) > 0.5:
                kr_ok += 1
print('TLV parsed ok=%d bad=%d' % (ok, bad))
print('failure reasons:', dict(reasons))
print('tags:', {hex(k): v for k, v in sorted(tags.items())})
print('alignment values (tag 01):', dict(align))
print('text segments=%d hangul-majority=%d' % (texts_dec, kr_ok))
for s in samples:
    print('  BAD', s)
