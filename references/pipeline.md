# The pipeline, stage by stage

Contents: [Layout](#episode-layout) · [Stage 1 split](#stage-1--split-the-deck) · [Stage 2 reference VO](#stage-2--reference-voiceover) · [Stage 3 timeline](#stage-3--timelinejson) · [Stage 4 generate](#stage-4--generate-the-composition) · [Stage 5 review](#stage-5--user-review) · [Stage 6 snapshot QA](#stage-6--snapshot-qa) · [Stage 7 render](#stage-7--render) · [Schema](#timelinejson-schema)

## Episode layout

```
<episode>/
  策划稿.md              the copy deck you were given
  script/seg-01.txt …    per-segment voiceover text (one file per segment)
  audio/vo/seg-01.*      reference voiceover, synthesized
  audio/segments.json    MEASURED durations — the input to stage 3
  audio/bgm.*  audio/sfx/  audio/bed.wav
  assets/                photos, screen recordings, logos
  timeline.json          source of truth: content + timing
  tools/build.mjs        generator: timeline.json → index.html
  index.html             GENERATED — never hand-edit; edit the JSON or the generator
  打点表.md               GENERATED timing sheet for the person recording
  renders/episode.mp4
```

`index.html` and `打点表.md` are build products. If they disagree with reality, the bug is in `timeline.json` or `build.mjs`, not in the generated file. Hand-editing a generated file guarantees the next run silently reverts it.

## Stage 1 — split the deck

8–14 segments. Each segment is **one idea**, not one sentence and not one paragraph.

Test each segment against two questions:
- Can it be one screen of type? If not, it is two segments.
- Does it have a claim? A segment that only sets up the next one is a cut, not a segment.

Set the segment order now, because stage 2 spends real time synthesizing.

## Stage 2 — reference voiceover

Do not skip this and do not eyeball the timing. A 634-character deck estimated at 2:20 measured 111.6s — the reference voice reads ~20% fast, and knowing that before layout is the difference between one revision and a re-cut.

1. Write each segment's voiceover text to `script/seg-NN.txt`. This is the text the person will later record, so write it as spoken language, not as slide copy.
2. Synthesize each one separately. Per-segment synthesis is what makes durations measurable and re-timable; a single monolithic synthesis cannot be re-laid-out when one sentence changes.
3. Measure them:

```bash
python3 <skill-dir>/scripts/measure_segments.py audio/vo --gap 0.35 --out audio/segments.json
```

`--gap` is the breath between segments; 0.30–0.40s reads as natural at 1× speed. The script reports each segment's real duration, its characters-per-second rate, and the total including gaps.

4. **Compare the measured total to the deck's own estimate.** If they differ by more than ~10%, stop and tell the user, with both numbers. Either the script is too long for the format or the estimate was fiction; the user decides whether to cut or to speed up, and that decision changes the entire layout.

5. If the user will record their own voice later, hand them `打点表.md` at stage 5 — a page they can record against, one line per sentence with the time it must land on. Their recording then matches the finished film by construction.

## Stage 3 — `timeline.json`

The single source of truth. Content and timing live here; the generator reads it and nothing else.

Write it after measuring, not before. The generator (`build.mjs`) turns this JSON into `index.html`.

Then validate — this is the gate, not a formality:

```bash
python3 <skill-dir>/scripts/validate_timeline.py timeline.json --out 打点表.md
```

It asserts:

- every id in the file is unique
- every element's on-screen time `t` falls inside its own segment `[t0, t1)`
- every card's rectangle sits inside `meta.safe`
- every duration is positive
- content beats do not run past their segment's end (cards may, by design — see below)

Re-run it with `--html index.html` after stage 4 to catch the classic failure: a field present in the JSON that the generator never emitted. A block that is supposed to render and silently does not is the single most common bug in this format, and it produces no error anywhere.

## Stage 4 — generate the composition

`build.mjs` reads `timeline.json` and writes `index.html`. Author the composition itself against `/hyperframes-core`.

The generator's own contract — these are the parts that break silently:

**Emit by iterating values, never by a hand-written field list.** The bug shape is:

```js
// BROKEN — row / row2 / bignum are not in this list, so they vanish
const FIELDS = ['t0', 't', 'text'];
```

Iterate the object and let a known-keys set decide which are optional. A generator that depends on remembering to update a list will always eventually miss one.

**Translate every time field.** A common variant: the JSON has both `t0` and `t`, the generator forwards only `t0`, and the element appears from 0.95s instead of its intended moment — with no error.

**One `fadeOut()` for everything:**

```js
const fadeOut = (ctx, sel, tIn, durIn, tail = 0.34) => {
  const t = Math.max(ctx.end - tail, tIn + durIn + 0.05);
  gsap.to(sel, { opacity: 0, duration: 0.34, ease: 'power2.in' }, t);
};
```

Because `fromTo` applies its "from" state at `seek(0)`, an element whose fade-out precedes its own fade-in completion never leaves the screen. Collapsing the rule into one function that cannot be mis-ordered eliminates the entire class.

**`NaN` in a time is invisible.** A fade-out read from a field that does not exist on the object (`nx.start` when the object only has `end`) lands on `NaN`, the tween never fires, and a dozen segment headers sit stacked on the same spot for the whole film. Validate times are finite — the static audit checks for `NaN` and `undefined` in emitted time arguments.

**Positioning wrapper is a parent.** `at(x, y, html)` must return a positioned container *containing* `html`, not a positioned div followed by a sibling.

**Stamp timing onto every timed element.** The moment you push an element, give its wrapper `data-start` and `data-duration`. An element without them is treated as present for the whole film, so every checker samples it — including at `opacity: 0` — and reports contrast and overlap failures for elements that are *supposed* to be invisible there. Those reports cannot be fixed by editing the element; they are the symptom of the missing attributes. A helper like `markLast(t, outT)` applied once at push time removes the whole class.

Then audit the output:

```bash
node <skill-dir>/scripts/audit_html.mjs index.html
```

This catches, without a browser: ids referenced by the runtime but never defined, `fromTo` pairs whose timing can strand an element, CSS numeric values with no unit, transforms applied to `<video>`, `<video>` without an id, and non-finite time arguments. It is a supplement to `npx hyperframes check`, not a replacement — the CLI's checker knows about contrast and overlap, this one knows about the silent-failure patterns specific to generated compositions.

**Read the check report line by line, not the count.** A drop from 232 issues to 35 to 0 sounds like progress; the 35 usually mixes two categories — real problems, and elements that have already faded to `opacity: 0` and are being sampled anyway. Distinguish them by reading each entry's id. "Fixing" the second category means changing elements that are supposed to be invisible.

## Stage 5 — user review

Hand over two things and wait:

1. **`打点表.md`** — every segment, every sentence, what time it goes on screen, generated from `timeline.json`. One page the user can read to correct the copy and the beat times without watching anything. This is much faster for them than reviewing a render.
2. **The storyboard / design direction** — the motif, the palette, the type scale.

Also surface the stage-2 finding: measured total vs estimated total.

Do not proceed to a full render on the strength of your own approval.

## Between stages 5 and 6 — copy revisions

If stage 5 comes back with changes, do not treat it as "redo the layout". Deleting a phrase means finding every copy of it first — including inside the stills you cut as graphic cards — and deciding whether it is data or a word the voiceover names. Re-running validate and audit is enough; a full re-layout is not. Procedure and the data-versus-words test: [revisions.md](revisions.md).

## Stage 6 — snapshot QA

Layout errors are found with images, never with renders.

```bash
npx hyperframes snapshot --at 1.2,3.4,6.8,9.1
```

Build the timestamp list from the timeline: **one frame per segment at 70–90% of the segment**, not at its start. Frames at segment starts land in the pre-animation gap and read as layout bugs that do not exist — early passes in this format wasted a full round of rework on exactly that misread.

Inspect each frame. Look for: text escaping the safe zone, the talking-head slot being occupied, overlapping elements, missing elements (the silent-omission bug), type too small to read at phone size, and a card whose backing video has already ended while the card is still visible.

**Cards must outlive their own video by ~0.7s.** If a card's backing clip ends first, the tail of the card shows an empty shell. Either trim the card or extend the clip.

Fix, re-snapshot, inspect. Only when every segment's frame is correct does a full render earn its cost.

## Stage 7 — render

```bash
npx hyperframes render --quality looks --output renders/episode.mp4
```

**Run it in the foreground of the call and poll there.** Backgrounding it with `nohup ... &`, or piping its output into `tail`, suspends the process: it stalls around 30–40%, then dies silently with no error and no exit status worth reading. A foreground run of a ~2-minute video takes two or three polls and finishes cleanly.

**If it stalls, it is suspended, not slow.** `ps -o pid,stat,%cpu,command` shows `T` (stopped), ~0% CPU, and no Chrome child process. `kill -CONT <pid>` resumes it. Confirming this in ten seconds is much cheaper than re-running and waiting.

Verify the output: file exists, non-empty, and `ffprobe` duration matches the timeline total.

**Render once, deliver twice.** The reference voiceover is a timing instrument, so the master that ships carries the bed and accents only, and a second cut carries the guide voice for whoever records next. Produce both from the same render — mux, do not re-render:

```bash
# the clean master already has its audio; the guide cut swaps in the reference VO
ffmpeg -i renders/episode.mp4 -i audio/master_voice.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 256k -shortest renders/episode-refvo.mp4
```

Name them so the difference survives being forwarded in a chat: `…-v1-纯配乐版` and `…-v1-参考口播版`. In the handover, say which is the master and that the guide cut must not be posted — a machine voice that sounds merely passable is the easiest mistake to ship.

**Then extract frames from the finished mp4 and look at them.** This is not optional and it is not a repeat of stage 6. The composition can pass every static check, validate clean, and still contain wrong art — a 2×2 grid drawn with full-cell width and height overlaps itself with no exception and no warning, and the only place that is visible is a frame of the delivered file.

```bash
ffmpeg -i renders/episode.mp4 -vf "select='eq(n\,<frame>)'" -vsync vfr qa/frame-<frame>.png
```

### On repeated renders

If you find yourself on render #2, stop and ask what class of bug render #1 could have caught. Almost always the answer is one of: no snapshot QA, a generator field silently dropped, a stranded fade, or a card outliving nothing. Fix the class, not the instance — the same bug will appear in the next episode otherwise.
