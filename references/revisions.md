# Revisions: when the user changes the copy

A revision is not an edit to `timeline.json`. It is an audit of **every place that phrase lives**, followed by the smallest re-render that clears it.

## 1. Find all the copies before touching any of them

A data point you delete from the timeline can still be visible somewhere you did not look.

| Where it can survive | How to check |
|---|---|
| On-screen text | walk every `text` in `timeline.json`, not just the segment you remember |
| The voiceover | `script/seg-*.txt` — a spoken number survives even after the caption is gone |
| The 打点表 | it is generated; regenerate it or it will contradict the film |
| **Baked into a still** | open every `assets/*.png` you cut as a graphic card and *look* |
| The cue list | `audio/cues.json` — an accent timed to a moved or deleted beat fires into the next segment; regenerate it with the timeline |
| Baked into footage | the screen recording shows it in pixels; grep cannot find it |
| The direction doc | the母题 paragraph usually names the number |

The still-image row is the one that gets skipped, and it is the one that ships a stale number into the film.

```bash
# text layer
python3 - <<'EOF'
import json
d = json.load(open('timeline.json'))
out = []
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == 'text' and isinstance(v, str): out.append(v)
            else: walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(d)
for t in sorted(set(out)): print(t)
EOF
# then OPEN the stills listed in cards[] and read them
```

## 2. Sort what you found into data and words

Not everything numeric is a claim.

- **Data** — a figure that could be read as a fact about the user's business. Percentages, rates, absolute counts, named clients, real dates. Delete or replace these.
- **Words** — a label that merely echoes the spoken line. Step names in a process list, headings, the segment's claim.

A voiceover line reading "改数字就是改一行字" is satisfied by a list item labelled **改数字** and breaks if you delete it. The same line's `4.8 → 5.2` is a fabricated figure and goes.

Rule of thumb: *if removing it would make the picture contradict the voice, it is a word; if removing it costs the viewer nothing except accuracy, it is data.* When both are true, keep the word and re-phrase the data into the same slot (`4.8 → 5.2` becomes `改一行字`).

## 3. Replace, do not just delete

Deleting a beat's anchor leaves a hole where the device used to be. The fix keeps the mechanic and changes the payload:

- a typed demo line keeps its shape — `## 延期率 4.8%` → `## 项目交付复盘`
- a before/after pair keeps both slots — `4.8 → 5.2` → `改一行字`
- the chart stills usually carry only generic sample numbers and need no change; verify, do not assume

## 4. Decide what must be re-rendered

| Change | Re-render? |
|---|---|
| Any on-screen text, timing, or a card | **yes** |
| Voiceover reference audio only | no — the film keeps its rhythm; only the guide track changes |
| A note in the direction doc or memory | no |
| Re-cutting a still whose number you deleted | only if you actually changed the still |

A copy revision never changes the timeline's *shape*, so a voice actor can start recording against the previous render while you re-render. Say so explicitly — it is the single most useful thing you can tell someone waiting on a deliverable.

## 5. Re-run the gates, and say what you changed

Re-run `validate_timeline.py --html index.html`, `audit_html.mjs`, `hyperframes check`, then snapshot **the segments you touched plus one before and one after** — a one-line edit moves nothing else, but a re-cut can shift a card's exit.

Then look at only what changed: the touched segments' snapshots, plus a 10fps strip across each boundary that borders them (see pipeline stage 7). One full contact-sheet pass comes at the end. Re-watching the whole film segment by segment after a one-line change is how a revision eats a day.

Report the change as a table of before → after, and state which assets you verified visually. The user is deciding whether to trust the file; "I checked" without naming what you checked is not the same as having checked.
