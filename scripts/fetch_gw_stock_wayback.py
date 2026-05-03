"""
fetch_gw_stock_wayback.py
─────────────────────────
Attempts to reconstruct historical GW stock data using the Wayback Machine.

Two strategies:
  1. CDX snapshot index  — finds all archived dates for each product URL.
     Useful to know WHEN a page was crawled (and infer activity/discontinuation).
  2. _next/data JSON     — Wayback also archives the Next.js data endpoint.
     These are pure JSON (no WAF challenge) and may contain stock fields.
     Works for snapshots taken after ~mid-2022 when GW moved to Next.js.

Output: data/gw_stock_wayback.csv
  — same schema as gw_stock_daily.csv but with source="wayback"

NOTE: Wayback coverage is sparse and inconsistent. Treat as supplementary.
      For systematic historical tracking, run fetch_gw_stock.py daily.
"""

import re, time, json
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).parent.parent
CFG     = ROOT / "config" / "gw_starter_products.csv"
OUT     = ROOT / "data" / "gw_stock_wayback.csv"
OUT.parent.mkdir(exist_ok=True)

LOCALE  = "en-US"
BASE    = "https://www.warhammer.com"
WB_CDX  = "https://web.archive.org/cdx/search/cdx"
WB_BASE = "https://web.archive.org/web"

# Only pull snapshots from 2022 onward (Next.js era)
FROM_TS = "20220101000000"
TO_TS   = "20260501000000"
DELAY   = 1.0

# ── Helpers ───────────────────────────────────────────────────────────────────

def cdx_snapshots(url: str, limit: int = 50) -> list[dict]:
    """Return list of {timestamp, status} for a URL from CDX API."""
    params = {
        "url":       url,
        "output":    "json",
        "fl":        "timestamp,statuscode,mimetype",
        "from":      FROM_TS,
        "to":        TO_TS,
        "limit":     str(limit),
        "collapse":  "timestamp:8",  # one per day max
        "filter":    "statuscode:200",
    }
    try:
        r = requests.get(WB_CDX, params=params, timeout=15)
        rows = r.json()
        if len(rows) <= 1:
            return []  # header only
        return [
            {"timestamp": row[0], "status": row[1], "mime": row[2]}
            for row in rows[1:]
        ]
    except Exception:
        return []


def fetch_wayback_json(slug: str, timestamp: str) -> dict | None:
    """
    Try to fetch the archived _next/data JSON for a slug at a given timestamp.
    Wayback archives these endpoints as plain JSON (no WAF challenge).
    """
    # We don't know the buildId at archive time, so we use a wildcard CDX search
    # to find any archived _next/data URL for this slug
    target_url = f"{BASE}/_next/data/*/{LOCALE}/shop/{slug}.json"
    params = {
        "url":    target_url,
        "output": "json",
        "fl":     "timestamp,original",
        "from":   timestamp[:8] + "000000",
        "to":     timestamp[:8] + "235959",
        "limit":  "3",
        "filter": "statuscode:200",
    }
    try:
        r = requests.get(WB_CDX, params=params, timeout=15)
        rows = r.json()
        if len(rows) <= 1:
            return None
        # Take first match
        ts, orig_url = rows[1][0], rows[1][1]
        wb_url = f"{WB_BASE}/{ts}if_/{orig_url}"
        r2 = requests.get(wb_url, timeout=20)
        if r2.status_code == 200 and len(r2.content) > 500:
            return r2.json()
    except Exception:
        pass
    return None


def _attr_value(attrs_raw: list, key: str) -> str:
    for attr in attrs_raw:
        if attr.get("name") == key:
            v = attr.get("value")
            if isinstance(v, dict):
                return v.get("en-US") or v.get("en-GB") or next(iter(v.values()), "")
            return str(v) if v is not None else ""
    return ""


def parse_stock_from_json(data: dict) -> dict:
    result = {"is_in_stock": None, "stock_status": None, "is_available": None,
              "last_chance": None, "parse_ok": False}
    try:
        page_props  = data.get("pageProps", {})
        attrs_raw   = (
            page_props
            .get("context", {})
            .get("productInformation", {})
            .get("inStore", {})
            .get("product", {})
            .get("masterData", {})
            .get("current", {})
            .get("masterVariant", {})
            .get("attributesRaw", [])
        )
        if attrs_raw:
            result["is_in_stock"]  = _attr_value(attrs_raw, "calculatedIsOnStockFlag")
            result["stock_status"] = _attr_value(attrs_raw, "calculatedStockStatus")
            result["is_available"] = _attr_value(attrs_raw, "calculatedIsAvailableFlag")
            result["last_chance"]  = _attr_value(attrs_raw, "lastChanceToBuy")
            result["parse_ok"]     = True
    except Exception:
        pass
    return result


def ts_to_date(ts: str) -> str:
    """Convert Wayback timestamp (YYYYMMDDHHmmss) to YYYY-MM-DD."""
    try:
        return datetime.strptime(ts[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return ts[:10]


# ── Load config ───────────────────────────────────────────────────────────────

products = pd.read_csv(CFG).to_dict("records")
print(f"GW Stock — Wayback Historical Pull")
print(f"Products: {len(products)}\n")

# ── Load existing wayback data to skip already-fetched (date, slug) pairs ─────

existing_keys: set[tuple] = set()
if OUT.exists():
    _ex = pd.read_csv(OUT, dtype=str)
    for _, row in _ex.iterrows():
        existing_keys.add((row.get("date", ""), row.get("slug", "")))

# ── Main loop ─────────────────────────────────────────────────────────────────

all_rows = []

for prod in products:
    slug     = prod["slug"].strip()
    name     = prod["name"].strip()
    category = prod["category"].strip()
    priority = prod["priority"].strip()
    shop_url = f"{BASE}/{LOCALE}/shop/{slug}"

    print(f"  {name[:55]:<57}", end="", flush=True)

    # 1. Get CDX snapshot dates
    snapshots = cdx_snapshots(shop_url, limit=60)
    if not snapshots:
        print("no Wayback snapshots")
        time.sleep(DELAY)
        continue

    print(f"{len(snapshots)} snapshot dates found")

    # 2. For each archived date, try to fetch the _next/data JSON
    hits = 0
    for snap in snapshots:
        ts   = snap["timestamp"]
        date_str = ts_to_date(ts)
        key  = (date_str, slug)
        if key in existing_keys:
            continue  # already have this day

        time.sleep(DELAY * 0.5)
        data = fetch_wayback_json(slug, ts)

        if data is None:
            # Record that we checked but couldn't get stock data
            all_rows.append({
                "date":        date_str,
                "slug":        slug,
                "name":        name,
                "category":    category,
                "priority":    priority,
                "in_stock":    "unknown",
                "stock_status": "",
                "is_available": "",
                "last_chance":  "",
                "http_status":  None,
                "build_id":    "",
                "source":      "wayback_no_json",
            })
        else:
            parsed = parse_stock_from_json(data)
            raw_flag   = (parsed.get("is_in_stock") or "").lower()
            raw_status = parsed.get("stock_status") or ""
            in_stock_bool = (
                "true"  if (raw_flag == "true" and raw_status in ("A", "P")) else
                "false" if parsed["parse_ok"] else
                "unknown"
            )
            all_rows.append({
                "date":        date_str,
                "slug":        slug,
                "name":        name,
                "category":    category,
                "priority":    priority,
                "in_stock":    in_stock_bool,
                "stock_status": raw_status,
                "is_available": parsed.get("is_available") or "",
                "last_chance":  (parsed.get("last_chance") or "").lower(),
                "http_status":  200,
                "build_id":    "",
                "source":      "wayback_json",
            })
            hits += 1
            existing_keys.add(key)

    if hits:
        print(f"    → {hits} stock snapshots recovered")
    time.sleep(DELAY)

# ── Save ──────────────────────────────────────────────────────────────────────

if not all_rows:
    print("\nNo new rows to save.")
else:
    new_df = pd.DataFrame(all_rows)
    if OUT.exists():
        existing = pd.read_csv(OUT, dtype=str)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "slug"], keep="last")
    else:
        combined = new_df
    combined.to_csv(OUT, index=False)
    json_hits = sum(1 for r in all_rows if r.get("source") == "wayback_json")
    print(f"\n✓ Saved {len(all_rows)} rows ({json_hits} with parseable stock data) → {OUT.relative_to(ROOT)}")
