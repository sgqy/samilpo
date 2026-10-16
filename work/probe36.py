"""A harmony whose <root-step> could not be resolved ('? major').

Reports every harmony in the output that lacks a root-step, with the source
0x45 node behind it and the FretInfo bytes, so the cause is visible: an absent
FretBoard, a shape whose strings are all muted, or a root outside the table.

Then counts the same condition across the corpus to size the gap.
"""
import argparse
import io
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, r'C:\research\samilpo\work')

HERE = r'C:\research\samilpo\work'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT = r'C:\research\samilpo\work\out_root_gap.txt'


def walk(node):
    for c in getattr(node, 'children', ()) or ():
        m = c.get('msg') if isinstance(c, dict) else c
        if m is None:
            continue
        yield m
        for x in walk(m):
            yield x


def main():
    import smc_read as S
    import smc2ir
    ns = argparse.Namespace(extent='score+ext', accidental_policy='explicit',
                            lyric_line_policy='by-measure-gap', lyric_gap_threshold=480,
                            hyphen_policy='literal', part_merge='auto',
                            accomp_mode='always',
                            emit_layout=False, timesig_clamp=False, dynamic_map=None)
    opts = smc2ir.Options(ns)

    f = open(OUT, 'w', encoding='utf-8')
    w = lambda *a: print(*a, file=f)

    w('=' * 78)
    w('1. 110SSS-001 - the harmony in m17 without a root')
    w('=' * 78)
    p = os.path.join(SONGS, '100SONG', '110SSS', '110SSS-001.smc')
    doc = S.load(p)
    cod = S.load_cod()
    n = 0
    for st in list(doc.system.staff1) + list(doc.system.staff2):
        for mi, meas in enumerate(st.meas):
            for m in walk(meas):
                if m.type != 0x45:
                    continue
                n += 1
                ce = getattr(m, 'chord_extra', None)
                info = ce.info if ce else b''
                fi = ce.fret_info if ce else b''
                root = None
                try:
                    from fret import root_from_fret_info
                    root = root_from_fret_info(fi) if ce else None
                except Exception as e:
                    root = 'ERR %s' % e
                if not root:
                    w('   m%-4d key=%-5d name=%-12r info=%-34s fret_info=%s'
                      % (mi + 1, m.key, (ce.name if ce else b''), info.hex(' '), fi.hex(' ')))
    w('   total 0x45 in this file: %d' % n)

    w('')
    w('=' * 78)
    w('2. corpus - harmony records whose root is null')
    w('=' * 78)
    files = []
    for dirpath, _, names in os.walk(SONGS):
        for nm in names:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    tot = 0
    nulls = 0
    with_null = []
    ex = []
    for i, path in enumerate(files):
        try:
            buf = io.StringIO()
            smc2ir.convert(path, opts, buf)
        except Exception:
            continue
        c = 0
        z = 0
        for line in buf.getvalue().splitlines():
            if '"harmony"' not in line:
                continue
            o = json.loads(line)
            c += 1
            if not o.get('root'):
                z += 1
                if len(ex) < 10:
                    ex.append((os.path.basename(path), o))
        tot += c
        nulls += z
        if z:
            with_null.append((os.path.basename(path), c, z))
        if (i + 1) % 2000 == 0:
            w('   ... %d/%d' % (i + 1, len(files)))

    w('harmony records total     : %d' % tot)
    w('   with a null root       : %d (%.3f%%)' % (nulls, 100.0 * nulls / max(tot, 1)))
    w('files containing any      : %d of %d' % (len(with_null), len(files)))
    for name, c, z in with_null[:30]:
        w('   %-28s %d of %d harmonies' % (name, z, c))
    if len(with_null) > 30:
        w('   ... and %d more' % (len(with_null) - 30))
    w('')
    w('examples:')
    for name, o in ex:
        w('   %s' % name)
        w('      %s' % {k: o.get(k) for k in ('meas', 'on', 'name', 'root', 'kind_text', 'anchored')})
        if 'ext' in o:
            w('      ext.fret_info_hex=%s' % o['ext'].get('fret_info_hex'))
            w('      ext.fret_base=%s' % o['ext'].get('fret_base'))
            w('      ext.info_hex=%s' % o['ext'].get('info_hex'))

    f.close()
    print('wrote', OUT)


if __name__ == '__main__':
    main()
