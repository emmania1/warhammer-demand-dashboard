"""
Daily Reddit metrics updater — expanded subreddit list.

Fetches the last 3 days of posts for every tracked subreddit and appends
aggregated daily stats to data/reddit_history_daily.csv.
Deduplicates on (subreddit, date) so re-running the same day is safe.

Subreddit coverage:
  Core 40k:      Warhammer40k, 40kLore, Grimdank
  Community:     Warhammer, ageofsigmar, paintingwarhammer
  Competitive:   WarhammerCompetitive
  Other systems: Warhammer30k, warhammerfantasy
"""

import os, time, requests
import pandas as pd
from datetime import datetime, timedelta, timezone

SUBREDDITS = [
    # core demand signals
    "Warhammer40k",
    "40kLore",
    "Grimdank",
    "Warhammer",
    "ageofsigmar",
    # hobby / painting engagement
    "minipainting",
    # competitive scene health
    "WarhammerCompetitive",
    # other GW product lines
    "Warhammer30k",
    "warhammerfantasy",
]

DAYS_BACK  = 3     # fetch last 3 days so we never miss a day
USER_AGENT = "warhammer-demand-tracker"
OUTFILE    = "data/reddit_history_daily.csv"


def utc_day(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_posts(subreddit, days_back=3):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    rows   = []
    after  = None

    for _ in range(25):   # max 25 pages = 2500 posts
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=100"
        if after:
            url += f"&after={after}"
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"    Error fetching r/{subreddit}: {e}")
            break

        children = data["data"]["children"]
        if not children:
            break

        for c in children:
            p   = c["data"]
            day = utc_day(p["created_utc"])
            if day < cutoff:
                return pd.DataFrame(rows)
            rows.append({
                "subreddit":    subreddit,
                "date":         day,
                "post_id":      p.get("id"),
                "author":       p.get("author"),
                "num_comments": int(p.get("num_comments", 0)),
                "score":        int(p.get("score", 0)),
            })

        after = data["data"].get("after")
        if not after:
            break
        time.sleep(1.0)

    return pd.DataFrame(rows)


def aggregate_daily(posts_df):
    if posts_df.empty:
        return pd.DataFrame()
    agg = posts_df.groupby(["subreddit", "date"]).agg(
        posts=("post_id", "count"),
        total_comments=("num_comments", "sum"),
        avg_comments_per_post=("num_comments", "mean"),
        unique_authors=("author", pd.Series.nunique),
        avg_score=("score", "mean"),
    ).reset_index()
    agg["avg_comments_per_post"] = agg["avg_comments_per_post"].round(2)
    agg["avg_score"]             = agg["avg_score"].round(2)
    return agg


os.makedirs("data", exist_ok=True)
all_daily = []

for sub in SUBREDDITS:
    print(f"Fetching r/{sub}...")
    posts = fetch_posts(sub, DAYS_BACK)
    daily = aggregate_daily(posts)
    if not daily.empty:
        all_daily.append(daily)
        dates = sorted(daily["date"].unique())
        print(f"  → {len(daily)} rows  ({dates[0]} → {dates[-1]})")
    else:
        print(f"  → no data")
    time.sleep(1.5)

if not all_daily:
    print("Nothing fetched.")
else:
    df_new = pd.concat(all_daily, ignore_index=True)

    if os.path.exists(OUTFILE):
        df_old = pd.read_csv(OUTFILE)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["subreddit", "date"], keep="last")
    else:
        df = df_new

    df = df.sort_values(["subreddit", "date"])
    df.to_csv(OUTFILE, index=False)
    print(f"\nSaved → {OUTFILE}")
    print(f"  Subreddits tracked : {df['subreddit'].nunique()}")
    print(f"  Total rows         : {len(df)}")
    print(f"  Date range         : {df['date'].min()}  →  {df['date'].max()}")
