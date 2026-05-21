"""
Warhammer Demand Intelligence — Beginner / New Player Funnel Tracker

Reads the existing youtube_videos_unified.csv, scans video titles for
beginner/starter/getting-started keywords, computes funnel metrics for
the current week's snapshot, and appends a row to:

    data/beginner_funnel_history.csv

This CSV enables longitudinal tracking of new-player inflow signals:
  - Is beginner content volume growing?
  - Are views on beginner content increasing?
  - When do spikes correlate with product releases or seasonal events?

Runs AFTER fetch_youtube_videos_unified.py in the weekly pipeline.
"""

import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

DATA_DIR         = "data"
VIDEOS_FILE      = os.path.join(DATA_DIR, "youtube_videos_unified.csv")
OUTPUT_FILE      = os.path.join(DATA_DIR, "beginner_funnel_history.csv")

# ── Beginner / new-player keyword list ─────────────────────────────────────
BEGINNER_KW = [
    "beginner", "starter", "getting started", "first army",
    "start collecting", "how to start", "new player",
    "new to warhammer", "starting warhammer", "beginners guide",
    "starter set", "complete guide", "introduction to warhammer",
    "getting into warhammer", "new to 40k", "start playing",
]

# ── Output CSV schema ───────────────────────────────────────────────────────
COLUMNS = [
    "date",
    "total_videos",
    "last_90d_count",
    "last_90d_views",
    "last_1y_count",
    "last_1y_views",
    "all_time_views",
    "top_video_title",
    "top_video_channel",
    "top_video_views",
    "top_video_published",
]


def load_videos():
    if not os.path.exists(VIDEOS_FILE):
        print(f"[WARN] Videos file not found: {VIDEOS_FILE}")
        return None
    df = pd.read_csv(VIDEOS_FILE)
    if df.empty:
        return None
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    return df


def compute_funnel_snapshot(videos_df):
    """Compute beginner-funnel metrics from the latest video snapshot."""
    # Use the most recent as_of_date snapshot
    latest_snap = videos_df["as_of_date"].max()
    latest      = videos_df[videos_df["as_of_date"] == latest_snap].copy()

    now = datetime.now(timezone.utc)
    latest["days_old"] = (now - latest["published_at"]).dt.days.clip(lower=1)

    # Filter by beginner keywords in title
    pat  = "|".join(BEGINNER_KW)
    mask = latest["title"].str.lower().str.contains(pat, na=False)
    beg  = latest[mask].copy()

    if beg.empty:
        print("[INFO] No beginner keyword matches in current video library.")
        return {
            "date":               str(datetime.now().date()),
            "total_videos":       0,
            "last_90d_count":     0,
            "last_90d_views":     0,
            "last_1y_count":      0,
            "last_1y_views":      0,
            "all_time_views":     0,
            "top_video_title":    "",
            "top_video_channel":  "",
            "top_video_views":    0,
            "top_video_published": "",
        }

    beg_90d = beg[beg["days_old"] <= 90]
    beg_1y  = beg[beg["days_old"] <= 365]
    top     = beg.nlargest(1, "views").iloc[0] if not beg.empty else None

    return {
        "date":               str(datetime.now().date()),
        "total_videos":       int(len(beg)),
        "last_90d_count":     int(len(beg_90d)),
        "last_90d_views":     int(beg_90d["views"].sum()) if not beg_90d.empty else 0,
        "last_1y_count":      int(len(beg_1y)),
        "last_1y_views":      int(beg_1y["views"].sum()) if not beg_1y.empty else 0,
        "all_time_views":     int(beg["views"].sum()),
        "top_video_title":    str(top["title"]) if top is not None else "",
        "top_video_channel":  str(top.get("channel_label", "")) if top is not None else "",
        "top_video_views":    int(top["views"]) if top is not None else 0,
        "top_video_published": str(top["published_at"])[:10] if top is not None else "",
    }


def append_to_history(row):
    """Append snapshot row to beginner_funnel_history.csv (dedup by date)."""
    new_df = pd.DataFrame([row], columns=COLUMNS)

    if os.path.exists(OUTPUT_FILE):
        existing = pd.read_csv(OUTPUT_FILE)
        # Remove any existing rows for today's date (dedup)
        existing = existing[existing["date"] != row["date"]]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = combined.sort_values("date").reset_index(drop=True)
    combined.to_csv(OUTPUT_FILE, index=False)
    return combined


def print_summary(row, history_df):
    print(f"\n── Beginner Funnel Snapshot: {row['date']} ──────────────────")
    print(f"  Total beginner videos (all-time): {row['total_videos']}")
    print(f"  Last 90 days:  {row['last_90d_count']} videos  |  {row['last_90d_views']:,} views")
    print(f"  Last 12 months: {row['last_1y_count']} videos  |  {row['last_1y_views']:,} views")
    print(f"  All-time views on beginner content: {row['all_time_views']:,}")
    if row["top_video_title"]:
        print(f"  Top video: \"{row['top_video_title'][:70]}\"")
        print(f"    Channel: {row['top_video_channel']}  |  Views: {row['top_video_views']:,}  |  Published: {row['top_video_published']}")
    print(f"\n  History: {len(history_df)} weekly snapshot(s) stored → {OUTPUT_FILE}")

    # Week-over-week change if ≥2 rows
    if len(history_df) >= 2:
        prev = history_df.iloc[-2]
        curr = history_df.iloc[-1]
        delta_90d_v = curr["last_90d_views"] - prev["last_90d_views"]
        sign        = "▲ +" if delta_90d_v >= 0 else "▼ "
        print(f"  Week-over-week 90d views: {sign}{delta_90d_v:,}")


if __name__ == "__main__":
    print("── Beginner Funnel Signals (new player inflow tracker) ──────────")

    videos_df = load_videos()
    if videos_df is None:
        print("[ERROR] No video data found. Run fetch_youtube_videos_unified.py first.")
        exit(1)

    row        = compute_funnel_snapshot(videos_df)
    history_df = append_to_history(row)
    print_summary(row, history_df)

    print("✓ Beginner funnel snapshot saved.")
