"""
Warhammer Community (warhammer-community.com) news article tracker.

Counts articles published in the last 7 and 30 days as a proxy for GW's
release and marketing cadence — more articles = more active release period.

Tries multiple scraping strategies in order:
  1. Category/news page HTML — count article cards with recent dates
  2. Sitemap index — find monthly sitemaps for current year and count entries
  3. RSS feed fallback

Appends to data/warcom_news_daily.csv, deduplicating on date.
"""

import re
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

OUT = Path("data/warcom_news_daily.csv")
OUT.parent.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}

BASE      = "https://www.warhammer-community.com"
today_str = str(date.today())
now       = datetime.now(timezone.utc)
cutoff_7d  = now - timedelta(days=7)
cutoff_30d = now - timedelta(days=30)

articles_7d  = set()
articles_30d = set()
method_used  = "none"


def get(url, **kwargs):
    return requests.get(url, headers=HEADERS, timeout=20, **kwargs)


# ── Strategy 1: scrape the main news listing pages ────────────────────────────
if HAS_BS4:
    print("Strategy 1: scraping article listing pages...")
    pages_to_try = [
        f"{BASE}/en-gb/",
        f"{BASE}/en-gb/articles/",
    ]
    for page_url in pages_to_try:
        try:
            r = get(page_url)
            soup = BeautifulSoup(r.text, "lxml")

            # Look for date strings in the page (ISO dates or "X days ago" patterns)
            # warhammer-community typically has <time> elements or data-date attributes
            time_els = soup.find_all("time")
            for t in time_els:
                raw = t.get("datetime") or t.get_text(strip=True)
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    link = t.find_parent("a")
                    url_str = (link["href"] if link else page_url)
                    if dt >= cutoff_7d:
                        articles_7d.add(url_str)
                    if dt >= cutoff_30d:
                        articles_30d.add(url_str)
                except Exception:
                    pass

            # Also look for article cards with data-date or similar
            for el in soup.find_all(attrs={"data-date": True}):
                try:
                    raw = el["data-date"]
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    link = el.find("a")
                    url_str = (link["href"] if link else page_url)
                    if dt >= cutoff_7d:
                        articles_7d.add(url_str)
                    if dt >= cutoff_30d:
                        articles_30d.add(url_str)
                except Exception:
                    pass

        except Exception as e:
            print(f"  {page_url}: {e}")

    if articles_7d or articles_30d:
        method_used = "html_scrape"
        print(f"  HTML scrape — 7d: {len(articles_7d)}  30d: {len(articles_30d)}")


# ── Strategy 2: count articles in monthly sitemaps for current year ───────────
if not articles_7d and not articles_30d:
    print("Strategy 2: monthly sitemap counting...")
    try:
        from xml.etree import ElementTree as ET

        # Try to find news-specific sitemaps
        r = get(f"{BASE}/sitemap.xml")
        root = ET.fromstring(r.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        all_sitemaps = [loc.text.strip() for loc in root.findall(".//sm:loc", ns)]

        # Filter to recent year sitemaps
        current_year = str(now.year)
        last_year    = str(now.year - 1)
        recent_maps  = [u for u in all_sitemaps if current_year in u or last_year in u]

        if not recent_maps:
            # Try sitemaps that look like news/article indexes
            recent_maps = [u for u in all_sitemaps if "news" in u.lower() or "article" in u.lower()]

        recent_maps = recent_maps[:20]
        print(f"  Found {len(recent_maps)} potentially recent sitemaps")

        # Get lastmod from each sitemap's parent entry if available
        # Alternative: count entries in the sitemap itself (all = recent if it's a monthly map)
        for sm_url in recent_maps:
            try:
                r2 = get(sm_url)
                sm_root = ET.fromstring(r2.content)
                items = sm_root.findall(".//sm:url", ns)
                locs  = [it.find("sm:loc", ns) for it in items]
                locs  = [l.text.strip() for l in locs if l is not None]

                lastmods = sm_root.findall(".//sm:lastmod", ns)
                dates    = []
                for lm in lastmods:
                    try:
                        raw = lm.text.strip()
                        if len(raw) == 10:
                            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        else:
                            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        dates.append(dt)
                    except Exception:
                        pass

                if dates:
                    for i, dt in enumerate(dates):
                        url_str = locs[i] if i < len(locs) else sm_url
                        if dt >= cutoff_7d:
                            articles_7d.add(url_str)
                        if dt >= cutoff_30d:
                            articles_30d.add(url_str)
                else:
                    # No dates — if this is a current-year map, count all entries as "recent"
                    if current_year in sm_url:
                        # Estimate: assume all entries in a current-year sitemap are within 30d
                        # Use a conservative count
                        for loc in locs:
                            articles_30d.add(loc)

                time.sleep(0.3)
            except Exception as e:
                pass

        if articles_7d or articles_30d:
            method_used = "sitemap"
            print(f"  Sitemap — 7d: {len(articles_7d)}  30d: {len(articles_30d)}")

    except Exception as e:
        print(f"  Sitemap error: {e}")


# ── Strategy 3: RSS feed ───────────────────────────────────────────────────────
if not articles_7d and not articles_30d:
    print("Strategy 3: RSS feed...")
    rss_urls = [
        f"{BASE}/feed/",
        f"{BASE}/rss/",
        f"{BASE}/en-gb/feed/",
        f"{BASE}/feed.xml",
    ]
    for rss_url in rss_urls:
        try:
            from xml.etree import ElementTree as ET
            from email.utils import parsedate_to_datetime

            r = get(rss_url)
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            print(f"  {rss_url}: {len(items)} items")

            for item in items:
                pub_el  = item.find("pubDate")
                link_el = item.find("link")
                if pub_el is None:
                    continue
                try:
                    dt = parsedate_to_datetime(pub_el.text).replace(tzinfo=timezone.utc)
                    url_str = link_el.text if link_el is not None else rss_url
                    if dt >= cutoff_7d:
                        articles_7d.add(url_str)
                    if dt >= cutoff_30d:
                        articles_30d.add(url_str)
                except Exception:
                    pass

            if articles_7d or articles_30d:
                method_used = "rss"
                break
        except Exception as e:
            print(f"  {rss_url}: {e}")

# ── Final fallback: count recent articles via HTML article count heuristic ─────
if not articles_7d and not articles_30d and HAS_BS4:
    print("Strategy 4: counting article links on homepage...")
    try:
        r = get(f"{BASE}/en-gb/")
        soup = BeautifulSoup(r.text, "lxml")
        # Find all links that look like article links
        article_links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/articles/" in href or "/en-gb/article" in href:
                article_links.add(href)
        # Use homepage article count as a floor estimate for recent activity
        # (homepage typically shows 20-40 recent articles)
        count = len(article_links)
        if count > 0:
            print(f"  Found {count} article links on homepage (used as 7d+30d proxy)")
            for link in article_links:
                articles_7d.add(link)
                articles_30d.add(link)   # same set — best available proxy
            method_used = "homepage_links"
    except Exception as e:
        print(f"  Homepage scrape failed: {e}")


# ── Save ───────────────────────────────────────────────────────────────────────
row = {
    "date":              today_str,
    "articles_last_7d":  len(articles_7d),
    "articles_last_30d": len(articles_30d),
    "method":            method_used,
}

df_new = pd.DataFrame([row])

if OUT.exists():
    df_old = pd.read_csv(OUT)
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["date"], keep="last")
else:
    df = df_new

df.to_csv(OUT, index=False)
print(f"\nSaved → {OUT}  (method: {method_used})")
print(f"  7d articles : {row['articles_last_7d']}")
print(f"  30d articles: {row['articles_last_30d']}")
