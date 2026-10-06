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

---

## 从六集真人口播里长出来的数

素材是 **Zoom 录的横屏**（16:9，人在画面偏左上）。做法：

```bash
# 先在源片里量出头的位置，再裁；别假设人物居中
crop=680:680:295:20, scale=640:640
```

裁成**正方形**之后再上 CSS `border-radius:50%` 圆形蒙版。反过来的顺序（先蒙版后裁）
会得到一张被拉伸的椭圆脸。

### 版位实测结论（1080×1920）

| 项 | 值 | 理由 |
|---|---|---|
| slot | bottom-right，`side 296`（短边 ≈ 15%） | 字幕带在左下，两侧不共用 |
| margin / marginBottom | 52 / 74 | `marginBottom 74` 比"看着合适"再低一档，头再往下靠，正好让开录屏演示区 |
| 卡片底边硬上限 | **y + h ≤ 1540** | 头像顶边 1550，留 10px |
| 字幕带 | `x 60, y 1436, w 656, size 44` | 与头像分居左右，几何上不可能相交 |
| 录屏卡片宽度 | 顶满 1016（`x 32`） | "让观众看清"这个要求靠**把卡片往上挪**（y 420–620）实现，不是靠缩窄 |

**字幕必须和头像分居两侧。** 字幕在左下 `x 60..716`、头像在右下 `x 732..1028`，
两者 x 区间不重叠，于是字幕可以合理地从"文字 vs 头像"检查里豁免；
同侧的话，这条豁免就是自欺欺人。换 slot 到左下时，把字幕带整体挪到右边，别偷懒。

### 检查器里的头像框必须现读 DOM

写一个 `{l:732,t:1552,r:1028,bo:1844}` 常量，第一次改 slot 或改尺寸就悄悄失配——
于是"文字压头像"这项永远绿，而画面已经糊了：

```js
const face = els.find(e => e.kind === 'face');
const FACE = face || { l: 732, t: 1552, r: 1028, bo: 1844 };  // 兜底，不是默认值
```

同理，`check_occlusion` 里那四个检查的**阈值**也要跟着量纲走：
文字 vs 头像 / 文字 vs 文字 用 250px²，文字 vs 卡片用 400px²（卡片是大色块，
压住一点点字是设计里允许的，压住几百像素才是事故）。

### 探针量不到 clip-path

`wipe` 这类"擦除"入场，元素在轮到它之前是 `opacity: 1` 只是被 `clip-path` 挡住的。
画面上完全看不见，但**任何几何探针都会读到一个满尺寸的盒子**，于是报出一堆
"这行字压住了那行字"的鬼影。

两条一起做：

1. 生成器里 `.at { opacity: 0 }` 打底，并且 **`from` 状态里永远不许出现 `opacity: 1`**
   （`wipe` 写成 `{clipPath:'inset(0% 100% 0% 0%)', opacity:0}`）。GSAP 的 `fromTo`
   会立刻渲染 from 值，这条不守，未上场的元素就是满不透明的。
2. 量字号要量**真正写字那一层**。`k-box` / `k-num` 的外层容器是 16px 默认值，
   量容器会把 40px 的正文报成 16px，然后你花半小时去找一个不存在的"字号太小"。
   取所有有文字的叶子节点里最小的那个字号。
3. 装饰件（标尺、竖轨、分层条、网格）也是 `.at` 包装，要按选择器白名单跳过，
   否则它们会以 16px 的身份刷满"字号过小"报告，把真问题淹掉。


---

## 补记（2026-10，六支真人露脸版实测）

- **圆心裁切**：Zoom 横屏 1280×720 的实录，`crop=640:640:320:0` 取正中正方形，
  头和领子都在里面，头顶留白约 80px。再紧就会削掉发际线。
- **头像槽位固定在右下**：`x = 706, y = 1512`，直径 320。所有录屏卡的下沿压到 ≤ 1440，
  于是"头像不挡演示"这件事在布局上就是成立的，不需要逐张卡去量。
- **描边两圈**：外圈强调色，内圈**底色**——浅底片子上这一圈必须是底色，
  否则头像周围出现一圈黑边。浅底同时要把 `mix-blend-mode` 从 `screen` 换成 `multiply`。
- **进度条要避开头像槽**：宽度按 `CW − 330` 收，否则一条线从头像中间穿过去。
- **头像和主口播必须来自同一条时间表**。头像单独剪一次，唇动就会和声音差半拍——
  这是观众一眼能看出"不对劲"、但没人说得清哪里不对的错误。
- **检查器读 opacity 的是元素自己**。`<div class="at"><div class="shell">` 这种包一层，
  `check_occlusion.mjs` 会把每一张卡都当成常驻可见。把 `.at` 和 `.shell` 放在同一个元素上。
