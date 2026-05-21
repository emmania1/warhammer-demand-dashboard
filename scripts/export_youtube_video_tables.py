import pandas as pd
from pathlib import Path

INFILE = Path("data/youtube_videos_daily.csv")
OUTDIR = Path("exports")
OUTDIR.mkdir(exist_ok=True)

df = pd.read_csv(INFILE)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["video_id", "date"])

latest = df["date"].max()
prev = latest - pd.Timedelta(days=7)

latest_df = df[df["date"] == latest].copy()

prev_df = (
    df[df["date"] <= prev]
    .sort_values("date")
    .groupby("video_id")
    .tail(1)
    .copy()
)

out = latest_df.merge(
    prev_df[["video_id","views","likes","comments"]],
    on="video_id",
    how="left",
    suffixes=("", "_prev")
)

out["views_delta_7d"] = out["views"] - out["views_prev"]
out["likes_delta_7d"] = out["likes"] - out["likes_prev"]
out["comments_delta_7d"] = out["comments"] - out["comments_prev"]

out.to_csv(OUTDIR / "youtube_videos_latest_with_7d_delta.csv", index=False)

print("Saved →", OUTDIR / "youtube_videos_latest_with_7d_delta.csv")
print("Latest date →", latest.date())
