# Audio: reference VO, music bed, accents

Contents: [The reference voiceover](#the-reference-voiceover-is-a-timing-instrument) · [Resolving music](#resolving-music) · [Leveling](#leveling-the-bed-by-rms-not-by-peak) · [Ducking](#duck-the-music-only) · [Programmatic music](#when-no-catalog-track-fits) · [SFX](#sound-effects) · [Cue alignment](#aligning-a-cue-to-its-action) · [Room for a cue](#room-for-a-cue-ducking-by-type) · [Beat-locked cues](#beat-locked-cues) · [Mix order](#mix-order) · [Delivery loudness](#delivery-loudness) · [When you cannot listen](#when-you-cannot-listen)

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

Arrange from the timeline's segment boundaries: act changes get an impact, with a beat of near-silence *before* it — the ear needs the gap to feel the hit. Reading-heavy segments thin out (fewer voices, melody back); fast-cut stretches tighten; the ending resolves harmonically with its tail fully decayed inside the film's length.

## Sound effects

- Small, self-made, and reused across episodes is a feature, not a shortcut.
- One accent per beat that deserves one. A video where every line has a whoosh has no accent left.
- Reserve SFX for **transitions and count-ins**; text appearing does not need a sound.
- In a muted-feed context, SFX do less work than people expect — do not let them push the music up.

**Choose by role, not by file.** A 30–120s film carries four to six accent roles, and the roles come from what the picture actually does:

| On-screen action | Accent | Pick it so that |
|---|---|---|
| A card or word settles | dry click / pop | clean onset, not bright |
| A count finishes, a numeral lands | two-tone confirm | recognizable, short tail |
| The argument changes act | whoosh | structural changes only — never per element |
| A reveal or keyword lands | low impact | stacked with the music's hit or instead of it, never both fighting |
| The closing beat | resolve / chime | tail fully decayed inside the film |

Repeated identical actions (typing beats, list items landing) alternate two takes of the same role (click / click-alt) — the same sample in rhythm exposes itself as one sample.

**Set gain by measured level, not by a default.** Bundled and procedurally generated SFX often sit near −20 dBFS; recorded library ones near 0 dBFS. The same `gain` value is a very different loudness across that range. Measure with `scripts/sfx_landmarks.py` and set each cue's gain from its measured peak — at the cue's moment, the accent's peak should not sit clearly below the ducked music's peak.

## Aligning a cue to its action

**The mistake:** dropping the file at the action's timestamp. Every file has a dead prefix, and a whoosh is *heard* at its swell, not at its sample zero — a cue placed by eye lands 30–80ms late and the whole film reads loose.

**The method:**

1. Measure each file once — `python3 <skill-dir>/scripts/sfx_landmarks.py audio/sfx/*.wav` prints onset (first transient above 30% of peak), peak time, and peak level.
2. Clicks, keys, and pops align at the **onset**. Whooshes, impacts, and swells align at the **peak** — and they must start *before* the picture, because the ear needs the swell to arrive with the cut, not after it.
3. `cue.at = action_time − syncOffset`, where `syncOffset` is whichever landmark you aligned on.
4. Tolerance: within one frame of the action at 30fps (33ms); two frames is the check limit. Beyond that it is audible.

Keep the cue list as data, not as command-line history: a small `audio/cues.json` beside the timeline — one entry per cue (`at`, `file`, `gain`, `syncOffset`, `role`). It derives from segment times, so when a copy revision moves a beat, the cues file is regenerated with it; a cue that survives in the mix after its action was cut is the audio version of a stale still.

## Room for a cue: ducking by type

The voice-keyed sidechain (above) reacts to the voice, not to accents — a confirm that lands on a bed swell gets covered exactly when it matters. Give important cues a **pre-computed dip** in the music: known times, known depth, rendered into the bed before the SFX are mixed.

| Accent role | Dip | attack / hold / release |
|---|---|---|
| Click, pop (a card settles) | 3–3.5 dB | 40ms / 100–120ms / 200–240ms |
| Typing cluster | 2.5 dB | 40ms / 350ms / 250ms |
| Act-change whoosh | 4 dB | 40ms / 160–200ms / 300–350ms |
| Count lands / confirm | 5–6 dB | 40ms / 350–450ms / 350–400ms |
| Closing beat | 5 dB | 40ms / 550ms / 450ms |

- Overlapping cues take the **deepest current dip** — never stack or multiply them.
- These are starting points, not a standard; the actual track's density decides.
- If the music audibly pumps: fewer cued dips, then shallower, then longer release — in that order. Do not raise the master to fix a covered accent.

One cue as a volume expression (a 4 dB dip, ≈ ×0.63, at 12.16s with 40ms in / 200ms hold / 350ms out), chained per cue onto the bed:

```bash
ffmpeg -i bed.wav -af "volume='if(lt(t,12.16),1, if(lt(t,12.20),1-0.37*(t-12.16)/0.04, if(lt(t,12.40),0.63, if(lt(t,12.75),0.63+0.37*(t-12.40)/0.35,1))))':eval=frame" bed-cued.wav
```

## Beat-locked cues

Measure the actual track's BPM and first beat — from the file or against its waveform — and never assume a round number. Then:

- Major segment transitions land on **downbeats** when the bed is on a grid.
- Light actions (a word settling, a card appearing) do not need to be on the grid — forcing them makes the film mechanical.
- The binding runs both directions: if the type lands on a fixed rhythmic grid, the bed sits on that same grid (see programmatic music above).

## Mix order

Build in this order, checking each stage:

1. Voice alone — is every segment intelligible at 1×?
2. Voice + bed, no SFX — is the bed under the voice by the target offset?
3. Voice + bed + duck — does the bed move without pumping?
4. Voice + bed + duck + SFX — are the accents audible and not fatiguing?
5. **The encoded MP4** — the file the viewer hears is not the WAV you auditioned: AAC encoding creates new peaks and can clip an accent's tail. Listen to the deliverable once, at the end.

Never audition a mix you have not heard in this order. Most "the music is too loud" reports are a stage-2 problem being diagnosed at stage-4.

## Delivery loudness

Level the finished mix to a target instead of shipping whatever the mix produced:

- Working target: **about −16 LUFS integrated, true peak ≤ −1.5 dBTP**. Platforms do not publish exact targets and normalize differently — the point is that episodes of a series match each other, not that −16 is magic.
- Use two-pass `loudnorm`: the first pass measures, the second carries the measured values in. Single-pass loudnorm is dynamic and pumps.

```bash
ffmpeg -i mix.wav -af loudnorm=I=-16:TP=-1.5:LRA=8:print_format=json -f null -   # pass 1: measure
ffmpeg -i mix.wav -af loudnorm=I=-16:TP=-1.5:LRA=8:measured_I=…:measured_TP=…:measured_LRA=…:measured_thresh=…:linear=true -ar 48k master.wav
```

- **Re-measure true peak after AAC encoding** — encoding creates new peaks the WAV measurement never saw.
- Check the ends: nothing slams at the head, the tail is not chopped mid-decay, music and picture are the same length.

### Loudness is a discriminator, not only a target

Integrated loudness is the cheapest available proof of **which master you actually rendered**.
The bands are far enough apart to be unambiguous:

| what went in | measured |
|---|---|
| voice master (voice + ducked bed + SFX) | −16 to −20 LUFS |
| guide master (bed + SFX only) | −23 to −25 LUFS |

A ~6 LU gap that nothing else reports. A voice master measuring −24 LUFS did not get quiet —
it is the **wrong file**, and the render is otherwise perfect. Measure every render, and
compare against the band for the cut you believe you made:

```bash
ffmpeg -hide_banner -nostats -i renders/episode.mp4 -af ebur128=peak=true -f null /dev/null \
  2>&1 | grep -E "^    I:|Peak:"
```

`scripts/verify_render.sh` wraps this: duration, resolution, frame count, and the loudness
band for the expected cut, in one command.

## When you cannot listen

If the environment cannot audition audio, say so — and check structure with evidence instead of claiming a pass:

- **Spectrogram**: impacts, pauses, swells and the ending are visible as shapes, and heavy low end (the most common synthesized-bed fault) shows immediately.
  `ffmpeg -i master.wav -lavfi showspectrumpic=s=1600x500:scale=log:fscale=log spec.png`
- **Momentary loudness over time** (`ffmpeg -i master.wav -filter_complex ebur128 -f null -`): confirms the dips and landings actually happen at the cue times.

These prove placement, not taste. "It sounds good" cannot be claimed without listening; report which of the two you did.

## Delivering before the voice exists

When the user has not recorded yet — the common case for a script-driven series — ship **two masters from one timeline**, not one master and a promise:

1. **Guide master** — bed + SFX only, no voice. This is what they lay their own recording over.
2. **Reference master** — the synthesized voice, ducked, at −15.5 dBFS against a −25.5 dB bed. This is a **pacing instrument, not a deliverable**, and it must be labelled as one in the filename and in your message.

The two differ only in which WAV the `<audio>` element points at, and **the timeline does not change between them**. That is worth telling the user out loud: they can start recording against the guide master while nothing is still being re-rendered, and a later copy revision will not move a single cue.

### Make the track a build parameter — never swap the file in place

There is no `--audio` flag on `hyperframes render`; the composition names a path. The
tempting workaround is to copy the other master over that path, render, and swap back.
**Do not.** It works until the round where you forget, and the failure is silent and total:

```
build_html.mjs:  <audio id="master" src="assets/master_bgm.wav" ...>
                                        ^^^^^^^^^^^^^ hardcoded
```

A three-and-a-half-minute render came out with the bed and no voice at all. Not a click out
of place, not a wrong level — the entire narration missing. Nothing in the render log, the
static audit, the overlap checks, or the duration check said anything, because **every one
of them is blind to which audio file was used.** The only thing that caught it was
integrated loudness measuring −24.6 LUFS where the voice master measures −17 to −19.

**Parameterise it instead**, so the choice is visible in the command that ran:

```js
const MASTER = process.argv[2] === 'bgm' ? 'master_bgm.wav' : 'master_voice.wav';
// …
`<audio id="master" src="assets/${MASTER}" …>`
```

```bash
node build_html.mjs                 # voice master (default)
node build_html.mjs bgm             # guide master
```

Print the resolved filename in the generator's own output line, so the build log names the
track it used:

```
index.html 已生成 · 总长 113.8s · 元素 95 · 动画 229 条 · 母带 master_voice.wav
```

**Rule.** *State that is a build-time choice belongs in the build, not in the filesystem.*
A path hardcoded in a template is a choice you cannot see, cannot vary, and cannot assert on.
