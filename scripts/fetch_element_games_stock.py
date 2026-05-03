"""
fetch_element_games_stock.py
────────────────────────────
Scrapes Element Games (elementgames.co.uk) for GW product stock status.
Element Games is the UK's largest independent GW stockist.

Why this works (and the old version didn't):
  Old approach used the search page — BigCommerce search results are
  JavaScript-loaded, so plain HTTP requests return empty result cards.
  This version uses DIRECT product page URLs, which are fully server-rendered
  HTML with no JavaScript required and no WAF.

Stock indicators in the HTML:
  green-button.png  + "X+ In Stock"  → In Stock
  red-button.png    + "Unavailable"  → Out of Stock
  blue-button.png   + "Backorder"    → Backorder (can order, stock incoming)
  "Stock Due"                        → Coming back soon
  "Pre-Order"                        → Pre-order

Price: class="currentPrice"  → EG's discounted price (~15% off GW RRP)
       class="old-price"     → GW RRP (useful for cross-referencing)

Output: data/element_games_stock_daily.csv

Historical note:
  Wayback Machine has ~1-2 captures per product since 2023 — not dense enough
  for OOS reconstruction. For historical data, use Keepa (Amazon channel).
  This script builds the UK indie retailer signal going forward from today.
"""

import re, time, requests
from pathlib import Path
from datetime import date

import pandas as pd

ROOT = Path(__file__).parent.parent
OUT  = ROOT / "data" / "element_games_stock_daily.csv"
OUT.parent.mkdir(exist_ok=True)

today = str(date.today())

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

EG = "https://elementgames.co.uk"

# ── Product list ─────────────────────────────────────────────────────────────
# Keys match gw_stock_daily.csv slugs for cross-reference.
# URLs confirmed as plain-HTML product pages (no JS, no WAF).
# New release URLs are best-guess slugs — 404 handled gracefully.

PRODUCTS = {
    # ── Core Starter Sets (URLs verified) ──────────────────────────────────
    "warhammer-40000-introductory-set-2023-eng": {
        "url":      f"{EG}/games-workshop/warhammer-40k/warhammer-40000-introductory-set-english-",
        "name":     "40k Introductory Set",
        "category": "40k Starter",
        "priority": "high",
    },
    "warhammer-40000-starter-set-2023-eng": {
        "url":      f"{EG}/warhammer-40000-starter-set-english-",
        "name":     "40k Starter Set",
        "category": "40k Starter",
        "priority": "high",
    },
    "warhammer-40000-ultimate-starter-set-2023-eng": {
        "url":      f"{EG}/new-releases/warhammer-40000-ultimate-starter-set-english-",
        "name":     "40k Combat Patrol Starter",
        "category": "40k Starter",
        "priority": "high",
    },
    "age-of-sigmar-starter-set-2024-eng": {
        "url":      f"{EG}/age-of-sigmar-introductory-set",
        "name":     "AoS Starter Set",
        "category": "AoS Starter",
        "priority": "high",
    },
    "age-of-sigmar-ultimate-starter-set-2024-eng": {
        "url":      f"{EG}/games-workshop/age-of-sigmar-ultimate-starter-set-",
        "name":     "AoS Spearhead Starter",
        "category": "AoS Starter",
        "priority": "high",
    },
    "kill-team-starter-set-2024-eng": {
        "url":      f"{EG}/games-workshop/warhammer-40k/warhammer-40000-kill-team/kill-team-starter-set-english-",
        "name":     "Kill Team Starter Set",
        "category": "Kill Team",
        "priority": "high",
    },

    # ── New Releases currently OOS on GW.com (URLs verified via Google) ────
    "spearhead-city-of-ash-2026-eng": {
        "url":      f"{EG}/games-workshop/new-warhammer-age-of-sigmar/spearhead-city-of-ash-english-",
        "name":     "Spearhead: City of Ash",
        "category": "AoS New Release",
        "priority": "medium",
    },
    "imperial-knights-knight-destrier-2026": {
        "url":      f"{EG}/games-workshop/warhammer-40k/the-maelstrom/imperial-knights-knight-destrier",
        "name":     "Knight Destrier",
        "category": "40k New Release",
        "priority": "medium",
    },
    "chaos-space-marines-defiler-2026": {
        "url":      f"{EG}/games-workshop/chaos-space-marines-defiler",
        "name":     "Defiler",
        "category": "40k New Release",
        "priority": "medium",
    },
    "venatari-sodality-2026": {
        "url":      f"{EG}/games-workshop/horus-heresy-miniatures/horus-heresy-legio-custodes/legio-custodes-venatari-sodality",
        "name":     "Venatari Sodality",
        "category": "40k New Release",
        "priority": "medium",
    },
    # Custodian Dreadnought — not indexed on EG as of 2026-05-02; monitor for listing
}


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_eg_page(url: str) -> dict:
    """
    Fetch an Element Games product page and return stock status + price.
    Pages are fully server-rendered — no JavaScript needed.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)

        if r.status_code == 404:
            return {"status": "not_found", "label": "Not Found on EG",
                    "price_gbp": 0.0, "price_rrp": 0.0, "name_found": ""}
        if r.status_code != 200:
            return {"status": "error",     "label": f"HTTP {r.status_code}",
                    "price_gbp": 0.0, "price_rrp": 0.0, "name_found": ""}

        html = r.text
        hl   = html.lower()

        # ── Stock status ───────────────────────────────────────────────────
        # Element Games HTML uses inline text after green/red/blue button images.
        # "10+ In Stock", "2 In Stock", "Out of Stock", "Backorder", etc.
        stock_m = re.search(r'(\d+)\+?\s*in\s*stock', hl)
        if stock_m:
            count  = int(stock_m.group(1))
            status = "in_stock"
            label  = f"{count}+ In Stock" if "+" in stock_m.group(0) else f"{count} In Stock"
        elif "out of stock" in hl or "unavailable" in hl:
            status = "oos"
            label  = "Out of Stock"
        elif "pre-order" in hl or "pre order" in hl:
            status = "preorder"
            label  = "Pre-Order"
        elif "backorder" in hl:
            status = "backorder"
            label  = "Backorder/Available"
        elif "stock due" in hl or "due soon" in hl:
            status = "low_stock"
            label  = "Stock Due"
        else:
            status = "unknown"
            label  = "Unknown"

        # ── Prices ────────────────────────────────────────────────────────
        # EG shows two prices: old-price (RRP) and currentPrice (EG discounted)
        # Prices encoded as &pound; in raw HTML
        def extract_price(pattern: str) -> float:
            m = re.search(pattern, html)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    pass
            return 0.0

        price_gbp = extract_price(r'class="currentPrice"[^>]*>&pound;([\d,]+\.?\d*)')
        price_rrp = extract_price(r'class="old-price"[^>]*>&pound;([\d,]+\.?\d*)')

        # Fallback if currentPrice class not found
        if price_gbp == 0.0:
            price_gbp = extract_price(r'&pound;(\d{2,3}(?:\.\d{2})?)')

        # ── Product name from page title ───────────────────────────────────
        title_m    = re.search(r'<title>([^<|]+)', html)
        name_found = title_m.group(1).strip()[:80] if title_m else url.split("/")[-1]

        return {
            "status":     status,
            "label":      label,
            "price_gbp":  price_gbp,
            "price_rrp":  price_rrp,
            "name_found": name_found,
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "label": "Timeout",
                "price_gbp": 0.0, "price_rrp": 0.0, "name_found": ""}
    except Exception as e:
        return {"status": "error", "label": str(e)[:80],
                "price_gbp": 0.0, "price_rrp": 0.0, "name_found": ""}


# ── Main ──────────────────────────────────────────────────────────────────────

print(f"Element Games Stock Fetcher — {today}")
print(f"Checking {len(PRODUCTS)} products (direct product page URLs)\n")
print(f"  {'Product':<38}  {'Status':>16}  {'EG Price':>8}  {'RRP':>7}")
print(f"  {'─'*38}  {'─'*16}  {'─'*8}  {'─'*7}")

rows = []
for gw_slug, prod in PRODUCTS.items():
    url      = prod["url"]
    name     = prod["name"]
    category = prod["category"]
    priority = prod["priority"]

    result = parse_eg_page(url)

    status    = result["status"]
    label     = result["label"]
    price_gbp = result["price_gbp"]
    price_rrp = result["price_rrp"]
    name_found = result.get("name_found", name)

    icon = ("✅" if status == "in_stock"
            else "🔴" if status == "oos"
            else "⚪" if status in ("preorder", "backorder", "low_stock")
            else "❌")  # error / not_found

    rrp_str = f"£{price_rrp:.2f}" if price_rrp else "  —   "
    print(f"  {icon} {name[:36]:<38}  {label[:16]:>16}  £{price_gbp:>6.2f}  {rrp_str:>7}")

    rows.append({
        "date":       today,
        "gw_slug":    gw_slug,
        "name":       name,
        "name_found": name_found[:80],
        "eg_url":     url,
        "category":   category,
        "priority":   priority,
        "status":     status,
        "label":      label,
        "price_gbp":  price_gbp,   # EG discounted price
        "price_rrp":  price_rrp,   # GW RRP (as shown on EG)
        "source":     "element_games_direct",
    })
    time.sleep(1.5)   # polite crawl delay

# ── Save ──────────────────────────────────────────────────────────────────────
new_df = pd.DataFrame(rows)
if OUT.exists():
    existing = pd.read_csv(OUT, dtype=str)
    existing = existing[existing["date"] != today]
    combined = pd.concat([existing, new_df], ignore_index=True)
else:
    combined = new_df
combined.to_csv(OUT, index=False)

in_stock_n = (new_df["status"] == "in_stock").sum()
oos_n      = (new_df["status"] == "oos").sum()
other_n    = len(new_df) - in_stock_n - oos_n
print(f"\n  Summary: {in_stock_n} in stock | {oos_n} OOS | {other_n} other (backorder/not found/error)")
print(f"✓ Saved {len(rows)} rows → {OUT.relative_to(ROOT)}")
