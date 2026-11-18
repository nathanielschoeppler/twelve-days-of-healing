# Acoustic-pop Christmas arrangement of the Twelve Days tune on the app's exact beat grid (100 BPM, beat 0 = 0.0 s).
# Writes one MIDI file per instrument (stems) so they can be rendered with real sampled instruments and mixed.
# usage: arrange.py OUT_DIR [key shift in semitones, e.g. -2 / 0 / 2]
import json, os, sys, random, mido
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
SHIFT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
random.seed(12)
TPB = 480; BPM = 100
BARS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'bars.json')))           # [{beats, mel, ch, v, line, outro}]
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'Bb': 10, 'B': 11}
def root(ch): return NOTE[ch.rstrip('7')]
TONES = {'F': [5, 9, 0], 'C7': [0, 4, 7, 10], 'Bb': [10, 2, 5], 'G7': [7, 11, 2, 5], 'C': [0, 4, 7]}
GTR = {'F': [41, 48, 53, 57, 60, 65], 'C7': [48, 52, 58, 60, 64], 'Bb': [46, 53, 58, 62, 65], 'G7': [43, 47, 50, 55, 59, 65], 'C': [48, 52, 55, 60, 64]}
PIANO_RH = {'F': [57, 60, 65], 'C7': [58, 60, 64], 'Bb': [58, 62, 65], 'G7': [59, 62, 65], 'C': [55, 60, 64]}
STR = {'F': [53, 57, 60, 65], 'C7': [52, 55, 58, 64], 'Bb': [50, 53, 58, 62], 'G7': [50, 53, 55, 59], 'C': [52, 55, 60, 64]}

# timeline: (start beat, beats, chord, bar) for every chord
starts = []; beat = 0.0
for b in BARS:
    b['start'] = beat; t = beat
    for name, n in b['ch']: starts.append((t, n, name, b)); t += n
    beat += b['beats']
TOTAL = beat
def lvl(v):                                            # how big the arrangement is on each day (0 intro .. 1 final)
    return 0.0 if v == 0 else min(1.0, 0.15 + 0.085 * (v - 1)) if v <= 12 else 1.0

class Stem:
    def __init__(s, name, prog, ch=0, bank=0):
        s.name, s.ch, s.ev = name, ch, []
        s.prog, s.bank = prog, bank
    def note(s, beat, dur, pitch, vel, hum=0.012):
        j = random.gauss(0, hum) if hum else 0
        on = max(0.0, beat + j / 0.6); off = beat + dur
        vel = int(max(1, min(127, vel + random.gauss(0, 4))))
        if s.ch != 9 and s.name != 'kit': pitch += SHIFT
        s.ev.append((on, 1, pitch, vel)); s.ev.append((max(on + 0.02, off), 0, pitch, 0))
    def cc(s, beat, num, val): s.ev.append((beat, 2, num, int(max(0, min(127, val)))))
    def save(s):
        mid = mido.MidiFile(ticks_per_beat=TPB); tr = mido.MidiTrack(); mid.tracks.append(tr)
        tr.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(BPM)))
        if s.bank: tr.append(mido.Message('control_change', channel=s.ch, control=0, value=s.bank))
        tr.append(mido.Message('program_change', channel=s.ch, program=s.prog))
        tr.append(mido.Message('control_change', channel=s.ch, control=7, value=110))
        evs = sorted(s.ev, key=lambda e: (e[0], e[1] != 0)); last = 0
        for t, kind, a, b in evs:
            tick = int(round(t * TPB)); d = max(0, tick - last); last = max(last, tick)
            if kind == 2: tr.append(mido.Message('control_change', channel=s.ch, control=a, value=b, time=d))
            else: tr.append(mido.Message('note_on' if kind == 1 else 'note_off', channel=s.ch, note=a, velocity=b, time=d))
        tr.append(mido.MetaMessage('end_of_track', time=int(3 * TPB)))
        mid.save(os.path.join(OUT, f'{s.name}.mid'))

piano = Stem('piano', 0); gtr = Stem('guitar', 25); bass = Stem('bass', 33); strings = Stem('strings', 48)
glock = Stem('glock', 9); drums = Stem('kit', 0, ch=0); shaker = Stem('shaker', 0, ch=9); bells = Stem('bells', 0, ch=9)

for t, n, name, b in starts:
    v = b['v']; L = lvl(v); r = root(name); outro = b.get('outro')
    # ---- piano: left-hand root octave + right hand (broken chords early, block chords later)
    lo = 29 + (r - 5) % 12 if r != 5 else 29                      # F1..E2 range for the octave root
    lo = lo + 12 if lo < 33 else lo
    piano.note(t, n, lo, 62 + 18 * L); piano.note(t, n, lo + 12, 56 + 16 * L)
    rh = PIANO_RH[name]
    if v <= 4 or outro:
        k = 0; x = t
        while x < t + n - 1e-6:
            piano.note(x, 0.55, rh[[0, 1, 2, 1][k % 4]] + (12 if k % 4 == 2 else 0), 50 + 14 * L); x += 0.5; k += 1
    else:
        for x in [t + i for i in range(int(n))]:
            for p in rh: piano.note(x, 0.9, p, 44 + 18 * L + (8 if x == t else 0))
    # ---- acoustic guitar strums (from day 1, louder later): D on beats, U on the "and"
    if v >= 1 and not outro:
        shape = GTR[name]; x = t
        while x < t + n - 1e-6:
            down = abs(x - round(x)) < 1e-6; acc = 10 if down and (round(x - b['start']) % 2 == 1) else 0
            strings_ = shape if down else list(reversed(shape[-4:]))
            vel = (58 if down else 42) + 22 * L + acc
            for i, p in enumerate(strings_): gtr.note(x + i * 0.022 / 0.6 * (1 if down else 0.7), 0.5 if down else 0.45, p, vel - i * 2, hum=0.006)
            x += 0.5
    # ---- bass from day 2: root, fifth, little pickups into chord changes
    if v >= 2 and not outro:
        R = 36 + (r - 0) % 12 if (r % 12) <= 7 else 24 + r % 12 + 12
        R = 36 + r if 36 + r <= 43 else 24 + r
        bass.note(t, min(n, 1.9), R, 70 + 20 * L)
        if n >= 3: bass.note(t + 2, n - 2 - 0.1, R + 7 if R + 7 <= 50 else R - 5, 62 + 18 * L)
        if v >= 5 and n >= 2: bass.note(t + n - 0.5, 0.45, R + (2 if name in ('F', 'C') else -1), 50 + 15 * L)
    # ---- strings pad from day 4, swelling on the big lines
    if v >= 4 or outro:
        voic = STR[name]
        for p in voic: strings.note(t, n + 0.05, p, 46 + 34 * L, hum=0)
        if v >= 9 or outro: strings.note(t, n + 0.05, voic[-1] + 12, 40 + 30 * L, hum=0)
        strings.cc(t, 11, 70 + 40 * L)
    # ---- drums and percussion (builds from day 1; he asked for more percussion)
    if v >= 1 and not outro:
        x = t
        while x < t + n - 1e-6:                                    # shaker eighths (GM 70), soft on days 1-2
            on = abs(x - round(x)) < 1e-6
            shaker.note(x, 0.2, 70, ((46 if on else 34) + 20 * L) * (0.75 if v <= 2 else 1), hum=0.006); x += 0.5
    if v >= 3 and not outro:
        for i in range(int(n)):
            x = t + i; bb = round(x - b['start'])
            if v < 5:                                              # days 3-4: soft kick on the 1, cross-stick joins on day 4
                if bb == 0: drums.note(x, 0.3, 36, 64 + 30 * L)
                if v == 4 and bb % 2 == 1: drums.note(x, 0.3, 37, 56 + 30 * L)
                continue
            if bb % 2 == 0: drums.note(x, 0.3, 36, 72 + 30 * L)                             # kick on 1 and 3
            else:
                drums.note(x, 0.3, 37 if v < 9 else 38, (64 if v < 9 else 70) + 30 * L)     # cross-stick, then snare
                if v >= 9: drums.note(x, 0.2, 39, 58 + 22 * L)                             # hand claps with the snare
                drums.note(x, 0.2, 54, 54 + 22 * L)                                         # tambourine on 2 and 4
            if v >= 7 and bb == 1 and b['beats'] == 4: drums.note(x + 0.5, 0.25, 36, 56 + 24 * L)   # kick push
            drums.note(x, 0.15, 42, 38 + 18 * L)                                            # hi-hat eighths
            last_and = v >= 9 and bb == b['beats'] - 1
            drums.note(x + 0.5, 0.25 if last_and else 0.15, 46 if last_and else 42, 48 + 20 * L)  # open hat into the next bar
            if v >= 9: drums.note(x + 0.5, 0.2, 54, 40 + 18 * L)                            # tambourine eighths
    # sleigh bells (jingle bell 83) from day 3
    if v >= 3 and not outro:
        x = t
        while x < t + n - 1e-6: bells.note(x, 0.25, 83, (52 if abs(x - round(x)) < 1e-6 else 38) + 25 * L, hum=0.005); x += 0.5

for bi, b in enumerate(BARS):
    v = b['v']; s = b['start']
    nb = BARS[bi + 1] if bi + 1 < len(BARS) else None
    if 5 <= v <= 11 and nb and nb.get('line') == 'open' and nb['v'] == v + 1:                # tom fill into each new day
        for k, (tom, vel) in enumerate([(50, 70), (48, 74), (45, 78), (43, 84)]): drums.note(s + 2 + 0.25 * k, 0.25, tom, vel + 2 * (v - 5))
    if v >= 9 and b.get('line') == 'open': drums.note(s, 2, 49, 84)                         # crash on each new day
    if b.get('chime'):                                                                       # "Fiiive": bell chime + swell + crash
        for k, (m, d) in enumerate([(84, 2), (86, 0.5), (83, 1.5)]): glock.note(s + [0, 2, 2.5][k], d, m, 88)
        if v >= 5: drums.note(s, 2, 49 if v >= 7 else 51, 70 + 3 * v)
        strings.cc(s, 11, 127)
    if v == 0:                                                                               # intro: glockenspiel plays the tune
        x = s
        for m, d in b['mel']:
            if m > 0: glock.note(x, d * 0.95, m + 12, 70)
            x += d
    if v == 12 and b.get('line') == 1:                                                       # last line: glock doubles the melody an octave up
        x = s
        for m, d in b['mel']:
            if m > 0: glock.note(x, d * 0.95, m + 24, 56)
            x += d
# final chord: big hit and ring-out
end = TOTAL - 4
drums.note(end, 3, 49, 96); drums.note(end, 1, 36, 100); glock.note(end, 3, 89, 70); glock.note(end, 3, 84, 70)
for s in (piano, gtr, bass, strings, glock, drums, shaker, bells): s.save()
print('arranged %.1f beats (%.1f s)' % (TOTAL, TOTAL * 0.6))
