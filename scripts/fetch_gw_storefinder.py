"""
fetch_gw_storefinder.py
───────────────────────
Snapshots GW's public store finder (daily) (https://www.warhammer.com/api/storefinder),
the same JSON the store-finder page loads: every GW-operated store plus the
independent stockists GW chooses to list (~9K locations, ~12.7MB). One request.

Signals:
  • GW-operated store count, openings/closures by name and date
    (isWarHammerStore = true; validated: Jun-2025 snapshot = 571 vs FY25 AR 570)
  • "Coming soon" GW stores — listed before opening
  • Independent stockists listed + their paint-range commitment (stockRange):
        BSF            ≥20  Warhammer Colour paints
        P150/P210/P360 ≥N   Warhammer Colour paints
        …_T150         + 150 Warhammer Pro (Tone Pro) paints
    (labels from the store-finder page's own text; field added Apr–Oct 2026)

Limits: the indie list is GW's marketing directory, not its trade-account base
(Jun-2025 listed 6,246 vs ~8,100 independents in the FY25 report). stockRange is
the store's committed range, not stock on hand or sales. Nothing here is
per-store inventory.

Output:
  data/gw_storefinder_summary.csv  — one row per snapshot date
  data/gw_storefinder_country.csv  — one row per (date, country)
  data/gw_storefinder_roster.csv   — one row per location ever seen:
                                     first_seen / last_seen / first_seen_pro
  data/gw_storefinder_changes.csv  — GW-store adds/removals between snapshots

Usage:
  python scripts/fetch_gw_storefinder.py                     # live snapshot
  python scripts/fetch_gw_storefinder.py --backfill-wayback  # one-time: rebuild
        history from Wayback Machine captures (≤1 per month), then live snapshot
"""

import re, sys, gzip, json, time, argparse, requests
from pathlib import Path
from datetime import date

import pandas as pd

URL     = "https://www.warhammer.com/api/storefinder"
CDX     = "https://web.archive.org/cdx/search/cdx"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

ROOT        = Path(__file__).parent.parent
OUT_SUMMARY = ROOT / "data" / "gw_storefinder_summary.csv"
OUT_COUNTRY = ROOT / "data" / "gw_storefinder_country.csv"
OUT_ROSTER  = ROOT / "data" / "gw_storefinder_roster.csv"
OUT_CHANGES = ROOT / "data" / "gw_storefinder_changes.csv"
OUT_SUMMARY.parent.mkdir(exist_ok=True)

STOCK_RANGES = ["BSF", "P150", "P150_T150", "P210", "P210_T150", "P360", "P360_T150"]
TIER_RANK    = {"BSF": 0, "P150": 1, "P210": 2, "P360": 3}       # 20 / 150 / 210 / 360 Warhammer Colour pots

# Independent-stockist label tracking (daily). State files hold each stockist's
# label as of the previous and current snapshot DATE, so several runs on one day
# always compare against yesterday, never against an earlier run of the same day.
OUT_INDIE_CHANGES = ROOT / "data" / "gw_storefinder_indie_changes.csv"
OUT_INDIE_DAILY   = ROOT / "data" / "gw_storefinder_indie_changes_summary.csv"
STATE_CUR  = ROOT / "data" / "gw_storefinder_indie_state.csv"
STATE_PREV = ROOT / "data" / "gw_storefinder_indie_state_prev.csv"
STATE_COLS = ["key", "name", "city", "country", "lat", "lng", "stock_range", "as_of"]
CHANGE_TYPES = ["gained_pro", "lost_pro", "tier_up", "tier_down", "label_added", "label_removed",
                "new_stockist", "dropped_stockist", "relisted"]
COMING_SOON  = re.compile(
    r"coming soon|grand opening|opening soon|kommt bald|prochainement|bient[oô]t|"
    r"pr[oó]ximamente|presto|近日|오픈 예정", re.I)
ROSTER_COLS = ["key", "kind", "object_id", "store_id", "name", "city", "region",
               "country", "lat", "lng", "stock_range", "coming_soon",
               "first_seen", "last_seen", "first_seen_pro", "present"]


# ── Fetch ─────────────────────────────────────────────────────────────────────

def _decode(content: bytes) -> list:
    if content[:2] == b"\x1f\x8b":          # some Wayback captures are stored gzipped
        content = gzip.decompress(content)
    data = json.loads(content)
    if not isinstance(data, list) or not data or "isWarHammerStore" not in data[0]:
        raise ValueError("unexpected storefinder payload")
    return data


def fetch_live(retries: int = 3) -> list:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(URL, headers=HEADERS, timeout=90)
            r.raise_for_status()
            return _decode(r.content)
        except (requests.RequestException, ValueError) as e:
            print(f"  attempt {attempt}/{retries} failed: {e}")
            if attempt == retries:
                raise
            time.sleep(30 * attempt)


def wayback_captures() -> list[str]:
    """One successful capture per calendar month (earliest in month)."""
    r = requests.get(CDX, params={"url": "warhammer.com/api/storefinder", "output": "json",
                                  "filter": "statuscode:200", "fl": "timestamp",
                                  "collapse": "timestamp:6"}, timeout=60)
    r.raise_for_status()
    return [row[0] for row in r.json()[1:]]


def fetch_wayback(ts: str) -> list:
    r = requests.get(f"https://web.archive.org/web/{ts}id_/{URL}", timeout=180)
    r.raise_for_status()
    return _decode(r.content)


# ── Normalise ─────────────────────────────────────────────────────────────────

def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def location_key(s: dict) -> str:
    """GW stores: objectID (stable). Independents: objectIDs get re-issued
    between snapshots, so key on name + ~100m grid location instead."""
    if s.get("isWarHammerStore"):
        return f"gw:{s.get('objectID')}"
    g = s.get("_geoloc") or {}
    return f"in:{_norm(s.get('name'))}@{round(g.get('lat', 0) or 0, 3)},{round(g.get('lng', 0) or 0, 3)}"


def to_frame(stores: list) -> pd.DataFrame:
    rows = []
    for s in stores:
        gw   = bool(s.get("isWarHammerStore"))
        name = s.get("displayName") or s.get("name") or ""
        g    = s.get("_geoloc") or {}
        rows.append({
            "key":         location_key(s),
            "kind":        "gw" if gw else "indie",
            "object_id":   s.get("objectID", ""),
            "store_id":    s.get("storeId", "") or "",
            "name":        name,
            "city":        s.get("city", ""),
            "region":      s.get("isoRegionCode") or s.get("region") or "",
            "country":     s.get("countryCode", ""),
            "lat":         g.get("lat", ""),
            "lng":         g.get("lng", ""),
            "stock_range": s.get("stockRange", "") or "",
            "coming_soon": str(gw and bool(COMING_SOON.search(name))).lower(),
        })
    df = pd.DataFrame(rows).drop_duplicates("key", keep="first")
    df["is_pro"] = df["stock_range"].str.endswith("_T150")
    return df


# ── Record one snapshot ───────────────────────────────────────────────────────

def _upsert(path: Path, new: pd.DataFrame, snap_date: str) -> None:
    if path.exists():
        ex = pd.read_csv(path, dtype=str, keep_default_na=False)
        ex = ex[ex["date"] != snap_date]
        new = pd.concat([ex, new.astype(str)], ignore_index=True)
    new.sort_values([c for c in ("date", "country") if c in new.columns]).to_csv(path, index=False)


def record(df: pd.DataFrame, snap_date: str, source: str) -> None:
    gw, ind = df[df["kind"] == "gw"], df[df["kind"] == "indie"]
    soon = gw["coming_soon"] == "true"

    # Summary
    summ = {
        "date": snap_date, "source": source,
        "total_locations": len(df),
        "gw_stores": len(gw), "gw_open": int((~soon).sum()), "gw_coming_soon": int(soon.sum()),
        "indie_listed": len(ind),
        "indie_with_stock_range": int((ind["stock_range"] != "").sum()),
        "indie_pro_range": int(ind["is_pro"].sum()),
    }
    for sr in STOCK_RANGES:
        summ[f"sr_{sr.lower()}"] = int((ind["stock_range"] == sr).sum())
    _upsert(OUT_SUMMARY, pd.DataFrame([summ]), snap_date)

    # Per country
    c = df.groupby("country").agg(
        gw_stores=("kind", lambda k: int((k == "gw").sum())),
        indie_listed=("kind", lambda k: int((k == "indie").sum())),
        indie_pro_range=("is_pro", "sum"),
    ).reset_index()
    c.insert(0, "date", snap_date)
    _upsert(OUT_COUNTRY, c, snap_date)

    # Roster (first/last seen per location)
    roster = (pd.read_csv(OUT_ROSTER, dtype=str, keep_default_na=False)
              if OUT_ROSTER.exists() else pd.DataFrame(columns=ROSTER_COLS))
    prev_gw = set(roster.loc[(roster["kind"] == "gw") & (roster["present"] == "true"), "key"])
    roster = roster.set_index("key")
    cur = df.set_index("key")

    latest_seen = roster["last_seen"].max() if len(roster) else ""
    if latest_seen and snap_date < latest_seen:
        raise SystemExit(f"Snapshot {snap_date} is older than roster ({latest_seen}); "
                         f"backfill must run in date order before live snapshots.")

    attrs = ["kind", "object_id", "store_id", "name", "city", "region", "country",
             "lat", "lng", "stock_range", "coming_soon"]
    new_keys = cur.index.difference(roster.index)
    for k in new_keys:
        roster.loc[k, ROSTER_COLS[1:]] = [""] * (len(ROSTER_COLS) - 1)
        roster.loc[k, "first_seen"] = snap_date
    for k in cur.index:
        for a in attrs:
            roster.loc[k, a] = str(cur.at[k, a])
        roster.loc[k, "last_seen"] = snap_date
        if cur.at[k, "is_pro"] and not roster.at[k, "first_seen_pro"]:
            roster.loc[k, "first_seen_pro"] = snap_date
    roster["present"] = "false"
    roster.loc[cur.index, "present"] = "true"
    roster.reset_index()[ROSTER_COLS].sort_values(["kind", "country", "name"]).to_csv(OUT_ROSTER, index=False)

    # GW store changes vs previous snapshot
    cur_gw = set(gw["key"])
    if prev_gw:
        changes = []
        for k in sorted(cur_gw - prev_gw):
            r = cur.loc[k]
            changes.append({"date": snap_date, "change": "added", "store_id": r["store_id"],
                            "name": r["name"], "city": r["city"], "country": r["country"],
                            "coming_soon": r["coming_soon"]})
        for k in sorted(prev_gw - cur_gw):
            r = roster.loc[k]
            changes.append({"date": snap_date, "change": "removed", "store_id": r["store_id"],
                            "name": r["name"], "city": r["city"], "country": r["country"],
                            "coming_soon": r["coming_soon"]})
        if changes:
            _upsert(OUT_CHANGES, pd.DataFrame(changes), snap_date)
        n_add = len(cur_gw - prev_gw); n_rem = len(prev_gw - cur_gw)
    else:
        n_add = n_rem = 0

    record_indie_changes(df, snap_date)
    print(f"  {snap_date} [{source:7}] GW {summ['gw_stores']:4} ({summ['gw_coming_soon']} coming soon, "
          f"+{n_add}/-{n_rem})  indie {summ['indie_listed']:5}  Pro-range indies {summ['indie_pro_range']:5}")


# ── Independent stockist label changes ────────────────────────────────────────

def indie_changes(prev: pd.DataFrame, cur: pd.DataFrame, snap_date: str) -> pd.DataFrame:
    """Compare two snapshots of independent stockists (key, stock_range, …).
      gained_pro / lost_pro      _T150 (150 Warhammer Pro pots) added / removed
      tier_up / tier_down        Warhammer Colour range tier BSF(20) < P150 < P210 < P360
      label_added / _removed     stockRange field appears / disappears
      new / dropped_stockist     listing appears / disappears
      relisted                   a drop and a new listing in the same country within ~300m
                                 (renamed / re-keyed — not a real add or drop)"""
    P, C = prev.set_index("key"), cur.set_index("key")
    rows = []
    def add(change, r, a, b):
        rows.append({"date": snap_date, "change": change, "country": r["country"], "name": r["name"],
                     "city": r["city"], "from_range": a, "to_range": b})
    for k in P.index.intersection(C.index):
        a, b = P.at[k, "stock_range"], C.at[k, "stock_range"]
        if a == b:
            continue
        r = C.loc[k]
        if b.endswith("_T150") and not a.endswith("_T150"): add("gained_pro", r, a, b)
        if a.endswith("_T150") and not b.endswith("_T150"): add("lost_pro", r, a, b)
        ta, tb = TIER_RANK.get(a.split("_")[0]), TIER_RANK.get(b.split("_")[0])
        if ta is not None and tb is not None and ta != tb: add("tier_up" if tb > ta else "tier_down", r, a, b)
        if not a and b: add("label_added", r, a, b)
        if a and not b: add("label_removed", r, a, b)
    new_k, gone_k = list(C.index.difference(P.index)), list(P.index.difference(C.index))
    def ll(df, k): return float(df.at[k, "lat"] or 0), float(df.at[k, "lng"] or 0)
    relist_new, relist_gone = set(), set()
    for g in gone_k:
        for n in new_k:
            if n in relist_new or C.at[n, "country"] != P.at[g, "country"]:
                continue
            (y1, x1), (y2, x2) = ll(P, g), ll(C, n)
            if abs(y1 - y2) < 0.003 and abs(x1 - x2) < 0.003:
                relist_new.add(n); relist_gone.add(g)
                add("relisted", C.loc[n], P.at[g, "stock_range"], C.at[n, "stock_range"]); break
    for n in new_k:
        if n not in relist_new: add("new_stockist", C.loc[n], "", C.at[n, "stock_range"])
    for g in gone_k:
        if g not in relist_gone: add("dropped_stockist", P.loc[g], P.at[g, "stock_range"], "")
    return pd.DataFrame(rows, columns=["date", "change", "country", "name", "city", "from_range", "to_range"])


def record_indie_changes(df: pd.DataFrame, snap_date: str) -> None:
    ind = df[df["kind"] == "indie"].copy()
    ind["as_of"] = snap_date
    cur = ind[STATE_COLS].astype(str)
    if STATE_CUR.exists():
        last = pd.read_csv(STATE_CUR, dtype=str, keep_default_na=False)
        if last["as_of"].iloc[0] < snap_date:
            last.to_csv(STATE_PREV, index=False)                 # yesterday becomes the comparison base
    prev = pd.read_csv(STATE_PREV, dtype=str, keep_default_na=False) if STATE_PREV.exists() else None
    cur.to_csv(STATE_CUR, index=False)
    if prev is None or prev["as_of"].iloc[0] >= snap_date:
        print("  indie label changes: no earlier snapshot to compare yet"); return
    ch = indie_changes(prev, cur, snap_date)
    if OUT_INDIE_CHANGES.exists():
        old = pd.read_csv(OUT_INDIE_CHANGES, dtype=str, keep_default_na=False)
        ch = pd.concat([old[old["date"] != snap_date], ch.astype(str)], ignore_index=True)
    ch.to_csv(OUT_INDIE_CHANGES, index=False)
    today_ch = ch[ch["date"] == snap_date]
    cnt = (today_ch.groupby(["country", "change"]).size().unstack(fill_value=0)
           .reindex(columns=CHANGE_TYPES, fill_value=0))
    totals = cur.assign(pro=cur["stock_range"].str.endswith("_T150")).groupby("country").agg(
        indie_listed=("key", "size"), indie_pro_range=("pro", "sum"))
    daily = totals.join(cnt, how="left").fillna(0).astype(int).reset_index()
    daily.insert(0, "date", snap_date); daily.insert(2, "since", prev["as_of"].iloc[0])
    if OUT_INDIE_DAILY.exists():
        old = pd.read_csv(OUT_INDIE_DAILY, dtype=str, keep_default_na=False)
        daily = pd.concat([old[old["date"] != snap_date], daily.astype(str)], ignore_index=True)
    daily.to_csv(OUT_INDIE_DAILY, index=False)
    tot = today_ch["change"].value_counts()
    print(f"  indie label changes since {prev['as_of'].iloc[0]}: " +
          ", ".join(f"{c} {int(tot.get(c, 0))}" for c in CHANGE_TYPES if tot.get(c, 0)))


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-wayback", action="store_true",
                    help="one-time: replay monthly Wayback captures before the live snapshot")
    args = ap.parse_args()

    print(f"GW Store Finder snapshot — {date.today()}")

    if args.backfill_wayback:
        for p in (OUT_SUMMARY, OUT_COUNTRY, OUT_ROSTER, OUT_CHANGES):
            if p.exists():
                sys.exit(f"{p.relative_to(ROOT)} already exists — backfill only runs on empty history.")
        caps = wayback_captures()
        print(f"  Wayback: {len(caps)} monthly captures")
        for ts in caps:
            snap_date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            try:
                record(to_frame(fetch_wayback(ts)), snap_date, "wayback")
            except Exception as e:
                print(f"  {snap_date} [wayback] skipped: {e}")
            time.sleep(5)    # polite to archive.org

    record(to_frame(fetch_live()), str(date.today()), "live")

    print(f"\n✓ {OUT_SUMMARY.relative_to(ROOT)}, {OUT_COUNTRY.name}, {OUT_ROSTER.name}, {OUT_CHANGES.name}")
