"""Is this text a question about GTA 6? Simple keyword rules, no AI."""
import re

GTA6_RE = re.compile(r"\b(gta\s?(6|vi)|grand theft auto\s?(6|vi))\b", re.I)
QUESTION_WORDS = re.compile(
    r"^\s*(who|what|when|where|why|how|is|are|will|would|can|could|does|do|did|should|has|have|any(one|body))\b",
    re.I | re.M,
)


def is_gta6_question(text: str, context: str = "") -> bool:
    if not text or len(text) < 8 or len(text) > 4000:
        return False
    # Mentions GTA 6 itself, or is a comment under a GTA 6 post/video.
    if not (GTA6_RE.search(text) or GTA6_RE.search(context or "")):
        return False
    return "?" in text or bool(QUESTION_WORDS.search(text))
