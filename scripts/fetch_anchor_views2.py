#!/usr/bin/env python3
"""
Pass 2: fix anchor data.
- Remove viral/recent videos (only 1 snapshot far back + huge jump)
- Get Luetin09 via uploads playlist (search.list failed)
- For channels missing historical data: target videos published pre-2022
  to ensure they have multi-year history, then Wayback Machine
"""

import os, re, time, datetime, requests, json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

API_KEY  = os.environ["YOUTUBE_API_KEY"]
DATA_DIR = Path(__file__).parent.parent / "data"
CFG_DIR  = Path(__file__).parent.parent / "config"
TODAY    = datetime.date.today().isoformat()
WB_WAIT  = 1.0

CHANNELS = {
    "Warhammer_Official":  "UCwdh3MTrFq3sXlB4ct8B-Fg",
    "WesHammer":           "UCSDj6ttwzj2sr464jDdg_pA",
    "Luetin09":            "UC8RfCCzWsMgNspTI-GTFenQ",
    "Squidmar_Miniatures": "UCDvZTWvHZPTxJ4K1yTD2a1g",
    "Majorkill":           "UC_wb8IVtmXwil8bN3IdVtZw",
    "Auspex_Tactics":      "UC6Gco9PWxmJmJ5CqfbChuiQ",
    "Valrak":              "UCrCHY6wVw5D7hMsM-LPBr1w",
}

CONTENT_TYPE = {
    "Warhammer_Official":  "Official Media",
    "WesHammer":           "Lore Education",
    "Luetin09":            "Lore Education",
    "Squidmar_Miniatures": "Hobby Tutorial",
    "Majorkill":           "Entertainment / Commentary",
    "Auspex_Tactics":      "Entertainment / Commentary",
    "Valrak":              "Lore Education",
}

# Channels that only got today's data — need pre-2022 videos for historical context
NEED_HISTORY = ["Warhammer_Official", "Majorkill", "Auspex_Tactics", "Valrak", "Luetin09"]


def yt_get(endpoint, params):
    params["key"] = API_KEY
    r = requests.get(f"https://www.googleapis.com/youtube/v3/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def get_uploads_playlist(channel_id):
    """Get uploads playlist ID for a channel."""
    r = yt_get("channels", {"part": "contentDetails", "id": channel_id})
    items = r.get("items", [])
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_playlist_videos(playlist_id, max_results=50):
    """Return list of video IDs from a playlist."""
    video_ids = []
    page_token = None
    while len(video_ids) < max_results:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        r = yt_get("playlistItems", params)
        for item in r.get("items", []):
            vid = item["contentDetails"].get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = r.get("nextPageToken")
        if not page_token or len(video_ids) >= max_results:
            break
    return video_ids


def get_video_stats(video_ids):
    """Batch-fetch video stats. Returns list of {video_id, title, views, published_at}."""
    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        r = yt_get("videos", {"part": "statistics,snippet", "id": ",".join(batch)})
        for item in r.get("items", []):
            results.append({
                "video_id":     item["id"],
                "title":        item["snippet"].get("title", ""),
                "views":        int(item["statistics"].get("viewCount", 0)),
                "published_at": item["snippet"].get("publishedAt", "")[:10],
            })
    return results


def get_top_old_videos(channel_id, n=3, before="2022-01-01"):
    """Get top-n most-viewed videos published before `before`."""
    try:
        sr = yt_get("search", {
            "part": "id", "channelId": channel_id, "type": "video",
            "order": "viewCount", "maxResults": 25,
            "publishedBefore": f"{before}T00:00:00Z",
        })
    except Exception as e:
        print(f"  search error: {e}")
        return []
    ids = [i["id"]["videoId"] for i in sr.get("items", []) if i["id"].get("videoId")]
    if not ids:
        return []
    stats = get_video_stats(ids)
    stats.sort(key=lambda x: -x["views"])
    return stats[:n]


def get_top_videos_by_playlist(channel_id, n=5, before="2023-01-01"):
    """Fallback for channels where search.list fails: scan uploads playlist."""
    pl = get_uploads_playlist(channel_id)
    if not pl:
        return []
    ids = get_playlist_videos(pl, max_results=200)
    stats = get_video_stats(ids)
    # Filter for videos published before the cutoff
    old = [v for v in stats if v["published_at"] < before]
    old.sort(key=lambda x: -x["views"])
    return old[:n]


def wb_snapshot(video_id, year):
    """Try Wayback Machine for a given video+year. Returns (wb_url, date_str) or None."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    target_ts = f"{year}0615"
    cdx = (
        f"http://web.archive.org/cdx/search/cdx?url={url}&output=json"
        f"&fl=timestamp,statuscode&limit=5&from={year}0101&to={year}1231"
        f"&closest={target_ts}"
    )
    try:
        r = requests.get(cdx, timeout=20)
        rows = r.json()
        for row in rows[1:]:
            ts, sc = row
            if sc in ("200", "301", "302", "-"):
                date_s = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                wb_url = f"https://web.archive.org/web/{ts}if_/https://www.youtube.com/watch?v={video_id}"
                return wb_url, date_s
    except Exception:
        pass
    return None


def wb_views(wb_url):
    """Extract view count from Wayback-archived YouTube page HTML."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(wb_url, headers=headers, timeout=25)
        html = r.text
        # Primary: "viewCount":"NNN"
        m = re.search(r'"viewCount"\s*:\s*"(\d+)"', html)
        if m:
            return int(m.group(1))
        # Secondary: videoDetails block
        m2 = re.search(r'"videoDetails"[^}]{0,500}"viewCount"\s*:\s*"(\d+)"', html, re.DOTALL)
        if m2:
            return int(m2.group(1))
        return None
    except Exception:
        return None


def slugify(ch, title):
    s = f"{ch}_{title}".lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s[:60].strip("_")


def main():
    # ── Load existing data ────────────────────────────────────────────────────
    existing_path = DATA_DIR / "youtube_evergreen_anchors.csv"
    if existing_path.exists():
        existing = pd.read_csv(existing_path)
    else:
        existing = pd.DataFrame()

    # Remove problematic viral video: WesHammer HLA7TjwrKdY
    # (had 8K views in Aug 2024 right after posting; now 3M — not evergreen)
    BAD_IDS = {"HLA7TjwrKdY", "vqLpCUKehWI"}  # remove videos with no valid history
    if not existing.empty and "video_id" in existing.columns:
        existing = existing[~existing["video_id"].isin(BAD_IDS)]
        print(f"After removing viral videos: {len(existing)} rows")

    new_rows = []

    # ── Luetin09 via uploads playlist (search.list returned nothing) ──────────
    print("\n── Luetin09 (uploads playlist scan)")
    luetin_vids = get_top_videos_by_playlist("UC8RfCCzWsMgNspTI-GTFenQ", n=4, before="2023-01-01")
    for v in luetin_vids:
        slug = slugify("luetin09", v["title"])
        print(f"  [{v['video_id']}] {v['title'][:60]}  pub={v['published_at']}  views={v['views']:,}")
        # Current snapshot
        new_rows.append({
            "date": TODAY, "channel_label": "Luetin09",
            "video_id": v["video_id"], "video_slug": slug,
            "title": v["title"], "views": v["views"], "content_type": "Lore Education",
        })
        # Historical via Wayback
        for yr in [2023, 2024, 2025]:
            time.sleep(WB_WAIT)
            wb = wb_snapshot(v["video_id"], yr)
            if wb is None:
                print(f"    {yr}: no snapshot")
                continue
            wb_url, wb_date = wb
            time.sleep(WB_WAIT)
            views = wb_views(wb_url)
            if views:
                print(f"    {yr} ({wb_date}): {views:,}")
                new_rows.append({
                    "date": wb_date, "channel_label": "Luetin09",
                    "video_id": v["video_id"], "video_slug": slug,
                    "title": v["title"], "views": views, "content_type": "Lore Education",
                })
            else:
                print(f"    {yr} ({wb_date}): snapshot found, views not parseable")

    # ── Channels with only today's data — find older videos ──────────────────
    for ch_label in ["Warhammer_Official", "Majorkill", "Auspex_Tactics", "Valrak"]:
        # Check if we already have historical pairs in existing data
        ch_existing = existing[existing["channel_label"] == ch_label] if not existing.empty else pd.DataFrame()
        has_hist = not ch_existing.empty and ch_existing["date"].nunique() > 1
        if has_hist:
            print(f"\n── {ch_label}: already has historical pairs, skipping")
            continue

        print(f"\n── {ch_label}: fetching pre-2022 videos for historical context")
        ch_id = CHANNELS[ch_label]
        ct    = CONTENT_TYPE[ch_label]
        vids  = get_top_old_videos(ch_id, n=3, before="2022-01-01")
        if not vids:
            print("  no pre-2022 videos found via search, trying playlist scan")
            vids = get_top_videos_by_playlist(ch_id, n=3, before="2022-01-01")
        for v in vids:
            slug = slugify(ch_label.lower().replace("_", ""), v["title"])
            print(f"  [{v['video_id']}] {v['title'][:60]}  pub={v['published_at']}  views={v['views']:,}")
            new_rows.append({
                "date": TODAY, "channel_label": ch_label,
                "video_id": v["video_id"], "video_slug": slug,
                "title": v["title"], "views": v["views"], "content_type": ct,
            })
            for yr in [2023, 2024, 2025]:
                time.sleep(WB_WAIT)
                wb = wb_snapshot(v["video_id"], yr)
                if wb is None:
                    print(f"    {yr}: no snapshot")
                    continue
                wb_url, wb_date = wb
                time.sleep(WB_WAIT)
                views = wb_views(wb_url)
                if views:
                    print(f"    {yr} ({wb_date}): {views:,}")
                    new_rows.append({
                        "date": wb_date, "channel_label": ch_label,
                        "video_id": v["video_id"], "video_slug": slug,
                        "title": v["title"], "views": views, "content_type": ct,
                    })
                else:
                    print(f"    {yr} ({wb_date}): not parseable")

    # ── Merge and save ────────────────────────────────────────────────────────
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = existing

    combined = combined.drop_duplicates(subset=["date", "channel_label", "video_slug"])
    combined = combined.sort_values(["channel_label", "video_slug", "date"]).reset_index(drop=True)

    combined.to_csv(existing_path, index=False)
    print(f"\n✓ Wrote {len(combined)} rows → {existing_path}")

    # Config file (unique videos)
    cfg_df = combined[["video_id","video_slug","title","channel_label","content_type"]].drop_duplicates("video_slug")
    cfg_path = CFG_DIR / "youtube_evergreen_anchors.csv"
    cfg_df.to_csv(cfg_path, index=False)
    print(f"✓ Wrote {len(cfg_df)} videos → {cfg_path}")

    # Summary
    print("\n── Coverage summary ──")
    for ch in CHANNELS:
        ch_df = combined[combined["channel_label"] == ch]
        vids  = ch_df["video_slug"].nunique()
        dates = sorted(ch_df["date"].unique())
        pairs = [(v, ch_df[ch_df["video_slug"] == v]["date"].nunique())
                 for v in ch_df["video_slug"].unique()]
        valid = sum(1 for _, n in pairs if n >= 2)
        print(f"  {ch}: {vids} videos, {valid} with paired dates, all_dates={dates}")


if __name__ == "__main__":
    main()
