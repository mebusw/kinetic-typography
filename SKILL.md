---
name: kinetic-typography
description: Produce vertical (9:16) kinetic-typography shorts — text-led explainers, opinion clips, and scripted shorts — from a copy deck or script, including when the voiceover has not been recorded yet. Use when asked to "make a kinetic typography video", "动效文字视频", "竖屏文字短视频", "字幕动效视频", or to turn a 策划稿/口播稿/文案 into a timed, captioned, music-backed vertical video with a reserved slot for a talking-head overlay. Covers reference-voiceover timing, retiming onto a real recorded voiceover (transcribe → tighten → re-derive), the timeline.json → composition pipeline, safe zones, talking-head slot layout and occlusion checks, per-segment snapshot QA, audio leveling, SFX cue alignment, synthesizing a BGM/SFX bed with numpy, and the silent-failure traps specific to this format. Not for landscape/16:9 promo films, slide decks, or plain subtitled video with no designed motion.
---

# Kinetic Typography (vertical)

Text is the subject, not the caption. Every element on screen is a word or a mark that moves because the argument moved.

This skill covers the production loop for vertical, script-driven, text-led shorts on HyperFrames. The framework contract (`data-*` timing, clips, tracks, seek safety) lives in `/hyperframes-core`; CLI mechanics in `/hyperframes-cli`; music/SFX/voice resolution in `/media-use`. Read those when you need them — this skill owns **timing, layout, and the QA gates**.

## The one idea that makes this work

**Measure the voiceover. Never estimate it.**

A copy deck's word count implies a duration; that number is wrong, often by 20%. Synthesize a reference voiceover, measure each segment's real duration with `ffprobe`, and lay the timeline out from those measurements. Then the timing table you hand the person to record against is *data* — they record to it and it lands. When the measured total disagrees with the deck's estimate by more than ~10%, that is a finding to surface before building, not after.

Full stage detail: [references/pipeline.md](references/pipeline.md).

**That paragraph is about a synthesized reference VO, which is a stopwatch. The moment a real
recording exists it stops being a stopwatch and becomes the score** — and the whole timing
basis has to be re-derived, not rescaled. Transcribe the take, tighten its pauses *before*
timing anything, cut any false starts the speaker owns up to, then compute every element's
time from the transcript. Budget 20–25% of the raw take for tightening; a cut that came back
within 5% of the raw length means the gate did not run. Full procedure, including the
re-transcribe-after-every-cut rule and the phrase-anchoring pattern:
[references/real-voiceover.md](references/real-voiceover.md).

## Default pipeline

Each stage is a gate. Do not enter stage *n+1* until stage *n* passes.

| # | Stage | Gate before moving on |
|---|---|---|
| 0 | **Direction** — one page: the narrative shape, the 母题, the devices derived from it, and an explicit *this episode will not* list | The motif is derived from this deck's content, not borrowed from the last episode; a series episode differs from its predecessor on ≥3 direction axes |
| 1 | **Split** the copy deck into 8–14 segments; each is one idea | Each segment's text fits one screen's worth of type |
| 2 | **Reference VO** — synthesize per segment, `ffprobe` real durations | Measured total vs deck estimate reported to the user |
| 3 | **Timeline** — write `timeline.json` (content + measured times); run the pre-flight validator | `validate_timeline.py` **and `assert_timeline.py`** pass |
| 4 | **Generate** the composition from the JSON; run the static audit | `audit_html.mjs` reports no missing ids and no timing hazards |
| 5 | **User review** — hand over the generated 打点表 (timing sheet) and storyboard | User has corrected the copy and beat times |
| 6 | **Snapshot QA** — one frame per segment, sampled late in the segment | Every frame inspected; layout errors fixed here |
| 7 | **Render once**, foreground, then extract frames and boundary strips from the finished mp4 | Frame count and duration match the timeline; every segment boundary seen in a cut strip |

The single most expensive mistake in this format is re-rendering to check layout. A full render costs minutes; a snapshot costs seconds. Stages 4–6 exist so that stage 7 happens **once**.

## Non-negotiables

These are the failure modes that produce a wrong video with **no error message at all**. Each has caused a full re-render.

1. **The generator asserts; it does not remember.** A generator driven by a hand-written list of "fields to emit" silently drops every field not on the list. Assert that all content keys reached the output, that every on-screen time falls inside its segment, and that every card sits inside the safe zone. Use `scripts/validate_timeline.py`.
2. **Named ids only.** Never recover an element id by arithmetic on a counter (`z - 5 + i`). The animation runtime logs one `target not found` line and the art is silently wrong — staircases become zigzags, a 2×2 grid collapses into overlapping quadrants.
3. **Animate `transform` and `opacity` only.** Never `left`, `top`, `width`, or `height` — layout properties quantize to whole pixels and stutter during render. And every CSS numeric value in generated code carries its unit (`36px`); a bare number is a syntax error the HTML renderer tolerates anyway.
4. **The positioning wrapper is the parent, not a sibling.** A helper that emits `<div class="at"><div class="content">` without the content being a child leaves the content in normal flow. The first few elements land in plausible positions by coincidence, which is what makes this bug survive four renders.
5. **One helper owns fade-out timing.** GSAP's `fromTo` applies its "from" state at `seek(0)`, so any element whose fade-out is scheduled before its fade-in finishes is stranded on screen for the whole film, silently. Route every element through a single `fadeOut()` that computes `t = max(end - tail, tIn + durIn + epsilon)`.
6. **Every `<video>` needs an `id`, and never gets a transform.** Without an id the frame renders frozen. Transform the untimed wrapper `<div>` around it; transforming the element itself misplaces and miscrops the picture.
7. **Snapshots sample the *end* of a segment.** A frame at the segment start lands in the gap before anything animates in, and reads as a layout bug that isn't there. Sample at 70–90% of each segment.
8. **Render in the foreground.** `nohup ... &`, or piping output to `tail`, suspends the process; it stalls around 30–40% and dies with no error. Run it in the foreground of the call and poll there.
9. **Contrast is computed, not judged.** Eyes are unreliable at low contrast and a background gradient makes paper calculations wrong anyway. Score candidates against the composited background: `scripts/contrast.py`.
10. **Missing footage is an opportunity.** If the missing clip carries information, draw it (SVG, diagram, staged reveal) instead of downgrading the segment. Self-drawn can show the *transition* from wrong to right; a camera can only show one state.
11. **When static analysis contradicts your mental model, render one frame and look.** Do not spend rounds theorizing about blur, stacking contexts, or selector scope. One screenshot ends the argument.
12. **Give every timed element `data-start` and `data-duration`.** An element carrying no timing attributes is treated as present for the whole film, so every checker samples it — including at `opacity: 0`. You then get phantom contrast and overlap reports about elements that are *supposed* to be invisible there, and you cannot fix them by editing the element. Stamp the attributes onto the wrapper the moment you push it; it is both framework-correct and the only cure for that whole report class.
13. **On-screen copy inherits the deck's red lines.** Copy decks for these videos usually carry wording rules — no jargon, no product name in the voice, one set of numbers. Screen text is bound by the same rules and breaks them more easily: a label naming the product violates a rule the voice obeys, and it is invisible in a contact sheet. Grep the finished frames for stray English and for numbers that contradict the deck.
14. **A group fades as one unit, or its children are stranded.** A "19 + nineteen dots" beat faded the number and the label and left the grid on screen for the rest of the film. Collect every child — number, label, every dot, every swatch — into one selector array and hand that array to the single fade. `audit_html.mjs` reports `never-fades-out`; read each id against its DOM parent first, since a true child of a fading parent legitimately inherits it.
15. **Anything that outlives its segment owns its own in and out.** A step track that fills across segments 11–13 has no per-segment beat to inherit a fade from, so without an explicit `set(opacity: 0)` at t=0 it is visible from the film's first frame. Persistent furniture is the one class of element that is never safe by default — pair it with the mapping-table rule under Layout constraints, which governs what the device *shows*; this governs *when it exists*.
16. **Two-column beats need explicit `x` and `w`.** A full-width text helper run at the content width will sit on top of the right column, and a card is centred until you pin it. Give every element in a split beat its own box.
17. **The placeholder voiceover is a stopwatch, never a deliverable.** Ship **two cuts**: a clean master with the bed and accents only, and a separate reference-VO cut for the person recording against. Name them so the distinction survives the folder (`…-v1-纯配乐版` / `…-v1-参考口播版`), say in the handover which one is which, and keep the machine-voice cut out of anything that gets posted. A synthesized voice that happens to sound passable is the single easiest thing to leak into a publish.
18. **Your QA tool can be the flaky thing.** Probing a live composition is where the environment, not the art, eats the time: software video decode makes the page's main thread stall unpredictably, so the same `evaluate` that returns in 3ms times out at 120s on the next run with no error from the page. Block `<video>`/`<audio>` in the probe — a layout probe needs geometry, not pixels, and every box keeps its real size. Measured on a 10-clip composition: ~50% of runs stalled without it, 0 of 6 with it.

Full diagnosis table — symptom, real cause, fix: [references/pitfalls.md](references/pitfalls.md).

## When the user asks for a change

Copy revisions have their own failure mode: **a phrase lives in more than one place.** A number deleted from the timeline is still visible inside a screenshot you cut as a still, and a "step name" that merely echoes the voiceover line is not the same kind of thing as the data itself. Before editing, grep the timeline *and* open the image assets.

The judgement call is data versus words: delete the fabricated figure, keep the step the spoken line names. Sample content on screen should be a title — `## 项目交付复盘` — never an invented metric, because portrait frames get screenshotted and a large fake percentage reads as a real business figure. Full procedure, including what must be re-rendered and what does not need to be: [references/revisions.md](references/revisions.md).

## Layout constraints that are not negotiable either

- **9:16, and the safe zone is not the frame.** Platform UI eats the top ~120px and the bottom ~300px. Text never enters those bands. The validator enforces this; see `meta.safe` in the timeline schema.
- **Reserve the talking-head slot.** If the user will record a face-cam later, carve it out **from the start**: short side ≈ ¼ of the frame's short side, anchored bottom-left or bottom-right, and keep the layout clear of it. If no footage exists yet, leave the slot empty — never shrink the type to fill it, and never move the composition to make room later. When the footage does arrive: **crop a square around the head before masking, mask with CSS `border-radius` and never with an alpha-encoded video** (a libvpx build without WebM alpha drops the plane silently and you get an opaque square), and give every screen-recording card a hard bottom edge above the slot. Three separate overlap checks are needed — text vs face-cam, face-cam vs cards, text vs cards — and text must be measured with a `Range`, not its full-width element box, or the check produces nothing but false positives. Layout table, crop probe, and the three-check harness: [references/facecam-layout.md](references/facecam-layout.md).
- **Abstract claims need a visible action.** "Viewers understand relationships, you gave them a list" has no picture. What works: three grey blocks in a row (the list) → connector lines drawn on in one stroke → reassembled into a tree. The audience verifies the claim with their own eyes instead of taking your word for it.
- **One motif per episode, derived from the product's *action*, not from its palette.** Before designing, write down what the previous episodes already used: motif, spine organ **and its orientation**, accent colour. A new episode that reuses the same organ in a different shape still reads as the same episode — differ in kind, not in appearance, because a right-hand vertical rail and a top horizontal rail are two different devices even though both are "a rail". Then derive the new motif from what the product actually *does* this episode, which is an action, not a look.
- **A persistent device is designed as a mapping before it is coded.** Write its per-segment state down as data — a small table of "segment → what lights up, where the playhead sits" — and generate the animation from that table. A spine whose states were improvised while writing animation code drifts out of the argument by the third segment.
- **Two beats in one segment need per-element durations, not a segment-wide exit.** When a long segment runs two judgements in the same layout rows, the first beat's elements must carry their own `dur` that ends before the second beat lands. Left on the segment's exit, both beats are declared on-screen at once and the overlap report is *correct* even though the picture looks fine.
- **Derive card height from the asset, never from memory.** Probe each cut once and store its `width,height`; compute the box from the real aspect ratio. Hand-typed heights are how a 16:9 still ends up stretched and a portrait clip ends up letterboxed into a bar.
- **A card's `t` and `out` are absolute time; a card's *authored* value is relative.** Cards are written into the segment spec as段内相对时间 and made absolute in one place — the expansion loop. When that conversion is missing for a segment that starts at 70s, its card fires at **0.8s**, during the title; the film still renders and still looks plausible in a contact sheet, because the first segment does have cards. Assert it: `0 <= cd['t'] - c['start'] <= c['dur']` for every card. This catches the whole family of relative/absolute slips, including an un-absolutised `out` landing *before* its own `t` so the card never appears at all.
- **Vertical means the type must be huge.** Assume a phone at arm's length. Body text below ~28px at 1080-wide is unreadable in-feed; if it will not survive that, cut the words.

Motion vocabulary, type scale, rhythm, and emphasis rules: [references/motion-and-layout.md](references/motion-and-layout.md).

## Audio

Full procedure: [references/audio.md](references/audio.md). The three rules that matter most:

- **Level by RMS against a target offset, never by peak normalization.** Peak-normalized music can measure louder than the voice. Target the bed ~20–25 dB below the voice's RMS, then listen.
- **Duck the music only.** A sidechain keyed to the voice must not touch sound effects — compress the SFX and the click/whoosh accents disappear.
- **Align every accent by its measured onset or peak.** Clicks align at the onset, whooshes at the peak and start *before* the picture; a cue dropped at the action's timestamp lands 30–80ms late and the whole film reads loose. `scripts/sfx_landmarks.py` prints the numbers, and the same measurement sets each cue's gain.
- **A synthesized bed is wrong in a way that produces no error.** Loudness checks all pass and the mix still feels uneasy, because the problem is *where the energy is*, not how loud it is. Three measurements catch it before a human does: spectral balance (**>55% of energy below 150Hz is the uncanny band** — target ~35% sub / 55% low-mid and leave 1.2k–8k deliberately empty for the voice), crest factor (**12–18dB healthy; under 9dB means the saturator crushed everything to one loudness**), and a zero clip count. Synthesizing the bed, writing `impact`/`pluck`/`bell` that do not sound like a knock and a beep, and lifting a proven synth's core while rewriting its arrangement: [references/bgm-and-sfx.md](references/bgm-and-sfx.md).

## Scripts

`<skill-dir>` below is this skill's own folder — resolve it to an absolute path before running. Every script takes `--help`.

| Script | Use it for |
|---|---|
| `scripts/measure_segments.py` | ffprobe a directory of per-segment voiceover files into measured durations + a laid-out timeline skeleton, and compare the measured total against the deck's own estimate |
| `scripts/validate_timeline.py` | Pre-flight assertions on `timeline.json`; with `--html` also catches ids the generator never emitted; `--out` writes the 打点表 timing sheet |
| `scripts/audit_html.mjs` | Static audit of the generated composition: unresolved selectors, duplicate ids, stranded-fade hazards, `NaN` times, unitless CSS values, layout-property animation, idless or transformed `<video>` |
| `scripts/assert_timeline.py` | Timeline assertions: every card inside its own segment (catches the relative→absolute slip), `out` after `t`, finite times, sfx inside the runtime. Run this **before** the static audit — it catches the one bug no other check sees |
| `scripts/check_occlusion.mjs` | Three overlap checks — text vs face-cam, face-cam vs cards, text vs cards — over a list of sample times. Text measured with a `Range`, whole sweep in one `evaluate`. Set `PUPPETEER_CORE` if `puppeteer-core` is not resolvable |
| `scripts/contrast.py` | WCAG ratio for candidate text colors against the real composited background, with alpha blending and passing-variant suggestions |
| `scripts/level_audio.py` | RMS-target the music bed, apply voice-keyed ducking and fades, and print the numbers it used |
| `scripts/sfx_landmarks.py` | Measure each accent file's onset, peak time and peak level — the numbers that align a cue to its action and set its gain |
| `scripts/probe_dom.mjs` | Drive the live composition: seek to given times, screenshot each, and dump computed style + geometry for named elements. Use it when a visual bug is real but the cause is not obvious. Blocks media by default (see non-negotiable 18); pass `--media` when the card pixels matter |

Start a new episode from `assets/timeline.template.json` — it is the schema the validator enforces, and it passes clean. Copy it into the episode folder and edit from there.

## When the series has several episodes

Single-episode rules assume one film's worth of footage. A series adds three constraints that are cheap to honour and expensive to discover after delivery:

- **Footage can belong to exactly one episode.** If only one script in the series says the product name out loud, only that episode may show the screen recording where the name is legible. The others look like they have the same footage and quietly break the naming convention the scripts depend on.
- **Shared long recordings get a different range per episode.** A 60-second scroll through a gallery, used whole twice, is the same shot twice. Take a different interval and freeze on a different page each time.
- **Divergent motifs are not decoration.** Adjacent episodes sharing a palette read as one long film; the motif rule under Layout constraints governs the choice, and the stage-0 "this episode will not" list is what keeps it honest once the deadline is near. The master table's columns are the axes — differ in at least three of them between adjacent episodes, in kind and not just in appearance.
- **Version the deliverables, and keep the two cuts apart.** `01 格式返工型-归位-v1-纯配乐版` and `…-参考口播版` is a naming scheme that survives being passed around in a chat message three weeks later. The number in the name is what lets the next episode say "same direction, v2" instead of "the one we changed". **The exception is a real voiceover:** once the actual face and voice are baked in, the reference-VO cut cannot exist — you cannot swap the audio without swapping the picture, because the picture *is* the person speaking. Ship one file, and do not leave a `…-参考口播版` sitting next to a real-voice episode where someone can publish the wrong one.

## Where to put the project

Do not assume a fixed root. Create the episode folder **beside the material the user gave you** — in the folder containing the 策划稿, or the series folder its siblings already live in. If neither is obvious, ask once, in one line, then proceed. Never write into this skill's own directory.

When this is episode *n* of a series, the series keeps **one** master file — a visual master table: one column per episode covering motif, spine organ **and its orientation**, palette, signature move, audio texture, exclusive footage, and a collision table of which source range each cut used. Episode *n* reads it before designing and appends a column when done.

The per-episode direction doc then carries only the **diff** — what this episode avoids and what it chose instead — plus a pointer to the master. Do not restate the previous episodes' motifs inside each direction doc: three copies of the same list drift apart, and by episode four nobody can tell which one is current. Keep the rule in this skill; keep the series' actual motifs, palettes and ranges in the project's own file, never here — a skill that hard-codes one project's palette is wrong for the next project.

Expected episode layout and the full `timeline.json` schema: [references/pipeline.md](references/pipeline.md).
