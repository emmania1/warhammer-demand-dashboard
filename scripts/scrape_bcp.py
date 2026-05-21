"""
scrape_bcp.py

Scrapes Best Coast Pairings (bestcoastpairings.com) for Warhammer 40k store-level events.

For each event pulls:
  store_name, city, state, country, date, player_count, event_type, event_id, event_name

Saves to data/bcp_events.json (accumulation model — never overwrites, always appends).

BCP's public API is used — same endpoints the web app calls.
client-id header = REACT_APP_AUTH_CLIENT_ID value from the web app JS bundle.

Endpoint:  https://newprod-api.bestcoastpairings.com/v1/events
Pagination: cursor-based via nextKey (not page numbers).
  Response shape: { data: [...], nextKey: "..." }

Usage:
    source venv/bin/activate

    # Normal incremental run (fetch events since last saved date):
    python3 scripts/scrape_bcp.py

    # Backfill N months of history (one month at a time, safe to re-run):
    python3 scripts/scrape_bcp.py --backfill 12

    # Control max pages per fetch window (default 25):
    python3 scripts/scrape_bcp.py --backfill 12 --pages 25

Outputs:
    data/bcp_events.json
"""

import os, json, time, sys, calendar
import requests
from datetime import date, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

OUT           = Path("data/bcp_events.json")
SNAPSHOT_DATE = str(date.today())
MAX_PAGES     = int(sys.argv[sys.argv.index("--pages") + 1]) if "--pages" in sys.argv else 25
BACKFILL_MONTHS = int(sys.argv[sys.argv.index("--backfill") + 1]) if "--backfill" in sys.argv else 0
PER_PAGE      = 25

# ── BCP API ───────────────────────────────────────────────────────────────────
BCP_EVENTS_URL  = "https://newprod-api.bestcoastpairings.com/v1/events"
WH40K_GAME_TYPE = "1"  # numeric ID — "W40k" string is not accepted

HEADERS = {
    "Accept":     "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; warhammer-demand-tracker/1.0)",
    "Origin":     "https://www.bestcoastpairings.com",
    "Referer":    "https://www.bestcoastpairings.com/",
    "client-id":  "web-app",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def month_window(year: int, month: int) -> tuple:
    """Return (start_date, end_date) strings for the given year/month."""
    last_day = calendar.monthrange(year, month)[1]
    return (
        f"{year:04d}-{month:02d}-01",
        f"{year:04d}-{month:02d}-{last_day:02d}",
    )


def months_back(n: int) -> list:
    """Return list of (year, month) tuples going back n months from today, oldest first."""
    today = date.today()
    result = []
    for i in range(n, 0, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        result.append((y, m))
    return result


def fetch_events_page(next_key, start_date: str, end_date: str) -> dict:
    """Fetch one page of Warhammer 40k events from BCP using cursor pagination."""
    params = {
        "gameType":      WH40K_GAME_TYPE,
        "limit":         PER_PAGE,
        "sortKey":       "eventDate",
        "sortAscending": "false",
        "startDate":     start_date,
        "endDate":       end_date,
    }
    if next_key:
        params["nextKey"] = next_key
    resp = requests.get(BCP_EVENTS_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def normalize_event(ev: dict) -> dict:
    """Extract the fields we care about from a raw BCP event record."""
    store = ev.get("store") or {}
    loc   = ev.get("location") or store.get("location") or {}

    city    = loc.get("city")    or ev.get("city")    or ""
    state   = loc.get("state")   or ev.get("state")   or ""
    country = loc.get("country") or ev.get("country") or ""

    players = (
        ev.get("totalPlayers")
        or ev.get("checkedInPlayers")
        or ev.get("queryNumPlayers")
        or ev.get("numberOfPlayers")
        or ev.get("playerCount")
        or ev.get("numPlayers")
        or 0
    )
    try:
        players = int(players)
    except (TypeError, ValueError):
        players = 0

    raw_date = ev.get("eventDate") or ev.get("date") or ""
    try:
        parsed     = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        event_date = parsed.strftime("%Y-%m-%d")
    except Exception:
        event_date = raw_date[:10] if raw_date else ""

    return {
        "event_id":      ev.get("id") or ev.get("eventId") or "",
        "event_name":    ev.get("name") or ev.get("eventName") or "",
        "store_name":    ev.get("gameStoreName") or store.get("name") or ev.get("storeName") or "",
        "city":          city,
        "state":         state,
        "country":       country,
        "date":          event_date,
        "player_count":  players,
        "event_type":    ev.get("eventType") or ev.get("type") or "",
        "game_type":     ev.get("gameType") or WH40K_GAME_TYPE,
        "game_system":   ev.get("gameSystemName") or "",
        "snapshot_date": SNAPSHOT_DATE,
    }


def fetch_window(start_date: str, end_date: str, seen_ids: set, label: str = "") -> list:
    """
    Fetch all events in a given date window, skipping already-seen IDs.
    Returns list of normalized new events.
    """
    new_events = []
    next_key   = None
    total      = 0

    print(f"\n  [{label or start_date}] Fetching {start_date} → {end_date}")

    for page_num in range(1, MAX_PAGES + 1):
        try:
            data = fetch_events_page(next_key, start_date, end_date)
        except requests.HTTPError as e:
            print(f"    [HTTP ERROR] page {page_num}: {e}")
            if e.response is not None:
                print(f"    Response: {e.response.text[:300]}")
            break
        except Exception as e:
            print(f"    [ERROR] page {page_num}: {e}")
            break

        if isinstance(data, list):
            events_raw = data
            next_key   = None
        elif isinstance(data, dict):
            events_raw = (
                data.get("data") or data.get("events") or data.get("results") or []
            )
            next_key = data.get("nextKey")
        else:
            events_raw = []
            next_key   = None

        if not events_raw:
            print(f"    Page {page_num}: empty — done.")
            break

        page_new = 0
        for ev in events_raw:
            norm = normalize_event(ev)
            eid  = norm["event_id"]
            if eid and eid in seen_ids:
                continue
            if eid:
                seen_ids.add(eid)
            if norm["player_count"] == 0:
                continue
            new_events.append(norm)
            page_new += 1

        total += page_new
        print(f"    Page {page_num:2d}: {page_new:3d} new  (window total: {total})"
              + (f"  nextKey: {str(next_key)[:35]}…" if next_key else "  [last page]"))

        if not next_key:
            break

        time.sleep(0.4)

    return new_events


def save(all_events: list):
    """Sort by date descending and write to disk."""
    all_events.sort(key=lambda e: e.get("date", ""), reverse=True)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(all_events, indent=2, ensure_ascii=False))


def print_summary(existing_count: int, new_events: list, all_events: list):
    from collections import Counter
    print(f"\n── Summary ──────────────────────────────────────────────────────────")
    print(f"  Previously stored:   {existing_count}")
    print(f"  New events added:    {len(new_events)}")
    print(f"  Total events saved:  {len(all_events)}")

    if all_events:
        non_zero    = [e for e in all_events if e["player_count"] > 0]
        avg_players = sum(e["player_count"] for e in non_zero) / len(non_zero) if non_zero else 0
        print(f"  Avg players/event:   {avg_players:.0f}")

        months = Counter(e["date"][:7] for e in all_events if e.get("date"))
        print(f"\n  Monthly event counts (most recent 18 months):")
        for ym in sorted(months.keys(), reverse=True)[:18]:
            bar = "█" * min(40, months[ym] // 10)
            print(f"    {ym}: {months[ym]:4d}  {bar}")

        countries = Counter(e["country"] for e in all_events if e.get("country"))
        print(f"\n  Top countries:")
        for country, n in countries.most_common(10):
            print(f"    {country or '(unknown)':20s}: {n}")

    print(f"\n  Saved to: {OUT}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load existing events
    existing_events: list = []
    seen_ids: set = set()

    if OUT.exists():
        try:
            existing_events = json.loads(OUT.read_text())
            seen_ids = {e["event_id"] for e in existing_events if e.get("event_id")}
            print(f"  Loaded {len(existing_events)} existing events from {OUT}")
        except Exception as ex:
            print(f"  [WARN] Could not load existing data ({ex}); starting fresh")

    existing_count = len(existing_events)

    print(f"\n── BCP Warhammer 40k Scrape — {SNAPSHOT_DATE} ────────────────────────")

    all_new: list = []

    if BACKFILL_MONTHS > 0:
        # ── Backfill mode: fetch one month at a time going back N months ────────
        windows = months_back(BACKFILL_MONTHS)
        # Also include current month
        today = date.today()
        windows.append((today.year, today.month))

        print(f"  Backfill mode: {BACKFILL_MONTHS} months back + current month")
        print(f"  Windows to fetch: {[f'{y}-{m:02d}' for y, m in windows]}")
        print(f"  Max pages per window: {MAX_PAGES}  ({MAX_PAGES * PER_PAGE} events/window)\n")

        for year, month in windows:
            start, end = month_window(year, month)
            label = f"{year}-{month:02d}"
            # Skip months already fully covered (has events AND latest date in that month)
            existing_in_month = [e for e in existing_events if e.get("date", "").startswith(label)]
            if existing_in_month:
                print(f"\n  [{label}] Already have {len(existing_in_month)} events — skipping")
                continue
            new = fetch_window(start, end, seen_ids, label=label)
            all_new.extend(new)
            # Save incrementally after each month so progress isn't lost on error
            combined = existing_events + all_new
            save(combined)
            print(f"  [{label}] Saved {len(new)} new events. Running total: {len(combined)}")
            time.sleep(1.0)  # be polite between months

    else:
        # ── Incremental mode: fetch from latest stored date forward ─────────────
        end_date = SNAPSHOT_DATE
        if existing_events:
            latest     = max(e["date"] for e in existing_events if e.get("date"))
            start_date = latest
            print(f"  Incremental mode: {start_date} → {end_date}")
        else:
            start_date = f"{int(SNAPSHOT_DATE[:4]) - 2}-{SNAPSHOT_DATE[5:]}"
            print(f"  No existing data — fetching 2-year window: {start_date} → {end_date}")

        print(f"  Max pages: {MAX_PAGES}  ({MAX_PAGES * PER_PAGE} events max)\n")
        all_new = fetch_window(start_date, end_date, seen_ids, label="incremental")

    # Final save + summary
    all_events = existing_events + all_new
    save(all_events)
    print_summary(existing_count, all_new, all_events)


if __name__ == "__main__":
    main()
