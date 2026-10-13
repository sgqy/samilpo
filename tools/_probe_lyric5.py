"""Verify lyric<->note key adjacency and print a worked example (read-only)."""
import sys, os, io, contextlib, struct, collections, random
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w
from smc_text import parse_cod, decode

D = r'C:\Program Files (x86)\Samilpo 2.0'
t, _, _ = parse_cod(os.path.join(D, '889F.cod')); T = t[0]

stack = []
rel = collections.Counter()
per_meas = collections.Counter()
seq = []

def read_object_core(r, depth, kind, embedded_only):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<h', h, 4)[0]
    head = r.take(max(headlen, 0))
    me = stack[-1] if stack else None
    n = 0
    for i in range(nchild):
        c = r.take(8)
        if c[4]:
            key, child = read_msg(r, depth + 1)
            if me and me[0] == 0x01 and child[0] == 0x19:
                n += 1
                nk = struct.unpack_from('<I', me[1], 0x24)[0]
                lk = struct.unpack_from('<I', child[1], 0x24)[0]
                rel[lk - nk] += 1
    if kind == 'msg' and me and me[0] == 0x01:
        per_meas[n] += 1
    return head

def read_msg(r, depth):
    start = r.p
    h = r.take(0x2c)
    t_ = h[0]
    w.stats['msg'] += 1
    stack.append((t_, h))
    hd = read_object_core(r, depth, 'msg', False)
    stack.pop()
    w.msg_types[t_] += 1
    w.heads.setdefault(t_, []).append((h, hd))
    if t_ == 0x45:
        w.read_chord_extra(r, depth + 1, start)
    return (struct.unpack_from('<I', h, 0x24)[0], (t_, h, hd))

w.read_object_core = read_object_core
w.read_msg = read_msg

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')]
random.seed(2)
for path in random.sample(files, 40):
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)

print('lyric_key - note_key:', dict(rel))
print('lyrics per note:', dict(per_meas))

# worked example: full lyric sequence of one file
target = os.path.join(D, '8000Songs', '100SONG', '150ALS', '150ALS-03DA', '150ALS-03DA-0012.smc')
if not os.path.exists(target):
    target = [p for p in files if '150ALS-03DA-0012' in p][0]
w.heads.clear(); w.msg_types.clear()
with contextlib.redirect_stdout(io.StringIO()):
    w.main(target)
print()
print('lyric sequence of', os.path.basename(target))
out = []
for hd, h in w.heads.get(0x19, []):
    ln = hd[0x0C]
    out.append(decode(hd[0x10:0x10 + ln], T, 0))
print('  ' + ' '.join(out))
print('  count', len(out), 'joined:', ''.join(out))
