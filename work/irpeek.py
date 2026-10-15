"""Ad-hoc IR inspection helper (work scratch).

Usage: python work/irpeek.py <file.ndjson> spans|notes <meas>|counts
"""
import collections
import json
import sys


def load(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def main():
    recs = load(sys.argv[1])
    mode = sys.argv[2]
    if mode == 'counts':
        print(dict(collections.Counter(r['kind'] for r in recs)))
        return
    if mode == 'spans':
        spans = [r for r in recs if r['kind'] == 'span']
        idx = collections.defaultdict(lambda: {'start': 0, 'stop': 0})
        for sp in spans:
            if not sp.get('resolved'):
                continue
            idx[(sp['part'], sp['from']['meas'], sp['from']['key'])]['start'] += 1
            idx[(sp['part'], sp['to']['meas'], sp['to']['key'])]['stop'] += 1
        print('spans=%d  index=%d  start=%d stop=%d' % (
            len(spans), len(idx),
            sum(v['start'] for v in idx.values()),
            sum(v['stop'] for v in idx.values())))
        print('kinds:', dict(collections.Counter(s['k'] for s in spans)))
        for k, v in list(idx.items())[:6]:
            print('  ', k, v)
        return
    if mode == 'notes':
        m = int(sys.argv[3])
        for r in recs:
            if r['kind'] == 'note' and r['meas'] == m:
                print(json.dumps(r, ensure_ascii=False))
        for r in recs:
            if r['kind'] == 'measure' and r['n'] == m:
                print('MEASURE', json.dumps(r, ensure_ascii=False))
        return
    if mode == 'kinds':
        for r in recs:
            if r['kind'] == sys.argv[3]:
                print(json.dumps(r, ensure_ascii=False))
        return


if __name__ == '__main__':
    main()
