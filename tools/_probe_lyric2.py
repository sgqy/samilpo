"""Verify lyric parent/message association and unmapped-code behaviour."""
import sys, os, io, contextlib, struct, collections, random
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
t, _, _ = parse_cod(os.path.join(D, '889F.cod')); T = t[0]

# 1) unmapped behaviour: what does the table hold for the "bad" codes?
for code in (0x8ED1, 0xF041, 0x8E9E, 0x8D69, 0x8DA2):
    print('code %04x -> table %04x  (0 means: keep original byte pair)' % (code, T.lookup(code)))

# 2) parent tracking: patch walker to note parent kind for each msg
parent = {}
orig_read_object_core = w.read_object_core

def read_object_core(r, depth, kind, embedded_only):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<h', h, 4)[0]
    head = r.take(max(headlen, 0))
    for i in range(nchild):
        c = r.take(8)
        emb = c[4]
        if emb:
            start = r.p
            parent[start] = kind
            read_msg(r, depth + 1)
    return head

def read_msg(r, depth):
    start = r.p
    h = r.take(0x2c)
    t_ = h[0]
    w.msg_types[t_] += 1
    w.stats['msg'] += 1
    parents.setdefault(t_, collections.Counter())[parent.get(start, '?')] += 1
    if t_ == 0x19:
        pos = struct.unpack_from('<hh', h, 0x14)  # +14 -> msg+0x5a, +16 -> +0x50
        ly[pos[1]].append(pos[0])
    hd = read_object_core(r, depth, 'msg', False)
    w.heads.setdefault(t_, []).append((h, hd))
    if t_ == 0x45:
        w.read_chord_extra(r, depth + 1, start)

w.read_object_core = read_object_core
w.read_msg = read_msg
parents = {}
ly = collections.defaultdict(list)

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')]
random.seed(11)
for path in random.sample(files, 60):
    w.heads.clear(); w.msg_types.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)

for t_ in sorted(parents):
    print('type 0x%02x parents: %s' % (t_, dict(parents[t_])))
print()
print('lyric x-pos by staff/voice index (field at msg+0x50):')
for k in sorted(ly):
    v = ly[k]
    print('  idx %d: n=%d min=%d max=%d' % (k, len(v), min(v), max(v)))
