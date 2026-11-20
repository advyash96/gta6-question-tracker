"""Cut GTA 6 recordings into upload-ready clips: normal 16:9 videos and vertical Shorts.

Needs ffmpeg on PATH (https://ffmpeg.org/download.html).

Usage:
    python creator/clipper.py recording.mp4 clips.txt
    python creator/clipper.py recording.mp4 clips.txt --captions --lang hi --facecam top-right

clips.txt has one clip per line:   start - end | title
    12:30 - 13:05 | Insane police chase in Vice City
Lines starting with # are ignored. Times can be SS, MM:SS or HH:MM:SS.

For every clip it writes, into the output folder (default: clips/):
    01_insane-police-chase_16x9.mp4   full-width video
    01_insane-police-chase_short.mp4  1080x1920 vertical for YouTube Shorts / Instagram Reels
and one upload_sheet.md with a ready title, description and hashtags for each clip.

Extras:
    --captions        burn word-by-word captions from what you say (needs: pip install faster-whisper)
    --facecam POS     Shorts get your facecam on top and gameplay below. POS = auto (found by face
                      tracking), top-left, top-right,
                      bottom-left, bottom-right, or x,y,w,h in percent of the frame, e.g. 75,0,25,25
    --shorts-style track   vertical crop that follows your face (full-screen camera footage)
    --no-hook         don't show the clip title as a big text hook for the first 3 seconds
    --keep-bars       don't auto-remove black bars

Nothing is uploaded anywhere: you upload the files yourself in YouTube Studio or the YouTube app.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from captions import write_ass  # noqa: E402

SHORTS_MAX_SECONDS = 180  # YouTube Shorts limit; keep most Shorts 20-60 s anyway
LINE_RX = re.compile(r"^\s*([\d:.]+)\s*[-–]\s*([\d:.]+)\s*(?:\|\s*(.*))?$")
FACECAM_PRESETS = {"top-left": (0, 0, 25, 25), "top-right": (75, 0, 25, 25),
                   "bottom-left": (0, 75, 25, 25), "bottom-right": (75, 75, 25, 25)}
VIDEO_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-movflags", "+faststart"]


def to_seconds(t: str) -> float:
    parts = [float(p) for p in t.strip().split(":")]
    if len(parts) > 3:
        raise ValueError(f"bad time: {t}")
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return secs


def fmt(secs: float) -> str:
    s = int(secs)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "clip"


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


def run(cmd: list[str], cwd: Path | None = None) -> str:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
    if res.returncode != 0:
        sys.exit("ffmpeg failed:\n" + res.stderr[-2000:])
    return res.stderr


def probe_size(src: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", str(src)],
                         capture_output=True, text=True).stdout
    first = next(ln for ln in out.splitlines() if ln.strip()).strip().split(",")
    return int(first[0]), int(first[1])


def detect_bars(src: Path, at: float) -> tuple[int, int, int, int] | None:
    """Returns (w, h, x, y) to crop away black bars, or None if there are none."""
    err = run(["ffmpeg", "-hide_banner", "-ss", f"{at}", "-i", str(src), "-t", "8", "-an",
               "-vf", "cropdetect=24:2:0", "-f", "null", "-"])
    found = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", err)
    if not found:
        return None
    w, h, x, y = map(int, found[-1])
    W, H = probe_size(src)
    if w * h >= 0.96 * W * H or w < W * 0.3 or h < H * 0.3:
        return None
    return w, h, x, y


def audio_args(mute: bool) -> list[str]:
    if mute:
        return ["-an"]
    # Loudness-normalise to YouTube's level so clips aren't too quiet or clipping.
    return ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]


def even(n: float) -> int:
    return max(2, int(round(n / 2)) * 2)


def facecam_box(size: tuple[int, int], facecam: tuple) -> tuple[int, int, int, int, int]:
    """Facecam crop (w, h, x, y) in pixels plus its height on the Short."""
    W, H = size
    fx, fy = even(W * facecam[0] / 100), even(H * facecam[1] / 100)
    fw, fh = min(even(W * facecam[2] / 100), W - fx), min(even(H * facecam[3] / 100), H - fy)
    return fw, fh, fx, fy, min(even(1080 * fh / fw), 760)


def short_filter(style: str, size: tuple[int, int], facecam: tuple | None) -> str:
    if facecam:
        fw, fh, fx, fy, top_h = facecam_box(size, facecam)
        bot_h = 1920 - top_h
        return (f"split[c][g];[c]crop={fw}:{fh}:{fx}:{fy},scale=1080:{top_h}[top];"
                f"[g]scale=1080:{bot_h}:force_original_aspect_ratio=increase,crop=1080:{bot_h}[bot];"
                f"[top][bot]vstack,setsar=1")
    if style == "track":
        return "TRACK"
    if style == "crop":
        return "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    return ("split[a][b];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")


def make_clip(src: Path, out_dir: Path, base: str, start: float, dur: float, *, title: str,
              shorts: bool = True, style: str = "blur", mute: bool = False, words: list | None = None,
              hook: bool = True, facecam: tuple | None = None, bars: tuple | None = None,
              font: str = "Arial") -> dict:
    """Cut one clip; returns the file names written."""
    src = src.resolve()
    pre = f"crop={bars[0]}:{bars[1]}:{bars[2]}:{bars[3]}," if bars else ""
    size = (bars[0], bars[1]) if bars else probe_size(src)
    seek = ["-ss", f"{start}", "-i", str(src), "-t", f"{dur}"]
    row = {"wide": f"{base}_16x9.mp4"}

    subs = ""
    if words:
        ass = write_ass(out_dir / f"{base}_16x9.ass", vertical=False, words=words,
                        clip_start=start, clip_end=start + dur, font=font)
        subs = f",subtitles={ass.name}"
    run(["ffmpeg", "-y", "-loglevel", "error", *seek,
         "-vf", f"{pre}scale=-2:'min(1080,ih)'{subs}", *VIDEO_ARGS, *audio_args(mute), row["wide"]], cwd=out_dir)

    if shorts and dur <= SHORTS_MAX_SECONDS:
        row["short"] = f"{base}_short.mp4"
        sf = short_filter(style, size, facecam)
        if sf == "TRACK":
            from facetrack import track_crop, write_sendcmd
            tr = track_crop(src, start, dur, size[0], size[1], bars)
            if tr:
                cw, pts = tr
                cmd = write_sendcmd(out_dir / f"{base}_track.cmd", pts)
                sf = (f"sendcmd=f={cmd.name},crop@track=w={cw}:h={size[1]}:x={pts[0][1]}:y=0,"
                      f"scale=1080:1920,setsar=1")
            else:
                print("    no face found: using a centre crop")
                sf = short_filter("crop", size, None)
        vf = f"[0:v]{pre}{sf}"
        if words or hook:
            ass = write_ass(out_dir / f"{base}_short.ass", vertical=True, words=words, clip_start=start,
                            clip_end=start + dur, hook=title if hook else None, font=font,
                            hook_top=facecam_box(size, facecam)[4] + 50 if facecam else None)
            vf += f",subtitles={ass.name}"
        run(["ffmpeg", "-y", "-loglevel", "error", *seek, "-filter_complex", vf,
             *VIDEO_ARGS, *audio_args(mute), row["short"]], cwd=out_dir)
    elif shorts:
        print(f"    skipped Short: {dur:.0f}s is longer than {SHORTS_MAX_SECONDS}s")
    for f in [*out_dir.glob(f"{base}_*.ass"), *out_dir.glob(f"{base}_*.cmd")]:
        f.unlink()
    return row


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
    lang = lang if lang in DESCRIPTIONS else "en"
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


def parse_facecam(v: str | None) -> tuple | None:
    if not v:
        return None
    if v == "auto":
        return "auto"
    if v in FACECAM_PRESETS:
        return FACECAM_PRESETS[v]
    try:
        x, y, w, h = (float(p) for p in v.split(","))
    except ValueError:
        sys.exit("--facecam must be auto, top-left/top-right/bottom-left/bottom-right or x,y,w,h in percent")
    return x, y, w, h


def add_common_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--out", type=Path, default=Path("clips"), help="output folder (default: clips)")
    ap.add_argument("--shorts-style", choices=["blur", "crop", "track"], default="blur",
                    help="blur = whole frame on blurred background; crop = fill screen with the centre; "
                         "track = fill screen and follow your face (camera footage)")
    ap.add_argument("--no-shorts", action="store_true", help="only make the 16:9 versions")
    ap.add_argument("--mute", action="store_true",
                    help="remove all audio (use if a clip has copyrighted in-game radio music)")
    ap.add_argument("--captions", action="store_true", help="burn word-by-word captions (faster-whisper)")
    ap.add_argument("--model", default="small", help="speech model for --captions (default: small)")
    ap.add_argument("--translate", action="store_true",
                    help="English captions even if you speak Hindi (translates your speech)")
    ap.add_argument("--facecam", help="facecam position for Shorts: auto (face tracking finds it), top-right, or 75,0,25,25")
    ap.add_argument("--no-hook", action="store_true", help="no title text in the first 3 s of Shorts")
    ap.add_argument("--keep-bars", action="store_true", help="don't auto-remove black bars")
    ap.add_argument("--font", default="Arial", help="caption font (Hindi on Windows: 'Nirmala UI')")
    ap.add_argument("--lang", default="en", help="speech + upload-sheet language: en or hi")
    ap.add_argument("--channel", default="my channel", help="your channel name for descriptions")


def cut_all(src: Path, clips: list[dict], a: argparse.Namespace, words: list | None = None) -> Path:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it from https://ffmpeg.org/download.html and add it to PATH.")
    if a.captions and words is None:
        from transcribe import transcribe
        words = transcribe(src, None if a.translate or a.lang == "en" else a.lang, a.model, a.translate)
    bars = None if a.keep_bars else detect_bars(src, clips[0]["start"])
    if bars:
        print(f"Removing black bars (crop to {bars[0]}x{bars[1]})")
    facecam = parse_facecam(a.facecam)
    if facecam == "auto":
        from facetrack import find_facecam
        from find_moments import duration
        print("Looking for your facecam...")
        facecam = find_facecam(src, duration(src), bars)
        print(f"  found at {facecam}" if facecam else "  no steady facecam: using the normal layout")
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, c in enumerate(clips, 1):
        dur = c["end"] - c["start"]
        base = f"{n:02d}_{slug(c['title'])}"
        print(f"[{n}/{len(clips)}] {c['title']}  {fmt(c['start'])}–{fmt(c['end'])} ({dur:.0f}s)")
        row = make_clip(src, a.out, base, c["start"], dur, title=c["title"], shorts=not a.no_shorts,
                        style=a.shorts_style, mute=a.mute, words=words if a.captions else None,
                        hook=not a.no_hook, facecam=facecam, bars=bars, font=a.font)
        rows.append({"n": n, "title": c["title"], "dur": dur, **row})
    sheet = write_sheet(rows, a.out, a.lang, a.channel)
    print(f"\nDone: {len(rows)} clip(s) in {a.out.resolve()}\nTitles & descriptions: {sheet}")
    return sheet


def main() -> None:
    ap = argparse.ArgumentParser(description="Cut GTA 6 recordings into YouTube videos and Shorts.")
    ap.add_argument("recording", type=Path, help="PS5 recording or downloaded stream VOD (.mp4/.webm)")
    ap.add_argument("clips", type=Path, help="text file of 'start - end | title' lines")
    add_common_args(ap)
    a = ap.parse_args()
    if not a.recording.exists():
        sys.exit(f"Recording not found: {a.recording}")
    cut_all(a.recording, parse_clips(a.clips), a)


if __name__ == "__main__":
    main()
