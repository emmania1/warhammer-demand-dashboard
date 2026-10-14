#!/usr/bin/env python3
"""
Fetch top posts from r/Warhammer + r/Warhammer40k (2023-2025).
Uses Arctic Shift API with monthly pagination to find high-score posts.
Writes:
  data/reddit_intel_posts.csv    — post_id, subreddit, year, title, score, topic
  data/reddit_intel_comments.csv — post_id, subreddit, year (one row per comment slot)
"""

import re, time, datetime, requests, pandas as pd
from pathlib import Path

DATA_DIR    = Path(__file__).parent.parent / "data"
WAIT        = 0.4   # seconds between Arctic Shift calls
MIN_SCORE   = 300   # keep posts above this score
TOP_N       = 30    # keep top-N per subreddit per year by score

SUBREDDITS  = ["Warhammer", "Warhammer40k"]
YEARS       = [2023, 2024, 2025]

FIELDS      = "id,title,score,num_comments,created_utc,subreddit"


# ── Topic categorization ────────────────────────────────────────────────────

def categorize(title: str) -> str:
    t = title.lower()

    if any(k in t for k in [
        "space marine 2", "space marine ii", "boltgun", "rogue trader", "total war",
        "darktide", "vermintide", "video game", "videogame", "pc game", "xbox", "playstation",
        "steam ", "game pass", "console ", "fps ", " rpg ", "warhammer game",
    ]):
        return "Video Games & Digital"

    if any(k in t for k in [
        "new to warhammer", "new to 40k", "new to the hobby", "just started", "just getting",
        "getting started", "new player", "first army", "first mini", "first model", "first time",
        "beginner", "help me choose", "where do i start", "how do i start", "complete beginner",
        "just bought my first", "just picked up", "bought my first",
    ]):
        return "New Player / Getting Started"

    if any(k in t for k in [
        "tournament", "competitive play", "itc ", " gt ", "grand tournament",
        "list building", "army list", "matched play", "points cost",
        "meta ", "codex errata", "faq update", "points change",
    ]):
        return "Competitive & Tournaments"

    if any(k in t for k in [
        "price increase", "price hike", "pricing", "overpriced", "expensive", "tariff",
        "the cost of", "how much does", "is it worth", "value for money",
        "secondary market", "resell", "ebay ", "afford ",
    ]):
        return "Pricing & Value"

    if any(k in t for k in [
        "new release", "just announced", "reveal ", "announcement", " leak", "rumour", "rumor",
        "preview ", "new codex", "codex drop", "combat patrol", "army box", "battleforce",
        "christmas box", "new model", "new kit", "new sculpt", "new edition", "10th edition",
        "chapter approved", "points update",
    ]):
        return "New Releases & News"

    if any(k in t for k in [
        "lore ", "the lore", "in lore", "fluff", "primarch", "the emperor",
        "chaos god", "heresy", "horus heresy", "history of", "story of",
        "what happened to", "explained", "novel ", "black library", "audio drama",
        "book review", "headcanon", "canonically", "40k universe",
    ]):
        return "Lore & Narrative"

    if any(k in t for k in [
        "flgs", "lgs ", "local game store", "local gaming", "game store",
        "warhammer store", "hobby store", "indie retailer",
    ]):
        return "Store & Retail"

    if any(k in t for k in [
        "meme", "cursed", "blessed", "wholesome", "funny", "lol ",
        "hot take", "unpopular opinion", "change my mind", "imagine if",
        "chad ", "based ", "absolute unit", "warhammer moment",
    ]):
        return "Community & Humour"

    if any(k in t for k in [
        "how many", "what is your", "which is your", "favourite", "favorite",
        "what do you think", "anyone else", "does anyone", "is it just me",
        "thoughts on", "would you rather", "poll ", "ama ", "hot takes",
        "opinion on", "discuss ", "serious question",
    ]):
        return "General Discussion"

    # Default: hobby/painting if model/paint keywords present
    if any(k in t for k in [
        "paint", "painted", "painting", "kitbash", "conversion", " wip", "w.i.p",
        "finished ", "finally finished", "my army", "my collection", "showcase",
        "model ", "miniature", "mini ", "primer", "airbrush", "highlight",
        "shade ", "wash ", "contrast", "display", "diorama", "terrain", "i made",
        "i built", "i sculpted",
    ]):
        return "Hobby & Painting"

    return "General Discussion"


# ── Arctic Shift fetch ──────────────────────────────────────────────────────

def fetch_month(subreddit: str, year: int, month: int) -> list[dict]:
    start = datetime.datetime(year, month, 1)
    if month == 12:
        end = datetime.datetime(year, 12, 31, 23, 59, 59)
    else:
        end = datetime.datetime(year, month + 1, 1) - datetime.timedelta(seconds=1)

    after  = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    before = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    url = "https://arctic-shift.photon-reddit.com/api/posts/search"
    params = {
        "subreddit": subreddit,
        "after":     after,
        "before":    before,
        "sort":      "desc",
        "limit":     100,
        "fields":    FIELDS,
    }
    try:
        r = requests.get(url, params=params, timeout=30,
                         headers={"User-Agent": "warhammer-demand-intel/1.0"})
        r.raise_for_status()
        return r.json().get("data") or []
    except Exception as e:
        print(f"    error {year}-{month:02d}: {e}")
        return []


def fetch_year(subreddit: str, year: int) -> list[dict]:
    """Fetch all months in a year, collect posts, return top-N by score."""
    all_posts: dict[str, dict] = {}
    for month in range(1, 13):
        posts = fetch_month(subreddit, year, month)
        for p in posts:
            pid   = p.get("id", "")
            score = p.get("score", 0) or 0
            if pid and score >= MIN_SCORE:
                all_posts[pid] = p
        time.sleep(WAIT)
    ranked = sorted(all_posts.values(), key=lambda x: -(x.get("score") or 0))
    return ranked[:TOP_N]


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    post_rows    = []
    comment_rows = []

    for sub in SUBREDDITS:
        for yr in YEARS:
            print(f"\n── r/{sub} {yr} (monthly scan)")
            posts = fetch_year(sub, yr)
            print(f"   {len(posts)} top posts collected (score ≥ {MIN_SCORE})")
            for p in posts:
                score = int(p.get("score", 0) or 0)
                pid   = p.get("id", "")
                title = p.get("title", "")
                n_com = int(p.get("num_comments", 0) or 0)
                topic = categorize(title)
                post_rows.append({
                    "post_id":      pid,
                    "subreddit":    sub,
                    "year":         yr,
                    "title":        title,
                    "score":        score,
                    "num_comments": n_com,
                    "topic":        topic,
                })
                for _ in range(min(n_com, 25)):
                    comment_rows.append({"post_id": pid, "subreddit": sub, "year": yr})
                print(f"   [{score:5,}] [{topic[:22]:22s}] {title[:60]}")

    if not post_rows:
        print("\nNo posts fetched.")
        return

    posts_df    = pd.DataFrame(post_rows).drop_duplicates("post_id")
    comments_df = pd.DataFrame(comment_rows)

    out_posts    = DATA_DIR / "reddit_intel_posts.csv"
    out_comments = DATA_DIR / "reddit_intel_comments.csv"
    posts_df.to_csv(out_posts, index=False)
    comments_df.to_csv(out_comments, index=False)

    print(f"\n✓ {len(posts_df)} posts → {out_posts}")
    print(f"✓ {len(comments_df)} comment rows → {out_comments}")

    print("\n── Topic breakdown ──")
    tbl = posts_df.groupby("topic").agg(posts=("post_id","count"), avg_score=("score","mean")).sort_values("posts", ascending=False)
    print(tbl.to_string())


if __name__ == "__main__":
    main()
