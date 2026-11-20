"""One command: video link or file in, finished Shorts + videos + upload sheet out.

    python creator/autoclip.py https://www.youtube.com/watch?v=VIDEO_ID --lang hi --channel "My Channel"
    python creator/autoclip.py stream.mp4 --top 10 --facecam top-right
    python creator/autoclip.py LINK --translate --lang en    # you speak Hindi, captions in English

Steps:
  1. download the video + live-chat replay (yt-dlp)         skipped for a local file
  2. transcribe your voice with word timings (faster-whisper) skip with --no-speech
  3. find the best moments (loudness, action, chat spikes, hype words)
  4. cut each one into a 16:9 video and a 9:16 Short with captions and a hook title
  5. write clips.txt (edit + re-run clipper.py to fine-tune) and upload_sheet.md

Only clip videos you have the rights to (your own streams).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clipper import add_common_args, cut_all  # noqa: E402
from fetch import chat_per_second, download  # noqa: E402
from find_moments import pick_moments, save_frames, write_clips_txt  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Link or file in, finished clips out.")
    ap.add_argument("source", help="YouTube/Twitch link, or a local video file")
    ap.add_argument("--top", type=int, default=8, help="how many clips (default 8)")
    ap.add_argument("--before", type=int, default=20)
    ap.add_argument("--after", type=int, default=10)
    ap.add_argument("--gap", type=int, default=60)
    ap.add_argument("--no-speech", action="store_true", help="skip transcription (no captions/hype words)")
    ap.add_argument("--downloads", type=Path, default=Path("downloads"))
    add_common_args(ap)
    a = ap.parse_args()

    chat = {}
    if a.source.startswith(("http://", "https://")):
        print("Downloading...")
        r = download(a.source, a.downloads)
        src = r["video"]
        chat = chat_per_second(r["chat"])
        print(f"Got: {r['title']}  ({src})" + (f", {sum(chat.values())} chat messages" if chat else ""))
    else:
        src = Path(a.source)
        if not src.exists():
            sys.exit(f"File not found: {src}")
        side = src.with_suffix(".live_chat.json")
        chat = chat_per_second(side if side.exists() else None)

    words = None
    if not a.no_speech:
        from transcribe import transcribe
        words = transcribe(src, None if a.translate or a.lang == "en" else a.lang, a.model, a.translate)
        a.captions = True

    moments = pick_moments(src, top=a.top, before=a.before, after=a.after, gap=a.gap,
                           chat=chat, words=words)
    if not moments:
        sys.exit("No moments found (is the video very short?)")
    a.out.mkdir(parents=True, exist_ok=True)
    write_clips_txt(moments, a.out / "clips.txt")
    save_frames(src, moments, a.out / "frames")
    cut_all(src, moments, a, words=words)
    print(f"Moment list (edit and re-run clipper.py to adjust): {a.out / 'clips.txt'}")


if __name__ == "__main__":
    main()
