# Independent online availability panel — how stores were found

Last used 2026-10-13. Re-run with `scripts/discover_indie_shopify.py` when expanding the panel.

## What worked: store-finder name → web address

GW's public store finder (`https://www.warhammer.com/api/storefinder`) lists every independent
stockist with its name, address and paint-range code, but no website. Guessing the website from
the name worked far better than web search:

1. **Start from the store finder.** On 2026-10-13: 3,041 independents with the Warhammer Pro range
   (`stockRange` ending `_T150`), ~1,900 of them in the US, UK and Canada.
2. **Name → slug → domain.** Lower-case, drop `LLC/Inc/Ltd/the/and/&`, cut anything after `" - "`
   (location suffixes like "GAME UNIVERSE - FRANKLIN"), strip non-letters. Try `.com` (US),
   `.co.uk` + `.com` (UK), `.ca` + `.com` (Canada). → 2,273 candidate domains.
3. **Is it a Shopify shop selling GW paint?** `robots.txt`, then `/collections.json`; keep sites with a
   collection named for Citadel / Warhammer Colour / Tone Pro. At most 2 requests per host.
   → **134 sites**.
4. **Is it the same business?** Shopify's public `/meta.json` gives the shop's own city and country;
   compare with the store-finder entry. Mismatches are dropped; a country-only match is kept but
   flagged.
5. **Does the data work?** Trial-read the paint collections with the panel fetcher and count paints
   that match GW's own Base / Layer / Tone Pro names. ≥60 Base/Layer = usable.
   → 96 domains (≈88 stores after merging `.ca`/`.com` duplicates) passed; 60 were chosen
   (20 per country) and the rest kept as reserves in `config/indie_paint_panel.csv` (`active=false`).

Web search, by comparison, found a website for 9 of a random 50 stockists and usable data for 2.
Several of those "no website" stores (e.g. Retrofix Games, Riftgate) turned up with this method.

## What it misses

- Stores whose domain isn't their name (e.g. `ggportland.com` for Guardian Games), or that use a
  different TLD. A second pass could try `games`/`hobbies` suffixes or the city name.
- Non-Shopify shops (WooCommerce, BigCommerce, Lightspeed, custom). These need their own adapter;
  the panel has hand-built ones for Element Games, Firestorm, The Outpost and Discount Games Inc.
- Stockists that don't sell online at all — the majority. That is why the panel skews to
  online-active stores and is not a sample of all stockists.

## Large retailers

Found by product search (and kept regardless of store-finder listing): Element Games, Firestorm,
The Outpost, Travelling Man, Loaded Dice, Goblin Gaming, Total Cards, Jadlam, 401 Games, Abyss,
Tabletop Heaven, Armada, Mox Boarding House, Discount Games Inc.

Checked 2026-10-13 and **not** usable without one request per product: Miniature Market (Magento;
listing shows in/pre-order only), Noble Knight, Atomic Empire, GameNerdz (BigCommerce; inventory is
only in the storefront API, not the page). Imaginaire and Whistle-Stop returned 403 to plain
requests and were excluded.

## Quantities

Only a few stores publish counts on listing pages: Firestorm (exact), Element Games (capped "10+"),
The Outpost (exact + "On The Way" units on order — the only on-order figure found), Loaded Dice and
Beanie Games ("N in stock" on collection pages), Battle City ("Only N left" when low). About half of
the Shopify panel stores show a count on individual product pages, but reading those would mean
~150–300 requests per store per day, so they are not used.

## Etiquette

Public pages only; no logins, carts or tokens. robots.txt checked for every URL (RFC 9309 longest
match). One store at a time in the daily run, ~2s between requests. User-Agent carries a contact
label. A 401/403/429 or bot challenge marks the store blocked — never worked around.
