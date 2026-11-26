#!/usr/bin/env python3
"""Measure frame selection on local videos (dev only, not part of the skill).

    python3 tools/measure.py lecture.mp4 screen.mp4 [--max-delta 255,60,40,25] [--keep DIR]

--max-delta sweeps frames.DEDUP_MAX_DELTA; 255 disables it (mean-only dedup).
img_tokens is an estimate: ceil(w/28) * ceil(h/28) per selected frame.
max_gap is the longest stretch in seconds without a selected frame.
"""
import argparse
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "watch" / "scripts"))
import frames  # noqa: E402


def frame_tokens(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True).stdout
    width, height = map(int, out.strip().split(",")[:2])
    return math.ceil(width / 28) * math.ceil(height / 28)


def measure(video, mode, out_dir):
    duration = frames.get_metadata(video)["duration_seconds"]
    started = time.monotonic()
    if mode == "efficient":
        selected, meta = frames.extract_keyframes(video, out_dir, max_frames=50)
    else:
        fps, target = frames.auto_fps(duration, max_frames=100)
        selected, meta = frames.extract_scene_or_uniform(video, out_dir, fps=fps, target_frames=target)
    elapsed = time.monotonic() - started
    stamps = [0.0, *(f["timestamp_seconds"] for f in selected), duration]
    return {
        "engine": meta["engine"],
        "candidates": meta["candidate_count"],
        "deduped": meta["deduped_count"],
        "selected": len(selected),
        "img_tokens": frame_tokens(selected[0]["path"]) * len(selected) if selected else 0,
        "max_gap": round(max(b - a for a, b in zip(stamps, stamps[1:]))),
        "seconds": round(elapsed, 1),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("videos", nargs="+")
    parser.add_argument("--max-delta", default=f"255,60,{frames.DEDUP_MAX_DELTA},25")
    parser.add_argument("--keep", type=Path, help="keep selected frames under DIR for visual review")
    args = parser.parse_args()
    deltas = [int(v) for v in args.max_delta.split(",")]

    columns = ["video", "mode", "max_delta", "engine", "candidates", "deduped",
               "selected", "img_tokens", "max_gap", "seconds"]
    print("| " + " | ".join(columns) + " |")
    print("|" + "---|" * len(columns))
    with tempfile.TemporaryDirectory() as tmp:
        root = args.keep or Path(tmp)
        for video in args.videos:
            for mode in ("efficient", "balanced"):
                for delta in deltas:
                    frames.DEDUP_MAX_DELTA = delta
                    out_dir = root / Path(video).stem / f"{mode}-{delta}"
                    row = {"video": Path(video).name, "mode": mode, "max_delta": delta,
                           **measure(video, mode, out_dir)}
                    print("| " + " | ".join(str(row[c]) for c in columns) + " |", flush=True)


if __name__ == "__main__":
    main()
