"""Find the most clip-worthy moments in a long recording, automatically.

Scores every second of the video by
  - loudness spikes (shouting, laughing, explosions, crashes, gunfire) and
  - fast action (many scene cuts / camera changes),
then picks the top moments, spaced apart, and writes a clips.txt that clipper.py can use.

Usage:
    python creator/find_moments.py stream.mp4                 # top 8 moments -> clips.txt
    python creator/find_moments.py stream.mp4 --top 12 --frames moments/
    python creator/clipper.py stream.mp4 clips.txt --lang hi  # then cut them

--frames saves one picture per moment so you can check them before cutting.
Titles are placeholders ("Moment at 12:30"): rename them in clips.txt.
Needs ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clipper import fmt  # noqa: E402


def ffmpeg_lines(args: list[str]) -> list[str]:
    res = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        sys.exit("ffmpeg failed:\n" + res.stderr[-1500:])
    return res.stdout.splitlines()


def duration(src: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout
    try:
        return float(out.strip())
    except ValueError:
        sys.exit(f"Could not read the length of {src}")


def loudness_per_second(src: Path) -> dict[int, float]:
    """RMS level (dB) for each second of audio."""
    lines = ffmpeg_lines(["-i", str(src), "-vn", "-af",
                          "aresample=8000,asetnsamples=n=8000:p=0,astats=metadata=1:reset=1,"
                          "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                          "-f", "null", "-"])
    out, t = {}, None
    for ln in lines:
        m = re.search(r"pts_time:([\d.]+)", ln)
        if m:
            t = int(float(m.group(1)))
            continue
        m = re.search(r"RMS_level=(-?[\d.]+|-inf)", ln)
        if m and t is not None:
            out[t] = -90.0 if m.group(1) == "-inf" else float(m.group(1))
    return out


def scene_cuts(src: Path) -> list[float]:
    lines = ffmpeg_lines(["-i", str(src), "-an", "-vf",
                          "fps=4,scale=320:-2,select='gt(scene,0.35)',metadata=print:file=-",
                          "-f", "null", "-"])
    return [float(m.group(1)) for ln in lines if (m := re.search(r"pts_time:([\d.]+)", ln))]


def zscores(vals: list[float]) -> list[float]:
    if len(vals) < 2:
        return [0.0] * len(vals)
    mu, sd = statistics.fmean(vals), statistics.pstdev(vals) or 1.0
    return [(v - mu) / sd for v in vals]


def smooth(vals: list[float], w: int) -> list[float]:
    out = []
    for i in range(len(vals)):
        win = vals[max(0, i - w): i + w + 1]
        out.append(sum(win) / len(win))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Find the best moments in a GTA 6 recording.")
    ap.add_argument("recording", type=Path)
    ap.add_argument("--top", type=int, default=8, help="how many moments to pick (default 8)")
    ap.add_argument("--before", type=int, default=20, help="seconds before the peak (default 20)")
    ap.add_argument("--after", type=int, default=10, help="seconds after the peak (default 10)")
    ap.add_argument("--gap", type=int, default=60, help="minimum seconds between moments (default 60)")
    ap.add_argument("--out", type=Path, default=Path("clips.txt"))
    ap.add_argument("--frames", type=Path, help="folder to save one picture per moment")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it and add it to PATH.")
    if not a.recording.exists():
        sys.exit(f"Recording not found: {a.recording}")

    total = int(duration(a.recording))
    print(f"Scanning {fmt(total)} of video (audio)...")
    loud = loudness_per_second(a.recording)
    print("Scanning video for fast action...")
    cuts = scene_cuts(a.recording)

    secs = list(range(total))
    audio = smooth(zscores([loud.get(s, -90.0) for s in secs]), 2)
    density = [0.0] * total
    for c in cuts:
        if int(c) < total:
            density[int(c)] += 1
    action = smooth(zscores(density), 4)
    score = [1.0 * a_ + 0.6 * v for a_, v in zip(audio, action)]

    # Greedy pick of the highest peaks, kept apart by --gap; skip the very start/end.
    order = sorted(range(total), key=lambda s: score[s], reverse=True)
    picks: list[int] = []
    for s in order:
        if len(picks) >= a.top:
            break
        if s < 5 or s > total - 3:
            continue
        if all(abs(s - p) >= a.gap for p in picks):
            picks.append(s)
    picks.sort()
    if not picks:
        sys.exit("No moments found (is the video very short?)")

    lines = ["# Auto-picked moments. Rename the titles, delete the ones you don't want.",
             "# start - end | title"]
    for p in picks:
        start, end = max(0, p - a.before), min(total, p + a.after)
        lines.append(f"{fmt(start)} - {fmt(end)} | Moment at {fmt(p)}")
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if a.frames:
        a.frames.mkdir(parents=True, exist_ok=True)
        for i, p in enumerate(picks, 1):
            for off, tag in ((-6, "a"), (0, "b"), (4, "c")):
                t = min(max(0, p + off), total - 1)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(a.recording),
                                "-frames:v", "1", "-vf", "scale=640:-2",
                                str(a.frames / f"{i:02d}{tag}_{fmt(t).replace(':', '-')}.jpg")])

    print(f"\nPicked {len(picks)} moments -> {a.out}")
    for p in picks:
        print(f"  {fmt(p)}  score {score[p]:.2f}")
    if a.frames:
        print(f"Pictures of each moment: {a.frames}")


if __name__ == "__main__":
    main()
