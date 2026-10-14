# Source audit — per-store Tone Pro inventory and sell-through

Tested 2026-10-14. Public data only: no logins, carts, accounts or API keys we don't hold;
robots.txt checked before every request; anything that blocked or challenged us was dropped,
not worked around. Request counts are what the test used.

**Goal:** per-store Tone Pro inventory, sell-through, and how they relate.
**Starting point:** 13 stores with counts — Firestorm, The Outpost (+ on-order), Element Games
(capped 10+), Loaded Dice, Beanie Games, Battle City (low-stock only) [UK]; Nutmeg, Games A Plunder
[US], Pastime Sports, Jeux AZ [CA] (per-colour, built 2026-10-14, off); Armada, Haunted Game Cafe,
Gamers Grove [US] (weekly product pages, built, off).

Usefulness: 5 = per-store unit counts at scale · 1 = no usable signal.

## Results by source

| # | Source | What it shows | Per store? | Quantities? | Coverage | Request cost | Score |
|---|---|---|---|---|---|---|---|
| 1 | **GW webstore, US index** (tracking now) | In stock / selling fast / last chance per SKU; pre-order flag; purchase limit | No — Memphis warehouse | No | All 152 Pro SKUs | 1/day | 3 |
| 2 | **GW regional indexes** (en-GB, de-DE, fr-FR, es-ES, it-IT, en-AU, en-NZ, en-CA, en-WW, en-EU) | Same flags, from **three warehouses**: Memphis (US/CA), Lenton (UK/EU/WW), Ingleburn (AU/NZ). In-stock paints today: AU 400, US 328, UK 318 | No — per warehouse | No | 3 warehouses × 152 SKUs | 1/day per warehouse (3) | 3 |
| 3 | GW Japan webstore | No product index (404) | — | — | — | — | 1 |
| 4 | **GW store finder** (tracking weekly) | Every GW store + listed independents; `stockRange` shows which independents committed to the 150-pot Pro range (3,025 on 13 Oct) | Yes | No (range commitment, not stock) | ~600 GW stores, ~8,500 independents | 1/week (12.7 MB) | 3 |
| 5 | GW store pages / mobile apps / click-and-collect | Store hours, events; "deliver to store" ships from the warehouse. No stock check or in-store availability found in site code or app descriptions. Apps couldn't be run here | — | No | — | — | 1 |
| 6 | GW checkout system (`inventoryEntries`) | Inventory by supply channel (warehouse), behind a checkout session token | — | — | — | Not used — non-public | n/a |
| 7 | US distributors (Alliance, ACD, GTS) | GW sells mostly direct to ~9,100 trade accounts; distributors are a minor channel. GTS catalogue is login-only; ACD shows no public catalogue; Alliance's site failed a certificate check | — | — | — | — | 1 |
| 8 | Amazon | Tone Pro not listed. Product pages reachable for a GW set but showed no "bought in past month" badge | No | No | — | 1/ASIN | 1 now |
| 9 | Keepa (Amazon history) | Would give price/offer history and Amazon's "X+ bought in past month" — a real sales signal — per ASIN. **Our key's plan has lapsed** (HTTP 402); re-subscribing is €49/month | No (marketplace) | Sales bands, not stock | Only if GW/resellers list Tone Pro on Amazon | Tokens | 2 (if subscribed and listed) |
| 10 | eBay sold listings | robots.txt disallows search pages; listing page returned 403. Official sold-data API needs a developer account | — | — | — | — | 1 |
| 11 | Price comparison (PriceRunner, PriceSpy, Idealo, Google Shopping) | Search pages disallowed (or 403); PriceSpy product data loads client-side; no Tone Pro listings | — | — | — | — | 1 |
| 12 | TCGplayer | Client-rendered; no Citadel products visible; API needs a key | — | — | — | — | 1 |
| 13 | **Shopify `products.json`** (panel, daily) | Listed / available per paint, date listed, price, SKU | Yes | No | ~120 stockists found; 60 in panel | 2–6/store/day | 4 |
| 14 | **Shopify collection pages** ("N in stock" in the theme) | Count per paint on listing pages | Yes | Yes | 3 of 60 panel stores (Loaded Dice, Beanie, Battle City-low) | 5–15/store/day | 4 |
| 15 | **Shopify colour-variant products** (one product, all colours as variants) | Count per colour from one page | Yes | Yes, exact | 4 of 119 scanned (Nutmeg, Games A Plunder, Pastime, Jeux AZ) | 1 page per range (≈3–4/store/day) | 5 (few stores) |
| 16 | **Shopify product pages** (embedded `inventory_quantity` / "Only X left") | Exact count per paint, incl. negatives (orders beyond stock) | Yes | Yes, exact | **~half of Shopify stockists** (~25 of 56 panel stores show a real count; each needs a one-off check that the number belongs to the page's own product — done for 3) | 1 page per SKU — 150/store for full Tone Pro | 5 (cost-limited) |
| 17 | WooCommerce Store API | In stock yes/no; stock text only if the store displays it (census: 2 of 10 Woo stockists list GW paint; text "In Stock!" only) | Yes | Rarely | Few | 1–3/store/day | 2 |
| 18 | **CrystalCommerce** (game-store platform) | "N In Stock" printed in search/listing results | Yes | Yes | ~1% of stockist domains (census: 3 of 300) | ~1 listing page per range | 4 (few stores) |
| 19 | **Lightspeed** | Category JSON: available yes/no; product JSON: **exact stock level** (`stock.level`) | Yes | Yes (per product) | ~1% (3 of 300); Discount Games, Jeux Jubes | 1/SKU for counts | 3 |
| 20 | BigCommerce | No counts on listing pages tested; inventory only via the storefront API token | Yes | No (public HTML) | ~1% | — | 1 |
| 21 | Square Online | Pages client-rendered; no counts in HTML; sitemap lists every product (shows *when* Tone Pro is added) | Yes | No | ~2% (5 of 300) | 1 sitemap/store | 2 |
| 22 | Wix, Squarespace, GoDaddy sites | No public product data | — | No | ~7% | — | 1 |
| 23 | Reddit / Discord / store social posts | "Sold out" / "restocked" reports — qualitative, dated | Sometimes | No | Patchy | Low | 2 |

### Platform mix of independent stockists (census)
300 random guessed domains of Pro-range stockists (US/UK/CA): 56% no site at that name; of the 131 live
sites, 46 mention Warhammer — Shopify 11, WooCommerce 6, Square 4, Lightspeed 3, BigCommerce 3, Wix 3,
CrystalCommerce 2, other ~14. Three of the 11 Shopify sites sell GW paint online with collection names my
first scan missed (Tyton Games 219 paints, Game Realm 79, Cardrade 28) — a broader collection match should
add ~20–25 Shopify stores.

## How inventory and sell-through relate (what each signal can and can't tell us)

- **Stock on hand** (sources 14–19): units on the shelf on a given day.
- **Receipts**: only The Outpost publishes units on order; elsewhere a delivery shows up as a rise in stock.
- **Outflow** = receipts − change in stock. With daily counts and on-order data (The Outpost) this is a
  good estimate of units leaving; with counts only it is a floor (a restock between reads hides sales);
  with weekly counts it can't separate restocks from sales within the week.
- **Sell-through rate** per store ≈ outflow ÷ (opening stock + receipts) over a window.
- Pre-launch, Shopify counts on pre-order items are allocations/pre-orders, not shelf stock; negative
  counts are orders taken beyond stock — themselves a demand signal.
- None of this is sales: outflow includes pre-order fulfilment, transfers and corrections.

## Recommendation

1. **Shopify product-page counts, sampled** (source 16) — the only way to get exact counts at scale.
   Read 30 Tone Pro pages per store weekly (tone 3 of each of the 30 colours; or all 150 for a few
   anchor stores) at ~30 Shopify stores that embed counts → ~900 requests/week (~30/store/week).
   Biggest gain in US coverage.
2. **Keep and switch on the cheap daily sources**: the 6 UK listing-count stores, the 4 colour-variant
   stores (+ re-scan 26 Oct), weekly Armada/Haunted/Gamers Grove.
3. **Add GW's other two warehouses** (Lenton, Ingleburn) to the daily paint tracker — 2 requests/day —
   so GW's own sell-outs can be compared across US / UK-EU / AU.
4. **Add CrystalCommerce and Lightspeed stockists** where found (cheap listing counts / exact JSON).
5. **Widen Shopify discovery** with broader collection names (+20–25 stores) and promote reserves.
6. **Daily cadence where it's cheap, weekly where it isn't**; use The Outpost (daily, with on-order) as
   the calibration store for how deliveries turn into stock and sell down.
7. Skip: distributors, eBay, price-comparison sites, TCGplayer, GW apps. Keepa only if Tone Pro appears
   on Amazon and the subscription is worth €49/month.

Likely outcome: ~40–50 stores with counts (≈15 daily, ≈30 weekly sampled), ~20 of them US, plus GW
warehouse availability in three regions and listing/availability at ~80 stores.

## Addendum (2026-10-14): store-finder `stockRange` as the "store label"

Daily diffs of the public store finder show labels change day to day, in regional batches:
13→14 Oct, 40 independents gained `_T150` (Pro) — 29 AU, 8 NZ, 3 KR — 3 AU lost it, 3 moved up a tier;
157 dropped / 47 new listings, mostly small 20-pot stockists in Europe (directory churn), 6 re-listings.
The field is absent from every archived store list (Jun 2025 – Apr 2026; no later copy). A June 2026
archived store-finder page already had untranslated placeholder labels for tiers P150/P300/P450/P510 and
no Pro label, so the current scheme (BSF/P150/P210/P360 + `_T150`) arrived between June and October —
around the Tone Pro announcement. No labelled history exists for past launches.

Interpretation: `_T150` most plausibly marks accounts GW's trade system records as taking the 150-pot
Pro range (rack). Daily `+Pro` counts ≈ accounts newly ranged; tier moves ≈ Colour rack size changes.
It does not show units received, reorders or sell-through, and covers only listed accounts
(~8,400 of ~9,100). Tracked daily by scripts/fetch_gw_storefinder.py → gw_storefinder_indie_changes*.csv.
