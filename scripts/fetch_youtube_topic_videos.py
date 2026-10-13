"""
fetch_youtube_topic_videos.py
─────────────────────────────
Tracks views on YouTube videos about a launch topic (e.g. Tone Pro paints).

Config : config/youtube_topic_queries.csv  (topic, query, must_match, published_after)
         must_match = regex checked against title + description, filters search noise
API key: .env → YOUTUBE_API_KEY

Each run:
  1. search.list per query (by view count + by upload date) to discover new videos
     — 100 quota units per call, so run weekly, not daily
  2. videos.list for every video ever tracked for the topic (1 unit per 50 videos)

WHAT THIS MEASURES: creator attention / viewer interest in the topic. Not sales.

Output:
  data/youtube_topic_videos.csv   — one row per (date, topic, video_id)
  data/youtube_topic_summary.csv  — one row per (date, topic)
"""

import os, re, requests
from pathlib import Path
from datetime import date

import pandas as pd

ROOT        = Path(__file__).parent.parent
CONFIG      = ROOT / "config" / "youtube_topic_queries.csv"
OUT_VIDEOS  = ROOT / "data" / "youtube_topic_videos.csv"
OUT_SUMMARY = ROOT / "data" / "youtube_topic_summary.csv"
OUT_VIDEOS.parent.mkdir(exist_ok=True)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

API_KEY = os.getenv("YOUTUBE_API_KEY", "")
if not API_KEY:
    raise SystemExit("YOUTUBE_API_KEY not set in .env")

API   = "https://www.googleapis.com/youtube/v3"
today = str(date.today())


def yt(endpoint: str, **params) -> dict:
    r = requests.get(f"{API}/{endpoint}", params={**params, "key": API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()


def search_ids(query: str, published_after: str) -> set[str]:
    ids = set()
    for order in ("viewCount", "date"):
        data = yt("search", part="id", q=query, type="video", order=order,
                  publishedAfter=f"{published_after}T00:00:00Z", maxResults=50)
        ids |= {i["id"]["videoId"] for i in data.get("items", [])}
    return ids


def video_details(ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        data = yt("videos", part="snippet,statistics", id=",".join(ids[i:i + 50]))
        out.extend(data.get("items", []))
    return out


cfg = pd.read_csv(CONFIG, dtype=str).fillna("")
existing = (pd.read_csv(OUT_VIDEOS, dtype=str, keep_default_na=False)
            if OUT_VIDEOS.exists() else pd.DataFrame())

print(f"YouTube topic tracker — {today}")
rows = []
for topic, qs in cfg.groupby("topic", sort=False):
    pattern = re.compile("|".join(f"(?:{m})" for m in qs["must_match"] if m) or ".", re.I)

    # Previously tracked videos stay tracked; search adds candidates
    tracked = set(existing.loc[existing["topic"] == topic, "video_id"]) if not existing.empty else set()
    candidates = set()
    for _, q in qs.iterrows():
        found = search_ids(q["query"], q["published_after"] or "2000-01-01")
        print(f"  [{topic}] '{q['query']}': {len(found)} search hits")
        candidates |= found

    items = video_details(sorted(tracked | candidates))
    kept = 0
    for v in items:
        sn, st = v["snippet"], v.get("statistics", {})
        vid = v["id"]
        text = f"{sn.get('title', '')}\n{sn.get('description', '')}"
        if vid not in tracked and not pattern.search(text):
            continue                                  # search noise — not about the topic
        kept += 1
        rows.append({
            "date":          today,
            "topic":         topic,
            "video_id":      vid,
            "title":         sn.get("title", ""),
            "channel_title": sn.get("channelTitle", ""),
            "channel_id":    sn.get("channelId", ""),
            "published_at":  sn.get("publishedAt", "")[:10],
            "views":         int(st.get("viewCount", 0) or 0),
            "likes":         int(st.get("likeCount", 0) or 0),
            "comments":      int(st.get("commentCount", 0) or 0),
            "first_tracked": "",
        })
    print(f"  [{topic}] {kept} videos tracked ({len(tracked)} previously, "
          f"{len(candidates - tracked)} new candidates before filtering)")

new_df = pd.DataFrame(rows)
if new_df.empty:
    raise SystemExit("No videos returned.")

# first_tracked = earliest date each video appears in the file
if not existing.empty:
    first = existing.groupby(["topic", "video_id"])["date"].min()
    new_df["first_tracked"] = [first.get((t, v), today) for t, v in zip(new_df["topic"], new_df["video_id"])]
    existing = existing[existing["date"] != today]
    all_df = pd.concat([existing, new_df.astype(str)], ignore_index=True)
else:
    new_df["first_tracked"] = today
    all_df = new_df
all_df.to_csv(OUT_VIDEOS, index=False)

# ── Summary: total views + views gained since the previous snapshot ───────────
summ_rows = []
for topic, g in new_df.groupby("topic"):
    prev = existing[existing["topic"] == topic] if not existing.empty else pd.DataFrame()
    prev_date = prev["date"].max() if not prev.empty else ""
    gained = None
    if prev_date:
        p = prev[prev["date"] == prev_date].set_index("video_id")["views"].astype(int)
        both = g[g["video_id"].isin(p.index)]
        gained = int((both["views"].values - p.loc[both["video_id"]].values).sum())
    summ_rows.append({
        "date":            today,
        "topic":           topic,
        "videos_tracked":  len(g),
        "channels":        g["channel_id"].nunique(),
        "total_views":     int(g["views"].sum()),
        "total_likes":     int(g["likes"].sum()),
        "total_comments":  int(g["comments"].sum()),
        "new_videos":      int((g["first_tracked"] == today).sum()) if prev_date else len(g),
        "prev_date":       prev_date,
        "views_gained_since_prev": "" if gained is None else gained,
    })
sum_df = pd.DataFrame(summ_rows)
if OUT_SUMMARY.exists():
    ex = pd.read_csv(OUT_SUMMARY, dtype=str, keep_default_na=False)
    ex = ex[ex["date"] != today]
    sum_df = pd.concat([ex, sum_df.astype(str)], ignore_index=True)
sum_df.to_csv(OUT_SUMMARY, index=False)

for topic, g in new_df.groupby("topic"):
    print(f"\n  {topic}: {len(g)} videos, {g['views'].sum():,} total views. Top 5:")
    for _, r in g.sort_values("views", ascending=False).head(5).iterrows():
        print(f"    {r['views']:>9,}  {r['channel_title'][:22]:22}  {r['title'][:60]}")
print(f"\n✓ {len(new_df)} rows → {OUT_VIDEOS.relative_to(ROOT)}")
print(f"✓ Summary → {OUT_SUMMARY.relative_to(ROOT)}")
