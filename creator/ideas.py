"""Turn the questions the tracker collected into video / Short ideas.

Usage:
    python bot.py scan              # collect questions first (see main README)
    python creator/ideas.py         # writes content_ideas.md
    python creator/ideas.py --days 3

People keep asking these questions on Reddit, YouTube and X, so a video answering them has
a ready audience. Read-only: it only reads the local gta6_questions.db.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import store  # noqa: E402
from report import _norm  # noqa: E402

# Video formats that suit each tracker topic. {q} = a real question people asked.
IDEAS = {
    "Release date / delays": ["Short: 'GTA 6 unlock time in India explained'", "Video: answering '{q}'"],
    "PC version": ["Short: 'Is GTA 6 on PC? What we know'", "Video: answering '{q}'"],
    "Consoles / platforms": ["Video: 'GTA 6 on PS5 vs PS5 Pro – which looks better?'", "Short: answering '{q}'"],
    "Price / editions": ["Short: 'Which GTA 6 edition should you buy in India?'", "Short: answering '{q}'"],
    "Trailers / marketing": ["Video: 'Trailer moments I found in the real game'"],
    "Story & characters": ["Stream: 'Story playthrough part N (no commentary spoilers in title)'",
                           "Short: best Lucia / Jason moment"],
    "Map & setting": ["Video: 'GTA 6 map tour – 10 places you missed'", "Short: answering '{q}'"],
    "Online / multiplayer": ["Stream: 'GTA 6 Online with viewers'", "Short: answering '{q}'"],
    "Gameplay & features": ["Short: '5 GTA 6 tricks nobody tells you'", "Video: answering '{q}'"],
    "Graphics & performance": ["Video: 'GTA 6 graphics settings – fidelity vs performance mode'"],
    "Leaks & rumors": ["Short: 'Leaks that turned out true in the real game'"],
    "Mods": ["Short: answering '{q}'"],
    "Other": ["Short: answering '{q}'"],
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Make content ideas from tracked GTA 6 questions.")
    ap.add_argument("--days", type=int, default=7, help="look at questions from the last N days")
    ap.add_argument("--out", type=Path, default=Path("content_ideas.md"))
    a = ap.parse_args()

    if not store.DB.exists():
        sys.exit("No questions collected yet. Run `python bot.py scan` first.")
    con = store.connect()
    rows = store.all_questions(con, since=time.time() - a.days * 86400)
    if not rows:
        sys.exit(f"No questions in the last {a.days} days. Run `python bot.py scan` first.")

    topic_counts = Counter(t for r in rows for t in r["topics"].split(";"))
    by_topic: dict[str, Counter] = {}
    sample: dict[str, str] = {}
    for r in rows:
        key = _norm(r["text"])
        sample.setdefault(key, r["text"].strip().replace("\n", " ")[:140])
        for t in r["topics"].split(";"):
            by_topic.setdefault(t, Counter())[key] += 1

    lines = [f"# GTA 6 content ideas", "",
             f"From {len(rows)} questions people asked in the last {a.days} days. "
             "Topics are sorted by how often they come up – start at the top.", ""]
    for topic, n in topic_counts.most_common():
        top_qs = [(c, sample[k]) for k, c in by_topic[topic].most_common(3) if k]
        lines += [f"## {topic} — {n} questions", ""]
        for i, tmpl in enumerate(IDEAS.get(topic, IDEAS["Other"])):
            if "{q}" in tmpl:
                if not top_qs:
                    continue
                tmpl = tmpl.format(q=top_qs[min(i, len(top_qs) - 1)][1])
            lines.append(f"- [ ] {tmpl}")
        if top_qs:
            lines += ["", "Most asked:"] + [f"  - ({c}×) {q}" for c, q in top_qs]
        lines.append("")
    a.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {a.out} ({len(topic_counts)} topics)")


if __name__ == "__main__":
    main()
