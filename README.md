# Kinetic Typography · Vertical kinetic-text shorts

**[中文](README.zh.md)** · [English](README.md)

Turn a copy deck or voiceover script into a **vertical (9:16) kinetic-typography short** — the type moves on its own, footage is placed and timed, music is mixed, and **a slot is reserved for the talking-head video you record later**.

This README is for humans and covers three things only: **what it does, what it's worth, how to use it**.
The rationale, the decision rules, and the post-mortems live in [`SKILL.md`](SKILL.md) and `references/`, which are written for the AI — you don't need to read them.

---

## 1. What it does

Give it a script (even before you've recorded anything) and it delivers:

| Output | What it is |
|---|---|
| **The vertical film** | 1080×1920, 30fps, type as the subject, designed motion — not a caption template |
| **`打点表.md`** | The timing sheet: which line lands at which second, so you record to the picture |
| **`timeline.json`** | The single source of truth for content and timing — a copy edit touches only this file |
| **The audio** | BGM leveled against the voice and ducked, so it never fights the speech |

It owns subtitles, footage editing, music, and the mix. **You** own recording the voiceover and the face-cam.

## 2. What it's worth

- **It skips the most expensive step.** Layout gets fixed during frame review, not by re-rendering until something looks right.
- **No waiting on a recording.** Start before the voiceover exists; by the time you record, the beats are already set.
- **Copy edits are cheap.** Change one line in `timeline.json` and the film follows.
- **It fails loudly, not silently.** Pre-render checks catch dropped elements, out-of-bounds cards, and unitless values before you spend a render.
- **The face-cam slot is reserved.** Bottom-left or bottom-right at a quarter of the frame's short side, so you paste your recording in later without re-laying out anything.
- **The mix doesn't fight you.** Music is RMS-matched to the voice and ducked automatically; sound effects ride a separate bus and don't get squashed.

## 3. How to use it

### 0. Install


Tell your Codex or any agent:

```bash
Install the SKILL by `npx skills add -g github.com/mebusw/kinetic-typography`
```


### 1. Invoke

Installed at `~/.agents/skills/kinetic-typography`. In Codex, just say:

```
Use $kinetic-typography to turn this copy deck into a vertical kinetic-typography
short. I have no voiceover yet — lay the beats out to how it will be spoken and
add BGM. I'll record my face-cam later, usually square or landscape, bottom-left
or bottom-right.
```

Or skip naming the skill and just describe the task — it triggers on its own.

### 2. What to bring

**A script is the only hard requirement.** The rest is a bonus:

- Required: the voiceover script / copy deck
- Optional: photos, screen recordings, intro/outro, brand colors and fonts
- Optional: an already-recorded voiceover or face-cam (used if present, reserved if not)

### 3. It checks in with you once

Before it lays anything out, it hands you the **`打点表.md`** and the visual direction. **That is the only moment that needs you** — confirm the copy and the beats, and it runs to a finished film from there.

### 4. Use the tools on their own

All six scripts run standalone and all take `--help`:

```bash
S=~/.agents/skills/kinetic-typography/scripts

# Measure per-segment durations (measured, not estimated from word count)
python3 $S/measure_segments.py audio/vo --gap 0.35 --out audio/segments.json

# Pre-flight the timeline and generate the timing sheet
python3 $S/validate_timeline.py timeline.json --out 打点表.md

# Cross-check the built page for anything the generator dropped
python3 $S/validate_timeline.py timeline.json --html index.html

# Static audit of the generated composition
node    $S/audit_html.mjs index.html

# Text contrast, computed rather than eyeballed
python3 $S/contrast.py "#7A9086" --bg "#08120E" --suggest

# Music bed: RMS-matched to the voice, with ducking
python3 $S/level_audio.py --voice vo.wav --music bgm.wav --out bed.wav --offset -22 --duck

# When something looks wrong, measure the live page
node    $S/probe_dom.mjs index.html --at 1.2,4.5,9
```

Start a new project from [`assets/timeline.template.json`](assets/timeline.template.json).

## 4. What's inside

```
SKILL.md          main pipeline and hard rules (read by the AI)
references/       manuals: pipeline, layout & motion, audio, revisions, pitfalls
scripts/          6 standalone tools
assets/           timeline template
agents/           UI display name and default prompt
```

## 5. Requirements

- Python 3 (`contrast.py` is stdlib-only — no third-party packages)
- FFmpeg / FFprobe
- Node.js 22+
- HyperFrames CLI (`npx hyperframes`)
- `probe_dom.mjs` additionally needs a local Chrome

---

## License and maintenance

The skill files themselves are free to use and modify. **You are responsible for the rights to whatever media ends up in the film** — check that your screen recordings, photos, and music are cleared for use.

After changing anything, run the self-check:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```


