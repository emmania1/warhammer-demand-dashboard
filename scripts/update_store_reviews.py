"""
update_store_reviews.py

Quarterly update pipeline for GW store review tracking.

For every store in data/stores.json, pulls the current review_count and rating
from the Google Places API, records the delta since the last snapshot, and appends
a new entry to data/review_history.json.

Usage:
    source venv/bin/activate
    python3 scripts/update_store_reviews.py

Outputs:
    data/stores.json         — updated with today's review_count / rating
    data/review_history.json — append-only log of quarterly snapshots

Suggested cron schedule (quarterly):
    # Run on the 1st of Jan, Apr, Jul, Oct at 08:00
    0 8 1 1,4,7,10 * cd /path/to/warhammer_demand && source venv/bin/activate && python3 scripts/update_store_reviews.py >> logs/store_reviews.log 2>&1

Requires: GOOGLE_PLACES_API_KEY in .env or environment.
"""

import os, json, time, sys
from datetime import date
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

PLACES_API_KEY  = os.getenv("GOOGLE_PLACES_API_KEY")
STORES_PATH     = Path("data/stores.json")
HISTORY_PATH    = Path("data/review_history.json")
SNAPSHOT_DATE   = str(date.today())

DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


# ── Places API helper ──────────────────────────────────────────────────────────

def get_place_details(place_id: str) -> dict:
    """Fetch current rating and user_ratings_total for a place_id."""
    params = {
        "place_id": place_id,
        "fields":   "name,rating,user_ratings_total",
        "key":      PLACES_API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        raise RuntimeError(f"Places API status={data.get('status')}")
    return data.get("result", {})


# ── History helpers ────────────────────────────────────────────────────────────

def load_history() -> list[dict]:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text())
        except json.JSONDecodeError:
            return []
    return []


def last_review_count(history: list[dict], place_id: str) -> int | None:
    """Return the most recent review_count recorded for this place_id, or None."""
    entries = [e for e in history if e.get("place_id") == place_id]
    if not entries:
        return None
    # Most recent entry by snapshot_date
    entries.sort(key=lambda e: e.get("snapshot_date", ""), reverse=True)
    return entries[0].get("review_count")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not PLACES_API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY not set in .env or environment.")
        sys.exit(1)

    if not STORES_PATH.exists():
        print(f"ERROR: {STORES_PATH} not found. Run scripts/scrape_gw_stores.py first.")
        sys.exit(1)

    stores: list[dict] = json.loads(STORES_PATH.read_text())
    history: list[dict] = load_history()

    # Check for duplicate run on same date
    today_entries = [e for e in history if e.get("snapshot_date") == SNAPSHOT_DATE]
    if today_entries:
        already = len(set(e["place_id"] for e in today_entries))
        print(f"⚠ {already} stores already logged for {SNAPSHOT_DATE}. Re-running will add duplicates.")
        print("  Pass --force to override, or delete today's entries from review_history.json.")
        if "--force" not in sys.argv:
            sys.exit(0)

    print(f"── Quarterly store review update — {SNAPSHOT_DATE} ──────────────────")
    print(f"   {len(stores)} stores in stores.json\n")

    new_history_entries: list[dict] = []
    ok_count   = 0
    err_count  = 0
    updated_stores: list[dict] = []

    for store in stores:
        pid  = store.get("place_id")
        name = store.get("name", "?")

        if not pid:
            print(f"  [SKIP] {name} — no place_id")
            updated_stores.append(store)
            continue

        prev_count = last_review_count(history, pid) or store.get("review_count") or 0

        try:
            details = get_place_details(pid)
            new_count  = details.get("user_ratings_total", store.get("review_count", 0))
            new_rating = details.get("rating", store.get("rating"))
            delta      = new_count - prev_count if prev_count is not None else None

            # Update the store record
            store["review_count"]  = new_count
            store["rating"]        = new_rating
            store["snapshot_date"] = SNAPSHOT_DATE

            # Append to history log
            new_history_entries.append({
                "place_id":      pid,
                "name":          name,
                "city":          store.get("city", ""),
                "country":       store.get("country", ""),
                "snapshot_date": SNAPSHOT_DATE,
                "review_count":  new_count,
                "rating":        new_rating,
                "delta":         delta,          # reviews added since last snapshot
            })

            delta_str = f"+{delta}" if delta and delta > 0 else str(delta) if delta is not None else "—"
            print(f"  ✓  {name:<45} reviews: {new_count:>5,}  Δ {delta_str:>6}  ★ {new_rating or '—'}")
            ok_count += 1

        except Exception as e:
            print(f"  ✗  {name:<45} ERROR: {e}")
            err_count += 1
            # Keep existing data, mark with error
            store["error"] = str(e)

        updated_stores.append(store)
        time.sleep(0.25)  # courtesy pause

    # Persist updated stores.json
    STORES_PATH.write_text(json.dumps(updated_stores, indent=2, ensure_ascii=False))

    # Append new entries to review_history.json
    history.extend(new_history_entries)
    HISTORY_PATH.parent.mkdir(exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False))

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n── Summary ──────────────────────────────────────────────────────────")
    print(f"   Stores updated:       {ok_count}")
    print(f"   Errors:               {err_count}")
    print(f"   History entries now:  {len(history)}")

    if new_history_entries:
        total_delta = sum(e["delta"] for e in new_history_entries if e.get("delta") is not None)
        top_movers  = sorted(new_history_entries, key=lambda e: e.get("delta") or 0, reverse=True)[:5]
        print(f"\n   Total new reviews this quarter: +{total_delta:,}")
        print(f"   Top 5 by review velocity:")
        for e in top_movers:
            d = e.get("delta")
            d_str = f"+{d}" if d and d > 0 else str(d) if d is not None else "—"
            print(f"     {e['name']:<45} Δ {d_str:>6}")

    if err_count:
        print(f"\n   ⚠ {err_count} errors — check place_ids or API quota.")

    print(f"\n   stores.json   → {STORES_PATH}")
    print(f"   review_history.json → {HISTORY_PATH}")


if __name__ == "__main__":
    main()
