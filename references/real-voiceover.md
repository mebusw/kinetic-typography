# Real voiceover: the human-voice edition

The pipeline in `pipeline.md` is built around a synthesized reference VO. That is the
right default for a first cut. It stops being the right default the moment a real
recording exists, and the whole timing basis has to move — not just the audio file.

This is what changes, in the order that changes.

---

## 1. The human recording is the score

A TTS reference VO is a stopwatch: its durations are synthetic, its pauses are uniform,
and its phrasing follows the punctuation you wrote. A real recording has none of that. It
has breaths, false starts, and sentences that run 30% long or short depending on how
excited the speaker was.

**Transcribe it, then throw the timings away and re-derive them.** Do not scale the old
timeline. Scale the timeline and every element drifts a little further from its own words
until nothing lines up.

```bash
# 1. pull the audio, transcribe with word timestamps
ffmpeg -v error -y -i speaker.mp4 -vn -ac 1 -ar 16000 vo.wav
python3 -c "
from faster_whisper import WhisperModel
import json
m = WhisperModel('medium', device='cpu', compute_type='int8')
segs, _ = m.transcribe('vo.wav', language='zh', vad_filter=True, word_timestamps=True)
out=[{'start':round(s.start,3),'end':round(s.end,3),'text':s.text.strip()} for s in segs]
json.dump(out, open('vo_segments.json','w'), ensure_ascii=False, indent=1)
"
```

**Model note:** `faster-whisper` needs a proxy workaround on a SOCKS-only machine. Point
it at the local snapshot rather than letting it resolve through the network:

```python
# bypass the download entirely
m = WhisperModel('/path/to/snapshots/<hash>', device='cpu', compute_type='int8')
# or fetch once with the proxy vars cleared:
# NO_PROXY='*' http_proxy= https_proxy= python3 -c "snapshot_download('Systran/faster-whisper-medium')"
```

---

## 2. Tighten the recording before you time anything

A raw take is 20–25% longer than it needs to be, and the dead air is uneven: some gaps are
0.3s, some are 2.8s. Cutting nothing means every element inherits that unevenness.

**Cut in the silence only, and only where the silence is long.**

```bash
ffmpeg -v info -i vo.wav -af "silencedetect=noise=-38dB:d=0.30" -f null - 2>&1 \
  | grep -E "silence_(start|end)"
```

Then, for each gap longer than the target:

```
gap d  →  keep TARGET seconds, remove (d − TARGET) seconds
cut = (silence_start + PAD, silence_end − (TARGET − PAD))
```

Two numbers decide whether the cut is safe:

- **`PAD` ≈ 0.18s** — how far the blade stays clear of the last/first phoneme. Cutting to
  the exact detected boundary clips consonants, and a clipped consonant is the one artefact
  a viewer will hear even if they cannot say what it is.
- **`TARGET` ≈ 0.40s** — the pause you leave. Do not compress everything to zero: a short
  breath is what makes a person sound like a person. Compress only what is long.

**The off-by-one that costs you a day:** the obvious formula
`cut = (a + (d−TARGET)/2, b − (d−TARGET)/2)` removes `TARGET` seconds, not `d − TARGET`.
Symmetric centring is wrong here because you are trimming a boundary, not centring.
Cut from the front of the gap, keep the tail.

Apply the same table to audio and video in one `filter_complex`, or the lips drift:

```python
for i, (a, b) in enumerate(keep):
    fc.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,fps=25[v{i}]")
    fc.append(f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
# concat wants the pads INTERLEAVED: [v0][a0][v1][a1]…  — not all video then all audio
fc.append(''.join(f'[v{i}][a{i}]' for i in range(len(keep)))
          + f"concat=n={len(keep)}:v=1:a=1[v][a]")
```

**Re-transcribe after cutting.** This is not optional. The cut changes every downstream
timestamp, and the transcription is what the next stage reads. On one cut the segment
`你看内容不需要推导重来` became two segments `你看` + `内容不需要推导重来`, which broke an
anchor that had matched fine a minute earlier.

---

## 3. Anchors are phrases, not sentences

Whisper's segmentation shifts when you re-run it, and it merges or splits at arbitrary
points. An anchor that is a whole sentence stops matching the moment one clause moves.

**Anchor on a distinctive fragment and keep a fuzzy fallback:**

```python
def find(key):
    for i, s in enumerate(segs):
        if key in s['text']: return i, s
    k = key[:6]                      # 前 6 个字模糊匹配
    for i, s in enumerate(segs):
        if k in s['text']: return i, s
    raise KeyError(key)
```

Anchor on content words, not function words. `字体字号` survives; `位置对齐上面` will
eventually lose its `上面` to a retake.

**Expect the ASR to be wrong about near-homophone words.** In one take 适合做对比图 came
back as 合作对比图 twice, and 标题大小也不统一 came back as 标题大小也不同意. When an anchor
fails to match, print the surrounding window and read it before assuming the cut is wrong.

---

## 4. Derive every element time from the transcript, never by hand

Hand-entering 38 offsets works until the recording changes once, and then all 38 are
wrong and nothing looks wrong enough to catch. **Compute them:**

```python
def at_time(key, after=0.0):
    for s in segs:
        if s['start'] >= after - 0.01 and key in s['text']:
            return s['start']
    raise KeyError(key)

def rel(pid, key, after=0.0, lead=0.0):
    """段内相对时间 = 发声时刻 − 段起点 − lead"""
    return round(at_time(key, after) - beats[pid]['start'] - lead, 3)
```

Keep the substitution table in a file next to the generator. When the recording changes
you re-run one script instead of re-reading forty numbers.

**`lead` is the taste dial.** A chip that appears on exactly the first phoneme of its word
feels reactive; 0.2–0.5s early feels like the deck is anticipating the speaker. Both are
defensible — pick one and apply it everywhere, because mixed values read as sloppiness.

### Deriving the times replaces one class of error with a quieter one

Replacing 38 hand-entered offsets with computed ones is strictly better, and it failed
anyway — one line in, because `lead=1.9` subtracted from a phrase that sat 1.44s into its
segment pushed the element to **-0.46s, before the segment existed**:

```
更干净    rel  1.44  abs 92.78
更专业    rel -0.46  abs 90.88     ← 段首是 91.34
```

Nobody typing 38 numbers gets this wrong, and nobody eyeballing a contact sheet sees it
either, because the element still appears — a beat early, in the previous segment, where
the layout it belongs to does not exist yet.

**Arithmetic errors are quieter than transcription errors.** A typed `0.8` that should have
been `70.8` is obviously wrong in a diff. A computed `-0.46` looks like a real answer
produced by a real script. **The more of the timeline you derive, the more the assertion
gate — not review — becomes the only thing between you and a plausible wrong video.**

Two habits that fall out of this:

- **Clamp `lead` to the phrase, not the segment.** A `lead` positions an element *within*
  the phrase it belongs to. If it has to be large enough to cross a segment boundary, the
  anchor is wrong, not the lead.
- **Assert the derived value in the same script that derives it.** `assert_timeline.py`
  caught this on its first run, against a timeline that was otherwise correct. A derivation
  script that writes without asserting has only moved the typo somewhere quieter.

---

## 5. Cards live in absolute time; everything else is relative

The single bug that costs a full re-render:

```python
def card(cid, src, w, top, media, t, dur, rot, out=None):
    return {..., 't': t, 'out': out}      # ← 段内相对时间

# ...later, in the expansion loop:
for cd in src['cards']:
    e = dict(cd)
    e['t']   = round(t0 + cd['t'], 3)      # ← 绝对化在这里做
    e['out'] = None if cd['out'] is None else round(t0 + cd['out'], 3)
```

If the absolute conversion is missing, a card in a segment that starts at 70.5s fires at
**0.8s** — during the title. The film still renders, plays, and looks plausible in a
contact sheet, because the first segment does have cards. Half the runtime is wrong.

**Assert it, always.** This catches the whole family in one line:

```python
for sid, c in tl['content'].items():
    for cd in c.get('cards', []):
        rel = cd['t'] - c['start']
        assert 0 <= rel <= c['dur'], f"{cd['id']} 不在 {sid} 段内"
```

The same relative/absolute split applies to `lead`, `sub`, `note`, every list item, and
`out`. A card's `out` is the one most often forgotten — an un-absolutised `out` ends up
before its own `t`, and the card never appears at all.

---

## 6. Two consecutive takes: cut the restart, keep the sentence

A speaker who starts a phrase, notices, and restarts it leaves this behind:

```
… 标题大小也不统一 │ 字行间 │ 行间距字间距也不统一 │ 图标也不像 │ 图标也像从不同的模板里面 拼凑出来的
```

Both `字行间` and `图标也不像` are dead air in the middle of a sentence. Cut them like any
other long pause — the silencedetect run already found the boundaries:

```
字行间      speech 51.405–52.299  →  cut [51.00, 52.50]
图标也不像  speech 54.788–55.648  →  cut [54.60, 56.00]
```

**This is a judgement call the machine cannot make** — which restart is a slip and which is
a rhetorical beat. Ask the speaker, or read the sentence aloud. Cutting a deliberate pause
that the speaker meant reads as a jump-cut error, which is worse than leaving the slip in.

Cutting a slip also **renumbers every timestamp after it**, so it belongs in the same pass
as the pause tightening, not after the timeline is built.

---

## 7. Budget: what a 2-minute talking-head piece actually costs

A measured rehearsal, for calibration:

| stage | before | after |
|---|---|---|
| raw take | 137.7s | — |
| pause tightening | | 114.7s |
| slip removal | | 111.8s |
| longest inter-segment gap | 2.81s | 0.72s |

Budget **20–25%** of the raw take for tightening. If your cut came back within 5% of the
raw length, the gate did not run.

---

## 8. Check the mouth, not the file

Audio and video are trimmed by one table, but the renderer can still drift if the two
streams were ever cut separately. One check, after the first render:

```bash
# 口播能量包络：每 10s 一格，段落切换处应该跟着内容起伏而不是一路平线
ffmpeg -v error -y -i final.mp4 -vn -ac 1 -ar 8000 /tmp/a.wav && python3 -c "
import wave, numpy as np
w = wave.open('/tmp/a.wav'); sr = w.getframerate(); n = w.getnframes()
d = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)/32768
win = sr*10
for i in range(len(d)//win):
    r = 20*np.log10(np.sqrt((d[i*win:(i+1)*win]**2).mean())+1e-9)
    print(f'{i*10:4d}s {r:6.1f} ' + '#'*max(0,int(r+40)))
"
```

Flat energy across the whole film means the voice is missing or buried. Visible envelope
swings means the voice is present and the music is not swamping it.

---

## 9. Ship one cut, not two

The two-cut rule (clean master + reference-VO cut) exists because a synthesized VO is a
disposable stand-in. Once the real face and real voice are baked in, **the reference cut no
longer exists** — you cannot swap the audio without also swapping the picture, because the
picture is the person who was speaking.

Ship one file. The `…-v1-参考口播版` name in a folder of real-voice episodes is a leftover
convention from the TTS era, and keeping it invites someone to publish the wrong one.

---

## 10. 锚点短语：先批量预检，再写分镜

段与元素的时间都从转录文本里的**短语锚点**解出来。真正吃掉时间的是"锚点找不到"——
`derive` 在第 7 个元素上抛一次错，你就得改一次 JSON 重跑一遍。做法前置：

```bash
python anchor_check.py <epdir> "拖框对齐调配色" "整个客户就觉得你不专业" "评论区再打"
# ✓ 10.38 拖框对齐调配色
# ✗ 找不到  半小时磨一页
```

一次把一集所有候选锚点丢进去，全绿了再写 `spec.json`。六集 130 多个锚点，预检把
返工从"每集 2–3 轮"压到"每集 0–1 轮"。

**ASR 会写错字，而且错得很有规律。** 实测错法：正门/正完、一夜/一页、反共/返工、
地产桌/地产出、元期率/不良率、换能篇/幻灯片、眼近/演进、不对乎/不对付。
规律是：**数字、专有名词、行业词最容易错；周围的动词副词几乎不错。**
所以锚点要选错字周围的词，不要选错字本身——`"画成2x2矩阵"` 稳，
`"2x2"` 不稳；`"评论区再打"` 稳，`"关系图"` 要看运气。

**匹配前必须剥掉所有标点。** 词级时间戳的逗号句号位置在重转录之后会漂，
带着标点匹配必然在第二次转录后失效。只留中日韩字与字母数字再做串接匹配。

## 11. lead 越界是锚点选错了的信号，不是参数没调好

元素时间 = 锚点时刻 − 段起点 − lead。出现一排
`lead 越界 rel=-0.10 → 收到 0`，意思是你把这集的**每个标题都锚在了本段的第一句话上**，
于是它们全都被夹到 0、整段元素齐刷刷一起进场。

不要去调 lead。换锚点：标题锚在本段**后半句**，让它晚 0.3–0.8s 进场，
字幕锚在本段第一句（本来就该 0）。一集 20 条越界告警 → 换锚点后 3 条以内。

顺带一条：**如果某段短于 ~2.5s，它装不下"标题 + 卡片"**。
实测一个 1.40s 的段（锚点撞上了讲话人更早说过的同一句话）只能并进邻段，
硬留的话卡片会越出段尾、标题会和卡片同帧打架。

## 12. 收紧率的真实区间

原片 → 收紧后实测：−19.4% / −12.7% / −12.9% / −12.4% / −8.6% / −11.6%。
SKILL 里的"预算 20–25%"是**上限**，不是目标：讲话人本来就快、素材本来就紧的时候，
8–12% 是对的。**别为了凑数字多剪**——把字与字之间压到 0.40s 以下，
听着就像抢拍。反过来，如果收紧率低于 8%，先去查 `silencedetect` 的噪声门
（`-38dB:d=0.30` 对有空调声的房间会漏检），别直接交。

## 13. 改稿：先剪语音，再改分镜，最后重打一遍锚点

客户回来说"这句话连语音一起去掉"时，**顺序反了会白干**：先改分镜 → 改完发现语音还在 →
再剪语音 → 时间轴全变 → 分镜坐标又全错。正确顺序：

1. **在 `asr_tight.json` 里定位**这句话的词级时间戳；
2. **剪 `tight.mp4`**（一次只剪一小段，不要回源片重跑整套收紧）；
3. **重新转录**（`transcribe.py --tag tight`）——剪过之后字与字的拼接会让 ASR 结果漂移，
   旧转录里的"正门"可能变成"正完"；
4. **全量重跑锚点预检**（`anchor_check.py`），改掉失效的锚点；
5. 最后才动 `spec.json` / `derive` / `build`。

**剪的粒度用"词"不用"句"。** 一句话里常常一半要留一半要删：
"想要的话评论区打 PPT 讲法**（留）**，私信发你完整的获取方式**（删）**"。
词级时间戳能精确到"私信"那个字的起点，`recut.py` 的 `{"w": "私信"}` 就是干这个的。
按整句删会把 CTA 关键词一起删掉。

## 14. 二次精剪的备份必须滚号

```python
# 错：第二次剪会退回第一次剪之前的素材，前面剪掉的内容全部复活
backup = "tight_v1.mp4"
if not os.path.exists(backup):
    shutil.copy(src, backup)

# 对：每次换一个名字
i = 1
while os.path.exists(f"tight_v{i}.mp4"): i += 1
backup = f"tight_v{i}.mp4"; shutil.copy(src, backup)
```

这个 bug 的**症状极具迷惑性**：它不报错，时长也基本对得上（因为 `total` 读的是当前文件，
而 ffmpeg 读的是备份），你只会发现"刚才明明删掉的那句话，又在 62 秒出现了"。
而此时原始文件已经被覆盖，只能从源片重跑一遍整套收紧。**凡是"读一个文件、写另一个文件"的
原地覆盖脚本，备份名一律滚号。**

