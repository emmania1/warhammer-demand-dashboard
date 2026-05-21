#!/usr/bin/env python3
"""
Warhammer Demand Dashboard — Live Data Patcher
Patches window.__yt in index.html with fresh data from:
  - Reddit API       (subscriber counts — run daily)
  - SteamCharts      (monthly avg players — run on 3rd of each month)
  - Reddit store API (store-thread counts — run daily, accumulates)

CRON SETUP (add to crontab -e):
  # Daily at 08:00 — Reddit subs + store threads
  0 8 * * * cd /Users/emmania/Desktop/warhammer_demand && python3 update_data.py --reddit --store >> update_log.txt 2>&1

  # Monthly on 3rd at 08:30 — Steam (prior month is fully closed)
  30 8 3 * * cd /Users/emmania/Desktop/warhammer_demand && python3 update_data.py --steam >> update_log.txt 2>&1

  # Quarterly Google Maps review velocity (1st of Jan, Apr, Jul, Oct at 07:00)
  # Requires GOOGLE_PLACES_API_KEY in environment.
  0 7 1 1,4,7,10 * cd /Users/emmania/Desktop/warhammer_demand && source venv/bin/activate && python3 update_data.py --gmaps >> update_log.txt 2>&1

  # Or run everything at once:
  0 8 3 * * cd /Users/emmania/Desktop/warhammer_demand && python3 update_data.py --all >> update_log.txt 2>&1
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Config ───────────────────────────────────────────────────────────────────
INDEX_HTML  = Path(__file__).parent / "index.html"
LOG_FILE    = Path(__file__).parent / "update_log.txt"
USER_AGENT  = "warhammer-demand-tracker/2.0"

REDDIT_SUBS  = ["Warhammer", "Warhammer40k", "AgeOfSigmar", "minipainting"]
REDDIT_LABELS = ["r/Warhammer", "r/Warhammer40k", "r/AgeOfSigmar", "r/minipainting"]

STEAM_GAMES = {
    "Total War: WH3": "1142710",
    "Space Marine 2": "2183900",
    "Darktide":       "1361210",
    "Vermintide 2":   "552500",
}
STEAM_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

STORE_SEARCH = (
    'title:FLGS OR title:LGS OR title:"local game store" OR '
    'title:"game store" OR title:"hobby shop" OR title:"game shop" OR '
    'title:"warhammer store" OR title:"local store"'
)

# ── Logging ───────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── HTML patch helpers ────────────────────────────────────────────────────────
def load_html():
    return INDEX_HTML.read_text(encoding="utf-8")


def extract_yt(html):
    m = re.search(r"(window\.__yt\s*=\s*)(\{.*?\})(;\s*\n)", html, re.DOTALL)
    if not m:
        raise ValueError("window.__yt not found in index.html")
    return m, json.loads(m.group(2))


def write_yt(html, m, data):
    new_blob = m.group(1) + json.dumps(data, separators=(",", ":")) + m.group(3)
    return html[: m.start()] + new_blob + html[m.end() :]


# ── Reddit subscriber fetch ───────────────────────────────────────────────────
def fetch_reddit_subs():
    counts = []
    for sub in REDDIT_SUBS:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/about.json",
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            r.raise_for_status()
            n = r.json()["data"]["subscribers"]
            counts.append(n)
            log(f"  Reddit r/{sub}: {n:,}")
            time.sleep(0.8)
        except Exception as e:
            log(f"  Reddit r/{sub} ERROR: {e}")
            counts.append(None)
    return counts


def patch_reddit(data, counts):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rd = data["reddit"]

    # Update my2026
    current = list(rd.get("my2026", [None] * len(REDDIT_LABELS)))
    for i, n in enumerate(counts):
        if n is not None:
            current[i] = n
    rd["my2026"] = current

    # Append trajectory point (skip if already have today's date)
    for i, ds in enumerate(rd.get("trajDatasets", [])):
        if i >= len(counts) or counts[i] is None:
            continue
        pts = ds.get("data", [])
        if pts and pts[-1].get("x") == today:
            pts[-1]["y"] = counts[i]   # overwrite same-day
        else:
            pts.append({"x": today, "y": counts[i]})
        ds["data"] = pts

    changed = [f"{REDDIT_LABELS[i]}={counts[i]:,}"
               for i, n in enumerate(counts) if n is not None]
    return ", ".join(changed)


# ── SteamCharts scrape ────────────────────────────────────────────────────────
MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def scrape_steam(app_id):
    r = requests.get(
        f"https://steamcharts.com/app/{app_id}",
        headers={"User-Agent": STEAM_UA},
        timeout=20,
    )
    r.raise_for_status()
    rows = re.findall(
        r'<td class="month-cell[^"]*"[^>]*>(.*?)</td>.*?'
        r'<td class="right num-f[^"]*">([\d.,]+)</td>',
        r.text, re.DOTALL,
    )
    result = {}
    for month_str, avg_str in rows:
        month_str = month_str.strip()
        if month_str == "Last 30 Days":
            continue
        parts = month_str.split()
        if len(parts) == 2 and parts[0] in MONTH_MAP:
            key = f"{parts[1]}-{MONTH_MAP[parts[0]]:02d}"
            result[key] = round(float(avg_str.replace(",", "")), 1)
    return result


def patch_steam(data, steam_results):
    s = data["steam"]
    labels = s["monthlyLabels"]
    changes = []

    for ds in s.get("monthlyDatasets", []):
        name = ds["label"]
        scraped = steam_results.get(name, {})
        if not scraped:
            continue
        vals = ds["data"]
        updated = 0
        for i, lbl in enumerate(labels):
            if lbl in scraped:
                new_val = scraped[lbl]
                if vals[i] != new_val:
                    vals[i] = new_val
                    updated += 1
        # Append any new months not yet in labels
        latest_label = labels[-1] if labels else "1900-01"
        for month_key in sorted(scraped.keys()):
            if month_key > latest_label:
                labels.append(month_key)
                vals.append(scraped[month_key])
                for other_ds in s["monthlyDatasets"]:
                    if other_ds["label"] != name:
                        other_ds["data"].append(None)
                updated += 1
        if updated:
            changes.append(f"{name}: {updated} cell(s) updated")
        ds["data"] = vals

    s["monthlyLabels"] = labels
    return "; ".join(changes) if changes else "no changes"


# ── Reddit store thread count ─────────────────────────────────────────────────
def fetch_store_count():
    today_ym = datetime.now(timezone.utc).strftime("%Y-%m")
    total = 0
    for sub in ["Warhammer", "Warhammer40k"]:
        try:
            url = (
                f"https://www.reddit.com/r/{sub}/search.json"
                f"?q={requests.utils.quote(STORE_SEARCH)}"
                f"&restrict_sr=1&sort=new&t=year&limit=100"
            )
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            posts = r.json().get("data", {}).get("children", [])
            month_count = sum(
                1 for p in posts
                if datetime.fromtimestamp(
                    int(p["data"]["created_utc"]), tz=timezone.utc
                ).strftime("%Y-%m") == today_ym
            )
            total += month_count
            log(f"  Store threads r/{sub} ({today_ym}): {month_count}")
            time.sleep(1.0)
        except Exception as e:
            log(f"  Store threads r/{sub} ERROR: {e}")
    return today_ym, total


def patch_store(data, today_ym, count):
    rt = data.get("retail", {})
    labels = rt.get("storeThreadsLabels", [])
    vals   = rt.get("storeThreadsVals", [])
    if today_ym in labels:
        idx = labels.index(today_ym)
        old = vals[idx]
        vals[idx] = max(old, count)   # take higher (accumulated data wins)
        change = f"{today_ym}: {old}→{vals[idx]}"
    else:
        labels.append(today_ym)
        vals.append(count)
        change = f"new month {today_ym}={count}"
    rt["storeThreadsLabels"] = labels
    rt["storeThreadsVals"]   = vals
    return change


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Patch index.html with fresh data")
    parser.add_argument("--reddit", action="store_true", help="Fetch Reddit subscriber counts")
    parser.add_argument("--steam",  action="store_true", help="Scrape SteamCharts")
    parser.add_argument("--store",  action="store_true", help="Fetch Reddit store threads")
    parser.add_argument("--gmaps",  action="store_true",
                        help="Quarterly Google Maps review velocity (requires GOOGLE_PLACES_API_KEY)")
    parser.add_argument("--all",    action="store_true", help="Run all sources")
    args = parser.parse_args()

    if not any([args.reddit, args.steam, args.store, args.gmaps, args.all]):
        parser.print_help()
        sys.exit(0)

    do_reddit = args.reddit or args.all
    do_steam  = args.steam  or args.all
    do_store  = args.store  or args.all
    do_gmaps  = args.gmaps  or args.all

    log("=" * 60)
    log(f"update_data.py started  reddit={do_reddit} steam={do_steam} store={do_store}")

    html = load_html()
    m, data = extract_yt(html)
    summary = []

    # ── Reddit subs ──────────────────────────────────────────────────────────
    if do_reddit:
        log("Fetching Reddit subscriber counts...")
        try:
            counts = fetch_reddit_subs()
            change = patch_reddit(data, counts)
            summary.append(f"Reddit subs: {change}")
            log(f"Reddit subs patched: {change}")
        except Exception as e:
            log(f"Reddit subs FAILED: {e}")

    # ── Steam ────────────────────────────────────────────────────────────────
    if do_steam:
        log("Scraping SteamCharts...")
        steam_results = {}
        for name, app_id in STEAM_GAMES.items():
            try:
                steam_results[name] = scrape_steam(app_id)
                log(f"  {name}: {len(steam_results[name])} months scraped")
                time.sleep(1.5)
            except Exception as e:
                log(f"  {name} FAILED: {e}")
        if steam_results:
            change = patch_steam(data, steam_results)
            summary.append(f"Steam: {change}")
            log(f"Steam patched: {change}")

    # ── Store threads ────────────────────────────────────────────────────────
    if do_store:
        log("Fetching Reddit store threads...")
        try:
            today_ym, count = fetch_store_count()
            change = patch_store(data, today_ym, count)
            summary.append(f"Store threads: {change}")
            log(f"Store threads patched: {change}")
        except Exception as e:
            log(f"Store threads FAILED: {e}")

    # ── Quarterly: Google Maps review velocity ───────────────────────────────
    if do_gmaps:
        log("Running quarterly Google Maps store review update...")
        gmaps_key = os.getenv("GOOGLE_PLACES_API_KEY")
        if not gmaps_key:
            log("  SKIP — GOOGLE_PLACES_API_KEY not set. Add it to .env to enable.")
        else:
            stores_json = Path(__file__).parent / "data" / "stores.json"
            if not stores_json.exists():
                log("  SKIP — data/stores.json not found. Run scripts/scrape_gw_stores.py first.")
            else:
                update_script = Path(__file__).parent / "scripts" / "update_store_reviews.py"
                result = subprocess.run(
                    [sys.executable, str(update_script)],
                    cwd=str(Path(__file__).parent),
                    capture_output=False,
                )
                if result.returncode == 0:
                    summary.append("Google Maps reviews: updated")
                    log("Google Maps store reviews updated successfully.")
                else:
                    log(f"Google Maps store reviews FAILED (exit {result.returncode})")

    # ── Write ────────────────────────────────────────────────────────────────
    new_html = write_yt(html, m, data)
    INDEX_HTML.write_text(new_html, encoding="utf-8")
    log(f"index.html written ({INDEX_HTML.stat().st_size // 1024}KB)")
    log(f"Summary: {' | '.join(summary) if summary else 'nothing changed'}")
    log("=" * 60)


if __name__ == "__main__":
    main()
