"""Convert one .smc into all products: IR, MusicXML and side text.

Usage:
    python work/smc_convert.py <file.smc> [--out-dir DIR] [options]

Always writes <stem>.ndjson and <stem>.musicxml. Writes <stem>.txt only when the
source carries multi-line side text (verses 2 and 3 written beside the staff).

Any other option is passed straight through to smc2ir.py, so the six parameters
of parameters.md H remain available here.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(args):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                       encoding='utf-8')
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(r.returncode)
    return r


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('smc')
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--no-side-text', action='store_true')
    known, passthrough = ap.parse_known_args()

    stem = os.path.splitext(os.path.basename(known.smc))[0]
    out_dir = known.out_dir or HERE
    os.makedirs(out_dir, exist_ok=True)
    ir = os.path.join(out_dir, stem + '.ndjson')
    xml = os.path.join(out_dir, stem + '.musicxml')
    txt = os.path.join(out_dir, stem + '.txt')

    run([os.path.join(HERE, 'smc2ir.py'), known.smc, ir] + passthrough)
    run([os.path.join(HERE, 'ir2musicxml.py'), ir, xml])
    print('%s written' % xml)

    if not known.no_side_text:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'side_text.py'),
                            ir, txt, '--header'],
                           capture_output=True, text=True, encoding='utf-8')
        if r.returncode == 0:
            print(r.stdout.strip())
        elif 'no multi-line side text' not in (r.stdout + r.stderr):
            sys.stderr.write(r.stderr)
        if not os.path.exists(txt):
            pass


if __name__ == '__main__':
    main()
