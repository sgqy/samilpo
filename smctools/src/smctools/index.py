"""Index function — extract Samilpo's IndexFiles into open formats.

Implemented (2026-11-07): Score.sci (SSIF, 8449 songs: title/path/lyricist/
composer/year) and CREATOR.CRI (SCIF, 290 creators) via indexfile.py.
SPEECH.OTX parses as an empty SSIF-variant. SamIlPo.idx (SHIF) uses a
different record layout and is not yet derived — see project/research-state.md.

Outputs: one JSON file (open storage) and one self-contained HTML page with a
search box (the single-page query app).
"""

import json
import os
import string
from importlib import resources

from . import indexfile


def _song_fields(rec, i):
    return {
        'i': i,
        'title': rec['g0']['name'],
        'lyricist': rec['g1']['name'],
        'composer': rec['g2']['name'],
        'year': rec['tail'],
        'path': rec['blob'].decode('latin-1').lstrip('\x01\x00').rstrip('\x00'),
        'f0': rec['f0'], 'f1': rec['f1'],
        'g0_items': rec['g0']['items'], 'g0_vals': rec['g0']['vals'],
        'g3': rec['g3']['name'], 'g4': rec['g4']['name'],
        'g1_items': rec['g1']['items'], 'g2_items': rec['g2']['items'],
    }


def extract(index_dir, out_json, out_html=None, software=None, template=None):
    """Convert IndexFiles into open JSON (+ optional single-page HTML app).

    ``template`` overrides the bundled query-app template (a file whose
    ``$payload`` placeholder receives the embedded JSON). Returns a summary
    dict. Raises indexfile.Fail on structural trouble.
    """
    songs = []
    creators = []
    tree = []
    speech = None
    notes = []

    p_sci = os.path.join(index_dir, 'Score.sci')
    if os.path.exists(p_sci):
        info, recs = indexfile.parse_ssif(p_sci)
        songs = [_song_fields(r, i) for i, r in enumerate(recs)]
        notes.append('Score.sci: %d records, residual %d bytes' % (info['count'], info['residual']))
    p_cri = os.path.join(index_dir, 'CREATOR.CRI')
    if os.path.exists(p_cri):
        info, recs = indexfile.parse_scif(p_cri)
        creators = [{'i': i, 'name': r['g0']['name'],
                     'blob': r['blob'].decode('latin-1'),
                     'bio': r['g1']['name']}
                    for i, r in enumerate(recs)]
        notes.append('CREATOR.CRI: %d records, residual %d bytes' % (info['count'], info['residual']))
    p_otx = os.path.join(index_dir, 'SPEECH.OTX')
    if os.path.exists(p_otx):
        info, recs = indexfile.parse_ssif(p_otx, b'SOTF')
        speech = {'count': info['count'], 'residual': info['residual']}
    p_idx = os.path.join(index_dir, 'SamIlPo.idx')
    if os.path.exists(p_idx):
        info, nodes = indexfile.parse_shif(p_idx)
        tree = [{'depth': d, 'name': nd['group']['name'],
                 'child_count': nd['child_count'],
                 'variants': nd['variants'],
                 'items': nd['group']['items'], 'vals': nd['group']['vals']}
                for nd, d in nodes]
        notes.append('SamIlPo.idx: %d tree nodes, residual %d bytes' % (info['count'], info['residual']))

    doc = {
        'dialect': 'samilpo-2.0',
        'songs': songs,
        'creators': creators,
        'tree': tree if p_idx and os.path.exists(p_idx) else [],
        'speech': speech,
        'notes': notes,
    }
    with open(out_json, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1,
                  default=lambda o: o.decode('latin-1') if isinstance(o, bytes) else None)
    written = [out_json]

    if out_html:
        with open(out_html, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(_render(doc, template))
        written.append(out_html)

    return {'songs': len(songs), 'creators': len(creators), 'written': written,
            'notes': notes}


def _render(doc, template=None):
    """Fill the query-app template with the embedded JSON payload.

    Uses the stdlib ``string.Template`` (a ``$payload`` placeholder); pass
    ``template`` to substitute your own layout. Jinja2 would be the upgrade
    path if templates ever need logic, but the zero-dependency default keeps
    the package installable anywhere.
    """
    if template:
        tmpl_src = open(template, encoding='utf-8').read()
    else:
        tmpl_src = resources.files('smctools').joinpath(
            'templates/index.html').read_text(encoding='utf-8')
    payload = json.dumps({'songs': doc['songs']}, ensure_ascii=False,
                         default=lambda o: o.decode('latin-1')
                         if isinstance(o, bytes) else None)
    # $$ would be an escape in string.Template; the JSON payload is passed in
    # as the one and only substitution, so no other $ sequences may appear.
    return string.Template(tmpl_src).substitute(payload=payload)
