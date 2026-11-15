# GTA 6 Question Tracker

A small, **read-only** personal tool that collects the questions people ask about GTA 6 on
Reddit, YouTube and X, and shows which topics come up most.

- **Never writes to any platform** – no posts, comments, votes, likes or messages.
- **Official APIs only** – Reddit Data API (application-only OAuth), YouTube Data API v3, X API v2.
- **No AI** – questions are detected and grouped with simple keyword rules.
- **Privacy-minded** – usernames are not collected; data stays on your computer and is deleted after 30 days.

## What it does

1. **Collect** recent public posts and comments that mention GTA 6:
   - Reddit: sitewide search plus new posts and comments in r/GTA6, r/GTA and r/gaming (~7 requests per run)
   - YouTube: comments on GTA 6 videos from the past week
   - X: recent posts mentioning GTA 6 that contain a question
2. **Filter** to messages phrased as questions (`detector.py`).
3. **Tag** each question with topics such as Release date, PC, Consoles, Price, Map, Story,
   Online, Gameplay, Graphics, Leaks and Mods (`topics.py`).
4. **Report**: builds `gta6_questions.html` (topic chart, most repeated questions, searchable list)
   and `gta6_questions.csv`.

### Data handling

| Stored | Not stored |
|---|---|
| Question text, link, where it was posted, topic tags, timestamps | Usernames, profiles, or any other user data |

- Stored locally in `gta6_questions.db`; nothing is uploaded or shared.
- Records older than 30 days are deleted automatically on every run (`store.py`, `RETENTION_DAYS`).
- Reports show aggregated questions and counts, never who asked.

## Setup

```bash
pip install -r requirements.txt
```

```bash
copy .env.example .env
```

Fill in `.env`. Each platform is skipped if its keys are missing.

| Platform | What you need | Cost |
|---|---|---|
| Reddit | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` – requires approved Reddit Data API access | Free |
| YouTube | `YOUTUBE_API_KEY` (Google Cloud → YouTube Data API v3) | Free (daily quota) |
| X | `X_BEARER_TOKEN` from developer.x.com | Paid API tier required for search |

## Use

```bash
python bot.py scan
```
Scan once and refresh the report.

```bash
python bot.py watch --every 60
```
Scan every 60 minutes while the window is open.

```bash
python bot.py report --days 7
```
Rebuild the report for the last 7 days only.

### Run automatically

Windows Task Scheduler, once per hour:

```bash
schtasks /Create /SC HOURLY /TN "GTA6 Question Tracker" /TR "python \"C:\path\to\gta6bot\bot.py\" scan"
```

Remove it with `schtasks /Delete /TN "GTA6 Question Tracker"`.

## Customise

- Topics: `TOPICS` in `topics.py`
- What counts as a question: `detector.py`
- Search terms and subreddits: `SEARCH_TERMS` and `REDDIT_SUBS` in `sources.py`
