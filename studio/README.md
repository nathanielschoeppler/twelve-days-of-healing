# Studio pipeline

Turns a take recorded in the app into a produced song: natural vocal tuning, harmonies, a full band,
mixed and mastered.

```bash
bash studio/setup.sh               # once: ffmpeg, fluidsynth + sampled instruments, Rubber Band, Python libs
python3 studio/studio.py make      # newest take in the online storage
python3 studio/studio.py make NAME # a specific take (see: python3 studio/studio.py list)
```

Output: `studio/out/<take>/`
- `<take> - studio mix.mp3` / `.wav`: the finished song (-14 LUFS, 48 kHz)
- `vocal_lead.wav`, `vocal_harmony.wav`: the tuned vocals on their own
- `QA.txt`: pitch before/after, vibrato kept, dropouts, timing, word check

How it works:
1. The app uploads her untouched voice (`__raw.wav`), already placed on the song timeline.
2. Key detection (E flat, F or G).
3. Natural tuning: each held note's centre is moved to the melody note with Rubber Band R3 and formant
   preservation. Her vibrato, slides and breaths stay as sung; nothing is resynthesized.
4. A harmony a third above, made the same way, on every "Fiiive healthy discs" and on the last line of days 9 to 12.
5. The band (`arrange.py`): piano, acoustic guitar, bass, strings, acoustic drum kit, shaker, sleigh bells and
   glockenspiel, rendered with sampled instruments and building from day 1 to day 12. It is cached per key in
   `studio/cache/`.
6. The mix: vocal EQ, de-essing, compression, plate reverb and eighth-note echo; vocal about 3 dB over the band; mastered.
