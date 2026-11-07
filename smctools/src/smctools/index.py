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


def extract(index_dir, out_json, out_html=None, software=None):
    """Convert IndexFiles into open JSON (+ optional single-page HTML app).

    Returns a summary dict. Raises indexfile.Fail on structural trouble.
    """
    songs = []
    creators = []
    speech = None
    notes = []

    p_sci = os.path.join(index_dir, 'Score.sci')
    if os.path.exists(p_sci):
        info, recs = indexfile.parse(p_sci, b'SSIF')
        songs = [_song_fields(r, i) for i, r in enumerate(recs)]
        notes.append('Score.sci: %d records, residual %d bytes' % (info['count'], info['residual']))
    p_cri = os.path.join(index_dir, 'CREATOR.CRI')
    if os.path.exists(p_cri):
        # SCIF (290 creators) uses a different record class: its strings are
        # ANSI (font names like "WKLGothic" appear where SSIF has wide text).
        # Needs FUN_004165E0's own record derivation - see research-state.md.
        try:
            info, recs = indexfile.parse(p_cri, b'SCIF')
            creators = [{'i': i, 'name': r['g0']['name'], 'blob': r['blob'].decode('latin-1'),
                         'g1': r['g1']['name'], 'g2': r['g2']['name'], 'tail': r['tail']}
                        for i, r in enumerate(recs)]
            notes.append('CREATOR.CRI: %d records, residual %d bytes' % (info['count'], info['residual']))
        except indexfile.Fail as e:
            notes.append('CREATOR.CRI: record layout differs from SSIF - skipped (%s)' % e)
    p_otx = os.path.join(index_dir, 'SPEECH.OTX')
    if os.path.exists(p_otx):
        info, recs = indexfile.parse(p_otx, b'SOTF')
        speech = {'count': info['count'], 'residual': info['residual']}
    p_idx = os.path.join(index_dir, 'SamIlPo.idx')
    if os.path.exists(p_idx):
        notes.append('SamIlPo.idx: present but SHIF record layout not yet derived - skipped')

    doc = {
        'dialect': 'samilpo-2.0',
        'songs': songs,
        'creators': creators,
        'speech': speech,
        'notes': notes,
    }
    with open(out_json, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    written = [out_json]

    if out_html:
        with open(out_html, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(_html(doc, software or 'smctools'))
        written.append(out_html)

    return {'songs': len(songs), 'creators': len(creators), 'written': written,
            'notes': notes}


_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>Samilpo index query</title>
<style>
body{font:14px/1.5 system-ui,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;margin:20px auto;max-width:980px;color:#1b1b1b}
h1{font-size:20px}input{font:16px inherit;padding:6px 10px;width:60%%}
table{border-collapse:collapse;width:100%%;margin-top:12px}
th,td{border:1px solid #ccc;padding:4px 8px;text-align:left;font-size:13px}
th{background:#f3f3f3;position:sticky;top:0}
td.num{font-variant-numeric:tabular-nums}
.c{color:#888;font-size:12px}
</style></head><body>
<h1>Samilpo乐谱索引查询 <span class="c" id="n"></span></h1>
<p><input id="q" placeholder="曲名 / 作词 / 作曲 / 年份 / 路径…（支持正则）" autofocus></p>
<table><thead><tr><th>#</th><th>曲名</th><th>作词</th><th>作曲</th><th>年份</th><th>路径</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
const DATA = %s;
const rows = document.getElementById('rows'), q = document.getElementById('q');
document.getElementById('n').textContent = '(' + DATA.songs.length + ' 首)';
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function render(){
  let re = null;
  try { re = new RegExp(q.value, 'i'); } catch(e) { re = null; }
  const out = [];
  for (const s of DATA.songs) {
    const hay = s.title + '\\n' + s.lyricist + '\\n' + s.composer + '\\n' + (s.year ?? '') + '\\n' + s.path;
    if (q.value && !(re ? re.test(hay) : hay.includes(q.value))) continue;
    out.push('<tr><td class="num">' + s.i + '</td><td>' + esc(s.title) + '</td><td>' +
      esc(s.lyricist) + '</td><td>' + esc(s.composer) + '</td><td class="num">' +
      (s.year ?? '?') + '</td><td class="c">' + esc(s.path) + '</td></tr>');
    if (out.length >= 500) { out.push('<tr><td colspan=6 class="c">… 仅显示前 500 条，请继续输入缩小范围</td></tr>'); break; }
  }
  rows.innerHTML = out.join('');
}
q.addEventListener('input', render); render();
</script></body></html>
"""


def _html(doc, software):
    payload = json.dumps({'songs': doc['songs']}, ensure_ascii=False)
    return _HTML % payload
