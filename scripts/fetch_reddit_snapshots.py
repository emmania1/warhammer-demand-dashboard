"""
Fetch Reddit subreddit snapshots for Warhammer demand tracking.

Appends one row per subreddit per run to data/reddit_snapshots.csv.
Dedup key: (date, subreddit) — safe to re-run same day.

API: Reddit public JSON endpoints (no OAuth required).
Rate limit: 1.2 req/sec conservative.

Engagement counting:
  Pages through /r/{sub}/new.json up to MAX_PAGES (100 posts/page).
  Counts posts and sums num_comments for posts created in last LOOKBACK_DAYS.
  If pagination doesn't cover full window, result is partial but labeled as api.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR         = "data"
CONFIG_DIR       = "config"
OUTPUT_CSV       = os.path.join(DATA_DIR,   "reddit_snapshots.csv")
SUBREDDIT_CONFIG = os.path.join(CONFIG_DIR, "reddit_subreddits.csv")

# ── Reddit API settings ───────────────────────────────────────────────────────
BASE_URL      = "https://www.reddit.com"
USER_AGENT    = "WarhammerdDemandTracker/1.0 (demand research)"
SLEEP_SEC     = 1.2      # conservative rate limit — Reddit public: ~1 req/sec
MAX_PAGES     = 12       # max pages of /new to fetch (100 posts/page = 1200 posts max)
LOOKBACK_DAYS = 30

SCHEMA = [
    "date", "subreddit", "members", "active_users",
    "posts_30d", "comments_30d", "posts_per_day", "comments_per_day", "source",
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


# ── API helpers ───────────────────────────────────────────────────────────────

def get_subreddit_info(sub: str) -> dict:
    """Fetch subscriber count and active users from /about.json."""
    url = f"{BASE_URL}/r/{sub}/about.json?raw_json=1"
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    data = r.json().get("data", {})
    return {
        "members":      data.get("subscribers", 0),
        "active_users": data.get("active_user_count", 0),
    }


def get_posts_stats(sub: str, lookback_days: int = LOOKBACK_DAYS) -> dict:
    """Page through /new.json, counting posts and comments within lookback window."""
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp()

    posts_count    = 0
    comments_total = 0
    after          = None
    window_covered = False

    for _ in range(MAX_PAGES):
        params = {"limit": 100, "raw_json": 1}
        if after:
            params["after"] = after

        r = SESSION.get(f"{BASE_URL}/r/{sub}/new.json", params=params, timeout=20)
        r.raise_for_status()
        time.sleep(SLEEP_SEC)

        payload  = r.json().get("data", {})
        children = payload.get("children", [])
        if not children:
            window_covered = True
            break

        for item in children:
            post = item.get("data", {})
            if post.get("created_utc", 0) < cutoff_ts:
                window_covered = True
                break
            posts_count    += 1
            comments_total += int(post.get("num_comments", 0))

        if window_covered:
            break

        after = payload.get("after")
        if not after:
            window_covered = True
            break

    return {
        "posts_30d":        posts_count,
        "comments_30d":     comments_total,
        "posts_per_day":    round(posts_count    / lookback_days, 1),
        "comments_per_day": round(comments_total / lookback_days, 1),
        "window_covered":   window_covered,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("── Reddit Snapshot Fetcher ─────────────────────────────────────")

    if not os.path.exists(SUBREDDIT_CONFIG):
        print(f"[ERROR] Missing {SUBREDDIT_CONFIG}")
        return

    cfg  = pd.read_csv(SUBREDDIT_CONFIG)
    subs = cfg["subreddit"].tolist()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Load existing data; strip today's rows so re-run is safe
    if os.path.exists(OUTPUT_CSV):
        df = pd.read_csv(OUTPUT_CSV)
        df = df[df["date"] != today]
    else:
        df = pd.DataFrame(columns=SCHEMA)

    new_rows = []
    print(f"  Fetching {len(subs)} subreddits → {today}\n")

    for sub in subs:
        print(f"  r/{sub}")
        try:
            info  = get_subreddit_info(sub)
            time.sleep(SLEEP_SEC)
            stats = get_posts_stats(sub)

            row = {
                "date":             today,
                "subreddit":        sub,
                "members":          info["members"],
                "active_users":     info["active_users"],
                "posts_30d":        stats["posts_30d"],
                "comments_30d":     stats["comments_30d"],
                "posts_per_day":    stats["posts_per_day"],
                "comments_per_day": stats["comments_per_day"],
                "source":           "api",
            }
            new_rows.append(row)

            coverage = "full" if stats["window_covered"] else f"partial (>{MAX_PAGES} pages)"
            print(f"    members: {info['members']:>10,}  "
                  f"posts/day: {stats['posts_per_day']:>6.1f}  "
                  f"comments/day: {stats['comments_per_day']:>8.1f}  "
                  f"[coverage: {coverage}]")

        except Exception as e:
            print(f"    [ERROR] {e}")

    if not new_rows:
        print("\n  [WARN] No data fetched.")
        return

    df_new = pd.DataFrame(new_rows)
    df     = pd.concat([df, df_new], ignore_index=True)
    df     = df.sort_values(["subreddit", "date"]).reset_index(drop=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\n── Snapshot Summary: {today} ────────────────────────────────────")
    for row in new_rows:
        print(f"  {row['subreddit']:20s}  "
              f"{row['members']:>10,} members  "
              f"{row['posts_per_day']:>6.1f} posts/day  "
              f"{row['comments_per_day']:>8.1f} comments/day")

    print(f"\n  ✓ {len(new_rows)} snapshots saved → {OUTPUT_CSV}")
    print(f"  Total rows: {len(df)}")


if __name__ == "__main__":
    main()
