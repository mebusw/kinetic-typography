#!/usr/bin/env python3
"""Measure per-segment voiceover durations and lay out a timeline skeleton.

Timing in this format comes from measured audio, never from a word-count
estimate. This walks a directory of per-segment voiceover files, probes each
one, and writes a JSON skeleton that timeline.json can be built from.

    python3 measure_segments.py audio/vo --gap 0.35 --out audio/segments.json
    python3 measure_segments.py audio/vo --text script --estimate 140
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".aiff", ".aif", ".flac", ".ogg", ".opus"}


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        raise SystemExit(f"could not read duration of {path}")


def char_count(path: Path, text_dir: Path | None) -> int | None:
    if text_dir is None:
        return None
    stem = path.stem
    for cand in (text_dir / f"{stem}.txt", text_dir / f"{stem}.md"):
        if cand.exists():
            return len("".join(cand.read_text(encoding="utf-8").split()))
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio_dir", type=Path, help="directory of per-segment voiceover files")
    ap.add_argument("--out", type=Path, help="write JSON here (default: stdout)")
    ap.add_argument("--gap", type=float, default=0.35,
                    help="breath between segments, seconds (default 0.35; 0.30-0.40 reads natural)")
    ap.add_argument("--text", type=Path, help="directory of per-segment .txt scripts, for rate reporting")
    ap.add_argument("--estimate", type=float, metavar="SEC",
                    help="the deck's own duration estimate, to compare the measured total against")
    ap.add_argument("--tolerance", type=float, default=0.10,
                    help="report when measured differs from --estimate by more than this fraction (default 0.10)")
    args = ap.parse_args()

    if not shutil.which("ffprobe"):
        raise SystemExit("ffprobe not found on PATH")

    files = sorted(p for p in args.audio_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in AUDIO_EXT)
    if not files:
        raise SystemExit(f"no audio files in {args.audio_dir}")

    segments, cursor = [], 0.0
    for i, f in enumerate(files, 1):
        dur = probe_duration(f)
        chars = char_count(f, args.text)
        seg = {
            "id": f"seg-{i:02d}",
            "voiceover": f.name,
            "t0": round(cursor, 3),
            "t1": round(cursor + dur, 3),
            "duration": round(dur, 3),
        }
        if chars is not None:
            seg["chars"] = chars
            seg["chars_per_sec"] = round(chars / dur, 2) if dur else 0.0
        segments.append(seg)
        cursor += dur + args.gap

    total = round(cursor - args.gap, 3)
    speech = round(sum(s["duration"] for s in segments), 3)

    result = {
        "measured_total": total,
        "speech_total": speech,
        "gap": args.gap,
        "segments": segments,
    }

    print(f"{len(segments)} segments · speech {speech:.1f}s · "
          f"with gaps {total:.1f}s ({total/60:.2f} min)", file=sys.stderr)
    for s in segments:
        rate = f" · {s['chars_per_sec']} char/s" if "chars_per_sec" in s else ""
        print(f"  {s['id']}  {s['t0']:7.2f} → {s['t1']:7.2f}  "
              f"({s['duration']:5.2f}s){rate}  {s['voiceover']}", file=sys.stderr)

    if args.estimate:
        delta = total - args.estimate
        rel = abs(delta) / args.estimate if args.estimate else 0.0
        verdict = "SURFACE THIS TO THE USER BEFORE BUILDING" if rel > args.tolerance else "within tolerance"
        print(f"\ndeck estimate {args.estimate:.1f}s vs measured {total:.1f}s "
              f"({delta:+.1f}s, {rel*100:.1f}%) — {verdict}", file=sys.stderr)
        result["deck_estimate"] = args.estimate
        result["delta_vs_estimate_pct"] = round(rel * 100, 1)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}", file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
