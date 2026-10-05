# The talking-head slot: layout, masking, and proving it is clear

`SKILL.md` says reserve the face-cam slot from the start. This is how, and what it costs
when the slot is treated as a suggestion instead of a constraint.

---

## Crop before you mask

A Zoom-style 16:9 recording has the face at some arbitrary horizontal offset, and the head
is rarely centred in the frame. Masking first gives you a circle centred on the *frame*,
not on the *head*.

**Probe one frame, find the head, then crop a square around it:**

```bash
ffmpeg -v error -y -ss 8 -i talk.mp4 -frames:v 1 -vf scale=1280:-1 face.png
```

For a 1280×720 Zoom take, a 640×640 crop at `x=320 y=8` frames head-and-collar well. Move
the crop a few frames along and confirm the head stays put — speakers shift, and a mask
that is right at 8s can be off at 90s.

**The bottom of the crop is what makes it read as "a person" rather than "a floating
face".** Stop above the chest: head plus a collar and the top of the shoulders is enough.
Anything lower turns into a webcam screenshot in a circle.

---

## Do not fight the encoder for alpha

The instinct is to bake the circle into the footage. Do not.

On a libvpx build without WebM alpha support, the alpha plane is accepted by the filter
graph (`alphamerge` produces a correct `yuva420p`, corner alpha 0 / centre 255) and then
**silently dropped by the encoder** — `ffprobe` reports `yuv420p` and the output is an
opaque square. The failure is invisible: the file is written, the size looks reasonable,
and you find out at render time.

**Mask in CSS instead.** A square 1:1 clip plus `border-radius:50%` on the wrapper is
crisper than any baked mask, costs nothing to re-tune, and has no codec dependency:

```css
.fcwrap { position:absolute; border-radius:50%; overflow:hidden;
  box-shadow: 0 18px 44px rgba(0,0,0,.55),
              0 0 0 3px rgba(237,234,228,.92),      /* 亮环：把圆形从背景里拎出来 */
              0 0 0 7px rgba(15,18,32,.85) }        /* 外圈：再压一道，和画面脱开 */
.fcwrap video { display:block; width:100%; height:100%; object-fit:cover }
```

Encode the clip as VP9/WebM at CRF ~31 (a 112s square face clip is ~8MB). Keep the
transform on the **wrapper**, never on the `<video>` (see `SKILL.md` non-negotiable 6).

---

## Where the slot goes, and what it costs

The platform UI eats the top ~120px and the bottom ~300px. A face-cam at the very bottom
therefore lands under the platform's own controls. So the slot has to sit inside the
content band, and everything else has to move.

A layout that holds up on 1080×1920:

| element | y |
|---|---|
| segment head | 132 |
| lead / headline | 280 |
| supporting line | 460–520 |
| list items | 560–1100 |
| **screen-recording cards** | 560–1460 |
| **face-cam circle** | **1512–1812** (⌀300, right 64, bottom 108) |
| ticks | 1876 |
| progress bar | 1894 |

Two decisions do most of the work:

- **The progress bar goes to the very bottom edge.** It is the one persistent element, and
  in the middle of the frame it splits the content band into two unusable halves. Moving it
  out is what buys the vertical room the bigger cards need.
- **Cards get a hard bottom edge at 1460**, i.e. 50px above the face-cam. Derive card
  height from the real aspect ratio, never from a remembered number:

```python
ASPECT = {'m_deck.mp4': 1080/630, 'm_story.mp4': 760/880, ...}   # measured, not guessed
h = round(w / ASPECT[src] / 2) * 2      # 偶数：避免 yuv420 色度半采样边界
```

A card that overhangs the slot is the failure users actually notice: they say the face-cam
is "covering the demo" and they are right, even though the interesting part of the card is
still visible.

---

## Four overlap checks, not three — and prove the fourth

There are **four** distinct collisions. A single "does the face-cam cover anything" check
catches one of them. Run all four over a dense sample of timestamps (5 per segment is
enough, 60 points for a 2-minute piece) in **one** `page.evaluate` per run — a CDP round
trip per seek is what makes a probe time out on a long composition.

| check | what it catches |
|---|---|
| text vs face-cam | unreadable copy |
| face-cam vs cards | the demo is hidden |
| text vs cards | both are unreadable; the card is evidence and must stay legible |
| **text vs text** | a note lands on the same line as a list item |

`scripts/check_occlusion.mjs` runs all four.

**Why the fourth is not an edge case.** A segment has a headline, a sub, a list and a note
— four elements in one column, and any two of them can land on each other. The first three
checks are all *cross*-category: each pairs a text element with either the face-cam or a
card. A note on top of the last list item involves neither, so **no subset of the first
three can ever see it.** In review, that collision was reported by a person while the
three-check harness had been reporting green — and once the fourth check existed it
immediately found a second one (a headline sitting 14px off the first chip) that the same
harness had also called clean.

**The lesson is not "add a check." It is that a green check is a claim you have to earn.**
A checker that has only ever run against a correct composition is an untested assertion.

**Prove each detector before trusting it.** Inject one fault of each type into a throwaway
timeline and confirm all four go red:

```python
tl['content']['P11']['quote']['top'] = 1560      # text / face-cam
tl['content']['P6']['cards'][0]['top']  = 1200    # face-cam / card
tl['content']['P2']['note']['top']      = 1000    # text / card
tl['content']['P7']['note']['top']      = 1300    # text / text
```

### Calibrate the text/text check against line boxes, not ink

The first run of the fourth check reported a 42px overlap between a two-line 104px headline
and the chip below it. Opening the frame showed ~14px of actual clearance. The extra 28px
was **half-leading**: `Range.getBoundingClientRect()` returns *line boxes*, and every line
of a multi-line element carries `(line-height − font-size) / 2` of space no glyph ink
reaches.

```js
const cs = getComputedStyle(el);
const fs = parseFloat(cs.fontSize) || 0;
const lh = cs.lineHeight === 'normal' ? fs * 1.2 : (parseFloat(cs.lineHeight) || fs);
const halfLead = Math.max(0, (lh - fs) / 2);
b = { ...b, top: b.top + halfLead, bottom: b.bottom - halfLead };
```

**Do not answer a false positive by loosening the threshold.** 42px → threshold 45px is how
a check becomes permanently green. Fix the measurement, then look at the pixels: the
number was wrong about *how much* and right that *something* was there — 14px of clearance
on a 104px headline is a spacing problem whatever the number said.

Measure text with a `Range`, not the element box. List items and notes are full-width
divs, so their boxes are 900px wide while the glyphs occupy 300px — box-based checking
produces a wall of false positives and gets ignored, which is worse than not checking.

```js
const rng = document.createRange();
rng.selectNodeContents(el);
const rb = rng.getBoundingClientRect();      // 真实字形范围
```

**Cards are not checked against text in the "is this broken" sense** — a card is allowed to
sit under the face-cam *only* if the region it covers is visually empty. Judge that by eye
on the finished render; a font dropdown with its list on the left is fine under a circle on
the right, a before/after comparison is not.

---

## Sampling discipline

A snapshot at a segment's start lands in the gap before anything animates in and reads as
a layout bug that is not there. Sample at 70–90% of each segment.

**And sample more than once per segment when a segment has two beats in one layout.**
In a measured case, four list rows in one segment were declared on screen simultaneously
because all four inherited the segment's exit — the overlap report was correct even though
the picture looked fine, because the rows were staggered in time. That is the same
stranded-element class as `SKILL.md` non-negotiable 5, arriving through the timeline rather
than through the stylesheet: **a group of elements that exit together must each carry their
own in-time, and their exits must all be after their own in-times, not after the segment's.**
