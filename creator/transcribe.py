"""Speech-to-text with word timings (faster-whisper), cached next to the video.

Usage:
    python creator/transcribe.py stream.mp4               # auto-detect language
    python creator/transcribe.py stream.mp4 --lang hi     # Hindi
    python creator/transcribe.py stream.mp4 --model medium

Writes stream.words.json: [{"s": start, "e": end, "w": "word"}, ...]. Runs offline on your
CPU (or GPU); the model downloads once on first use. Needs: pip install faster-whisper
Models: tiny / base / small (default, good balance) / medium / large-v3 (best, slow on CPU).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def words_path(video: Path) -> Path:
    return video.with_suffix(".words.json")


def transcribe(video: Path, lang: str | None = None, model: str = "small") -> list[dict]:
    cache = words_path(video)
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper is not installed. Run: pip install faster-whisper")
    print(f"Transcribing {video.name} with the '{model}' model (first run downloads it)...")
    m = WhisperModel(model, device="auto", compute_type="int8")
    segments, info = m.transcribe(str(video), language=lang, word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"s": round(w.start, 2), "e": round(w.end, 2), "w": w.word.strip()})
        print(f"\r  {seg.end / 60:.1f} min done", end="", flush=True)
    print(f"\n  language: {info.language}, {len(words)} words")
    cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


def load_words(video: Path) -> list[dict]:
    p = words_path(video)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a video with word timings.")
    ap.add_argument("video", type=Path)
    ap.add_argument("--lang", help="language code, e.g. hi or en (default: auto-detect)")
    ap.add_argument("--model", default="small")
    a = ap.parse_args()
    words = transcribe(a.video, a.lang, a.model)
    print(f"Saved {len(words)} words to {words_path(a.video)}")


if __name__ == "__main__":
    main()
