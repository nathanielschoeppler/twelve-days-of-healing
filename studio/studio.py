#!/usr/bin/env python3
"""The Twelve Days of Healing: studio pipeline for a singer's take.

  python3 studio/studio.py make            # newest recording in the online storage
  python3 studio/studio.py make NAME.wav   # a specific recording (name as listed in storage, or a local file)

Steps (all automatic):
  1. download the take's raw vocal (the "__raw.wav" the app uploads, already on the song timeline)
  2. find the key she sang in (F, or a tone lower/higher)
  3. natural tuning on her REAL recording: note-by-note centre correction with Rubber Band R3 + formant
     preservation, her vibrato/slides/breaths untouched (no resynthesis = no robot sound, no static)
  4. harmony a third above, made the same way, on every "Fiiive" line and the last line of days 9-12
  5. full-band backing (piano, acoustic guitar, bass, strings, acoustic drums, shaker, sleigh bells,
     glockenspiel) rendered with sampled instruments, building from day 1 to day 12 (cached per key)
  6. mix: vocal chain (EQ, de-ess, two-stage compression, plate reverb, eighth-note echo), harmonies wide,
     vocal ~1 dB over the band (VOCAL_OVER_BAND, dB), mastered to -14 LUFS with no clipping
  7. QA report: pitch accuracy, vibrato kept, tone cleanliness, timing, dropouts, word check
Outputs land in studio/out/<take>/ ; the finished song is "<take> - studio mix.mp3".
"""
import json, os, re, sys, subprocess, urllib.request, urllib.parse
import numpy as np, soundfile as sf
from scipy.ndimage import uniform_filter1d, median_filter
from scipy.signal import resample_poly, fftconvolve

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
CLOUD = 'https://lhdslrttbfrukdjhxyjx.supabase.co'
KEY = 'sb_publishable_RpXoVj4nSVHWwpVwFmIXfQ_JTx1no8c'      # public anon key (already in the app); storage is a public bucket
SF_GM = '/usr/share/sounds/sf2/MuseScore_General_Full.sf2'
SF_KIT = '/usr/share/sounds/sf2/Buskmans_Holiday_LV2.sf2'
SR = 48000
FP = 10.0; FS = FP / 1000
BEAT = 0.6                                                    # 100 BPM, beat 0 = 0.0 s

def sh(*a, **k): return subprocess.run(list(a), check=True, **k)
def song():
    D = json.load(open(os.path.join(DATA, 'songdata.json'))); notes = []; beat = 0
    for b in D['bars']:
        mb = 0
        for m, d in b['mel']:
            if m > 0: notes.append((m, (beat + mb) * BEAT, d * BEAT))
            mb += d
        beat += b['beats']
    return D['marks'], notes

# ---------------------------------------------------------------- 1. fetch
def cloud_list():
    req = urllib.request.Request(f'{CLOUD}/storage/v1/object/list/recordings', data=json.dumps({'prefix': '', 'limit': 1000}).encode(),
                                 headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req))
def fetch(name, out_dir):
    if os.path.exists(name): return name
    if name in ('', 'latest'):
        raws = sorted([o for o in cloud_list() if o['name'].endswith('__raw.wav')], key=lambda o: o['created_at'])
        if not raws: sys.exit('No recordings in storage yet.')
        name = raws[-1]['name']
    if not name.endswith('__raw.wav'): name = name.replace('.wav', '') + '__raw.wav'
    dst = os.path.join(out_dir, name)
    if not os.path.exists(dst):
        urllib.request.urlretrieve(f'{CLOUD}/storage/v1/object/public/recordings/{urllib.parse.quote(name)}', dst)
    return dst

# ---------------------------------------------------------------- 2. pitch + key
def pitch_track(x, sr):
    import pyworld as pw
    x16 = resample_poly(x, 16000, sr) if sr != 16000 else x
    f0, _ = pw.harvest(x16, 16000, f0_floor=110, f0_ceil=1000, frame_period=FP)
    return np.where(f0 > 0, 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440), np.nan)
def melody_frames(notes, n, shift=0, start=5.0):
    E = np.full(n, np.nan)
    for m, s, d in notes:
        if s >= start: E[int(s / FS):min(n, int((s + d) / FS))] = m + shift
    return E
def find_key(mid, notes):
    best = None
    for sh_ in (-2, 0, 2):
        E = melody_frames(notes, len(mid), sh_); ok = ~np.isnan(E) & ~np.isnan(mid)
        if ok.sum() < 200: continue
        d = mid[ok] - E[ok]; d -= 12 * np.round(d / 12); sc = np.mean(np.cos(d * np.pi / 6))
        if best is None or sc > best[0]: best = (sc, sh_)
    return best[1] if best else 0

# ---------------------------------------------------------------- 3+4. natural tuning + harmony
def natural_tune(raw_path, out_dir, shift, strength=1.0, retune_ms=50.0, maxfix=2.0):
    M, notes = song()
    x, sr = sf.read(raw_path, dtype='float64'); x = x.mean(1) if x.ndim > 1 else x
    mid = pitch_track(x, sr); n = len(mid)
    vo = ~np.isnan(mid); idx = np.where(vo)[0]
    runs = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1) if len(idx) else []
    slow = mid.copy()
    for r in runs: slow[r] = uniform_filter1d(median_filter(mid[r], 5), min(len(r), 15), mode='nearest')
    NF = [(m + shift, int(s / FS), int((s + d) / FS)) for m, s, d in notes if s >= 5]
    corr = np.full(n, np.nan); tuned = 0
    for r in runs:                                   # held notes -> centre toward the melody note sung around then
        k = 0
        while k < len(r):
            j = k
            while j + 1 < len(r) and abs(slow[r[j + 1]] - np.median(slow[r[k:j + 1]])) < 0.55: j += 1
            fr = r[k:j + 1]
            if len(fr) >= 6:
                med = np.median(mid[fr]); a, b = fr[0] - 25, fr[-1] + 25
                cands = [m for m, s0, s1 in NF if s1 > a and s0 < b]
                if cands:
                    tg = min((c + 12 * np.round((med - c) / 12) for c in cands), key=lambda c: abs(c - med))
                    if abs(tg - med) < maxfix: corr[fr] = strength * (tg - med); tuned += 1
            k = j + 1
    ii = np.where(~np.isnan(corr))[0]
    corr = np.interp(np.arange(n), ii, corr[ii]) if len(ii) else np.zeros(n)
    corr = uniform_filter1d(corr, max(1, int(retune_ms / FP)))
    # harmony: diatonic third above the melody (key-aware) on chosen lines
    scale = [(p + shift) % 12 for p in (5, 7, 9, 10, 0, 2, 4)]
    def third_up(m):
        pc = m % 12
        return (scale[(scale.index(pc) + 2) % 7] - pc) % 12 if pc in scale else 3
    H = np.full(n, np.nan)
    for m, s, d in notes: H[int(s / FS):min(n, int((s + d) / FS))] = third_up(m + shift)
    hi = np.where(~np.isnan(H))[0]; Hf = uniform_filter1d(median_filter(np.interp(np.arange(n), hi, H[hi]), 5), 4)
    hmask = np.zeros(n); lines = 0
    for i, mk in enumerate(M):
        nxt = M[i + 1]['t'] if i + 1 < len(M) else mk['t'] + 6
        if (mk['line'] == 5 and mk['v'] >= 5) or (mk['line'] == 1 and mk['v'] >= 9):
            hmask[int((mk['t'] - 0.25) / FS):min(n, int((nxt - 0.1) / FS))] = 1; lines += 1
    def rubberband(offsets, path):
        pm = os.path.join(out_dir, '_pitchmap.txt')
        with open(pm, 'w') as fh:
            for k in range(n): fh.write(f'{int(k * FS * sr)} {offsets[k]:.4f}\n')
        sh('rubberband', '-q', '-3', '-F', '--pitchmap', pm, raw_path, path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        y, _ = sf.read(path, dtype='float64'); y = y.mean(1) if y.ndim > 1 else y
        ex = np.abs(x[int(30 * sr):int(150 * sr)]); ey = np.abs(y[int(30 * sr):int(150 * sr) + int(0.3 * sr)])
        lat = int(np.argmax(fftconvolve(ey, ex[::-1], mode='valid')[:int(0.3 * sr)]))       # realtime-mode latency
        y = y[lat:lat + len(x)]; return np.pad(y, (0, max(0, len(x) - len(y))))
    lead = rubberband(corr, os.path.join(out_dir, '_lead_tmp.wav'))
    har = rubberband(corr + Hf * hmask, os.path.join(out_dir, '_har_tmp.wav'))
    har *= np.interp(np.arange(len(x)) / sr / FS, np.arange(n), uniform_filter1d(hmask, 6))
    g = 0.7 / (np.max(np.abs(lead)) + 1e-9)
    sf.write(os.path.join(out_dir, 'vocal_lead.wav'), (lead * g).astype(np.float32), sr)
    sf.write(os.path.join(out_dir, 'vocal_harmony.wav'), (har / (np.max(np.abs(har)) + 1e-9) * 0.7).astype(np.float32), sr)
    for f in ('_lead_tmp.wav', '_har_tmp.wav', '_pitchmap.txt'): os.remove(os.path.join(out_dir, f))
    print(f'  tuned {tuned} held notes (natural mode), harmony on {lines} lines')

# ---------------------------------------------------------------- 5. backing (cached per key)
def plate_ir(path):
    if os.path.exists(path): return
    n = int(SR * 1.9); t = np.arange(n) / SR
    def tail(seed):
        r = np.random.default_rng(seed).standard_normal(n); lo = np.convolve(r, np.ones(24) / 24, 'same')
        return (r * np.exp(-t / 0.35) * 0.35 + lo) * np.exp(-t * 3.0 / 1.9)
    ir = np.stack([tail(1), tail(2)], 1); ir[:int(0.03 * SR)] = 0; ir /= np.sqrt((ir ** 2).sum() / 2) * 3.2
    sf.write(path, ir.astype(np.float32), SR)
def backing(shift):
    path = os.path.join(HERE, 'cache', f'backing_{shift:+d}.wav')
    if os.path.exists(path): return path
    os.makedirs(os.path.dirname(path), exist_ok=True); wd = os.path.join(HERE, 'cache', f'stems_{shift:+d}'); os.makedirs(wd, exist_ok=True)
    sh(sys.executable, os.path.join(HERE, 'arrange.py'), wd, str(shift))
    for s in ('piano', 'guitar', 'bass', 'strings', 'glock', 'bells', 'shaker'):
        sh('fluidsynth', '-ni', '-q', '-R', '0', '-C', '0', '-g', '0.6', '-r', str(SR), '-F', f'{wd}/{s}.wav', SF_GM, f'{wd}/{s}.mid', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sh('fluidsynth', '-ni', '-q', '-R', '0', '-C', '0', '-g', '0.6', '-r', str(SR), '-F', f'{wd}/kit.wav', SF_KIT, f'{wd}/kit.mid', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ir = os.path.join(HERE, 'cache', 'plate.wav'); plate_ir(ir)
    B = json.load(open(os.path.join(DATA, 'bars.json'))); st = {}; beat = 0
    for b in B:                                                  # each day's section = its opening bar
        if b.get('line') == 'open' and b['v'] not in st: st[b['v']] = beat * BEAT
        beat += b['beats']
    GAIN = {1: -7, 2: -6, 3: -4.5, 4: -3.5, 5: -2.5, 6: -2, 7: -1.5, 8: -1, 9: -0.5, 10: 0, 11: 0, 12: 0}
    expr = '0'
    for d in range(12, 0, -1): expr = f"if(gte(t,{st[d] - 0.6:.2f}),{10 ** (GAIN[d] / 20):.3f},{expr})"
    expr = expr.replace(',0)', ',0.45)', 1)
    S = [('piano', -1.5, 'highpass=f=70,equalizer=f=180:t=q:w=1:g=-4,equalizer=f=350:t=q:w=1:g=-3,equalizer=f=3000:t=q:w=1:g=2.5,highshelf=f=8000:g=2', 0.22, 0.22),
         ('guitar', 1.0, 'highpass=f=110,equalizer=f=200:t=q:w=1:g=-5,equalizer=f=4000:t=q:w=1:g=3.5,highshelf=f=9000:g=2.5,acompressor=threshold=0.2:ratio=3:attack=5:release=80:makeup=1.3', -0.4, 0.15),
         ('bass', -1.0, 'highpass=f=35,lowpass=f=3500,equalizer=f=800:t=q:w=1:g=1.5,acompressor=threshold=0.15:ratio=4:attack=10:release=120:makeup=1.6', 0.0, 0.0),
         ('strings', -3.0, 'highpass=f=150,equalizer=f=300:t=q:w=1:g=-4,highshelf=f=7000:g=1.5', 0.0, 0.45),
         ('glock', -2.0, 'highpass=f=400', 0.25, 0.5),
         ('bells', -5.0, 'highpass=f=2000', -0.55, 0.3),
         ('shaker', -5.5, 'highpass=f=1500', 0.5, 0.15),
         ('kit', 0.0, 'highpass=f=40,equalizer=f=350:t=q:w=1:g=-4,equalizer=f=4500:t=q:w=1:g=3,highshelf=f=10000:g=2,acompressor=threshold=0.25:ratio=3:attack=8:release=100:makeup=1.4', 0.0, 0.14)]
    ins, fc, dry, snd = [], [], [], []
    for i, (nm, gain, chain, pan, sendv) in enumerate(S):
        ins += ['-i', f'{wd}/{nm}.wav']; l, r = min(1, 1 - pan), min(1, 1 + pan)
        fc.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,{chain},volume={gain}dB,pan=stereo|c0={l:.2f}*c0|c1={r:.2f}*c1,asplit=2[d{i}][s{i}];[s{i}]volume={sendv}[w{i}]")
        dry.append(f'[d{i}]'); snd.append(f'[w{i}]')
    k = len(S); ins += ['-i', ir]
    fc.append(f"{''.join(snd)}amix=inputs={k}:normalize=0,highpass=f=200,lowpass=f=9000[rin];[rin][{k}:a]afir=dry=0:wet=1[rv]")
    fc.append("[d1]asplit=2[gA][gB];[gB]adelay=17|0,pan=stereo|c0=0.0*c0|c1=0.7*c0,volume=-2dB[gD]"); dry[1] = '[gA]'
    fc.append(f"{''.join(dry)}[gD][rv]amix=inputs={k + 2}:normalize=0,volume='{expr}':eval=frame,highpass=f=28,"
              "acompressor=threshold=0.3:ratio=2:attack=30:release=250:makeup=1.1,highshelf=f=12000:g=1.5,alimiter=limit=0.95:level=false[o]")
    sh('ffmpeg', '-loglevel', 'error', '-y', *ins, '-filter_complex', ';'.join(fc), '-map', '[o]', '-t', '277.2', '-c:a', 'pcm_s24le', path)
    return path

# ---------------------------------------------------------------- 6. mix + master
# He heard her voice "overlapping" with the harmony copy and the eighth-note echo: both are off unless asked for.
HARMONY = float(os.environ.get('HARMONY', '0'))     # 1 = harmony a third above on "Fiiive" lines + last lines of days 9-12
ECHO = float(os.environ.get('ECHO', '0'))           # 0.3 = the old eighth-note echo level
def vocal_graph(gb, gv=1.0, gh=1.0):
    return (f"[3:a]asplit=2[ir1][ir2];"
            f"[0:a]aresample={SR}:resampler=soxr,afftdn=nr=10:nf=-52:tn=1,highpass=f=100,equalizer=f=280:t=q:w=1.2:g=-3,equalizer=f=480:t=q:w=1:g=-2.5,"
            f"equalizer=f=3200:t=q:w=1.1:g=2.5,highshelf=f=9500:g=3,deesser=i=0.4,acompressor=threshold=0.25:ratio=4:attack=3:release=60:makeup=1.4,"
            f"acompressor=threshold=0.1:ratio=2:attack=25:release=250:makeup=1.6,volume={1.65 * gv},asplit=3[dry][rvs][dls];"
            f"[rvs]highpass=f=250,lowpass=f=9000,aformat=channel_layouts=stereo[rvin];[rvin][ir1]afir=dry=0:wet=1,volume=0.36[rv];"
            f"[dls]highpass=f=400,lowpass=f=5000,aecho=0.8:0.9:300|600:0.28|0.12,volume=0.5,aformat=channel_layouts=stereo[dl];"
            f"[dry]aformat=channel_layouts=stereo[dry2];[dry2][rv][dl]amix=inputs=3:weights='1 1 {ECHO}':normalize=0[voc];"
            f"[1:a]aresample={SR}:resampler=soxr,afftdn=nr=10:nf=-52:tn=1,highpass=f=220,equalizer=f=3000:t=q:w=1:g=1.5,highshelf=f=9000:g=2,deesser=i=0.5,"
            f"acompressor=threshold=0.15:ratio=4:attack=5:release=100:makeup=1.5,volume={0.42 * gh * HARMONY},asplit=3[ha][hb][hr];"
            f"[ha]adelay=9[hal];[hb]adelay=21,equalizer=f=1800:t=q:w=2:g=-1.5[hbr];[hal][hbr]join=inputs=2:channel_layout=stereo[hst];"
            f"[hr]aformat=channel_layouts=stereo,highpass=f=300[hrin];[hrin][ir2]afir=dry=0:wet=1,volume=0.5[hrv];[hst][hrv]amix=inputs=2:normalize=0[har];"
            f"[2:a]aresample={SR},lowshelf=f=100:g=4,equalizer=f=500:t=q:w=1:g=-2,equalizer=f=3000:t=q:w=1.2:g=-2.5,equalizer=f=1200:t=q:w=1:g=-1,volume={gb}[bk];"
            f"[voc][har][bk]amix=inputs=3:normalize=0,acompressor=threshold=0.35:ratio=1.8:attack=30:release=300:makeup=1.0,highshelf=f=12000:g=2.5,afade=t=in:d=0.3[o]")
def mix(out_dir, bk, title):
    lead, har, ir = os.path.join(out_dir, 'vocal_lead.wav'), os.path.join(out_dir, 'vocal_harmony.wav'), os.path.join(HERE, 'cache', 'plate.wav')
    plate_ir(ir)
    def render(path, gb, gv=1.0, gh=1.0):
        sh('ffmpeg', '-loglevel', 'error', '-y', '-i', lead, '-i', har, '-i', bk, '-i', ir, '-filter_complex', vocal_graph(gb, gv, gh), '-map', '[o]', '-t', '277.8', '-c:a', 'pcm_f32le', path)
    def rms(p, a, b):
        x, sr = sf.read(p, dtype='float32'); x = x.mean(1); s = x[int(a * sr):int(b * sr)]; return 20 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-12)
    tv, tb, pre = (os.path.join(out_dir, f) for f in ('_v.wav', '_b.wav', '_pre.wav'))
    render(tv, 0.0, 1, 0); render(tb, 1.0, 0, 0)
    # balance on the days she actually sang: vocal this many dB over the band (Nathaniel asked for the band a bit louder: 3 -> 1)
    x, sr = sf.read(tv, dtype='float32'); x = x.mean(1); h = int(sr * 0.5); e = np.sqrt((x[:len(x) // h * h].reshape(-1, h) ** 2).mean(1))
    live = np.where(e > np.max(e) * 0.05)[0]; a, b = (live[0] * 0.5, live[-1] * 0.5 + 0.5) if len(live) else (6, 272)
    gb = 10 ** ((rms(tv, a, b) - float(os.environ.get('VOCAL_OVER_BAND', '1.0')) - rms(tb, a, b)) / 20)
    render(pre, gb)
    m = subprocess.run(['ffmpeg', '-hide_banner', '-i', pre, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    g = -14.0 - float(re.findall(r'I:\s+(-?[\d.]+) LUFS', m)[-1])
    wav = os.path.join(out_dir, f'{title} - studio mix.wav'); mp3 = wav[:-4] + '.mp3'
    sh('ffmpeg', '-loglevel', 'error', '-y', '-i', pre, '-af', f'volume={g:.2f}dB,alimiter=limit=0.89:attack=1:release=60:level=false', '-c:a', 'pcm_s24le', wav)
    sh('ffmpeg', '-loglevel', 'error', '-y', '-i', wav, '-b:a', '320k', '-ar', str(SR), mp3)
    for f in (tv, tb, pre): os.remove(f)
    return wav, mp3

# ---------------------------------------------------------------- 7. QA
def qa(raw, lead, mixwav, shift, words=True):
    M, notes = song(); rep = []
    def stats(p):
        x, sr = sf.read(p, dtype='float64'); x = x.mean(1) if x.ndim > 1 else x
        mid = pitch_track(x, sr); E = melody_frames(notes, len(mid), shift)
        # shrink each note a little so note changes don't count as "off"
        ok = ~np.isnan(E) & ~np.isnan(mid); d = mid[ok] - E[ok]; d -= 12 * np.round(d / 12)
        sl = uniform_filter1d(np.nan_to_num(mid), 15); fast = (mid - sl)[ok & (np.abs(np.nan_to_num(mid - sl)) < 1)]
        return np.mean(np.abs(d) < .5) * 100, np.std(fast) * 100, x, sr
    p0, v0, xr, sr = stats(raw); p1, v1, xl, _ = stats(lead)
    rep.append(f'notes within a quarter-tone: {p0:.0f}% raw -> {p1:.0f}% tuned (her vibrato {v0:.0f} -> {v1:.0f} cents; should stay about the same)')
    from scipy.signal import butter, sosfiltfilt
    from scipy.ndimage import maximum_filter1d
    lp = butter(6, 3500, 'low', fs=sr, output='sos')
    def env(x, a, b):                                   # 50 ms levels below 3.5 kHz, relative to the loud singing
        s = sosfiltfilt(lp, x[int(a * sr):int(b * sr)]); n = int(sr * .05); s = s[:len(s) // n * n].reshape(-1, n)
        e = 20 * np.log10(np.sqrt((s ** 2).mean(1)) + 1e-9); return e - np.percentile(e, 90)
    er, el = env(xr, 6, 272), env(xl, 6, 272); emin = -maximum_filter1d(-er, 5)     # quietest nearby raw level (timing-tolerant)
    drops = int(np.sum((emin > -12) & (el - emin < -8))); rep.append(f'dropouts while singing: {drops}')
    a, b = int(30 * sr), int(150 * sr); c = fftconvolve(np.abs(xl[a:b + 4800]), np.abs(xr[a:b])[::-1], mode='valid'); rep.append(f'timing vs her original: {np.argmax(c) / sr * 1000:.0f} ms')
    y, ysr = sf.read(mixwav, dtype='float32'); rep.append(f'mix: clipped samples {int(np.sum(np.abs(y) > 0.999))}')
    if words:
        try:
            from faster_whisper import WhisperModel
            wm = WhisperModel('small.en', device='cpu', compute_type='int8'); mm = y.mean(1)
            for v in (1, 5, 12):
                ms = [k for k in M if k['v'] == v]; nx = [k for k in M if k['v'] == v + 1]; a = ms[0]['t'] - 0.6; b = nx[0]['t'] - 0.1 if nx else 272
                s = mm[int(a * ysr):int(b * ysr)]
                if np.sqrt(np.mean(s ** 2)) < 1e-3: continue
                s16 = np.interp(np.arange(0, len(s), ysr / 16000), np.arange(len(s)), s).astype(np.float32)
                rep.append(f'day {v} heard as: ' + ' '.join(t.text.strip() for t in wm.transcribe(s16, beam_size=5, condition_on_previous_text=False)[0]))
        except Exception as e: rep.append(f'(word check skipped: {e})')
    return rep

def make(name=''):
    tmp = os.path.join(HERE, 'out', '_dl'); os.makedirs(tmp, exist_ok=True)
    print('1. fetching the take'); raw = fetch(name, tmp)
    title = os.path.basename(raw).replace('__raw.wav', '').replace('.wav', '')
    out = os.path.join(HERE, 'out', title); os.makedirs(out, exist_ok=True)
    x, sr = sf.read(raw, dtype='float64'); x = x.mean(1) if x.ndim > 1 else x
    print(f'   {title}: {len(x) / sr:.0f} s at {sr} Hz')
    _, notes = song(); shift = find_key(pitch_track(x, sr), notes)
    print(f"2. key: {({-2: 'E flat', 0: 'F', 2: 'G'})[shift]} major")
    print('3-4. natural tuning + harmony'); natural_tune(raw, out, shift)
    print('5. band'); bk = backing(shift)
    print('6. mix + master'); wav, mp3 = mix(out, bk, title)
    print('7. QA'); rep = qa(raw, os.path.join(out, 'vocal_lead.wav'), wav, shift)
    open(os.path.join(out, 'QA.txt'), 'w').write('\n'.join(rep) + '\n')
    for r in rep: print('   ' + r)
    print('DONE:', mp3)

if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'make': make(sys.argv[2] if len(sys.argv) > 2 else '')
    elif len(sys.argv) >= 3 and sys.argv[1] == 'remix':            # re-mix a take already processed (keeps its tuned vocals)
        title = sys.argv[2].replace('__raw.wav', '').replace('.wav', ''); out = os.path.join(HERE, 'out', title)
        raw = os.path.join(HERE, 'out', '_dl', title + '__raw.wav'); x, sr = sf.read(raw, dtype='float64'); x = x.mean(1) if x.ndim > 1 else x
        _, notes = song(); shift = find_key(pitch_track(x, sr), notes)
        wav, mp3 = mix(out, backing(shift), title); rep = qa(raw, os.path.join(out, 'vocal_lead.wav'), wav, shift, words=False)
        open(os.path.join(out, 'QA.txt'), 'w').write('\n'.join(rep) + '\n'); print('\n'.join(rep)); print('DONE:', mp3)
    elif len(sys.argv) >= 2 and sys.argv[1] == 'list':
        for o in sorted(cloud_list(), key=lambda o: o['created_at']): print(o['created_at'][:16], o['name'])
    else: print(__doc__)
