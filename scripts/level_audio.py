#!/usr/bin/env python3
"""Level a music bed against a voice track by RMS, with optional voice-keyed
ducking. Peak normalization does not control loudness — a track normalized to
-1 dBFS can still measure louder than the voice. This targets an RMS offset
and prints the numbers it used so the result is checkable without a render.

    python3 level_audio.py --voice vo.wav --music bgm.wav --out bed.wav --offset -22 --duck

SFX are mixed AFTER this step and must not be routed through the duck: a
sidechain that compresses the effects bus takes the accents down with the bed.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FALLBACK_DB = -70.0


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{p.stderr[-2000:]}")


def duration_s(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        raise SystemExit(f"could not read duration of {path}")


def rms_db(path: Path) -> float:
    """Overall RMS in dBFS via ffmpeg's astats — no numpy dependency."""
    p = subprocess.run(
        ["ffprobe", "-v", "info", "-f", "lavfi",
         f"amovie={path},astats=metadata=1:reset=0", "-show_entries",
         "frame_tags=lavfi.astats.Overall.RMS_level", "-of", "json"],
        capture_output=True, text=True)
    vals = re.findall(r'"lavfi\.astats\.Overall\.RMS_level"\s*:\s*"?(-?[\d.]+)', p.stdout or "")
    finite = [float(v) for v in vals if float(v) > FALLBACK_DB]
    if not finite:
        # Lavfi movie may not be enabled; fall back to decoding the file directly.
        p = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(path), "-af",
             "astats=metadata=1:reset=0", "-f", "null", "-"], capture_output=True, text=True)
        vals = re.findall(r"RMS level dB:\s*(-?[\d.]+)", p.stderr or "")
        finite = [float(v) for v in vals if float(v) > FALLBACK_DB]
    if not finite:
        raise SystemExit(f"could not measure RMS of {path} (is it silent? empty?)")
    # astats reports a running value per frame; the max is the settled level.
    return max(finite)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", type=Path, required=True, help="the voiceover track (the reference key)")
    ap.add_argument("--music", type=Path, required=True, help="the music to level and duck")
    ap.add_argument("--out", type=Path, required=True, help="output bed")
    ap.add_argument("--offset", type=float, default=-22.0,
                    help="target RMS offset of bed vs voice, dB (default -22; -20 to -25 is the working range)")
    ap.add_argument("--duck", action="store_true", help="apply voice-keyed sidechain compression to the music")
    ap.add_argument("--threshold", type=float, default=0.03, help="duck threshold, linear (default 0.03)")
    ap.add_argument("--ratio", type=float, default=6.0, help="duck ratio (default 6)")
    ap.add_argument("--release", type=int, default=300, help="duck release, ms (default 300 — slow, or the bed pumps)")
    ap.add_argument("--attack", type=int, default=5, help="duck attack, ms (default 5)")
    ap.add_argument("--fade", type=float, default=1.2, help="music fade in/out, seconds (default 1.2)")
    ap.add_argument("--json", action="store_true", help="print the numbers as JSON")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found on PATH")
    for p in (args.voice, args.music):
        if not p.exists():
            raise SystemExit(f"no such file: {p}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    v_db = rms_db(args.voice)
    m_db = rms_db(args.music)
    target = v_db + args.offset
    gain = target - m_db

    print(f"  voice RMS      {v_db:7.2f} dBFS")
    print(f"  music RMS      {m_db:7.2f} dBFS")
    print(f"  target bed     {target:7.2f} dBFS  (voice {args.offset:+.0f} dB)")
    print(f"  gain applied   {gain:+7.2f} dB")

    peak_guard = gain > 12.0
    if peak_guard:
        print(f"  NOTE: +{gain:.1f} dB is a large boost — check the source is not already quiet-noisy")

    m_dur = duration_s(args.music)
    fade_out = min(args.fade, m_dur / 2.0)
    out_st = round(m_dur - fade_out, 3)
    fades = f"afade=t=in:st=0:d={fade_out},afade=t=out:st={out_st}:d={fade_out}"

    # Ducking needs the voice as a second input, so it gets its own graph.
    if args.duck:
        # [music] is compressed; [voice] is split into the sidechain key and a
        # sink so the graph has no dangling outputs. SFX are NOT in this graph.
        fc = (f"[0:a]volume={gain:.2f}dB[m];"
              # sidechaincompress truncates to the shortest input, so pad the
              # voice key out to the music length or the bed is cut short.
              f"[1:a]apad,atrim=0:{m_dur},asplit=2[sc][ksink];"
              f"[m][sc]sidechaincompress="
              f"threshold={args.threshold}:ratio={args.ratio}:"
              f"attack={args.attack}:release={args.release}[ducked];"
              f"[ksink]anullsink;"
              f"[ducked]{fades}[out]")
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(args.music), "-i", str(args.voice),
               "-filter_complex", fc, "-map", "[out]", str(args.out)]
    else:
        fc = f"[0:a]volume={gain:.2f}dB,{fades}[out]"
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(args.music),
               "-filter_complex", fc, "-map", "[out]", str(args.out)]
    run(cmd)

    out_db = rms_db(args.out)
    print(f"  bed RMS        {out_db:7.2f} dBFS  (measured on the output)")
    print(f"  final offset   {out_db - v_db:+7.2f} dB")
    print(f"  fades          {fade_out:.2f}s in / out (music is {m_dur:.2f}s)")
    if args.duck:
        print("  duck           keyed to the voice; mix SFX AFTER this step, not through this graph")

    if args.json:
        print(json.dumps({
            "voice_rms_db": round(v_db, 2), "music_rms_db": round(m_db, 2),
            "target_bed_db": round(target, 2), "gain_db": round(gain, 2),
            "out_rms_db": round(out_db, 2), "final_offset_db": round(out_db - v_db, 2),
            "ducked": bool(args.duck), "offset_requested": args.offset,
            "large_boost_warning": peak_guard,
        }, indent=2))

    # Fades and ducking both pull the average level down, so a bed with them
    # lands under target by design. Only flag drift that they do not explain.
    drift = (out_db - v_db) - args.offset
    budget = 1.0 + 2.5 * (fade_out / max(m_dur, 0.001)) * 10 + (4.0 if args.duck else 0.0)
    if drift < -(budget + 2.0):
        print(f"  WARNING: the bed landed {-drift:.1f} dB below target — beyond what the "
              f"fades ({fade_out:.1f}s) and ducking explain. Check for a limiter on the source.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
