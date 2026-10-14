"""
fetch_indie_paint_panel.py
──────────────────────────
Daily snapshot of Base / Layer and Tone Pro paint availability at a fixed panel of
independent online hobby retailers (config/indie_paint_panel.csv).

Each store is read through its own public storefront data:
  shopify     /collections/<handle>/products.json   availability, date listed, SKU
  outpost     WooCommerce category pages (HTML)     in stock (N) / On The Way (M)
  elementgames category pages (HTML)                "N In Stock" (capped at 10+)
  firestorm   category page (HTML)                  "N in Stock" (exact), GW code
  lightspeed  category ?format=json                 availability only

Etiquette: robots.txt is checked for every URL (RFC 9309 longest match), one store
at a time, ~2s between requests, capped pages per store, identifying User-Agent.
A store that returns 401/403/429 or a bot challenge is recorded as blocked and
skipped — never worked around.

Store titles are matched to GW's own paint names (from data/gw_paint_stock_daily.csv)
so the same paint lines up across stores. Bundles/sets and other ranges are ignored.

WHAT THIS MEASURES: whether each panel store lists each paint and lets you buy it
online ("available" — for Shopify/Lightspeed stores this can include pre-orders), plus
true shelf stock and a quantity at the stores that display one. NOT sales, NOT per-store
deliveries, NOT a sample of all GW stockists — panel stores are online-active and
skew UK/Canada.

Output:
  data/indie_paint_panel_daily.csv     one row per (date, store, paint)
  data/indie_paint_panel_summary.csv   one row per (date, store, line)
  data/indie_paint_panel_runs.csv      one row per (date, store): status, counts
  data/indie_paint_panel_unmatched.csv latest run's unmatched titles (for QA)
"""

import re, sys, json, time, html, difflib, argparse, requests
from pathlib import Path
from datetime import date
from urllib.parse import urlparse, urljoin

import pandas as pd

ROOT        = Path(__file__).parent.parent
CONFIG      = ROOT / "config" / "indie_paint_panel.csv"
GW_PAINTS   = ROOT / "data" / "gw_paint_stock_daily.csv"
OUT_DAILY   = ROOT / "data" / "indie_paint_panel_daily.csv"
OUT_SUMMARY = ROOT / "data" / "indie_paint_panel_summary.csv"
OUT_RUNS    = ROOT / "data" / "indie_paint_panel_runs.csv"
OUT_UNMATCH = ROOT / "data" / "indie_paint_panel_unmatched.csv"
OUT_QTY     = ROOT / "data" / "indie_paint_panel_qty_series.csv"
OUT_QTY_SUM = ROOT / "data" / "indie_paint_panel_qty_summary.csv"

# Contact label (confirmed 2026-10-14).
USER_AGENT = "WarhammerDemandResearch/1.0 (+contact: en@pillsburycap.com)"
HEADERS    = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
DELAY_S    = 2.0
MAX_PAGES  = 12
LINES      = ("Base", "Layer", "Tone Pro", "Tech Pro")
today      = str(date.today())


# ── robots.txt (RFC 9309: longest matching rule wins, Allow wins ties) ────────

def load_robots(base: str) -> list[tuple[str, str]] | None:
    try:
        r = requests.get(base + "/robots.txt", headers=HEADERS, timeout=20)
    except requests.RequestException:
        return []
    if r.status_code in (401, 403):
        return None                                   # treat as fully disallowed
    if r.status_code != 200:
        return []
    groups, cur, collecting = [], None, False
    for raw in r.text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not collecting:
                cur = {"agents": [], "rules": []}; groups.append(cur); collecting = True
            cur["agents"].append(v.lower())
        elif k in ("allow", "disallow") and cur is not None:
            collecting = False
            if v:
                cur["rules"].append((k, v))
    ua = USER_AGENT.lower()
    mine = [g for g in groups if any(a != "*" and a in ua for a in g["agents"])]
    use = mine or [g for g in groups if "*" in g["agents"]]
    return [r for g in use for r in g["rules"]]


def robots_allows(rules, url: str) -> bool:
    if rules is None:
        return False
    p = urlparse(url)
    path = (p.path or "/") + ("?" + p.query if p.query else "")
    best_kind, best_len = "allow", -1
    for kind, pat in rules:
        rx = "^" + re.escape(pat).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path):
            if len(pat) > best_len or (len(pat) == best_len and kind == "allow"):
                best_kind, best_len = kind, len(pat)
    return best_kind == "allow"


class Blocked(Exception):
    pass


class Fetcher:
    def __init__(self, base: str):
        self.base = base
        self.rules = load_robots(base)
        self.n = 1

    def get(self, url: str) -> requests.Response | None:
        if not robots_allows(self.rules, url):
            return None
        time.sleep(DELAY_S)
        self.n += 1
        r = requests.get(url, headers=HEADERS, timeout=40)
        head = r.text[:5000]
        if r.status_code in (401, 403, 429) or "cf-chl" in head or "challenge-platform" in head:
            raise Blocked(f"HTTP {r.status_code}")
        return r


# ── Canonical paint names (GW's own catalogue) ────────────────────────────────

def _norm(s: str) -> str:
    s = html.unescape(s).lower()
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    # US spellings used by some stores → GW's UK spellings
    return re.sub(r"\bgray\b", "grey", re.sub(r"\barmor\b", "armour", s))


def _fuzzy(text: str, options: list[tuple[str, str]], cutoff: float = 0.88) -> str | None:
    """Best canonical name whose colour closely matches a same-length word window
    of `text` (catches store typos like 'Karskin' for 'Kasrkin'). Requires a clear
    winner: best ratio >= cutoff and >= 0.04 ahead of the runner-up."""
    words = text.split()
    scored = []
    for col, name in options:
        k = len(col.split())
        best = max((difflib.SequenceMatcher(None, col, " ".join(words[i:i + k])).ratio()
                    for i in range(max(1, len(words) - k + 1))), default=0)
        scored.append((best, name))
    scored.sort(reverse=True)
    if scored and scored[0][0] >= cutoff and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.04):
        return scored[0][1]
    return None


def load_canon() -> dict[str, list[tuple[str, str]]]:
    """line → [(normalised colour, canonical name)], longest colour first."""
    df = pd.read_csv(GW_PAINTS, dtype=str, keep_default_na=False)
    df = df[df["date"] == df["date"].max()]
    canon: dict[str, list] = {}
    for name, line in zip(df["name"], df["line"]):
        if line not in LINES:
            continue
        colour = name.split(":", 1)[1].strip()
        canon.setdefault(line, []).append((_norm(colour), name))
    for line in canon:
        canon[line].sort(key=lambda x: -len(x[0]))
    return canon


EXCLUDE = re.compile(r"\b(set|sets|bundle|bundles|full range|collection|brush|brushes|spray|air|dry|"
                     r"contrast|shade|shades|technical|medium|rack|case|primer)\b", re.I)
# 'shading medium' / 'blending medium' are Tech Pro names — handled before EXCLUDE.


def match_paint(title: str, canon) -> tuple[str, str] | None:
    """Store title → (line, canonical GW name), or None."""
    t = _norm(title)
    if re.search(r"\btech ?pro\b|\b(shading|blending) medium\b", t):
        for col, name in canon.get("Tech Pro", []):
            if col.replace("tech pro ", "") in t or col in t:
                return "Tech Pro", name
        return None
    if re.search(r"\btone ?pro\b", t):
        if EXCLUDE.search(t) or re.search(r"\b1 ?5\b|\b1 to 5\b", t):
            return None
        for col, name in canon.get("Tone Pro", []):
            col_base = re.sub(r"\s\d$", "", col)               # "blackstone void"
            tone = col[-1]
            if re.search(rf"\b{re.escape(col_base)}\s*(?:tone\s*)?{tone}\b", t):
                return "Tone Pro", name
        tone = re.search(r"\b([1-5])\b(?!.*\b[1-5]\b)", t)        # last standalone 1-5
        if tone:
            opts = [(re.sub(r"\s\d$", "", c), n) for c, n in canon.get("Tone Pro", []) if c.endswith(tone.group(1))]
            hit = _fuzzy(re.sub(r"\b(warhammer|tone|pro|12 ?ml|[1-5])\b", " ", t), opts)
            if hit:
                return "Tone Pro", hit
        return None
    if EXCLUDE.search(t):
        return None
    line = "Base" if re.search(r"\bbase\b", t) else "Layer" if re.search(r"\blayer\b", t) else None
    if line is None:
        return None
    t2 = re.sub(r"\b(base|layer)\b", " ", t)
    other = "Layer" if line == "Base" else "Base"
    for ln in (line, other):            # other line catches store mislabels (e.g. a Base sold as 'Layer')
        for col, name in canon.get(ln, []):
            if re.search(rf"\b{re.escape(col)}\b", t2):
                return ln, name
    t3 = re.sub(r"\b(citadel|warhammer|colour|games workshop|paints?|12 ?ml|\d\d \d\d)\b", " ", t2)
    hit = _fuzzy(t3, canon.get(line, []))
    if hit:
        return line, hit
    return None


# ── Store adapters → list of raw items ────────────────────────────────────────
# Raw item: {title, status, qty, qty_floor, on_order, price, listed_at, url}
# status ∈ in_stock   shelf stock shown by the store (HTML stores)
#          available  can be bought online; feed doesn't say whether from stock or pre-order
#          preorder | backorder | stock_due | oos | unknown

def adapt_shopify(f: Fetcher, cfg) -> list[dict]:
    items, seen = [], set()
    for handle in cfg["targets"].split("|"):
        for page in range(1, MAX_PAGES + 1):
            r = f.get(f"{f.base}/collections/{handle}/products.json?limit=250&page={page}")
            if r is None or r.status_code != 200:
                break
            prods = r.json().get("products", [])
            for p in prods:
                multi = len(p["variants"]) > 1
                for v in p["variants"]:
                    key = (p["id"], v["id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    title = f"{p['title']} {v['title']}" if multi and v["title"] != "Default Title" else p["title"]
                    pre = re.search(r"pre-?order", f"{p['title']} {' '.join(p.get('tags', []))}", re.I)
                    items.append({
                        "title": title,
                        "status": ("preorder" if pre else "available") if v.get("available") else "oos",
                        "qty": "", "qty_floor": "", "on_order": "",
                        "price": v.get("price", ""),
                        "listed_at": (p.get("published_at") or p.get("created_at") or "")[:10],
                        "sku": v.get("sku") or "",
                        "url": f"{f.base}/products/{p['handle']}",
                        "handle": p["handle"],
                        "variant_id": str(v["id"]),
                    })
            if len(prods) < 250:
                break
    if cfg.get("qty_html", "") and items:
        _shopify_html_qty(f, cfg, items)
    return items


QTY_TEXT = re.compile(r"\b(\d{1,4})\+?\s*(?:in stock|left in stock|units? left)\b|only\s+(\d{1,3})\s+left", re.I)


def _shopify_html_qty(f: Fetcher, cfg, items: list[dict]) -> None:
    """Some Shopify themes print 'N in stock' / 'Only N left' on collection pages
    (products.json never includes quantities). Read the collection HTML pages and
    attach the number to the matching product handle. qty_html = 'all' when the theme
    shows counts for every product, 'low' when only below a low-stock threshold."""
    counts = {}
    for it in items:
        counts[it["handle"]] = counts.get(it["handle"], 0) + 1
    by_handle = {it["handle"]: it for it in items if counts[it["handle"]] == 1}   # skip multi-variant products
    for handle in cfg["targets"].split("|"):
        seen_page = set()
        for page in range(1, MAX_PAGES + 1):
            r = f.get(f"{f.base}/collections/{handle}?page={page}")
            if r is None or r.status_code != 200:
                break
            hs = set(re.findall(r'/products/([a-z0-9\-]+)', r.text))
            if not hs or hs <= seen_page:
                break
            seen_page |= hs
            for seg in re.split(r'(?=href="[^"]*/products/[a-z0-9\-]+)', r.text):
                hm = re.search(r'/products/([a-z0-9\-]+)', seg)
                it = by_handle.get(hm.group(1)) if hm else None
                if it is None or it["qty"] != "":
                    continue
                m = QTY_TEXT.search(_text(seg)[:3000])
                if m:
                    it["qty"] = m.group(1) or m.group(2)
                    it["qty_floor"] = "true" if "+" in m.group(0) else "false"
                    if it["status"] in ("available", "preorder") and int(it["qty"]) > 0:
                        it["status"] = "in_stock"


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def adapt_outpost(f: Fetcher, cfg) -> list[dict]:
    items = []
    for cat in cfg["targets"].split("|"):
        for page in range(1, MAX_PAGES + 1):
            url = cat if page == 1 else f"{cat.rstrip('/')}/page/{page}/"
            r = f.get(url)
            if r is None or r.status_code != 200:
                break
            cards = re.split(r'<li class="([^"]*\bproduct type-product[^"]*)"', r.text)
            if len(cards) < 3:
                break
            for i in range(1, len(cards) - 1, 2):
                cls, body = cards[i], cards[i + 1]
                name = re.search(r'woocommerce-loop-product__title">([^<]+)<', body)
                link = re.search(r'href="([^"]+/product/[^"]+)"', body)
                txt = _text(body)
                m = re.search(r"In ?stock \((\d+)\)\s*/\s*On The Way \((\d+)\)", txt, re.I)
                status = ("preorder" if "pre-order" in cls or "Pre Order" in body else
                          "backorder" if "onbackorder" in cls else
                          "in_stock" if "instock" in cls else "oos" if "outofstock" in cls else "unknown")
                price = re.findall(r"&pound;</span>([\d.]+)</bdi>", body)
                items.append({"title": name.group(1).strip() if name else "",
                              "status": status,
                              "qty": m.group(1) if m else "", "qty_floor": "false" if m else "",
                              "on_order": m.group(2) if m else "",
                              "price": price[-1] if price else "", "listed_at": "", "sku": "",
                              "url": link.group(1) if link else url})
    return items


def adapt_elementgames(f: Fetcher, cfg) -> list[dict]:
    items = []
    for cat in cfg["targets"].split("|"):
        r = f.get(cat)
        if r is None or r.status_code != 200:
            continue
        for body in r.text.split('<div class="productgrid">')[1:]:
            name = re.search(r'class="producttitle"[^>]*>([^<]+)<', body)
            link = re.search(r'href="([^"]+)"', body)
            txt = _text(body.split('<div class="productgrid">')[0])[:600]
            m = re.search(r"(\d+)(\+?)\s*In Stock", txt, re.I)
            status = ("in_stock" if m else "preorder" if re.search(r"pre-?order", txt, re.I) else
                      "stock_due" if re.search(r"stock due", txt, re.I) else
                      "oos" if re.search(r"unavailable|out of stock", txt, re.I) else "unknown")
            price = re.search(r'class="price">&pound;([\d.]+)', body)
            items.append({"title": name.group(1).strip() if name else "", "status": status,
                          "qty": m.group(1) if m else "", "qty_floor": ("true" if m.group(2) else "false") if m else "",
                          "on_order": "", "price": price.group(1) if price else "", "listed_at": "", "sku": "",
                          "url": urljoin(cat, link.group(1)) if link else cat})
    return items


def adapt_firestorm(f: Fetcher, cfg) -> list[dict]:
    items = []
    for cat in cfg["targets"].split("|"):
        r = f.get(cat)
        if r is None or r.status_code != 200:
            continue
        for body in r.text.split('itemtype="http://schema.org/Product"')[1:]:
            name = re.search(r'itemprop="name" content="([^"]+)"', body)
            model = re.search(r'itemprop="model" content="([^"]+)"', body)
            avail = re.search(r'itemprop="availability" href="[^"]*/(\w+)"', body)
            link = re.search(r'href="(/[^"]+)" itemprop="offers"', body)
            price = re.search(r'itemprop="price" content="([\d.]+)"', body)
            m = re.search(r"(\d+)\s+in Stock", _text(body)[:1500], re.I)
            a = avail.group(1) if avail else ""
            status = {"InStock": "in_stock", "PreOrder": "preorder", "OutOfStock": "oos",
                      "BackOrder": "backorder"}.get(a, "unknown")
            items.append({"title": name.group(1) if name else "", "status": status,
                          "qty": m.group(1) if m else "", "qty_floor": "false" if m else "", "on_order": "",
                          "price": price.group(1) if price else "", "listed_at": "",
                          "sku": model.group(1) if model else "",
                          "url": urljoin(f.base, link.group(1)) if link else cat})
    return items


def adapt_lightspeed(f: Fetcher, cfg) -> list[dict]:
    items = []
    for cat in cfg["targets"].split("|"):
        for page in range(1, MAX_PAGES * 3 + 1):
            url = f"{cat.rstrip('/')}/{'' if page == 1 else f'page{page}.html'}?format=json&limit=100"
            r = f.get(url)
            if r is None or r.status_code != 200:
                break
            coll = r.json().get("collection", {})
            prods = coll.get("products", {})
            prods = list(prods.values()) if isinstance(prods, dict) else prods
            for p in prods:
                items.append({"title": p.get("fulltitle") or p.get("title", ""),
                              "status": "available" if p.get("available") else "oos",
                              "qty": "", "qty_floor": "", "on_order": "",
                              "price": (p.get("price") or {}).get("price", ""), "listed_at": "",
                              "sku": p.get("code") or "", "url": p.get("url", "")})
            if page >= int(coll.get("pages") or 1):
                break
    return items


ADAPTERS = {"shopify": adapt_shopify, "outpost": adapt_outpost, "elementgames": adapt_elementgames,
            "firestorm": adapt_firestorm, "lightspeed": adapt_lightspeed}


# ── Quantity series (stores that publish numbers) ─────────────────────────────

def build_qty_series(daily: pd.DataFrame) -> None:
    """Per (store, paint): shelf quantity and on-order units over time, with
    day-over-day estimates. Only exact counts are used for changes ('10+' floors
    are kept in the series but never differenced).

      received_est = larger of: fall in on-order units (The Outpost's 'On The Way'),
                     rise in shelf qty                (stores with on-order data)
      outflow_est  = received_est - change in shelf qty   (stores with on-order data)
                   = fall in shelf qty                     (stores without; a floor —
                                                            any restock hides outflow)
    Outflow covers sales, pre-order fulfilment and stock corrections alike; it is
    an estimate of units leaving the shelf, not a sales figure."""
    q = daily[(daily["qty"] != "") | (daily["on_order"] != "")].copy()
    if q.empty:
        return
    q = q.sort_values(["store_id", "paint", "date"])
    q["qty_n"] = pd.to_numeric(q["qty"], errors="coerce")
    q["oo_n"] = pd.to_numeric(q["on_order"], errors="coerce")
    exact = q["qty_is_floor"] != "true"
    g = q.groupby(["store_id", "paint"])
    q["prev_date"] = g["date"].shift()
    q["d_qty"] = q["qty_n"] - g["qty_n"].shift()
    q.loc[~exact | (g["qty_is_floor"].shift() == "true"), "d_qty"] = float("nan")
    q["d_on_order"] = q["oo_n"] - g["oo_n"].shift()
    has_oo = q["oo_n"].notna() & q["d_on_order"].notna()
    # Arrivals show up as on-order falling and/or shelf rising (whichever is larger)
    q["received_est"] = pd.concat([-q["d_on_order"], q["d_qty"].fillna(0)], axis=1).max(axis=1).clip(lower=0).where(has_oo)
    q["outflow_est"] = (q["received_est"] - q["d_qty"]).where(has_oo & q["d_qty"].notna())
    q.loc[~has_oo, "outflow_est"] = (-q["d_qty"]).clip(lower=0)
    q["outflow_est"] = q["outflow_est"].clip(lower=0)
    cols = ["date", "prev_date", "store_id", "country", "line", "paint", "status", "qty", "qty_is_floor",
            "on_order", "d_qty", "d_on_order", "received_est", "outflow_est"]
    out = q[cols].copy()
    for c in ("d_qty", "d_on_order", "received_est", "outflow_est"):
        out[c] = out[c].map(lambda v: "" if pd.isna(v) else str(int(v)))
    out.to_csv(OUT_QTY, index=False)

    num = q.assign(shelf=q["qty_n"].fillna(0), oo=q["oo_n"].fillna(0),
                   rec=q["received_est"].fillna(0), outf=q["outflow_est"].fillna(0))
    summ = (num.groupby(["date", "store_id", "country", "line"])
            .agg(paints=("paint", "size"),
                 shelf_units=("shelf", "sum"), shelf_is_floor=("qty_is_floor", lambda x: str((x == "true").any()).lower()),
                 on_order_units=("oo", "sum"), received_est=("rec", "sum"), outflow_est=("outf", "sum"),
                 paints_in_stock=("qty_n", lambda x: int((x > 0).sum())))
            .reset_index())
    for c in ("shelf_units", "on_order_units", "received_est", "outflow_est"):
        summ[c] = summ[c].astype(int)
    summ.to_csv(OUT_QTY_SUM, index=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def upsert(path: Path, new: pd.DataFrame, keys: list[str]) -> None:
    if path.exists():
        ex = pd.read_csv(path, dtype=str, keep_default_na=False)
        drop = ex.set_index(keys).index.isin(new.set_index(keys).index)
        new = pd.concat([ex[~drop], new.astype(str)], ignore_index=True)
    new.to_csv(path, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated store_ids to run")
    args = ap.parse_args()

    cfg = pd.read_csv(CONFIG, dtype=str, keep_default_na=False)
    cfg = cfg[cfg["active"].str.lower() == "true"]
    if args.only:
        cfg = cfg[cfg["store_id"].isin(args.only.split(","))]
    canon = load_canon()

    print(f"Indie paint panel — {today} — {len(cfg)} stores")
    rows, runs, unmatched = [], [], []
    for _, s in cfg.iterrows():
        f = Fetcher(f"https://{s['domain']}")
        status, items = "ok", []
        try:
            if f.rules is None:
                raise Blocked("robots.txt 401/403")
            items = ADAPTERS[s["platform"]](f, s)
        except Blocked as e:
            status = f"blocked: {e}"
        except Exception as e:                                   # one store failing never stops the run
            status = f"error: {type(e).__name__}: {str(e)[:80]}"

        matched = {}
        for it in items:
            it["title"] = html.unescape(it["title"])
            m = match_paint(it["title"], canon)
            if m is None:
                if re.search(r"tone ?pro|\bbase\b|\blayer\b", it["title"], re.I):
                    unmatched.append({"date": today, "store_id": s["store_id"], "title": it["title"]})
                continue
            line, paint = m
            prev = matched.get(paint)
            # Duplicate listings of one paint (e.g. old + new packaging): keep the buyable one
            if prev is None or (prev["status"] not in ("in_stock", "available") and it["status"] in ("in_stock", "available")):
                matched[paint] = {**it, "line": line, "paint": paint}
        for paint, it in matched.items():
            rows.append({"date": today, "store_id": s["store_id"], "country": s["country"],
                         "line": it["line"], "paint": paint, "status": it["status"],
                         "available_online": str(it["status"] in ("in_stock", "available")).lower(),
                         "qty": it["qty"], "qty_is_floor": it["qty_floor"], "on_order": it["on_order"],
                         "price": it["price"], "currency": s["currency"], "listed_at": it["listed_at"],
                         "store_sku": it.get("sku", ""), "store_title": it["title"], "url": it["url"],
                         "variant_id": it.get("variant_id", "")})
        n_by_line = {l: sum(1 for v in matched.values() if v["line"] == l) for l in LINES}
        runs.append({"date": today, "store_id": s["store_id"], "status": status, "requests": f.n,
                     "items_seen": len(items), "matched": len(matched),
                     **{f"n_{l.lower().replace(' ', '_')}": n for l, n in n_by_line.items()}})
        print(f"  {s['store_id']:<22} {status:<10} req={f.n:<3} seen={len(items):<5} "
              f"base={n_by_line['Base']:<3} layer={n_by_line['Layer']:<3} tone_pro={n_by_line['Tone Pro']}")

    daily = pd.DataFrame(rows)
    if not daily.empty:
        upsert(OUT_DAILY, daily, ["date", "store_id", "paint"])
        summ = (daily.groupby(["date", "store_id", "country", "line"])
                .agg(listed=("paint", "size"),
                     available=("available_online", lambda x: int((x == "true").sum())),
                     in_stock_shelf=("status", lambda x: int((x == "in_stock").sum())),
                     preorder=("status", lambda x: int(x.isin(["preorder", "backorder", "stock_due"]).sum())),
                     oos=("status", lambda x: int((x == "oos").sum())),
                     qty_reported=("qty", lambda x: int((x != "").sum())),
                     qty_sum=("qty", lambda x: int(pd.to_numeric(x, errors="coerce").fillna(0).sum())),
                     on_order_sum=("on_order", lambda x: int(pd.to_numeric(x, errors="coerce").fillna(0).sum())))
                .reset_index())
        upsert(OUT_SUMMARY, summ, ["date", "store_id", "line"])
        build_qty_series(pd.read_csv(OUT_DAILY, dtype=str, keep_default_na=False))
    upsert(OUT_RUNS, pd.DataFrame(runs), ["date", "store_id"])
    pd.DataFrame(unmatched, columns=["date", "store_id", "title"]).to_csv(OUT_UNMATCH, index=False)

    ok = sum(r["status"] == "ok" for r in runs)
    print(f"\n✓ {ok}/{len(runs)} stores ok · {len(daily)} paint rows → {OUT_DAILY.relative_to(ROOT)}")
    print(f"✓ {len(unmatched)} unmatched Base/Layer/Tone Pro-looking titles → {OUT_UNMATCH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
