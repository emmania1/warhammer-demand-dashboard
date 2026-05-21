"""
Warhammer Reddit Community Intelligence
Fetches top posts + comments from r/Warhammer and r/Warhammer40k,
categorizes by topic, and builds a comprehensive demand dataset.
"""
import requests, time, os, json
import pandas as pd
from datetime import datetime, timezone
from collections import defaultdict

USER_AGENT  = "warhammer-demand-tracker"
SUBREDDITS  = ["Warhammer40k", "Warhammer"]
POSTS_OUT   = "data/reddit_intel_posts.csv"
COMMENTS_OUT = "data/reddit_intel_comments.csv"
SUMMARY_OUT  = "data/reddit_intel_summary.csv"

# ── Topic categories (checked in order — first match wins) ───────────────────
TOPICS = {
    "New Player / Getting Started": [
        "new to", "just started", "starting out", "getting into", "how do i start",
        "beginner", "first army", "first model", "where to start", "new starter",
        "just bought my first", "overwhelmed", "advice for new", "noob", "newbie",
        "help me choose", "which army", "starter set", "recruit edition",
    ],
    "Hobby & Painting": [
        "painted", "painting", "kitbash", "conversion", "basing", "primer",
        "wip", "work in progress", "finished my", "drybrus", "wash ", "contrast paint",
        "airbrush", "sculpt", "3d print", "magnetize", "assembly", "hobby",
        "highlight", "base coat", "layer", "varnish", "texture paint",
    ],
    "Competitive & Tournaments": [
        "tournament", "competitive", "meta ", "list building", "army list",
        "top table", " gt ", "grand tournament", "bracket", "i won", "placed ",
        "matched play", "league night", "ranked", "10th edition meta",
    ],
    "Lore & Narrative": [
        "lore", "fluff", "narrative", "story", "novel", "horus heresy",
        "chaos gods", "emperor ", "primarch", "chapter ", "regiment", "clan ",
        "omnissiah", "warp ", "xenos", "history of", "lore question",
        "what happened to", "explain the", "who is",
    ],
    "New Releases & News": [
        "new release", "preorder", "pre-order", "revealed", "announcement",
        "new model", "new kit", "leaked", "rumour", "upcoming", "gw announced",
        "new edition", "codex", "battletome", "warscroll", "roadmap",
        "revealed:", "new box",
    ],
    "Store & Retail": [
        "flgs", "lgs", "local game store", "warhammer store", "hobby shop",
        "game shop", "in stock", "sold out", "store event", "store closing",
        "game night at", "at my store", "just opened", "local store",
    ],
    "Pricing & Value": [
        "price increase", "too expensive", "overpriced", "price hike",
        "cost of", "msrp", "markup", "how much does", "is it worth",
        "budget army", "tariff", "cheaper alternative",
    ],
    "Video Games & Digital": [
        "space marine 2", "space marine 3", "dawn of war", "total war warhammer",
        "rogue trader", "boltgun", "chaos gate", "video game", "pc game",
        "steam ", "console", "tacticus", "warhammer quest",
    ],
    "Community & Humour": [
        "meme", "joke ", "funny", "cursed ", "blessed ", "lmao", "this is fine",
        "heresy", "for the emperor", "purge ", "exterminatus", "based",
    ],
}

def categorize(title, flair="", comment_text=""):
    combined = f"{title} {flair} {comment_text}".lower()
    for cat, keywords in TOPICS.items():
        if any(kw in combined for kw in keywords):
            return cat
    return "General Discussion"

def fetch_posts(subreddit, timeframe, max_pages=10):
    rows, after = [], None
    base = (f"https://www.reddit.com/r/{subreddit}/top.json"
            f"?t={timeframe}&limit=100")
    for pg in range(max_pages):
        url = base + (f"&after={after}" if after else "")
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            print(f"    page {pg}: {e}"); break
        children = d.get("data", {}).get("children", [])
        if not children: break
        for c in children:
            p = c["data"]
            ts = int(p["created_utc"])
            rows.append({
                "post_id":     p["id"],
                "subreddit":   subreddit,
                "date":        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "month":       datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m"),
                "year":        datetime.fromtimestamp(ts, tz=timezone.utc).year,
                "title":       p.get("title", ""),
                "flair":       p.get("link_flair_text") or "",
                "score":       int(p.get("score", 0)),
                "num_comments":int(p.get("num_comments", 0)),
                "url":         f"https://reddit.com{p.get('permalink','')}",
            })
        after = d.get("data", {}).get("after")
        if not after: break
        time.sleep(1.1)
    return pd.DataFrame(rows)

def fetch_comments(post_id, subreddit, limit=30):
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
            f"?limit={limit}&depth=1&sort=top",
            headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
        data = r.json()
        out = []
        for c in data[1]["data"]["children"]:
            if c["kind"] != "t1": continue
            body = c["data"].get("body","")
            if not body or body in ("[deleted]","[removed]"): continue
            out.append({
                "post_id":    post_id,
                "comment_id": c["data"]["id"],
                "score":      int(c["data"].get("score", 0)),
                "body":       body[:600],
            })
        return out
    except:
        return []

# ── Phase 1: Fetch posts ─────────────────────────────────────────────────────
print("=" * 60)
print("Phase 1 — Fetching posts")
print("=" * 60)
all_posts = []
for sub in SUBREDDITS:
    for tf in ["year", "all"]:
        print(f"  r/{sub} top of {tf}...")
        df = fetch_posts(sub, tf, max_pages=10)
        if not df.empty:
            print(f"    → {len(df)} posts, {df['year'].min()}–{df['year'].max()}")
            all_posts.append(df)
        time.sleep(1.5)

posts_df = pd.concat(all_posts, ignore_index=True)
posts_df = posts_df.drop_duplicates(subset="post_id", keep="first")
posts_df = posts_df[posts_df["year"].between(2022, 2026)]
posts_df["topic"] = posts_df.apply(
    lambda r: categorize(r["title"], r["flair"]), axis=1)

print(f"\nTotal unique posts (2022-2026): {len(posts_df)}")
print(posts_df.groupby(["year","topic"]).size().unstack(fill_value=0))

posts_df.to_csv(POSTS_OUT, index=False)
print(f"\nSaved posts → {POSTS_OUT}")

# ── Phase 2: Fetch comments for posts with score > 150 ───────────────────────
print("\n" + "=" * 60)
print("Phase 2 — Fetching comments (top posts by score)")
print("=" * 60)
to_fetch = posts_df[posts_df["score"] >= 150].sort_values("score", ascending=False)
print(f"Posts to fetch comments for: {len(to_fetch)}")

all_comments = []
for i, (_, row) in enumerate(to_fetch.iterrows()):
    comments = fetch_comments(row["post_id"], row["subreddit"])
    for c in comments:
        c["subreddit"] = row["subreddit"]
        c["year"]      = row["year"]
        c["month"]     = row["month"]
        c["post_topic"]= row["topic"]
        c["post_title"]= row["title"][:80]
        c["post_score"] = row["score"]
        # categorize the comment itself too
        c["comment_topic"] = categorize(c["body"])
    all_comments.extend(comments)
    if (i+1) % 25 == 0:
        print(f"  {i+1}/{len(to_fetch)} posts done, {len(all_comments)} comments so far...")
    time.sleep(1.1)

comments_df = pd.DataFrame(all_comments)
comments_df.to_csv(COMMENTS_OUT, index=False)
print(f"\nTotal comments collected: {len(comments_df)}")
print(f"Saved → {COMMENTS_OUT}")

# ── Phase 3: Summary by topic + year ────────────────────────────────────────
print("\n" + "=" * 60)
print("Phase 3 — Building summary")
print("=" * 60)

summary = (posts_df[posts_df["year"].between(2023,2025)]
    .groupby(["topic","year"])
    .agg(post_count=("post_id","count"),
         avg_score=("score","mean"),
         total_score=("score","sum"),
         total_comments=("num_comments","sum"))
    .reset_index())
summary["avg_score"] = summary["avg_score"].round(0).astype(int)
summary.to_csv(SUMMARY_OUT, index=False)

pivot = summary.pivot_table(
    index="topic", columns="year",
    values=["post_count","avg_score"], aggfunc="sum")
print(pivot.to_string())
