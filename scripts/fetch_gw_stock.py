"""
fetch_gw_stock.py
─────────────────
Pulls targeted GW product data from their Algolia search index and logs daily
stock snapshots. No Playwright, no WAF, no per-product scraping loops.

Algolia credentials are public/search-only (embedded in GW's frontend JS).

Strategy: instead of fetching all 3,700+ products (the search-only key is
capped at 1,000 per query), we run focused queries for what matters:
  1. ALL out-of-stock products sitewide  — the core signal
  2. All new releases                   — time-sensitive sell-out signal
  3. Selling fast / last chance items   — directional indicators
  4. Specific starter set slugs         — investment priority watchlist
  5. Kill Team + specialty game boxes   — hobby breadth signal

Output files:
  data/gw_stock_daily.csv    — one row per (date, slug): OOS products + starters + new releases
  data/gw_stock_summary.csv  — one row per date: aggregate counts by game system
"""

import json, time, requests
from pathlib import Path
from datetime import date

import pandas as pd

# ── Algolia (public search-only key from GW's own frontend JS) ────────────────
ALGOLIA_APP_ID  = "M5ZIQZNQ2H"
ALGOLIA_API_KEY = "92c6a8254f9d34362df8e6d96475e5d8"
ALGOLIA_INDEX   = "prod-lazarus-product-en-us"
ALGOLIA_URL     = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
ALGOLIA_HEADERS = {
    "x-algolia-application-id": ALGOLIA_APP_ID,
    "x-algolia-api-key":        ALGOLIA_API_KEY,
    "Content-Type":             "application/json",
}
ATTRS = [
    "name", "slug", "price", "sku",
    "isInStock", "isAvailable", "statusCode",
    "isLastChanceToBuy", "isSellingFast", "isMadeToOrder",
    "isNewRelease", "isPreOrder", "isAvailableWhileStocksLast",
    "isWebstoreExclusive", "productType", "GameSystemsRoot",
]

# ── High-priority watchlist (always check these regardless of OOS status) ─────
STARTER_WATCHLIST = {
    "warhammer-40000-introductory-set-2023-eng": ("40k Introductory Set",        "40k Starter",      "high"),
    "warhammer-40000-starter-set-2023-eng":      ("40k Starter Set",             "40k Starter",      "high"),
    "warhammer-40000-ultimate-starter-set-2023-eng": ("40k Combat Patrol Starter Set","40k Starter",  "high"),
    "age-of-sigmar-starter-set-2024-eng":        ("AoS Starter Set",             "AoS Starter",      "high"),
    "age-of-sigmar-ultimate-starter-set-2024-eng":("AoS Spearhead Starter Set",  "AoS Starter",      "high"),
    "kill-team-starter-set-2024-eng":            ("Kill Team Starter Set",        "Kill Team Starter","high"),
    "warcry-crypt-of-blood-2023-eng":            ("Warcry: Crypt of Blood",       "Warcry Starter",   "medium"),
    "warhammer-40000-paints-tools-set-2023":     ("40k Paints + Tools Set",       "40k Starter",      "medium"),
    "getting-started-with-warhammer-40k-2023-eng":("Getting Started with 40k",   "40k Starter",      "medium"),
}

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
OUT_DAILY   = ROOT / "data" / "gw_stock_daily.csv"
OUT_SUMMARY = ROOT / "data" / "gw_stock_summary.csv"
OUT_DAILY.parent.mkdir(exist_ok=True)

today = str(date.today())

# ── Algolia query helper ──────────────────────────────────────────────────────

def algolia_query(query_str: str = "", filters: str = "", n: int = 1000) -> list[dict]:
    body = {
        "query":                query_str,
        "filters":              filters,
        "hitsPerPage":          n,
        "attributesToRetrieve": ATTRS,
    }
    r = requests.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=body, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data.get("hits", []), data.get("nbHits", 0)


def get_system(h: dict) -> str:
    """Return the primary game system label for an Algolia hit."""
    gs = h.get("GameSystemsRoot", "")
    if isinstance(gs, dict):
        return str(gs.get("lvl0", "Other"))
    if isinstance(gs, str):
        return gs or "Other"
    if isinstance(gs, list):
        # Algolia stores this as a flat list of strings like
        # ["Warhammer 40,000"] or ["Age of Sigmar", "Other Games"]
        for g in gs:
            if isinstance(g, str) and g:
                return g         # first non-empty string wins
            if isinstance(g, dict) and "lvl0" in g:
                return str(g["lvl0"])
        return "Other"
    return "Other"


def hit_to_row(h: dict, category: str = "", priority: str = "") -> dict:
    system = get_system(h)
    # Normalise game system name
    SYSTEM_MAP = {
        "Warhammer 40,000":  "40k",
        "Age of Sigmar":     "AoS",
        "The Horus Heresy":  "Horus Heresy",
        "The Old World":     "The Old World",
        "Other Games":       "Specialty Games",
        "Middle-Earth":      "Middle-Earth",
    }
    system_short = SYSTEM_MAP.get(system, system)
    return {
        "date":            today,
        "slug":            h.get("slug", ""),
        "name":            h.get("name", ""),
        "game_system":     system_short,
        "category":        category or system_short,
        "priority":        priority,
        "price_usd":       h.get("price", 0) or 0,
        "in_stock":        str(h.get("isInStock",   False)).lower(),
        "is_available":    str(h.get("isAvailable", False)).lower(),
        "status_code":     h.get("statusCode", ""),
        "is_last_chance":  str(h.get("isLastChanceToBuy", False)).lower(),
        "is_selling_fast": str(h.get("isSellingFast",     False)).lower(),
        "is_new_release":  str(h.get("isNewRelease",      False)).lower(),
        "is_preorder":     str(h.get("isPreOrder",        False)).lower(),
        "is_mto":          str(h.get("isMadeToOrder",     False)).lower(),
        "product_type":    h.get("productType", ""),
        "source":          "algolia",
    }


# ── Fetch all signal categories ───────────────────────────────────────────────

print(f"GW Stock Fetcher (Algolia) — {today}")
all_rows: dict[str, dict] = {}   # slug → row (dedupe within this run)

# 1 ── All out-of-stock products (any price, any system)
print("  [1/4] Out-of-stock products sitewide...")
oos_hits, oos_total = algolia_query(filters="isInStock:false AND price > 15")
print(f"        {oos_total} OOS products found (fetched {len(oos_hits)})")
for h in oos_hits:
    row = hit_to_row(h, category="OOS Product")
    all_rows[row["slug"]] = row

time.sleep(0.3)

# 2 ── New releases (whether in stock or not — we want to track sell-out speed)
print("  [2/4] New releases...")
nr_hits, nr_total = algolia_query(filters="isNewRelease:true AND price > 15")
print(f"        {nr_total} new releases")
nr_oos = 0
for h in nr_hits:
    slug = h.get("slug", "")
    row = hit_to_row(h, category="New Release")
    if not h.get("isInStock"): nr_oos += 1
    # Don't overwrite OOS rows; new release info is additive
    if slug not in all_rows:
        all_rows[slug] = row
    else:
        all_rows[slug]["is_new_release"] = "true"
        all_rows[slug]["category"] = "New Release (OOS)"
print(f"        {nr_oos} new releases already OOS")

time.sleep(0.3)

# 3 ── Selling fast flag
print("  [3/4] Selling fast + last chance...")
sf_hits, sf_total = algolia_query(filters="isSellingFast:true")
for h in sf_hits:
    slug = h.get("slug", "")
    if slug in all_rows:
        all_rows[slug]["is_selling_fast"] = "true"
lc_hits, lc_total = algolia_query(filters="isLastChanceToBuy:true")
for h in lc_hits:
    slug = h.get("slug", "")
    if slug in all_rows:
        all_rows[slug]["is_last_chance"] = "true"
print(f"        {sf_total} selling fast | {lc_total} last chance")

time.sleep(0.3)

# 4 ── Starter watchlist (always fetch, in stock or not)
print("  [4/4] Starter set watchlist...")
for slug, (name, category, priority) in STARTER_WATCHLIST.items():
    hits, _ = algolia_query(query_str=name, n=5)
    matched = next((h for h in hits if h.get("slug") == slug), None)
    if matched is None:
        # Search by slug fragment
        hits2, _ = algolia_query(query_str=slug.replace("-", " "), n=5)
        matched = next((h for h in hits2 if h.get("slug") == slug), None)
    if matched:
        row = hit_to_row(matched, category=category, priority=priority)
        all_rows[slug] = row  # always overwrite to ensure latest status
        status = "✅" if matched.get("isInStock") else "🔴"
        trans  = " [TRANSITIONAL]" if matched.get("statusCode") == "P" else ""
        print(f"        {status} ${matched.get('price',0):<6.0f} {name}{trans}")
    else:
        # Not found in Algolia — product retired or slug changed
        all_rows[slug] = {
            "date": today, "slug": slug, "name": name,
            "game_system": category.split()[0], "category": category,
            "priority": priority, "price_usd": 0,
            "in_stock": "unknown", "is_available": "unknown",
            "status_code": "NOT_FOUND", "is_last_chance": "false",
            "is_selling_fast": "false", "is_new_release": "false",
            "is_preorder": "false", "is_mto": "false",
            "product_type": "", "source": "algolia",
        }
        print(f"        ⚪ NOT FOUND  {name}")
    time.sleep(0.2)

# ── Save daily detail ─────────────────────────────────────────────────────────
rows_list = list(all_rows.values())
new_df = pd.DataFrame(rows_list)

if OUT_DAILY.exists():
    existing = pd.read_csv(OUT_DAILY, dtype=str)
    # Drop today's rows then re-add fresh
    existing = existing[existing["date"] != today]
    combined = pd.concat([existing, new_df], ignore_index=True)
else:
    combined = new_df

combined.to_csv(OUT_DAILY, index=False)

# ── Summary row ───────────────────────────────────────────────────────────────
SYSTEMS = ["40k", "AoS", "Horus Heresy", "The Old World", "Specialty Games", "Middle-Earth"]

summary = {
    "date":                 today,
    "total_oos":            int((new_df["in_stock"] == "false").sum()),
    "new_releases_total":   int((new_df["is_new_release"] == "true").sum()),
    "new_releases_oos":     int(((new_df["is_new_release"] == "true") & (new_df["in_stock"] == "false")).sum()),
    "last_chance_total":    int((new_df["is_last_chance"] == "true").sum()),
    "selling_fast_total":   int((new_df["is_selling_fast"] == "true").sum()),
    "starter_40k_in_stock": int(((new_df["category"].str.contains("40k Starter", na=False)) & (new_df["in_stock"] == "true")).sum()),
    "starter_40k_oos":      int(((new_df["category"].str.contains("40k Starter", na=False)) & (new_df["in_stock"] == "false")).sum()),
    "starter_aos_in_stock": int(((new_df["category"].str.contains("AoS Starter", na=False)) & (new_df["in_stock"] == "true")).sum()),
    "starter_aos_oos":      int(((new_df["category"].str.contains("AoS Starter", na=False)) & (new_df["in_stock"] == "false")).sum()),
}
for gs in SYSTEMS:
    sub = new_df[new_df["game_system"] == gs]
    summary[f"oos_{gs.lower().replace(' ','_').replace('-','_')}"] = int((sub["in_stock"] == "false").sum())

sum_df = pd.DataFrame([summary])
if OUT_SUMMARY.exists():
    existing_sum = pd.read_csv(OUT_SUMMARY, dtype=str)
    existing_sum = existing_sum[existing_sum["date"] != today]
    combined_sum = pd.concat([existing_sum, sum_df], ignore_index=True)
else:
    combined_sum = sum_df
combined_sum.to_csv(OUT_SUMMARY, index=False)

# ── Print summary ─────────────────────────────────────────────────────────────
print(f"\n── Snapshot Summary ({today}) ────────────────────────────────────────")
print(f"  Total OOS products logged:   {summary['total_oos']}")
print(f"  New releases:               {summary['new_releases_total']} total, {summary['new_releases_oos']} already OOS")
print(f"  Last chance to buy:         {summary['last_chance_total']}")
print(f"  Selling fast:               {summary['selling_fast_total']}")

print(f"\n── OOS by Game System ────────────────────────────────────────────────")
for gs in SYSTEMS:
    col = f"oos_{gs.lower().replace(' ','_').replace('-','_')}"
    n   = summary.get(col, 0)
    bar = "█" * min(int(n / 3), 30)
    print(f"  {gs:<20} {n:>4} OOS  {bar}")

print(f"\n── Starter Set Status (Investment Priority) ──────────────────────────")
starters = new_df[new_df["priority"].isin(["high","medium"])].sort_values(["priority","name"])
for _, r in starters.iterrows():
    icon = "✅" if r["in_stock"] == "true" else ("🔴" if r["in_stock"] == "false" else "⚪")
    trans = " [TRANSITIONAL]" if r.get("status_code","") == "P" else ""
    print(f"  {icon} ${float(r['price_usd'] or 0):<6.0f}  {r['name']}{trans}")

print(f"\n── New Releases Already OOS ──────────────────────────────────────────")
nr_oos_df = new_df[(new_df["is_new_release"] == "true") & (new_df["in_stock"] == "false")].sort_values("price_usd", ascending=False)
if nr_oos_df.empty:
    print("  (none)")
else:
    for _, r in nr_oos_df.head(15).iterrows():
        print(f"  ${float(r['price_usd']):<6.0f}  {r['name'][:60]}  [{r['game_system']}]")

print(f"\n✓ {len(rows_list)} rows → {OUT_DAILY.relative_to(ROOT)}")
print(f"✓ Summary → {OUT_SUMMARY.relative_to(ROOT)}")
