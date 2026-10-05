#!/usr/bin/env python3
"""Score text colors for WCAG contrast against the REAL composited background.

Contrast is arithmetic, not judgement. A grey that computes 4.6:1 on a flat
swatch can measure 4.43:1 in situ because a gradient or image behind it is
lighter than the swatch you checked against. This blends alpha over the
background first, then scores the result, so the number matches what ships.

    python3 contrast.py "#7A9086" --bg "#08120E"
    python3 contrast.py "#6C7488" --bg "#08120E,#112233" --large
    python3 contrast.py "#ffffff,#8A94A6" --bg "#0b1020,#1a2740" --alpha 0.9
    python3 contrast.py "#ffffff" --bg "#08120E,#0d1a16" --suggest
"""
import argparse
import colorsys
import json
import sys

BODY_MIN = 4.5   # WCAG AA, normal text
LARGE_MIN = 3.0  # WCAG AA, large text (>=24px, or >=18.66px bold)


def parse_color(s: str) -> tuple[float, float, float, float]:
    s = s.strip().lstrip("#")
    if "," in s or " " in s:
        parts = [p for p in s.replace(",", " ").split() if p]
        vals = [float(p.rstrip("%")) / (100 if p.endswith("%") else 1) for p in parts]
        if len(vals) == 3:
            vals.append(1.0)
        if len(vals) != 4 or any(v < 0 or v > 1 for v in vals):
            raise SystemExit(f"cannot parse color: {s}")
        return tuple(vals)
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 6:
        s += "ff"
    if len(s) != 8:
        raise SystemExit(f"cannot parse color: {s}")
    return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4, 6))


def over(fg: tuple, bg: tuple) -> tuple:
    """Composite fg over opaque bg (source-over)."""
    a = fg[3]
    return (fg[0] * a + bg[0] * (1 - a),
            fg[1] * a + bg[1] * (1 - a),
            fg[2] * a + bg[2] * (1 - a), 1.0)


def luminance(c: tuple) -> float:
    def lin(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c[0]), lin(c[1]), lin(c[2]))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(c1: tuple, c2: tuple) -> float:
    l1, l2 = luminance(c1), luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def hexs(c: tuple) -> str:
    return "#" + "".join(f"{round(max(0, min(1, v)) * 255):02X}" for v in c[:3])


def score(fg_s: str, bg_s: str, large: bool) -> dict:
    fg, bg = parse_color(fg_s), parse_color(bg_s)
    comp = over(fg, bg)
    r = ratio(comp, bg)
    need = LARGE_MIN if large else BODY_MIN
    return {"fg": fg_s, "bg": bg_s, "composited": hexs(comp),
            "ratio": round(r, 2), "required": need, "pass": r >= need}


def lighten_toward_white(fg: tuple, bg: tuple, need: float) -> tuple:
    """Walk the foreground toward white in HSL lightness until it passes."""
    h, l, sat = colorsys.rgb_to_hls(*fg[:3])
    for step in range(1, 101):
        nl = min(1.0, l + step / 100.0)
        cand = colorsys.hls_to_rgb(h, nl, sat)
        if ratio((*cand, 1.0), bg) >= need:
            return (*cand, 1.0)
    return (1.0, 1.0, 1.0, 1.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fg", nargs="+", help="foreground color(s) to score")
    # Comma-separated (repeatable) rather than nargs="+", which would be ambiguous
    # against the greedy positional and silently swallow backgrounds.
    ap.add_argument("--bg", action="append", default=None, metavar="COLORS",
                    help="background color(s), comma-separated; repeatable. Every fg is scored against every bg. Default #000000")
    ap.add_argument("--large", action="store_true", help=f"large text (>=24px / >=18.66px bold): require {LARGE_MIN}:1 instead of {BODY_MIN}:1")
    ap.add_argument("--alpha", type=float, help="override the foreground alpha (e.g. 0.9 for a tinted text layer)")
    ap.add_argument("--suggest", action="store_true", help="also propose a passing variant of each failing color")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    bgs: list[str] = []
    for group in (args.bg or ["#000000"]):
        bgs.extend(c for c in (x.strip() for x in group.split(",")) if c)

    rows = []
    for f in args.fg:
        fg = parse_color(f)
        if args.alpha is not None:
            fg = (fg[0], fg[1], fg[2], args.alpha)
        for b in bgs:
            row = score(hexs(fg), b, args.large)
            rows.append(row)
            if args.suggest and not row["pass"]:
                fixed = lighten_toward_white(fg, parse_color(b), row["required"])
                row["suggestion"] = hexs(fixed)
                row["suggestion_ratio"] = round(ratio(fixed, parse_color(b)), 2)

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'foreground':>10}  {'background':>10}  {'on':>9}  {'ratio':>6}  {'need':>5}  result")
        for r in rows:
            verdict = "PASS" if r["pass"] else "FAIL"
            extra = ""
            if r.get("suggestion"):
                extra = f"   -> try {r['suggestion']} ({r['suggestion_ratio']}:1)"
            print(f"{r['fg']:>10}  {r['bg']:>10}  {r['composited']:>9}  {r['ratio']:>5.2f}:1  {r['required']:>4}:1  {verdict}{extra}")
        failed = [r for r in rows if not r["pass"]]
        if failed:
            print(f"\n{len(failed)} of {len(rows)} combination(s) below the "
                  f"{'large-text' if args.large else 'body-text'} threshold.", file=sys.stderr)
            if not args.suggest:
                print("Re-run with --suggest to get passing variants.", file=sys.stderr)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
