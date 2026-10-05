# Pitfalls: symptom → real cause → fix

The failures in this format share one property: **most of them produce a wrong video and no error at all.** Organize by that, not by tool.

Contents: [Silent omissions](#silent-omission-nothing-renders-nothing-errors) · [Stranded elements](#stranded-elements-something-is-stuck-on-screen) · [Wrong art, no error](#wrong-art-no-error) · [Tofu and fonts](#tofu-and-fonts) · [The checking](#the-checking) · [Rendering](#rendering) · [Live DOM A/B probe](#live-dom-ab-probe) · [Cost](#the-expensive-way-to-learn-the-same-things)

## Silent omission: nothing renders, nothing errors

**Symptom.** A whole block of a segment is missing from the finished video. `check` is green, the render succeeds, no console error.

**Cause.** The generator emits based on a hand-maintained list of fields. Anything not on the list is dropped without a word.

**Fix.** Iterate the data and assert. Then, after building, cross-check the ids in `timeline.json` against the ids in `index.html`:

```bash
python3 <skill-dir>/scripts/validate_timeline.py timeline.json --html index.html
```

**Rule.** *Add assertions, not memory.* A generator that depends on you remembering to update a list will miss one eventually. The same class covers a time field that exists in the JSON but is never translated — the element appears at the wrong moment instead of not at all.

## Stranded elements: something is stuck on screen

**Symptom.** A dot-matrix of numbers, or a dozen segment headers, is visible on *every* frame of the film. It was supposed to appear in one segment for 2 seconds.

**Causes, in order of likelihood:**

1. **GSAP's `fromTo` with `immediateRender`.** The "from" state applies at `seek(0)`. If the fade-out is scheduled before the fade-in finishes, the element never leaves. No error. Route every element through one `fadeOut()` that computes `max(end - tail, tIn + durIn + epsilon)`.
2. **A `NaN` time.** The fade-out read `nx.start` when the object only has `end`. The tween lands on `NaN`, never fires, and the element stays. This is what stacked twelve segment heads on one spot. Always assert times are finite.
3. **A selector matching the wrong element.** `#root>div` matches far more than you meant.
4. **A group's children were not in the fade.** The number and the label faded; the nineteen dots did not. Same symptom, and the fix is different: build the group's selector array while you create it (`marks.push(...)`), then fade the array.
5. **A persistent element with no fade at all.** A step track that fills across segments 11–13 has no per-segment beat to inherit a fade from, so with no explicit `set(opacity:0)` at t=0 it is on screen from frame one. "Never fades out" is not only a stranded *end*; it can be a stranded *beginning*. `audit_html.mjs` catches both as `never-fades-out`.

**Fix.** One helper, finite-time assertions, and a static scan for `fromTo` pairs whose windows can invert.

**Compounding case.** A helper-line element with `opacity: .9` in its `from` state is the worst version of this — the line is at 90% opacity from t=0 to its own start time. Use `set` + `to` for anything that must be truly absent beforehand.

## Wrong art, no error

**Symptom.** A staircase renders as a zigzag. A 2×2 grid's four quadrants sit on top of each other.

**Cause.** Not GSAP. Ids were recovered by arithmetic on a generation counter (`z - 5 + i`) instead of being named. The runtime logs one `target not found` and the geometry is silently wrong.

**Fix.** Named ids, always. This is why: with named ids, the same class of error has not recurred.

**The 2×2 trap specifically.** Drawing four quadrants using the *full* cell width and height makes them overlap. Half-open rectangles: `w/2` and `h/2`, with the second quadrant offset by `w/2` and `h/2`. There is no error and no warning for this — check all green — and it is only visible in a frame of the finished mp4.

**The overlap report that lies.** A `content_overlap` entry like `#cn93 inside #cn93` claiming two things overlap at t=1.12s, when that element first appears at t=50s, is usually a mis-scoped selector or a stacking-context artifact. When a static analyzer's complaint cannot be reconciled with your mental model, **render one frame and look at it.** This cost six wasted calls in one session and the screenshot ended it immediately.

## Horizontal collision: the beat that looked fine and covered itself

**Symptom.** In a two-column beat, the left column is clean and the right column's annotation is half-hidden behind a card. Nothing errors; `check` reports a `content_overlap` you read past, because the columns look intentional.

**Causes:**

1. **The text helper defaults to full content width.** Run at `CW`, a line intended for a 456px column is emitted 912px wide and lies on top of its neighbour. A text element needs `x` and `w` the moment it enters a split beat.
2. **Cards are centred until pinned.** A card helper that centres by default will sit exactly on the annotation column. Same beat, same fix: pass `x`.
3. **The audit only knows the safe zone, not the neighbours.** `validate_timeline.py` checks cards against `meta.safe`; it does not check card against text. Nothing static catches this — the frame does.

**Fix.** Give every element in a split beat an explicit box, and snapshot that beat at full resolution. A contact sheet at 300px wide hides a half-covered column; a single full-size frame does not.

## Tofu and fonts

**Symptom.** Characters render as boxes.

**Do not** cycle through font stacks (Menlo → ui-monospace → PingFang → …) building comparison pages. That was three rounds and six control renders before the real cause turned out to be somewhere else entirely.

**Cheap falsifying experiment.** Clone the element in the live page, inject it with identical CSS, and compare. A clean clone under the same CSS means the problem is not the CSS or the stack.

**Rule.** *An assumption must be falsifiable by one cheap experiment.* If it is not, change the assumption — not the parameters.

**When you do fix fonts:** `@font-face` with `src: local(...)`, and verify the render machine resolves the same face the design machine shows.

## The checking

- **Contrast is arithmetic.** A grey at a nominal 4.6:1 on a flat swatch measured 4.43:1 in situ because a gradient overlay made the real background lighter. Score candidates against the composited background with `scripts/contrast.py` (it blends alpha), pick the passing one, and move on. Eyes are unreliable at low contrast.
- **Secondary text gets sampled even when invisible.** After a fade, elements at `opacity: 0` are still measured. Separate real violations from these before changing anything — "fixing" an invisible element's color is a wasted edit that can make a real element worse.
- **The cure for the invisible ones is not to silence them — it is to make the element genuinely timed.** An untimed element has no declared lifetime, so the checker is right to sample it everywhere. Add `data-start`/`data-duration` to its wrapper and the framework keys visibility off it, the checker skips it outside its window, and the entry disappears because the report was correct. Expect this report to contain both kinds at once — in one episode the real colour violations and the invisible-element artifacts sat in the same list and only the ids told them apart.
- **A third category: the element is mid-crossfade over a bright card.** A contrast entry reading ~2:1 for a dim label is usually the checker sampling a frame where that label is at 40% opacity while a white screen recording fills the band behind it. Neither state is the resting state. Tell them apart by timestamp: an entry whose time coincides with that element's fade tween is a crossfade, and the fix is to shorten the overlap or move the label, never to repaint the colour.
- **Read the report per entry, not per count.** 232 → 35 → 0 is not a story. Each entry's id is.
- **Snapshot sampling points are a technique.** One frame per segment, at 70–90% of the segment. Segment starts are empty and produce false alarms.
- **Baseline against a known-good sibling before you blame yourself or the tool.** When a project that has always checked clean suddenly reports dozens of overlaps, run the same command on the previous episode's project. Forty errors that are really "my new element introduced a genuine collision" and forty that are "this tool is noisy" need opposite responses, and the sibling tells you which in one command.
- **A fabricated figure on a vertical frame is an editorial problem, not a design one.** Portrait frames get screenshotted and reposted. Sample content on screen should be a title (`## 项目交付复盘`), never an invented percentage that reads as the user's real business data. Demo stills are usually fine — open them and look rather than assuming.
- **A smoke test verifies the mechanism, not the layout.** A 20-second render proves the pipeline works; it says nothing about whether the cards are inside the safe zone.

## Rendering

- **Foreground only.** `nohup ... &` or piping into `tail` suspends the process. It stalls at 30–40% and dies with no error. Run in the foreground of the call and poll there. This is the single most expensive lesson in the format.
- **The stall is diagnosable in ten seconds.** `ps -o pid,stat,%cpu,command` on the render process shows `T` (stopped), ~0% CPU, and no Chrome child. `kill -CONT <pid>` resumes it. Do not re-run before checking this — the log tail looks identical either way, and a re-run costs minutes and changes nothing.
- **Frame the finished file.** A composition can pass lint, pass check, and still contain wrong art. Extract frames from the delivered mp4 and inspect them. This step has no substitute.
- **Keep keyframes dense** in any footage you cut (`-g 30`); sparse keyframes cause seek failures and visible stutter.

## Live DOM A/B probe

When a visual bug is real but its cause is not obvious, stop guessing and measure the page. Inject a clone of the suspect element, dump computed styles and geometry for both, and diff:

```js
// paste in the devtools console on the live preview, or via a Playwright evaluate
const probe = (sel) => {
  const el = document.querySelector(sel);
  const c = el.cloneNode(true);
  c.id = el.id + '__probe';
  c.style.cssText += ';position:fixed;left:0;top:0;z-index:99999;';
  document.body.appendChild(c);
  const dump = (n) => {
    const s = getComputedStyle(n), r = n.getBoundingClientRect();
    return { sel: n.id, rect: [r.x, r.y, r.width, r.height].map(v => +v.toFixed(1)),
             position: s.position, transform: s.transform, opacity: s.opacity,
             display: s.display, zIndex: s.zIndex, fontFamily: s.fontFamily };
  };
  return JSON.stringify([dump(el), dump(c)], null, 2);
};
console.log(probe('#the-element'));
```

This has diagnosed both the sibling-positioning bug and the stacked-headers bug directly — the clone's numbers differ from the original's in a way that names the cause immediately. It is a standing diagnostic, not a one-off script; `scripts/audit_html.mjs` covers the statically detectable subset of the same failures. `scripts/probe_dom.mjs` is the tooled form of exactly this.

**The probe's own flakiness is a separate trap, and it is not the art's fault.** Software video decode lets a page with a dozen clips plus a music bed stall the main thread for tens of seconds, so a call that returned in 3ms times out at 120s on the next run, with nothing wrong in the page. Two symptoms, one cause: `Runtime.evaluate timed out`, and `Target closed` when the renderer dies mid-call. Before you start hunting for a bug in the composition, re-run the probe with media blocked (`probe_dom.mjs` does this by default; `--media` opts out) and see whether the failure survives.

**Several cached puppeteer copies are not interchangeable.** A copy paired with a mismatched Chromium can pass a trivial evaluate and then kill the renderer the instant request interception aborts a `file://` media request. Selecting the newest one by mtime is a coin flip. Validate the candidate, or pin the one you measured.

## The card that plays at 0.8s

**Symptom.** Half the film's screen recordings are missing and the first segment's card is
showing something it shouldn't. The render succeeds, the contact sheet looks plausible —
because the *first* segment does have cards, so the frame at the top of the sheet is fine.

**Cause.** Cards are authored as段内相对时间 inside the segment spec and made absolute in
the expansion loop. A refactor that introduces a `card()` helper returns the authored
values and the expansion loop copies them through unchanged. A card in a segment that
starts at 70.5s now fires at its relative 0.8s — during the title card.

**Why it survives review.** It is not a total failure. The first ~10 seconds look right, the
duration is right, the audio is in sync, and a reviewer scrubbing the middle finds "no
card" which reads as a deliberate sparse layout.

**Fix.** One assertion, in the generator, before it writes anything:

```python
for sid, c in out['content'].items():
    for cd in c.get('cards', []):
        assert 0 <= round(cd['t'] - c['start'], 3) <= round(c['dur'], 3), \
            f"{cd['id']} 不在 {sid} 段内（t={cd['t']} 段起={c['start']}）"
        if cd.get('out') is not None:
            assert cd['out'] >= cd['t'], f"{cd['id']} 的 out 早于 t —— 卡片永不出现"
```

**Rule.** *The relative→absolute conversion is the highest-value assertion in this skill.*
It is the one transformation whose failure is invisible in every other check, and the
`out`-before-`t` variant produces an element that silently never appears at all.

## The mix that passes every loudness check and still feels wrong

**Symptom.** "The music is 诡异 / weird / unsettling." Every measurement is in range: the
bed is 20dB under the voice, nothing clips, the sidechain works, the cue alignments are
right. Played back, it is genuinely unpleasant.

**Cause.** Loudness is not the only axis. The failure is *spectral placement*: a bed with
70%+ of its energy below 150Hz is a low drone under everything, and the ear reads that as
unease even at −29dB. It is not too loud, it is too low.

**Fix.** Measure the distribution before showing a render:

```
20-150      36%      ← target 30–40; above 55% is the uncanny band
150-400     59%
400-1.2k     8%
1.2-3k      0.1%    ← deliberately empty: this is where the voice lives
3-8k        0%
```

Two more numbers travel with it: **crest factor** (`peak − RMS`, target 12–18dB; under 9dB
means the saturator has crushed every peak to the same loudness and the mix will feel flat
and lifeless) and **clip count** (must be 0).

**Compounding case.** Raising the bed because it "sits too far back" pushes the saturator
into compression and eats exactly the dynamics the user asked for. Re-check the crest
factor after every gain change, not just the loudness.

## The face-cam that hides the thing it is supposed to accompany

**Symptom.** "The avatar is covering the screen recording." The face-cam is in the right
place by the spec — short side ≈ ¼, bottom-right — and it still covers the demo.

**Causes, in order:**

1. **The card was sized before the slot moved.** The layout table was written for one
   face-cam position and the slot was later pushed down to free the middle for bigger
   cards. Cards keep their old bottom edge and now cross the new slot boundary. This
   happens every time either number changes.
2. **Height typed instead of derived.** A card's `h` came from a remembered number rather
   than `w / measured_aspect`, so it is taller than intended by 40px and crosses the line.
3. **The slot is reserved but not enforced.** "Keep the layout clear of it" was a note in
   the direction doc, never turned into a check.

**Fix.** A single hard number that both sides agree on, plus one automated check per
collision type. On 1080×1920 with a 300px circle at bottom-right: slot occupies y
1512–1812, cards get a hard bottom edge at 1460, progress bar moves to the very bottom
edge (ticks 1876 / bar 1894) — moving the persistent chrome out is what buys the room the
bigger cards need.

**Rule.** *A reserved slot is a coordinate, not an intention.* Three separate checks —
text vs slot, slot vs cards, text vs cards — and text measured with a `Range` so the
full-width element boxes stop drowning the report in false positives. One check catches one
of the three failures and leaves the other two invisible.

## The click that got louder the moment you de-clicked it

**Symptom.** SFX were rebuilt to stop competing with the voice, and now a single 85ms tick
measures a 3.1kHz spectral centroid — up from 520Hz. It sits exactly where you were trying
to keep the mix empty.

**Cause.** A few milliseconds of broadband noise added to the attack. White noise carries
most of its energy above 3kHz, and on an 85ms sound the attack *is* the spectrum — a 3ms
noise burst dominates the centroid even at low level.

**Fix.** Keep the air, lose the bandwidth: put the noise in the first 6–8ms, ramp it to
zero, and lowpass the result. Better still, make the tick tonal — a `pluck` (fundamental
plus 2nd/3rd/5th harmonics) reads as a physical object landing where a sine pip reads as a
computer beep.

**Rule.** *Spectral centroid is a design constraint for short SFX, not a diagnostic.* Any
sound under ~200ms needs a centroid target stated up front, because its spectrum is
whatever its attack is.

## A cut that barely cut anything

**Symptom.** The tightened voiceover came back at 96% of the raw length, and the dead air
is still there. The gate reported success.

**Cause.** The silent-centring formula. `cut = (a + (d−TARGET)/2, b − (d−TARGET)/2)` has
length `TARGET`, so it removes 0.40s from *every* long gap regardless of how long that gap
was — a 2.75s pause becomes 2.35s and still reads as a pause. The cut list is correct; the
arithmetic subtracted the wrong quantity.

**Fix.** Trim the boundary, do not centre it:

```
remove (d − TARGET) seconds   →   cut = (silence_start + PAD, silence_end − (TARGET − PAD))
```

**Rule.** *Assert the recovery rate, not the cut count.* Budget 20–25% of the raw take; a
result within 5% of the raw length means the gate did not run, regardless of how many
entries it wrote.

## The check that cannot fail

**Symptom.** Three overlap checks report green for two rounds. Then a reviewer points at
1:09 where a chip is sitting on top of a note — and re-running the checker on a composition
rebuilt with the bug still in it says **"无遮挡：60 个采样时刻，三项检查全部干净"**.

**Cause.** The three pairs were text/face-cam, face-cam/cards, text/cards. Every one is
*cross*-category. A note on top of a list item is text/text and touches neither the
face-cam nor a card, so no subset of the three can ever see it. The checker was not
broken; it was complete for the failures it was written against.

**Why it survived so long.** Every one of the three had fired at least once on a real bug
during this project, so each one had a receipt and looked trustworthy. Coverage-by-
regression is not coverage.

**Fix.** Enumerate the categories, not the instances:

| | face-cam | card | text |
|---|---|---|---|
| **face-cam** | — | check 2 | check 1 |
| **card** | | — | check 3 |
| **text** | | | **check 4** |

One missing cell in a 3×3 grid, and the three that existed gave no hint it was missing.
`scripts/check_occlusion.mjs` now runs all four.

**Rule.** *A checker is a claim about the space, not a pile of bug reports.* Ask "what
classes of failure could this possibly miss?" and answer with a grid, then prove each
detector by injecting its failure:

```python
tl['content']['P11']['quote']['top'] = 1560      # text / face-cam
tl['content']['P6']['cards'][0]['top']  = 1200    # face-cam / card
tl['content']['P2']['note']['top']      = 1000    # text / card
tl['content']['P7']['note']['top']      = 1300    # text / text
```

## The derived number that is wrong in a way a typed number cannot be

**Symptom.** Every element's time is computed from the transcript instead of typed. A chip
appears a beat before its segment starts, in the previous segment's layout, and the
segment still has all of its content. Nothing errors.

**Cause.** A `lead` offset used to place a second element relative to a phrase that sits
early in its segment. `phrase_time − lead` went negative relative to the segment. This is
the *reward* for removing 38 hand-typed numbers — and it is strictly harder to see, because
a computed `-0.46` looks like a real answer from a real script, while a typed `0.8` that
should have been `70.8` is obviously wrong in a diff.

**Fix.** Assert in the same script that derives:

```python
rel = round(cd['t'] - c['start'], 3)
assert 0 <= rel <= c['dur'], f"{cd['id']} 相对时间 {rel} 越出段 [{c['start']}, {c['end']}]"
```

**Rule.** *Every hand-typed magic number you remove must be replaced by an assertion, not
just by a formula.* Derivation moves your errors somewhere quieter; it does not remove
them. And keep `lead` scoped to the phrase — if it has to be large enough to cross a
segment boundary, the anchor is wrong.

## The false positive that gets answered with a bigger threshold

**Symptom.** A newly added overlap check reports a 42px collision on a composition that has
already shipped. The frame shows ~14px of clearance.

**Cause.** `Range.getBoundingClientRect()` returns *line boxes*. Every line of a multi-line
element carries `(line-height − font-size) / 2` of half-leading that no glyph reaches, and a
two-line headline has one above and one below.

**Fix.** Subtract it before comparing:

```js
const lh = cs.lineHeight === 'normal' ? fs * 1.2 : (parseFloat(cs.lineHeight) || fs);
const halfLead = Math.max(0, (lh - fs) / 2);
```

**Rule.** *When a check fires on something you believe is fine, the first move is to look at
the pixels — not to raise the threshold.* Raising it is how a check becomes permanently
green, and you will not notice the day it stops catching the real thing. This one was both
wrong about the magnitude and right that something was there: 14px under a 104px headline
is a spacing bug whatever the measurement said.

## The render with no voice in it

**Symptom.** A full-length render — 2m23s, 40MB, every static check green, every overlap
check green, duration matching the timeline to the frame. And the person in the circular
avatar is moving their mouth with nothing coming out.

**Cause.** The composition names one fixed audio path:

```html
<audio id="master" src="assets/master_bgm.wav" data-start="0" …>
```

The project also produces a voice master. The workflow was: copy the voice master over
`master_bgm.wav`, render, copy the bed back. One round, the copy-back did not happen, and
the next render shipped the bed alone.

**Why nothing caught it.** Duration, resolution, frame count, the static audit, the four
overlap checks, and the mouth-vs-envelope check are all **blind to which file the `<audio>`
element points at.** The picture was perfect. The narration was missing. Every one of those
checks returned pass on a film with no voice in it.

**Fix, prevention.** Make the track a build parameter so the choice is in the command that
ran, and print the resolved name in the build log:

```js
const MASTER = process.argv[2] === 'bgm' ? 'master_bgm.wav' : 'master_voice.wav';
// index.html 已生成 · 总长 113.8s · 母带 master_voice.wav
```

**Fix, detection.** Integrated loudness separates the two masters by ~6 LU and costs one
command:

| rendered | LUFS |
|---|---|
| voice master | −16 … −20 |
| bed-only master | −23 … −25 |

`scripts/verify_render.sh <file> voice` turns that into a gate. It has been run against the
actual incident file and reports `FAIL … 响度 -24.6 LUFS 不在 'voice' 母带区间` while every
other number on that line reads normal.

**Rule.** *When a render can differ by a file, not just by numbers, one of your checks has
to interrogate the file.* Ask what two finished films could differ in, and find the signal
that tells them apart. Duration cannot; loudness can.

## "Duration matches, so the render is fine"

**Symptom.** The natural next thought after a verification gap, and it is a bad one. Three
concrete failures this project shipped or nearly shipped that matched duration exactly:

- bed-only master in a voice cut (above),
- half the screen-recording cards firing at 0.8s instead of 68s — the runtime is unchanged,
  the *content* is wrong,
- a `note` sitting on top of a list item at 1:09.

None of them touches the duration.

**Fix.** The minimum bar is four numbers, not one:

```bash
scripts/verify_render.sh renders/episode.mp4 voice --expect-total 113.3
```

duration · resolution · frame count · **integrated loudness band**. And separately, the two
content gates that duration cannot stand in for: `assert_timeline.py` for *when* things
appear, `check_occlusion.mjs` for *where* they sit.

## The expensive way to learn the same things

Recorded honestly, because the cost is the point:

- **Four full renders at ~3 minutes each — 12 minutes spent checking layout that a snapshot would have shown in seconds.** The right order is: timeline → generate → snapshot every segment → fix → **one** render.
- **Three font stack substitutions and six control renders** to solve a bug that was not about fonts.
- **A backgrounded render that hung for ~20 minutes** before being recognised as suspended.
- **Two rounds of re-surveying screen-recording slices** because the first survey was at 2.2s granularity and kept landing on page transitions.
- **A debugging detour that blamed fonts for four rounds** while the real cause was two dozen identical headers stacked on one spot, left there by a tween scheduled at `NaN`. One clone-in-the-page experiment would have named it; three font substitutions and six control renders did not.
- **Building the QA probe while debugging with it.** The same session that fixed the composition also rewrote the tool four times, because there was no tool — only a throwaway script each round. Write the probe once, before the first visual bug, not during it.

The pattern underneath all four: *verify the cheap way, first, and believe the artifact over the mental model.*
