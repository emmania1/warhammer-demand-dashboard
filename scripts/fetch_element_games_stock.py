"""
fetch_element_games_stock.py
────────────────────────────
Scrapes Element Games (elementgames.co.uk) for GW product stock status.
Element Games is the UK's largest independent GW stockist — clean HTML,
no WAF, and their site has strong coverage of the GW range.

Why: Provides a parallel UK market signal to validate the GW US store data.
UK supply tightens first (GW's home market). When something goes OOS at
Element Games it often precedes GW direct going OOS.

Strategy: Search Element Games for the same product names we track on GW,
scrape the product status, and log to data/element_games_stock_daily.csv.

Element Games stock indicators:
  "Add to Basket" button → In Stock
  "Out of Stock" / "Notify Me" text → OOS
  "Pre Order" → Pre-order

Output: data/element_games_stock_daily.csv (same schema as gw_stock_daily.csv)
"""

import re, time, requests
from pathlib import Path
from datetime import date

import pandas as pd

ROOT    = Path(__file__).parent.parent
OUT     = ROOT / "data" / "element_games_stock_daily.csv"
OUT.parent.mkdir(exist_ok=True)

today = str(date.today())

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Product search terms — keyed on the GW slug for cross-reference
PRODUCTS_TO_CHECK = {
    # Starter sets (high priority)
    "warhammer-40000-introductory-set-2023-eng":      ("Warhammer 40000 Introductory Set",        "40k Starter",      "high"),
    "warhammer-40000-starter-set-2023-eng":           ("Warhammer 40000 Starter Set",             "40k Starter",      "high"),
    "warhammer-40000-ultimate-starter-set-2023-eng":  ("Warhammer 40000 Combat Patrol Starter",   "40k Starter",      "high"),
    "age-of-sigmar-starter-set-2024-eng":             ("Age of Sigmar Starter Set",               "AoS Starter",      "high"),
    "age-of-sigmar-ultimate-starter-set-2024-eng":    ("Age of Sigmar Spearhead Starter",         "AoS Starter",      "high"),
    "kill-team-starter-set-2024-eng":                 ("Kill Team Starter Set",                   "Kill Team",        "high"),
    # New releases OOS on GW site
    "spearhead-city-of-ash-2026-eng":                 ("Spearhead City of Ash",                   "AoS New Release",  "medium"),
    "imperial-knights-knight-destrier-2026":          ("Knight Destrier",                          "40k New Release",  "medium"),
    "chaos-space-marines-defiler-2026":               ("Defiler",                                  "40k New Release",  "medium"),
    # Kill Team boxes
    "kill-team-blades-of-khaine-2024":                ("Kill Team Blades of Khaine",               "Kill Team",        "medium"),
    "kill-team-mandrakes-2024":                       ("Kill Team Mandrakes",                      "Kill Team",        "medium"),
    "kill-team-raveners-2025":                        ("Kill Team Raveners",                        "Kill Team",        "medium"),
    "kill-team-deathwatch-2025":                      ("Kill Team Deathwatch",                     "Kill Team",        "medium"),
    # Blood Bowl
    "blood-bowl-third-season-edition-2025-eng":       ("Blood Bowl Third Season",                  "Blood Bowl",       "medium"),
    # Necromunda
    "necromunda-hive-secundus-2024":                  ("Necromunda Hive Secundus",                 "Necromunda",       "medium"),
}

SEARCH_URL = "https://www.elementgames.co.uk/search?search_query={query}&section=product"


def search_element(query: str) -> list[dict]:
    """Search Element Games and return list of {name, url, status, price}."""
    url = SEARCH_URL.format(query=requests.utils.quote(query))
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return []
        content = r.text

        # Parse product cards — Element Games uses a consistent card structure
        products = []
        # Find product blocks: title + price + stock
        # Their product cards contain class="product-title" and stock info
        blocks = re.findall(
            r'<article[^>]+class="[^"]*product[^"]*"[^>]*>(.*?)</article>',
            content, re.DOTALL
        )
        if not blocks:
            # Try alternate structure
            blocks = re.findall(
                r'class="product-item[^"]*"[^>]*>(.*?)</li>',
                content, re.DOTALL
            )

        for block in blocks[:5]:
            # Product name
            name_m = re.search(r'<(?:h2|h3|span)[^>]*class="[^"]*(?:title|name)[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', block, re.DOTALL)
            if not name_m:
                name_m = re.search(r'<a[^>]*class="[^"]*(?:product|item)[^"]*"[^>]*>([^<]{5,80})</a>', block, re.DOTALL)
            name = name_m.group(1).strip() if name_m else "?"

            # Price
            price_m = re.search(r'£\s*([\d,.]+)', block)
            price_gbp = float(price_m.group(1).replace(",", "")) if price_m else 0

            # Stock
            block_lower = block.lower()
            if "out of stock" in block_lower or "notify me" in block_lower or "unavailable" in block_lower:
                status = "false"
                status_label = "Out of Stock"
            elif "add to basket" in block_lower or "add to cart" in block_lower or "in stock" in block_lower:
                status = "true"
                status_label = "In Stock"
            elif "pre order" in block_lower or "pre-order" in block_lower:
                status = "preorder"
                status_label = "Pre-Order"
            else:
                status = "unknown"
                status_label = "Unknown"

            if name and name != "?":
                products.append({
                    "name": name,
                    "price_gbp": price_gbp,
                    "in_stock": status,
                    "status_label": status_label,
                })

        return products

    except Exception as e:
        return [{"error": str(e)}]


def best_match(products: list[dict], query: str) -> dict | None:
    """Return the best matching product from search results."""
    if not products:
        return None
    query_words = set(query.lower().split())
    best = None
    best_score = 0
    for p in products:
        name_words = set((p.get("name", "") or "").lower().split())
        overlap = len(query_words & name_words)
        if overlap > best_score:
            best_score = overlap
            best = p
    return best if best_score >= 2 else products[0] if products else None


# ── Main ──────────────────────────────────────────────────────────────────────

print(f"Element Games Stock Fetcher — {today}")
print(f"Checking {len(PRODUCTS_TO_CHECK)} products...\n")
print(f"  {'Product':<45}  {'GW Status':>12}  {'EG Price':>9}")
print(f"  {'─'*45}  {'─'*12}  {'─'*9}")

rows = []
for gw_slug, (query, category, priority) in PRODUCTS_TO_CHECK.items():
    results = search_element(query)
    match   = best_match(results, query)

    if match and "error" not in match:
        in_stock     = match["in_stock"]
        price_gbp    = match["price_gbp"]
        status_label = match["status_label"]
        name_found   = match["name"][:50]
    else:
        in_stock     = "error"
        status_label = "Error"
        price_gbp    = 0
        name_found   = query[:50]

    icon = "✅" if in_stock == "true" else ("🔴" if in_stock == "false" else "⚪")
    print(f"  {icon} {query[:43]:<45}  {status_label:>12}  £{price_gbp:>7.2f}")

    rows.append({
        "date":           today,
        "gw_slug":        gw_slug,
        "search_query":   query,
        "name_found":     name_found,
        "category":       category,
        "priority":       priority,
        "in_stock":       in_stock,
        "status_label":   status_label,
        "price_gbp":      price_gbp,
        "source":         "element_games",
    })
    time.sleep(1.0)   # polite delay

# Save
new_df = pd.DataFrame(rows)
if OUT.exists():
    existing = pd.read_csv(OUT, dtype=str)
    existing = existing[existing["date"] != today]
    combined = pd.concat([existing, new_df], ignore_index=True)
else:
    combined = new_df
combined.to_csv(OUT, index=False)

in_stock_n = (new_df["in_stock"] == "true").sum()
oos_n      = (new_df["in_stock"] == "false").sum()
print(f"\n  Summary: {in_stock_n} in stock | {oos_n} OOS | {len(new_df) - in_stock_n - oos_n} unknown/error")
print(f"✓ Saved {len(rows)} rows → {OUT.relative_to(ROOT)}")
