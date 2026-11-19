"""Build .ass subtitle files: word-by-word highlighted captions and a hook title.

Used by clipper.py; ffmpeg burns the file into the video with its `subtitles` filter.
"""
from __future__ import annotations

from pathlib import Path

HIGHLIGHT = "&H0000E5FF&"  # yellow (ASS colours are &HBBGGRR&)


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    cs = int(round(sec * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def chunk_words(words: list[dict], max_words: int = 3, max_gap: float = 0.6) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    for w in words:
        if chunks and len(chunks[-1]) < max_words and w["s"] - chunks[-1][-1]["e"] <= max_gap:
            chunks[-1].append(w)
        else:
            chunks.append([w])
    return chunks


def write_ass(path: Path, *, vertical: bool, words: list[dict] | None = None, clip_start: float = 0.0,
              clip_end: float = 0.0, hook: str | None = None, hook_seconds: float = 3.0,
              font: str = "Arial", hook_top: int | None = None) -> Path:
    """Words use absolute times from the full recording; clip_start/end select and shift them."""
    w_, h_ = (1080, 1920) if vertical else (1920, 1080)
    cap_size, cap_margin = (84, 560) if vertical else (76, 80)
    hook_size, hook_margin = (72, 170) if vertical else (60, 60)
    if hook_top is not None:
        hook_margin = hook_top
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w_}", f"PlayResY: {h_}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{cap_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,{cap_margin},1",
        f"Style: Hook,{font},{hook_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,0,0,3,18,0,8,70,70,{hook_margin},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook:
        lines.append(f"Dialogue: 1,{_t(0)},{_t(hook_seconds)},Hook,,0,0,0,,{_esc(hook.upper())}")
    clip_words = [w for w in (words or []) if w["e"] > clip_start and w["s"] < clip_end and w["w"]]
    for chunk in chunk_words(clip_words):
        for i, cur in enumerate(chunk):
            start = cur["s"] - clip_start
            end = (chunk[i + 1]["s"] if i + 1 < len(chunk) else cur["e"] + 0.25) - clip_start
            text = " ".join(
                (f"{{\\c{HIGHLIGHT}\\fscx110\\fscy110}}{_esc(w['w'])}{{\\r}}" if j == i else _esc(w["w"]))
                for j, w in enumerate(chunk))
            lines.append(f"Dialogue: 0,{_t(start)},{_t(max(end, start + 0.1))},Cap,,0,0,0,,{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
