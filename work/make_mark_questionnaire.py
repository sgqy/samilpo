"""Build the MarkTB identification questionnaire.

One corpus pass collects, per type 0x08 mark index, how the mark is used
(container, dy sign, measure position, sample locations).  Each index is then
rendered from KAYAKUMA.TTF and everything is written to a self-contained HTML
questionnaire plus a TSV answer sheet for a human to fill in.

The point is to stop guessing at glyph identity from outlines: a person looking
at the running program (or a printed score) can name each symbol in seconds.
"""
import base64
import collections
import io
import json
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from PIL import Image, ImageDraw

sys.path.insert(0, r'C:\research\samilpo\work')
import smc_read as S

FONT = r'C:\Program Files (x86)\Samilpo 2.0\Font\KAYAKUMA.TTF'
SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'
OUT_HTML = r'C:\research\samilpo\work\mark-questionnaire.html'
OUT_TSV = r'C:\research\samilpo\work\mark-questionnaire.tsv'
OUT_JSON = r'C:\research\samilpo\work\mark-stats.json'
SAMPLE_FILE = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs\500KFS\500KFS-0041.smc'

# MarkTB at 0x1010059C: 51 entries x 6 bytes; byte 0 is the font code, the rest
# is zero in this build.  Font byte 0xNN renders as U+F0NN in KAYAKUMA.TTF.
MARKTB = [0x00, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x62, 0x56, 0x57, 0x58, 0x59, 0x5c,
          0x65, 0x55, 0x4e, 0x2b, 0x2c, 0x5a, 0x5b, 0x51, 0x52, 0x50, 0x4f, 0x54,
          0x53, 0x73, 0x75, 0x74, 0x76, 0x63, 0x64, 0x7d, 0x7c, 0x77, 0x79, 0x78,
          0x68, 0x70, 0x6f, 0x71, 0x7a, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0x4b,
          0x4a, 0xa9, 0xaa]


# --------------------------------------------------------------- glyph render

def contours_of(pen_value, steps=24):
    out, cur, start = [], [], None

    def quad(p0, c, p1):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p1[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p1[1])
                for t in (i / steps for i in range(1, steps + 1))]

    for op, args in pen_value:
        if op == 'moveTo':
            if cur:
                out.append(cur)
            cur = [args[0]]
            start = args[0]
        elif op == 'lineTo':
            cur.append(args[0])
        elif op == 'qCurveTo':
            pts = list(args)
            if pts[-1] is None:
                pts[-1] = start
            offs, endpt = pts[:-1], pts[-1]
            for i in range(len(offs) - 1):
                c, nxt = offs[i], offs[i + 1]
                cur.extend(quad(cur[-1], c, ((c[0] + nxt[0]) / 2, (c[1] + nxt[1]) / 2)))
            if offs:
                cur.extend(quad(cur[-1], offs[-1], endpt))
            else:
                cur.append(endpt)
        elif op == 'curveTo':
            pts = list(args)
            p0, c1, c2, p1 = cur[-1], pts[-3], pts[-2], pts[-1]
            for i in range(1, steps + 1):
                t = i / steps
                mt = 1 - t
                cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p1[0],
                            mt ** 3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p1[1]))
        elif op == 'closePath':
            if cur:
                out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [c for c in out if len(c) > 2]


class Glyphs:
    def __init__(self):
        self.font = TTFont(FONT, lazy=True)
        self.cmap = self.font.getBestCmap()
        self.gs = self.font.getGlyphSet()

    def png(self, idx, CW=190, CH=190, color=(0, 0, 0)):
        g = MARKTB[idx]
        img = Image.new('RGB', (CW, CH), 'white')
        name = self.cmap.get(0xF000 | g) if g else None
        if not name:
            return img
        pen = RecordingPen()
        self.gs[name].draw(pen)
        cs = contours_of(pen.value)
        if not cs:
            return img
        xs = [p[0] for c in cs for p in c]
        ys = [p[1] for c in cs for p in c]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        dx, dy = (x1 - x0) or 1.0, (y1 - y0) or 1.0
        pad = 12
        sc = min((CW - 2 * pad) / dx, (CH - 2 * pad) / dy)
        mask = Image.new('L', (CW, CH), 0)
        for c in cs:
            tmp = Image.new('L', (CW, CH), 0)
            td = ImageDraw.Draw(tmp)
            pts = [(pad + (p[0] - x0) * sc, CH - pad - (p[1] - y0) * sc) for p in c]
            td.polygon(pts, fill=255)
            mask = Image.frombytes('L', (CW, CH),
                                   bytes(a ^ b for a, b in zip(mask.tobytes(), tmp.tobytes())))
        img.paste(Image.new('RGB', (CW, CH), color), (0, 0), mask)
        return img


def b64(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


# ------------------------------------------------------------- corpus survey

def iter_marks(doc):
    """Yield (mark_msg, container_kind, staff_no, measure_index, note_info)."""
    staves = []
    for st in list(getattr(doc.system, 'staff1', []) or []):
        staves.append(st)
    for st in list(getattr(doc.system, 'staff2', []) or []):
        staves.append(st)
    # system-level and page-level message trees, no measure context
    roots = [(doc.system, None, None)]
    for pg in doc.pages:
        roots.append((pg, None, None))
    for root, _, _ in roots:
        stack = [(root, 'system', None, None, None)]
        while stack:
            node, kind, staff_no, mi, note = stack.pop()
            for c in getattr(node, 'children', ()) or ():
                m = c.get('msg') if isinstance(c, dict) else c
                if m is None:
                    continue
                if m.type == 0x08:
                    yield m, kind, staff_no, mi, note
                ck = {1: 'note', 3: 'rest', 0x14: 'beam', 0x25: 'chord',
                      0x45: 'chord symbol'}.get(m.type, 'msg%02x' % m.type)
                nxt_note = m if m.type == 0x01 else note
                stack.append((m, ck, staff_no, mi, nxt_note))
    for si, st in enumerate(staves):
        for mi, meas in enumerate(getattr(st, 'meas', []) or []):
            stack = [(meas, 'measure', si, mi, None)]
            while stack:
                node, kind, staff_no, mix, note = stack.pop()
                for c in getattr(node, 'children', ()) or ():
                    m = c.get('msg') if isinstance(c, dict) else c
                    if m is None:
                        continue
                    if m.type == 0x08:
                        yield m, kind, staff_no, mix, note
                    ck = {1: 'note', 3: 'rest', 0x14: 'beam', 0x25: 'chord',
                          0x45: 'chord symbol'}.get(m.type, 'msg%02x' % m.type)
                    nxt_note = m if m.type == 0x01 else note
                    stack.append((m, ck, staff_no, mix, nxt_note))


def survey():
    files = []
    for dp, _, nms in os.walk(SONGS):
        for nm in nms:
            if nm.lower().endswith('.smc'):
                files.append(os.path.join(dp, nm))
    files.sort()

    total = collections.Counter()
    owner = collections.defaultdict(collections.Counter)
    dysign = collections.defaultdict(collections.Counter)
    fileset = collections.defaultdict(set)
    samples = collections.defaultdict(list)
    n_files = 0
    n_marks = 0

    for p in files:
        try:
            doc = S.load(p)
        except Exception:
            continue
        n_files += 1
        base = os.path.basename(p)
        for m, ck, staff_no, mi, note in iter_marks(doc):
            idx = m.head_type
            if not (0 <= idx < len(MARKTB)):
                continue
            total[idx] += 1
            n_marks += 1
            owner[idx][ck] += 1
            dysign[idx]['dy<0 (выше)' if False else ('dy<0' if m.dy < 0 else ('dy>0' if m.dy > 0 else 'dy=0'))] += 1
            fileset[idx].add(base)
            if len(samples[idx]) < 10:
                ctx = ''
                if note is not None:
                    ctx = 'note start=%d dur=%d' % (note.start, getattr(note, 'duration', 0))
                samples[idx].append({
                    'file': base,
                    'staff': staff_no,
                    'measure': (mi + 1) if mi is not None else None,
                    'container': ck,
                    'dx': m.dx, 'dy': m.dy, 'voice': m.voice,
                    'start': m.start,
                    'ctx': ctx,
                    'off': m.off,
                })

    print('survey: %d files, %d marks, %d indices' % (n_files, n_marks, len(total)),
          file=sys.stderr)
    return {
        'files': n_files,
        'marks': n_marks,
        'total': {str(k): v for k, v in total.items()},
        'owner': {str(k): dict(v) for k, v in owner.items()},
        'dysign': {str(k): dict(v) for k, v in dysign.items()},
        'files_per_index': {str(k): len(v) for k, v in fileset.items()},
        'samples': {str(k): v for k, v in samples.items()},
    }


def sample_file_marks():
    doc = S.load(SAMPLE_FILE)
    rows = []
    for m, ck, staff_no, mi, note in iter_marks(doc):
        rows.append({
            'staff': staff_no,
            'measure': (mi + 1) if mi is not None else None,
            'container': ck,
            'idx': m.head_type,
            'byte': MARKTB[m.head_type] if 0 <= m.head_type < len(MARKTB) else None,
            'dx': m.dx, 'dy': m.dy, 'voice': m.voice,
            'note': ('start=%d dur=%d' % (note.start, getattr(note, 'duration', 0))) if note else '',
            'off': m.off,
        })
    rows.sort(key=lambda r: (r['measure'] or 0, r['off']))
    return rows


# ------------------------------------------------------------------ artifacts

def main():
    stats = survey()
    sample_rows = sample_file_marks()
    stats['sample_file'] = {'path': SAMPLE_FILE, 'rows': sample_rows}
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)

    gl = Glyphs()
    used = sorted(int(k) for k in stats['total'])
    if not used:
        raise SystemExit('corpus survey found no type 0x08 marks')

    # full table strip for the appendix
    allimgs = [gl.png(i, 96, 96) for i in range(len(MARKTB))]
    cols = 13
    rows = (len(allimgs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 96, rows * 112), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(allimgs):
        cx, cy = (i % cols) * 96, (i // cols) * 112
        sheet.paste(im, (cx + 4, cy + 4))
        d.rectangle([cx, cy, cx + 95, cy + 111], outline=(190, 190, 190))
        d.text((cx + 5, cy + 98), '[%d] 0x%02X' % (i, MARKTB[i]), fill=(0, 0, 0))
    atlas_b64 = b64(sheet)

    html = []
    w = html.append
    w('<!doctype html><html lang="zh"><head><meta charset="utf-8">')
    w('<title>SMC type 0x08 记号识别问卷</title>')
    w('<style>')
    w('body{font:14px/1.55 -apple-system,"Segoe UI",Roboto,"Noto Sans CJK SC",sans-serif;'
      'margin:24px auto;max-width:1180px;color:#1b1b1b}')
    w('h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;'
      'border-bottom:2px solid #ddd;padding-bottom:4px}')
    w('table{border-collapse:collapse;width:100%;margin:8px 0 4px}')
    w('th,td{border:1px solid #cfcfcf;padding:6px 8px;vertical-align:top;text-align:left}')
    w('th{background:#f3f3f3;font-weight:600;font-size:13px}')
    w('td.num{font-variant-numeric:tabular-nums}')
    w('.glyph{text-align:center;background:#fff}')
    w('.fill{background:#fffdf0}')
    w('code{background:#f4f4f4;padding:1px 4px;border-radius:3px;font-size:12px}')
    w('.note{background:#f7f9fc;border-left:3px solid #4a7fb5;padding:8px 12px;margin:10px 0}')
    w('.warn{background:#fff6f4;border-left:3px solid #c0563a;padding:8px 12px;margin:10px 0}')
    w('img.atlas{width:100%;border:1px solid #ccc}')
    w('ol{margin:6px 0 6px 22px}li{margin:6px 0}')
    w('</style></head><body>')

    w('<h1>SMC <code>type 0x08</code> 记号识别问卷</h1>')
    w('<p>目标：为 <b>Samilpo 2.0</b> 的 <code>type 0x08</code>（<code>CScoreView::DrawMark</code>）'
      '逐项确认音乐含义，以便映射到 MusicXML。字形本身只有轮廓可依据——程序里没有任何字符串'
      '资源给出记号名称（已全量搜索 Shift-JIS / 889F / UTF-16 三种编码），所以必须由人眼判定。</p>')

    w('<h2>1. 已确证的事实（不需要您回答）</h2>')
    w('<ul>')
    w('<li><code>MarkTB</code> 在 <code>engine.dll 0x1010059C</code>，51 项 × 6 字节；'
      '第 0 字节是字体码，其余 5 字节在本版本全为 0。</li>')
    w('<li><code>DrawMark</code>（<code>0x10065570</code>）取 <code>glyph = MarkTB[MsgHdr+0x06]</code>，'
      '用 <code>DrawTextOut</code> 画 <b>1 个字符</b>；位置 = <code>obj+0x50</code>/<code>obj+0x52</code>'
      '（X/Y）加缩放。<code>MsgHdr+0x05==2</code> 时走绝对定位分支。</li>')
    w('<li>字体 <code>Font\\KAYAKUMA.TTF</code> 是 Windows 符号字体，字体码 <code>0xNN</code> '
      '渲染为 <code>U+F0NN</code>；glyph 名（<code>U</code>、<code>comma</code>…）是无意义占位名。</li>')
    w('<li>全语料 8451 个 <code>.smc</code> 中 <code>type 0x08</code> 共 <b>%d</b> 条，'
      '只用到下表 14 个索引。所有记录的 <code>headLen=0</code>、<code>flags=0</code>，'
      '即记号除索引与位置外不带其他参数。</li>' % stats['marks'])
    w('<li><code>CSMMsg::Read</code> 把 <code>type 0x41</code> 重映射为 <code>0x08</code>，'
      '但本语料中不存在 0x41。</li>')
    w('<li><code>obj+0x74</code>/<code>obj+0x75</code>（= <code>MsgHdr+0x03</code>/<code>+0x04</code>）'
      '另有一套「音符上/下方记号」槽位，<code>&amp;0x7F</code> 是索引、<code>&amp;0x80</code> 是加圆括号；'
      '本语料中该两个字节全为 0，未使用。</li>')
    w('</ul>')

    w('<h2>2. 需要您判定的 14 个索引</h2>')
    w('<div class="note">每行请填写：<b>名称</b>（中文/한국어/日本語任一）、'
      '<b>类别</b>（弓法 bowing / 奏法 articulation / 装饰音 ornament / 力度 dynamic / '
      '延音 fermata / 其他）、<b>MusicXML 元素</b>（见第 4 节候选清单）。'
      '答案请直接填在 <code>work/mark-questionnaire.tsv</code>（最后一列备注可自由填写）。</div>')

    w('<table><tr>')
    w('<th style="width:104px">字形</th><th style="width:74px">索引</th>')
    w('<th style="width:64px">出现次数</th><th style="width:104px">所属容器</th>')
    w('<th style="width:96px">dy 分布</th><th style="width:56px">文件数</th>')
    w('<th>语料中的典型位置</th></tr>')
    for idx in used:
        total = stats['total'][str(idx)]
        owner = stats['owner'][str(idx)]
        dys = stats['dysign'][str(idx)]
        nf = stats['files_per_index'][str(idx)]
        samples = stats['samples'][str(idx)]
        samp = '<br>'.join(
            '%s 第%s小节 %s dx=%d dy=%d%s' % (
                s['file'], s['measure'] if s['measure'] is not None else '-',
                s['container'], s['dx'], s['dy'],
                (' · ' + s['ctx']) if s['ctx'] else '')
            for s in samples[:4])
        w('<tr>')
        w('<td class="glyph"><img src="%s" width="96" height="96" alt="MarkTB[%d]"></td>'
          % (b64(gl.png(idx, 128, 128)), idx))
        w('<td class="num"><b>%d</b><br><code>0x%02X</code><br>U+F0%02X</td>'
          % (idx, MARKTB[idx], MARKTB[idx]))
        w('<td class="num">%d</td>' % total)
        w('<td>%s</td>' % '<br>'.join('%s x%d' % (k, v) for k, v in sorted(owner.items())))
        w('<td>%s</td>' % '<br>'.join('%s x%d' % (k, v) for k, v in sorted(dys.items())))
        w('<td class="num">%d</td>' % nf)
        w('<td style="font-size:12px">%s</td>' % samp)
        w('</tr>')
    w('</table>')

    w('<h2>3. 重点疑问：500KFS-0041.smc 的「&gt; 形记号」</h2>')
    w('<div class="warn">您提到该文件里看着像 <code>&gt;</code> 的力度记号中，'
      '<b>有一个其实是延音记号</b>。这个文件恰好同时出现索引 13 与索引 29，'
      '而两者的字形轮廓差别很大（见下）。请对照程序画面确认：'
      '<b>同一索引是否会在不同位置被画成不同符号</b>，还是「&gt; 形」与「延音」本来就是两个索引。</div>')

    pair = [(13, 'occurrences in 500KFS-0041'), (29, 'occurrences in 500KFS-0041')]
    w('<table><tr><th style="width:150px">索引与字形</th><th>该文件中的全部出现位置</th></tr>')
    for idx, _ in pair:
        occ = [r for r in sample_rows if r['idx'] == idx]
        w('<tr><td class="glyph"><img src="%s" width="120" height="120"><br>'
          '<b>[%d]</b> <code>0x%02X</code></td>' % (b64(gl.png(idx, 150, 150)), idx, MARKTB[idx]))
        w('<td style="font-size:12.5px">')
        for r in occ:
            w('第 <b>%s</b> 小节 · %s · %s · dx=%d dy=%d<br>'
              % (r['measure'], r['container'],
                 ('音符上（' + r['note'] + '）') if r['note'] else '小节级',
                 r['dx'], r['dy']))
        w('</td></tr>')
    w('</table>')

    w('<h2>4. 可用的 MusicXML 落点（供「MusicXML 元素」列选择）</h2>')
    w('<table><tr><th style="width:210px">类别</th><th>元素</th></tr>')
    w('<tr><td>奏法 articulation</td><td><code>&lt;articulations&gt;</code> → '
      '<code>accent</code>、<code>strong-accent</code>、<code>staccato</code>、'
      '<code>staccatissimo</code>、<code>tenuto</code>、<code>detached-legato</code>、'
      '<code>marcato</code>、<code>breath-mark</code>、<code>caesura</code>、'
      '<code>spiccato</code>、<code>scoop</code>、<code>plop</code>、<code>doit</code>、'
      '<code>falloff</code></td></tr>')
    w('<tr><td>弓法 technical</td><td><code>&lt;technical&gt;</code> → '
      '<code>up-bow</code>、<code>down-bow</code>、<code>open-string</code>、'
      '<code>harmonic</code>、<code>fingering</code></td></tr>')
    w('<tr><td>装饰音 ornaments</td><td><code>&lt;ornaments&gt;</code> → '
      '<code>trill-mark</code>、<code>mordent</code>、<code>inverted-mordent</code>、'
      '<code>turn</code>、<code>inverted-turn</code>、<code>shake</code>、'
      '<code>wavy-line</code></td></tr>')
    w('<tr><td>延长记号</td><td><code>&lt;fermata&gt;</code>（可带 <code>type="upright"</code> / '
      '<code>"inverted"</code>）</td></tr>')
    w('<tr><td>力度 dynamic</td><td><code>&lt;dynamics&gt;</code> → <code>p</code>、<code>f</code>、'
      '<code>mf</code>、… 或 <code>other-dynamics</code></td></tr>')
    w('<tr><td>其他</td><td><code>&lt;words&gt;</code>（无法归类时的兜底）、'
      '<code>&lt;segno&gt;</code>、<code>&lt;coda&gt;</code>、<code>&lt;pedal&gt;</code></td></tr>')
    w('</table>')

    w('<h2>5. 填写方式</h2>')
    w('<ol>')
    w('<li>打开 <code>work/mark-questionnaire.tsv</code>（制表符分隔，Excel/LibreOffice/文本编辑器均可）。</li>')
    w('<li>每行一个索引，填写 <code>name_zh</code>、<code>name_ko_or_ja</code>、<code>category</code>、'
      '<code>musicxml</code>、<code>placement</code>、<code>notes</code> 六列；不确定的列留 <code>?</code>。</li>')
    w('<li>第 3 节的疑问请写在对应索引的 <code>notes</code> 列。</li>')
    w('<li>填完即可；我会据此更新 <code>docs/smc-format.md</code> §6.3、'
      '<code>docs/music-fields.md</code>、<code>docs/unknown-fields.md</code> '
      '并替换 <code>ir2musicxml.py</code> 里的 <code>&lt;words&gt;smc-type-8&lt;/words&gt;</code> 占位。</li>')
    w('</ol>')

    w('<h2>附录：MarkTB 全 51 项</h2>')
    w('<p>红框/无标注者为语料中未出现的索引。'
      '若第 2 节有索引您认为画错了字形，可在此对照。</p>')
    w('<img class="atlas" src="%s" alt="MarkTB 全表">' % atlas_b64)
    w('<p style="color:#666;font-size:12px">生成自 <code>engine.dll</code> '
      '<code>0x1010059C</code> 与 <code>Font\\KAYAKUMA.TTF</code>；'
      '语料 %d 个文件、%d 条 type 0x08。</p>' % (stats['files'], stats['marks']))
    w('</body></html>')

    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html))

    header = ['idx', 'font_byte', 'count', 'files', 'container', 'dy',
              'name_zh', 'name_ko_or_ja', 'category', 'musicxml', 'placement', 'notes']
    lines = ['\t'.join(header)]
    for idx in used:
        lines.append('\t'.join([
            str(idx),
            '0x%02X' % MARKTB[idx],
            str(stats['total'][str(idx)]),
            str(stats['files_per_index'][str(idx)]),
            ';'.join('%s:%d' % (k, v) for k, v in sorted(stats['owner'][str(idx)].items())),
            ';'.join('%s:%d' % (k, v) for k, v in sorted(stats['dysign'][str(idx)].items())),
            '?', '?', '?', '?', '?', '',
        ]))
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print('wrote', OUT_HTML)
    print('wrote', OUT_TSV)
    print('wrote', OUT_JSON)
    print('indices used:', used)


main()
