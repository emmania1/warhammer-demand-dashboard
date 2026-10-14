"""
fetch_us_tone_pro_qty.py
────────────────────────
Weekly US unit counts for Tone Pro at a few panel stores whose Shopify product
pages embed the variant's inventory quantity (products.json never includes it).

Reads ONLY the Tone Pro product pages each store already lists, taken from the
latest panel snapshot (data/indie_paint_panel_daily.csv) — no discovery requests.
The quantity is taken only when it sits next to that product's own variant id, so
counts from "recommended products" blocks on the same page are ignored.

Stores (US_STORES below): Armada Games, The Haunted Game Cafe, Gamers Grove —
each verified 2026-10-14 to embed inventory_quantity for the page's own variant.

Request budget per weekly run: 1 robots.txt per store + 1 page per listed Tone Pro
SKU (max 150 per store). Pages ~3s apart, one store at a time.

WHAT THIS MEASURES: units the store's system shows on hand for each Tone Pro paint
on the day of the run. Negative numbers mean orders taken beyond stock (pre-orders /
backorders). Not sales, and only 3 US stores.

Output: data/us_tone_pro_qty_weekly.csv — one row per (date, store, paint)
"""

import re, sys, argparse, importlib.util
from pathlib import Path
from datetime import date

import pandas as pd

ROOT  = Path(__file__).parent.parent
PANEL = ROOT / "data" / "indie_paint_panel_daily.csv"
OUT   = ROOT / "data" / "us_tone_pro_qty_weekly.csv"

_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "fetch_indie_paint_panel.py")
panel = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(panel)

US_STORES = ["armada_games", "the_haunted_game_cafe", "gamers_grove"]
DELAY_S   = 3.0
today     = str(date.today())


def plan(stores=US_STORES) -> pd.DataFrame:
    d = pd.read_csv(PANEL, dtype=str, keep_default_na=False)
    d = d[(d["date"] == d["date"].max()) & d["store_id"].isin(stores) & (d["line"] == "Tone Pro")]
    return d[["store_id", "paint", "url", "variant_id", "status"]]


def page_qty(html: str, variant_id: str) -> int | None:
    """inventory_quantity belonging to this variant: the nearest variant id in the
    300 characters before the number must be ours."""
    for m in re.finditer(r'"?inventory_?[qQ]uantity"?\s*[:=]\s*(-?\d+)', html):
        ids = re.findall(r"\b\d{11,16}\b", html[max(0, m.start() - 300):m.start()])
        if ids and ids[-1] == variant_id:
            return int(m.group(1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the request plan only")
    ap.add_argument("--limit", type=int, default=0, help="max pages per store (testing)")
    args = ap.parse_args()

    todo = plan()
    per_store = todo.groupby("store_id").size().reindex(US_STORES, fill_value=0)
    n_req = int(per_store.clip(upper=args.limit or 10**6).sum() + (per_store > 0).sum())
    print(f"US Tone Pro quantities — {today}")
    for sid, n in per_store.items():
        print(f"  {sid:24} {n:3} Tone Pro pages")
    print(f"  total requests this run: {n_req}")
    if args.dry_run or todo.empty:
        return

    panel.DELAY_S = DELAY_S
    rows = []
    for sid, g in todo.groupby("store_id"):
        if args.limit:
            g = g.head(args.limit)
        f = panel.Fetcher(f"https://{g['url'].iloc[0].split('/')[2]}")
        for _, r in g.iterrows():
            qty, note = None, ""
            if not r["variant_id"]:
                note = "no variant id in panel data"
            else:
                try:
                    resp = f.get(r["url"])
                    if resp is None:
                        note = "robots disallow"
                    elif resp.status_code != 200:
                        note = f"HTTP {resp.status_code}"
                    else:
                        qty = page_qty(resp.text, r["variant_id"])
                        note = "" if qty is not None else "quantity not on page"
                except panel.Blocked as e:
                    note = f"blocked: {e}"
                    rows.append({"date": today, "store_id": sid, "paint": r["paint"], "qty": "",
                                 "panel_status": r["status"], "note": note, "url": r["url"]})
                    break                                    # stop this store
            rows.append({"date": today, "store_id": sid, "paint": r["paint"],
                         "qty": "" if qty is None else qty, "panel_status": r["status"],
                         "note": note, "url": r["url"]})
        got = sum(1 for x in rows if x["store_id"] == sid and x["qty"] != "")
        print(f"  {sid:24} {got}/{len(g)} quantities read, {f.n} requests")

    new = pd.DataFrame(rows)
    if OUT.exists():
        ex = pd.read_csv(OUT, dtype=str, keep_default_na=False)
        ex = ex[~((ex["date"] == today) & ex["store_id"].isin(new["store_id"].unique()))]
        new = pd.concat([ex, new.astype(str)], ignore_index=True)
    new.to_csv(OUT, index=False)
    print(f"✓ {len(rows)} rows → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
