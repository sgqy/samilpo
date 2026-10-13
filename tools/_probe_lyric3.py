"""Determine lyric (0x19) parent message type and association fields."""
import sys, os, io, contextlib, struct, collections, random
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w

D = r'C:\Program Files (x86)\Samilpo 2.0'
stack = []
parent_type = {}
lrec = []

def read_object_core(r, depth, kind, embedded_only):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<h', h, 4)[0]
    head = r.take(max(headlen, 0))
    for i in range(nchild):
        c = r.take(8)
        if c[4]:
            start = r.p
            parent_type[start] = stack[-1] if stack else None
            read_msg(r, depth + 1)
    return head

def read_msg(r, depth):
    start = r.p
    h = r.take(0x2c)
    t_ = h[0]
    w.msg_types[t_] += 1
    w.stats['msg'] += 1
    if t_ == 0x19:
        lrec.append((parent_type.get(start), h))
    stack.append(t_)
    hd = read_object_core(r, depth, 'msg', False)
    stack.pop()
    w.heads.setdefault(t_, []).append((h, hd))
    if t_ == 0x45:
        w.read_chord_extra(r, depth + 1, start)

w.read_object_core = read_object_core
w.read_msg = read_msg

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')]
random.seed(5)
for path in random.sample(files, 40):
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)

print('total lyrics', len(lrec))
print('parent msg type distribution:',
      {('0x%02x' % k) if k is not None else 'None': v for k, v in
       collections.Counter(p for p, _ in lrec).most_common()})

f = collections.defaultdict(collections.Counter)
rng = collections.defaultdict(lambda: [1 << 30, -1 << 30])
for p, h in lrec:
    for name, off in [('+0x48', 0x0e), ('+0x50', 0x16), ('+0x52', 0x18), ('+0x54', 0x1a),
                      ('+0x56', 0x1c), ('+0x5a', 0x14), ('+0x5c', 6), ('+0x5e', 8)]:
        v = struct.unpack_from('<h', h, off)[0]
        f[name][v] += 1
        r = rng[name]
        r[0] = min(r[0], v); r[1] = max(r[1], v)
for name in ['+0x48', '+0x50', '+0x52', '+0x54', '+0x56', '+0x5a', '+0x5c', '+0x5e']:
    print('%-6s distinct=%-4d range=%s top=%s' % (
        name, len(f[name]), rng[name], f[name].most_common(5)))
