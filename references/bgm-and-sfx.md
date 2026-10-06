# BGM and SFX: synthesizing the bed

`audio.md` covers levels, ducking, and cue alignment. It assumes the bed came from a
catalog. When no catalog track has the right shape — or when the brief says the music must
be original — the bed is another synthesis job, with the same trap as everything else here:
**it can be wrong in a way that produces no error at all.**

The failure mode is not "it sounds bad", it is "it sounds *fine* and wrong". A bed that is
20dB under the voice is technically correct and still makes the film feel strange. Measure.

---

## The three measurements that catch it

Run these before showing anyone a render. Each one has caught a real bad mix.

**1. Spectral balance.** Not "does it sound muddy" — where the energy actually is.

```bash
ffmpeg -v error -y -i bgm.wav -ac 1 -ar 16000 -f wav /tmp/b.wav && python3 -c "
import wave, numpy as np
w = wave.open('/tmp/b.wav'); sr = w.getframerate(); n = w.getnframes()
d = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)/32768
S = np.abs(np.fft.rfft(d*np.hanning(len(d)))); f = np.fft.rfftfreq(len(d), 1/sr)
print('centroid %.0f Hz' % ((S*f).sum()/S.sum()))
tot = (S**2).sum()
for lo,hi,name in [(20,150,'20-150'),(150,400,'150-400'),(400,1200,'400-1.2k'),
                   (1200,3000,'1.2-3k'),(3000,8000,'3-8k')]:
    m=(f>=lo)&(f<hi); print(f'  {name:10s} {100*(S[m]**2).sum()/tot:5.1f}%')
"
```

For a spoken bed, **>55% of energy below 150Hz is the "诡异" band.** It is not loud, it is
not clipping — it is a low drone under everything that the ear reads as unease. Target
roughly: 35% sub, 55% low-mid, 8% mid, **and deliberately near-zero from 1.2k up**, because
that is where the voice lives and the bed has no business there.

**2. Crest factor.** Printed by the synthesizer, and the only number that tells you whether
the saturator ate your dynamics.

```
crest = peak_dBFS − rms_dBFS
12–18 dB   healthy
< 9 dB     crushed into a square wave — everything is now the same loudness forever
```

Getting this wrong is easy: `tanh(x * (1.15/peak))` is a *soft* clipper only while the
drive is low. If the raw mix peaks at +20dB, `1.15/peak` is a big number and you are
slamming the whole signal into the rail. Use `ref = raw_peak * 1.9` so the tanh only
touches the top of the peaks.

**3. Clipping count.** `int((np.abs(d) > 0.999).sum())` must be 0.

---

## Building the bed for a film with a voice

A no-VO personal intro is not the same problem as a talking-head explainer. In the intro
the drums are the subject. In the explainer someone is talking for two minutes and the bed
has one job: be felt, not heard.

| | No-VO intro | Spoken explainer |
|---|---|---|
| kick | every beat, structural | one soft heartbeat per ~1.2s, 0.12 gain |
| snare / hats | carry the groove | **delete them** — they fight the voice's midrange |
| bass | moving eighth-note line | long root note per segment, ×2 so it sits above the mud |
| pad | wide, bright | lowpassed to 1.6–2.4kHz |
| arp | decoration | the main melodic interest, and therefore the thing you tune |
| section changes | drum fill | one `impact` on the segment boundary |

**The relationship to the screen is structural, not decorative.** Every segment boundary
gets a chord change and a landing accent. A bed with no landmarks under a video with hard
cuts sounds like two unrelated things playing at once.

---

## Timbre: why a "thud" feels like a knock

A dull low impact is almost always the same mistake:

```python
# ✗ sounds like someone knocking on a door
def thud(dur=.42, f0=150, f1=64):
    ph = 2*np.pi*(f0*t + (f1-f0)/dur*t**2/2)
    s = np.sin(ph) + 0.30*np.sin(ph*1.5) + 0.10*np.sin(ph*2.0)
    return lowpass(s * env, 900)          # 1.5x harmonic + a 900Hz ceiling
```

Two sins. The harmonic content stops at 300Hz, so there is no air and no transient — the
ear has nothing to latch onto and files it as "knock". And the lowpass at 900Hz is applied
to a signal whose fundamental is already 150Hz, which just makes it smaller and muddier.

A cinematic landing hit is the same pitch sweep **plus a noise body and a much steeper
bend**:

```python
def impact(sub_dur=1.1, f0=180, f1=32, boom_tau=0.42):
    sub  = sweep_sine(sub_dur, f0, f1, bend=0.10) * 1.15   # bend 0.10 = near-instant drop
    n    = int(sub_dur*SR)
    boom = lowpass(rng.standard_normal(n), 1100) * np.exp(-np.arange(n)/SR/boom_tau)
    return sub + boom * 0.55                               # 55% noise, 45% sub
```

`bend` is the whole trick. `bend=0.35` slides down over a third of the tail and sounds like
a slide whistle; `bend=0.10` collapses almost immediately and reads as weight. Then the
noise body gives the ear something broadband to place the hit in space. Add a short reverb
(`decay=1.1, mix=0.14`) and it sits in a room instead of on top of the mix.

Three lengths cover almost every editorial need: 0.62s for a segment head, 0.95s for a
beat, 1.45s for the conclusion.

**The same argument applies to the rest of the palette:**

- **Ticks should be plucks, not sine pips.** A pure sine click has no harmonic structure
  and reads as a computer beep. A short pluck — fundamental plus 2nd/3rd/5th harmonics,
  4ms attack, exponential decay — reads as a physical object landing.
- **Keep clicks out of the broadband noise band.** A 3ms white-noise burst on a 85ms tick
  pulled that tick's spectral centroid from 520Hz to 3100Hz and put it right back into the
  range where it competes with speech. If you want air, put it in the first 8ms at low
  level, and lowpass the result.
- **Bells want inharmonic partials.** 2.76× / 5.40× / 8.93× rather than 2/3/4 — that is
  what makes it read as struck metal instead of a synth pad.

---

## Mixing a synthesized bed under a real voice

The bed is mastered at a deliberately low ceiling (`peak_db=-3`) because it still has to be
mixed. The voice-keyed sidechain from `audio.md` does the rest.

A working split on a spoken piece:

| track | level | sidechained? |
|---|---|---|
| real voice | −16.5 dBFS | — |
| music bed | −26 to −29 dBFS | **yes**, −7 to −7.5 dB |
| SFX | −25 to −27 dBFS | **no** |

The SFX exclusion is the part people get wrong. A sidechain keyed to the voice ducks
everything above the threshold, and a transient click has all its energy in the first 30ms
— which is exactly where the gain reduction is largest. The accents disappear. Key the
duck to the music bus only.

**Raise the bed when asked, carefully.** "The arpeggio and accents feel too far back" is a
gains request, not a rewrite: +2 to +4dB on the arp bus, +20% on the landing gains, and
raise the bed 1.5–2dB. Check the crest factor afterwards — a louder bed often means the
saturator is now compressing, and the dynamics you just added are the first thing to go.

---

## Reusing a proven synth

When the brief points at an existing generator that is known to work — a personal-intro
BGM, a title sting, a client's brand bed — **lift the synth core, not the arrangement.**

The instruments and the utilities are reusable as-is: the noise shapes, the envelope
helpers, the `pad`/`pluck`/`bell`/`sub_note` constructions, the FFT lowpass and convolution
helpers, the sidechain, the saturator. The **arrangement** is what has to be rewritten,
because it encodes what the music is for.

Two edits make the difference between "a BGM" and "this film's BGM":

1. Strip the drum role down to a heartbeat (see the table above).
2. Drive the chord progression and the landing accents from the segment list, not from a
   fixed grid. Read the beat boundaries from the same JSON the timeline uses, so a
   re-timed recording re-times the music with it.

---

## 频谱是配出来的，不是 EQ 出来的

六集全部用 numpy 合成，跑完 `measure()` 看三个数。**踩到的三个坑，全都不是"音量"问题：**

### 坑 1：和弦按根音算，pad 会整坨掉进 150Hz 以下

`root = A2 (110Hz)`，三和弦级数 0/2/4 → 110 / 123 / 139 Hz，**全部低于 150Hz**。
量出来 pad 是 `20-150Hz 96.0%` —— 远超 55% 的"发闷阈值"，听着像胸腔共鸣在打架。

修法不是加 EQ，是**把 pad 抬八度**：

```python
freqs = [root*2 * 2**(s/12) for s in ch] + [root*4 * 2**(s/12) for s in ch]  # 220–560
```

低音留在根音并补一层 ×0.5 的下基音（55Hz），20–150Hz 才有内容又不独占。

### 坑 2：pad 按分音数归一之后，能量只有低音的十几分之一

`pad_chord()` 里 `y /= len(freqs)*3` 是为了防削波，但副作用是 pad 的波形幅度只有
低音的 ~1/18，**频谱能量小两个数量级**。于是你怎么调 pad 的音量旋钮，
"150–400Hz"那一栏都不动。补一个显式的 stem 增益（实测 ×3.0）才对得上。

**教训：多 stem 合成时，先量每个 stem 单独的能量，再配平；不要靠听。**

### 坑 3：饱和器把床压成一条直线

原来收尾是 `tanh(mix/ref*1.15)`。床的 crest 从 13dB 掉到 **8.0dB** ——
低于 9dB 的"被压扁"红线，整条床变成一个恒定响度，起伏全没了。
改成**只做峰值归一**，crest 回到 **12.5–14.0dB**，六集全部落在 12–18dB 的健康区间。

最终混音那一步才上软膝限幅（阈值 0.62），只压过冲：
mix crest 19.0 → 18.6，动态基本没动。

### 六集实测（床）

| 集 | 根音 | 20-150 | 150-400 | 400-1.2k | 1.2k-8k | crest | clip |
|---|---|---|---|---|---|---|---|
| 01 | A2 minor | 48.1% | 26.4% | 25.4% | 0.1% | 13.3 | 0 |
| 02 | D3 dorian | 52.2% | 21.2% | 25.6% | 1.0% | 14.0 | 0 |
| 03 | F2 minor | 41.5% | 45.3% | 13.2% | 0.0% | 12.5 | 0 |
| 04 | C3 ionian | 54.1% | 21.7% | 23.7% | 0.5% | 13.2 | 0 |
| 05 | G2 mixo | 48.8% | 31.3% | 19.8% | 0.1% | 13.1 | 0 |
| 06 | E2 minor | 45.2% | 44.1% | 10.7% | 0.0% | 13.7 | 0 |

**根音决定低频占比**：02 用 D2（73Hz）时是 58.1%，越线；抬到 D3 变成 52.2%，合规。
低频超 55% 时**抬根音八度比动 EQ 干净**。1.2k–8k 全程留空给主持人（≤1.0%）——
这条是硬要求，合成床里任何"亮一点"的冲动都会去抢人声的频段。

### 音效落点与增益

| cue | 落点 | 增益 |
|---|---|---|
| `impact` | 段起点，且该段有 `head`/`quote`；全片上限 9 个 | 0.50 |
| `tick` | 其余段起点，上限 14 个 | 0.34 |
| `whoosh` | **卡片入场前 0.22s**（不是入场那一刻） | 0.26 |
| `bell` | 片尾前 4.2s | 0.26 |
| `phone` | 剧情里"手机响了"那一秒 | 0.30 |

闪避只作用在 bed 数组上（`bed * duck`），SFX 是**另加**的一条轨，
从构造上就不可能被压掉——比"记得排除 SFX"可靠。
人声 RMS ≈ −20 dBFS，床相对人声 **−22 dB**，闪避深度 0.62（起压点在人声包络
70 分位以下 26dB），attack 0.08s / release 0.35s。

### 各集之间还要再过一道整片响度归一

按 RMS 配平完，六集的整片 LUFS 实测仍然在 **−19.6 … −21.0** 之间漂，
其中一集直接掉出人声带。原因：LUFS 是 K 加权 + 门控的，讲话人的停顿分布、
胸腔共鸣多少都会改变它，RMS 配平管不到。所以最后统一走一遍两遍式 `loudnorm`
（先量 `input_i/tp/lra/thresh/target_offset`，再 `linear=true` 线性施加），
目标 **I = −19 LUFS / TP = −1.5 dBFS / LRA = 11**：

```
六集归一后：全部 −19.0 LUFS，真峰值 −1.5 dBFS
```

用**线性**模式（`linear=true`），不要单遍动态模式——动态增益会在句子之间抽水，
口播听着一起一伏。这一步也可以只换音轨重封（`-c:v copy`），不用重渲染。
