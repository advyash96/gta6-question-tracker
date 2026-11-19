"""Cut GTA 6 recordings into upload-ready clips: normal 16:9 videos and vertical Shorts.

Needs ffmpeg installed and on PATH (https://ffmpeg.org/download.html).

Usage:
    python creator/clipper.py recording.mp4 clips.txt
    python creator/clipper.py recording.mp4 clips.txt --shorts-style crop --mute --lang hi

clips.txt has one clip per line:   start - end | title
    12:30 - 13:05 | Insane police chase in Vice City
    1:02:10 - 1:02:40 | Funniest NPC reaction
Lines starting with # are ignored. Times can be SS, MM:SS or HH:MM:SS.

For every clip it writes, into the output folder (default: clips/):
    01_insane-police-chase_16x9.mp4   full-width video for a normal upload / compilation
    01_insane-police-chase_short.mp4  1080x1920 vertical for YouTube Shorts / Instagram Reels
and one upload_sheet.md with a ready title, description and hashtags for each clip.

Nothing is uploaded anywhere: you upload the files yourself in YouTube Studio or the YouTube app.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SHORTS_MAX_SECONDS = 180  # YouTube Shorts limit; keep most Shorts 20-60 s anyway

LINE_RX = re.compile(r"^\s*([\d:.]+)\s*[-–]\s*([\d:.]+)\s*(?:\|\s*(.*))?$")


def to_seconds(t: str) -> float:
    parts = [float(p) for p in t.strip().split(":")]
    if len(parts) > 3:
        raise ValueError(f"bad time: {t}")
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return secs


def parse_clips(path: Path) -> list[dict]:
    clips = []
    for n, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE_RX.match(line)
        if not m:
            sys.exit(f"{path}:{n}: can't read this line (expected 'start - end | title'):\n  {raw}")
        start, end = to_seconds(m.group(1)), to_seconds(m.group(2))
        if end <= start:
            sys.exit(f"{path}:{n}: end time must be after start time")
        clips.append({"start": start, "end": end, "title": (m.group(3) or f"Clip {len(clips) + 1}").strip()})
    if not clips:
        sys.exit(f"No clips found in {path}")
    return clips


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "clip"


def audio_args(mute: bool) -> list[str]:
    if mute:
        return ["-an"]
    # Loudness-normalise to YouTube's level so clips aren't too quiet or clipping.
    return ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]


VIDEO_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-movflags", "+faststart"]


def run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        sys.exit("ffmpeg failed:\n" + res.stderr[-2000:])


def cut_wide(src: Path, out: Path, start: float, dur: float, mute: bool) -> None:
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start}", "-i", str(src), "-t", f"{dur}",
         "-vf", "scale=-2:'min(1080,ih)'", *VIDEO_ARGS, *audio_args(mute), str(out)])


def cut_short(src: Path, out: Path, start: float, dur: float, mute: bool, style: str) -> None:
    if style == "crop":
        # Fill the whole phone screen with the centre of the frame (best when action is centred).
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    else:
        # Whole frame in the middle, blurred copy behind it (nothing gets cut off).
        vf = ("split[a][b];"
              "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
              "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start}", "-i", str(src), "-t", f"{dur}",
         "-filter_complex", f"[0:v]{vf}", *VIDEO_ARGS, *audio_args(mute), str(out)])


def fmt(secs: float) -> str:
    s = int(secs)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


DESCRIPTIONS = {
    "en": ("{title} in GTA 6 🔥\n\nFull GTA 6 streams on {channel} – subscribe and turn on notifications "
           "so you don't miss the next one.\n\n"),
    "hi": ("GTA 6 mein {title} 🔥\n\nPoore GTA 6 live streams {channel} par – channel ko subscribe karo "
           "aur bell icon dabao taaki agla stream miss na ho.\n\n"),
}
HASHTAGS = {
    "en": "#GTA6 #GTAVI #GrandTheftAuto6 #PS5 #Gaming",
    "hi": "#GTA6 #GTA6India #GTAVI #HindiGaming #PS5",
}


def write_sheet(rows: list[dict], out_dir: Path, lang: str, channel: str) -> Path:
    lines = ["# Upload sheet", "",
             "Copy each block into YouTube Studio (or the YouTube app) when you upload the file.", ""]
    for r in rows:
        desc = DESCRIPTIONS[lang].format(title=r["title"], channel=channel)
        lines += [f"## {r['n']:02d}. {r['title']}  ({fmt(r['dur'])})", ""]
        if r.get("short"):
            lines += [f"**Short:** `{r['short']}`", "",
                      f"- Title: `{r['title'][:90]} #GTA6 #Shorts`",
                      f"- Description:\n\n```\n{desc}{HASHTAGS[lang]} #Shorts\n```", ""]
        lines += [f"**Video:** `{r['wide']}`", "",
                  f"- Title: `{r['title'][:80]} | GTA 6`",
                  f"- Description:\n\n```\n{desc}{HASHTAGS[lang]}\n```",
                  "- Tags: GTA 6, GTA VI, Grand Theft Auto 6, GTA 6 gameplay, PS5", ""]
    path = out_dir / "upload_sheet.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Cut GTA 6 recordings into YouTube videos and Shorts.")
    ap.add_argument("recording", type=Path, help="PS5 recording or downloaded stream VOD (.mp4/.webm)")
    ap.add_argument("clips", type=Path, help="text file of 'start - end | title' lines")
    ap.add_argument("--out", type=Path, default=Path("clips"), help="output folder (default: clips)")
    ap.add_argument("--shorts-style", choices=["blur", "crop"], default="blur",
                    help="blur = whole frame on blurred background; crop = fill screen with the centre")
    ap.add_argument("--no-shorts", action="store_true", help="only make the 16:9 versions")
    ap.add_argument("--mute", action="store_true",
                    help="remove all audio (use if a clip has copyrighted in-game radio music)")
    ap.add_argument("--lang", choices=["en", "hi"], default="en", help="language for upload_sheet.md")
    ap.add_argument("--channel", default="my channel", help="your channel name for descriptions")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it from https://ffmpeg.org/download.html and add it to PATH.")
    if not a.recording.exists():
        sys.exit(f"Recording not found: {a.recording}")

    clips = parse_clips(a.clips)
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, c in enumerate(clips, 1):
        dur = c["end"] - c["start"]
        base = f"{n:02d}_{slug(c['title'])}"
        print(f"[{n}/{len(clips)}] {c['title']}  {fmt(c['start'])}–{fmt(c['end'])} ({dur:.0f}s)")
        wide = a.out / f"{base}_16x9.mp4"
        cut_wide(a.recording, wide, c["start"], dur, a.mute)
        row = {"n": n, "title": c["title"], "dur": dur, "wide": wide.name}
        if not a.no_shorts:
            if dur > SHORTS_MAX_SECONDS:
                print(f"    skipped Short: {dur:.0f}s is longer than {SHORTS_MAX_SECONDS}s")
            else:
                short = a.out / f"{base}_short.mp4"
                cut_short(a.recording, short, c["start"], dur, a.mute, a.shorts_style)
                row["short"] = short.name
        rows.append(row)

    sheet = write_sheet(rows, a.out, a.lang, a.channel)
    print(f"\nDone: {len(rows)} clip(s) in {a.out.resolve()}\nTitles & descriptions: {sheet}")


if __name__ == "__main__":
    main()
