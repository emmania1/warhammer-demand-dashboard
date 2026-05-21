"""
Retail signal scanner for Warhammer creator channels.

Scans video titles (and optionally descriptions via YouTube API) for keywords
that indicate retail activity: sales announcements, bestseller content, sold-out
notices, pre-orders, new releases, and industry commentary.

Target channels: Element_Games, Honest_Wargamer (retail / industry commentary)
Extended scan:   All channels, for broader retail-adjacent signals.

Saves flagged videos to data/retail_signals.csv.
Deduplicates on video_id — re-running is safe.
"""

import os, csv, time, re
import requests
import pandas as pd
from pathlib import Path
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

KEY              = os.getenv("YOUTUBE_API_KEY")
VIDEOS_FILE      = Path("data/youtube_videos_unified.csv")
OUT              = Path("data/retail_signals.csv")
OUT.parent.mkdir(exist_ok=True)
today            = str(date.today())

# ── Signal keyword groups ─────────────────────────────────────────────────────
SIGNAL_GROUPS = {
    "sales_figures": [
        "sales figures", "we sold", "units sold", "revenue", "profit",
        "bestsell", "best sell", "top seller", "number one seller", "#1 seller",
        "sales record", "broke records", "highest selling",
    ],
    "sold_out": [
        "sold out", "out of stock", "sold through", "flying off",
        "can't keep", "can not keep", "back in stock", "restock",
    ],
    "new_release": [
        "new release", "just released", "out now", "available now",
        "launching today", "launch day", "pre-order", "preorder",
        "pre order", "up for order", "order now", "available to order",
    ],
    "industry_commentary": [
        "industry", "market", "gw stock", "games workshop stock",
        "shareholder", "annual report", "sales report", "business",
        "retail", "store sales", "lgs", "local game store",
        "price increase", "price rise", "price hike",
    ],
    "discount_deal": [
        "discount", "sale %", "% off", "deal", "bundle", "save money",
        "black friday", "boxing day", "cyber monday", "clearance",
    ],
    "demand_signal": [
        "demand", "popular", "trending", "everyone is buying",
        "flying out", "can't stop", "unstoppable", "huge",
    ],
}

# Channels to scan deeply (primary targets)
PRIMARY_CHANNELS = {"Element_Games", "Honest_Wargamer"}
# All channels also scanned, but with a stricter keyword match threshold

# Warhammer context terms — at least one must appear for a signal to be valid
WARHAMMER_CONTEXT = [
    "warhammer", "games workshop", "40k", "age of sigmar", "aos",
    "space marine", "chaos space", "ork", "eldar", "necron", "tau", "tyranid",
    "stormcast", "primaris", "heresy", "grimdark", "grimdank",
    "miniature", "minis", "mini kit", "paint pot", "citadel", "resin kit",
    "sigmar", "primarch", "astartes", "imperium", "nurgle", "tzeentch",
    "khorne", "slaanesh", "dark angels", "ultramarine", "blood angel",
]

def has_warhammer_context(text: str) -> bool:
    """Returns True only if text contains at least one Warhammer-related term."""
    t = text.lower()
    return any(term in t for term in WARHAMMER_CONTEXT)


def find_signals(text: str) -> dict:
    """Returns {signal_type: [matched_keywords]} for all matches."""
    text_lower = text.lower()
    found = {}
    for signal_type, keywords in SIGNAL_GROUPS.items():
        hits = [kw for kw in keywords if kw in text_lower]
        if hits:
            found[signal_type] = hits
    return found


# ── Load existing video data ───────────────────────────────────────────────────
if not VIDEOS_FILE.exists():
    print(f"No video data found at {VIDEOS_FILE} — run fetch_youtube_videos_unified.py first.")
    exit(0)

df_vids = pd.read_csv(VIDEOS_FILE)
# Take the latest snapshot only
latest_snap = df_vids["as_of_date"].max()
df_vids = df_vids[df_vids["as_of_date"] == latest_snap].copy()
print(f"Scanning {len(df_vids)} videos (snapshot: {latest_snap})")

# ── Step 1: title scan (all channels) ─────────────────────────────────────────
flagged_rows = []

for _, row in df_vids.iterrows():
    title   = str(row.get("title", ""))
    channel = str(row.get("channel_label", ""))
    is_primary = channel in PRIMARY_CHANNELS

    signals = find_signals(title)

    # Require Warhammer context in title (prevents false positives from wrestling, gaming news, etc.)
    if not has_warhammer_context(title):
        continue
    # For non-primary channels, require at least 2 different signal types to reduce noise
    if not is_primary and len(signals) < 2:
        continue
    if not signals:
        continue

    signal_types   = list(signals.keys())
    keywords_found = [kw for hits in signals.values() for kw in hits]

    flagged_rows.append({
        "video_id":      row["video_id"],
        "channel_label": channel,
        "title":         title,
        "published_at":  str(row.get("published_at", ""))[:10],
        "views":         int(row.get("views", 0) or 0),
        "signal_types":  "|".join(signal_types),
        "keywords_found": "|".join(keywords_found),
        "source":        "title_scan",
        "date_fetched":  today,
    })

print(f"  Title scan → {len(flagged_rows)} videos flagged")

# ── Step 2: description scan via YouTube API for primary channels ──────────────
if KEY:
    primary_ids = df_vids[df_vids["channel_label"].isin(PRIMARY_CHANNELS)]["video_id"].tolist()
    already_flagged = {r["video_id"] for r in flagged_rows}
    to_check = [vid for vid in primary_ids if vid not in already_flagged]

    print(f"  Fetching descriptions for {len(to_check)} primary-channel videos...")
    for i in range(0, len(to_check), 50):
        batch = to_check[i:i+50]
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet",
                    "id":   ",".join(batch),
                    "key":  KEY,
                },
                timeout=30,
            )
            r.raise_for_status()
            for item in r.json().get("items", []):
                vid_id = item["id"]
                snip   = item.get("snippet", {})
                desc   = snip.get("description", "")
                title  = snip.get("title", "")
                full_text = title + " " + desc

                signals = find_signals(full_text)
                if not signals:
                    continue
                # Require Warhammer context even in description scan
                if not has_warhammer_context(full_text):
                    continue

                # Check if already in flagged_rows and merge, or add new
                matching = [f for f in flagged_rows if f["video_id"] == vid_id]
                if matching:
                    # Merge new signal types from description
                    existing = matching[0]
                    new_types = list(signals.keys())
                    existing_types = existing["signal_types"].split("|")
                    merged_types = list(set(existing_types + new_types))
                    existing["signal_types"] = "|".join(merged_types)
                    existing["source"] = "title+desc_scan"
                else:
                    vid_row = df_vids[df_vids["video_id"] == vid_id]
                    if not vid_row.empty:
                        vr = vid_row.iloc[0]
                        signal_types   = list(signals.keys())
                        keywords_found = [kw for hits in signals.values() for kw in hits]
                        flagged_rows.append({
                            "video_id":      vid_id,
                            "channel_label": str(vr["channel_label"]),
                            "title":         title,
                            "published_at":  str(vr.get("published_at", ""))[:10],
                            "views":         int(vr.get("views", 0) or 0),
                            "signal_types":  "|".join(signal_types),
                            "keywords_found": "|".join(keywords_found),
                            "source":        "desc_scan",
                            "date_fetched":  today,
                        })
            time.sleep(0.2)
        except Exception as e:
            print(f"    Error fetching descriptions batch: {e}")

    print(f"  After description scan → {len(flagged_rows)} videos flagged total")
else:
    print("  (No YouTube API key — skipping description scan)")

# ── Save ───────────────────────────────────────────────────────────────────────
df_new = pd.DataFrame(flagged_rows)

if not df_new.empty:
    if OUT.exists():
        df_old = pd.read_csv(OUT)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["video_id"], keep="last")
    else:
        df = df_new

    df = df.sort_values("published_at", ascending=False)
    df.to_csv(OUT, index=False)
    print(f"\nSaved → {OUT} | {len(df)} retail signals total")

    # Print summary
    print(f"\n{'Channel':<25} {'Title':<55} {'Signals'}")
    print("─" * 100)
    for _, r in df.head(15).iterrows():
        ch = str(r["channel_label"])[:24]
        ti = str(r["title"])[:54]
        si = str(r["signal_types"])
        print(f"  {ch:<24} {ti:<55} {si}")
else:
    print("\nNo retail signals found in current video data.")
    # Create empty file
    if not OUT.exists():
        pd.DataFrame(columns=[
            "video_id","channel_label","title","published_at","views",
            "signal_types","keywords_found","source","date_fetched"
        ]).to_csv(OUT, index=False)
