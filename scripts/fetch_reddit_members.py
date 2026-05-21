"""
Reddit subreddit member count tracker.

Uses Reddit's public /about.json endpoint (no auth required) to fetch
the subscriber/member count for each tracked subreddit.
Despite Reddit hiding member counts on the web in 2023, the API still
returns the 'subscribers' field.

Saves to data/reddit_members_weekly.csv.
Deduplicates on (date, subreddit) so re-running the same day is safe.
Run weekly (alongside the main pipeline) to build member growth history.
"""

import time
import requests
import pandas as pd
from pathlib import Path
from datetime import date

SUBREDDITS = [
    "Warhammer40k",
    "40kLore",
    "Grimdank",
    "Warhammer",
    "ageofsigmar",
    "minipainting",
    "WarhammerCompetitive",
    "Warhammer30k",
    "warhammerfantasy",
]

USER_AGENT = "warhammer-demand-tracker/1.0"
OUT        = Path("data/reddit_members_weekly.csv")
OUT.parent.mkdir(exist_ok=True)
today      = str(date.today())

print(f"Fetching Reddit member counts for {len(SUBREDDITS)} subreddits...")
rows = []

for sub in SUBREDDITS:
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{sub}/about.json",
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        members      = data.get("subscribers")
        active_users = data.get("accounts_active")   # currently browsing (when available)
        title        = data.get("title", sub)
        rows.append({
            "date":         today,
            "subreddit":    sub,
            "members":      int(members) if members is not None else None,
            "active_users": int(active_users) if active_users is not None else None,
            "title":        title,
            "source":       "reddit_api",
        })
        if members:
            print(f"  r/{sub:<25} {members:>10,} members"
                  + (f"  ({active_users:,} active)" if active_users else ""))
        else:
            print(f"  r/{sub}: members=None (hidden or error)")
    except Exception as e:
        print(f"  r/{sub}: ERROR — {e}")
        rows.append({
            "date": today, "subreddit": sub,
            "members": None, "active_users": None, "title": sub, "source": "reddit_api",
        })
    time.sleep(1.5)   # polite gap

# ── Append / dedup ────────────────────────────────────────────────────────────
df_new = pd.DataFrame(rows)

if OUT.exists():
    df_old = pd.read_csv(OUT)
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["date", "subreddit"], keep="last")
else:
    df = df_new

df = df.sort_values(["subreddit", "date"])
df.to_csv(OUT, index=False)

print(f"\nSaved → {OUT}")
print(f"  Total rows : {len(df)}")
print(f"  Snapshots  : {df['date'].nunique()}")
