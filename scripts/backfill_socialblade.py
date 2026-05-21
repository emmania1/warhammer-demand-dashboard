"""
Social Blade historical backfill for YouTube channels.

Scrapes monthly subscriber and view counts from Social Blade's public pages,
giving years of channel history as a baseline before we started tracking.

Saves to data/youtube_channels_monthly_history.csv
Deduplicates on (channel_id, month).
"""

import time
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
import re

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

import csv

CHANNELS_CFG = Path("config/youtube_channels.csv")
OUT          = Path("data/youtube_channels_monthly_history.csv")
OUT.parent.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

channels = []
with open(CHANNELS_CFG, newline="") as f:
    for row in csv.DictReader(f):
        channels.append({
            "label":      row["label"].strip(),
            "channel_id": row["channel_id"].strip(),
        })

print(f"Channels to backfill: {len(channels)}")

def parse_sb_number(text):
    """Parse Social Blade numbers like '1.2M', '500K', '1,234,567'."""
    if not text:
        return None
    text = text.strip().replace(",", "").replace("+", "").replace("--", "")
    if not text or text in ("", "N/A", "--"):
        return None
    try:
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        return int(float(text))
    except (ValueError, TypeError):
        return None


def scrape_channel_monthly(channel_id, label):
    """Return list of {month, subscribers, views} dicts."""
    url = f"https://socialblade.com/youtube/channel/{channel_id}/monthly"
    rows = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 429:
            print(f"  Rate limited — sleeping 30s")
            time.sleep(30)
            r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} for {label}")
            return rows

        soup = BeautifulSoup(r.text, "lxml")

        # Social Blade monthly table: look for rows with month data
        # The monthly table has columns: Month, Subscribers, Video Views, ...
        table = soup.find("table", id=re.compile(r"monthly", re.I))
        if not table:
            # Try finding any table that looks like monthly stats
            tables = soup.find_all("table")
            for t in tables:
                header = t.find("tr")
                if header and any("month" in th.get_text().lower() for th in header.find_all(["th","td"])):
                    table = t
                    break

        if not table:
            # Try the div-based layout Social Blade sometimes uses
            monthly_divs = soup.find_all("div", style=re.compile(r"display.*flex", re.I))
            # Look for rows with date patterns like "2024-01" or "January 2024"
            date_pattern = re.compile(r"(20\d\d)-(0[1-9]|1[0-2])")
            for div in soup.find_all(string=date_pattern):
                parent = div.parent
                if parent:
                    text = parent.get_text(separator=" ", strip=True)
                    m = date_pattern.search(text)
                    if m:
                        month_str = f"{m.group(1)}-{m.group(2)}"
                        nums = re.findall(r"[\d,]+(?:\.\d+)?[KMB]?", text)
                        parsed = [parse_sb_number(n) for n in nums if n]
                        parsed = [p for p in parsed if p and p > 1000]
                        if len(parsed) >= 2:
                            rows.append({
                                "channel_id": channel_id,
                                "channel_label": label,
                                "month": month_str,
                                "subscribers": parsed[0],
                                "views": parsed[1],
                                "source": "socialblade",
                            })
            return rows

        for tr in table.find_all("tr")[1:]:   # skip header
            cells = [td.get_text(strip=True) for td in tr.find_all(["td","th"])]
            if len(cells) < 3:
                continue
            # cells[0] = month, cells[1] = subscriber delta or total, cells[2] = view delta or total
            month_text = cells[0]
            m = re.search(r"(20\d\d)-(0[1-9]|1[0-2])", month_text)
            if not m:
                # try "January 2024" format
                m2 = re.search(r"(\w+ 20\d\d)", month_text)
                if m2:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(m2.group(1), "%B %Y")
                        month_text = dt.strftime("%Y-%m")
                    except Exception:
                        continue
                else:
                    continue
            else:
                month_text = f"{m.group(1)}-{m.group(2)}"

            subs  = parse_sb_number(cells[1]) if len(cells) > 1 else None
            views = parse_sb_number(cells[2]) if len(cells) > 2 else None

            if month_text:
                rows.append({
                    "channel_id":    channel_id,
                    "channel_label": label,
                    "month":         month_text,
                    "subscribers":   subs,
                    "views":         views,
                    "source":        "socialblade",
                })

    except Exception as e:
        print(f"  Error scraping {label}: {e}")

    return rows


all_rows = []

for c in channels:
    print(f"Scraping {c['label']} ({c['channel_id']})...")
    rows = scrape_channel_monthly(c["channel_id"], c["label"])
    if rows:
        print(f"  → {len(rows)} months of data")
        all_rows.extend(rows)
    else:
        print(f"  → no data found")
    time.sleep(3)   # be polite

if not all_rows:
    print("No data scraped — Social Blade may have blocked the requests.")
    print("Try running again or check if socialblade.com is accessible.")
else:
    df_new = pd.DataFrame(all_rows)
    df_new = df_new.dropna(subset=["month"])

    if OUT.exists():
        df_old = pd.read_csv(OUT)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["channel_id", "month"], keep="last")
    else:
        df = df_new

    df = df.sort_values(["channel_label", "month"])
    df.to_csv(OUT, index=False)
    print(f"\nSaved → {OUT}")
    print(f"  Channels : {df['channel_label'].nunique()}")
    print(f"  Months   : {df['month'].nunique()}")
    print(f"  Total rows: {len(df)}")
    print(f"  Date range: {df['month'].min()} → {df['month'].max()}")
