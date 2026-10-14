"""
scan_variant_qty_stores.py
──────────────────────────
Finds Shopify stockists that list GW paints as ONE product with every colour as a
variant (e.g. "Citadel Base Paints" with 57 colour variants) AND embed a quantity
for each colour on that product page — so one page request returns per-colour
unit counts for a whole range.

Input : data/indie_shopify_discovered.csv (stores found by the store-finder
        name → domain method, see docs/indie_panel_discovery.md)
Output: data/variant_qty_scan.csv — one row per (scan date, store), appended

Per store (one request at a time, ~1.2s apart, robots.txt respected):
  1. products.json for its Citadel / Warhammer Colour / Tone Pro collections (2–6)
  2. classify paint products: variant-style (≥5 variants, ≥3 matching GW names)
     vs one-product-per-paint
  3. if variant-style: that product's .js (variant ids) + its page (2), and count
     variants whose id sits next to a quantity (inventory_quantity / data-stock /
     similar). Tone Pro variant products are checked first.

est_daily_requests = 1 robots.txt + one page per variant-style Base/Layer/Tone Pro
product — what a daily per-colour quantity read would cost for that store.

Scheduled one-off re-run after the Tone Pro launch: .github/workflows/variant_scan.yml
"""

import re, sys, argparse, importlib.util, concurrent.futures as cf
from pathlib import Path
from datetime import date

import pandas as pd

ROOT = Path(__file__).parent.parent
IN   = ROOT / "data" / "indie_shopify_discovered.csv"
OUT  = ROOT / "data" / "variant_qty_scan.csv"

_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "fetch_indie_paint_panel.py")
panel = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(panel)

GOOD = re.compile(r"base|layer|tone|pro|citadel|colou?r|paint", re.I)
BAD  = re.compile(r"air|spray|contrast|shade|dry|technical|brush|tool|case|basing|bases|dice|primer|accessor|bundle|sale", re.I)
QTY_NEAR_ID = re.compile(r'(?i)(?:inventory_?quantity|inventoryQuantity|qty|quantity|stock|inventory)["\']?\s*[:=]\s*["\']?(-?\d+)')
LINES = ("Base", "Layer", "Tone Pro")
today = str(date.today())


def pick_handles(colls: str) -> list[str]:
    hs = [h for h in colls.split("|") if h]
    tp = [h for h in hs if re.search(r"tone|warhammer-pro", h, re.I)]
    rest = [h for h in hs if GOOD.search(h) and not BAD.search(h) and h not in tp]
    return (tp[:2] + rest[:4])[:6] or hs[:4]          # nothing passed the filter → use what the store has


def qty_per_variant(page: str, ids: set[str]) -> dict[str, int]:
    """variant id → quantity, where a quantity-labelled number follows the id
    within 250 chars, or the id is the nearest one before an inventory_quantity."""
    found = {}
    for vid in ids:
        for m in re.finditer(vid, page):
            q = QTY_NEAR_ID.search(page[m.end():m.end() + 250])
            if q:
                found[vid] = int(q.group(1)); break
    for m in re.finditer(r'"?inventory_?[qQ]uantity"?\s*[:=]\s*(-?\d+)', page):
        near = re.findall(r"\b\d{11,16}\b", page[max(0, m.start() - 300):m.start()])
        if near and near[-1] in ids:
            found.setdefault(near[-1], int(m.group(1)))
    return found


def scan(row, canon) -> dict:
    host = row["domain"]
    f = panel.Fetcher(f"https://{host}")
    rec = {"date": today, "domain": host, "country": row["shop_country"] or row["finder_country"],
           "store": row["shop_name"] or row["finder_name"], "status": "ok"}
    try:
        prods = {}
        for h in pick_handles(row["gw_collections"]):
            for pg in (1, 2):
                r = f.get(f"https://{host}/collections/{h}/products.json?limit=250&page={pg}")
                if r is None or r.status_code != 200:
                    break
                ps = r.json().get("products", [])
                prods.update({x["id"]: x for x in ps})
                if len(ps) < 250:
                    break
        var = {l: [] for l in LINES}
        tp_paints = set()
        for x in prods.values():
            ms = [panel.match_paint(f"{x['title']} {v['title']}", canon) for v in x["variants"]] if len(x["variants"]) >= 5 else []
            ok = [m for m in ms if m]
            if len(ok) >= 3:
                line = max({m[0] for m in ok}, key=[m[0] for m in ok].count)
                if line in var:
                    var[line].append((x["handle"], len(ok)))
                tp_paints |= {m[1] for m in ok if m[0] == "Tone Pro"}
            else:
                m = panel.match_paint(x["title"], canon)
                if m and m[0] == "Tone Pro":
                    tp_paints.add(m[1])
        for l in LINES:
            key = l.lower().replace(" ", "_")
            rec[f"{key}_variant_products"] = len(var[l])
            rec[f"{key}_variant_colours"] = sum(n for _, n in var[l])
        rec["tone_pro_paints_listed"] = len(tp_paints)
        sample = var["Tone Pro"] or var["Base"] or var["Layer"]
        if sample:
            h = sample[0][0]
            js = f.get(f"https://{host}/products/{h}.js")
            pg = f.get(f"https://{host}/products/{h}")
            if js is not None and pg is not None and js.status_code == 200 and pg.status_code == 200:
                ids = {str(v["id"]) for v in js.json()["variants"]}
                found = qty_per_variant(pg.text, ids)
                rec.update(qty_check_product=h, qty_check_variants=len(ids), qty_check_with_qty=len(found))
        n_var = sum(len(var[l]) for l in LINES)
        rec["per_colour_qty"] = str(bool(rec.get("qty_check_variants")) and
                                    rec.get("qty_check_with_qty", 0) >= 0.9 * rec["qty_check_variants"]).lower()
        rec["est_daily_requests"] = 1 + n_var if n_var else 0
    except panel.Blocked as e:
        rec["status"] = f"blocked: {e}"
    except Exception as e:
        rec["status"] = f"error: {type(e).__name__}"
    rec["requests"] = f.n
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated domains")
    ap.add_argument("--workers", type=int, default=4, help="stores scanned in parallel (each store sequential)")
    args = ap.parse_args()
    stores = pd.read_csv(IN, dtype=str, keep_default_na=False)
    if args.only:
        stores = stores[stores["domain"].isin(args.only.split(","))]
    panel.DELAY_S = 1.2
    canon = panel.load_canon()
    print(f"Variant-format quantity scan — {today} — {len(stores)} stores")
    with cf.ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(lambda r: scan(r, canon), [r for _, r in stores.iterrows()]))
    df = pd.DataFrame(rows)
    if OUT.exists():
        ex = pd.read_csv(OUT, dtype=str, keep_default_na=False)
        ex = ex[~((ex["date"] == today) & ex["domain"].isin(df["domain"]))]
        df = pd.concat([ex, df.astype(str)], ignore_index=True)
    df.to_csv(OUT, index=False)

    cur = pd.DataFrame(rows)
    var = cur[cur.filter(like="_variant_products").apply(pd.to_numeric).sum(axis=1) > 0]
    qty = var[var["per_colour_qty"] == "true"]
    tp = cur[pd.to_numeric(cur["tone_pro_paints_listed"], errors="coerce") > 0]
    print(f"\n  stores scanned: {len(cur)} (errors/blocked: {int((cur['status'] != 'ok').sum())})")
    print(f"  variant-format stores: {len(var)} · with per-colour quantities: {len(qty)}")
    print(f"  listing Tone Pro (any format): {len(tp)} · Tone Pro in variant format with quantities: "
          f"{int(((pd.to_numeric(qty['tone_pro_variant_colours']) > 0)).sum()) if len(qty) else 0}")
    for _, r in qty.iterrows():
        print(f"    {r['domain']:30} {r['country']}  base={r['base_variant_colours']} layer={r['layer_variant_colours']} "
              f"tone_pro={r['tone_pro_variant_colours']}  ≈{r['est_daily_requests']} requests/day")
    print(f"✓ → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
