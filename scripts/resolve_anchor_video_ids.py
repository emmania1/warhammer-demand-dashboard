"""
Warhammer Demand Intelligence — Evergreen Anchor Video ID Resolver

One-time (or on-demand) script that resolves YouTube video IDs for anchor
videos whose video_id is still "TBD" in config/youtube_evergreen_anchors.csv.

Strategy:
  For each TBD anchor, issues a YouTube Data API v3 search request constrained
  to the owning channel, ordered by relevance, and picks the top result.
  The user can review and correct the resolved IDs before they take effect.

Usage:
    python scripts/resolve_anchor_video_ids.py

Output:
    - Updates config/youtube_evergreen_anchors.csv in place (replaces TBD values)
    - Prints a resolution report for manual review

Quotas:
    YouTube Search costs ~100 units per call. With 15 anchors, this uses
    ~1,500 units (out of the 10,000 daily quota). Run once when new anchors
    are added.
"""

import os
import sys
import requests
import pandas as pd
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

API_KEY      = os.getenv("YOUTUBE_API_KEY", "")
CONFIG_FILE  = "config/youtube_evergreen_anchors.csv"
SEARCH_URL   = "https://www.googleapis.com/youtube/v3/search"


def search_video_on_channel(channel_id: str, title: str) -> str | None:
    """Search YouTube for a video by title within a specific channel.
    Returns the best-match video_id, or None on failure."""
    if not API_KEY:
        print("[ERROR] YOUTUBE_API_KEY not set — cannot resolve video IDs.")
        return None

    params = {
        "key":        API_KEY,
        "part":       "snippet",
        "channelId":  channel_id,
        "q":          title,
        "type":       "video",
        "maxResults": 3,
        "order":      "relevance",
    }
    try:
        r = requests.get(SEARCH_URL, params=params, timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
        if items:
            return items[0]["id"]["videoId"]
    except Exception as e:
        print(f"  [WARN] Search failed for '{title}': {e}")
    return None


def main():
    print("── Resolving Evergreen Anchor Video IDs ─────────────────────────")

    if not os.path.exists(CONFIG_FILE):
        print(f"[ERROR] Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    cfg = pd.read_csv(CONFIG_FILE)

    if "video_id" not in cfg.columns:
        print("[ERROR] Config missing 'video_id' column.")
        sys.exit(1)

    tbd_mask  = cfg["video_id"].str.strip().str.upper() == "TBD"
    tbd_count = tbd_mask.sum()
    print(f"  Found {tbd_count} anchor(s) with TBD video_id\n")

    if tbd_count == 0:
        print("  All anchors already resolved. Nothing to do.")
        return

    resolved   = 0
    unresolved = 0

    for idx, row in cfg[tbd_mask].iterrows():
        slug       = row["video_slug"]
        title      = row["title"]
        channel_id = row["channel_id"]
        channel    = row["channel_label"]

        print(f"  Resolving [{channel}] {slug}")
        print(f"    Query: \"{title}\"")

        vid_id = search_video_on_channel(channel_id, title)

        if vid_id:
            cfg.at[idx, "video_id"] = vid_id
            print(f"    ✓ Resolved → https://youtube.com/watch?v={vid_id}")
            resolved += 1
        else:
            print(f"    ✗ Could not resolve — leaving as TBD")
            unresolved += 1

    cfg.to_csv(CONFIG_FILE, index=False)

    print(f"\n── Resolution Summary ────────────────────────────────────────────")
    print(f"  Resolved:   {resolved}")
    print(f"  Unresolved: {unresolved}")
    print(f"  Config updated → {CONFIG_FILE}")
    print(f"\n  Please review resolved IDs before running fetch_youtube_evergreen_anchors.py")
    print(f"  You can verify any ID by visiting: https://youtube.com/watch?v=<video_id>")


if __name__ == "__main__":
    main()
