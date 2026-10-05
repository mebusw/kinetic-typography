# Audio: reference VO, music bed, accents

Contents: [The reference voiceover](#the-reference-voiceover-is-a-timing-instrument) · [Resolving music](#resolving-music) · [Leveling](#leveling-the-bed-by-rms-not-by-peak) · [Ducking](#duck-the-music-only) · [Programmatic music](#when-no-catalog-track-fits) · [SFX](#sound-effects) · [Mix order](#mix-order)

## The reference voiceover is a timing instrument

In this workflow the synthesized voice is not a deliverable — it is a **stopwatch**. It exists so the timeline can be measured instead of estimated, and so the person recording later has a sheet of times to hit.

- Synthesize **per segment**, not as one block. Per-segment files are measurable and re-timable; a single file means re-recording everything when one sentence changes.
- Measure with `scripts/measure_segments.py`. Lay out the gaps explicitly rather than hoping the concatenation breathes.
- If a generation provider is unavailable, say so and fall back — the layout does not depend on the audio existing, only on the durations, and a locally generated placeholder tone of known length is enough to proceed. Do not stall the whole build on a provider outage.
- When the deck's own duration estimate and the measured total disagree by more than ~10%, report both before building. That gap is a content decision, not a technical one.

The person recording later should be handed `打点表.md` (generated at stage 5) rather than asked to match the finished film by ear.

## Resolving music

Use `/media-use` to resolve rather than hunting for files:

```bash
npx hyperframes media-use resolve --type bgm --intent "<mood, tempo feel, instrumentation, energy curve>" --project <episode-dir>
```

Describe the *shape* of the track, not a genre label. What matters for a text-led video is that it does not have a recognisable melody in the register the voice is speaking in, and that its energy can sit under a voice for two minutes without becoming irritating. Check `--candidates` before pulling something new; a bed you reuse across episodes is a legitimate choice when the series has a sound.

Programmatic generation services are sometimes closed to new accounts (HTTP 410 is the signature). Verify availability once, then move on rather than debugging a dead endpoint.

## Leveling the bed by RMS, not by peak

**The mistake:** peak-normalizing the music, then judging by ear. Peak normalization says nothing about loudness — a track normalized to −1 dBFS can measure *louder* than the voice by RMS, and "it looks right on the meter" is not the same as "it sits under the voice".

**The method:**

1. Measure the voice's overall RMS.
2. Target the bed at `voice_RMS + offset`, with `offset` around **−20 to −25 dB**.
3. Apply exactly that gain, with a short fade-in and a fade-out.
4. Listen once at 1× — a bed that is technically 22 dB down can still be fatiguing if its spectrum is mid-heavy.

```bash
python3 <skill-dir>/scripts/level_audio.py --voice audio/vo/full.wav --music audio/bgm.wav \
  --out audio/bed.wav --offset -22 --duck
```

The script prints the measured RMS of each input and the gain it applied. Read those numbers — a 3 dB error here is audible, and the printed values are how you catch it without a full render.

## Duck the music only

Sidechain compression keyed to the voice should touch the **music bus only**. Running sound effects through the same compressor ducks the accents along with the bed, and the click/whoosh that gives a text video its snap disappears exactly when it is needed.

- Key: the voice track.
- Affected: the music.
- Unaffected: SFX, and any intentional music-only swell.

Typical settings: threshold just above the voice's quiet floor, ratio 4–8, fast attack (~5ms), slow release (~250–400ms). Release slower than you think — a fast release makes the bed pump audibly between words.

## When no catalog track fits

A short numpy/FM synthesis is enough for a plain pad, and it is fully license-clean. Keep the parameters as data so the next episode reuses the script with a different tempo, key, and section structure: BPM, chord progression, a sawtooth/triangle pad voice, a soft filtered-noise texture, and a section map (intro / build / peak / outro) matched to the timeline's segment boundaries.

Match the BPM to the cut, not to your taste. If the text lands on a fixed rhythmic grid, the bed should sit on that same grid — an off-grid bed under on-grid type feels subtly wrong and nobody can say why.

## Sound effects

- Small, self-made, and reused across episodes is a feature, not a shortcut.
- One accent per beat that deserves one. A video where every line has a whoosh has no accent left.
- Reserve SFX for **transitions and count-ins**; text appearing does not need a sound.
- In a muted-feed context, SFX do less work than people expect — do not let them push the music up.

## Mix order

Build in this order, checking each stage:

1. Voice alone — is every segment intelligible at 1×?
2. Voice + bed, no SFX — is the bed under the voice by the target offset?
3. Voice + bed + duck — does the bed move without pumping?
4. Voice + bed + duck + SFX — are the accents audible and not fatiguing?

Never audition a mix you have not heard in this order. Most "the music is too loud" reports are a stage-2 problem being diagnosed at stage-4.

## Delivering before the voice exists

When the user has not recorded yet — the common case for a script-driven series — ship **two masters from one timeline**, not one master and a promise:

1. **Guide master** — bed + SFX only, no voice. This is what they lay their own recording over.
2. **Reference master** — the synthesized voice, ducked, at −15.5 dBFS against a −25.5 dB bed. This is a **pacing instrument, not a deliverable**, and it must be labelled as one in the filename and in your message.

The two differ only in which WAV the `<audio>` element points at, and **the timeline does not change between them**. That is worth telling the user out loud: they can start recording against the guide master while nothing is still being re-rendered, and a later copy revision will not move a single cue.

Mechanically, there is no `--audio` flag on `hyperframes render`. The composition references a fixed path (e.g. `assets/bed.wav`); to produce the second master, swap that file in place, render, and swap it back. Keep the two masters under distinct filenames — overwriting one with the other is how a guide track gets published by accident.
