"""
fetch_page_qty_weekly.py
────────────────────────
Unit counts read from individual product pages (weekly; daily on a small subset during the Tone Pro launch window) at independent stores whose
pages carry a per-product stock figure (config/page_qty_stores.csv):

  shopify     the product page embeds the variant's inventory quantity
              (inventory_quantity / data-stock), matched to that product's own
              variant id so counts from "recommended products" blocks are ignored
  lightspeed  the product's public JSON view (?format=json) → stock.level

What is read per store, once a week:
  mode=sample  Tone Pro tone 3 of each of the 30 colours (≤30 pages) + 10 fixed
               Base/Layer comparison paints
  mode=all     every Tone Pro paint the store lists (≤150) + the 10 comparison paints
Only paints the store actually lists are read. Each store has its own weekday
(column `weekday`, 0=Mon) so the load is spread across the week; the daily GitHub
job calls this script and it reads only today's stores (or --all).

Cost: 1 robots.txt + 1–6 product-list requests + 1 page per paint read, ~3s apart,
one request at a time per store.

WHAT THIS MEASURES: units the store's system shows on hand for each paint on the
day read. Pre-launch, counts on pre-order items are allocations / pre-orders.
Negative = orders taken beyond stock. Not sales.

Output: data/page_qty_weekly.csv — one row per (date, store, paint)

Usage:
  python scripts/fetch_page_qty_weekly.py              # today's stores
  python scripts/fetch_page_qty_weekly.py --all        # every store now
  python scripts/fetch_page_qty_weekly.py --verify domain1,domain2 --targets h1|h2;h3   (one-off check)
"""

import os, re, sys, argparse, importlib.util, concurrent.futures as cf
from pathlib import Path
from datetime import date, datetime, timezone

import pandas as pd

ROOT   = Path(__file__).parent.parent
CONFIG = ROOT / "config" / "page_qty_stores.csv"
OUT    = ROOT / "data" / "page_qty_weekly.csv"
PLAN   = ROOT / "data" / "page_qty_plan.csv"          # where each paint's page is, cached from the last listing

# Tone Pro launch window: between these dates (inclusive), and only when the env var
# LAUNCH_DAILY=true (repo variable LAUNCH_DAILY_ENABLED), every store is also read
# DAILY on a small fixed subset — enough to date each delivery and size it per pot —
# using cached page locations (≈13 requests/store/day). Outside it: weekly only.
LAUNCH_WINDOW = ("2026-10-22", "2026-10-31")
DAILY_TP = [f"Tone Pro: {c} 3" for c in ("Blackstone Void", "Bloodtoof Red", "Carmine Blades", "Ultramar Blue",
            "Khemri Sands", "Lustria Green", "Eye of Terror", "Necrolith Bone", "Megaboss Yellow", "Shalaxi Violet")]
DAILY_CMP = ["Base: Abaddon Black", "Layer: Evil Sunz Scarlet"]

_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "fetch_indie_paint_panel.py")
panel = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(panel)

DELAY_S = 3.0
COMPARISON = ["Base: Abaddon Black", "Base: Mephiston Red", "Base: Leadbelcher", "Base: Retributor Armour",
              "Base: Macragge Blue", "Layer: Evil Sunz Scarlet", "Layer: Ushabti Bone",
              "Layer: Administratum Grey", "Layer: Wild Rider Red", "Layer: Stormhost Silver"]
today = str(date.today())


# ── Product lists (where each paint's page is) ────────────────────────────────

def shopify_listing(f, targets: str, canon) -> dict:
    """paint → {url, variant_id} from the store's own collection products.json."""
    out = {}
    for it in panel.adapt_shopify(f, {"targets": targets, "qty_html": ""}):
        m = panel.match_paint(it["title"], canon)
        if m and m[1] not in out and it.get("variant_id"):
            out[m[1]] = {"url": it["url"], "variant_id": it["variant_id"], "handle": it["handle"]}
    per_handle = {}
    for v in out.values():
        per_handle[v["handle"]] = per_handle.get(v["handle"], 0) + 1
    for v in out.values():
        v["multi"] = per_handle[v["handle"]] > 1
    return out


def lightspeed_listing(f, targets: str, canon) -> dict:
    out = {}
    for it in panel.adapt_lightspeed(f, {"targets": targets}):
        m = panel.match_paint(it["title"], canon)
        if m and m[1] not in out and it.get("url"):
            u = it["url"] if it["url"].startswith("http") else f"{f.base}/{it['url'].lstrip('/')}"
            out[m[1]] = {"url": u, "variant_id": "", "handle": ""}
    return out


def choose(listing: dict, mode: str) -> list[str]:
    tp = sorted(p for p in listing if p.startswith("Tone Pro:"))
    if mode != "all":
        tp = [p for p in tp if p.endswith(" 3")]
    return tp + [p for p in COMPARISON if p in listing]


# ── Read one page ─────────────────────────────────────────────────────────────

def read_qty(f, platform: str, item: dict) -> tuple[int | None, str]:
    if platform == "lightspeed":
        r = f.get(item["url"].split("?")[0] + "?format=json")
        if r is None:
            return None, "robots disallow"
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        lvl = ((r.json().get("product") or {}).get("stock") or {}).get("level")
        return (int(lvl), "") if lvl is not None else (None, "no stock level")
    # Shopify: a multi-colour product shares one page — read it once per handle
    cache = f.__dict__.setdefault("_page_cache", {})
    if item["handle"] not in cache:
        r = f.get(item["url"])
        cache[item["handle"]] = r.text if (r is not None and r.status_code == 200) else None
    page = cache[item["handle"]]
    if page is None:
        return None, "page unavailable"
    q = panel.qty_per_variant(page, {item["variant_id"]}).get(item["variant_id"])
    if q is not None:
        return q, ""
    # Single-paint page: the visible "N in stock" / "Only N left" text can only be this product.
    # Taken from the main product area (before the first recommendations block).
    if not item.get("multi"):
        main = re.split(r"(?i)you may also like|related products|recommended|recently viewed|frequently bought", page)[0]
        m = VISIBLE_QTY.search(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", main))))
        if m:
            return int(m.group(1) or m.group(2)), "visible text"
    return None, "quantity not on page"


VISIBLE_QTY = re.compile(r"(?i)\b(\d{1,4})\s*(?:in stock|left in stock|units? left|available)\b|only\s+(\d{1,3})\s+left")


def load_plan(store_id: str) -> dict:
    if not PLAN.exists():
        return {}
    p = pd.read_csv(PLAN, dtype=str, keep_default_na=False)
    p = p[p["store_id"] == store_id]
    return {r["paint"]: {"url": r["url"], "variant_id": r["variant_id"], "handle": r["handle"],
                         "multi": r["multi"] == "True"} for _, r in p.iterrows()}


def save_plan(store_id: str, listing: dict) -> None:
    new = pd.DataFrame([{"store_id": store_id, "paint": k, "url": v["url"], "variant_id": v["variant_id"],
                         "handle": v["handle"], "multi": str(v.get("multi", False)), "listed_on": today}
                        for k, v in listing.items()])
    if PLAN.exists():
        old = pd.read_csv(PLAN, dtype=str, keep_default_na=False)
        new = pd.concat([old[old["store_id"] != store_id], new.astype(str)], ignore_index=True)
    new.to_csv(PLAN, index=False)


def run_store(s, canon, read_type: str = "weekly") -> list[dict]:
    f = panel.Fetcher(f"https://{s['domain']}")
    rows = []
    try:
        lister = lightspeed_listing if s["platform"] == "lightspeed" else shopify_listing
        if read_type == "weekly":
            listing = lister(f, s["targets"], canon)
            save_plan(s["store_id"], listing)
            paints = choose(listing, s["mode"])
        else:                                   # launch-window daily subset from cached locations
            listing = load_plan(s["store_id"])
            if not any(p.startswith("Tone Pro:") for p in listing):
                listing = lister(f, s["targets"], canon)      # store may have just listed Tone Pro
                save_plan(s["store_id"], listing)
            paints = [p for p in DAILY_TP + DAILY_CMP if p in listing]
        for paint in paints:
            q, note = read_qty(f, s["platform"], listing[paint])
            rows.append({"date": today, "store_id": s["store_id"], "country": s["country"], "paint": paint,
                         "line": paint.split(":")[0], "qty": "" if q is None else q, "note": note,
                         "url": listing[paint]["url"], "read_type": read_type})
        status = "ok"
    except panel.Blocked as e:
        status = f"blocked: {e}"
    except Exception as e:
        status = f"error: {type(e).__name__}"
    got = sum(1 for r in rows if r["qty"] != "")
    print(f"  {s['store_id']:28} {read_type:6} {status:9} {got:3}/{len(rows):3} counts · {f.n} requests")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="read every store now, not just today's")
    ap.add_argument("--only", help="comma-separated store_ids")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    panel.DELAY_S = DELAY_S
    cfg = pd.read_csv(CONFIG, dtype=str, keep_default_na=False)
    cfg = cfg[cfg["active"].str.lower() == "true"]
    wd = datetime.now(timezone.utc).weekday()
    in_window = (LAUNCH_WINDOW[0] <= today <= LAUNCH_WINDOW[1]
                 and os.environ.get("LAUNCH_DAILY", "").lower() == "true")
    if args.only:
        cfg = cfg[cfg["store_id"].isin(args.only.split(","))]
        jobs = [(s, "weekly") for _, s in cfg.iterrows()]
    elif args.all:
        jobs = [(s, "weekly") for _, s in cfg.iterrows()]
    else:
        jobs = [(s, "weekly" if int(s["weekday"]) == wd else "daily") for _, s in cfg.iterrows()
                if int(s["weekday"]) == wd or in_window]
    n_w = sum(1 for _, t in jobs if t == "weekly")
    print(f"Product-page counts — {today} (weekday {wd}{', launch window' if in_window else ''}) — "
          f"{n_w} weekly + {len(jobs) - n_w} daily-subset stores")
    if args.dry_run or not jobs:
        return
    canon = panel.load_canon()
    with cf.ThreadPoolExecutor(args.workers) as ex:
        rows = [r for rs in ex.map(lambda j: run_store(j[0], canon, j[1]), jobs) for r in rs]
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
