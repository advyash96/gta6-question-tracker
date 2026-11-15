"""Local SQLite store of GTA 6 questions.

Data handling:
- Only the question text, a link to it, where it was posted and topic tags are stored.
  No usernames or other user data.
- Everything older than RETENTION_DAYS is deleted automatically on every run.
"""
import os
import sqlite3
import time
from pathlib import Path

DB = Path(os.getenv("GTA6BOT_DB", Path(__file__).with_name("gta6_questions.db")))
RETENTION_DAYS = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    platform TEXT, text TEXT, url TEXT, context TEXT,
    topics TEXT,          -- semicolon-separated
    posted TEXT,          -- when it was posted (as given by the platform)
    found_at REAL         -- when we collected it (unix time)
);
-- IDs of non-question items already checked, so they aren't re-processed
CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, found_at REAL);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    purge_old(con)
    return con


def purge_old(con) -> int:
    cutoff = time.time() - RETENTION_DAYS * 86400
    n = con.execute("DELETE FROM questions WHERE found_at < ?", (cutoff,)).rowcount
    con.execute("DELETE FROM seen WHERE found_at < ?", (cutoff,))
    con.commit()
    return n


def is_seen(con, item_id: str) -> bool:
    return (con.execute("SELECT 1 FROM questions WHERE id=?", (item_id,)).fetchone() is not None
            or con.execute("SELECT 1 FROM seen WHERE id=?", (item_id,)).fetchone() is not None)


def mark_seen(con, item_id: str) -> None:
    con.execute("INSERT OR IGNORE INTO seen (id, found_at) VALUES (?, ?)", (item_id, time.time()))


def save_question(con, item: dict, topics: list[str]) -> None:
    con.execute(
        "INSERT OR REPLACE INTO questions (id, platform, text, url, context, topics, posted, found_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (item["id"], item["platform"], item["text"], item["url"], item.get("context"),
         ";".join(topics), str(item.get("created", "")), time.time()),
    )


def all_questions(con, since: float = 0) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM questions WHERE found_at >= ? ORDER BY found_at DESC", (since,)
    ).fetchall()
