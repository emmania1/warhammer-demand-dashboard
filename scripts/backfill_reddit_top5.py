import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import os

SUBREDDITS = [
    "Warhammer40k", "Grimdank", "Warhammer", "40kLore", "ageofsigmar",
    "WarhammerCompetitive", "Warhammer30k", "minipainting", "warhammerfantasy",
]
DAYS_BACK = 60
USER_AGENT = "warhammer-demand-tracker"

OUTFILE = "data/reddit_history_daily.csv"

def utc_day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

def fetch_new_posts(subreddit: str, after_fullname: str | None = None, limit: int = 100):
    # Reddit public JSON (no auth). 'after' works with fullnames like t3_xxxxx
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    if after_fullname:
        url += f"&after={after_fullname}"
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()

def backfill_subreddit(subreddit: str, cutoff_date: str) -> pd.DataFrame:
    rows = []
    after = None
    seen = 0

    while True:
        data = fetch_new_posts(subreddit, after_fullname=after, limit=100)
        children = data["data"]["children"]
        if not children:
            break

        for c in children:
            p = c["data"]
            created_utc = int(p["created_utc"])
            day = utc_day(created_utc)

            # Stop once we go older than cutoff
            if day < cutoff_date:
                return pd.DataFrame(rows)

            rows.append({
                "subreddit": subreddit,
                "date": day,
                "post_id": p.get("id"),
                "author": p.get("author"),
                "num_comments": int(p.get("num_comments", 0)),
                "score": int(p.get("score", 0)),
            })
            seen += 1

        after = data["data"].get("after")
        if after is None:
            break

        # be nice to Reddit
        time.sleep(1.0)

    return pd.DataFrame(rows)

def aggregate_daily(posts_df: pd.DataFrame) -> pd.DataFrame:
    if posts_df.empty:
        return posts_df

    agg = posts_df.groupby(["subreddit", "date"]).agg(
        posts=("post_id", "count"),
        total_comments=("num_comments", "sum"),
        avg_comments_per_post=("num_comments", "mean"),
        unique_authors=("author", pd.Series.nunique),
        avg_score=("score", "mean"),
    ).reset_index()

    # tidy numeric fields
    agg["avg_comments_per_post"] = agg["avg_comments_per_post"].round(2)
    agg["avg_score"] = agg["avg_score"].round(2)
    return agg

def main():
    os.makedirs("data", exist_ok=True)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    all_daily = []

    for sub in SUBREDDITS:
        print(f"Backfilling r/{sub} back to {cutoff} ...")
        posts = backfill_subreddit(sub, cutoff)
        daily = aggregate_daily(posts)
        all_daily.append(daily)

    out = pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame()
    out = out.sort_values(["subreddit", "date"])

    out.to_csv(OUTFILE, index=False)
    print(f"Saved daily history → {OUTFILE}")
    print(f"Rows: {len(out)}")

if __name__ == "__main__":
    main()