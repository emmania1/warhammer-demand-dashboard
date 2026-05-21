"""
Reddit Store Thread Tracker — physical retail demand signal.

Searches r/Warhammer and r/Warhammer40k for store-related posts
(store, FLGS, hobby shop, game shop, local store) and saves:
  - Monthly post-count totals → data/reddit_store_threads_monthly.csv
  - Recent high-engagement threads → data/reddit_store_threads_recent.csv

These are two separate signals:
  Monthly count trend   — is store discussion growing over time?
  High-score threads    — qualitative: what are people saying about stores?

No auth required. Uses public Reddit JSON API (same pattern as fetch_reddit_daily.py).
Rate limit: 1 second between requests.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone

SUBREDDITS   = ["Warhammer", "Warhammer40k"]
# title: prefix = search title text only, avoiding "store my minis" body-text noise
SEARCH_Q     = ("title:FLGS OR title:LGS OR title:\"local game store\" OR "
                "title:\"game store\" OR title:\"hobby shop\" OR title:\"game shop\" OR "
                "title:\"warhammer store\" OR title:\"local store\"")
USER_AGENT   = "warhammer-demand-tracker"
MONTHLY_OUT  = "data/reddit_store_threads_monthly.csv"
RECENT_OUT   = "data/reddit_store_threads_recent.csv"
RAW_OUT      = "data/reddit_store_threads_raw.csv"
MAX_PAGES    = 10    # max 10 pages × 100 = 1000 posts per subreddit per run
TOP_N_RECENT = 20    # save top-N threads by score for the recent table


def utc_month(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m")


def fetch_store_posts(subreddit, max_pages=MAX_PAGES):
    """Fetch recent store-related posts via Reddit search JSON endpoint."""
    rows = []
    after = None
    url_base = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={requests.utils.quote(SEARCH_Q)}"
        f"&restrict_sr=1&sort=new&t=year&limit=100"
    )

    for _ in range(max_pages):
        url = url_base + (f"&after={after}" if after else "")
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"    Error fetching r/{subreddit}: {e}")
            break

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        for c in children:
            p = c["data"]
            rows.append({
                "subreddit":    subreddit,
                "post_id":      p.get("id"),
                "month":        utc_month(p["created_utc"]),
                "date":         datetime.fromtimestamp(int(p["created_utc"]), tz=timezone.utc).strftime("%Y-%m-%d"),
                "title":        p.get("title", ""),
                "score":        int(p.get("score", 0)),
                "num_comments": int(p.get("num_comments", 0)),
                "url":          f"https://reddit.com{p.get('permalink', '')}",
                "flair":        p.get("link_flair_text") or "",
            })

        after = data.get("data", {}).get("after")
        if not after:
            break
        time.sleep(1.0)

    return pd.DataFrame(rows)


os.makedirs("data", exist_ok=True)
all_posts = []

for sub in SUBREDDITS:
    print(f"Searching r/{sub} for store threads...")
    df = fetch_store_posts(sub)
    if not df.empty:
        all_posts.append(df)
        months = sorted(df["month"].unique())
        print(f"  → {len(df)} posts  ({months[0]} → {months[-1]})")
    else:
        print(f"  → no results")
    time.sleep(1.5)

if not all_posts:
    print("Nothing fetched.")
else:
    posts_df = pd.concat(all_posts, ignore_index=True)
    posts_df = posts_df.drop_duplicates(subset=["post_id"])

    # ── Monthly counts ──────────────────────────────────────────────────────
    monthly = (
        posts_df.groupby(["subreddit", "month"])
        .agg(
            post_count=("post_id", "count"),
            avg_score=("score", "mean"),
            total_comments=("num_comments", "sum"),
        )
        .reset_index()
    )
    monthly["avg_score"] = monthly["avg_score"].round(1)

    # Ecosystem totals row per month
    eco_monthly = (
        posts_df.groupby("month")
        .agg(
            post_count=("post_id", "count"),
            avg_score=("score", "mean"),
            total_comments=("num_comments", "sum"),
        )
        .reset_index()
    )
    eco_monthly["subreddit"] = "__eco__"
    eco_monthly["avg_score"] = eco_monthly["avg_score"].round(1)

    monthly_all = pd.concat([monthly, eco_monthly], ignore_index=True)
    monthly_all = monthly_all.sort_values(["subreddit", "month"])

    # Merge with existing file
    if os.path.exists(MONTHLY_OUT):
        old = pd.read_csv(MONTHLY_OUT)
        combined = pd.concat([old, monthly_all], ignore_index=True)
        combined = combined.drop_duplicates(subset=["subreddit", "month"], keep="last")
    else:
        combined = monthly_all

    combined = combined.sort_values(["subreddit", "month"])
    combined.to_csv(MONTHLY_OUT, index=False)
    print(f"\nSaved monthly counts → {MONTHLY_OUT}")
    print(f"  Months tracked : {combined['month'].nunique()}")
    print(f"  Total rows     : {len(combined)}")

    # ── Recent high-engagement threads ─────────────────────────────────────
    recent = (
        posts_df
        .sort_values("score", ascending=False)
        .head(TOP_N_RECENT)
        [["subreddit", "date", "title", "score", "num_comments", "flair", "url"]]
        .copy()
    )
    recent.to_csv(RECENT_OUT, index=False)
    print(f"Saved recent threads  → {RECENT_OUT}  ({len(recent)} rows)")
    if not recent.empty:
        print(f"  Top thread: [{recent.iloc[0]['score']} pts] {recent.iloc[0]['title'][:80]}")

    # ── Raw posts (title-level) for category breakdown in dashboard ──────────
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
    print(f"Saved raw posts       → {RAW_OUT}  ({len(raw_combined)} posts)")
