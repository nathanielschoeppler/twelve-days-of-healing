#!/usr/bin/env python3
"""Make a lyric score of the song for AI singers (Synthesizer V / ACE Studio): MusicXML (one syllable per note)
plus a MIDI with lyric events, on the app's exact grid (100 BPM, beat 0 = 0:00), in F major (or a shifted key).
usage: make_score.py OUT_DIR [shift]"""
import json, os, re, sys, mido
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, 'data')
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'; SHIFT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
BARS = json.load(open(os.path.join(DATA, 'bars.json'))); M = json.load(open(os.path.join(DATA, 'songdata.json')))['marks']
BEAT = 0.6
SYL = {'christmas': ['Christ', 'mas'], 'healing': ['heal', 'ing'], 'chiropractor': ['chi', 'ro', 'prac', 'tor'],
       'second': ['sec', 'ond'], 'seventh': ['sev', 'enth'], 'eleventh': ['e', 'lev', 'enth'], 'perfectly': ['per', 'fect', 'ly'],
       'aligned': ['a', 'ligned'], 'posture': ['pos', 'ture'], 'healthy': ['health', 'y'], 'nutrition': ['nu', 'tri', 'tion'],
       'seven': ['sev', 'en'], 'therapies': ['ther', 'a', 'pies'], 'restoring': ['re', 'stor', 'ing'], 'sleeping': ['sleep', 'ing'],
       'headaches': ['head', 'aches'], 'leaving': ['leav', 'ing'], 'fading': ['fad', 'ing'], 'eleven': ['e', 'lev', 'en'],
       'surgeries': ['sur', 'ger', 'ies'], 'prevented': ['pre', 'vent', 'ed'], 'wellness': ['well', 'ness']}
def syllables(text):
    """-> list of (syllable, syllabic) with syllabic in single/begin/middle/end"""
    t = text.lower().replace('fiiiiiive', 'five').replace('x-ray', 'ex ray').replace('a-fading', 'a fading')
    out = []
    for w in re.findall(r"[a-z']+", t):
        parts = SYL.get(w, [w])
        if w == 'christmas': pass
        for i, p in enumerate(parts):
            kind = 'single' if len(parts) == 1 else 'begin' if i == 0 else 'end' if i == len(parts) - 1 else 'middle'
            out.append((p.capitalize() if (w == 'christmas' and i == 0) else p, kind))
    return out
# every melody note (beat, length, pitch) of the sung days
notes = []; beat = 0
for b in BARS:
    x = beat
    for m, d in b['mel']:
        if m > 0 and b['v'] <= 12: notes.append([x, d, m + SHIFT])
        x += d
    beat += b['beats']
TOTAL = beat
# group the notes into lyric lines (same rule as the app's karaoke)
lines = []
for i, mk in enumerate(M):
    a = mk['t'] / BEAT; z = M[i + 1]['t'] / BEAT if i + 1 < len(M) else TOTAL
    ln = [n[:] for n in notes if a - 0.03 <= n[0] < z - 0.03]
    lines.append((mk, ln))
def split(ln, k):                           # split note k into two halves (same pitch)
    s, d, p = ln[k]; ln[k:k + 1] = [[s, d / 2, p], [s + d / 2, d / 2, p]]
score = []                                   # (beat, length, pitch, syllable, syllabic)
for mk, ln in lines:
    syl = syllables(mk['text'])
    if mk['line'] == 'open':                 # "On my __ Christmas of healing, my chiropractor gave to me": fitted by hand
        i = next(j for j in range(len(ln)) if ln[j][1] == 1.0 and j > 2); split(ln, i)          # "of heal-" share the quarter
        i = next(j for j in range(len(ln)) if ln[j][2] == 67 + SHIFT and j > 5); split(ln, i)   # "chi-ro" share the eighth
        split(ln, len(ln) - 1); s, d, p = ln[-2]; ln[-2][1] = 0.5; ln[-1] = [s + 0.5, d * 2 - 0.5, p]  # "to" eighth, "me" long
    while len(ln) < len(syl):                # more syllables than notes: split the longest note (not the last)
        k = max(range(len(ln) - 1), key=lambda j: (ln[j][1], -j)); split(ln, k)
    for j, (s, d, p) in enumerate(ln):
        if j < len(syl): score.append((s, d, p) + syl[j])
        else: score.append((s, d, p, '-', 'single'))       # fewer syllables: hold the last one (slur)
    if len(syl) > len(ln): print('WARNING not all syllables placed:', mk['text'])
# ---- MusicXML
STEP = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
def pitch_xml(m):
    n = STEP[m % 12]; alter = '<alter>-1</alter>' if 'b' in n else ''
    return f'<pitch><step>{n[0]}</step>{alter}<octave>{m // 12 - 1}</octave></pitch>'
DIV = 4
def dur_type(q):
    return {4: 'whole', 3: 'half', 2: 'half', 1.5: 'quarter', 1: 'quarter', 0.75: 'eighth', 0.5: 'eighth', 0.25: '16th'}.get(q, 'quarter'), q in (3, 1.5, 0.75)
meas = []; beat = 0; last_ts = None
for bi, b in enumerate(BARS):
    a, z = beat, beat + b['beats']; items = []; x = a
    for s, d, p, sy, kind in [n for n in score if a - 1e-6 <= n[0] < z - 1e-6]:
        if s > x + 1e-6: items.append(('rest', x, s - x))
        items.append(('note', s, d, p, sy, kind)); x = s + d
    if z > x + 1e-6: items.append(('rest', x, z - x))
    xml = [f'<measure number="{bi + 1}">']
    if b['beats'] != last_ts or bi == 0:
        attr = f'<time><beats>{b["beats"]}</beats><beat-type>4</beat-type></time>'
        if bi == 0: attr = f'<divisions>{DIV}</divisions><key><fifths>{-1 + {0: 0, -2: -2, 2: 2}.get(SHIFT, 0)}</fifths></key>' + attr + '<clef><sign>G</sign><line>2</line></clef>'
        xml.append(f'<attributes>{attr}</attributes>'); last_ts = b['beats']
    if bi == 0: xml.append('<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>100</per-minute></metronome></direction-type><sound tempo="100"/></direction>')
    for it in items:
        if it[0] == 'rest':
            q = it[2]; t, dot = dur_type(q)
            xml.append(f'<note><rest/><duration>{int(round(q * DIV))}</duration><type>{t}</type>{"<dot/>" if dot else ""}</note>')
        else:
            _, s, q, p, sy, kind = it; t, dot = dur_type(q)
            lyr = f'<lyric number="1"><syllabic>{kind}</syllabic><text>{sy}</text></lyric>'     # "-" = Synthesizer V's hold/slur
            xml.append(f'<note>{pitch_xml(p)}<duration>{int(round(q * DIV))}</duration><type>{t}</type>{"<dot/>" if dot else ""}{lyr}</note>')
    xml.append('</measure>'); meas.append(''.join(xml)); beat = z
doc = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n'
       '<score-partwise version="3.1"><work><work-title>The Twelve Days of Healing</work-title></work>'
       '<part-list><score-part id="P1"><part-name>Vocal</part-name></score-part></part-list><part id="P1">' + '\n'.join(meas) + '</part></score-partwise>\n')
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'Twelve Days of Healing - vocal melody with lyrics.musicxml'), 'w').write(doc)
# ---- MIDI with lyric events (backup), Synthesizer V style: "+" = next syllable of the same word, "-" = hold
mid = mido.MidiFile(ticks_per_beat=480); tr = mido.MidiTrack(); mid.tracks.append(tr)
tr.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(100))); last = 0; words = []
for s, d, p, sy, kind in score:
    lyr = '-' if sy == '-' else ('+' if kind in ('middle', 'end') else None)
    if lyr is None:                          # whole word goes on its first note
        k = score.index((s, d, p, sy, kind)); w = sy
        for s2, d2, p2, sy2, kind2 in score[k + 1:]:
            if kind2 in ('middle', 'end'): w += sy2
            else: break
        lyr = w
    on = int(round(s * 480)); tr.append(mido.MetaMessage('lyrics', text=lyr, time=on - last))
    tr.append(mido.Message('note_on', note=p, velocity=90, time=0)); tr.append(mido.Message('note_off', note=p, velocity=0, time=int(round(d * 480)) - 2)); last = on + int(round(d * 480)) - 2
mid.save(os.path.join(OUT, 'Twelve Days of Healing - vocal melody with lyrics.mid'))
print(f'{len(score)} sung notes, {sum(1 for n in score if n[3] == "-")} held, total {TOTAL} beats ({TOTAL * BEAT:.1f} s)')
# ---- notes-only MIDI + pasteable lyric text (Synthesizer V "Insert Lyrics": one token per note, in order)
mid2 = mido.MidiFile(ticks_per_beat=480); tr2 = mido.MidiTrack(); mid2.tracks.append(tr2)
tr2.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(100))); last = 0; toks = []
for t_ in tr:
    if t_.type == 'lyrics': toks.append(t_.text)
for s, d, p, sy, kind in score:
    on = int(round(s * 480)); tr2.append(mido.Message('note_on', note=p, velocity=90, time=on - last))
    off = on + int(round(d * 480)) - 2; tr2.append(mido.Message('note_off', note=p, velocity=0, time=off - on)); last = off
mid2.save(os.path.join(OUT, 'Twelve Days of Healing - melody (notes only).mid'))
# one line of text per sung line, tokens separated by spaces
lines_txt = []; k = 0
for mk, ln in lines:
    n_ = sum(1 for n in score if n[0] >= mk['t'] / BEAT - 0.03 and (mk is M[-1] or n[0] < M[M.index(mk) + 1]['t'] / BEAT - 0.03))
    lines_txt.append(' '.join(toks[k:k + n_])); k += n_
assert k == len(toks) == len(score), (k, len(toks), len(score))
open(os.path.join(OUT, 'Twelve Days of Healing - lyrics to paste.txt'), 'w').write('\n'.join(lines_txt) + '\n')
print('paste text:', len(toks), 'tokens for', len(score), 'notes')
# ---- Synthesizer V project (.svp): opens directly with every note's lyric already set
import uuid
BL = 705600000                                   # SynthV "blicks" per quarter note
gid = str(uuid.uuid4())
sv_notes = []
for (s, d, p, sy, kind), tok in zip(score, toks):
    sv_notes.append({"onset": int(round(s * BL)), "duration": int(round(d * BL)) - 1000, "lyrics": tok, "phonemes": "",
                     "pitch": p, "detune": 0, "attributes": {}})
empty = {"mode": "cubic", "points": []}
params = {k: dict(empty) for k in ("pitchDelta", "vibratoEnv", "loudness", "tension", "breathiness", "voicing", "gender", "toneShift")}
proj = {"version": 153,
        "time": {"meter": [{"index": 0, "numerator": 4, "denominator": 4}], "tempo": [{"position": 0, "bpm": 100.0}]},
        "library": [],
        "tracks": [{"name": "Vocal", "dispColor": "ff7db235", "dispOrder": 0, "renderEnabled": False,
                    "mixer": {"gainDecibel": 0.0, "pan": 0.0, "mute": False, "solo": False, "display": True},
                    "mainGroup": {"name": "main", "uuid": gid, "parameters": params, "notes": sv_notes},
                    "mainRef": {"groupID": gid, "blickOffset": 0, "pitchOffset": 0, "isInstrumental": False,
                                "database": {"name": "", "language": "english", "phoneset": ""}, "dictionary": "", "voice": {}},
                    "groups": []}],
        "renderConfig": {"destination": "", "filename": "Twelve Days of Healing - vocal", "numChannels": 1, "aspirationFormat": "noAspiration",
                         "bitDepth": 16, "sampleRate": 44100, "exportMixDown": True}}
json.dump(proj, open(os.path.join(OUT, 'Twelve Days of Healing - vocal (Synthesizer V project).svp'), 'w'))
print('svp:', len(sv_notes), 'notes, all with lyrics:', all(n['lyrics'] for n in sv_notes))

