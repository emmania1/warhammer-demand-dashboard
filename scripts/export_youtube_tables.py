import pandas as pd
from pathlib import Path

INFILE = Path("data/youtube_channels_daily.csv")
OUTDIR = Path("exports")
OUTDIR.mkdir(exist_ok=True)

df = pd.read_csv(INFILE)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["channel_id", "date"])

latest = df["date"].max()
prev = latest - pd.Timedelta(days=7)

# latest snapshot
latest_df = df[df["date"] == latest].copy()

# nearest snapshot >= 7 days ago (if exists)
prev_df = df[df["date"] <= prev].sort_values("date").groupby("channel_id").tail(1).copy()

out = latest_df.merge(prev_df[["channel_id","subscribers","views","videos"]], on="channel_id", how="left", suffixes=("", "_prev"))

out["subs_delta_7d"] = out["subscribers"] - out["subscribers_prev"]
out["views_delta_7d"] = out["views"] - out["views_prev"]

# if prev doesn't exist yet, deltas will be NaN
out.to_csv(OUTDIR / "youtube_channels_latest_with_7d_delta.csv", index=False)
print(f"Saved → {OUTDIR / 'youtube_channels_latest_with_7d_delta.csv'}")
print(f"Latest date → {latest.date()}")
