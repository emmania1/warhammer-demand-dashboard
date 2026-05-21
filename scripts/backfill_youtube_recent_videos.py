import os, csv, time
from pathlib import Path
from datetime import date
import requests
import pandas as pd

KEY = os.getenv("YOUTUBE_API_KEY")
if not KEY:
    raise SystemExit("Missing YOUTUBE_API_KEY. Load it from .env first.")

CONFIG = Path("config/youtube_channels.csv")
OUT = Path("data/youtube_recent_videos_backfill.csv")
OUT.parent.mkdir(exist_ok=True)

def yt_get(url, params):
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

channels = []
with open(CONFIG, newline="") as f:
    for row in csv.DictReader(f):
        channels.append({"label": row["label"].strip(), "channel_id": row["channel_id"].strip()})

all_video_ids = []

# Get each channel's "uploads" playlist
for c in channels:
    data = yt_get("https://www.googleapis.com/youtube/v3/channels", {
        "part": "contentDetails",
        "id": c["channel_id"],
        "key": KEY
    })
    uploads = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    c["uploads_playlist_id"] = uploads
    time.sleep(0.2)

# Pull last 50 videos per channel from uploads playlist
for c in channels:
    vids = []
    page = None
    while len(vids) < 50:
        data = yt_get("https://www.googleapis.com/youtube/v3/playlistItems", {
            "part": "contentDetails",
            "playlistId": c["uploads_playlist_id"],
            "maxResults": 50,
            "pageToken": page,
            "key": KEY
        })
        for it in data.get("items", []):
            vids.append(it["contentDetails"]["videoId"])
            if len(vids) >= 50:
                break
        page = data.get("nextPageToken")
        if not page:
            break
        time.sleep(0.2)
    for vid in vids:
        all_video_ids.append((c["label"], c["channel_id"], vid))

rows = []
today = str(date.today())

# Fetch stats in batches of 50
for i in range(0, len(all_video_ids), 50):
    batch = all_video_ids[i:i+50]
    ids = ",".join([x[2] for x in batch])
    data = yt_get("https://www.googleapis.com/youtube/v3/videos", {
        "part": "snippet,statistics",
        "id": ids,
        "key": KEY
    })
    items = {it["id"]: it for it in data.get("items", [])}
    for label, channel_id, video_id in batch:
        it = items.get(video_id)
        if not it:
            continue
        s = it.get("statistics", {})
        sn = it.get("snippet", {})
        rows.append({
            "as_of_date": today,
            "channel_label": label,
            "channel_id": channel_id,
            "video_id": video_id,
            "title": sn.get("title",""),
            "published_at": sn.get("publishedAt",""),
            "views": int(s.get("viewCount", 0) or 0),
            "likes": int(s.get("likeCount", 0) or 0),
            "comments": int(s.get("commentCount", 0) or 0),
        })
    time.sleep(0.2)

df = pd.DataFrame(rows)
df.to_csv(OUT, index=False)
print("Saved →", OUT, "| rows:", len(df))
