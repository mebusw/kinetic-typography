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
