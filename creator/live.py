"""Record a live stream while it's live, and cut clips automatically when something happens.

    python creator/live.py https://www.youtube.com/watch?v=LIVE_ID --channel "My Channel" --lang hi
    python creator/live.py https://www.twitch.tv/yourname --facecam top-right

While the stream runs it:
  - records it to disk in 30-second pieces (nothing is lost if your PC hiccups)
  - follows the live chat (YouTube) and the stream's loudness
  - when chat suddenly explodes or the audio spikes, cuts that moment into a Short + 16:9 video
    within about a minute, with a hook title, into live_session/clips/
Press Ctrl+C (or let the stream end) to stop. You then get live_session/full.mp4 plus its chat
replay, so you can run autoclip.py on it afterwards for captions and the best overall picks.

Only record streams you have the rights to use (your own). Needs yt-dlp and ffmpeg.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clipper import fmt, make_clip, parse_facecam, write_sheet  # noqa: E402
from find_moments import loudness_per_second  # noqa: E402


def stream_url(url: str, max_height: int) -> str:
    try:
        import yt_dlp
    except ImportError:
        sys.exit("yt-dlp is not installed. Run: pip install yt-dlp")
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                           "format": f"best[height<={max_height}]/best"}) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info.get("is_live"):
        print("Note: this video is not live right now. Use autoclip.py for finished videos.")
    if not info.get("url"):
        sys.exit("Could not get the stream address from this link.")
    return info["url"]


def find_timestamp_usec(obj) -> int | None:
    """Live-chat items carry 'timestampUsec' somewhere inside; find it."""
    if isinstance(obj, dict):
        if "timestampUsec" in obj:
            try:
                return int(obj["timestampUsec"])
            except (TypeError, ValueError):
                return None
        for v in obj.values():
            r = find_timestamp_usec(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_timestamp_usec(v)
            if r:
                return r
    return None


class ChatFollower:
    """Reads new lines of a growing live_chat.json and counts messages per recording second."""

    def __init__(self, paths: list[Path], rec_start: float):
        self.paths, self.rec_start, self.pos = paths, rec_start, 0
        self.counts: dict[int, int] = {}

    def poll(self) -> None:
        path = next((p for p in self.paths if p.exists()), None)
        if not path:
            return
        with path.open(encoding="utf-8", errors="ignore") as f:
            f.seek(self.pos)
            while True:
                line = f.readline()
                if not line or not line.endswith("\n"):
                    break
                self.pos = f.tell()
                try:
                    ts = find_timestamp_usec(json.loads(line))
                except json.JSONDecodeError:
                    continue
                t = (ts / 1e6 if ts else time.time()) - self.rec_start
                if t >= 0:
                    self.counts[int(t)] = self.counts.get(int(t), 0) + 1


def spike(history: list[float], current: float, k: float, floor: float, min_hist: int = 6) -> bool:
    if len(history) < min_hist:
        return False  # still learning what "normal" looks like
    mu, sd = statistics.fmean(history), statistics.pstdev(history)
    return current >= max(floor, mu + k * max(sd, 0.5))


def main() -> None:
    ap = argparse.ArgumentParser(description="Record a live stream and auto-clip the big moments.")
    ap.add_argument("url", nargs="?", help="live stream link (YouTube, Twitch, ...)")
    ap.add_argument("--input", help="record from this file/address instead (for testing)")
    ap.add_argument("--chat-file", type=Path, help="follow this live_chat.json instead of downloading chat")
    ap.add_argument("--out", type=Path, default=Path("live_session"))
    ap.add_argument("--segment", type=int, default=30, help="seconds per recorded piece (default 30)")
    ap.add_argument("--before", type=int, default=20)
    ap.add_argument("--after", type=int, default=10)
    ap.add_argument("--gap", type=int, default=60, help="minimum seconds between auto clips")
    ap.add_argument("--sensitivity", type=float, default=2.5,
                    help="lower = more clips (default 2.5 standard deviations above normal)")
    ap.add_argument("--no-chat", action="store_true")
    ap.add_argument("--no-audio-trigger", action="store_true", help="only clip on chat spikes")
    ap.add_argument("--max-height", type=int, default=1080)
    ap.add_argument("--facecam", help="facecam position for Shorts: auto, top-right, or x,y,w,h")
    ap.add_argument("--shorts-style", choices=["blur", "crop", "track"], default="blur")
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--channel", default="my channel")
    a = ap.parse_args()
    if not (a.url or a.input):
        ap.error("give a live stream link")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it and add it to PATH.")

    seg_dir, clip_dir, tmp_dir = a.out / "segments", a.out / "clips", a.out / "tmp"
    for d in (seg_dir, clip_dir, tmp_dir):
        d.mkdir(parents=True, exist_ok=True)
    seg_list = a.out / "segments.csv"
    seg_list.unlink(missing_ok=True)

    source = a.input or stream_url(a.url, a.max_height)
    rec_start = time.time()
    rec = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", *(["-re"] if a.input else []), "-i", source,
         "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-f", "segment", "-segment_time", str(a.segment),
         "-segment_format", "mpegts", "-reset_timestamps", "1", "-segment_list", str(seg_list),
         "-segment_list_type", "csv", str(seg_dir / "seg_%05d.ts")],
        stdin=subprocess.DEVNULL)
    chat_proc = None
    chat_paths = [a.chat_file] if a.chat_file else [a.out / "chat.live_chat.json", a.out / "chat.live_chat.json.part"]
    if a.url and not a.no_chat and not a.chat_file:
        chat_proc = subprocess.Popen([sys.executable, "-m", "yt_dlp", "--skip-download", "--write-subs",
                                      "--sub-langs", "live_chat", "--quiet", "--no-warnings",
                                      "-o", str(a.out / "chat"), a.url],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chat = ChatFollower(chat_paths, rec_start) if (chat_proc or a.chat_file) else None
    facecam = parse_facecam(a.facecam)

    print(f"Recording to {a.out.resolve()}  (Ctrl+C to stop)")
    segments: list[tuple[str, float, float]] = []
    loud_hist: list[float] = []
    chat_hist: list[float] = []
    pending: list[dict] = []
    rows: list[dict] = []
    last_clip = -1e9
    last_chat_check = 0

    def add_segment(r: list[str]) -> None:
        # Piece times may be absolute or restart at 0 for each piece; make them absolute.
        name, s, e = r[0], float(r[1]), float(r[2])
        prev_end = segments[-1][2] if segments else 0.0
        if segments and s < prev_end - 1:
            s, e = s + prev_end, e + prev_end
        segments.append((name, s, e))

    def queue(peak: float, why: str) -> None:
        nonlocal last_clip
        if peak - last_clip < a.gap:
            return
        last_clip = peak
        pending.append({"peak": peak, "why": why})
        print(f"  ★ {why} at {fmt(peak)} – clip coming up")

    def cut_ready(final: bool = False) -> None:
        nonlocal facecam
        recorded = segments[-1][2] if segments else 0
        for m in list(pending):
            start, end = max(0.0, m["peak"] - a.before), m["peak"] + a.after
            if recorded < end and not final:
                continue
            pending.remove(m)
            parts = [s for s in segments if s[2] > start and s[1] < end]
            if not parts:
                continue
            n = len(rows) + 1
            joined = tmp_dir / f"moment_{n:02d}.ts"
            listing = tmp_dir / "concat.txt"
            listing.write_text("".join(f"file '{(seg_dir / p[0]).resolve().as_posix()}'\n" for p in parts),
                               encoding="utf-8")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
                            str(listing), "-c", "copy", str(joined)], check=False)
            if facecam == "auto":
                from facetrack import find_facecam
                facecam = find_facecam(joined, parts[-1][2] - parts[0][1], samples=12)
                print(f"  facecam: {facecam or 'not found, normal layout'}")
            title = f"{m['why']} at {fmt(m['peak'])}"
            local = start - parts[0][1]
            row = make_clip(joined, clip_dir, f"{n:02d}_live_{int(m['peak'])}", local,
                            min(end, parts[-1][2]) - start, title=title, style=a.shorts_style, mute=a.mute,
                            facecam=facecam if facecam != "auto" else None)
            rows.append({"n": n, "title": title, "dur": end - start, **row})
            write_sheet(rows, clip_dir, a.lang, a.channel)
            joined.unlink(missing_ok=True)
            print(f"  ✓ clip {n} saved: {row.get('short') or row['wide']}")

    try:
        while True:
            alive = rec.poll() is None
            # New finished pieces of the recording.
            if seg_list.exists():
                with seg_list.open(newline="") as f:
                    rows_csv = list(csv.reader(f))
                for r in rows_csv[len(segments):]:
                    add_segment(r)
                    if not a.no_audio_trigger:
                        loud = loudness_per_second(seg_dir / r[0])
                        for sec in sorted(loud):
                            v = loud[sec]
                            t = segments[-1][1] + sec
                            if spike(loud_hist[-300:], v, a.sensitivity + 0.5, -25, min_hist=45) and v > -60:
                                queue(t, "Big moment")
                            loud_hist.append(v)
            # Chat: compare the last 10 seconds with the last 5 minutes.
            if chat:
                chat.poll()
                now = time.time() - rec_start
                if now - last_chat_check >= 10:
                    last_chat_check = now
                    cur = sum(chat.counts.get(int(now) - i, 0) for i in range(1, 11))
                    if spike(chat_hist[-30:], cur, a.sensitivity, 8):
                        queue(max(0.0, now - 9), "Chat went crazy")
                    chat_hist.append(cur)
            cut_ready()
            if not alive:
                print("Stream ended.")
                break
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if rec.poll() is None:
            rec.terminate()
            try:
                rec.wait(10)
            except subprocess.TimeoutExpired:
                rec.kill()
        if chat_proc and chat_proc.poll() is None:
            chat_proc.terminate()

    # Pick up the last piece written while stopping, then finish pending clips.
    if seg_list.exists():
        with seg_list.open(newline="") as f:
            for r in list(csv.reader(f))[len(segments):]:
                add_segment(r)
    cut_ready(final=True)

    if segments:
        listing = tmp_dir / "concat.txt"
        listing.write_text("".join(f"file '{(seg_dir / s[0]).resolve().as_posix()}'\n" for s in segments),
                           encoding="utf-8")
        full = a.out / "full.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", str(full)], check=False)
        if chat and chat.counts:
            chat.poll()
            with (a.out / "full.live_chat.json").open("w", encoding="utf-8") as f:
                for sec, n in sorted(chat.counts.items()):
                    for _ in range(n):
                        f.write(json.dumps({"replayChatItemAction": {"videoOffsetTimeMsec": str(sec * 1000)}}) + "\n")
        print(f"\nFull recording: {full}  ({fmt(segments[-1][2])})")
        print(f"Auto clips: {len(rows)} in {clip_dir}")
        print(f"For captions + the best overall picks, run:\n  python creator/autoclip.py {full} --lang {a.lang}")
        print(f"When full.mp4 looks right you can delete {seg_dir} to free space.")
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
