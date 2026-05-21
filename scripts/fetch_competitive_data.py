"""
Warhammer tournament / competitive attendance tracker.

Tries multiple data sources in order:
  1. Best Coast Pairings public event API
  2. Longshanks tournament platform (Warhammer-specific)
  3. Fallback: empty results (script fails gracefully)

Saves the 20 most recent completed Warhammer 40k and AoS events to
data/competitive_events.csv. Deduplicates on event_id.

Fields: event_id, event_name, event_date, player_count, location,
        system (40k / AoS / Fantasy / etc.), source, date_fetched
"""

import re
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

OUT        = Path("data/competitive_events.csv")
OUT.parent.mkdir(exist_ok=True)
today      = str(date.today())
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}

new_events = []


# ── Source 1: Best Coast Pairings public API ───────────────────────────────────
print("Source 1: Best Coast Pairings API...")
BCP_BASE = "https://bestcoastpairings.com"

# BCP uses a GraphQL or REST API; try known public endpoints
bcp_endpoints = [
    # Public event search endpoints (various documented versions)
    f"{BCP_BASE}/api/events?game=Warhammer+40%2C000&limit=20&eventType=0",
    f"{BCP_BASE}/api/events?game=Warhammer+40000&limit=20",
    f"{BCP_BASE}/api/public/events?limit=20",
]

bcp_games = {
    "warhammer 40": "40k",
    "warhammer40": "40k",
    "40k": "40k",
    "age of sigmar": "AoS",
    "aos": "AoS",
    "sigmar": "AoS",
    "old world": "Old World",
    "fantasy": "Fantasy",
    "underworlds": "Underworlds",
    "kill team": "Kill Team",
}

bcp_success = False
for url in bcp_endpoints:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            events_raw = data if isinstance(data, list) else data.get("events", data.get("data", []))
            if events_raw:
                print(f"  Got {len(events_raw)} events from {url}")
                for ev in events_raw[:20]:
                    name = ev.get("name", ev.get("title", ""))
                    ev_date = ev.get("startDate", ev.get("date", ev.get("eventDate", "")))
                    if isinstance(ev_date, str) and len(ev_date) > 10:
                        ev_date = ev_date[:10]
                    players = ev.get("playerCount", ev.get("players", ev.get("pairings_count", 0)))
                    location = ev.get("location", ev.get("city", ""))
                    ev_id = str(ev.get("id", ev.get("eventId", "")))

                    # Determine system
                    name_lower = name.lower()
                    system = "Other GW"
                    for keyword, sys_name in bcp_games.items():
                        if keyword in name_lower:
                            system = sys_name
                            break

                    new_events.append({
                        "event_id":     f"bcp_{ev_id}",
                        "event_name":   name,
                        "event_date":   ev_date,
                        "player_count": int(players) if players else None,
                        "location":     location,
                        "system":       system,
                        "source":       "bestcoastpairings",
                        "date_fetched": today,
                    })
                bcp_success = True
                break
    except Exception as e:
        print(f"  BCP endpoint failed ({url[:60]}): {e}")

if not bcp_success:
    print("  BCP API not accessible — trying Longshanks...")


# ── Source 2: Longshanks (Warhammer-dedicated tournament platform) ────────────
if not new_events and HAS_BS4:
    print("Source 2: Longshanks...")
    LONGSHANKS_BASE = "https://www.longshanks.org"
    # Longshanks lists completed events at /events/?status=completed
    ls_games = [
        ("Warhammer 40,000", "40k",       "/events/?game=Warhammer+40%2C000&status=completed"),
        ("Age of Sigmar",    "AoS",       "/events/?game=Age+of+Sigmar&status=completed"),
    ]
    for game_name, system, path in ls_games:
        try:
            r = requests.get(f"{LONGSHANKS_BASE}{path}", headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "lxml")

            # Longshanks event rows — adapt selectors as needed
            rows_el = (
                soup.select("table.events tbody tr") or
                soup.select(".event-list .event-row") or
                soup.select("tr[data-event-id]")
            )
            print(f"  {game_name}: found {len(rows_el)} event rows")

            for row in rows_el[:10]:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                ev_name = cells[0].get_text(strip=True)
                ev_date = cells[1].get_text(strip=True)
                players_text = cells[2].get_text(strip=True)
                location = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                # Parse player count
                players = None
                m = re.search(r'\d+', players_text)
                if m:
                    players = int(m.group())

                # Normalize date
                try:
                    parsed_date = datetime.strptime(ev_date, "%d/%m/%Y").strftime("%Y-%m-%d")
                except Exception:
                    try:
                        parsed_date = datetime.strptime(ev_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                    except Exception:
                        parsed_date = ev_date

                # Get event ID from link if available
                link = row.find("a")
                ev_id = ""
                if link and link.get("href"):
                    m2 = re.search(r'/(\d+)', link["href"])
                    if m2:
                        ev_id = m2.group(1)

                new_events.append({
                    "event_id":     f"ls_{ev_id or ev_name[:20]}",
                    "event_name":   ev_name,
                    "event_date":   parsed_date,
                    "player_count": players,
                    "location":     location,
                    "system":       system,
                    "source":       "longshanks",
                    "date_fetched": today,
                })
            time.sleep(1)
        except Exception as e:
            print(f"  Longshanks {game_name}: {e}")


# ── Source 3: Warhammer Community GT/tournament articles (last resort) ─────────
if not new_events and HAS_BS4:
    print("Source 3: WarCom tournament articles...")
    try:
        r = requests.get(
            "https://www.warhammer-community.com/en-gb/",
            headers=HEADERS, timeout=20,
        )
        soup = BeautifulSoup(r.text, "lxml")
        # Look for any article titles mentioning GT or championship
        gt_keywords = ["grand tournament", "gt 2025", "gt 2026", "championship", "world championship", "warhammer world"]
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True).lower()
            if any(kw in title for kw in gt_keywords):
                new_events.append({
                    "event_id":     f"warcom_{a['href'][-20:]}",
                    "event_name":   a.get_text(strip=True),
                    "event_date":   today,
                    "player_count": None,
                    "location":     "Warhammer World / unknown",
                    "system":       "40k/AoS",
                    "source":       "warcom_article",
                    "date_fetched": today,
                })
    except Exception as e:
        print(f"  WarCom fallback: {e}")


# ── Save ───────────────────────────────────────────────────────────────────────
if new_events:
    df_new = pd.DataFrame(new_events)
    # Deduplicate on event_id
    if OUT.exists():
        df_old = pd.read_csv(OUT)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["event_id"], keep="last")
    else:
        df = df_new

    if "event_date" in df.columns:
        df = df.sort_values("event_date", ascending=False)
    df.to_csv(OUT, index=False)

    print(f"\nSaved → {OUT} | {len(df)} total events")
    for _, ev in df.head(10).iterrows():
        p = f"  {ev.get('player_count')} players" if ev.get('player_count') else ""
        print(f"  [{ev.get('system','?'):10}] {str(ev.get('event_date',''))[:10]}  "
              f"{str(ev.get('event_name',''))[:50]}{p}")
else:
    print("\nNo competitive event data retrieved from any source.")
    print("This is expected if BCP and Longshanks block automated requests.")
    print("Competitive tracking will populate once a source becomes accessible.")
    # Write an empty file so the report knows the script has run
    if not OUT.exists():
        pd.DataFrame(columns=[
            "event_id","event_name","event_date","player_count",
            "location","system","source","date_fetched"
        ]).to_csv(OUT, index=False)
        print(f"Created empty → {OUT}")
