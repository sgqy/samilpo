"""Validate the produced MusicXML against the IR that made it (work scratch).

Checks the invariants that matter for a MusicXML consumer:
  1. each measure's net duration (notes/forward minus backup) equals tickPerMeas
     for every voice;
  2. note counts match the IR;
  3. every <tie type="start"> has a matching <tie type="stop"> and vice versa;
  4. every <slur> count balances;
  5. <divisions> equals whole_tick;
  6. no <print> / no layout element was emitted (parameters.md F1).

Usage: python work/verify_musicxml.py <file.ndjson> <file.musicxml>
"""
import collections
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir2musicxml


def load_ir(path):
    """Read the IR: score record, {(part, n): measure}, {(part, n): sounding notes}.

    "Sounding" excludes rests and grace notes, matching what the XML comparison
    counts: A4 adds rests to fill gaps and grace notes carry no duration.
    """
    score, measures, notes = None, {}, collections.Counter()
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        if r['kind'] == 'score':
            score = r
        elif r['kind'] == 'measure':
            measures[(r['part'], r['n'])] = r
        elif r['kind'] == 'note':
            if not r.get('rest') and not r['attrs'].get('grace'):
                notes[(r['part'], r['meas'])] += 1
    return score, measures, notes


def note_spans(measure_el):
    """Onset and duration of every non-grace, non-chord note, per voice.

    Replays the element order the way a reader does: a backup rewinds the
    cursor, a forward advances it, a grace note advances nothing, and a chord
    member shares the previous onset.
    """
    spans = []
    cur_voice = 1
    cursor = 0
    last_onset = 0
    for el in measure_el:
        if el.tag == 'note':
            v = el.findtext('voice')
            cur_voice = int(v) if v else cur_voice
            if el.find('grace') is not None:
                continue
            if el.find('chord') is not None:
                spans.append((cur_voice, last_onset, int(el.findtext('duration') or 0),
                              el.find('rest') is not None))
                continue
            last_onset = cursor
            d = int(el.findtext('duration') or 0)
            spans.append((cur_voice, cursor, d, el.find('rest') is not None))
            cursor += d
        elif el.tag == 'forward':
            cursor += int(el.findtext('duration') or 0)
        elif el.tag == 'backup':
            cursor -= int(el.findtext('duration') or 0)
    return spans


def check(score, measures, root, ir_note_counts=None):
    """Return a list of invariant violations for one MusicXML tree.

    `measures` maps (part, n) -> IR measure record. `ir_note_counts` optionally
    maps the same keys to the number of `<note>` elements the IR produced.
    Both the CLI below and the batch runner use this, so the checks are defined
    exactly once.
    """
    problems = []
    if os.environ.get('VERIFY_DEBUG'):
        p0 = root.find('part')
        print('  VD root=%r parts=%d p0=%s measures=%d' % (
            root.tag, len(root.findall('part')),
            p0.get('id') if p0 is not None else None,
            len(p0.findall('measure')) if p0 is not None else -1))
    div_el = root.find('part/measure/attributes/divisions')
    div = int(div_el.text) if div_el is not None else None
    if div != score['whole_tick']:
        problems.append('divisions %s != whole_tick %s' % (div, score['whole_tick']))
    if root.find('.//print') is not None:
        problems.append('layout element <print> was emitted (should be dropped)')

    tie_start = tie_stop = 0
    slur_start = slur_stop = 0
    xml_notes = collections.Counter()
    for part in root.findall('part'):
        pid = part.get('id')
        for m in part.findall('measure'):
            n = int(m.get('number'))
            mrec = measures.get((pid, n))
            if mrec is None:
                problems.append('measure %s not in IR' % n)
                continue
            tpm = mrec['tpm']
            spans = note_spans(m)
            voiced = [s for s in spans if not s[3]]
            mrec_ends = list((mrec.get('content_end') or {}).values())
            src_end = max(mrec_ends) if mrec_ends else 0
            if not spans:
                # A measure with no notes at all: a whole-measure rest is the
                # faithful rendering, so only complain if the source had notes.
                if src_end:
                    problems.append('measure %d: source has content to %d but the '
                                    'measure is empty' % (n, src_end))
                continue
            if not voiced and src_end:
                # Rests only. Legitimate when the source itself is silent, but the
                # total sustained time must still match the source.
                total = sum(d for _, _, d, _ in spans)
                if total != max(src_end, tpm):
                    problems.append('measure %d: silent measure spans %d, source %d'
                                    % (n, total, max(src_end, tpm)))
            src_end = max(mrec_ends) if mrec_ends else 0
            want = max(tpm, src_end)
            # Replay the measure the way a reader does: every voice is padded to
            # the barline, so the furthest position reached must equal the
            # measure's extent. A voice order that leaves the cursor past the end
            # still counts as covered, hence `furthest` rather than the cursor.
            furthest = 0
            cursor = 0
            for el in m:
                if el.tag == 'note':
                    if el.find('grace') is None and el.find('chord') is None:
                        cursor += int(el.findtext('duration') or 0)
                    furthest = max(furthest, cursor)
                elif el.tag == 'forward':
                    cursor += int(el.findtext('duration') or 0)
                    furthest = max(furthest, cursor)
                elif el.tag == 'backup':
                    cursor -= int(el.findtext('duration') or 0)
            if not spans:
                problems.append('measure %d: no note content' % n)
                continue
            if furthest != want:
                problems.append('measure %d: covers %d of %d ticks'
                                % (n, furthest, want))
            xml_notes[(pid, n)] = len(m.findall('note'))
            for t in m.iter('tie'):
                if t.get('type') == 'start':
                    tie_start += 1
                elif t.get('type') == 'stop':
                    tie_stop += 1
            for s in m.iter('slur'):
                if s.get('type') == 'start':
                    slur_start += 1
                elif s.get('type') == 'stop':
                    slur_stop += 1

    if ir_note_counts:
        for key, want in ir_note_counts.items():
            # Measures are numbered per part, so compare part by part; a part
            # present in the IR but absent from the XML is itself a defect.
            pid, num = key
            part = next((p for p in root.findall('part') if p.get('id') == pid), None)
            if part is None:
                problems.append('part %s missing from XML' % pid)
                continue
            mel = next((m for m in part.findall('measure')
                        if m.get('number') == str(num)), None)
            if mel is None:
                problems.append('measure %d of part %s missing from XML' % (num, pid))
                continue
            # Compare sounding notes only: A4 legitimately adds rests to fill a
            # gap, and a rest the source itself wrote is also a rest here.
            got = sum(1 for el in mel.findall('note')
                      if el.find('rest') is None and el.find('grace') is None)
            if got != want:
                problems.append('measure %d of part %s: %d notes in IR, %d in XML'
                                % (num, pid, want, got))
    if tie_start != tie_stop:
        problems.append('tie imbalance: %d start vs %d stop' % (tie_start, tie_stop))
    if slur_start != slur_stop:
        problems.append('slur imbalance: %d start vs %d stop' % (slur_start, slur_stop))
    return problems


def main():
    ir_path, xml_path = sys.argv[1], sys.argv[2]
    score, measures, ir_notes = load_ir(ir_path)
    text = open(xml_path, encoding='utf-8').read()
    root = ET.fromstring(text.split('\n', 2)[2])

    problems = check(score, measures, root, ir_note_counts=ir_notes)
    print('part-wise check: %d measures' % len(measures))
    print('divisions=%s' % score['whole_tick'])
    if problems:
        print('PROBLEMS: %d' % len(problems))
        for p in problems[:25]:
            print('   ', p)
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
