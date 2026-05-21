"""
Warhammer Demand Intelligence — Ecosystem Summary Generator.

Aggregates all data sources into weekly_summary.json.
Strategic focus: YoY structural audience growth, creator ecosystem expansion,
digital gaming base, new player funnel signals, retail/supply signals.

Google Trends removed. Short-term weekly noise removed.
"""

import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

DATA_DIR = "data"
HISTORY_FILE        = os.path.join(DATA_DIR, "reddit_history_daily.csv")
YT_CHANNELS_FILE    = os.path.join(DATA_DIR, "youtube_channels_daily.csv")
YT_VIDEOS_FILE      = os.path.join(DATA_DIR, "youtube_videos_unified.csv")
STEAM_FILE          = os.path.join(DATA_DIR, "steam_metrics_daily.csv")
WARCOM_FILE         = os.path.join(DATA_DIR, "warcom_news_daily.csv")
REDDIT_MEMBERS_FILE = os.path.join(DATA_DIR, "reddit_members_weekly.csv")
COMPETITIVE_FILE    = os.path.join(DATA_DIR, "competitive_events.csv")
RETAIL_FILE         = os.path.join(DATA_DIR, "retail_signals.csv")
OUTPUT_FILE         = "weekly_summary.json"

# ── Keyword lists ──────────────────────────────────────────────────────────────

TRAILER_KW = [
    "trailer", "gameplay trailer", "launch trailer", "reveal trailer",
    "gameplay reveal", "official reveal", "preview", "teaser", "announce",
    "reveal", "gameplay footage", "cinematic",
]

BEGINNER_KW = [
    "beginner", "starter", "getting started", "first army",
    "start collecting", "how to start", "new player",
    "new to warhammer", "starting warhammer", "beginners guide",
    "starter set", "complete guide", "introduction to warhammer",
    "getting into warhammer", "new to 40k", "start playing",
]

SUPPLY_SIGNAL_KW = [
    "sold out", "out of stock", "sold through", "flying off", "back in stock",
    "restock", "allocation", "inventory", "demand is", "we can't keep",
    "pre-order", "preorder", "order now", "limited stock",
]


def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def percent_change(new, old):
    if old is None or old == 0:
        return None
    return float((new - old) / old * 100)


def compute_30d_structural(df, col):
    df = df.sort_values("date")
    if len(df) < 28:
        return None
    first_half  = df[col].iloc[:14].mean()
    second_half = df[col].iloc[-14:].mean()
    return percent_change(second_half, first_half)


def nearest_snapshot(df, date_col, target_date, window_days=45):
    """Return subset of df whose date_col is within window_days of target_date."""
    return df[
        (df[date_col] >= target_date - pd.Timedelta(days=window_days)) &
        (df[date_col] <= target_date + pd.Timedelta(days=window_days))
    ]


def build_summary():
    summary = {
        "date": str(datetime.now().date()),
        "reddit_ecosystem": {},
    }

    # ── Reddit engagement (30d structural) ─────────────────────────────────────
    history = load_csv(HISTORY_FILE)
    if history is not None and not history.empty:
        subs = history["subreddit"].unique()
        subreddit_data = []
        ecosystem_first14, ecosystem_last14 = 0, 0

        for sub in subs:
            sub_df = history[history["subreddit"] == sub].sort_values("date")
            structural = compute_30d_structural(sub_df, "total_comments")

            if len(sub_df) >= 28:
                ecosystem_first14 += sub_df["total_comments"].iloc[:14].sum()
                ecosystem_last14  += sub_df["total_comments"].iloc[-14:].sum()

            subreddit_data.append({
                "subreddit":                   sub,
                "structural_30d_comments_pct": structural,
            })

        summary["reddit_ecosystem"]["subreddits"] = subreddit_data
        summary["reddit_ecosystem"]["ecosystem_structural_30d_comments_pct"] = (
            percent_change(ecosystem_last14, ecosystem_first14)
        )

    # ── Reddit member counts — YoY structural growth ───────────────────────────
    reddit_members = load_csv(REDDIT_MEMBERS_FILE)
    if reddit_members is not None and not reddit_members.empty:
        reddit_members["date"] = pd.to_datetime(reddit_members["date"])
        latest_rm = reddit_members["date"].max()

        targets = {
            "1y":   latest_rm - pd.Timedelta(days=365),
            "2y":   latest_rm - pd.Timedelta(days=730),
            "sep25": pd.Timestamp("2025-09-01"),
        }

        latest_m = reddit_members[reddit_members["date"] == latest_rm]
        member_rows = []

        for _, row in latest_m.iterrows():
            sub      = row["subreddit"]
            sub_hist = reddit_members[reddit_members["subreddit"] == sub].sort_values("date")
            current  = int(row["members"]) if pd.notna(row["members"]) else None

            growth = {}
            for key, tgt in targets.items():
                window = nearest_snapshot(sub_hist, "date", tgt, window_days=90)
                if not window.empty and current:
                    ref = int(window.sort_values("date").iloc[-1]["members"])
                    growth[key] = round(percent_change(current, ref), 1) if ref > 0 else None
                else:
                    growth[key] = None

            oldest = sub_hist.iloc[0]
            member_rows.append({
                "subreddit":         sub,
                "members":           current,
                "growth_1y_pct":     growth["1y"],
                "growth_2y_pct":     growth["2y"],
                "growth_5m_pct":     growth["sep25"],   # Sept 2025 → now
                "oldest_data_point": {
                    "date":    str(oldest["date"].date()),
                    "members": int(oldest["members"]) if pd.notna(oldest["members"]) else None,
                },
            })

        summary["reddit_ecosystem"]["member_counts"]       = member_rows
        summary["reddit_ecosystem"]["member_counts_as_of"] = str(latest_rm.date())

        # Per-subreddit time series (for charts)
        member_history = {}
        for sub in reddit_members["subreddit"].unique():
            sub_df = reddit_members[reddit_members["subreddit"] == sub].sort_values("date")
            member_history[sub] = [
                {
                    "date":    str(r["date"].date()),
                    "members": int(r["members"]) if pd.notna(r["members"]) else None,
                    "source":  str(r.get("source", "reddit_api")),
                }
                for _, r in sub_df.iterrows()
            ]
        summary["reddit_ecosystem"]["member_history"] = member_history

        summary["reddit_ecosystem"]["history_context"] = {
            "platform_note": (
                "Reddit removed public subscriber counts from the web in September 2025. "
                "The Reddit API still returns accurate member counts and is used for ongoing tracking."
            ),
            "milestones": [
                {"subreddit": "Warhammer40k", "event": "Surpassed 1M members", "date": "2024-10"},
            ],
            "annual_growth_rate_range_pct": [13, 25],
            "historical_data_since": "2023-10-01",
        }

    # ── YouTube channels — subscriber & view expansion ─────────────────────────
    yt_channels = load_csv(YT_CHANNELS_FILE)
    if yt_channels is not None and not yt_channels.empty:
        yt_channels["date"] = pd.to_datetime(yt_channels["date"])
        latest_date = yt_channels["date"].max()
        n_snapshots = yt_channels["date"].nunique()

        latest_ch = yt_channels[yt_channels["date"] == latest_date]

        # YoY reference windows
        yr1_ch = nearest_snapshot(yt_channels, "date",
                                  latest_date - pd.Timedelta(days=365)).sort_values("date") \
                     .groupby("channel_id").tail(1)
        yr2_ch = nearest_snapshot(yt_channels, "date",
                                  latest_date - pd.Timedelta(days=730)).sort_values("date") \
                     .groupby("channel_id").tail(1)

        channel_rows = []
        for _, row in latest_ch.iterrows():
            if int(row.get("subscribers", 0)) == 0 and int(row.get("views", 0)) == 0:
                continue
            cid       = row["channel_id"]
            subs_now  = int(row["subscribers"])
            views_now = int(row["views"])

            def yoy_subs(ref_df):
                r = ref_df[ref_df["channel_id"] == cid]
                if r.empty: return None
                s = int(r.iloc[0]["subscribers"])
                return round(percent_change(subs_now, s), 1) if s > 0 else None

            def yoy_views(ref_df):
                r = ref_df[ref_df["channel_id"] == cid]
                if r.empty: return None
                v = int(r.iloc[0]["views"])
                return round(percent_change(views_now, v), 1) if v > 0 else None

            channel_rows.append({
                "label":               row["label"],
                "channel_id":          cid,
                "subscribers":         subs_now,
                "total_views":         views_now,
                "growth_1y_subs_pct":  yoy_subs(yr1_ch),
                "growth_2y_subs_pct":  yoy_subs(yr2_ch),
                "growth_1y_views_pct": yoy_views(yr1_ch),
            })

        total_subs  = sum(c["subscribers"]  for c in channel_rows)
        total_views = sum(c["total_views"]   for c in channel_rows)

        summary["youtube_channels"] = {
            "as_of":                      str(latest_date.date()),
            "snapshots_available":        n_snapshots,
            "total_ecosystem_subscribers": total_subs,
            "total_ecosystem_views":       total_views,
            "channels":                   channel_rows,
            "yoy_data_available":         n_snapshots >= 52,
        }

    # ── YouTube videos — content performance, trailers, beginner funnel ─────────
    yt_videos = load_csv(YT_VIDEOS_FILE)
    if yt_videos is not None and not yt_videos.empty:
        yt_videos["published_at"] = pd.to_datetime(yt_videos["published_at"], utc=True)
        now         = datetime.now(timezone.utc)
        latest_snap = yt_videos["as_of_date"].max()
        latest_vids = yt_videos[yt_videos["as_of_date"] == latest_snap].copy()
        snapshots   = sorted(yt_videos["as_of_date"].unique())

        latest_vids["days_old"]     = (now - latest_vids["published_at"]).dt.days.clip(lower=1)
        latest_vids["views_per_day"] = (latest_vids["views"] / latest_vids["days_old"]).round(1)

        # Top 10 all-time
        top_all = (
            latest_vids.nlargest(10, "views")
            [["channel_label","title","published_at","views","views_per_day"]]
            .copy()
        )
        top_all["published_at"] = top_all["published_at"].dt.strftime("%Y-%m-%d")

        # Top 10 last 60 days
        recent_cutoff = now - pd.Timedelta(days=60)
        recent_vids   = (
            latest_vids[latest_vids["published_at"] >= recent_cutoff]
            .nlargest(10, "views")
            [["channel_label","title","published_at","views","views_per_day"]]
            .copy()
        )
        recent_vids["published_at"] = recent_vids["published_at"].dt.strftime("%Y-%m-%d")

        # WoW view gainers (if 2+ snapshots)
        wow_rows = []
        velocity_proxy = []
        if len(snapshots) >= 2:
            prev_vids = yt_videos[yt_videos["as_of_date"] == snapshots[-2]][
                ["video_id", "views"]].rename(columns={"views": "views_prev"})
            merged = latest_vids.merge(prev_vids, on="video_id", how="inner")
            merged["views_delta_7d"] = merged["views"] - merged["views_prev"]
            wow_rows = (
                merged.nlargest(10, "views_delta_7d")
                [["channel_label","title","views","views_delta_7d"]]
                .to_dict(orient="records")
            )
        else:
            fast_recent = (
                latest_vids[latest_vids["days_old"] <= 30]
                .nlargest(10, "views_per_day")
                [["channel_label","title","published_at","views","views_per_day","days_old"]]
                .copy()
            )
            fast_recent["published_at"] = fast_recent["published_at"].dt.strftime("%Y-%m-%d")
            fast_recent["est_7d_views"] = (fast_recent["views_per_day"] * 7).round(0).astype(int)
            velocity_proxy = fast_recent.to_dict(orient="records")

        # ── Trailers & tentpole reveals ──────────────────────────────────────
        t_pat     = "|".join(TRAILER_KW)
        t_mask    = latest_vids["title"].str.lower().str.contains(t_pat, na=False)
        trailers  = (
            latest_vids[t_mask]
            .nlargest(15, "views")
            [["channel_label","title","published_at","views","views_per_day","days_old"]]
            .copy()
        )
        trailers["published_at"] = trailers["published_at"].dt.strftime("%Y-%m-%d")

        # ── Beginner / new player funnel ─────────────────────────────────────
        b_pat   = "|".join(BEGINNER_KW)
        b_mask  = latest_vids["title"].str.lower().str.contains(b_pat, na=False)
        beg_df  = latest_vids[b_mask].copy()
        beg_90d = beg_df[beg_df["days_old"] <= 90]
        beg_1y  = beg_df[beg_df["days_old"] <= 365]
        beg_top = (
            beg_df.nlargest(10, "views")
            [["channel_label","title","published_at","views","views_per_day","days_old"]]
            .copy()
        )
        beg_top["published_at"] = beg_top["published_at"].dt.strftime("%Y-%m-%d")

        summary["youtube_videos"] = {
            "as_of":               latest_snap,
            "snapshots_available": len(snapshots),
            "top_all_time":        top_all.to_dict(orient="records"),
            "top_recent_60d":      recent_vids.to_dict(orient="records"),
            "top_view_gainers_7d": wow_rows,
            "top_velocity_proxy":  velocity_proxy,
            "trailers": {
                "total_found":  len(trailers),
                "top_trailers": trailers.to_dict(orient="records"),
            },
            "beginner_funnel": {
                "total_videos":   len(beg_df),
                "last_90d_count": int(len(beg_90d)),
                "last_90d_views": int(beg_90d["views"].sum()) if not beg_90d.empty else 0,
                "last_1y_count":  int(len(beg_1y)),
                "last_1y_views":  int(beg_1y["views"].sum()) if not beg_1y.empty else 0,
                "all_time_views": int(beg_df["views"].sum()) if not beg_df.empty else 0,
                "top_videos":     beg_top.to_dict(orient="records"),
            },
        }

    # ── Steam — structural digital gaming base ─────────────────────────────────
    steam = load_csv(STEAM_FILE)
    if steam is not None and not steam.empty:
        steam["date"] = pd.to_datetime(steam["date"])
        latest_steam  = steam["date"].max()

        yr1_steam = nearest_snapshot(steam, "date",
                                     latest_steam - pd.Timedelta(days=365),
                                     window_days=14) \
                        .sort_values("date").groupby("app_id").tail(1)

        latest_s  = steam[steam["date"] == latest_steam]
        game_rows = []
        for _, row in latest_s.iterrows():
            app_id      = row["app_id"]
            players_now = int(row["current_players"]) if pd.notna(row.get("current_players")) else None
            reviews_now = int(row["total_reviews"])   if pd.notna(row.get("total_reviews"))   else None
            owners_low  = int(row["owners_low"])  if "owners_low"  in row and pd.notna(row.get("owners_low"))  else None
            owners_high = int(row["owners_high"]) if "owners_high" in row and pd.notna(row.get("owners_high")) else None
            avg_2w      = int(row["avg_playtime_2w_min"]) if "avg_playtime_2w_min" in row and pd.notna(row.get("avg_playtime_2w_min")) else None
            pos_pct     = float(row["positive_pct"]) if pd.notna(row.get("positive_pct")) else None

            # YoY player count
            growth_1y = None
            yr1_row   = yr1_steam[yr1_steam["app_id"] == app_id]
            if not yr1_row.empty and players_now is not None:
                p1 = int(yr1_row.iloc[0]["current_players"]) if pd.notna(yr1_row.iloc[0].get("current_players")) else None
                if p1 and p1 > 0:
                    growth_1y = round(percent_change(players_now, p1), 1)

            game_rows.append({
                "label":                  row["label"],
                "current_players":        players_now,
                "total_reviews":          reviews_now,
                "positive_pct":           pos_pct,
                "owners_low":             owners_low,
                "owners_high":            owners_high,
                "avg_playtime_2w_min":    avg_2w,
                "growth_1y_players_pct":  growth_1y,
            })

        summary["steam"] = {
            "as_of":           str(latest_steam.date()),
            "total_players":   sum(g["current_players"] or 0 for g in game_rows),
            "games":           game_rows,
            "yoy_available":   not yr1_steam.empty,
        }

    # ── Warhammer Community — GW cadence ──────────────────────────────────────
    warcom = load_csv(WARCOM_FILE)
    if warcom is not None and not warcom.empty:
        warcom   = warcom.sort_values("date")
        latest_wc = warcom.iloc[-1]
        summary["warcom"] = {
            "as_of":             latest_wc["date"],
            "articles_last_7d":  int(latest_wc["articles_last_7d"]),
            "articles_last_30d": int(latest_wc.get("articles_last_30d") or 0),
            "method":            str(latest_wc.get("method", "")),
        }

    # ── Competitive events ─────────────────────────────────────────────────────
    competitive = load_csv(COMPETITIVE_FILE)
    if competitive is not None and not competitive.empty:
        if "event_date" in competitive.columns:
            competitive = competitive.sort_values("event_date", ascending=False)
        summary["competitive_events"] = competitive.head(10).to_dict(orient="records")

    # ── Retail & supply signals ────────────────────────────────────────────────
    retail = load_csv(RETAIL_FILE)
    if retail is not None and not retail.empty:
        if "published_at" in retail.columns:
            retail = retail.sort_values("published_at", ascending=False)
        summary["retail_signals"] = retail.head(10).to_dict(orient="records")

    return summary


if __name__ == "__main__":
    summary = build_summary()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(summary, f, indent=4)
    print(f"Ecosystem summary generated → {OUTPUT_FILE}")
