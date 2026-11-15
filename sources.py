"""Read-only scanners for Reddit, YouTube and X, using each platform's official API.

Each scanner returns a list of item dicts:

    {"id", "platform", "text", "url", "created", "context"}

Usernames are deliberately not collected. `id` is prefixed by platform so the
store can skip items it has already seen.
"""
from __future__ import annotations

import os
import time
from typing import Iterable

import requests

USER_AGENT = os.getenv("BOT_USER_AGENT", "gta6-question-tracker/1.0 (read-only personal research script)")
SEARCH_TERMS = ['"GTA 6"', "GTA6", '"GTA VI"', '"Grand Theft Auto VI"']
REDDIT_SUBS = ("GTA6", "GTA", "gaming")
TIMEOUT = 20


def _get(url: str, **kw) -> dict:
    headers = {"User-Agent": USER_AGENT, **kw.pop("headers", {})}
    r = requests.get(url, headers=headers, timeout=TIMEOUT, **kw)
    if r.status_code == 429:
        raise RuntimeError(f"Rate limited by {url.split('/')[2]} - try again later")
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------- Reddit
def _reddit_token() -> str:
    """Application-only OAuth token (read-only, no user login)."""
    cid, secret = os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        raise RuntimeError("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are not set (needs approved Reddit API access)")
    r = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(cid, secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def scan_reddit(limit: int = 50, subreddits: Iterable[str] = REDDIT_SUBS) -> list[dict]:
    """About 7 read-only requests: one sitewide search + new posts and comments per subreddit."""
    base = "https://oauth.reddit.com"
    headers = {"Authorization": f"bearer {_reddit_token()}"}
    items: list[dict] = []

    def add_post(p: dict) -> None:
        items.append({
            "id": f"reddit:{p['name']}",
            "platform": "reddit",
            "text": f"{p.get('title', '')}\n\n{p.get('selftext', '')}".strip(),
            "url": "https://www.reddit.com" + p.get("permalink", ""),
            "created": p.get("created_utc", 0),
            "context": f"r/{p.get('subreddit', '')} post",
        })

    data = _get(f"{base}/search", params={"q": " OR ".join(SEARCH_TERMS), "sort": "new", "limit": limit, "t": "week"},
                headers=headers)
    for child in data.get("data", {}).get("children", []):
        add_post(child["data"])

    for sub in subreddits:
        time.sleep(1)
        data = _get(f"{base}/r/{sub}/new", params={"limit": limit}, headers=headers)
        for child in data.get("data", {}).get("children", []):
            add_post(child["data"])
        time.sleep(1)
        data = _get(f"{base}/r/{sub}/comments", params={"limit": limit}, headers=headers)
        for child in data.get("data", {}).get("children", []):
            c = child["data"]
            items.append({
                "id": f"reddit:{c['name']}",
                "platform": "reddit",
                "text": c.get("body", ""),
                "url": "https://www.reddit.com" + c.get("permalink", ""),
                "created": c.get("created_utc", 0),
                "context": f"comment on r/{sub}: {c.get('link_title', '')}",
            })
    return items


# --------------------------------------------------------------------------- YouTube
def scan_youtube(max_videos: int = 10, comments_per_video: int = 50) -> list[dict]:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not set (see README: Google Cloud -> YouTube Data API v3)")
    api = "https://www.googleapis.com/youtube/v3"
    published_after = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7 * 86400))
    vids = _get(f"{api}/search", params={
        "key": key, "part": "snippet", "q": "GTA 6", "type": "video",
        "order": "date", "maxResults": max_videos, "publishedAfter": published_after,
        "relevanceLanguage": "en",
    })
    items: list[dict] = []
    for v in vids.get("items", []):
        vid = v["id"]["videoId"]
        title = v["snippet"]["title"]
        try:
            threads = _get(f"{api}/commentThreads", params={
                "key": key, "part": "snippet", "videoId": vid,
                "maxResults": comments_per_video, "order": "time", "textFormat": "plainText",
            })
        except requests.HTTPError:
            continue  # comments disabled on this video
        for t in threads.get("items", []):
            s = t["snippet"]["topLevelComment"]["snippet"]
            items.append({
                "id": f"youtube:{t['id']}",
                "platform": "youtube",
                "text": s.get("textDisplay", ""),
                "url": f"https://www.youtube.com/watch?v={vid}&lc={t['id']}",
                "created": s.get("publishedAt", ""),
                "context": f"comment on YouTube video: {title}",
            })
    return items


# --------------------------------------------------------------------------- X (Twitter)
def scan_x(max_results: int = 50) -> list[dict]:
    bearer = os.getenv("X_BEARER_TOKEN")
    if not bearer:
        raise RuntimeError("X_BEARER_TOKEN is not set (X API search needs a paid tier - see README)")
    query = f"({' OR '.join(SEARCH_TERMS)}) ? -is:retweet lang:en"
    data = _get("https://api.x.com/2/tweets/search/recent", params={
        "query": query,
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at",
    }, headers={"Authorization": f"Bearer {bearer}"})
    return [{
        "id": f"x:{t['id']}",
        "platform": "x",
        "text": t["text"],
        "url": f"https://x.com/i/status/{t['id']}",  # works without knowing the username
        "created": t.get("created_at", ""),
        "context": "post on X",
    } for t in data.get("data", [])]


SCANNERS = {"reddit": scan_reddit, "youtube": scan_youtube, "x": scan_x}
