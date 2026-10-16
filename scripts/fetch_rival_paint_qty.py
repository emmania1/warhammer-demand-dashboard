"""
fetch_rival_paint_qty.py
────────────────────────
Unit counts for rival paint ranges — Army Painter (Warpaints Fanatic, classic Warpaints)
and Vallejo (Game Color, Xpress Color, Model Color) — at the unit-count stores that
stock them (config/rival_paint_stores.csv), read the same way as Tone Pro and Base/Layer:

  daily stores   (Firestorm, The Outpost, Element Games, Loaded Dice, Beanie, Battle City)
                 the store's own category / collection listing pages, which print a
                 count per product → every listed pot, every day
  weekly stores  (product-page stores) once a week on the store's own weekday: up to
                 10 pots per brand, fixed once chosen (data/rival_paint_plan.csv), read
                 from each product page's stock figure (Shopify inventory_quantity matched
                 to the product's own variant id; Lightspeed ?format=json stock.level)

Same etiquette as the panel: robots.txt per URL, ~2-3s apart, one request at a time
per store, identifying User-Agent; 401/403/429/challenge → recorded as blocked, skipped.

WHAT THIS MEASURES: units each store's system shows on hand. Not sales.
Output: data/rival_paint_qty.csv — one row per (date, store, paint)

Usage:
  python scripts/fetch_rival_paint_qty.py            # daily stores + today's weekly stores
  python scripts/fetch_rival_paint_qty.py --all      # every store now (baseline read)
  python scripts/fetch_rival_paint_qty.py --dry-run  # list what would be read
"""

import re, argparse, threading, importlib.util, concurrent.futures as cf
from pathlib import Path
from datetime import date, datetime, timezone

import pandas as pd

ROOT   = Path(__file__).parent.parent
CONFIG = ROOT / "config" / "rival_paint_stores.csv"
OUT    = ROOT / "data" / "rival_paint_qty.csv"
PLAN   = ROOT / "data" / "rival_paint_plan.csv"
today  = str(date.today())
PER_BRAND = 10                                   # pots per brand at weekly stores
_plan_lock = threading.Lock()

def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

panel = _load("panel", "fetch_indie_paint_panel.py")
pages = _load("pages", "fetch_page_qty_weekly.py")
disc  = _load("disc", "discover_rival_paint_targets.py")

BRAND_OF = {"Army Painter Fanatic": "Army Painter", "Army Painter Warpaints": "Army Painter",
            "Vallejo Game Color": "Vallejo", "Vallejo Xpress Color": "Vallejo", "Vallejo Model Color": "Vallejo"}
LINE_ORDER = list(BRAND_OF)                      # preference within a brand when sampling


def canon(line: str, title: str) -> str:
    """'Warpaints Fanatic: Pure Red' → 'Army Painter Fanatic: Pure Red' (stable per store)."""
    t = re.sub(r"(?i)the army painter|army painter|warpaints?|fanatic|vallejo|game colou?r|model colou?r|xpress colou?r|"
               r"intense|\b(?:VAL ?)?7[02][.\- ]?\d{3}\b|\bWP\d{4}\b|\d+ ?ml|\(\s*\)|[:\-–|]", " ", title)
    return f"{line}: {' '.join(t.split()).strip(' ()').title()}"


def listing(f, s) -> list[dict]:
    """All rival single pots the store lists in its rival targets, with counts where the listing has them."""
    cfg = {"targets": s["targets"], "qty_html": s.get("qty_html", "")}
    raw = panel.ADAPTERS[s["platform"]](f, cfg)
    out, seen = [], set()
    for it in raw:
        line = disc.classify(it["title"], "", it.get("sku", ""))
        if not line:
            continue
        p = canon(line, it["title"])
        if p in seen:
            continue
        seen.add(p)
        url = it["url"] if it["url"].startswith("http") else f"{f.base}/{it['url'].lstrip('/')}"
        out.append({**it, "url": url, "line": line, "paint": p})
    return out


def sample(items: list[dict], store_id: str) -> list[dict]:
    """Up to PER_BRAND pots per brand, evenly spread across the store's range; sticky week to week."""
    with _plan_lock:
        return _sample(items, store_id)


def _sample(items: list[dict], store_id: str) -> list[dict]:
    plan = pd.read_csv(PLAN, dtype=str, keep_default_na=False) if PLAN.exists() else pd.DataFrame(columns=["store_id", "paint"])
    keep = set(plan[plan["store_id"] == store_id]["paint"])
    by = {it["paint"]: it for it in items}
    chosen = [by[p] for p in keep if p in by]
    for brand in ("Army Painter", "Vallejo"):
        have = [c for c in chosen if BRAND_OF[c["line"]] == brand]
        need = PER_BRAND - len(have)
        if need <= 0:
            continue
        for line in [l for l in LINE_ORDER if BRAND_OF[l] == brand]:
            pool = sorted([it for it in items if it["line"] == line and it not in chosen], key=lambda x: x["paint"])
            if not pool or need <= 0:
                continue
            step = max(1, len(pool) // need)
            pick = pool[::step][:need]
            chosen += pick; need -= len(pick)
    new = pd.DataFrame([{"store_id": store_id, "paint": c["paint"], "line": c["line"], "url": c["url"],
                         "chosen_on": today} for c in chosen])
    plan = pd.concat([plan[plan["store_id"] != store_id], new], ignore_index=True)
    plan.to_csv(PLAN, index=False)
    return chosen


def run_store(s, read_type: str) -> list[dict]:
    f = panel.Fetcher(f"https://{s['domain']}")
    rows, status = [], "ok"
    try:
        if f.rules is None:
            raise panel.Blocked("robots.txt 401/403")
        items = listing(f, s)
        if s["cadence"] == "weekly":
            for it in sample(items, s["store_id"]):
                q, note = pages.read_qty(f, s["platform"], {"url": it["url"], "variant_id": it.get("variant_id", ""),
                                                            "handle": it.get("handle", it["url"]), "multi": False})
                rows.append((it, "" if q is None else str(q), "false", "", note))
        else:
            for it in items:
                rows.append((it, it["qty"], it["qty_floor"] or "false", it.get("on_order", ""), "" if it["qty"] != "" else "no count on listing"))
    except panel.Blocked as e:
        status = f"blocked: {e}"
    except Exception as e:
        status = f"error: {type(e).__name__}: {str(e)[:60]}"
    out = [{"date": today, "store_id": s["store_id"], "country": s["country"], "brand": BRAND_OF[it["line"]],
            "line": it["line"], "paint": it["paint"], "qty": q, "qty_is_floor": fl, "on_order": oo,
            "status": it["status"], "note": note, "url": it["url"], "read_type": read_type}
           for it, q, fl, oo, note in rows]
    got = sum(1 for r in out if r["qty"] != "")
    print(f"  {s['store_id']:28} {s['cadence']:6} {status:9} {got:4}/{len(out):4} counts · {f.n} requests")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="read every store now (baseline)")
    ap.add_argument("--only", help="comma-separated store_ids")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    panel.DELAY_S = 2.5
    cfg = pd.read_csv(CONFIG, dtype=str, keep_default_na=False)
    cfg = cfg[cfg["active"].str.lower() == "true"]
    if args.only:
        cfg = cfg[cfg["store_id"].isin(args.only.split(","))]
    wd = datetime.now(timezone.utc).weekday()
    jobs = [(s, "daily" if s["cadence"] == "daily" else "weekly") for _, s in cfg.iterrows()
            if args.all or args.only or s["cadence"] == "daily" or int(s["weekday"]) == wd]
    print(f"Rival paint counts — {today} (weekday {wd}) — {len(jobs)} stores")
    if args.dry_run or not jobs:
        for s, t in jobs:
            print(f"  {s['store_id']:28} {t}")
        return
    with cf.ThreadPoolExecutor(4) as ex:
        rows = [r for rs in ex.map(lambda j: run_store(*j), jobs) for r in rs]
    new = pd.DataFrame(rows)
    if new.empty:
        return
    if OUT.exists():
        old = pd.read_csv(OUT, dtype=str, keep_default_na=False)
        old = old[~((old["date"] == today) & old["store_id"].isin(new["store_id"].unique()))]
        new = pd.concat([old, new.astype(str)], ignore_index=True)
    new.to_csv(OUT, index=False)
    print(f"✓ {len(rows)} rows → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
