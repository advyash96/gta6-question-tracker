"""Find the most clip-worthy moments in a long recording, automatically.

Scores every second of the video using up to four signals:
  - loudness spikes   (shouting, laughing, explosions, crashes, gunfire)
  - fast action       (many scene cuts / camera changes)
  - chat spikes       (live-chat replay: viewers going crazy), if a live_chat.json is given
  - hype words        ("bhai", "kya", "oh my god", "no no no"...), if a transcript exists
Each signal is compared with this video's own normal level, so quiet and loud streams both work.
Then it picks the top moments, spaced apart, and writes a clips.txt that clipper.py can use.

Usage:
    python creator/find_moments.py stream.mp4                       # top 8 -> clips.txt
    python creator/find_moments.py stream.mp4 --top 12 --frames moments/
    python creator/find_moments.py stream.mp4 --chat stream.live_chat.json
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

HYPE = re.compile(
    r"\b(oh my god|omg|what+|no+ no+|bro+|bhai+|kya+|arre+|abe+|bhago+|mar gaya|gaya|wow+|let'?s go+|"
    r"holy|yes+|oh no|run+|wait+|brother|crazy|insane|damn|dude|look at|bas+|chal+|ruk+|wah+|haha+|lol)\b|भाई|क्या|अरे|भागो|मर गया|वाह|रुक|चल",
    re.I)
WEIGHTS = {"audio": 1.0, "action": 0.6, "chat": 1.2, "speech": 0.8}


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
    mu, sd = statistics.fmean(vals), statistics.pstdev(vals)
    return [(v - mu) / sd for v in vals] if sd else [0.0] * len(vals)


def smooth(vals: list[float], w: int) -> list[float]:
    out = []
    for i in range(len(vals)):
        win = vals[max(0, i - w): i + w + 1]
        out.append(sum(win) / len(win))
    return out


def per_second(counts: dict[int, float], total: int) -> list[float]:
    return [float(counts.get(s, 0)) for s in range(total)]


def speech_title(words: list[dict], peak: int) -> str | None:
    """A short quote of what was said right at the peak, to use as a working title."""
    near = [w["w"] for w in words if peak - 3 <= w["s"] <= peak + 2]
    if len(near) < 2:
        return None
    text = re.sub(r"\s+", " ", " ".join(near[:7])).strip(" .,!?")
    return f'"{text}"' if text else None


def pick_moments(src: Path, *, top: int = 8, before: int = 20, after: int = 10, gap: int = 60,
                 chat: dict[int, int] | None = None, words: list[dict] | None = None) -> list[dict]:
    total = int(duration(src))
    print(f"Scanning {fmt(total)} of video: audio...")
    loud = loudness_per_second(src)
    print("Scanning video: fast action...")
    density: dict[int, float] = {}
    for c in scene_cuts(src):
        density[int(c)] = density.get(int(c), 0) + 1

    signals = {
        "audio": smooth(zscores([loud.get(s, -90.0) for s in range(total)]), 2),
        "action": smooth(zscores(per_second(density, total)), 4),
    }
    if chat:
        # Chat reacts a few seconds late: shift it back 4 s.
        shifted = {s - 4: n for s, n in chat.items()}
        signals["chat"] = smooth(zscores(per_second(shifted, total)), 3)
    if words:
        hype: dict[int, float] = {}
        for w in words:
            if HYPE.search(w["w"]):
                hype[int(w["s"])] = hype.get(int(w["s"]), 0) + 1
        signals["speech"] = smooth(zscores(per_second(hype, total)), 3)
    print("Signals used: " + ", ".join(signals))
    score = [sum(WEIGHTS[k] * v[s] for k, v in signals.items()) for s in range(total)]

    picks: list[int] = []
    for s in sorted(range(total), key=lambda s: score[s], reverse=True):
        if len(picks) >= top:
            break
        if 5 <= s <= total - 3 and all(abs(s - p) >= gap for p in picks):
            picks.append(s)
    picks.sort()
    return [{"peak": p, "score": score[p], "start": max(0, p - before), "end": min(total, p + after),
             "title": (speech_title(words, p) if words else None) or f"Moment at {fmt(p)}"}
            for p in picks]


def save_frames(src: Path, moments: list[dict], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for i, m in enumerate(moments, 1):
        for off, tag in ((-6, "a"), (0, "b"), (4, "c")):
            t = max(0, m["peak"] + off)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(src),
                            "-frames:v", "1", "-vf", "scale=640:-2",
                            str(folder / f"{i:02d}{tag}_{fmt(t).replace(':', '-')}.jpg")])


def write_clips_txt(moments: list[dict], path: Path) -> None:
    lines = ["# Auto-picked moments. Rename the titles, delete the ones you don't want.",
             "# start - end | title"]
    lines += [f"{fmt(m['start'])} - {fmt(m['end'])} | {m['title'].replace('|', ' ')}" for m in moments]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Find the best moments in a GTA 6 recording.")
    ap.add_argument("recording", type=Path)
    ap.add_argument("--top", type=int, default=8, help="how many moments to pick (default 8)")
    ap.add_argument("--before", type=int, default=20, help="seconds before the peak (default 20)")
    ap.add_argument("--after", type=int, default=10, help="seconds after the peak (default 10)")
    ap.add_argument("--gap", type=int, default=60, help="minimum seconds between moments (default 60)")
    ap.add_argument("--chat", type=Path, help="live_chat.json from fetch.py (adds chat-spike signal)")
    ap.add_argument("--out", type=Path, default=Path("clips.txt"))
    ap.add_argument("--frames", type=Path, help="folder to save 3 pictures per moment")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it and add it to PATH.")
    if not a.recording.exists():
        sys.exit(f"Recording not found: {a.recording}")
    from fetch import chat_per_second
    from transcribe import load_words
    moments = pick_moments(a.recording, top=a.top, before=a.before, after=a.after, gap=a.gap,
                           chat=chat_per_second(a.chat), words=load_words(a.recording))
    if not moments:
        sys.exit("No moments found (is the video very short?)")
    write_clips_txt(moments, a.out)
    if a.frames:
        save_frames(a.recording, moments, a.frames)
    print(f"\nPicked {len(moments)} moments -> {a.out}")
    for m in moments:
        print(f"  {fmt(m['peak'])}  score {m['score']:.2f}  {m['title']}")
    if a.frames:
        print(f"Pictures of each moment: {a.frames}")


if __name__ == "__main__":
    main()
