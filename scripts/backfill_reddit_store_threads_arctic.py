"""
Historical backfill for Reddit store threads using Arctic Shift archive.
Arctic Shift (arctic-shift.photon-reddit.com) is a free Reddit archive
that goes back to 2020+ with full post history — not limited by Reddit's
search recency bias.

Fetches store-related posts from r/Warhammer + r/Warhammer40k going back
to Jan 2023. Merges into the same CSVs as the weekly tracker.
Run once. After this, weekly fetch_reddit_store_threads.py keeps it current.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone

SUBREDDITS  = ["Warhammer", "Warhammer40k"]
# Title-only search via Arctic Shift `title=` param — avoids body-text noise
# ("store" as a body keyword matches "how do I store my minis?" and SM2 hype posts)
KEYWORD_LIST = ["FLGS", "LGS", "local game store", "game store", "hobby shop",
                "game shop", "warhammer store", "local store"]
USER_AGENT  = "warhammer-demand-tracker"
MONTHLY_OUT = "data/reddit_store_threads_monthly.csv"
RECENT_OUT  = "data/reddit_store_threads_recent.csv"
RAW_OUT     = "data/reddit_store_threads_raw.csv"
TOP_N       = 20
BASE_URL    = "https://arctic-shift.photon-reddit.com/api/posts/search"

# Backfill from Jan 2023 to now
START_TS = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())
END_TS   = int(datetime.now(timezone.utc).timestamp())


def utc_month(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m")


def fetch_keyword(subreddit, keyword):
    """
    Fetch all posts matching a single keyword via Arctic Shift from START_TS to now.
    Uses 'after' as a Unix timestamp cursor (sort=asc).
    NOTE: Combined OR queries break with after=, so we fetch each keyword separately.
    """
    rows = []
    cursor_ts = START_TS
    page = 0

    while True:
        page += 1
        try:
            r = requests.get(
                BASE_URL,
                params={
                    "subreddit": subreddit,
                    "title":     keyword,   # title-only: avoids body-text false positives
                    "limit":     100,
                    "sort":      "asc",
                    "after":     cursor_ts,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json().get("data") or []
        except requests.exceptions.HTTPError as e:
            if r.status_code == 429:
                print(f"      Rate limited on page {page} — waiting 30s...")
                time.sleep(30)
                continue   # retry same page
            print(f"      Error page {page}: {e}")
            break
        except Exception as e:
            print(f"      Error page {page}: {e}")
            break

        if not data:
            break

        newest_ts = None
        for p in data:
            ts = int(p.get("created_utc") or p.get("created", 0))
            rows.append({
                "subreddit":    subreddit,
                "post_id":      p.get("id"),
                "month":        utc_month(ts),
                "date":         datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "title":        p.get("title", ""),
                "score":        int(p.get("score", 0)),
                "num_comments": int(p.get("num_comments", 0)),
                "url":          f"https://reddit.com{p.get('permalink', '')}",
                "flair":        p.get("link_flair_text") or "",
            })
            newest_ts = ts

        if len(data) < 100 or (newest_ts and newest_ts >= END_TS):
            break

        cursor_ts = newest_ts + 1
        time.sleep(0.5)

    return rows


def fetch_all_posts(subreddit):
    """Run one fetch per keyword, combine and dedup by post_id."""
    all_rows = []
    for kw in KEYWORD_LIST:
        rows = fetch_keyword(subreddit, kw)
        print(f"  [{kw}]: {len(rows)} posts")
        all_rows.extend(rows)
        time.sleep(1.0)

    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["post_id"])
    return df


os.makedirs("data", exist_ok=True)
all_posts = []

for sub in SUBREDDITS:
    print(f"\nBackfilling r/{sub} via Arctic Shift (Jan 2023 → now)...")
    df = fetch_all_posts(sub)
    if not df.empty:
        df = df.drop_duplicates(subset=["post_id"])
        all_posts.append(df)
        months = sorted(df["month"].unique())
        print(f"  → {len(df)} posts  ({months[0]} → {months[-1]})")
    else:
        print(f"  → no results")
    time.sleep(1.0)

if not all_posts:
    print("Nothing fetched.")
else:
    posts_df = pd.concat(all_posts, ignore_index=True).drop_duplicates(subset=["post_id"])

    # Monthly aggregation
    monthly = (
        posts_df.groupby(["subreddit", "month"])
        .agg(post_count=("post_id", "count"),
             avg_score=("score", "mean"),
             total_comments=("num_comments", "sum"))
        .reset_index()
    )
    monthly["avg_score"] = monthly["avg_score"].round(1)

    eco = (
        posts_df.groupby("month")
        .agg(post_count=("post_id", "count"),
             avg_score=("score", "mean"),
             total_comments=("num_comments", "sum"))
        .reset_index()
    )
    eco["subreddit"] = "__eco__"
    eco["avg_score"] = eco["avg_score"].round(1)

    monthly_new = pd.concat([monthly, eco], ignore_index=True)

    # Merge with existing CSV
    if os.path.exists(MONTHLY_OUT):
        old = pd.read_csv(MONTHLY_OUT)
        combined = pd.concat([old, monthly_new], ignore_index=True)
        combined = combined.drop_duplicates(subset=["subreddit", "month"], keep="last")
    else:
        combined = monthly_new

    combined = combined.sort_values(["subreddit", "month"])
    combined.to_csv(MONTHLY_OUT, index=False)

    eco_rows = combined[combined["subreddit"] == "__eco__"].sort_values("month")
    months_list = eco_rows["month"].tolist()
    print(f"\nSaved → {MONTHLY_OUT}")
    print(f"  Date range : {months_list[0]} → {months_list[-1]}  ({len(months_list)} months)")
    print(f"  Total rows : {len(combined)}")

    # Update top recent threads
    recent = (
        posts_df.sort_values("score", ascending=False)
        .head(TOP_N)
        [["subreddit", "date", "title", "score", "num_comments", "flair", "url"]]
        .copy()
    )
    recent.to_csv(RECENT_OUT, index=False)
    print(f"Saved → {RECENT_OUT}  ({len(recent)} top threads)")
    if not recent.empty:
        print(f"  Top thread: [{recent.iloc[0]['score']} pts] {recent.iloc[0]['title'][:80]}")

    # Save raw posts (title-level) for category breakdown analysis in dashboard
    raw_cols = ["post_id", "subreddit", "date", "month", "title", "score", "num_comments", "url", "flair"]
    raw_new = posts_df[raw_cols].copy()
    if os.path.exists(RAW_OUT):
        old_raw = pd.read_csv(RAW_OUT)
        raw_combined = pd.concat([old_raw, raw_new], ignore_index=True)
        raw_combined = raw_combined.drop_duplicates(subset=["post_id"], keep="last")
    else:
        raw_combined = raw_new
    raw_combined = raw_combined.sort_values(["subreddit", "date"])
    raw_combined.to_csv(RAW_OUT, index=False)
    print(f"Saved → {RAW_OUT}  ({len(raw_combined)} individual posts)")
