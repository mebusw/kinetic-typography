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

## The expensive way to learn the same things

Recorded honestly, because the cost is the point:

- **Four full renders at ~3 minutes each — 12 minutes spent checking layout that a snapshot would have shown in seconds.** The right order is: timeline → generate → snapshot every segment → fix → **one** render.
- **Three font stack substitutions and six control renders** to solve a bug that was not about fonts.
- **A backgrounded render that hung for ~20 minutes** before being recognised as suspended.
- **Two rounds of re-surveying screen-recording slices** because the first survey was at 2.2s granularity and kept landing on page transitions.
- **A debugging detour that blamed fonts for four rounds** while the real cause was two dozen identical headers stacked on one spot, left there by a tween scheduled at `NaN`. One clone-in-the-page experiment would have named it; three font substitutions and six control renders did not.
- **Building the QA probe while debugging with it.** The same session that fixed the composition also rewrote the tool four times, because there was no tool — only a throwaway script each round. Write the probe once, before the first visual bug, not during it.

The pattern underneath all four: *verify the cheap way, first, and believe the artifact over the mental model.*
