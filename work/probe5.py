"""Structure inventory across the whole corpus (work scratch).

Usage: python work/probe5.py [--dir <songs dir>] [--max N] [--csv <out>]

Collects, per file: layout shape, msg-type census, timesig/keysig census, voice
usage, note flags, tie/slur endpoint resolution, lyric stats, chord/fret stats.
Prints aggregate tables that the IR design can cite as measured facts.
"""
import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc_read as S
from probe_smc import walk_msgs, play_time, tick_per_meas, tname

DEFAULT_DIR = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'


def files(d, maxn):
    """Recursively collect *.smc under d."""
    out = sorted(glob.glob(os.path.join(d, '**', '*.smc'), recursive=True))
    return out[:maxn] if maxn else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DEFAULT_DIR)
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--csv', default=None)
    args = ap.parse_args()

    cnt = collections.Counter()
    flags = collections.Counter()
    vers = collections.Counter()
    fails = []
    nfile = 0
    cod = None
    lyric_lens = collections.Counter()
    try:
        cod = S.load_cod()
    except Exception as e:
        print('889F.cod unavailable: %s' % e)

    for path in files(args.dir, args.max):
        nfile += 1
        try:
            doc = S.load(path)
        except S.Fail as e:
            fails.append((os.path.basename(path), str(e)))
            continue
        vers[doc.version] += 1
        cnt['files'] += 1
        cnt['meas'] += sum(len(st.meas) for st in doc.system.staff1 + doc.system.staff2)
        cnt['staves'] += len(doc.system.staff1) + len(doc.system.staff2)
        cnt['staff2'] += len(doc.system.staff2)
        cnt['pages'] += doc.doc_pages
        cnt['wholeTick=%d' % doc.system.whole_tick] += 1

        keys_here = {}
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                for meas in st.meas:
                    cnt['timesig=%d/%d' % (meas.ts_num, meas.ts_den)] += 1
                    cnt['keysig_type=%d' % meas.keysig_type] += 1
                    cnt['keysig_sym=%d' % meas.keysig_symbol] += 1
                    cnt['keysig_n=%d' % meas.keysig_count] += 1
                    for c in meas.children:
                        if not c['msg']:
                            continue
                        for m, dd in walk_msgs([c['msg']]):
                            cnt['type:' + tname(m.type)] += 1
                            cnt['voice=%d' % m.voice] += 1
                            if m.type == 0x01:
                                flags['note flags 0x%04x' % m.flags] += 1
                                flags['headtype=%d' % m.head_type] += 1
                                flags['note dots=%d' % m.dots] += 1
                                flags['note exp=%d' % (m.type_index & 0x1F)] += 1
                                flags['note vel=%d' % m.head[1]] += 1
                            if m.type == 0x19:
                                n = m.head[0x0C] if len(m.head) >= 0x0D else 0
                                lyric_lens['headlen=%d' % m.head_len] += 1
                                lyric_lens['bytelen=%d' % n] += 1
                                if cod and m.lyric_bytes:
                                    s = S.decode(m.lyric_bytes, cod)
                                    lyric_lens['chars=%d' % len(s)] += 1
                                    for ch in s:
                                        if 0xF000 <= ord(ch) < 0xF100:
                                            lyric_lens['PUA-in-text'] += 1
                            if m.type in (0x09, 0x0A, 0x12):
                                keys_here[m.key] = 1
        # endpoint resolution per file
        allkeys = set()
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                for meas in st.meas:
                    for c in meas.children:
                        if c['msg']:
                            for m, dd in walk_msgs([c['msg']]):
                                allkeys.add(m.key)
        dead = 0
        for gi, g in (('s1', doc.system.staff1), ('s2', doc.system.staff2)):
            for st in g:
                for meas in st.meas:
                    for c in meas.children:
                        if c['msg']:
                            for m, dd in walk_msgs([c['msg']]):
                                if m.type in (0x09, 0x0A, 0x12):
                                    if m.endpoint not in allkeys:
                                        dead += 1
        cnt['endpoint-dead-total'] += dead

    print('files parsed: %d   failures: %d' % (cnt['files'], len(fails)))
    for f, e in fails[:10]:
        print('   FAIL %s : %s' % (f, e))
    print()
    print('version            : %s' % dict(vers))
    print('wholeTick          : %s' % {k: v for k, v in cnt.items() if k.startswith('wholeTick')})
    print('pages total        : %d' % cnt['pages'])
    print('staves total       : %d (staff2=%d)' % (cnt['staves'], cnt['staff2']))
    print('measures total     : %d' % cnt['meas'])
    print()
    print('msg type census:')
    for k, v in sorted(cnt.items()):
        if k.startswith('type:'):
            print('   %-12s %d' % (k[5:], v))
    print()
    print('voices        : %s' % {k: v for k, v in sorted(cnt.items()) if k.startswith('voice=')})
    print('timesigs      : %s' % {k: v for k, v in sorted(cnt.items()) if k.startswith('timesig=')})
    print('keysig type   : %s' % {k: v for k, v in sorted(cnt.items()) if k.startswith('keysig_type')})
    print('keysig symbol : %s' % {k: v for k, v in sorted(cnt.items()) if k.startswith('keysig_sym')})
    print('keysig count  : %s' % {k: v for k, v in sorted(cnt.items()) if k.startswith('keysig_n')})
    print('unresolved endpoints (total): %d' % cnt['endpoint-dead-total'])
    print()
    print('note flag/attr detail:')
    for k, v in sorted(flags.items()):
        print('   %-22s %d' % (k, v))
    print()
    print('lyric head length / decoded char count:')
    for k, v in sorted(lyric_lens.items(), key=lambda kv: str(kv[0])):
        print('   %-16s %d' % (k, v))


if __name__ == '__main__':
    main()
