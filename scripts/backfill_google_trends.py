"""
Google Trends 5-year historical backfill.

Pulls weekly interest data in 6-month chunks to stay under pytrends rate limits.
Appends to data/trends_data.csv, deduplicating on (date, keyword).

Run once to seed history. Safe to re-run — skips chunks already present.
"""

import time
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from pytrends.request import TrendReq

OUT = Path("data/trends_data.csv")
OUT.parent.mkdir(exist_ok=True)

KEYWORDS = [
    "Warhammer 40k",
    "Warhammer starter set",
    "buy Warhammer",
    "Warhammer Age of Sigmar",
    "Warhammer Space Marine",
]

YEARS_BACK   = 5
CHUNK_MONTHS = 6
SLEEP_SEC    = 5   # between chunks — pytrends rate-limits aggressively


def date_chunks(years_back, chunk_months):
    """Return list of (start_str, end_str) in YYYY-MM-DD format."""
    end   = datetime.now()
    start = end - timedelta(days=365 * years_back)
    chunks = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=30 * chunk_months), end)
        chunks.append((cursor.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cursor = chunk_end
    return chunks


def already_have(df_existing, start, end):
    """True if we already have data covering this whole chunk."""
    if df_existing is None or df_existing.empty:
        return False
    dates = pd.to_datetime(df_existing["date"])
    return (dates >= start).any() and (dates <= end).any()


# Load existing data so we can skip chunks we already have
df_existing = pd.read_csv(OUT) if OUT.exists() else None

pytrends = TrendReq(hl="en-US", tz=0)
chunks   = date_chunks(YEARS_BACK, CHUNK_MONTHS)
all_rows = []

print(f"Pulling {len(chunks)} time chunks ({YEARS_BACK} years, {CHUNK_MONTHS}-month slices)...")

for i, (start, end) in enumerate(chunks):
    if df_existing is not None:
        start_dt = pd.Timestamp(start)
        end_dt   = pd.Timestamp(end)
        chunk_dates = pd.to_datetime(df_existing["date"])
        # Skip if we already have at least one row in this date range for every keyword
        covered_kws = df_existing[
            (chunk_dates >= start_dt) & (chunk_dates <= end_dt)
        ]["keyword"].nunique()
        if covered_kws >= len(KEYWORDS):
            print(f"  [{i+1}/{len(chunks)}] {start} → {end}  SKIP (already have data)")
            continue

    print(f"  [{i+1}/{len(chunks)}] {start} → {end}  fetching...")
    try:
        pytrends.build_payload(KEYWORDS, timeframe=f"{start} {end}", geo="")
        data = pytrends.interest_over_time()
        if not data.empty:
            for dt, row in data.iterrows():
                for kw in KEYWORDS:
                    all_rows.append({
                        "date":    str(dt.date()),
                        "keyword": kw,
                        "score":   int(row[kw]),
                    })
            print(f"    → {len(data)} weeks of data")
        else:
            print(f"    → no data returned")
        time.sleep(SLEEP_SEC)
    except Exception as e:
        print(f"    ERROR: {e}  (sleeping 15s before continuing)")
        time.sleep(15)

if not all_rows:
    print("No new rows fetched.")
else:
    df_new = pd.DataFrame(all_rows)

    if df_existing is not None:
        df = pd.concat([df_existing, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["date", "keyword"], keep="last")
    else:
        df = df_new

    df = df.sort_values(["keyword", "date"])
    df.to_csv(OUT, index=False)

    print(f"\nSaved → {OUT}")
    print(f"  New rows  : {len(df_new)}")
    print(f"  Total rows: {len(df)}")
    print(f"  Date range: {df['date'].min()}  →  {df['date'].max()}")
