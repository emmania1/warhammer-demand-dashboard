"""
Unified YouTube video snapshot fetcher.

Pulls the most recent 50 videos from every tracked channel AND any
manually-listed tentpole videos, then appends today's stats to
data/youtube_videos_unified.csv.

Deduplicates on (as_of_date, video_id) so re-running the same day is safe.
Run this script on whatever cadence you want (daily, weekly) to build history.
"""

import os, csv, time
from pathlib import Path
from datetime import date
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass
import pandas as pd

KEY = os.getenv("YOUTUBE_API_KEY")
if not KEY:
    raise SystemExit("Missing YOUTUBE_API_KEY. Load it from .env first.")

CHANNELS_CFG  = Path("config/youtube_channels.csv")
TENTPOLE_CFG  = Path("config/tentpole_videos.csv")
OUT           = Path("data/youtube_videos_unified.csv")
OUT.parent.mkdir(exist_ok=True)

COLS = [
    "as_of_date", "channel_label", "channel_id", "video_id",
    "title", "published_at", "views", "likes", "comments", "is_tentpole"
]

today = str(date.today())


def yt_get(url, params):
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Load config ───────────────────────────────────────────────────────────────

channels = []
with open(CHANNELS_CFG, newline="") as f:
    for row in csv.DictReader(f):
        channels.append({
            "label":      row["label"].strip(),
            "channel_id": row["channel_id"].strip()
        })

tentpole_ids = set()
tentpole_map = {}  # video_id → label
with open(TENTPOLE_CFG, newline="") as f:
    for row in csv.DictReader(f):
        vid = row["video_id"].strip()
        tentpole_ids.add(vid)
        tentpole_map[vid] = row["label"].strip()

print(f"Channels: {len(channels)}  |  Tentpole videos: {len(tentpole_ids)}")


# ── Step 1: get uploads playlist ID for each channel ─────────────────────────

print("Fetching uploads playlist IDs...")
for c in channels:
    data = yt_get("https://www.googleapis.com/youtube/v3/channels", {
        "part": "contentDetails",
        "id":   c["channel_id"],
        "key":  KEY
    })
    c["uploads_playlist"] = (
        data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )
    time.sleep(0.2)


# ── Step 2: pull last 50 video IDs per channel from uploads playlist ──────────

print("Fetching recent video IDs per channel...")
all_video_ids = []   # list of (channel_label, channel_id, video_id, is_tentpole)

for c in channels:
    vids = []
    page = None
    try:
        while len(vids) < 50:
            data = yt_get("https://www.googleapis.com/youtube/v3/playlistItems", {
                "part":        "contentDetails",
                "playlistId":  c["uploads_playlist"],
                "maxResults":  50,
                "pageToken":   page,
                "key":         KEY
            })
            for it in data.get("items", []):
                vids.append(it["contentDetails"]["videoId"])
                if len(vids) >= 50:
                    break
            page = data.get("nextPageToken")
            if not page:
                break
            time.sleep(0.2)
    except Exception as e:
        print(f"  WARN: skipping {c['label']} playlist — {e}")

    for vid in vids:
        all_video_ids.append((c["label"], c["channel_id"], vid, vid in tentpole_ids))

    print(f"  {c['label']}: {len(vids)} videos")


# ── Step 3: add any tentpole videos not captured via channel playlists ────────

captured = {x[2] for x in all_video_ids}
for vid, label in tentpole_map.items():
    if vid not in captured:
        all_video_ids.append((label, "", vid, True))
        print(f"  Tentpole (standalone): {label} / {vid}")


# ── Step 4: fetch video stats in batches of 50 ───────────────────────────────

print(f"Fetching stats for {len(all_video_ids)} videos...")
rows = []

for i in range(0, len(all_video_ids), 50):
    batch = all_video_ids[i:i+50]
    ids   = ",".join(x[2] for x in batch)
    data  = yt_get("https://www.googleapis.com/youtube/v3/videos", {
        "part": "snippet,statistics",
        "id":   ids,
        "key":  KEY
    })
    items_map = {it["id"]: it for it in data.get("items", [])}

    for label, channel_id, video_id, is_tp in batch:
        it = items_map.get(video_id)
        if not it:
            print(f"  WARN: missing stats for {video_id}")
            continue
        s  = it.get("statistics", {})
        sn = it.get("snippet", {})
        rows.append({
            "as_of_date":    today,
            "channel_label": label or sn.get("channelTitle", ""),
            "channel_id":    channel_id or sn.get("channelId", ""),
            "video_id":      video_id,
            "title":         sn.get("title", ""),
            "published_at":  sn.get("publishedAt", ""),
            "views":         int(s.get("viewCount",   0) or 0),
            "likes":         int(s.get("likeCount",   0) or 0),
            "comments":      int(s.get("commentCount", 0) or 0),
            "is_tentpole":   is_tp,
        })
    time.sleep(0.2)


# ── Step 5: append to unified CSV, dedup on (as_of_date, video_id) ───────────

df_new = pd.DataFrame(rows, columns=COLS)

if OUT.exists():
    df_old = pd.read_csv(OUT)
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["as_of_date", "video_id"], keep="last")
else:
    df = df_new

df.to_csv(OUT, index=False)

print(f"\nSaved → {OUT}")
print(f"  New rows added : {len(df_new)}")
print(f"  Total rows now : {len(df)}")
print(f"  Date snapshots : {df['as_of_date'].nunique()}")
