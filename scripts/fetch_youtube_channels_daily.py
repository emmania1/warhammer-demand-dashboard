"""
fetch_youtube_channels_daily.py
────────────────────────────────
Fetches subscriber counts, total views, and video counts for all tracked
YouTube channels via the YouTube Data API v3.

Config  : config/youtube_channels.csv  (label, channel_id)
Output  : data/youtube_channels_daily.csv  (appends daily rows)
API key : .env  →  YOUTUBE_API_KEY
"""

import os
import requests
import pandas as pd
from pathlib import Path
from datetime import date

ROOT      = Path(__file__).parent.parent
CONFIG    = ROOT / "config" / "youtube_channels.csv"
OUT       = ROOT / "data" / "youtube_channels_daily.csv"
OUT.parent.mkdir(exist_ok=True)

# ── API key ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

API_KEY = os.getenv("YOUTUBE_API_KEY", "")
if not API_KEY:
    raise SystemExit("YOUTUBE_API_KEY not set in .env")

# ── Load channel config ───────────────────────────────────────────────────────
channels = pd.read_csv(CONFIG)
channel_ids = channels["channel_id"].tolist()
id_to_label = dict(zip(channels["channel_id"], channels["label"]))

print(f"Fetching stats for {len(channel_ids)} channels...")

# ── Fetch from YouTube API (batch up to 50 IDs per call) ─────────────────────
rows = []
today = str(date.today())

for i in range(0, len(channel_ids), 50):
    batch = channel_ids[i:i+50]
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={
            "part": "snippet,statistics",
            "id":   ",".join(batch),
            "key":  API_KEY,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    for item in data.get("items", []):
        ch_id  = item["id"]
        stats  = item.get("statistics", {})
        label  = id_to_label.get(ch_id, ch_id)
        subs   = int(stats.get("subscriberCount", 0))
        views  = int(stats.get("viewCount", 0))
        videos = int(stats.get("videoCount", 0))
        rows.append({
            "date":        today,
            "label":       label,
            "channel_id":  ch_id,
            "subscribers": subs,
            "total_views": views,
            "video_count": videos,
        })

print(f"  Got data for {len(rows)} channels")

# ── Merge with existing CSV ───────────────────────────────────────────────────
new_df = pd.DataFrame(rows)

if OUT.exists():
    existing = pd.read_csv(OUT)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date", "label"], keep="last")
    combined = combined.sort_values(["label", "date"]).reset_index(drop=True)
else:
    combined = new_df

combined.to_csv(OUT, index=False)
print(f"Saved → {OUT.relative_to(ROOT)}")
print(f"  Total rows : {len(combined)}")
print(f"  Snapshots  : {combined['date'].nunique()}")
print()
print(f"  {'Channel':<28} {'Subscribers':>12}  {'Total Views':>13}  {'Videos':>7}")
print(f"  {'─'*28} {'─'*12}  {'─'*13}  {'─'*7}")
for _, row in new_df.sort_values("subscribers", ascending=False).iterrows():
    subs  = f"{row['subscribers']/1e6:.2f}M" if row['subscribers'] >= 1e6 else f"{row['subscribers']//1000}K"
    views = f"{row['total_views']/1e6:.1f}M" if row['total_views'] >= 1e6 else f"{row['total_views']//1000}K"
    print(f"  {row['label']:<28} {subs:>12}  {views:>13}  {row['video_count']:>7}")
