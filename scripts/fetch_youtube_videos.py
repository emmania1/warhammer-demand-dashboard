import os, csv
import requests
import pandas as pd
from datetime import date
from pathlib import Path

KEY = os.environ.get("YOUTUBE_API_KEY")
if not KEY:
    raise SystemExit("Missing YOUTUBE_API_KEY env var. Set it first.")

CFG = Path("config/tentpole_videos.csv")
OUT = Path("data/youtube_videos_daily.csv")
OUT.parent.mkdir(exist_ok=True)

videos = []
with open(CFG, newline="") as f:
    for row in csv.DictReader(f):
        videos.append({"label": row["label"].strip(), "video_id": row["video_id"].strip()})

ids = ",".join([v["video_id"] for v in videos])

url = "https://www.googleapis.com/youtube/v3/videos"
params = {
    "part": "snippet,statistics,contentDetails",
    "id": ids,
    "key": KEY,
    "maxResults": 50
}
r = requests.get(url, params=params, timeout=30)
r.raise_for_status()
data = r.json()

today = str(date.today())
items = {it["id"]: it for it in data.get("items", [])}

rows = []
for v in videos:
    it = items.get(v["video_id"])
    if not it:
        print("WARN missing:", v["label"], v["video_id"])
        continue
    s = it.get("statistics", {})
    sn = it.get("snippet", {})
    cd = it.get("contentDetails", {})
    rows.append({
        "date": today,
        "label": v["label"],
        "video_id": v["video_id"],
        "title": sn.get("title",""),
        "channel_title": sn.get("channelTitle",""),
        "published_at": sn.get("publishedAt",""),
        "duration": cd.get("duration",""),
        "views": int(s.get("viewCount", 0) or 0),
        "likes": int(s.get("likeCount", 0) or 0),
        "comments": int(s.get("commentCount", 0) or 0),
    })

df_new = pd.DataFrame(rows)

if OUT.exists():
    df_old = pd.read_csv(OUT)
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["date","video_id"], keep="last")
else:
    df = df_new

df.to_csv(OUT, index=False)
print("Saved →", OUT, "| added rows:", len(df_new))
print(df_new[["label","views","likes","comments","video_id"]].to_string(index=False))
