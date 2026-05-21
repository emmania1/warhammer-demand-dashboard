"""
One-time backfill for Reddit store threads — goes back as far as Reddit's search allows.

Uses t=all (no time limit) and 25 pages (2500 posts max) per subreddit.
Run once to populate historical data. After that, the weekly
fetch_reddit_store_threads.py (t=year, 10 pages) keeps it current.

Merges into the same CSVs as the weekly script so data is seamless.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone

SUBREDDITS   = ["Warhammer", "Warhammer40k"]
SEARCH_Q     = "store OR FLGS OR \"hobby shop\" OR \"game shop\""
USER_AGENT   = "warhammer-demand-tracker"
MONTHLY_OUT  = "data/reddit_store_threads_monthly.csv"
RECENT_OUT   = "data/reddit_store_threads_recent.csv"
MAX_PAGES    = 25     # 2500 posts max per subreddit
TOP_N_RECENT = 20


def utc_month(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m")


def fetch_store_posts(subreddit, max_pages=MAX_PAGES):
    rows = []
    after = None
    url_base = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={requests.utils.quote(SEARCH_Q)}"
        f"&restrict_sr=1&sort=new&t=all&limit=100"   # t=all = no time limit
    )

    for page_num in range(max_pages):
        url = url_base + (f"&after={after}" if after else "")
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"    Error on page {page_num+1}: {e}")
            break

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        oldest_in_page = None
        for c in children:
            p = c["data"]
            month = utc_month(p["created_utc"])
            oldest_in_page = month
            rows.append({
                "subreddit":    subreddit,
                "post_id":      p.get("id"),
                "month":        month,
                "date":         datetime.fromtimestamp(int(p["created_utc"]), tz=timezone.utc).strftime("%Y-%m-%d"),
                "title":        p.get("title", ""),
                "score":        int(p.get("score", 0)),
                "num_comments": int(p.get("num_comments", 0)),
                "url":          f"https://reddit.com{p.get('permalink', '')}",
                "flair":        p.get("link_flair_text") or "",
            })

        after = data.get("data", {}).get("after")
        print(f"    Page {page_num+1}: {len(children)} posts, oldest: {oldest_in_page}")
        if not after:
            print(f"    No more pages.")
            break
        time.sleep(1.0)

    return pd.DataFrame(rows)


os.makedirs("data", exist_ok=True)
all_posts = []

for sub in SUBREDDITS:
    print(f"\nBackfilling r/{sub} (t=all, {MAX_PAGES} pages max)...")
    df = fetch_store_posts(sub)
    if not df.empty:
        all_posts.append(df)
        months = sorted(df["month"].unique())
        print(f"  → {len(df)} posts  ({months[0]} → {months[-1]})")
    else:
        print(f"  → no results")
    time.sleep(2.0)

if not all_posts:
    print("Nothing fetched.")
else:
    posts_df = pd.concat(all_posts, ignore_index=True)
    posts_df = posts_df.drop_duplicates(subset=["post_id"])

    # Monthly aggregation
    monthly = (
        posts_df.groupby(["subreddit", "month"])
        .agg(post_count=("post_id", "count"),
             avg_score=("score", "mean"),
             total_comments=("num_comments", "sum"))
        .reset_index()
    )
    monthly["avg_score"] = monthly["avg_score"].round(1)

    eco_monthly = (
        posts_df.groupby("month")
        .agg(post_count=("post_id", "count"),
             avg_score=("score", "mean"),
             total_comments=("num_comments", "sum"))
        .reset_index()
    )
    eco_monthly["subreddit"] = "__eco__"
    eco_monthly["avg_score"] = eco_monthly["avg_score"].round(1)

    monthly_new = pd.concat([monthly, eco_monthly], ignore_index=True)

    # Merge with existing
    if os.path.exists(MONTHLY_OUT):
        old = pd.read_csv(MONTHLY_OUT)
        combined = pd.concat([old, monthly_new], ignore_index=True)
        combined = combined.drop_duplicates(subset=["subreddit", "month"], keep="last")
    else:
        combined = monthly_new

    combined = combined.sort_values(["subreddit", "month"])
    combined.to_csv(MONTHLY_OUT, index=False)

    months_all = sorted(combined[combined["subreddit"] == "__eco__"]["month"].unique())
    print(f"\nSaved → {MONTHLY_OUT}")
    print(f"  Date range : {months_all[0]} → {months_all[-1]}  ({len(months_all)} months)")
    print(f"  Total rows : {len(combined)}")

    # Update recent threads
    recent = (
        posts_df.sort_values("score", ascending=False)
        .head(TOP_N_RECENT)
        [["subreddit", "date", "title", "score", "num_comments", "flair", "url"]]
        .copy()
    )
    recent.to_csv(RECENT_OUT, index=False)
    print(f"Saved → {RECENT_OUT}  ({len(recent)} top threads)")
    if not recent.empty:
        print(f"  Top thread: [{recent.iloc[0]['score']} pts] {recent.iloc[0]['title'][:80]}")
