# The Twelve Days of Healing: notes for Claude

This repo is the karaoke/recording app (`index.html`, served by GitHub Pages) plus a studio pipeline
(`studio/`) that turns a singer's take into a finished, produced song.

## When Nathaniel says a new recording is uploaded (or asks to edit / mix / produce a take)

Use the studio pipeline. It is the quality bar he signed off on: natural tuning, full band, harmonies.

```bash
bash studio/setup.sh                       # once per machine (apt + pip)
python3 studio/studio.py list              # see what is in the online storage
python3 studio/studio.py make              # newest take
python3 studio/studio.py make <file name>  # a specific take
python3 studio/studio.py remix <file name> # re-mix an already processed take (keeps its tuned vocals)
```

Then send him `studio/out/<take>/<take> - studio mix.mp3` (SendUserFile) with a short summary built from
`studio/out/<take>/QA.txt`, and give him timestamps to listen to for anything QA flags.

Before running it, look at the take: which days are sung (verse-by-verse takes can be partial), whether the
words match the lyrics, and whether there is talking or noise to cut. Say what you found. If days are missing,
say so; never invent or copy material without telling him.

## Quality rules he set (do not regress)

- Tuning must sound natural, never "auto-tune": note-centre correction on her REAL recording with Rubber Band
  (`-3 -F --pitchmap`), her vibrato/slides kept. Never resynthesize the voice (WORLD/vocoders made it sound
  robotic and grainy). No chorus doubling, no exciter on the lead.
- Vocal must never cut out or fade: no aggressive gates or noise reduction (only light `afftdn`).
- The band is the sampled-instrument arrangement in `studio/arrange.py`, on the app's exact beat grid
  (100 BPM, beat 0 = 0.0 s), building from day 1 to day 12. Keep it locked to her vocal.
- Mix: vocal about 1 dB over the band (he asked for the instruments a bit louder; `VOCAL_OVER_BAND`), harmonies a third above on "Fiiive" lines and the last line of
  days 9-12, master at -14 LUFS with no clipping.
- Check before sending: pitch before/after, vibrato kept, dropouts 0, timing ~0 ms, words. Never send audio you
  have not verified (an earlier mistake: sending files with no vocals in them).
- Be honest about limits: the checks are measurements, not listening, so ask him to listen at specific times.

## The song

Lyrics (her wording): "On my <ordinal> Christmas of healing, my chiropractor gave to me", then Twelve months of
wellness / Eleven back surgeries prevented / Ten pains a-fading / Nine headaches leaving / Eight calm nights
sleeping / Seven therapies restoring / Six nutrition plans / Fiiiiiive healthy discs / Four x-ray views /
Three punch cards / Two posture tips / And one perfectly aligned spine!
The melody/timing source of truth is `tdSong()` in `index.html`; `studio/data/` holds an export of it.

## App deployment

Edit and push `index.html` to `main`; GitHub Pages serves it. Bump the "App version N" label in the menu with
each change so the singer can confirm she has the update (close and reopen the Home Screen app).
Recordings go to the public Supabase bucket `recordings` (mix + `__raw.wav` at full quality).
