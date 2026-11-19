"""Download a video (and its live-chat replay, if it was a live stream) with yt-dlp.

Usage:
    python creator/fetch.py https://www.youtube.com/watch?v=VIDEO_ID
    python creator/fetch.py URL --out downloads --max-height 1080 --no-chat

Only download videos you have the rights to use (your own streams), or clips you
re-upload can get copyright strikes. Needs: pip install yt-dlp, and ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def download(url: str, out_dir: Path, max_height: int = 1080, chat: bool = True) -> dict:
    """Returns {"video": Path, "chat": Path | None, "title": str, "id": str}."""
    try:
        import yt_dlp
    except ImportError:
        sys.exit("yt-dlp is not installed. Run: pip install yt-dlp")
    out_dir.mkdir(parents=True, exist_ok=True)
    h = max_height
    opts = {
        "format": f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True, "no_warnings": True, "noprogress": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
    if not video.exists():  # merged file can keep another extension
        found = sorted(out_dir.glob(f"{info['id']}.*"), key=lambda p: p.stat().st_size, reverse=True)
        video = next((p for p in found if p.suffix in (".mp4", ".mkv", ".webm")), video)

    chat_path = None
    if chat and (info.get("was_live") or info.get("live_status") == "was_live"):
        try:
            with yt_dlp.YoutubeDL({"skip_download": True, "writesubtitles": True,
                                   "subtitleslangs": ["live_chat"], "quiet": True, "no_warnings": True,
                                   "outtmpl": str(out_dir / "%(id)s.%(ext)s")}) as ydl:
                ydl.download([url])
            p = out_dir / f"{info['id']}.live_chat.json"
            chat_path = p if p.exists() else None
        except Exception as e:  # chat is a bonus; never fail the download for it
            print(f"(no live chat: {e})")
    return {"video": video, "chat": chat_path, "title": info.get("title", ""), "id": info["id"]}


def chat_per_second(path: Path | None) -> dict[int, int]:
    """Messages per second from a yt-dlp live_chat.json replay file."""
    counts: dict[int, int] = {}
    if not path or not path.exists():
        return counts
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                ms = int(json.loads(line)["replayChatItemAction"]["videoOffsetTimeMsec"])
            except (ValueError, KeyError, TypeError):
                continue
            counts[ms // 1000] = counts.get(ms // 1000, 0) + 1
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description="Download a video with yt-dlp.")
    ap.add_argument("url")
    ap.add_argument("--out", type=Path, default=Path("downloads"))
    ap.add_argument("--max-height", type=int, default=1080)
    ap.add_argument("--no-chat", action="store_true", help="don't download the live-chat replay")
    a = ap.parse_args()
    r = download(a.url, a.out, a.max_height, not a.no_chat)
    print(f"Video: {r['video']}\nTitle: {r['title']}")
    if r["chat"]:
        print(f"Live chat: {r['chat']} ({sum(chat_per_second(r['chat']).values())} messages)")


if __name__ == "__main__":
    main()
