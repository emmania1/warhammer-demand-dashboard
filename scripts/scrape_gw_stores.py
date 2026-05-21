"""
scrape_gw_stores.py

Discovers all official GW/Warhammer stores in US, UK, Germany, Australia, and France
using the Google Places Text Search API, then pulls review_count and rating for each.

Saves to data/stores.json with this structure per store:
  name, city, country, place_id, review_count, rating, snapshot_date

Requires: GOOGLE_PLACES_API_KEY in .env or environment.
Usage:
    source venv/bin/activate
    python3 scripts/scrape_gw_stores.py

Outputs:
    data/stores.json
"""

import os, json, time, sys
import requests
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
OUT = Path("data/stores.json")
SNAPSHOT_DATE = str(date.today())

# ── Places API endpoints ───────────────────────────────────────────────────────
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL     = "https://maps.googleapis.com/maps/api/place/details/json"

# ── Coverage: cities to search per country ────────────────────────────────────
# We run multiple city-level queries to ensure complete national coverage.
# GW stores are named "Warhammer" or "Warhammer — [suburb]".
SEARCHES = {
    "UK": [
        "Warhammer store London UK",
        "Warhammer store Birmingham UK",
        "Warhammer store Manchester UK",
        "Warhammer store Edinburgh UK",
        "Warhammer store Bristol UK",
        "Warhammer store Leeds UK",
        "Warhammer store Sheffield UK",
        "Warhammer store Liverpool UK",
        "Warhammer store Newcastle UK",
        "Warhammer store Cardiff UK",
        "Warhammer store Nottingham UK",
        "Warhammer store Southampton UK",
        "Warhammer store Brighton UK",
        "Warhammer store Oxford UK",
        "Warhammer store Cambridge UK",
        "Warhammer store Coventry UK",
        "Warhammer store Leicester UK",
        "Warhammer store Plymouth UK",
        "Warhammer store Reading UK",
        "Warhammer store Glasgow UK",
    ],
    "US": [
        "Warhammer store New York USA",
        "Warhammer store Los Angeles USA",
        "Warhammer store Chicago USA",
        "Warhammer store Houston USA",
        "Warhammer store Phoenix USA",
        "Warhammer store Philadelphia USA",
        "Warhammer store San Antonio USA",
        "Warhammer store San Diego USA",
        "Warhammer store Dallas USA",
        "Warhammer store San Jose USA",
        "Warhammer store Austin USA",
        "Warhammer store Seattle USA",
        "Warhammer store Denver USA",
        "Warhammer store Boston USA",
        "Warhammer store Atlanta USA",
        "Warhammer store Miami USA",
        "Warhammer store Minneapolis USA",
        "Warhammer store Portland Oregon USA",
        "Warhammer store Las Vegas USA",
        "Warhammer store Columbus Ohio USA",
    ],
    "Germany": [
        "Warhammer store Berlin Germany",
        "Warhammer store Hamburg Germany",
        "Warhammer store Munich Germany",
        "Warhammer store Cologne Germany",
        "Warhammer store Frankfurt Germany",
        "Warhammer store Stuttgart Germany",
        "Warhammer store Düsseldorf Germany",
        "Warhammer store Leipzig Germany",
        "Warhammer store Dortmund Germany",
        "Warhammer store Essen Germany",
        "Warhammer store Bremen Germany",
        "Warhammer store Dresden Germany",
        "Warhammer store Hannover Germany",
        "Warhammer store Nuremberg Germany",
    ],
    "Australia": [
        "Warhammer store Sydney Australia",
        "Warhammer store Melbourne Australia",
        "Warhammer store Brisbane Australia",
        "Warhammer store Perth Australia",
        "Warhammer store Adelaide Australia",
        "Warhammer store Canberra Australia",
        "Warhammer store Hobart Australia",
        "Warhammer store Gold Coast Australia",
        "Warhammer store Newcastle Australia",
        "Warhammer store Wollongong Australia",
    ],
    "France": [
        "Warhammer store Paris France",
        "Warhammer store Lyon France",
        "Warhammer store Marseille France",
        "Warhammer store Toulouse France",
        "Warhammer store Bordeaux France",
        "Warhammer store Lille France",
        "Warhammer store Nantes France",
        "Warhammer store Strasbourg France",
        "Warhammer store Nice France",
        "Warhammer store Rennes France",
    ],
}


def is_official_gw_store(name: str) -> bool:
    """
    Returns True if the place name looks like an official GW/Warhammer store.
    Official stores are named exactly 'Warhammer' or 'Warhammer — [something]'
    or 'Warhammer - [something]'. Filters out indie retailers and hobby shops.
    """
    n = name.strip()
    if n.lower() == "warhammer":
        return True
    if n.lower().startswith("warhammer —") or n.lower().startswith("warhammer -"):
        return True
    # Some stores are listed as "Warhammer [City]" without a dash
    if n.lower().startswith("warhammer ") and "40" not in n.lower() and "age" not in n.lower():
        return True
    return False


def text_search(query: str) -> list[dict]:
    """Run a Places Text Search and return all pages of results."""
    results = []
    params = {
        "query": query,
        "type":  "store",
        "key":   PLACES_API_KEY,
    }
    while True:
        resp = requests.get(TEXT_SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            print(f"  [WARN] Places API status={status} for query={query!r}")
            break
        results.extend(data.get("results", []))
        next_token = data.get("next_page_token")
        if not next_token:
            break
        # API requires a short delay before next_page_token is valid
        time.sleep(2.5)
        params = {"pagetoken": next_token, "key": PLACES_API_KEY}
    return results


def get_place_details(place_id: str) -> dict:
    """Fetch full details (review count, rating) for a Place ID."""
    params = {
        "place_id": place_id,
        "fields":   "name,rating,user_ratings_total,formatted_address",
        "key":      PLACES_API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        return {}
    return data.get("result", {})


def extract_city(formatted_address: str, country: str) -> str:
    """Best-effort city extraction from formatted_address."""
    if not formatted_address:
        return ""
    parts = [p.strip() for p in formatted_address.split(",")]
    # Address format: street, city, postcode/state, country
    # Try second-to-last before the country name
    if len(parts) >= 3:
        return parts[-3] if len(parts) >= 3 else parts[0]
    return parts[0] if parts else ""


def main():
    if not PLACES_API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY not set in .env or environment.")
        print("Add it to .env:  GOOGLE_PLACES_API_KEY=your_key_here")
        sys.exit(1)

    # Load existing stores to allow incremental runs without re-fetching known place_ids
    existing: dict[str, dict] = {}
    if OUT.exists():
        try:
            existing_list = json.loads(OUT.read_text())
            existing = {s["place_id"]: s for s in existing_list if "place_id" in s}
            print(f"Loaded {len(existing)} existing stores from {OUT}")
        except Exception:
            pass

    discovered: dict[str, dict] = {}  # place_id → store record

    for country, queries in SEARCHES.items():
        print(f"\n── {country} ({len(queries)} queries) ────────────────────────────")
        for query in queries:
            print(f"  Searching: {query!r}")
            try:
                places = text_search(query)
            except Exception as e:
                print(f"  [ERROR] {e}")
                time.sleep(2)
                continue
            for place in places:
                name = place.get("name", "")
                pid  = place.get("place_id", "")
                if not pid or not is_official_gw_store(name):
                    continue
                if pid in discovered:
                    continue
                addr = place.get("formatted_address", "")
                city = extract_city(addr, country)
                discovered[pid] = {
                    "name":          name,
                    "city":          city,
                    "country":       country,
                    "place_id":      pid,
                    "review_count":  place.get("user_ratings_total", 0),
                    "rating":        place.get("rating", None),
                    "snapshot_date": SNAPSHOT_DATE,
                }
            time.sleep(0.3)  # courtesy pause between queries

    print(f"\n── Enriching {len(discovered)} discovered stores with Place Details ──")
    stores_out = []
    ok_count = 0
    err_count = 0

    for pid, store in discovered.items():
        # Use existing data if we already have it and it was scraped today
        if pid in existing and existing[pid].get("snapshot_date") == SNAPSHOT_DATE:
            stores_out.append(existing[pid])
            ok_count += 1
            continue
        try:
            details = get_place_details(pid)
            if details:
                addr = details.get("formatted_address", "")
                store["city"]         = extract_city(addr, store["country"]) or store["city"]
                store["review_count"] = details.get("user_ratings_total", store["review_count"])
                store["rating"]       = details.get("rating", store["rating"])
            stores_out.append(store)
            ok_count += 1
        except Exception as e:
            print(f"  [ERROR] place_id={pid} name={store['name']!r}: {e}")
            store["error"] = str(e)
            stores_out.append(store)
            err_count += 1
        time.sleep(0.25)

    # Sort: by country then review_count desc
    stores_out.sort(key=lambda s: (s["country"], -(s.get("review_count") or 0)))

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(stores_out, indent=2, ensure_ascii=False))

    print(f"\n── Summary ──────────────────────────────────────────────────────────")
    print(f"  Total stores saved:  {len(stores_out)}")
    print(f"  Successfully pulled: {ok_count}")
    print(f"  Errors:              {err_count}")
    by_country = {}
    for s in stores_out:
        by_country.setdefault(s["country"], 0)
        by_country[s["country"]] += 1
    for c, n in sorted(by_country.items()):
        print(f"    {c}: {n} stores")
    print(f"\n  Saved to: {OUT}")
    if err_count:
        print(f"\n  ⚠ {err_count} stores had errors — check place_id values manually.")


if __name__ == "__main__":
    main()
