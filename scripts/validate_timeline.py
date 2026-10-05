#!/usr/bin/env python3
"""Pre-flight validation for a kinetic-typography timeline.json, plus the
human-readable timing sheet (打点表).

This is the gate that catches the failure mode which produces no error
anywhere: content present in the JSON that the generator never emitted, or
that was emitted at a time outside its own segment.

    python3 validate_timeline.py timeline.json --out 打点表.md
    python3 validate_timeline.py timeline.json --html index.html --strict

Exits non-zero when errors are found (warnings alone do not fail unless
--strict is given).
"""
import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_SAFE = {"top": 120, "bottom": 300, "left": 80, "right": 80}
# A card may outlive its segment by this much so its backing clip is not
# exposed as an empty shell at the tail. Content beats may not.
CARD_TAIL_GRACE = 0.8

ELEMENT_KEYS = ("beats", "cards", "shapes", "overlays", "clips", "figures", "labels")


def finite(x) -> bool:
    """True for a real, usable number. NaN and inf are the ones that
    silently kill a tween or an animation target, so they are rejected here."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and x not in (float("inf"), float("-inf"))


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def collect_elements(tl: dict) -> list[tuple[str, dict, dict | None]]:
    """Flatten every timed element across all segments, with its owning segment."""
    out = []
    for seg in tl.get("segments", []):
        for key in ELEMENT_KEYS:
            items = seg.get(key)
            if items is None:
                continue
            if not isinstance(items, list):
                out.append((key, {"__notalist__": items}, seg))
                continue
            for el in items:
                out.append((key, el, seg))
    return out


def check_timing(tl: dict, rep: Report) -> None:
    safe = {**DEFAULT_SAFE, **(tl.get("meta", {}).get("safe") or {})}
    W = tl.get("meta", {}).get("width")
    H = tl.get("meta", {}).get("height")
    seen_ids: dict[str, str] = {}

    if not tl.get("segments"):
        rep.err("no segments in timeline")
        return

    prev_end = -1.0
    for i, seg in enumerate(tl["segments"]):
        sid = seg.get("id") or f"segments[{i}]"
        t0, t1 = seg.get("t0"), seg.get("t1")

        if sid in seen_ids:
            rep.err(f"{sid}: duplicate segment id (also in {seen_ids[sid]})")
        seen_ids[sid] = sid

        if not finite(t0) or not finite(t1):
            rep.err(f"{sid}: segment bounds must be finite numbers, got t0={t0!r} t1={t1!r}")
            continue
        if t1 <= t0:
            rep.err(f"{sid}: t1 ({t1}) must be greater than t0 ({t0})")
        if t0 < prev_end - 1e-6:
            rep.err(f"{sid}: starts at {t0}, before the previous segment ended at {prev_end:.3f} — segments must be ordered and non-overlapping")
        prev_end = t1
        if not seg.get("beat"):
            rep.warn(f"{sid}: no `beat` (the segment's one-line claim) — this is what makes the 打点表 readable")

    for kind, el, seg in collect_elements(tl):
        sid = (seg or {}).get("id", "?")
        eid = el.get("id")
        if el.get("__notalist__") is not None:
            rep.err(f"{sid}.{kind}: expected a list, got {type(el['__notalist__']).__name__}")
            continue
        if not eid:
            rep.err(f"{sid}.{kind}: element without an id — ids are how the generator addresses elements and how the audit cross-checks them")
            continue
        if eid in seen_ids:
            rep.err(f"id '{eid}' is not unique (already used by {seen_ids[eid]}) — duplicate ids silently misdirect every animation")
        seen_ids[eid] = f"{sid}.{kind}"

        t, dur = el.get("t"), el.get("dur")
        if not finite(t):
            rep.err(f"{eid} ({sid}.{kind}): `t` must be a finite number, got {t!r} — a NaN here means the tween never fires and the element never leaves")
            continue
        if dur is None:
            rep.err(f"{eid}: missing `dur`")
            continue
        if not finite(dur) or dur <= 0:
            rep.err(f"{eid}: `dur` must be a positive finite number, got {dur!r}")
            continue

        s0, s1 = seg.get("t0"), seg.get("t1")
        if not (finite(s0) and finite(s1)):
            continue
        grace = CARD_TAIL_GRACE if kind == "cards" else 0.0
        if t < s0 - 1e-6:
            rep.err(f"{eid}: on-screen at {t}, before its segment starts at {s0} — the element appears in the previous segment")
        if t >= s1:
            rep.err(f"{eid}: on-screen at {t}, at or after its segment ends at {s1} — it will never be seen in its own segment")
        if t + dur > s1 + grace + 1e-6:
            msg = (f"{eid}: runs to {t + dur:.2f}, past its segment end {s1:.2f}")
            if kind == "cards":
                msg += f" (a card may overrun by up to {CARD_TAIL_GRACE}s so its backing clip is not exposed)"
                rep.warn(msg)
            else:
                rep.err(msg)

        if kind == "beats" and not (el.get("text") or "").strip():
            rep.err(f"{eid}: beat has no `text` — the whole segment renders blank")

        if kind == "cards" and W and H:
            x, y, w, h = el.get("x"), el.get("y"), el.get("w"), el.get("h")
            if None in (x, y, w, h):
                rep.err(f"{eid}: card needs x, y, w, h to be checked against the safe zone (got {x!r},{y!r},{w!r},{h!r})")
            else:
                if x < safe["left"] or x + w > W - safe["right"]:
                    rep.err(f"{eid}: card spans x {x}→{x + w}, outside the safe zone (x must stay within {safe['left']}→{W - safe['right']})")
                if y < safe["top"] or y + h > H - safe["bottom"]:
                    rep.err(f"{eid}: card spans y {y}→{y + h}, outside the safe zone (y must stay within {safe['top']}→{H - safe['bottom']})")


def check_html(tl: dict, html: Path, rep: Report) -> None:
    """Catch the silent omission: ids in the JSON that never reached the output."""
    src = html.read_text(encoding="utf-8", errors="replace")
    declared = {el["id"] for _, el, _ in collect_elements(tl) if el.get("id")}
    present = set(re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', src))
    missing = sorted(declared - present)
    if missing:
        rep.err(f"{html.name}: {len(missing)} id(s) in the timeline never appear in the output — "
                f"the generator is dropping them: {', '.join(missing[:12])}"
                f"{' …' if len(missing) > 12 else ''}")
    if not missing and declared:
        print(f"  all {len(declared)} timeline ids present in {html.name}")


def fmt(t) -> str:
    return f"{t:6.2f}"


def write_sheet(tl: dict, path: Path, measured_total=None) -> None:
    meta = tl.get("meta", {})
    L = []
    L.append(f"# {meta.get('title', 'Untitled')} — 打点表 / timing sheet")
    L.append("")
    L.append(f"Format {meta.get('width', 1080)}×{meta.get('height', 1920)} @ {meta.get('fps', 30)}fps · "
             f"total {tl.get('total', (tl.get('segments') or [{}])[-1].get('t1', 0)):.1f}s")
    if measured_total:
        L.append(f"Measured voiceover total {measured_total:.1f}s — this sheet is laid out from real audio durations, not estimates.")
    L.append("")
    L.append("Record each line so it lands on its time. Content beats are the lines; the claim is the point of the segment.")
    L.append("")

    for seg in tl.get("segments", []):
        L.append(f"## {seg.get('id')} · {fmt(seg.get('t0', 0))} → {fmt(seg.get('t1', 0))}"
                 f" ({seg.get('t1', 0) - seg.get('t0', 0):.1f}s)")
        L.append("")
        L.append(f"**VO:** {seg.get('vo', '—')}")
        L.append("")
        if seg.get("beat"):
            L.append(f"**Claim on screen:** {seg['beat']}")
            L.append("")
        rows = [el for el in seg.get("beats", []) if (el.get("text") or "").strip()]
        if rows:
            L.append("| on screen | off | line | role |")
            L.append("|---|---|---|---|")
            for el in rows:
                L.append(f"| {fmt(el.get('t', 0))} | {fmt(el.get('t', 0) + el.get('dur', 0))} "
                         f"| {el['text']} | {el.get('role', '')} |")
            L.append("")
        cards = seg.get("cards", [])
        if cards:
            names = ", ".join(f"`{c.get('id')}`" for c in cards)
            L.append(f"Footage/graphics: {names}")
            L.append("")

    L.append("---")
    L.append("")
    L.append("Generated from `timeline.json` by `validate_timeline.py`. Do not hand-edit — "
             "it is rebuilt from the timeline, which is the source of truth.")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  wrote {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("timeline", type=Path, help="path to timeline.json")
    ap.add_argument("--html", type=Path, help="generated index.html — cross-check ids against it")
    ap.add_argument("--out", type=Path, help="write the 打点表 timing sheet here")
    ap.add_argument("--segments", type=Path, help="segments.json from measure_segments.py, for the measured total")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = ap.parse_args()

    tl = json.loads(args.timeline.read_text(encoding="utf-8"))
    rep = Report()
    check_timing(tl, rep)
    if args.html:
        if not args.html.exists():
            rep.err(f"{args.html} does not exist yet — run the generator first")
        else:
            check_html(tl, args.html, rep)

    measured = None
    if args.segments and args.segments.exists():
        measured = json.loads(args.segments.read_text(encoding="utf-8")).get("measured_total")
        if measured:
            est = tl.get("total")
            if est and abs(measured - est) / est > 0.02:
                rep.warn(f"timeline total {est:.1f}s differs from measured voiceover {measured:.1f}s "
                         f"by more than 2% — one of them is stale")

    for w in rep.warnings:
        print(f"WARN  {w}", file=sys.stderr)
    for e in rep.errors:
        print(f"ERROR {e}", file=sys.stderr)

    print(f"\n{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)", file=sys.stderr)
    if args.out:
        write_sheet(tl, args.out, measured)

    if rep.errors or (args.strict and rep.warnings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
