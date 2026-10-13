"""
discover_indie_shopify.py
─────────────────────────
Finds candidate stores for the independent online availability panel by turning
GW store-finder stockist names into likely web addresses ("Game Kastle" →
gamekastle.com) and keeping the ones that are Shopify shops selling GW paints.
On 2026-10-13 this found 134 such shops from the ~1,900 US/UK/CA stockists listed
as ranging Warhammer Pro — far more than web search did. Method write-up:
docs/indie_panel_discovery.md

Steps per stockist:
  1. name → slug (drop LLC/Inc/Ltd/the/&, location suffixes after " - ", non-letters)
  2. try slug + country TLD (.com for US; .co.uk/.com for GB; .ca/.com for CA)
  3. robots.txt, then /collections.json — keep Shopify sites with a Citadel /
     Warhammer Colour / Tone Pro collection                    (≤2 requests/host)
  4. for keepers: /meta.json (the shop's own city/country) to confirm it is the
     same business, then a trial read of the paint collections through the panel
     fetcher's matcher, counting Base / Layer / Tone Pro paints   (≤~8 requests)

Output: data/indie_panel_candidates.csv — ranked; review it, then copy chosen rows
into config/indie_paint_panel.csv (platform=shopify, targets=suggested_targets).
Not part of the daily pipeline — run by hand when expanding the panel.

Usage:
  python scripts/discover_indie_shopify.py                    # US,GB,CA, Pro-range stockists
  python scripts/discover_indie_shopify.py --countries US --all-ranges
"""

import re, json, argparse, unicodedata, importlib.util, concurrent.futures as cf
from pathlib import Path

import requests
import pandas as pd

ROOT = Path(__file__).parent.parent
OUT  = ROOT / "data" / "indie_panel_candidates.csv"
SF_URL = "https://www.warhammer.com/api/storefinder"

_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "fetch_indie_paint_panel.py")
panel = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(panel)

TLDS = {"US": [".com"], "GB": [".co.uk", ".com"], "CA": [".ca", ".com"]}
GW_COLL = re.compile(r"citadel|warhammer[-_ ]?(colou?r|pro|paint)|tone[-_ ]?pro|games[-_ ]?workshop[-_ ]?(paint|hobby)|gw[-_ ]paint", re.I)
GOOD = re.compile(r"base|layer|tone|warhammer-pro|all-citadel|citadel-paints?$|citadel-colou?r|^citadel$|shop-all|paints?-and|paint-hobby", re.I)
BAD = re.compile(r"air|spray|contrast|shade|dry|technical|brush|tool|case|basing|bases|dice|primer|accessor|set|bundle|preorder|pre-order|sale", re.I)


def ascii_lower(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def slug(name: str) -> str:
    n = ascii_lower(name).split(" - ")[0]
    n = re.sub(r"\b(llc|inc|ltd|limited|co|the|and)\b|&|'", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


def pick_targets(handles: list[str]) -> list[str]:
    good = [h for h in handles if GOOD.search(h) and not BAD.search(h)]
    specific = [h for h in good if re.search(r"base|layer|tone|pro", h)]
    return (specific or good or handles)[:4]


def shopify_gw_collections(host: str) -> list[str] | None:
    """≤2 requests: robots.txt + collections.json. None = not a Shopify GW stockist."""
    rules = panel.load_robots(f"https://{host}")
    url = f"https://{host}/collections.json?limit=250"
    if rules is None or not panel.robots_allows(rules, url):
        return None
    try:
        r = requests.get(url, headers=panel.HEADERS, timeout=10)
    except requests.RequestException:
        return None
    if r.status_code != 200 or '"collections"' not in r.text[:300]:
        return None
    hs = [c["handle"] for c in r.json().get("collections", []) if GW_COLL.search(c["handle"] + " " + c.get("title", ""))]
    return hs or None


def qualify(host: str, handles: list[str], canon) -> dict:
    f = panel.Fetcher(f"https://{host}")
    rec = {"domain": host, "suggested_targets": "|".join(pick_targets(handles))}
    try:
        m = f.get(f"https://{host}/meta.json")
        if m is not None and m.status_code == 200:
            j = m.json()
            rec.update(shop_name=j.get("name", ""), shop_city=j.get("city", ""),
                       shop_country=j.get("country", ""), currency=j.get("currency", ""))
        items = panel.adapt_shopify(f, {"targets": rec["suggested_targets"], "qty_html": ""})
        hits = {}
        for it in items:
            x = panel.match_paint(it["title"], canon)
            if x:
                hits[x[1]] = x[0]
        rec.update(base=sum(v == "Base" for v in hits.values()), layer=sum(v == "Layer" for v in hits.values()),
                   tone_pro=sum(v == "Tone Pro" for v in hits.values()), status="ok")
    except panel.Blocked as e:
        rec["status"] = f"blocked: {e}"
    except Exception as e:
        rec["status"] = f"error: {type(e).__name__}"
    rec["requests"] = f.n
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", default="US,GB,CA")
    ap.add_argument("--all-ranges", action="store_true", help="include stockists without the Warhammer Pro range")
    ap.add_argument("--workers", type=int, default=6, help="parallel hosts in the cheap step-3 scan")
    args = ap.parse_args()
    countries = args.countries.split(",")

    stores = requests.get(SF_URL, headers=panel.HEADERS, timeout=120).json()
    pool = [s for s in stores if not s.get("isWarHammerStore") and s.get("countryCode") in countries
            and (args.all_ranges or str(s.get("stockRange", "")).endswith("_T150"))]
    existing = set(pd.read_csv(panel.CONFIG, dtype=str)["domain"].str.replace("www.", "", regex=False))

    guesses = {}
    for s in pool:
        sl = slug(s["name"])
        if len(sl) < 5:
            continue
        for tld in TLDS.get(s["countryCode"], [".com"]):
            host = sl + tld
            if host not in existing:
                guesses.setdefault(host, s)
    print(f"{len(pool)} stockists → {len(guesses)} candidate domains")

    keep = {}
    with cf.ThreadPoolExecutor(args.workers) as ex:
        for host, hs in zip(guesses, ex.map(shopify_gw_collections, guesses)):
            if hs:
                keep[host] = hs
    print(f"{len(keep)} Shopify sites with GW paint collections; qualifying one at a time…")

    panel.DELAY_S, panel.MAX_PAGES = 1.2, 3
    canon = panel.load_canon()
    rows = []
    for host, hs in keep.items():
        sf = guesses[host]
        rec = qualify(host, hs, canon)
        same_city = ascii_lower(rec.get("shop_city", ""))[:5] == ascii_lower(sf.get("city", ""))[:5]
        rec.update(finder_name=sf["name"], finder_city=sf.get("city", ""), finder_country=sf["countryCode"],
                   stock_range=sf.get("stockRange", ""),
                   location_check=("city match" if same_city else
                                   "country match" if rec.get("shop_country") == sf["countryCode"] else
                                   "no meta" if not rec.get("shop_city") else "MISMATCH"))
        rows.append(rec)
        print(f"  {host:34} {rec['location_check']:13} base={rec.get('base', 0):3} layer={rec.get('layer', 0):3} tone_pro={rec.get('tone_pro', 0)}")

    df = pd.DataFrame(rows)
    if df.empty:
        print("No candidates."); return
    df["base_layer"] = df["base"].fillna(0) + df["layer"].fillna(0)
    df = df.sort_values(["location_check", "base_layer"], ascending=[True, False])
    df.to_csv(OUT, index=False)
    print(f"\n✓ {len(df)} candidates → {OUT.relative_to(ROOT)}  "
          f"({int(((df.base_layer >= 60) & (df.location_check != 'MISMATCH')).sum())} with ≥60 Base/Layer and a location match)")


if __name__ == "__main__":
    main()
