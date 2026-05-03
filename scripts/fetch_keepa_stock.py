"""
fetch_keepa_stock.py
────────────────────
Fetches historical GW product stock/OOS data via the Keepa API.
Keepa tracks every Amazon price change including availability windows.
OOS on Amazon is encoded as value = -1 in the price history arrays.

Why Keepa is the best available historical source:
  - GW.com: AWS WAF blocks Wayback Machine from capturing stock status
  - Wayback + UK retailers: 1-2 captures/product since 2023 (too sparse)
  - Keepa: near-hourly snapshots on Amazon going back to product launch
  - GW ASINs confirmed on Amazon UK + US (launched August 2023 for 10th Ed)

Cost: €49/month (20 tokens/min tier — sufficient for this use case)
      https://keepa.com/#!api/pricing

Setup:
  1. Subscribe at keepa.com
  2. Get API key from keepa.com/#!api
  3. Add to .env: KEEPA_API_KEY=your_key_here
  4. Run: python3 scripts/fetch_keepa_stock.py

Output: data/keepa_stock_history.csv
  Columns: date, asin, name, edition, category, market, is_oos, price, source

GW ASINs confirmed:
  ┌──────────────┬────────────────────────────────┬──────────┐
  │ ASIN         │ Product                        │ Edition  │
  ├──────────────┼────────────────────────────────┼──────────┤
  │ B0CBKH9V27   │ 40k Introductory Set           │ 10th Ed  │
  │ B0CBKLS5XD   │ 40k Starter Set                │ 10th Ed  │
  │ B0CBKJVLFB   │ 40k Combat Patrol Starter Set  │ 10th Ed  │
  │ B08CFDSXNZ   │ 40k Command Edition            │ 9th Ed   │
  │ B09CG7L7KC   │ 40k Recruit Edition            │ 9th Ed   │
  │ B09CG7LC6V   │ 40k Elite Edition              │ 9th Ed   │
  └──────────────┴────────────────────────────────┴──────────┘

10th Edition launched August 2023 → history from Aug 2023 to present.
9th Edition released 2020 → history from ~2020 to 2023 (when discontinued).
Together these cover the full 2020–present starter set availability history.
"""

import os, time
import requests
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

ROOT = Path(__file__).parent.parent
OUT  = ROOT / "data" / "keepa_stock_history.csv"
OUT.parent.mkdir(exist_ok=True)

# ── API key ───────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

KEEPA_API_KEY = os.getenv("KEEPA_API_KEY", "")
if not KEEPA_API_KEY:
    raise SystemExit(
        "\n  KEEPA_API_KEY not set.\n"
        "  1. Subscribe at https://keepa.com/#!api/pricing  (€49/month)\n"
        "  2. Get your key at https://keepa.com/#!api\n"
        "  3. Add to .env: KEEPA_API_KEY=your_key_here\n"
    )

# ── Products to track ─────────────────────────────────────────────────────────
ASINS = {
    # 10th Edition starters (Aug 2023 – present)
    "B0CBKH9V27": ("40k Introductory Set",          "10th Ed", "40k Starter"),
    "B0CBKLS5XD": ("40k Starter Set",               "10th Ed", "40k Starter"),
    "B0CBKJVLFB": ("40k Combat Patrol Starter Set", "10th Ed", "40k Starter"),
    # 9th Edition starters (2020–2023) — historical OOS baseline
    "B08CFDSXNZ": ("40k Command Edition",           "9th Ed",  "40k Starter"),
    "B09CG7L7KC": ("40k Recruit Edition",           "9th Ed",  "40k Starter"),
    "B09CG7LC6V": ("40k Elite Edition",             "9th Ed",  "40k Starter"),
}

# Keepa domain codes: 1=US, 3=UK, 4=DE, 5=FR, 6=JP, 8=IT, 9=ES
MARKETPLACES = {1: "US", 3: "UK"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def keepa_ts_to_date(keepa_ts: int) -> str:
    """
    Keepa timestamps = minutes since 2011-01-01 00:00:00 UTC.
    Returns YYYY-MM-DD string.
    """
    KEEPA_EPOCH = 1293840000  # 2011-01-01 00:00:00 UTC in Unix seconds
    ts_unix = KEEPA_EPOCH + keepa_ts * 60
    return datetime.fromtimestamp(ts_unix, tz=timezone.utc).strftime("%Y-%m-%d")


def parse_price_csv(csv_arr: list) -> list[dict]:
    """
    Parse a Keepa price CSV array (alternating [timestamp, value] pairs).
    value == -1  → out of stock
    value >  0   → price in cents (divide by 100 for USD/GBP)
    value ==  0  → ambiguous, skip
    Returns list of {date, is_oos, price} dicts.
    """
    records = []
    if not csv_arr or len(csv_arr) < 2:
        return records
    for i in range(0, len(csv_arr) - 1, 2):
        ts    = csv_arr[i]
        value = csv_arr[i + 1]
        if ts < 0 or value == 0:
            continue
        records.append({
            "date":   keepa_ts_to_date(ts),
            "is_oos": (value == -1),
            "price":  round(value / 100.0, 2) if value > 0 else 0.0,
        })
    return records


def keepa_fetch_product(asin: str, domain: int) -> dict:
    """Call Keepa product API and return raw product dict (or {})."""
    r = requests.get(
        "https://api.keepa.com/product",
        params={"key": KEEPA_API_KEY, "domain": domain, "asin": asin, "stats": 0},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    products = data.get("products")
    if not products:
        return {}
    return products[0]


# ── Main ──────────────────────────────────────────────────────────────────────

print("GW Starter Set Historical Stock — Keepa API")
print(f"Tracking {len(ASINS)} ASINs × {len(MARKETPLACES)} marketplaces\n")

all_rows = []

for asin, (name, edition, category) in ASINS.items():
    for domain, market in MARKETPLACES.items():
        print(f"  {name:40} [{market}]  ", end="", flush=True)
        try:
            prod = keepa_fetch_product(asin, domain)
            if not prod:
                print("not found in Keepa")
                continue

            csv_arrays = prod.get("csv") or []

            # CSV index reference (Keepa docs):
            #   [0]  = AMAZON price (official Amazon listing)
            #   [1]  = Marketplace NEW (3rd party new)
            #   [18] = Buy Box price (what customer actually sees/pays)
            # OOS signal: any of these going to -1
            # Buy Box is most reliable — it's what the customer sees
            primary = (
                csv_arrays[18] if len(csv_arrays) > 18 and csv_arrays[18]
                else csv_arrays[0] if csv_arrays and csv_arrays[0]
                else []
            )

            records = parse_price_csv(primary)
            if not records:
                print("no price history")
                continue

            oos_events = sum(1 for r in records if r["is_oos"])
            print(f"{len(records):4} snapshots, {oos_events} OOS events"
                  f"  ({records[0]['date']} → {records[-1]['date']})")

            for rec in records:
                all_rows.append({
                    "date":     rec["date"],
                    "asin":     asin,
                    "name":     name,
                    "edition":  edition,
                    "category": category,
                    "market":   market,
                    "is_oos":   rec["is_oos"],
                    "price":    rec["price"],
                    "source":   "keepa",
                })

        except requests.HTTPError as e:
            print(f"HTTP error: {e}")
        except Exception as e:
            print(f"error: {e}")

        time.sleep(2.5)   # respect Keepa rate limits (20 tokens/min)

# ── Save ──────────────────────────────────────────────────────────────────────
if not all_rows:
    print("\nNo data retrieved — check API key and ASIN availability.")
else:
    df = pd.DataFrame(all_rows)
    df = df.sort_values(["asin", "market", "date"]).reset_index(drop=True)
    df.to_csv(OUT, index=False)

    oos_total  = int(df["is_oos"].sum())
    date_range = f"{df['date'].min()} → {df['date'].max()}"
    print(f"\n── Summary ────────────────────────────────────────────────────────")
    print(f"  {len(df):,} total snapshots | {oos_total:,} OOS events | {date_range}")
    print()

    for name in df["name"].unique():
        for market in MARKETPLACES.values():
            sub = df[(df["name"] == name) & (df["market"] == market)]
            if sub.empty:
                continue
            n_oos = int(sub["is_oos"].sum())
            pct   = round(100 * n_oos / len(sub), 1) if len(sub) else 0
            print(f"  {name:40} [{market}]  {n_oos:3} OOS / {len(sub):4} snapshots  ({pct}% time OOS)")

    print(f"\n✓ Saved → {OUT.relative_to(ROOT)}")
    print(f"\n  Interpret: % time OOS = fraction of Amazon history the product was unavailable.")
    print(f"  Rising OOS % over consecutive editions = structural demand exceeding production.")
