"""GTA 6 question tracker - read-only. Collects what people ask; never posts anything.

    python bot.py scan                  # scan Reddit, YouTube and X once, then refresh the report
    python bot.py scan -p reddit        # only some platforms
    python bot.py watch --every 30      # keep scanning every 30 minutes
    python bot.py report --days 7       # rebuild the report for the last 7 days
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

try:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")
except ImportError:
    pass

import report
import store
from detector import is_gta6_question
from sources import SCANNERS
from topics import tag

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_HTML = HERE / "gta6_questions.html"
OUT_CSV = HERE / "gta6_questions.csv"


def scan(platforms: list[str]) -> int:
    con = store.connect()
    total = 0
    for name in platforms:
        try:
            items = SCANNERS[name]()
        except Exception as e:  # one broken platform shouldn't stop the others
            print(f"[{name}] skipped: {e}")
            continue
        found = 0
        for item in items:
            if store.is_seen(con, item["id"]):
                continue
            if is_gta6_question(item["text"], item.get("context", "")):
                store.save_question(con, item, tag(item["text"] + " " + item.get("context", "")))
                found += 1
            else:
                store.mark_seen(con, item["id"])
        con.commit()
        total += found
        print(f"[{name}] {len(items)} fetched, {found} new GTA 6 questions saved")
    return total


def build_report(days: int | None) -> None:
    con = store.connect()
    since = time.time() - days * 86400 if days else 0
    rows = store.all_questions(con, since)
    report.write_csv(rows, OUT_CSV)
    report.write_html(rows, OUT_HTML, days)
    print(f"Report: {OUT_HTML.name} and {OUT_CSV.name} ({len(rows)} questions)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect GTA 6 questions from Reddit, YouTube and X")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "watch"):
        p = sub.add_parser(name)
        p.add_argument("-p", "--platforms", nargs="+", default=list(SCANNERS), choices=list(SCANNERS))
        p.add_argument("--days", type=int, default=None, help="limit the report to the last N days")
        if name == "watch":
            p.add_argument("--every", type=float, default=30, help="minutes between scans")
    r = sub.add_parser("report")
    r.add_argument("--days", type=int, default=None)
    args = ap.parse_args()

    if args.cmd == "scan":
        scan(args.platforms)
        build_report(args.days)
    elif args.cmd == "watch":
        while True:
            scan(args.platforms)
            build_report(args.days)
            print(f"Next scan in {args.every:g} min (Ctrl+C to stop)")
            time.sleep(args.every * 60)
    else:
        build_report(args.days)


if __name__ == "__main__":
    main()
