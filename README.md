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

## Creator tools (separate from the tracker)

`creator/` turns your GTA 6 streams into Shorts and videos. Everything runs on your own computer;
nothing is uploaded or posted for you.

**Easiest (Windows): double-click `AutoClip.bat`, paste a YouTube link, get finished clips.** It installs Python, ffmpeg and Deno on first run.

**One command – link or file in, finished clips out:**

```bash
pip install -r creator/requirements.txt      # yt-dlp + faster-whisper (also needs ffmpeg)
python creator/autoclip.py https://www.youtube.com/watch?v=VIDEO_ID --lang hi --channel "My Channel"
python creator/autoclip.py stream.mp4 --top 10 --facecam auto --font "Nirmala UI"
python creator/live.py https://www.youtube.com/watch?v=LIVE_ID --facecam auto   # while you're live
```

You get, in `clips/`: a 16:9 video and a 9:16 Short per moment (captions, hook title, loudness
normalised), `upload_sheet.md` with titles/descriptions/hashtags, `clips.txt` and `frames/` to review.

| Tool | What it does |
|---|---|
| `autoclip.py` | Whole pipeline: download → transcribe → find moments → cut → upload sheet |
| `live.py` | Records a live stream as it happens and cuts a clip within about a minute whenever chat explodes or the audio spikes; saves `full.mp4` + chat replay at the end |
| `facetrack.py` | Face tracking: finds your facecam automatically (`--facecam auto`) and keeps a vertical crop on your face (`--shorts-style track`) |
| `fetch.py` | Download a video + its live-chat replay with yt-dlp |
| `transcribe.py` | Offline speech-to-text with word timings (faster-whisper; Hindi and English) |
| `find_moments.py` | Scores every second by loudness, fast action, chat spikes and hype words ("bhai", "kya", "oh my god"); writes `clips.txt` |
| `clipper.py` | Cuts `clips.txt` into videos + Shorts: word-by-word captions, hook title, facecam-on-top layout (manual or `auto`), face-tracking crop, black-bar removal, `--mute` for radio music |
| `clip-marker.html` | Phone page: tap during a live stream to mark moments, copy a ready `clips.txt` |
| `ideas.py` | Turns questions collected by the tracker into video ideas |
| `STREAMING_PLAN.md` | PS5 → YouTube plan, weekly schedule, clip and upload workflow |

Only clip videos you have the rights to – your own streams.
