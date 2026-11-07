"""smctools command line.

score   SMC -> IR -> MusicXML (+ side text). Two modes:
          single:  smctools score FILE.smc -o OUT [options]
          batch :  smctools score --install-dir DIR -o OUT [options] [--limit N]
        The converter parameters of parameters.md H are inherited unchanged
        from the work/ design. The code table resolves as --cod >
        (--install-dir | SAMILPO_INSTALL)/889F.cod; with none of these the
        command refuses to run rather than degrading text decoding.
        Type 0x08 marks whose MarkTB index has no confirmed meaning produce a
        warning on stderr and survive as <words> (nothing is dropped).
verify  validate one MusicXML against the IR that produced it.
index   index conversion / score query (placeholder — see index.py).

The package is machine-independent: no install path is baked in anywhere.
"""

import argparse
import json
import os
import sys

from . import __version__, pipeline, paths
from . import verify as verify_mod


def _add_output_params(ap):
    ap.add_argument('-o', '--out-dir', required=True,
                    help='output directory (batch: subsets are kept as subdirectories)')


def _add_converter_params(ap):
    _add_output_params(ap)
    ap.add_argument('--cod',
                    help='code table for Samilpo 2.0 files (889F.cod from the '
                         'install dir). The original Music Score Viewer format '
                         'stores text as UTF-16 and needs no table; omitting '
                         'the table on Samilpo files yields wrong text characters.')
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


def _resolve_cod(a):
    """--cod > (--install-dir | SAMILPO_INSTALL)/889F.cod; None when
    unresolvable (the caller then runs in original-dialect mode)."""
    if a.cod:
        return a.cod
    install = paths.resolve_install(a.install_dir)
    return paths.cod_path(install) if install else None


def _note_no_cod(a):
    if a.cod:
        return
    sys.stderr.write(
        'note: no code table given - text is decoded as UTF-16LE '
        '(original Music Score Viewer dialect).\n'
        '  For Samilpo 2.0 files load its table: --cod <install>\\889F.cod, '
        '--install-dir <dir>, or SAMILPO_INSTALL.\n')


def _score_single(a):
    a.cod = _resolve_cod(a)
    if a.cod and not os.path.isfile(a.cod):
        sys.stderr.write('score: code table not found: %s\n' % a.cod)
        return 2
    _note_no_cod(a)
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


def _score_batch(a):
    install = paths.resolve_install(a.install_dir)
    if not install:
        sys.stderr.write('score: batch mode needs the install directory.\n'
                         '  Provide --install-dir <dir> or set %s.\n'
                         % paths.INSTALL_ENV)
        return 2
    a.cod = a.cod or paths.cod_path(install)
    if a.cod and not os.path.isfile(a.cod):
        sys.stderr.write('note: %s not found - running without a code table '
                         '(original-dialect text decoding).\n' % a.cod)
        a.cod = None
    _note_no_cod(a)
    opts = pipeline.make_opts(a)
    s = pipeline.convert_corpus(install, a.out_dir, opts,
                                software=a.software, namespaced=a.namespaced,
                                side=not a.no_side_text,
                                check=not a.no_verify, limit=a.limit)
    pipeline.print_corpus_summary(s)
    return 0 if not s['fails'] else 1


def cmd_score(a):
    if a.smc and a.install_dir:
        sys.stderr.write('score: give either a .smc file (single mode) '
                         'or --install-dir (batch mode), not both\n')
        return 2
    if a.smc:
        return _score_single(a)
    return _score_batch(a)
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
    from . import index
    if a.action != 'extract':
        sys.stderr.write('index: unknown action %r (only "extract" is '
                         'implemented; SHIF/SamIlPo.idx not yet derived)\n' % a.action)
        return 2
    install = paths.resolve_install(a.install_dir)
    if not install:
        sys.stderr.write('index: needs --install-dir or %s.\n' % paths.INSTALL_ENV)
        return 2
    os.makedirs(a.out_dir, exist_ok=True)
    s = index.extract(os.path.join(install, 'IndexFiles'),
                      os.path.join(a.out_dir, 'score-index.json'),
                      None if a.no_html else os.path.join(a.out_dir, 'index.html'),
                      template=a.template)
    print('songs: %d  creators: %d' % (s['songs'], s['creators']))
    for w in s['written']:
        print('written: %s' % w)
    for n in s['notes']:
        print('note: %s' % n)
    return 0


def main():
    ap = argparse.ArgumentParser(prog='smctools', description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('score', help='convert scores (single file or whole install)')
    sp.add_argument('smc', nargs='?', help='.smc file (single mode)')
    sp.add_argument('--install-dir', default=None,
                    help='install directory (batch corpus layout '
                         '<dir>/8000Songs/**/*.smc); default: the '
                         'SAMILPO_INSTALL environment variable')
    _add_converter_params(sp)
    sp.add_argument('--limit', type=int, default=0,
                    help='batch: convert only the first N files (testing)')
    sp.set_defaults(func=cmd_score)

    vp = sub.add_parser('verify', help='validate a MusicXML against its IR')
    vp.add_argument('ir')
    vp.add_argument('xml')
    vp.set_defaults(func=cmd_verify)

    ip = sub.add_parser('index',
                        help='convert the install indexes into open storage + '
                             'a single-page query app')
    ip.add_argument('action', nargs='?', default='extract',
                    help='only "extract" is implemented')
    ip.add_argument('--install-dir', default=None,
                    help='install directory; default: the SAMILPO_INSTALL '
                         'environment variable')
    ip.add_argument('--no-html', action='store_true',
                    help='skip the single-page query app (JSON only)')
    ip.add_argument('--template',
                    help='custom query-app template (string.Template with a '
                         '$payload placeholder); default: the bundled one')
    _add_output_params(ip)
    ip.set_defaults(func=cmd_index)

    a = ap.parse_args()
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
