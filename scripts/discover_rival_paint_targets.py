"""
discover_rival_paint_targets.py
───────────────────────────────
One-off check: at each of the 40 unit-count stores (10 daily-count panel stores +
30 weekly product-page stores), does the store list Army Painter (Warpaints Fanatic,
classic Warpaints) and Vallejo (Game Color, Xpress Color, Model Color) paints, and
where (collection handle / category URL)?

  shopify      /collections.json (collection names) → products.json of the matching
               collections, classified by vendor + title + SKU code
  lightspeed   /search/<brand>/?format=json, page 1
  html stores  one category page each from the store's own navigation links

Same etiquette as the panel: robots.txt checked per URL, ~2s apart, one store at a
time, identifying User-Agent; blocks are recorded, never worked around.

Output: data/rival_paint_discovery.csv — one row per (store, line): collections, products
listed, example titles.
"""

import re, importlib.util
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("panel", ROOT / "scripts" / "fetch_indie_paint_panel.py")
panel = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(panel)
OUT = ROOT / "data" / "rival_paint_discovery.csv"

DAILY_COUNT = ["element_games", "firestorm_games", "the_outpost", "loaded_dice", "beanie_games", "battle_city_games",
               "nutmeg_games", "games_a_plunder", "pastime_sports_games", "jeux_az_games"]
COLL_RX = re.compile(r"army.?painter|warpaint|fanatic|vallejo|game.?colou?r|model.?colou?r|xpress", re.I)
EXCLUDE = re.compile(r"\b(set|sets|bundle|mega|starter|collection|kit|brush|spray|primer|varnish|medium|"
                     r"thinner|airbrush|wash set|case|rack|undercoat|stabili[sz]er|retarder|flow improver|glue|cement|marker)\b", re.I)


VAL_CODE = r"(?:\bVAL ?|\b)7[02][.\- ]?\d{3}\b"


def classify(title: str, vendor: str = "", sku: str = "") -> str | None:
    """Single-pot paint → line, else None. Uses brand, line names (Game Color, Xpress Color,
    Model Color and Warpaints are brand-specific names) and product codes (WP3xxx Fanatic,
    WP1xxx classic Warpaints, 72.4xx Xpress, 72.xxx Game Color, 70.xxx Model Color)."""
    t = f"{vendor} {title} {sku}"
    if EXCLUDE.search(title) or re.search(r"\(x\d+\)|\bx\d+\b|marker|speedpaint|air\b", title, re.I):
        return None
    if re.search(r"fanatic|\bWP3\d{3}\b", t, re.I) and re.search(r"army.?painter|warpaint|\bWP3\d{3}\b", t, re.I):
        return "Army Painter Fanatic"
    if re.search(r"warpaint|\bWP1\d{3}\b", t, re.I):
        return "Army Painter Warpaints"
    code = re.search(VAL_CODE, t, re.I)
    c = re.sub(r"\D", "", code.group(0)) if code else ""
    if re.search(r"xpress", t, re.I) or c.startswith("724"):
        return "Vallejo Xpress Color"
    if re.search(r"game.?colou?r", t, re.I) or c.startswith("72"):
        return "Vallejo Game Color"
    if re.search(r"model.?colou?r", t, re.I) or c.startswith("70"):
        return "Vallejo Model Color"
    return None


def shopify(f, out):
    colls, allc = [], []
    for page in range(1, 9):
        r = f.get(f"{f.base}/collections.json?limit=250&page={page}")
        if r is None or r.status_code != 200:
            break
        cs = r.json().get("collections", [])
        allc += cs
        colls += [c for c in cs if COLL_RX.search(f"{c.get('handle', '')} {c.get('title', '')}")]
        if len(cs) < 250:
            break
    if not colls:                       # fallback: the store's general paint collections (brand mixed in)
        colls = [c for c in allc if re.search(r"paint", c.get("handle", ""), re.I)
                 and not re.search(r"citadel|contrast|games-workshop|warhammer|brush|marker|spray|set|painted|tool", c["handle"], re.I)]
        colls = sorted(colls, key=lambda c: -int(c.get("products_count") or 0))[:2]
        pages_max = 10
    else:
        pages_max = 3
    # Prefer the most specific collections (line-level before brand-level), cap 6
    colls.sort(key=lambda c: (not re.search(r"fanatic|game.?colou?r|xpress|model.?colou?r|warpaint", c["handle"], re.I),
                              -int(c.get("products_count") or 0)))
    for c in colls[:6]:
        for page in range(1, pages_max + 1):
            r = f.get(f"{f.base}/collections/{c['handle']}/products.json?limit=250&page={page}")
            if r is None or r.status_code != 200:
                break
            prods = r.json().get("products", [])
            for p in prods:
                v0 = (p.get("variants") or [{}])[0]
                line = classify(p["title"], p.get("vendor", ""), v0.get("sku") or "")
                if line:
                    o = out.setdefault(line, {"handles": set(), "products": set(), "examples": [], "multi_variant": 0})
                    o["handles"].add(c["handle"]); o["products"].add(p["id"])
                    o["multi_variant"] += len(p.get("variants", [])) > 3
                    if len(o["examples"]) < 3:
                        o["examples"].append(p["title"])
            if len(prods) < 250:
                break


def lightspeed(f, out):
    for q in ("army-painter", "vallejo"):
        r = f.get(f"{f.base}/search/{q}/?format=json&limit=100")
        if r is None or r.status_code != 200:
            continue
        coll = r.json().get("collection") or {}
        prods = coll.get("products") or {} if isinstance(coll, dict) else {}
        for p in (prods.values() if isinstance(prods, dict) else prods):
            title = p.get("fulltitle") or p.get("title", "")
            line = classify(title, p.get("brand", {}).get("title", "") if isinstance(p.get("brand"), dict) else "", p.get("code") or "")
            if line:
                o = out.setdefault(line, {"handles": set(), "products": set(), "examples": [], "multi_variant": 0})
                o["handles"].add(f"/search/{q}/"); o["products"].add(p.get("id") or title)
                if len(o["examples"]) < 3:
                    o["examples"].append(title)


def html_store(f, start_url, out):
    """Follow army-painter / vallejo links from the store's own paint category page, one page each."""
    r = f.get(start_url)
    if r is None or r.status_code != 200:
        return
    links = sorted({urljoin(f.base, h) for h in re.findall(r'href="([^"#?]+)"', r.text)
                    if re.search(r"army-?painter|warpaint|fanatic|vallejo|game-colou?r|model-colou?r|xpress", h, re.I)
                    and urljoin(f.base, h).startswith(f.base)}, key=len)[:6]
    for u in links:
        r = f.get(u)
        if r is None or r.status_code != 200:
            continue
        titles = re.findall(r'(?:woocommerce-loop-product__title|producttitle|itemprop="name" content=)"?[^>]*>?([^<"]{6,120})', r.text)
        for t in titles:
            line = classify(t)
            if line:
                o = out.setdefault(line, {"handles": set(), "products": set(), "examples": [], "multi_variant": 0})
                o["handles"].add(u); o["products"].add(t.strip())
                if len(o["examples"]) < 3:
                    o["examples"].append(t.strip())


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); args = ap.parse_args()
    pc = pd.read_csv(ROOT / "config" / "indie_paint_panel.csv", dtype=str, keep_default_na=False)
    qc = pd.read_csv(ROOT / "config" / "page_qty_stores.csv", dtype=str, keep_default_na=False)
    stores = [(r["store_id"], r["domain"], r["platform"], r["targets"], "daily") for _, r in pc[pc["store_id"].isin(DAILY_COUNT)].iterrows()]
    stores += [(r["store_id"], r["domain"], r["platform"], r["targets"], "weekly") for _, r in qc[qc["active"].str.lower() == "true"].iterrows()]
    if args.only:
        stores = [x for x in stores if x[0] in args.only.split(",")]
    rows = []
    for sid, domain, platform, targets, cadence in stores:
        f = panel.Fetcher(f"https://{domain}")
        out, status = {}, "ok"
        try:
            if f.rules is None:
                raise panel.Blocked("robots.txt 401/403")
            if platform == "shopify":
                shopify(f, out)
            elif platform == "lightspeed":
                lightspeed(f, out)
            else:
                html_store(f, targets.split("|")[0], out)
        except panel.Blocked as e:
            status = f"blocked: {e}"
        except Exception as e:
            status = f"error: {type(e).__name__}: {str(e)[:60]}"
        print(f"  {sid:30} {cadence:6} {status:8} req={f.n:<3} " + ", ".join(f"{k}={len(v['products'])}" for k, v in out.items()))
        for line, o in out.items():
            rows.append({"store_id": sid, "cadence": cadence, "platform": platform, "line": line,
                         "products": len(o["products"]), "multi_variant_products": o["multi_variant"],
                         "where": "|".join(sorted(o["handles"])), "examples": " / ".join(o["examples"]),
                         "status": status, "requests": f.n})
        if not out:
            rows.append({"store_id": sid, "cadence": cadence, "platform": platform, "line": "", "products": 0,
                         "multi_variant_products": 0, "where": "", "examples": "", "status": status, "requests": f.n})
    new = pd.DataFrame(rows)
    if args.only and OUT.exists():
        old = pd.read_csv(OUT, dtype=str, keep_default_na=False)
        new = pd.concat([old[~old["store_id"].isin(new["store_id"])], new.astype(str)], ignore_index=True)
    new.to_csv(OUT, index=False)
    print(f"✓ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
