"""smctools command line.

score   SMC -> IR -> MusicXML (+ side text). Two modes:
          single:  smctools score FILE.smc -o OUT [options]
          batch :  smctools score --install-dir DIR -o OUT [options] [--limit N]
        The converter parameters of parameters.md H are inherited unchanged
        from the work/ design; batch mode auto-reads <install>/889F.cod.
        Type 0x08 marks whose MarkTB index has no confirmed meaning produce a
        warning on stderr and survive as <words> (nothing is dropped).
verify  validate one MusicXML against the IR that produced it.
index   index conversion / score query (placeholder — see index.py).
"""

import argparse
import json
import os
import sys

from . import __version__, pipeline
from . import verify as verify_mod
from .paths import DEFAULT_INSTALL, default_cod


def _add_converter_params(ap):
    ap.add_argument('-o', '--out-dir', required=True,
                    help='output directory (batch: subsets are kept as subdirectories)')
    ap.add_argument('--cod',
                    help='code-table path; default: <install-dir>/889F.cod '
                         '(single mode: the default install table)')
    ap.add_argument('--software', default='smctools ' + __version__)
    ap.add_argument('--namespaced', action='store_true',
                    help='emit the namespaced MusicXML form')
    ap.add_argument('--no-side-text', action='store_true',
                    help='skip the side-text product (verses beside the staff)')
    ap.add_argument('--no-verify', action='store_true',
                    help='skip the IR/MusicXML invariant check')
    # the six parameters of parameters.md H, inherited from work/smc2ir.py
    ap.add_argument('--extent', default='score+ext',
                    choices=['musical', 'score+ext', 'debug'])
    ap.add_argument('--accidental-policy', default='explicit',
                    choices=['explicit', 'transposed'])
    ap.add_argument('--lyric-line-policy', default='by-measure-gap',
                    choices=['by-measure-gap', 'none'])
    ap.add_argument('--lyric-gap-threshold', type=int, default=480)
    ap.add_argument('--hyphen-policy', default='literal',
                    choices=['literal', 'syllabic'])
    ap.add_argument('--part-merge', default='auto', choices=['auto', 'none', 'all'])
    # Accompaniment is not optional. The arrangement stored in the chord
    # symbols is music the source file really contains; it is invisible only
    # because the original program does not draw it, and "not drawn" is a layout
    # state, not a reason to drop material. `--accomp-mode` therefore has a
    # single legal value: there is no way to switch the accompaniment off, and
    # adding another mode would have to be a deliberate decision rather than a
    # quiet default.
    ap.add_argument('--accomp', action='store_true', default=True,
                    help='emit every accompaniment track as its own part '
                         '(always on; hidden material must survive)')
    ap.add_argument('--accomp-mode', default='always', choices=['always'],
                    help='only "always" exists: hidden tracks are never dropped')
    ap.add_argument('--emit-layout', action='store_true')
    ap.add_argument('--timesig-clamp', action='store_true')
    ap.add_argument('--dynamic-map', help='JSON file mapping dynamic code -> name')


def cmd_score(a):
    if a.install_dir:
        # batch mode: auto-read the install's code table unless --cod was given
        a.cod = a.cod or default_cod(a.install_dir)
        opts = pipeline.make_opts(a)
        s = pipeline.convert_corpus(a.install_dir, a.out_dir, opts,
                                    software=a.software, namespaced=a.namespaced,
                                    side=not a.no_side_text,
                                    check=not a.no_verify, limit=a.limit)
        pipeline.print_corpus_summary(s)
        return 0 if not s['fails'] else 1
    if not a.smc:
        sys.stderr.write('score: give a .smc file (single mode) '
                         'or --install-dir (batch mode)\n')
        return 2
    # single mode: an absent --cod falls back to the default install table
    a.cod = a.cod or default_cod()
    opts = pipeline.make_opts(a)
    s = pipeline.convert_file(a.smc, a.out_dir, opts, software=a.software,
                              namespaced=a.namespaced, side=not a.no_side_text,
                              check=not a.no_verify)
    print('%s -> %s' % (os.path.basename(a.smc), s['xml']))
    print('ir: %s' % s['ir'])
    if s['txt']:
        print('side text: %s' % s['txt'])
    print('records: %d' % s['records'])
    print('audit: %s' % json.dumps(s['audit'], ensure_ascii=False))
    for w in s['mark_warnings']:
        sys.stderr.write('WARNING: unknown type 0x08 mark MarkTB[%d] (glyph U+%04X) '
                         'at part %s measure %s — kept as words\n'
                         % (w['code'], w['glyph'] or 0, w['part'], w['meas']))
    if s['problems']:
        print('PROBLEMS: %d' % len(s['problems']))
        for p in s['problems'][:25]:
            print('   ', p)
        return 1
    if not a.no_verify:
        print('verify: OK')
    return 0


def cmd_verify(a):
    return verify_mod.run(a.ir, a.xml)


def cmd_index(a):
    from .index import run
    return run(a.index_args)


def main():
    ap = argparse.ArgumentParser(prog='smctools', description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('score', help='convert scores (single file or whole install)')
    sp.add_argument('smc', nargs='?', help='.smc file (single mode)')
    sp.add_argument('--install-dir', default=None,
                    help='batch mode: install directory (default corpus layout '
                         '<dir>/8000Songs/**/*.smc); default: %s' % DEFAULT_INSTALL)
    _add_converter_params(sp)
    sp.add_argument('--limit', type=int, default=0,
                    help='batch: convert only the first N files (testing)')
    sp.set_defaults(func=cmd_score)

    vp = sub.add_parser('verify', help='validate a MusicXML against its IR')
    vp.add_argument('ir')
    vp.add_argument('xml')
    vp.set_defaults(func=cmd_verify)

    ip = sub.add_parser('index', help='index conversion / score query (placeholder)')
    ip.add_argument('index_args', nargs='*')
    ip.set_defaults(func=cmd_index)

    a = ap.parse_args()
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
