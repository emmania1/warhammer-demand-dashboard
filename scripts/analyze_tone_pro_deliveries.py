"""
analyze_tone_pro_deliveries.py
──────────────────────────────
Turns the store-level unit counts into Tone Pro delivery, pack-size and reorder
estimates. No network requests — reads data/ only; runs daily after the fetchers.

Inputs
  data/indie_paint_panel_daily.csv   daily counts at the 10 daily-count stores
                                      (exact counts only; "10+" floors ignored)
  data/page_qty_weekly.csv           product-page counts at 30 stores (weekly,
                                      daily subset during the launch window)
  data/gw_storefinder_country.csv    Pro-label (_T150) stockists by country

How a delivery shows up
  Stores take pre-orders one of two ways:
   (a) load the expected allocation as stock before launch → count is already
       there and falls as pre-orders sell; the delivery itself shows no jump.
       Allocation ≈ the pre-launch peak.
   (b) sell beyond stock → count goes negative, then jumps on delivery.
       Allocation ≈ the size of the jump.
  So per store × paint:  allocation_obs = max(pre-launch peak count,
                                              largest rise in the launch window)

Outputs
  data/tone_pro_receipts.csv      every rise in a count: date, store, paint, from → to,
                                  type = prelaunch_update | launch_delivery | reorder
  data/tone_pro_pack_test.csv     per store: paints observed, most common allocation,
                                  share of paints at that number → standard pack yes/no
  data/tone_pro_units_estimate.csv by country: Pro-label stores × 150 pots × pack size
                                  (low / mid / high from the tested stores)
  data/tone_pro_reorders.csv      per store × ISO week: reorder events and units
  data/tone_pro_sellthrough.csv   per store: opening stock, received, units gone, on hand, sell-through

WHAT THIS IS: an estimate from ~40 online-active stores, extrapolated to every
stockist GW labels as carrying the Pro range. Rises in a count can also be
returns or corrections; weekly reads net restocks against sales.
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
D = ROOT / "data"
PANEL, PAGES, SF_COUNTRY = D / "indie_paint_panel_daily.csv", D / "page_qty_weekly.csv", D / "gw_storefinder_country.csv"
OUT_REC, OUT_PACK = D / "tone_pro_receipts.csv", D / "tone_pro_pack_test.csv"
OUT_EST, OUT_REORD = D / "tone_pro_units_estimate.csv", D / "tone_pro_reorders.csv"
OUT_SELL = D / "tone_pro_sellthrough.csv"
PREORDERS_OPEN = "2026-10-10"

LAUNCH          = "2026-10-24"
WINDOW          = ("2026-10-20", "2026-10-31")   # launch deliveries land in here
POTS_PER_RACK   = 150                            # 30 colours × 5 tones
MIN_PAINTS      = 5                              # paints needed to test a store's pack
STANDARD_SHARE  = 0.7                            # ≥70% of paints at one number → standard pack
MIN_STORES      = 5                              # tested stores needed before any extrapolation
EST_COLS = ["country", "pro_label_stores", "pack_basis", "pots_per_paint_low", "pots_per_paint_mid",
            "pots_per_paint_high", "units_low", "units_mid", "units_high"]


def observations() -> pd.DataFrame:
    frames = []
    if PANEL.exists():
        p = pd.read_csv(PANEL, dtype=str, keep_default_na=False)
        p = p[(p["qty"] != "") & (p.get("qty_is_floor", "") != "true")]
        frames.append(p[["date", "store_id", "country", "paint", "line", "qty"]].assign(source="panel",
                      on_order=p.get("on_order", "")))
    if PAGES.exists():
        q = pd.read_csv(PAGES, dtype=str, keep_default_na=False)
        q = q[q["qty"] != ""]
        frames.append(q[["date", "store_id", "country", "paint", "line", "qty"]].assign(source="page", on_order=""))
    if not frames:
        return pd.DataFrame()
    o = pd.concat(frames, ignore_index=True)
    o["qty"] = pd.to_numeric(o["qty"], errors="coerce")
    o["on_order"] = pd.to_numeric(o["on_order"], errors="coerce")
    o = o.dropna(subset=["qty"]).sort_values(["store_id", "paint", "date", "source"])
    return o.drop_duplicates(["store_id", "paint", "date"], keep="first")      # panel first if both


def receipts(o: pd.DataFrame) -> pd.DataFrame:
    g = o.groupby(["store_id", "paint"])
    o = o.assign(prev_date=g["date"].shift(), prev_qty=g["qty"].shift(), prev_oo=g["on_order"].shift())
    o = o.dropna(subset=["prev_qty"])
    # A rise in stock, or (The Outpost) a fall in units on order, whichever is larger
    o["received"] = pd.concat([o["qty"] - o["prev_qty"], (o["prev_oo"] - o["on_order"]).fillna(0)], axis=1).max(axis=1)
    r = o[o["received"] > 0].copy()
    first_launch = (r[(r["date"] >= WINDOW[0]) & (r["date"] <= WINDOW[1])]
                    .groupby("store_id")["date"].min())
    def kind(row):
        if row["date"] < WINDOW[0]:
            return "prelaunch_update"
        if row["date"] <= WINDOW[1]:
            return "launch_delivery"
        return "reorder"
    r["type"] = r.apply(kind, axis=1)
    # A second rise for the same paint inside the window, after the store's first delivery day → reorder
    fl = r["store_id"].map(first_launch)
    early_reorder = (r["type"] == "launch_delivery") & r.duplicated(["store_id", "paint"], keep="first") & (r["date"] > fl)
    r.loc[early_reorder & (r["date"] > LAUNCH), "type"] = "reorder"
    r["gap_days"] = (pd.to_datetime(r["date"]) - pd.to_datetime(r["prev_date"])).dt.days
    cols = ["date", "prev_date", "gap_days", "store_id", "country", "paint", "line", "prev_qty", "qty", "received", "type", "source"]
    return r[cols].sort_values(["date", "store_id", "paint"])


def pack_test(o: pd.DataFrame, rec: pd.DataFrame) -> pd.DataFrame:
    tp = o[o["line"] == "Tone Pro"]
    pre = tp[tp["date"] < LAUNCH].groupby(["store_id", "paint"])["qty"].max()
    lr = rec[(rec["line"] == "Tone Pro") & (rec["type"] == "launch_delivery")].groupby(["store_id", "paint"])["received"].max()
    alloc = pd.concat([pre.rename("pre_peak"), lr.rename("launch_rise")], axis=1).fillna(0)
    alloc["allocation_obs"] = alloc[["pre_peak", "launch_rise"]].max(axis=1)
    alloc = alloc[alloc["allocation_obs"] > 0].reset_index()
    rows = []
    country = o.drop_duplicates("store_id").set_index("store_id")["country"]
    for sid, g in alloc.groupby("store_id"):
        v = g["allocation_obs"].round().astype(int)
        mode = int(v.mode().iloc[0]); share = float((v == mode).mean())
        rows.append({"store_id": sid, "country": country.get(sid, ""), "paints_observed": len(v),
                     "mode_units": mode, "share_at_mode": round(share, 2),
                     "median_units": float(v.median()), "min_units": int(v.min()), "max_units": int(v.max()),
                     "standard_pack": str(len(v) >= MIN_PAINTS and share >= STANDARD_SHARE).lower(),
                     "evidence": "launch rise" if g["launch_rise"].gt(0).any() else "pre-launch stock only"})
    return pd.DataFrame(rows)


def units_estimate(pack: pd.DataFrame) -> pd.DataFrame:
    if pack.empty or not SF_COUNTRY.exists():
        return pd.DataFrame(columns=EST_COLS)
    sf = pd.read_csv(SF_COUNTRY, dtype=str, keep_default_na=False)
    sf = sf[sf["date"] == sf["date"].max()]
    sf["indie_pro_range"] = pd.to_numeric(sf["indie_pro_range"], errors="coerce").fillna(0).astype(int)
    tested = pack[pack["paints_observed"] >= MIN_PAINTS]
    if len(tested) < MIN_STORES:
        print(f"  units estimate: only {len(tested)} store(s) tested — need {MIN_STORES} before extrapolating")
        return pd.DataFrame(columns=EST_COLS)
    per_store = tested["median_units"]                     # pots per paint at each tested store
    allq = per_store.quantile([0.25, 0.5, 0.75]) if len(per_store) else None
    rows = []
    for _, c in sf[sf["indie_pro_range"] > 0].iterrows():
        loc = tested[tested["country"] == c["country"]]["median_units"]
        q = loc.quantile([0.25, 0.5, 0.75]) if len(loc) >= 3 else allq
        basis = f"{len(loc)} {c['country']} stores" if len(loc) >= 3 else f"all {len(per_store)} tested stores"
        if q is None:
            continue
        n = int(c["indie_pro_range"])
        rows.append({"country": c["country"], "pro_label_stores": n, "pack_basis": basis,
                     "pots_per_paint_low": q[0.25], "pots_per_paint_mid": q[0.5], "pots_per_paint_high": q[0.75],
                     "units_low": int(n * POTS_PER_RACK * q[0.25]), "units_mid": int(n * POTS_PER_RACK * q[0.5]),
                     "units_high": int(n * POTS_PER_RACK * q[0.75])})
    est = pd.DataFrame(rows).sort_values("pro_label_stores", ascending=False)
    if not est.empty:
        tot = {"country": "ALL", "pro_label_stores": int(est["pro_label_stores"].sum()), "pack_basis": "sum of countries"}
        for c in ("units_low", "units_mid", "units_high"):
            tot[c] = int(est[c].sum())
        est = pd.concat([est, pd.DataFrame([tot])], ignore_index=True)
    return est


def reorders(rec: pd.DataFrame) -> pd.DataFrame:
    r = rec[(rec["type"] == "reorder") & (rec["line"] == "Tone Pro")].copy()
    if r.empty:
        return pd.DataFrame(columns=["iso_week", "store_id", "country", "paints_restocked", "units", "first_date"])
    r["iso_week"] = pd.to_datetime(r["date"]).dt.strftime("%G-W%V")
    return (r.groupby(["iso_week", "store_id", "country"])
            .agg(paints_restocked=("paint", "nunique"), units=("received", "sum"), first_date=("date", "min"))
            .reset_index())


def sellthrough(o: pd.DataFrame) -> pd.DataFrame:
    """Per store: Tone Pro units gone and sell-through since pre-orders opened.
      each interval: received = max(rise in count, fall in on-order, 0)
                     gone     = max(received − change in count, 0)
      gone also includes pre-orders taken before tracking began (a count below zero
      at the first observation = units already sold, not yet delivered).
      sell-through = gone ÷ (opening stock + received)."""
    t = o[(o["line"] == "Tone Pro") & (o["date"] >= PREORDERS_OPEN)].sort_values(["store_id", "paint", "date"])
    if t.empty:
        return pd.DataFrame(columns=["store_id", "country", "paints", "opening", "received", "gone", "on_hand",
                                     "sell_through", "first_date", "last_date", "days"])
    g = t.groupby(["store_id", "paint"])
    dq = t["qty"] - g["qty"].shift()
    oo = (g["on_order"].shift() - t["on_order"]).fillna(0)
    rec = pd.concat([dq, oo], axis=1).max(axis=1).clip(lower=0).fillna(0)
    gone = (rec - dq).clip(lower=0).fillna(0)
    t = t.assign(received=rec, gone=gone)
    per = t.groupby(["store_id", "paint"]).agg(country=("country", "first"), first_qty=("qty", "first"),
            last_qty=("qty", "last"), received=("received", "sum"), gone=("gone", "sum"),
            first_date=("date", "first"), last_date=("date", "last")).reset_index()
    per["gone"] += (-per["first_qty"]).clip(lower=0)                # pre-orders already taken
    per["opening"] = per["first_qty"].clip(lower=0)
    st = per.groupby(["store_id", "country"]).agg(paints=("paint", "nunique"), opening=("opening", "sum"),
            received=("received", "sum"), gone=("gone", "sum"), on_hand=("last_qty", "sum"),
            first_date=("first_date", "min"), last_date=("last_date", "max")).reset_index()
    supply = st["opening"] + st["received"]
    st["sell_through"] = (st["gone"] / supply.where(supply > 0)).round(3)
    st["days"] = (pd.to_datetime(st["last_date"]) - pd.to_datetime(st["first_date"])).dt.days
    return st


def main():
    o = observations()
    if o.empty:
        print("No count data yet."); return
    rec = receipts(o)
    pack = pack_test(o, rec)
    est = units_estimate(pack)
    reo = reorders(rec)
    sell = sellthrough(o)
    sell.to_csv(OUT_SELL, index=False)
    rec.to_csv(OUT_REC, index=False); pack.to_csv(OUT_PACK, index=False)
    est.to_csv(OUT_EST, index=False); reo.to_csv(OUT_REORD, index=False)
    print(f"Tone Pro deliveries — {len(o)} count observations, {o['store_id'].nunique()} stores")
    print(f"  receipts: {rec['type'].value_counts().to_dict()}")
    if not pack.empty:
        std = pack[pack["standard_pack"] == "true"]
        print(f"  pack test: {len(pack)} stores with Tone Pro counts; {len(std)} look like a standard pack; "
              f"pots per paint (median by store): {sorted(pack['median_units'].tolist())}")
    if not est.empty:
        a = est[est["country"] == "ALL"].iloc[0]
        print(f"  units estimate, all Pro-label stores: {a['units_low']:,} – {a['units_mid']:,} – {a['units_high']:,}")
    print(f"  reorders: {len(reo)} store-weeks")
    if not sell.empty:
        print(f"  sell-through: {len(sell)} stores; median {sell['sell_through'].median():.0%} "
              f"(units gone {int(sell['gone'].sum()):,} of {int((sell['opening'] + sell['received']).sum()):,} supplied)")


if __name__ == "__main__":
    main()
