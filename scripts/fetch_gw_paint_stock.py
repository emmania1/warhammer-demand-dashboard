"""
fetch_gw_paint_stock.py
───────────────────────
Daily SKU-level stock snapshot of EVERY paint on GW.com (US store), via the
same public Algolia search index used by fetch_gw_stock.py. One query.

Why a separate tracker: fetch_gw_stock.py only logs products that are OOS,
new releases or on its watchlist, and filters price > $15 — so most paints
(and all in-stock Tone Pro SKUs) never appear there.

Focus lines:
  Tone Pro / Tech Pro  — premium "Warhammer Pro" range, launched 2026-10-24
  Base / Layer / Shade — core range, the like-for-like comparison
  Contrast             — older range, mostly statusCode P/O (being phased out),
                         so its OOS reflects run-down, not demand

WHAT THIS MEASURES: GW web-store availability flags (in stock yes/no,
selling fast, last chance). NOT sales, NOT quantities, NOT retail/indie stock.
A daily snapshot cannot see a stock-out that starts and ends between runs.

Output:
  data/gw_paint_stock_daily.csv    — one row per (date, sku)
  data/gw_paint_stock_summary.csv  — one row per (date, line): counts + % OOS
  data/gw_paint_oos_episodes.csv   — one row per OOS run per SKU (rebuilt
                                     each day from the daily file)
"""

import time, requests
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
    "name", "slug", "sku", "price", "statusCode",
    "isInStock", "isAvailable", "isPreOrder", "isNewRelease",
    "isSellingFast", "isLastChanceToBuy", "isAvailableWhileStocksLast",
    "quantityLimits", "supplyChannel",
]

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
OUT_DAILY    = ROOT / "data" / "gw_paint_stock_daily.csv"
OUT_SUMMARY  = ROOT / "data" / "gw_paint_stock_summary.csv"
OUT_EPISODES = ROOT / "data" / "gw_paint_oos_episodes.csv"
OUT_DAILY.parent.mkdir(exist_ok=True)

today = str(date.today())

LINE_ORDER = ["Tone Pro", "Tech Pro", "Base", "Layer", "Shade", "Contrast",
              "Technical", "Air", "Dry", "Spray"]
PRO_LINES  = {"Tone Pro", "Tech Pro"}


def paint_line(name: str, price: float) -> str:
    """'Tone Pro: Blackstone Void 5' → 'Tone Pro'. Unprefixed paints on GW.com
    are spray primers (~$21–35) or Dry paints ($4.75)."""
    if ":" in name:
        return name.split(":", 1)[0].strip()
    return "Spray" if (price or 0) >= 15 else "Dry"


def fetch_all_paints(retries: int = 3) -> list[dict]:
    body = {"query": "", "filters": "productType:paint",
            "hitsPerPage": 1000, "attributesToRetrieve": ATTRS}
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=body, timeout=30)
            r.raise_for_status()
            data = r.json()
            hits = data.get("hits", [])
            if data.get("nbHits", 0) > len(hits):
                print(f"  ⚠ {data['nbHits']} paints in index but only {len(hits)} returned "
                      f"(Algolia page cap) — split the query")
            return hits
        except requests.RequestException as e:
            print(f"  attempt {attempt}/{retries} failed: {e}")
            if attempt == retries:
                raise
            time.sleep(15 * attempt)


def build_episodes(daily: pd.DataFrame) -> pd.DataFrame:
    """Collapse consecutive OOS snapshots per SKU into episodes.
    'Consecutive' = adjacent snapshot dates in the file (the tracker's own
    run dates), so a missed run day does not split an episode."""
    run_dates = sorted(daily["date"].unique())
    pos = {d: i for i, d in enumerate(run_dates)}
    last_run = run_dates[-1]
    rows = []
    for sku, g in daily.sort_values("date").groupby("sku"):
        oos = g[g["in_stock"] == "false"]
        if oos.empty:
            continue
        start = prev = None
        for d in oos["date"]:
            if start is None:
                start = prev = d
            elif pos[d] == pos[prev] + 1:
                prev = d
            else:
                rows.append((sku, start, prev))
                start = prev = d
        rows.append((sku, start, prev))

    meta = daily.sort_values("date").groupby("sku").last()
    out = []
    for sku, start, end in rows:
        m = meta.loc[sku]
        ongoing = end == last_run
        # Back in stock = first run date after the episode's last OOS run
        nxt = pos[end] + 1
        back_date = run_dates[nxt] if nxt < len(run_dates) else ""
        out.append({
            "sku":            sku,
            "name":           m["name"],
            "line":           m["line"],
            "oos_first_seen": start,
            "oos_last_seen":  end,
            "back_in_stock":  "" if ongoing else back_date,
            "snapshots_oos":  pos[end] - pos[start] + 1,
            "days_oos_min":   (pd.to_datetime(end) - pd.to_datetime(start)).days + 1,
            "ongoing":        str(ongoing).lower(),
            # True = already OOS on the tracker's first run; real start is earlier
            "started_before_tracking": str(start == run_dates[0]).lower(),
        })
    return pd.DataFrame(out, columns=[
        "sku", "name", "line", "oos_first_seen", "oos_last_seen", "back_in_stock",
        "snapshots_oos", "days_oos_min", "ongoing", "started_before_tracking"])


# ── Fetch ─────────────────────────────────────────────────────────────────────
print(f"GW Paint Stock Fetcher (Algolia) — {today}")
hits = fetch_all_paints()
print(f"  {len(hits)} paint SKUs")

rows = []
for h in hits:
    price = h.get("price", 0) or 0
    qlim  = h.get("quantityLimits")
    rows.append({
        "date":            today,
        "sku":             h.get("sku", "") or h.get("objectID", ""),
        "name":            h.get("name", ""),
        "line":            paint_line(h.get("name", ""), price),
        "slug":            h.get("slug", ""),
        "price_usd":       price,
        "status_code":     h.get("statusCode", "") or "",
        "in_stock":        str(bool(h.get("isInStock"))).lower(),
        "is_available":    str(bool(h.get("isAvailable"))).lower(),
        "is_preorder":     str(bool(h.get("isPreOrder"))).lower(),
        "is_new_release":  str(bool(h.get("isNewRelease"))).lower(),
        "is_selling_fast": str(bool(h.get("isSellingFast"))).lower(),
        "is_last_chance":  str(bool(h.get("isLastChanceToBuy"))).lower(),
        "qty_limit":       "" if qlim is None else qlim,
        "supply_channel":  h.get("supplyChannel", "") or "",
        "source":          "algolia",
    })
new_df = pd.DataFrame(rows).drop_duplicates("sku")

# ── Save daily detail (replace today's rows if re-run) ────────────────────────
if OUT_DAILY.exists():
    existing = pd.read_csv(OUT_DAILY, dtype=str, keep_default_na=False)
    existing = existing[existing["date"] != today]
    daily = pd.concat([existing, new_df.astype(str)], ignore_index=True)
else:
    daily = new_df.astype(str)
daily.to_csv(OUT_DAILY, index=False)

# ── Summary: one row per (date, line) ─────────────────────────────────────────
sum_rows = []
for line, g in new_df.groupby("line"):
    n = len(g)
    n_oos = int((g["in_stock"] == "false").sum())
    sum_rows.append({
        "date":            today,
        "line":            line,
        "skus":            n,
        "in_stock":        n - n_oos,
        "oos":             n_oos,
        "oos_pct":         round(n_oos / n * 100, 1) if n else 0,
        "selling_fast":    int((g["is_selling_fast"] == "true").sum()),
        "last_chance":     int((g["is_last_chance"] == "true").sum()),
        "preorder":        int((g["is_preorder"] == "true").sum()),
        "status_a":        int((g["status_code"] == "A").sum()),
        "status_p":        int((g["status_code"] == "P").sum()),
        "status_o":        int((g["status_code"] == "O").sum()),
    })
sum_df = pd.DataFrame(sum_rows)
sum_df["_o"] = sum_df["line"].map({l: i for i, l in enumerate(LINE_ORDER)}).fillna(99)
sum_df = sum_df.sort_values("_o").drop(columns="_o")
if OUT_SUMMARY.exists():
    ex = pd.read_csv(OUT_SUMMARY, dtype=str)
    ex = ex[ex["date"] != today]
    sum_all = pd.concat([ex, sum_df.astype(str)], ignore_index=True)
else:
    sum_all = sum_df
sum_all.to_csv(OUT_SUMMARY, index=False)

# ── OOS episodes (how often / how long) ───────────────────────────────────────
episodes = build_episodes(daily)
episodes.to_csv(OUT_EPISODES, index=False)

# ── Print ─────────────────────────────────────────────────────────────────────
print(f"\n  {'Line':<11} {'SKUs':>5} {'OOS':>5} {'OOS%':>6} {'Fast':>5} {'Last':>5} {'PreO':>5}  status A/P/O")
for _, r in sum_df.iterrows():
    print(f"  {r['line']:<11} {r['skus']:>5} {r['oos']:>5} {r['oos_pct']:>5}% "
          f"{r['selling_fast']:>5} {r['last_chance']:>5} {r['preorder']:>5}  "
          f"{r['status_a']}/{r['status_p']}/{r['status_o']}")

pro_oos = new_df[new_df["line"].isin(PRO_LINES) & (new_df["in_stock"] == "false")]
if not pro_oos.empty:
    print(f"\n  Pro SKUs out of stock today ({len(pro_oos)}):")
    for _, r in pro_oos.sort_values("name").head(25).iterrows():
        print(f"    🔴 {r['name']}")

n_open = int((episodes["ongoing"] == "true").sum()) if not episodes.empty else 0
print(f"\n✓ {len(new_df)} rows → {OUT_DAILY.relative_to(ROOT)}")
print(f"✓ Summary → {OUT_SUMMARY.relative_to(ROOT)}")
print(f"✓ {len(episodes)} OOS episodes ({n_open} ongoing) → {OUT_EPISODES.relative_to(ROOT)}")


# ── Other GW warehouses: Lenton (UK/EU — en-gb index), Ingleburn (AU/NZ — en-au) ──
# Each regional webstore reports availability from its own warehouse. Same flags as
# above; no quantities. Memphis rows are copied in from the US run for comparison.
REGIONS = [("lenton", "en-gb"), ("ingleburn", "en-au")]
OUT_REG_DAILY    = ROOT / "data" / "gw_paint_stock_regions_daily.csv"
OUT_REG_SUMMARY  = ROOT / "data" / "gw_paint_stock_regions_summary.csv"
OUT_REG_EPISODES = ROOT / "data" / "gw_paint_oos_episodes_regions.csv"
REG_COLS = ["date", "warehouse", "sku", "name", "line", "price", "status_code", "in_stock",
            "is_preorder", "is_selling_fast", "is_last_chance", "qty_limit"]

reg_rows = [{"date": today, "warehouse": "memphis", "sku": r["sku"], "name": r["name"], "line": r["line"],
             "price": r["price_usd"], "status_code": r["status_code"], "in_stock": r["in_stock"],
             "is_preorder": r["is_preorder"], "is_selling_fast": r["is_selling_fast"],
             "is_last_chance": r["is_last_chance"], "qty_limit": r["qty_limit"]} for _, r in new_df.iterrows()]
for wh, loc in REGIONS:
    ALGOLIA_URL = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/prod-lazarus-product-{loc}/query"
    try:
        hs = fetch_all_paints()
    except requests.RequestException as e:
        print(f"  ⚠ {wh} ({loc}) failed: {e}")
        continue
    for h in hs:
        price = h.get("price", 0) or 0
        qlim = h.get("quantityLimits")
        reg_rows.append({"date": today, "warehouse": wh, "sku": h.get("sku", "") or h.get("objectID", ""),
                         "name": h.get("name", ""), "line": paint_line(h.get("name", ""), price), "price": price,
                         "status_code": h.get("statusCode", "") or "",
                         "in_stock": str(bool(h.get("isInStock"))).lower(),
                         "is_preorder": str(bool(h.get("isPreOrder"))).lower(),
                         "is_selling_fast": str(bool(h.get("isSellingFast"))).lower(),
                         "is_last_chance": str(bool(h.get("isLastChanceToBuy"))).lower(),
                         "qty_limit": "" if qlim is None else qlim})
    print(f"  {wh:9} ({loc}): {len(hs)} paint SKUs")

reg = pd.DataFrame(reg_rows, columns=REG_COLS).drop_duplicates(["warehouse", "name"]).astype(str)
if OUT_REG_DAILY.exists():
    ex = pd.read_csv(OUT_REG_DAILY, dtype=str, keep_default_na=False)
    reg_all = pd.concat([ex[ex["date"] != today], reg], ignore_index=True)
else:
    reg_all = reg
reg_all.to_csv(OUT_REG_DAILY, index=False)

rs = (reg.groupby(["date", "warehouse", "line"])
      .agg(skus=("name", "size"),
           in_stock=("in_stock", lambda x: int((x == "true").sum())),
           oos=("in_stock", lambda x: int((x == "false").sum())),
           preorder=("is_preorder", lambda x: int((x == "true").sum())),
           selling_fast=("is_selling_fast", lambda x: int((x == "true").sum())),
           last_chance=("is_last_chance", lambda x: int((x == "true").sum())))
      .reset_index())
rs["oos_pct"] = (rs["oos"] / rs["skus"] * 100).round(1)
if OUT_REG_SUMMARY.exists():
    ex = pd.read_csv(OUT_REG_SUMMARY, dtype=str)
    rs = pd.concat([ex[ex["date"] != today], rs.astype(str)], ignore_index=True)
rs.to_csv(OUT_REG_SUMMARY, index=False)

eps = []
for wh, g in reg_all.groupby("warehouse"):
    e = build_episodes(g.assign(sku=g["warehouse"] + "|" + g["name"]))
    if not e.empty:
        e.insert(0, "warehouse", wh)
        e["sku"] = e["sku"].str.split("|", n=1).str[1]
        eps.append(e)
(pd.concat(eps, ignore_index=True) if eps else pd.DataFrame()).to_csv(OUT_REG_EPISODES, index=False)

cur = rs[rs["date"].astype(str) == today]
pro = cur[cur["line"].isin(PRO_LINES)].groupby("warehouse")[["skus", "oos", "preorder"]].sum()
print("\n  Pro line by warehouse (SKUs / OOS / pre-order):")
for wh, r in pro.iterrows():
    print(f"    {wh:9} {r['skus']}/{r['oos']}/{r['preorder']}")
print(f"✓ {len(reg)} rows → {OUT_REG_DAILY.relative_to(ROOT)}; summary + episodes by warehouse")
