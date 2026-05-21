"""
Fetch current YouTube channel stats (subscribers, views, video count) for all
tracked channels and append a snapshot to data/youtube_channels_daily.csv.

Deduplicates on (date, channel_id) so re-running the same day is safe.
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
    raise SystemExit("Missing YOUTUBE_API_KEY — set it in .env")

CHANNELS_CFG = Path("config/youtube_channels.csv")
OUT          = Path("data/youtube_channels_daily.csv")
OUT.parent.mkdir(exist_ok=True)

today = str(date.today())

# ── Load channel list ─────────────────────────────────────────────────────────

channels = []
with open(CHANNELS_CFG, newline="") as f:
    for row in csv.DictReader(f):
        channels.append({
            "label":      row["label"].strip(),
            "channel_id": row["channel_id"].strip(),
        })

print(f"Fetching stats for {len(channels)} channels...")

# ── Fetch in batches of 50 ────────────────────────────────────────────────────

all_ids = [c["channel_id"] for c in channels]
id_to_label = {c["channel_id"]: c["label"] for c in channels}
rows = []

for i in range(0, len(all_ids), 50):
    batch = all_ids[i:i+50]
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={
            "part": "snippet,statistics",
            "id":   ",".join(batch),
            "key":  KEY,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    for item in data.get("items", []):
        cid   = item["id"]
        stats = item.get("statistics", {})
        snip  = item.get("snippet", {})
        rows.append({
            "date":        today,
            "label":       id_to_label.get(cid, cid),
            "channel_id":  cid,
            "title":       snip.get("title", ""),
            "subscribers": int(stats.get("subscriberCount", 0) or 0),
            "views":       int(stats.get("viewCount",        0) or 0),
            "videos":      int(stats.get("videoCount",       0) or 0),
        })

    time.sleep(0.3)

print(f"  Got data for {len(rows)} channels")

# ── Append / dedup ────────────────────────────────────────────────────────────

df_new = pd.DataFrame(rows)

if OUT.exists():
    df_old = pd.read_csv(OUT)
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["date", "channel_id"], keep="last")
else:
    df = df_new

df = df.sort_values(["label", "date"])
df.to_csv(OUT, index=False)

print(f"Saved → {OUT}")
print(f"  Total rows : {len(df)}")
print(f"  Snapshots  : {df['date'].nunique()}")
print()
print(f"  {'Channel':<28} {'Subscribers':>12}  {'Total Views':>13}  {'Videos':>7}")
print(f"  {'─'*28} {'─'*12}  {'─'*13}  {'─'*7}")
for _, r2 in df[df["date"] == today].sort_values("subscribers", ascending=False).iterrows():
    subs = r2["subscribers"]
    views = r2["views"]
    vids = r2["videos"]
    subs_fmt = f"{subs/1_000_000:.2f}M" if subs >= 1_000_000 else f"{subs/1_000:.0f}K"
    views_fmt = f"{views/1_000_000:.1f}M" if views >= 1_000_000 else f"{views/1_000:.0f}K"
    print(f"  {r2['label']:<28} {subs_fmt:>12}  {views_fmt:>13}  {vids:>7}")
