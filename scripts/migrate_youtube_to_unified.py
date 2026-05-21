"""
One-time migration script.

Seeds data/youtube_videos_unified.csv from the two legacy files:
  - data/youtube_recent_videos_backfill.csv  (channel playlist snapshots)
  - data/youtube_videos_daily.csv            (manually-tracked tentpole videos)

Safe to re-run — deduplicates on (as_of_date, video_id).
"""

import pandas as pd
from pathlib import Path

OUT  = Path("data/youtube_videos_unified.csv")
OUT.parent.mkdir(exist_ok=True)

COLS = [
    "as_of_date", "channel_label", "channel_id", "video_id",
    "title", "published_at", "views", "likes", "comments", "is_tentpole"
]

# channel_title → channel_id mapping for the legacy tentpole file
CHANNEL_ID_MAP = {
    "Warhammer":           "UCwdh3MTrFq3sXlB4ct8B-Fg",
    "Luetin09":            "UC8RfCCzWsMgNspTI-GTFenQ",
    "WesHammer":           "UCSDj6ttwzj2sr464jDdg_pA",
    "Squidmar Miniatures": "UCDvZTWvHZPTxJ4K1yTD2a1g",
    "Majorkill":           "UC_wb8IVtmXwil8bN3IdVtZw",
}

dfs = []

# ── Source 1: youtube_recent_videos_backfill.csv ──────────────────────────────
backfill = Path("data/youtube_recent_videos_backfill.csv")
if backfill.exists():
    df1 = pd.read_csv(backfill)
    df1["is_tentpole"] = False
    df1 = df1[COLS]
    dfs.append(df1)
    print(f"Backfill:        {len(df1):>5} rows  ({backfill})")
else:
    print(f"Skipped (not found): {backfill}")

# ── Source 2: youtube_videos_daily.csv (tentpole videos) ─────────────────────
daily = Path("data/youtube_videos_daily.csv")
if daily.exists():
    df2 = pd.read_csv(daily)
    df2 = df2.rename(columns={"date": "as_of_date", "label": "channel_label"})
    df2["channel_id"] = df2["channel_title"].map(CHANNEL_ID_MAP).fillna("")
    df2["is_tentpole"] = True
    df2 = df2[COLS]
    dfs.append(df2)
    print(f"Tentpole daily:  {len(df2):>5} rows  ({daily})")
else:
    print(f"Skipped (not found): {daily}")

if not dfs:
    print("No source files found — nothing to migrate.")
else:
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["as_of_date", "video_id"], keep="last")
    combined = combined.sort_values(["as_of_date", "channel_label", "published_at"])

    if OUT.exists():
        existing = pd.read_csv(OUT)
        combined = pd.concat([existing, combined], ignore_index=True)
        combined = combined.drop_duplicates(subset=["as_of_date", "video_id"], keep="last")
        print(f"Merged with existing unified file ({len(existing)} rows already present)")

    combined.to_csv(OUT, index=False)
    print(f"\nSaved → {OUT}")
    print(f"  Total rows : {len(combined)}")
    print(f"  Snapshots  : {combined['as_of_date'].nunique()} date(s)")
    print(f"  Videos     : {combined['video_id'].nunique()} unique video IDs")
    print(f"  Channels   : {combined['channel_label'].nunique()} unique channels")
