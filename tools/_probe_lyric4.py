"""Lyric<->note association: correct parent tracking."""
import sys, os, io, contextlib, struct, collections, random
sys.path.insert(0, r'C:\research\samilpo\tools')
import smc_walk as w

D = r'C:\Program Files (x86)\Samilpo 2.0'
stack = []          # list of (type, msghdr)
pairs = []          # (lyric_msghdr, parent_type, parent_msghdr)
lens = collections.Counter()
per_note = collections.Counter()

def read_object_core(r, depth, kind, embedded_only):
    h = r.take(12)
    nchild, headlen = h[0], struct.unpack_from('<h', h, 4)[0]
    head = r.take(max(headlen, 0))
    me = stack[-1] if stack else None
    nly = 0
    for i in range(nchild):
        c = r.take(8)
        if c[4]:
            child = read_msg(r, depth + 1)
            if me is not None and me[0] == 0x01 and child[0] == 0x19:
                nly += 1
                pairs.append((child[1], me[1]))
    if kind == 'msg' and me is not None and me[0] == 0x01:
        per_note[nly] += 1
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
    if t_ == 0x19:
        lens[len(hd) - 0x10] += 1
    if t_ == 0x45:
        w.read_chord_extra(r, depth + 1, start)
    return (t_, h)

w.read_object_core = read_object_core
w.read_msg = read_msg

files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(D, '8000Songs'))
         for f in fs if f.endswith('.smc')]
random.seed(21)
for path in random.sample(files, 30):
    with contextlib.redirect_stdout(io.StringIO()):
        w.main(path)

print('lyrics per note:', dict(per_note))
print('lyric text length distribution:', {k: v for k, v in lens.items()})
print('pairs', len(pairs))
def g(h, off): return struct.unpack_from('<h', h, off)[0]
fields = collections.defaultdict(collections.Counter)
for lh, nh in pairs:
    fields['lyric+0x50 (MsgHdr+0x16)'][g(lh, 0x16)] += 1
    fields['parent+0x50 (MsgHdr+0x16)'][g(nh, 0x16)] += 1
    fields['parent+0x5a (MsgHdr+0x14)'][g(nh, 0x14)] += 1
    fields['parent+0x52 (MsgHdr+0x18)'][g(nh, 0x18)] += 1
    fields['lyric+0x54 (MsgHdr+0x1a)'][g(lh, 0x1a)] += 1
for k in fields:
    c = fields[k]
    print('  %-28s range=[%d,%d] distinct=%d top=%s' % (k, min(c), max(c), len(c), c.most_common(4)))
print()
for lh, nh in pairs[:4]:
    print('  L', lh.hex(' '))
    print('  N', nh.hex(' '))
