# Motion and layout for vertical kinetic typography

Contents: [Frame and safe zone](#frame-and-safe-zone) · [Type](#type) · [The face-cam slot](#the-face-cam-slot) · [Motion vocabulary](#motion-vocabulary) · [Rhythm](#rhythm) · [Emphasis](#emphasis-what-to-actually-animate) · [Making claims visible](#making-abstract-claims-visible) · [Footage](#footage) · [A persistent element can do the viewer's thinking](#a-persistent-element-can-do-the-viewers-thinking)

## Frame and type

**Canvas.** 1080×1920 (or 900×1600 for a lighter project), 30fps. `meta.width`/`meta.height` in `timeline.json` carry this; the generator reads them rather than hardcoding.

**Safe zone.** Not the frame — the part of the frame that survives platform UI.

| Band | Insets from |
|---|---|
| Top | 120px — status bar, platform chrome, and the title/handle overlay |
| Bottom | 300px — caption block, action row, and the progress bar |
| Left / right | 80px |

`meta.safe` in the timeline is the single declaration; the validator fails on any card outside it. Get the user's actual platform's insets if they named one — Douyin, Xiaohongshu, and Reels reserve different amounts, and the difference is visible in the finished post.

**Type scale** (at 1080 wide). These are floors, not targets.

| Role | Size | Weight | Notes |
|---|---|---|---|
| Segment hook | 84–120px | 700–800 | The one line that has to stop the scroll |
| Claim / headline | 56–72px | 600–700 | The argument of this segment |
| Body | 34–44px | 400–500 | Never below 28px |
| Beat number | 96–140px | 800 | Numerals read as KPI — see the caveat below |
| Label / caption | 28–32px | 500 | Must clear 4.5:1 contrast |

**Font.** Declare with `@font-face` and `src: local(...)` so the render machine resolves the same face the design machine shows. Noto Sans SC / Source Han Sans for Chinese; a clean grotesque for Latin and numerals. Pair one display face with one text face, and set numerals with `font-variant-numeric: tabular-nums` so figures do not jitter between beats.

**Numerals are read as real business data.** In a vertical feed a large figure looks like a KPI from the company being discussed. If a number is a step name or an illustrative count, keep it visually subordinate to the sentence it belongs to. When deleting content, distinguish **data** (delete it — it will be believed) from **words bound to the voiceover** (keep it — deleting it desynchronizes picture and speech). "改数字" as a step name stays; a stray "4.8%" does not.

## The face-cam slot

Many of these videos are recorded later, by the person, as a square or landscape clip. Design for it now:

- Short side ≈ **¼ of the frame's short side** (270px at 1080 wide).
- Anchored **bottom-left or bottom-right**, inside the safe zone's left/right inset and sitting above the bottom reserved band.
- Rounded corners, a subtle border or shadow so it reads as a layer above the text.
- **No footage yet? Leave the slot empty.** Do not shrink the type to fill it, do not center the composition to avoid it, do not insert a placeholder image. The composition is built around the slot from the first frame so that dropping the recording in later is a paste, not a re-layout.
- If the user has footage, match its aspect before sizing it, and re-check the frames — a slot that was designed empty often turns out to overlap a headline that was previously free to be large.

## Motion vocabulary

Search the registry before hand-authoring (`npx hyperframes catalog --query "<the move, in plain English>"`, `/hyperframes-registry`). Author by hand only when nothing fits.

| Move | Use for |
|---|---|
| Line-by-line reveal | Enumerating a list; one line lands per beat, not all at once |
| Word-scale stagger | The default for body text — each word rises and settles |
| Character scramble / decode | A term being defined or rejected |
| Count-up numeral | A quantity the argument is building toward |
| Masked wipe | Transitioning between two claims |
| Push-in hold | A claim that deserves stillness after motion |
| Stack assemble | Items becoming a system — the "list → relationship" move |
| Draw-on connector | Making a relationship visible between existing things |

Rules that hold across all of them:

- **Enter fast, settle slow.** Roughly 0.18–0.28s in, then a longer ease-out. Snappy entry is what reads as "confident" at feed speed.
- **One motion per element per beat.** Two simultaneous motions on one element is noise.
- **Stagger, don't sequence**, when a group should feel like one gesture; sequence when order carries meaning.
- **Only `transform` and `opacity`.** Never `left`/`top`/`width`/`height` — they quantize to whole pixels and stutter in the render.
- **Every CSS value carries its unit.** A generated `36` is an implicit syntax error that HTML tolerates silently.
- **Dwell at least 1.2s** on anything the viewer is meant to read. Fast kinetic styling still has to be readable in a feed that autoplays muted.

## Rhythm

The video is a sequence of **holds with motion between them**, not continuous motion. Structure each segment as:

```
claim lands (motion) → 1.5–3s hold → support appears (motion) → hold → segment exits
```

Vary the pattern between segments or the whole thing flattens into a metronome. A segment that is nothing but a wall of text with a fade is a legitimate rest point — do not animate a segment just to animate it.

Beat duration comes from the measured voiceover, never from a default. If a sentence is 1.4s of speech, its text has ~1.4s minus an entry animation. That constraint is what forces you to cut words, which is the point.

## Emphasis: what to actually animate

Not everything on screen moves. Rank by what the voiceover is doing at that moment:

- **The word the voice is on.** The strongest emphasis available, and it is free. Re-time the build to the measured speech, not to a nice-looking rhythm.
- **The claim.** When a segment states its argument, that line gets the biggest type, the longest dwell, and the stillest frame.
- **The contrast pair.** When the argument is "not A but B", A and B should not appear together at equal weight.
- **The number being counted to.** Animate the count itself, not a decoration near it.

Everything else stays still. Kinetic typography fails when everything moves, because then nothing is emphasized.

## Making abstract claims visible

The most valuable craft move in this format: **an abstract claim must become one visible action.**

A sentence like "viewers understand relationships, you gave them a list" has no picture. The version that lands:

1. Three grey blocks side by side — this is *a list*, and it looks like one.
2. Connector lines draw on in a single stroke, one after another.
3. The blocks reassemble into a tree, a staircase, or a 2×2 grid — this is *a relationship*.

The audience verifies the claim with their own eyes instead of taking your word for it. That is the difference between a video that restates its script and one that argues.

Test each abstract line: *what would a camera pointed at this sentence film?* If the answer is nothing, build the diagram. Prefer self-drawn SVG over stock footage here — the argument is usually a transition, and a camera can only hold one state of it.

## A persistent element can do the viewer's thinking

The highest-leverage design decision available. A single element that stays on screen for the whole video, advancing through the video's own argument (hierarchy → sequence → two dimensions → everything lit), does two things a caption cannot:

- A viewer scrolling **muted** still gets the structure of the argument from it alone.
- A viewer who did not follow the voiceover can reconstruct what the video was claiming, after the fact.

Build it once, drive it from `timeline.json`, and check its own states in the snapshot pass.

**Design it as data before it is design.** Write the per-segment state — which states are lit, where the playhead sits — as a small table beside the timeline, then generate the animation from it. The payoff is that the spine's own progression becomes a second, wordless statement of the argument: if the table does not trace the order in which the video actually proves its case, the spine is decoration and the table is where the design error is visible before any code is written. States improvised while writing animation code drift out of argument by the third segment and nothing catches it.

## Footage

**Screen recordings.** Two rules that each cost a rework:

- **A crop cannot be chosen from one frame.** The window moves and the layout shifts over time, so the same crop rectangle frames different content at t=2 and t=9. Sample across the time axis and choose a crop that is valid for the whole interval you intend to use.
- **Survey at 0.5–0.8s granularity, not ~2s.** Coarse sampling lands repeatedly on dark page-turn transitions, and you will conclude the recording has no usable frames when it has plenty.
- **Re-encode the slices densely**: `ffmpeg -i in.mp4 -c:v libx264 -g 30 -crf 18 out.mp4`. Sparse keyframes make the renderer seek poorly and stutter. Always use a GOP shorter than the clip length.
- **When content appears in both a title bar and the body**, a crop cannot remove it — re-cut the clip to start after it leaves. Check the *body*, not just the chrome: a line of body text can name the product for twenty seconds after the title bar has scrolled away.
- **Cut the card longer than the card is on screen.** A card's `<video>` ends and the shell keeps rendering, so the tail of the card shows an empty box. Extend the clip ~0.7s past the card's own exit rather than trimming the card to fit.
- **Give the clip a short fade-in** (`data-fade-in`). A video card often reveals its first frame a beat after its box appears, and the mismatch reads as a flash.

**Series: a range is used once.** Episodes cut from one shared recording pool must not reuse the same in/out ranges. Keep a per-episode `clip → in → out` table next to the footage and check it before cutting. A duplicated range is invisible to every check and is the first thing a viewer scrolling the series notices — it is what makes a series read as a template instead of six distinct pieces.

**Photos.** Cut on the beat. Hold a photo for less time than feels right; a still frame held too long reads as a stall in a feed.

**ffmpeg notes.** `say` cannot write mp3 directly — it produces a 16-byte empty shell; write aiff and convert. `tile`/`xstack` fail on mismatched input sizes; pad to a common size first. `drawtext` is absent from some builds (Homebrew's ffmpeg ships without it in some configurations) — check with `ffmpeg -filters | grep drawtext` before building a QA step around it, and label contact sheets by filename instead of burning timestamps into the frame.
