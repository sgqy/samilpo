"""Batch-run smc_walk over a sample of files and summarise outcomes (read-only)."""
import sys, os, random, io, contextlib, collections
sys.path.insert(0, os.path.dirname(__file__))
import smc_walk

root = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
files = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if f.lower().endswith('.smc')]
random.seed(1)
sample = files if n <= 0 else random.sample(files, min(n, len(files)))
res = collections.Counter(); ver = collections.Counter(); types = collections.Counter(); bad = []
for f in sample:
    smc_walk.stats.clear(); smc_walk.msg_types.clear()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            smc_walk.main(f)
        out = buf.getvalue()
    except Exception as e:
        out = buf.getvalue() + '\nEXC %r' % e
    for line in out.splitlines():
        if line.startswith('magic='):
            ver[line.split('version=')[1]] += 1
    if 'consumed body' in out and 'FAIL' not in out:
        a, b = out.split('consumed body ')[1].split('\n')[0].split(' / ')
        ok = a == b
        tail = out.split('trailer after body (')[1].split(' ')[0]
        res['ok_exact' if ok else 'ok_partial'] += 1
        res['trailer_%s' % tail] += 1
        types.update(smc_walk.msg_types)
    else:
        res['fail'] += 1
        bad.append((f, [l for l in out.splitlines() if 'FAIL' in l or 'EXC' in l or 'legacy' in l][:1]))
print('files', len(files), 'sampled', len(sample))
print(dict(res)); print('versions', dict(ver))
print('msg types', {hex(k): v for k, v in sorted(types.items())})
for f, l in bad[:20]:
    print('BAD', f, l)
