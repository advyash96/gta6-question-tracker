# GTA 6 Streaming Plan (PS5, India, YouTube)

The goal: grow a GTA 6 channel in the first 4–6 weeks after launch, while interest is at its peak,
and turn it into income through YouTube monetization and later brand deals.

**Core idea:** stream live for long sessions, then cut each stream into 3–5 Shorts and 1 highlight
video. Streams build loyal viewers; Shorts bring in new ones.

---

## 1. One-time setup (≈30 minutes)

### PS5 settings
- **Settings → Captures and Broadcasts → Captures**
  - File type: **MP4** (works everywhere; WebM is harder to edit)
  - Video resolution: **1080p** (4K files are huge and Shorts are 1080p anyway)
  - Include your microphone audio: **On** (your commentary is the content)
- **Settings → Captures and Broadcasts → Broadcasts** → link your **YouTube** account.
- Plug in a headset with a mic. A cheap USB/3.5 mm headset is fine to start.
- Optional: a PS5 HD camera for facecam. Facecam streams usually hold viewers better.

### YouTube channel
- Verify your phone number in YouTube Studio: needed for live streaming and custom thumbnails.
  **The first live stream needs 24 hours after enabling, so do this today.**
- Channel name + banner that says *GTA 6* and your language (e.g. "GTA 6 Hindi Live").
- Make 3 playlists: **GTA 6 Story Playthrough**, **GTA 6 Shorts**, **GTA 6 Tips & Guides**.

### On your PC/laptop
- Install **ffmpeg** (https://ffmpeg.org/download.html) and Python 3.
- The tools in this folder:
  - `clipper.py` cuts recordings into upload-ready videos + Shorts and writes titles/descriptions
  - `ideas.py` turns the questions the tracker collects into video ideas

### Upgrade later (once you earn)
Capture card (Elgato / a ₹2–4k HDMI USB capture card) + OBS on a PC: facecam overlays,
alerts, better quality, and you can stream to YouTube and Instagram at the same time.

---

## 2. Weekly schedule (first 4 weeks)

Consistency beats length. Pick fixed times and put them in your channel banner.

| Day | What | Length |
|---|---|---|
| Mon | Story playthrough stream | 3–4 h |
| Tue | Cut clips from Monday, post 2 Shorts | 1 h of editing |
| Wed | Story playthrough stream | 3–4 h |
| Thu | 1 guide video (from `ideas.py`) + 1 Short | — |
| Fri | Free-roam / chaos / viewer challenges stream | 3 h |
| Sat | Highlight video of the week + 2 Shorts | — |
| Sun | Rest, or GTA Online with viewers (once available) | — |

**Evening IST (8 PM – 12 AM)** is when most Indian viewers are online. Start at the same time every day.

Targets: **4–5 streams, 8–10 Shorts, 1–2 longer videos per week.**

---

## 3. How each stream should go

1. **Title** with a hook + language + part number:
   `GTA 6 Hindi Live 🔴 Story Part 3 – Vice City Heist`
2. **First 5 minutes:** say what you're doing today, ask viewers to like + subscribe.
3. **During:** read chat out loud, reply by name. Note the time of every big moment
   (chase, crash, funny NPC, story twist) — write it on paper or your phone, e.g. `1:12:30 crazy jump`.
4. **Every ~45 min:** remind new viewers what's happening + ask for subs.
5. **End:** tell them when the next stream is.

---

## 4. Uploading GTA 6 snippets (the clip workflow)

### Step 1 — Get the footage
Use either:
- **Your stream VOD:** after a YouTube stream ends it stays on your channel. Download it from
  YouTube Studio → Content → Live → ⋮ → Download.
- **PS5 recordings:** press **Create** during play → *Save recent gameplay* (grabs the last
  few minutes to an hour) or *Start new recording*. Copy them to a **USB drive**:
  Media Gallery → select → ⋯ → *Copy to USB drive*. (Use an exFAT-formatted drive.)

### Step 2 — Write the clip list
Make a text file, e.g. `clips.txt`, from the times you noted:
```
# start - end | title
1:12:20 - 1:12:55 | Craziest jump in GTA 6
2:03:10 - 2:03:40 | This NPC lost his mind
2:45:00 - 2:46:30 | Police chase through Vice City
```
Good Shorts are **15–45 seconds**: start right at the action, no intro.

### Step 3 — Run the clipper
```bash
python creator/clipper.py stream.mp4 clips.txt --lang hi --channel "Your Channel"
```
In `clips/` you get:
- `01_craziest-jump-in-gta-6_short.mp4` → vertical **Short** (1080×1920)
- `01_craziest-jump-in-gta-6_16x9.mp4` → normal video, or use it in your weekly highlight video
- `upload_sheet.md` → title, description and hashtags to copy-paste for each clip

Options:
- `--shorts-style crop` fills the phone screen (good when the action is in the middle);
  default `blur` keeps the whole frame with a blurred background.
- `--mute` removes the audio, if a clip has licensed radio music playing (see section 6).
- `--lang en` for English descriptions.

### Step 4 — Upload
**From PC:** YouTube Studio → **Create → Upload videos** → pick the `_short.mp4` file.
A vertical video under 3 minutes automatically becomes a Short. Paste the title + description
from `upload_sheet.md`, add it to the *GTA 6 Shorts* playlist, choose **Schedule** to space them out.

**From phone:** copy the files to your phone → YouTube app → **+** → *Upload a video*.
The phone app lets you add trending music/text before posting. Post the same `_short.mp4`
to **Instagram Reels** too: free extra reach.

**Spacing:** 1–2 Shorts per day. Use Schedule instead of dumping 10 at once.

### Step 5 — Thumbnails (longer videos only)
Shorts don't need one. For highlights/guides: a bright screenshot (PS5 Create → Screenshot),
big 2–4 word text ("NO WAY 😱", "SECRET CAR"), your face if you use a camera. Canva's free plan is enough.

---

## 5. Making money — the realistic path

| Stage | What unlocks | What to do |
|---|---|---|
| Start | Nothing yet | Stream + Shorts consistently. Focus on retention, not money. |
| Early YouTube Partner Program tier | Channel memberships, Super Chat, Super Stickers | Turn on Super Chat for streams; viewers in India use it a lot during live games. |
| Full YouTube Partner Program | Ad revenue on streams, videos and Shorts | Longer videos (8+ min) earn the most ads; keep posting Shorts for growth. |
| ~5–10k engaged subs | Sponsorships | Gaming gear, apps, energy drinks. Make a simple media kit (subs, average views, audience age/region). |

Check the current subscriber / watch-hour thresholds in YouTube Studio → **Earn** — YouTube changes them.

Also: **affiliate links** (Amazon India Associates for your headset, controller, capture card) in
every description — small but adds up.

Realistic expectations: most channels earn little in the first 2–3 months. The ones that make
it post every day during launch hype, pick a clear angle (Hindi commentary, comedy, guides)
and stick to the same schedule.

---

## 6. Rules to stay safe (don't lose the channel)

- **Rockstar policy:** gameplay videos and streams, including monetized ones, are generally
  allowed. Don't upload leaked or pre-release content, and don't sell your footage as a product.
- **In-game radio music** can trigger copyright claims (ads revenue goes to the label, or the
  VOD gets muted). Turn the radio off / down in audio settings while streaming, or use `--mute` for clips.
- **No region-switch / early-unlock tricks.** Platforms have warned streamers about bans for this.
- **No spoilers in titles or thumbnails** for big story moments — viewers report and leave.
- **Don't buy subscribers or views.** YouTube removes them and can reject monetization.
- Never stream personal info (your address, phone number, PSN messages on screen).

---

## 7. Use the question tracker for ideas

The tracker in this repo already finds what people keep asking about GTA 6.
```bash
python bot.py scan
python creator/ideas.py --days 7
```
Opens `content_ideas.md`: topics ranked by how often they're asked, with ready video/Short ideas.
Every repeated question is a video people are already searching for.

---

## Daily checklist

- [ ] Stream at the usual time (note big-moment timestamps)
- [ ] Cut 2–3 clips with `clipper.py`
- [ ] Schedule 1–2 Shorts on YouTube + post 1 Reel
- [ ] Reply to comments for 15 minutes (the algorithm favours active channels)
- [ ] Check YouTube Studio → Analytics: which Short got the most views? Make more like it.
