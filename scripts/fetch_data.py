import requests
from datetime import datetime, timedelta
from pytrends.request import TrendReq
import csv

print("════════════════════════════════════════════════════")
print("Warhammer Demand Tracker —", datetime.now().date())
print("════════════════════════════════════════════════════")

# ===============================
# GOOGLE TRENDS SECTION
# ===============================

def fetch_trends():
    pytrends = TrendReq()
    keywords = [
        "Warhammer 40k",
        "Warhammer starter set",
        "buy Warhammer",
        "Warhammer Age of Sigmar",
        "Warhammer Space Marine"
    ]

    pytrends.build_payload(keywords, timeframe="now 7-d")
    data = pytrends.interest_over_time()

    rows = []

    if not data.empty:
        latest = data.iloc[-1]
        today = datetime.now().strftime("%Y-%m-%d")

        for kw in keywords:
            rows.append({
                "date": today,
                "keyword": kw,
                "score": int(latest[kw])
            })

    return rows

# ===============================
# REDDIT SECTION (NO API NEEDED)
# ===============================

def fetch_reddit_metrics(subreddit="Warhammer40k"):
    headers = {"User-Agent": "warhammer-demand-tracker"}

    about_url = f"https://www.reddit.com/r/{subreddit}/about.json"
    about_resp = requests.get(about_url, headers=headers, timeout=10)
    about_data = about_resp.json()["data"]

    subscribers = about_data["subscribers"]
    active_users = about_data.get("accounts_active", 0)

    new_url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=100"
    new_resp = requests.get(new_url, headers=headers, timeout=10)
    posts = new_resp.json()["data"]["children"]

    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    posts_24h = 0
    total_comments = 0

    for post in posts:
        created = datetime.utcfromtimestamp(post["data"]["created_utc"])
        if created > last_24h:
            posts_24h += 1
            total_comments += post["data"]["num_comments"]

    avg_comments = total_comments / posts_24h if posts_24h > 0 else 0

    return {
        "date": now.strftime("%Y-%m-%d"),
        "subscribers": subscribers,
        "active_users": active_users,
        "posts_last_24h": posts_24h,
        "avg_comments_per_post": round(avg_comments, 2)
    }

# ===============================
# SAVE DATA
# ===============================

def save_trends(rows):
    if not rows:
        print("No Trends data collected.")
        return

    file_exists = False
    try:
        open("data/trends_data.csv", "r")
        file_exists = True
    except:
        pass

    with open("data/trends_data.csv", "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "keyword", "score"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} Trends rows → trends_data.csv")

def save_reddit(metrics):
    file_exists = False
    try:
        open("data/reddit_data.csv", "r")
        file_exists = True
    except:
        pass

    with open("data/reddit_data.csv", "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date",
            "subscribers",
            "active_users",
            "posts_last_24h",
            "avg_comments_per_post"
        ])

        if not file_exists:
            writer.writeheader()

        writer.writerow(metrics)

    print("Saved Reddit data → reddit_data.csv")

# ===============================
# RUN
# ===============================

try:
    trends = fetch_trends()
    save_trends(trends)
except Exception as e:
    print("Trends error:", e)

try:
    reddit_metrics = fetch_reddit_metrics()
    save_reddit(reddit_metrics)
except Exception as e:
    print("Reddit error:", e)

print("Done.")