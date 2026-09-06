#!/usr/bin/env python3
"""
Seed youtube_evergreen_anchors.csv and youtube_anchor_history.csv.

Steps:
1. YouTube API → top-N videos by view count per channel (current snapshot)
2. Wayback Machine CDX API → find archived YouTube pages for each video in 2023/2024/2025
3. Fetch each archive page and extract view count from YouTube's initial-data JSON blob
4. Write data/youtube_evergreen_anchors.csv (all snapshots) for the generator
5. Write config/youtube_evergreen_anchors.csv (video config list)
"""

import os
import re
import json
import time
import datetime
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

API_KEY   = os.environ["YOUTUBE_API_KEY"]
DATA_DIR  = Path(__file__).parent.parent / "data"
CFG_DIR   = Path(__file__).parent.parent / "config"

# Channels: label → channel_id
CHANNELS = {
    "Warhammer_Official":  "UCwdh3MTrFq3sXlB4ct8B-Fg",
    "WesHammer":           "UCSDj6ttwzj2sr464jDdg_pA",
    "Luetin09":            "UC8RfCCzWsMgNspTI-GTFenQ",
    "Squidmar_Miniatures": "UCDvZTWvHZPTxJ4K1yTD2a1g",
    "Majorkill":           "UC_wb8IVtmXwil8bN3IdVtZw",
    "Auspex_Tactics":      "UC6Gco9PWxmJmJ5CqfbChuiQ",
    "Valrak":              "UCrCHY6wVw5D7hMsM-LPBr1w",
}

# Content-type hints (best-guess for flagship video types per channel)
CONTENT_TYPE_HINTS = {
    "Warhammer_Official":  "Official Media",
    "WesHammer":           "Lore Education",
    "Luetin09":            "Lore Education",
    "Squidmar_Miniatures": "Hobby Tutorial",
    "Majorkill":           "Entertainment / Commentary",
    "Auspex_Tactics":      "Entertainment / Commentary",
    "Valrak":              "Lore Education",
}

TOP_N = 3          # videos per channel
TODAY = datetime.date.today().isoformat()
TARGET_YEARS = [2023, 2024, 2025]   # historical years to try via Wayback
WB_WAIT = 1.2      # seconds between Wayback requests


def yt_get(endpoint, params):
    params["key"] = API_KEY
    r = requests.get(f"https://www.googleapis.com/youtube/v3/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def get_top_videos(channel_id, n=TOP_N):
    """Return list of {video_id, title, views, published_at} for top-n by view count."""
    # search.list with order=viewCount gives most-viewed uploads
    try:
        sr = yt_get("search", {
            "part": "id,snippet", "channelId": channel_id,
            "type": "video", "order": "viewCount", "maxResults": n * 3,
        })
    except Exception as e:
        print(f"  search error for {channel_id}: {e}")
        return []

    video_ids = [item["id"]["videoId"] for item in sr.get("items", []) if item["id"].get("videoId")][:n*3]
    if not video_ids:
        return []

    # videos.list for actual view counts
    vr = yt_get("videos", {
        "part": "statistics,snippet", "id": ",".join(video_ids)
    })
    results = []
    for item in vr.get("items", []):
        vid = item["id"]
        stats = item.get("statistics", {})
        snip  = item.get("snippet", {})
        views = int(stats.get("viewCount", 0))
        title = snip.get("title", "")
        pub   = snip.get("publishedAt", "")[:10]
        results.append({"video_id": vid, "title": title, "views": views, "published_at": pub})

    results.sort(key=lambda x: -x["views"])
    return results[:n]


def wb_find_snapshot(video_id, year):
    """Find a Wayback Machine snapshot URL for a YouTube video in a given year."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    # CDX API: find closest snapshot to mid-year
    target_ts = f"{year}0615"
    cdx_url = (
        f"http://web.archive.org/cdx/search/cdx"
        f"?url={url}&output=json&fl=timestamp,original&limit=3"
        f"&from={year}0101&to={year}1231&filter=statuscode:200"
        f"&closest={target_ts}"
    )
    try:
        r = requests.get(cdx_url, timeout=20)
        rows = r.json()
        if len(rows) < 2:
            return None
        # rows[0] = header, rows[1:] = data
        ts = rows[1][0]
        return f"https://web.archive.org/web/{ts}/https://www.youtube.com/watch?v={video_id}", ts[:8]
    except Exception:
        return None


def wb_extract_views(wb_url):
    """Fetch a Wayback-archived YouTube page and extract viewCount from initial data."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        r = requests.get(wb_url, headers=headers, timeout=20)
        html = r.text

        # YouTube embeds stats in var ytInitialData or ytInitialPlayerResponse
        m = re.search(r'"viewCount"\s*:\s*\{\s*"videoViewCountRenderer"\s*:\s*\{[^}]*?"shortViewCount"\s*:\s*\{[^}]*?"simpleText"\s*:\s*"([^"]+)"', html)
        if m:
            raw = m.group(1).replace(",", "").replace("\xa0", "")
            num = re.sub(r"[^\d]", "", raw)
            return int(num) if num else None

        # fallback: "viewCount":"NNN"
        m2 = re.search(r'"viewCount"\s*:\s*"(\d+)"', html)
        if m2:
            return int(m2.group(1))

        # fallback 2: videoDetails.viewCount
        m3 = re.search(r'videoDetails["\s\S]{0,200}"viewCount"\s*:\s*"(\d+)"', html)
        if m3:
            return int(m3.group(1))

        return None
    except Exception:
        return None


def slugify(title):
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s[:60].strip("_")


def main():
    rows = []   # (date, channel_label, video_id, video_slug, title, views, content_type)

    for ch_label, ch_id in CHANNELS.items():
        ct = CONTENT_TYPE_HINTS.get(ch_label, "Entertainment / Commentary")
        print(f"\n── {ch_label} ({ch_id})")
        videos = get_top_videos(ch_id)
        if not videos:
            print("  no videos found")
            continue

        for v in videos:
            vid   = v["video_id"]
            title = v["title"]
            slug  = f"{slugify(ch_label)}_{slugify(title)}"
            curr_views = v["views"]
            print(f"  [{vid}] {title[:60]}  current={curr_views:,}")

            # Current snapshot (today)
            rows.append({
                "date": TODAY, "channel_label": ch_label,
                "video_id": vid, "video_slug": slug,
                "title": title, "views": curr_views, "content_type": ct,
            })

            # Historical snapshots via Wayback Machine
            for yr in TARGET_YEARS:
                time.sleep(WB_WAIT)
                result = wb_find_snapshot(vid, yr)
                if result is None:
                    print(f"    {yr}: no Wayback snapshot")
                    continue
                wb_url, wb_date_s = result
                wb_date = f"{wb_date_s[:4]}-{wb_date_s[4:6]}-{wb_date_s[6:8]}"
                time.sleep(WB_WAIT)
                hist_views = wb_extract_views(wb_url)
                if hist_views is None:
                    print(f"    {yr} ({wb_date}): snapshot found but view count not parseable")
                    continue
                print(f"    {yr} ({wb_date}): {hist_views:,} views")
                rows.append({
                    "date": wb_date, "channel_label": ch_label,
                    "video_id": vid, "video_slug": slug,
                    "title": title, "views": hist_views, "content_type": ct,
                })

    if not rows:
        print("\nNo data collected.")
        return

    df = pd.DataFrame(rows).drop_duplicates(subset=["date","channel_label","video_slug"])
    df = df.sort_values(["channel_label","video_slug","date"]).reset_index(drop=True)

    # Write data/youtube_evergreen_anchors.csv (all snapshots — used by generator)
    out_data = DATA_DIR / "youtube_evergreen_anchors.csv"
    df.to_csv(out_data, index=False)
    print(f"\n✓ Wrote {len(df)} rows → {out_data}")

    # Write config/youtube_evergreen_anchors.csv (unique video list — config)
    cfg_df = df[["video_id","video_slug","title","channel_label","content_type"]].drop_duplicates("video_slug")
    out_cfg = CFG_DIR / "youtube_evergreen_anchors.csv"
    cfg_df.to_csv(out_cfg, index=False)
    print(f"✓ Wrote {len(cfg_df)} videos → {out_cfg}")

    # Summary
    print("\n── Coverage summary ──")
    for ch in CHANNELS:
        ch_df = df[df["channel_label"] == ch]
        vids  = ch_df["video_slug"].nunique()
        dates = sorted(ch_df["date"].unique())
        print(f"  {ch}: {vids} videos, dates={dates}")


if __name__ == "__main__":
    main()
