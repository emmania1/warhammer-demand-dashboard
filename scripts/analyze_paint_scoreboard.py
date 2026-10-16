"""
analyze_paint_scoreboard.py
───────────────────────────
Weekly "paint scoreboard": units gone per store and sell-through by brand —
Tone Pro, Citadel Base/Layer, Army Painter (Warpaints Fanatic + classic Warpaints)
and Vallejo (Game Color, Xpress Color, Model Color) — at the stores that publish
unit counts. No network requests; reads data/ only; runs daily after the fetchers.

Inputs
  data/indie_paint_panel_daily.csv   daily counts at the 10 daily-count stores
                                      (exact counts only; capped "10+" counts ignored)
  data/page_qty_weekly.csv           product-page counts at the 30 weekly stores
  data/rival_paint_qty.csv           Army Painter / Vallejo counts (fetch_rival_paint_qty.py)

Method (same as the Tone Pro sell-down)
  position = count on hand + units on order (on order only at The Outpost)
  for each store × paint, between consecutive reads ≤ 10 days apart:
      gone     = fall in position     received = rise in position
  each interval is credited to the ISO week of its later read.
  per store × brand × week:  units gone, paints read, opening position, received
  per brand × week:          stores, median units gone per store, units gone per paint,
                             sell-through = Σ gone ÷ Σ (opening + received)

WHAT THIS IS: units leaving stock at stores that publish counts — sales, pre-orders,
cancellations and corrections alike, net of any restock between reads (so weekly
reads understate). Not sales. Before 24 Oct, Tone Pro falls are pre-orders.

Output: data/paint_scoreboard_store_week.csv, data/paint_scoreboard.csv
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
D = ROOT / "data"
PANEL, PAGES, RIVAL = D / "indie_paint_panel_daily.csv", D / "page_qty_weekly.csv", D / "rival_paint_qty.csv"
OUT_STORE, OUT = D / "paint_scoreboard_store_week.csv", D / "paint_scoreboard.csv"
MAX_GAP_DAYS = 10

BRAND = {"Tone Pro": "Tone Pro", "Base": "Citadel Base/Layer", "Layer": "Citadel Base/Layer",
         "Army Painter Fanatic": "Army Painter", "Army Painter Warpaints": "Army Painter",
         "Vallejo Game Color": "Vallejo", "Vallejo Xpress Color": "Vallejo", "Vallejo Model Color": "Vallejo"}
BRANDS = ["Tone Pro", "Citadel Base/Layer", "Army Painter", "Vallejo"]
STORE_COLS = ["iso_week", "store_id", "country", "brand", "paints", "reads", "opening", "received", "gone", "sell_through"]
COLS = ["iso_week", "week_start", "brand", "stores", "paints_per_store", "units_gone", "units_gone_per_store_median",
        "units_gone_per_store_mean", "units_gone_per_paint", "sell_through", "store_ids"]


def observations() -> pd.DataFrame:
    frames = []
    if PANEL.exists():
        p = pd.read_csv(PANEL, dtype=str, keep_default_na=False)
        p = p[(p["qty"] != "") & (p["qty_is_floor"] != "true")]
        frames.append(p[["date", "store_id", "country", "paint", "line", "qty", "on_order"]])
    if PAGES.exists():
        q = pd.read_csv(PAGES, dtype=str, keep_default_na=False)
        q = q[q["qty"] != ""]
        frames.append(q[["date", "store_id", "country", "paint", "line", "qty"]].assign(on_order=""))
    if RIVAL.exists():
        r = pd.read_csv(RIVAL, dtype=str, keep_default_na=False)
        r = r[(r["qty"] != "") & (r["qty_is_floor"] != "true")]
        frames.append(r[["date", "store_id", "country", "paint", "line", "qty", "on_order"]])
    if not frames:
        return pd.DataFrame()
    o = pd.concat(frames, ignore_index=True)
    o["brand"] = o["line"].map(BRAND)
    o = o.dropna(subset=["brand"])
    o["position"] = pd.to_numeric(o["qty"], errors="coerce") + pd.to_numeric(o["on_order"], errors="coerce").fillna(0)
    o = o.dropna(subset=["position"]).drop_duplicates(["store_id", "paint", "date"], keep="first")
    return o.sort_values(["store_id", "paint", "date"])


def store_weeks(o: pd.DataFrame) -> pd.DataFrame:
    g = o.groupby(["store_id", "paint"])
    o = o.assign(prev_pos=g["position"].shift(), prev_date=g["date"].shift())
    iv = o.dropna(subset=["prev_pos"]).copy()
    iv = iv[(pd.to_datetime(iv["date"]) - pd.to_datetime(iv["prev_date"])).dt.days <= MAX_GAP_DAYS]
    if iv.empty:
        return pd.DataFrame(columns=STORE_COLS)
    dp = iv["position"] - iv["prev_pos"]
    iv["gone"], iv["received"] = (-dp).clip(lower=0), dp.clip(lower=0)
    iv["iso_week"] = pd.to_datetime(iv["date"]).dt.strftime("%G-W%V")
    iv = iv.sort_values("date")
    first = iv.groupby(["iso_week", "store_id", "paint"])["prev_pos"].first().clip(lower=0).rename("opening").reset_index()
    sw = (iv.groupby(["iso_week", "store_id", "country", "brand"])
          .agg(paints=("paint", "nunique"), reads=("date", "nunique"), received=("received", "sum"), gone=("gone", "sum"))
          .reset_index())
    op = first.merge(iv[["iso_week", "store_id", "paint", "brand"]].drop_duplicates(), on=["iso_week", "store_id", "paint"])
    sw = sw.merge(op.groupby(["iso_week", "store_id", "brand"])["opening"].sum().reset_index(), on=["iso_week", "store_id", "brand"])
    sup = sw["opening"] + sw["received"]
    sw["sell_through"] = (sw["gone"] / sup.where(sup > 0)).round(3)
    return sw[STORE_COLS].sort_values(["iso_week", "brand", "store_id"])


def scoreboard(sw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (wk, brand), g in sw.groupby(["iso_week", "brand"]):
        sup = g["opening"].sum() + g["received"].sum()
        rows.append({"iso_week": wk, "week_start": pd.Timestamp.fromisocalendar(int(wk[:4]), int(wk[-2:]), 1).strftime("%Y-%m-%d"),
                     "brand": brand, "stores": g["store_id"].nunique(), "paints_per_store": float(g["paints"].median()),
                     "units_gone": int(g["gone"].sum()), "units_gone_per_store_median": float(g["gone"].median()),
                     "units_gone_per_store_mean": round(float(g["gone"].mean()), 1),
                     "units_gone_per_paint": round(float(g["gone"].sum() / g["paints"].sum()), 2) if g["paints"].sum() else None,
                     "sell_through": round(float(g["gone"].sum() / sup), 3) if sup > 0 else None,
                     "store_ids": "|".join(sorted(g["store_id"].unique()))})
    out = pd.DataFrame(rows, columns=COLS)
    if not out.empty:
        out["_b"] = out["brand"].map({b: i for i, b in enumerate(BRANDS)})
        out = out.sort_values(["iso_week", "_b"]).drop(columns="_b")
    return out


def main():
    o = observations()
    if o.empty:
        pd.DataFrame(columns=STORE_COLS).to_csv(OUT_STORE, index=False)
        pd.DataFrame(columns=COLS).to_csv(OUT, index=False)
        print("No count data yet."); return
    sw = store_weeks(o)
    sb = scoreboard(sw)
    sw.to_csv(OUT_STORE, index=False); sb.to_csv(OUT, index=False)
    print(f"Paint scoreboard — {len(o)} count reads, {o['store_id'].nunique()} stores, "
          f"brands seen: {o.groupby('brand')['store_id'].nunique().to_dict()}")
    for _, r in sb[sb["iso_week"] == sb["iso_week"].max()].iterrows() if not sb.empty else []:
        print(f"  {r['iso_week']} {r['brand']:20} stores={r['stores']:<3} gone/store(median)={r['units_gone_per_store_median']:<6} "
              f"per paint={r['units_gone_per_paint']} sell-through={r['sell_through']}")


if __name__ == "__main__":
    main()
