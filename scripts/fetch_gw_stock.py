"""
fetch_gw_stock.py
─────────────────
Scrape GW website stock status for all products in config/gw_starter_products.csv.
Appends a daily snapshot to data/gw_stock_daily.csv.
Deduplicates on (date, slug) so re-running the same day is safe.

Method (hybrid approach):
  1. Launch a headless Chromium browser (Playwright) once to solve the AWS WAF
     JavaScript challenge and extract the aws-waf-token cookie + Next.js buildId.
  2. Use that cookie in regular requests against the fast JSON endpoint:
       /_next/data/{buildId}/en-US/shop/{slug}.json
     No browser needed per product — typically < 1s per request.

Stock status codes:
  A = Available (in stock, normal)
  P = Phased   (transitional — still purchasable if calculatedIsAvailableFlag=true)
  O = Obsolete / discontinued
  G = Made-to-Order
"""

import os, re, csv, time
from pathlib import Path
from datetime import date

import requests
import pandas as pd

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
CFG  = ROOT / "config" / "gw_starter_products.csv"
OUT  = ROOT / "data" / "gw_stock_daily.csv"
OUT.parent.mkdir(exist_ok=True)

BASE_URL   = "https://www.warhammer.com"
LOCALE     = "en-US"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DELAY_SECS  = 0.8   # polite delay between JSON requests
WAF_WAIT_MS = 8000  # ms to wait for WAF JS challenge to resolve
TIMEOUT     = 25

today = str(date.today())

# ── Step 1: Playwright — solve WAF + get buildId ──────────────────────────────

def get_waf_cookie_and_build_id() -> tuple[dict | None, str | None]:
    """
    Launch a headless browser, load the shop homepage, wait for the AWS WAF
    JS challenge to complete, then return (waf_cookie_dict, buildId).
    """
    if not HAS_PLAYWRIGHT:
        raise SystemExit(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        )

    print("Launching browser to solve WAF challenge (one-time, ~10s)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=BROWSER_UA,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = context.new_page()
        # Remove the navigator.webdriver fingerprint
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page.goto(f"{BASE_URL}/{LOCALE}/shop", timeout=45000)
        page.wait_for_timeout(WAF_WAIT_MS)

        content = page.content()
        build_id_match = re.search(r'"buildId"\s*:\s*"([^"]+)"', content)
        build_id = build_id_match.group(1) if build_id_match else None

        all_cookies = context.cookies()
        waf_cookie  = next(
            (c for c in all_cookies if "waf" in c["name"].lower() or "aws" in c["name"].lower()),
            None,
        )
        browser.close()

    return waf_cookie, build_id


# ── Step 2: Parse stock from _next/data JSON ──────────────────────────────────

def _attr_value(attrs_raw: list, key: str) -> str:
    """Extract the English value for a product attribute key."""
    for attr in attrs_raw:
        if attr.get("name") == key:
            v = attr.get("value")
            if isinstance(v, dict):
                return v.get("en-US") or v.get("en-GB") or next(iter(v.values()), "")
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        return item.get("en-US") or next(iter(item.values()), "")
            return str(v) if v is not None else ""
    return ""


def parse_stock(data: dict) -> dict:
    """Walk Next.js pageProps to find stock attributes."""
    result = {
        "is_in_stock": None, "stock_status": None,
        "is_available": None, "last_chance": None,
        "selling_fast": None, "parse_ok": False,
    }
    try:
        attrs_raw = (
            data.get("pageProps", {})
            .get("context", {})
            .get("productInformation", {})
            .get("inStore", {})
            .get("product", {})
            .get("masterData", {})
            .get("current", {})
            .get("masterVariant", {})
            .get("attributesRaw", [])
        )
        if not attrs_raw:
            # Alternate path: first variant
            attrs_raw = (
                data.get("pageProps", {})
                .get("context", {})
                .get("productInformation", {})
                .get("inStore", {})
                .get("product", {})
                .get("masterData", {})
                .get("current", {})
                .get("variants", [{}])[0]
                .get("attributesRaw", [])
            )
        if attrs_raw:
            result["is_in_stock"]  = _attr_value(attrs_raw, "calculatedIsOnStockFlag")
            result["stock_status"] = _attr_value(attrs_raw, "calculatedStockStatus")
            result["is_available"] = _attr_value(attrs_raw, "calculatedIsAvailableFlag")
            result["last_chance"]  = _attr_value(attrs_raw, "lastChanceToBuy")
            result["selling_fast"] = _attr_value(attrs_raw, "calculatedIsSellingFastFlag")
            result["parse_ok"]     = True
    except Exception as e:
        result["parse_error"] = str(e)
    return result


def fetch_product(slug: str, session: requests.Session, build_id: str) -> dict:
    """Fetch stock status for one product via the JSON endpoint."""
    url = f"{BASE_URL}/_next/data/{build_id}/{LOCALE}/shop/{slug}.json"
    out = {
        "slug": slug, "http_status": None,
        "is_in_stock": None, "stock_status": None,
        "is_available": None, "last_chance": None,
        "selling_fast": None, "parse_ok": False,
    }
    try:
        r = session.get(url, timeout=TIMEOUT)
        out["http_status"] = r.status_code
        if r.status_code == 200 and len(r.content) > 500:
            data = r.json()
            if data.get("notFound"):
                out["stock_status"] = "NOT_FOUND"
            else:
                out.update(parse_stock(data))
        elif r.status_code == 404:
            out["stock_status"] = "NOT_FOUND"
    except Exception as e:
        out["parse_error"] = str(e)
    return out


# ── Interpret raw flags into a human-readable label ───────────────────────────

STATUS_MAP = {
    "A": "In Stock",
    "P": "Transitional",
    "O": "Discontinued",
    "G": "Made-to-Order",
}

def interpret(result: dict) -> tuple[str, str]:
    """Return (in_stock_bool_str, display_label)."""
    raw_status = result.get("stock_status") or ""
    raw_flag   = (result.get("is_in_stock")  or "").lower()
    raw_avail  = (result.get("is_available")  or "").lower()

    if raw_status == "NOT_FOUND":
        return "unknown", "NOT FOUND"
    if not result.get("parse_ok"):
        return "error", f"ERROR (HTTP {result.get('http_status')})"

    # In stock = available flag true AND status is purchasable (A or P)
    is_in = raw_avail == "true" and raw_status in ("A", "P")
    bool_str = "true" if is_in else "false"
    label = STATUS_MAP.get(raw_status, raw_status or "Unknown")
    if not is_in and raw_status not in ("O", "G", "NOT_FOUND"):
        label = "Out of Stock"
    if result.get("last_chance", "").lower() == "true":
        label += " (Last Chance)"
    if result.get("selling_fast", "").lower() == "true" and is_in:
        label += " (Selling Fast)"
    return bool_str, label


# ── Main ──────────────────────────────────────────────────────────────────────

products = []
with open(CFG, newline="") as f:
    for row in csv.DictReader(f):
        products.append({k: v.strip() for k, v in row.items()})

print(f"GW Stock Fetcher — {today}")
print(f"Products to check: {len(products)}\n")

# Get WAF cookie and buildId (one browser launch)
waf_cookie, build_id = get_waf_cookie_and_build_id()

if not build_id:
    raise SystemExit("Could not retrieve Next.js buildId — site may have changed.")
if not waf_cookie:
    raise SystemExit("Could not retrieve AWS WAF token — browser challenge failed.")

print(f"  ✓ buildId:   {build_id}")
print(f"  ✓ WAF token: {waf_cookie['name']}=...{waf_cookie['value'][-8:]}\n")

# Build a requests session with WAF cookie
sess = requests.Session()
sess.headers.update({
    "User-Agent": BROWSER_UA,
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/{LOCALE}/shop",
})
sess.cookies.set(
    waf_cookie["name"],
    waf_cookie["value"],
    domain=waf_cookie.get("domain", ".warhammer.com"),
)

# Fetch each product
rows = []
print(f"  {'Product':<52}  Status")
print(f"  {'─'*52}  {'─'*22}")

for i, prod in enumerate(products):
    slug = prod["slug"]
    print(f"  [{i+1:02d}/{len(products)}] {prod['name'][:46]:<48}", end="", flush=True)

    result = fetch_product(slug, sess, build_id)
    in_stock_bool, display = interpret(result)
    print(display)

    rows.append({
        "date":         today,
        "slug":         slug,
        "name":         prod["name"],
        "category":     prod["category"],
        "priority":     prod["priority"],
        "in_stock":     in_stock_bool,
        "stock_status": result.get("stock_status") or "",
        "is_available": (result.get("is_available") or "").lower(),
        "last_chance":  (result.get("last_chance")  or "").lower(),
        "selling_fast": (result.get("selling_fast")  or "").lower(),
        "http_status":  result.get("http_status"),
        "build_id":     build_id,
        "source":       "live",
    })
    time.sleep(DELAY_SECS)

# Save with dedup
new_df = pd.DataFrame(rows)
if OUT.exists():
    existing = pd.read_csv(OUT, dtype=str)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date", "slug"], keep="last")
else:
    combined = new_df

combined.to_csv(OUT, index=False)
print(f"\n✓ Saved {len(rows)} rows → {OUT.relative_to(ROOT)}")

# Summary
valid = new_df[new_df["in_stock"].isin(["true", "false"])]
n_total = len(valid)
n_in    = (valid["in_stock"] == "true").sum()
n_out   = (valid["in_stock"] == "false").sum()
oos_pct = round(100 * n_out / n_total, 1) if n_total else 0

print(f"\n── Snapshot Summary ───────────────────────────────────")
print(f"  In Stock:     {n_in:3d} / {n_total}")
print(f"  Out of Stock: {n_out:3d} / {n_total}")
print(f"  OOS Rate:     {oos_pct}%")

high_oos = new_df[(new_df["in_stock"] == "false") & (new_df["priority"] == "high")]
if not high_oos.empty:
    print(f"\n  ⚠  HIGH-PRIORITY OOS:")
    for _, r in high_oos.iterrows():
        print(f"     • {r['name']}")
else:
    print("\n  ✓ All high-priority starter sets are in stock.")
