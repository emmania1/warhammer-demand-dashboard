"""
Warhammer Demand Intelligence — Evergreen Anchor View Fetcher

Weekly script that reads the resolved anchor video IDs from
config/youtube_evergreen_anchors.csv, fetches current view counts via the
YouTube Data API v3, and appends a dated snapshot row to:

    data/youtube_evergreen_anchors.csv

Deduplication: (date, video_slug) — re-running on the same day overwrites
today's row cleanly.

Prerequisite: Run resolve_anchor_video_ids.py once to populate video_id
              values in the config (replacing TBD entries).

Runs as part of the weekly pipeline AFTER fetch_youtube_channels_daily.py.

Quota cost: 1 unit per video (Videos.list). With 15 anchors → ~15 units/week.
"""

import os
import sys
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

API_KEY     = os.getenv("YOUTUBE_API_KEY", "")
CONFIG_FILE = "config/youtube_evergreen_anchors.csv"
OUTPUT_FILE = "data/youtube_evergreen_anchors.csv"
VIDEOS_URL  = "https://www.googleapis.com/youtube/v3/videos"

OUTPUT_COLS = [
    "date", "channel_label", "video_slug", "title", "content_type",
    "views", "source",
]


def fetch_video_stats(video_ids: list[str]) -> dict[str, int]:
    """Batch-fetch view counts for a list of video IDs.
    Returns {video_id: view_count}."""
    if not API_KEY:
        print("[ERROR] YOUTUBE_API_KEY not set.")
        return {}

    stats = {}
    # YouTube API accepts up to 50 IDs per request
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        params = {
            "key":  API_KEY,
            "part": "statistics",
            "id":   ",".join(batch),
        }
        try:
            r = requests.get(VIDEOS_URL, params=params, timeout=20)
            r.raise_for_status()
            for item in r.json().get("items", []):
                vid_id = item["id"]
                views  = int(item["statistics"].get("viewCount", 0))
                stats[vid_id] = views
        except Exception as e:
            print(f"  [WARN] Batch fetch failed: {e}")
    return stats


def main():
    print("── Evergreen Anchor Views Fetcher ───────────────────────────────")

    if not os.path.exists(CONFIG_FILE):
        print(f"[ERROR] Config not found: {CONFIG_FILE}")
        print("  Run resolve_anchor_video_ids.py first.")
        sys.exit(1)

    cfg = pd.read_csv(CONFIG_FILE)

    # Filter to anchors with resolved video IDs
    resolved = cfg[cfg["video_id"].str.strip().str.upper() != "TBD"].copy()
    tbd      = cfg[cfg["video_id"].str.strip().str.upper() == "TBD"]

    if tbd.shape[0] > 0:
        print(f"  [WARN] {tbd.shape[0]} anchor(s) still have TBD video_id — skipping them.")
        print(f"         Run resolve_anchor_video_ids.py to resolve them.")

    if resolved.empty:
        print("[ERROR] No resolved anchors found. Nothing to fetch.")
        sys.exit(1)

    print(f"  Fetching views for {len(resolved)} resolved anchors...")

    video_ids = resolved["video_id"].tolist()
    stats     = fetch_video_stats(video_ids)

    today = str(datetime.now().date())
    rows  = []

    for _, row in resolved.iterrows():
        vid_id = row["video_id"]
        views  = stats.get(vid_id)

        if views is None:
            print(f"  [WARN] No data returned for {row['video_slug']} ({vid_id})")
            continue

        rows.append({
            "date":          today,
            "channel_label": row["channel_label"],
            "video_slug":    row["video_slug"],
            "title":         row["title"],
            "content_type":  row["content_type"],
            "views":         views,
            "source":        "api",
        })

    if not rows:
        print("[ERROR] No view data collected.")
        sys.exit(1)

    new_df = pd.DataFrame(rows, columns=OUTPUT_COLS)

    # Append to existing CSV, dedup on (date, video_slug)
    if os.path.exists(OUTPUT_FILE):
        existing = pd.read_csv(OUTPUT_FILE)
        # Remove today's rows to allow clean re-run
        existing = existing[
            ~((existing["date"] == today) &
              (existing["video_slug"].isin(new_df["video_slug"])))
        ]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = combined.sort_values(["video_slug", "date"]).reset_index(drop=True)
    combined.to_csv(OUTPUT_FILE, index=False)

    print(f"\n── Snapshot Summary: {today} ──────────────────────────────────")
    for r in rows:
        print(f"  {r['channel_label']:25s}  {r['video_slug']:35s}  {r['views']:>12,} views")

    print(f"\n  ✓ {len(rows)} anchor snapshots saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
