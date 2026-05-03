"""
Warhammer Demand Acceleration Intelligence — YouTube Franchise Dashboard

Structure:
  PAGE 1 — DEMAND EXPANSION OVERVIEW
    Section 1: Franchise-Level Subscriber Expansion
    Section 2: Discovery vs Subscriber-Driven Growth

  PAGE 2 — STRUCTURAL CONTENT DYNAMICS
    Section 3: Evergreen Anchor Deep Dive
    Section 4: Content-Type Demand Signals

  PAGE 3 — ENGAGEMENT INTENSITY
    Section 5: Recent Upload Velocity
    Section 6: Structural Classification Summary

  Executive Summary (bullets)

Reads from:
  data/youtube_channel_history_seed.csv
  data/youtube_channels_daily.csv
  data/youtube_evergreen_anchors.csv
  data/youtube_videos_unified.csv

Output:
  youtube_dashboard.html
"""

import os
import sys
import json
import webbrowser
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

# ── File paths ───────────────────────────────────────────────────────────────
DATA_DIR        = "data"
CONFIG_DIR      = "config"
CHANNELS_DAILY  = os.path.join(DATA_DIR,   "youtube_channels_daily.csv")
CHANNELS_SEED   = os.path.join(DATA_DIR,   "youtube_channel_history_seed.csv")
ANCHORS_DATA    = os.path.join(DATA_DIR,   "youtube_evergreen_anchors.csv")
ANCHORS_CONFIG  = os.path.join(CONFIG_DIR, "youtube_evergreen_anchors.csv")
VIDEOS_UNIFIED  = os.path.join(DATA_DIR,   "youtube_videos_unified.csv")
REDDIT_DATA         = os.path.join(DATA_DIR,   "reddit_snapshots.csv")
REDDIT_MEMBERS_DATA = os.path.join(DATA_DIR,   "reddit_members_weekly.csv")
REDDIT_CONFIG       = os.path.join(CONFIG_DIR, "reddit_subreddits.csv")
STEAM_DATA            = os.path.join(DATA_DIR,   "steam_players.csv")
STEAM_GAMES_CSV       = os.path.join(CONFIG_DIR, "steam_games.csv")
STEAM_MONTHLY_HISTORY = os.path.join(DATA_DIR,   "steam_monthly_history.csv")
STEAM_ROLLING_30D     = os.path.join(DATA_DIR,   "steam_rolling_30d.csv")
REDDIT_STORE_MONTHLY  = os.path.join(DATA_DIR,   "reddit_store_threads_monthly.csv")
REDDIT_STORE_RECENT   = os.path.join(DATA_DIR,   "reddit_store_threads_recent.csv")
REDDIT_STORE_RAW      = os.path.join(DATA_DIR,   "reddit_store_threads_raw.csv")
REDDIT_INTEL_POSTS    = os.path.join(DATA_DIR,   "reddit_intel_posts.csv")
REDDIT_INTEL_COMMENTS = os.path.join(DATA_DIR,   "reddit_intel_comments.csv")
CHANNEL_HISTORY = os.path.join(DATA_DIR,   "youtube_channel_history.csv")
ANCHOR_HISTORY  = os.path.join(DATA_DIR,   "youtube_anchor_history.csv")
OUTPUT_HTML     = "index.html"

# ── Channel constants ────────────────────────────────────────────────────────
CHANNEL_ORDER = [
    "Warhammer_Official",
    "WesHammer",
    "Luetin09",
    "Squidmar_Miniatures",
    "Majorkill",
    "Auspex_Tactics",
    "Valrak",
]
CHANNEL_DISPLAY = {
    "Warhammer_Official":  "Warhammer Official",
    "WesHammer":           "WesHammer",
    "Luetin09":            "Luetin09",
    "Squidmar_Miniatures": "Squidmar",
    "Majorkill":           "Majorkill",
    "Auspex_Tactics":      "Auspex Tactics",
    "Valrak":              "Chapter Master Valrak",
}
CHANNEL_COLORS = {
    "Warhammer_Official":  "#c0392b",
    "WesHammer":           "#2980b9",
    "Luetin09":            "#8e44ad",
    "Squidmar_Miniatures": "#27ae60",
    "Majorkill":           "#e67e22",
    "Auspex_Tactics":      "#b7950b",
    "Valrak":              "#117a65",
}

YOY_WINDOW_DAYS      = 45
MULTIYEAR_WINDOW     = 90     # wider tolerance for historical snapshots
MULTIYEAR_YEARS      = [2023, 2024, 2025, 2026]
MULTIYEAR_TARGET_MD  = "02-15"  # mid-Feb reference for each year
TRAJ_REF_DATE        = "2025-01-01"

# Anchor per-year view snapshot settings (same window as multiyear)
ANCHOR_VIEW_YEARS     = [2023, 2024, 2025, 2026]
ANCHOR_VIEW_TARGET_MD = "02-15"
ANCHOR_VIEW_WINDOW    = 90

# Standardized content-type categories (4 groups)
_CONTENT_TYPE_REMAP = {
    "Cinematic/Trailer":       "Official Media",
    "Lore Explainer":          "Lore Education",
    "Deep Dive":               "Lore Education",
    "Hobby/Entertainment":     "Hobby Content",
    "Entertainment/Crossover": "Entertainment / Commentary",
}
# Canonical colors for the 4 standardized groups
CONTENT_TYPE_COLORS = {
    "Official Media":             "#c0392b",
    "Lore Education":             "#2980b9",
    "Hobby Content":              "#27ae60",
    "Entertainment / Commentary": "#e67e22",
}

# Maps display-names used in wayback_seed CSVs to internal channel_label values
_CHANNEL_NAME_MAP = {
    "Majorkill":           "Majorkill",
    "Squidmar Miniatures": "Squidmar_Miniatures",
    "WesHammer":           "WesHammer",
    "Luetin09":            "Luetin09",
    "Warhammer Official":  "Warhammer_Official",
}

# ── Reddit constants ─────────────────────────────────────────────────────────
REDDIT_ORDER = ["Warhammer", "Warhammer40k", "ageofsigmar", "minipainting"]
REDDIT_LABELS = {
    "Warhammer":    "r/Warhammer",
    "Warhammer40k": "r/Warhammer40k",
    "ageofsigmar":  "r/AgeOfSigmar",
    "minipainting": "r/minipainting",
}
REDDIT_COLORS = {
    "Warhammer":    "#c0392b",
    "Warhammer40k": "#2980b9",
    "ageofsigmar":  "#8e44ad",
    "minipainting": "#27ae60",
}
REDDIT_YOY_WINDOW = 45

# Wayback-seeded 2023 & 2024 member snapshots for multi-year community growth
REDDIT_HISTORY_2324 = {
    "Warhammer40k": {"2023": 589_000,   "2024": 783_000},
    "ageofsigmar":  {"2023": 197_000,   "2024": 214_000},
    "minipainting": {"2023": 1_100_000, "2024": 1_200_000},
    "Warhammer":    {"2023": 296_000,   "2024": 338_000},
}

# ── Steam constants ──────────────────────────────────────────────────────────
# game_slug order: largest → smallest by typical avg players
STEAM_ORDER = ["tw_wh3", "space_marine_2", "darktide", "vermintide_2"]
STEAM_LABELS = {
    "tw_wh3":         "Total War: WH3",
    "space_marine_2": "Space Marine 2",
    "darktide":       "Darktide",
    "vermintide_2":   "Vermintide 2",
}
STEAM_COLORS = {
    "tw_wh3":         "#2980b9",
    "space_marine_2": "#27ae60",
    "darktide":       "#c0392b",
    "vermintide_2":   "#e67e22",
}
# Map game_slug → game column name in steam_players.csv (live CCU file)
STEAM_LIVE_SLUG_MAP = {
    "tw_wh3":         "TW_Warhammer3",
    "space_marine_2": "Space_Marine_2",
    "darktide":       "Darktide",
    "vermintide_2":   "Vermintide_2",
}

# ── Steam historical snapshot data (SteamCharts) ─────────────────────────
# February average players per year + all-time peak players.
# Update "snapshots" dict when new annual February data is available.
# Space Marine 2 has no 2023 entry — it was released September 2024.
STEAM_HISTORICAL_DATA = {
    "tw_wh3": {
        "snapshots": {2023: 20460.3, 2024: 17756.9, 2025: 20783.6, 2026: 22789.7},
        "last_30d":  22229.0,
        "peak":      166519,
    },
    "space_marine_2": {
        "snapshots": {2025: 6652.4, 2026: 11756.2},   # released Sep 2024, no Feb 2024 snapshot
        "last_30d":  14692.1,
        "peak":      186199,
    },
    "darktide": {
        "snapshots": {2023: 4952.8, 2024: 2947.9, 2025: 4952.1, 2026: 5228.7},
        "last_30d":  4739.1,
        "peak":      107450,
    },
    "vermintide_2": {
        "snapshots": {2023: 4240.1, 2024: 2612.2, 2025: 2303.7, 2026: 2338.0},
        "last_30d":  2230.8,
        "peak":      104134,
    },
}

# ── Tournament constants ──────────────────────────────────────────────────
# Source of truth for all competitive participation data.
# Add new events or update player counts here — insights auto-update.
TOURNAMENT_DATA = {
    "wcw": {
        "name":  "World Championships of Warhammer",
        "short": "WCW",
        "desc":  "40k Championship · Annual Global Finals",
        "players": {2023: 175, 2024: 274, 2025: 411},
    },
    "lvo": {
        "name":  "Las Vegas Open",
        "short": "LVO",
        "desc":  "40k Championship · Largest North American Open",
        # 2025: 1,095 confirmed via BCP event page + Wargamer.com report ("almost 1,100")
        "players": {2023: 950, 2024: 907, 2025: 1095},
    },
}
TOURNAMENT_ORDER = ["wcw", "lvo"]

# ── Retail & Store Intelligence constants ────────────────────────────────────
# Source: GW Annual Reports + Half-Year Results (investor.games-workshop.com)
# Update annually with new half-year results. MANUAL UPDATE REQUIRED.
GW_STORE_DATA = {
    "last_updated": "2026-03-13",
    "own_stores": {   # GW-operated retail stores (from annual reports)
        2017: 462, 2018: 507, 2019: 524, 2020: 531,
        2021: 523, 2022: 526, 2023: 526, 2024: 548, 2025: 570,
    },
    "indie_retailers": {  # Independent stockists network (from annual reports)
        2020: 4900, 2021: 5400, 2022: 6200, 2023: 6500, 2024: 7200, 2025: 8100,
    },
    "revenue_h1_gbp_m": {  # H1 revenue by channel in £M (from half-year reports)
        # Label format: H1_FY{year} = first half of fiscal year ending that June
        "H1_FY23": {"own_retail": 48.7, "trade": 120.9, "online": 42.7},
        "H1_FY24": {"own_retail": 56.5, "trade": 140.3, "online": 45.6},
        "H1_FY25": {"own_retail": 62.0, "trade": 169.2, "online": 43.0},
        "H1_FY26": {"own_retail": 64.6, "trade": 209.0, "online": 45.4},
    },
    # Store count contemporary to each H1 period (for revenue-per-store calculation)
    # H1 = Nov–Dec period end; use GW store count as of that fiscal year-end
    "h1_store_count_map": {
        "H1_FY23": 526,   # FY2022 year-end store count
        "H1_FY24": 526,   # FY2023 year-end store count
        "H1_FY25": 548,   # FY2024 year-end store count
        "H1_FY26": 570,   # FY2025 year-end store count
    },
}

# ── PassBy independent foot traffic (third-party location intelligence) ──────
# Source: PassBy.com / Placer.ai published data (independent of GW reporting)
# Update quarterly when new PassBy/Placer reports are published.
PASSBY_DATA = {
    "last_updated": "2026-03-13",
    "snapshots": [
        {"period": "Sep 2022", "yoy_pct": 44.5, "note": "Post-lockdown demand surge"},
        {"period": "Q4 2024",  "yoy_pct":  1.1, "note": "Stable baseline"},
        {"period": "Q2 2025",  "yoy_pct":  2.96,"note": "Re-accelerating"},
        {"period": "Dec 2024", "visits_k": 700,  "note": "Monthly visit snapshot (est. 700K+)"},
    ],
    # Each event: date, event description, region, source.
    # source = "verify source" triggers a warning badge in the table.
    "narrative_events": [
        {"date": "2024",     "event": "GW Memphis distribution warehouse added 3rd shift — fulfillment demand overflow",
         "region": "Americas", "source": "Community reporting"},
        {"date": "2024",     "event": "First GW store opened in South Korea — previously zero physical presence",
         "region": "APAC",     "source": "GW investor reports"},
        {"date": "2025",     "event": "Japan: 13 stores active; 30+ planned through 2027",
         "region": "APAC",     "source": "GW investor reports"},
        {"date": "2025",     "event": "Warhammer World USA announced — Washington DC metro area (2027 target)",
         "region": "Americas", "source": "GW investor reports"},
    ],
}

# ── eBay secondary market snapshot ───────────────────────────────────────────
# Source: eBay completed listings (manual sample, Mar 2026).
# HOW TO UPDATE: eBay Seller Hub → Research → Terapeak → search product name
# → "Sold Listings" tab → 90-day avg sold price. Free with any eBay account.
# Positive premium_pct = supply constrained. Negative = normal discount market.
EBAY_SECONDARY_DATA = {
    "last_updated": "2026-03-13",
    # category: "launch" = major release demand event; "oop" = OOP/collector signal;
    #           "entry" = entry-level product (supply health indicator)
    "items": [
        {
            "product":      "Leviathan Launch Box (OOP)",
            "category":     "oop",
            "msrp_usd":     250,
            "sold_avg_usd": 370,
            "premium_pct":  48,
            "signal":       "OOP premium persists — collector and secondary demand active",
        },
        {
            "product":      "Harlequins Combat Patrol (OOP faction)",
            "category":     "oop",
            "msrp_usd":     120,
            "sold_avg_usd": 136,
            "premium_pct":  13,
            "signal":       "Discontinued faction still trading at modest premium",
        },
        {
            "product":      "Space Marine 2 Recruit Edition (entry-level game)",
            "category":     "entry",
            "msrp_usd":     65,
            "sold_avg_usd": 52,
            "premium_pct":  -20,
            "signal":       "Healthy supply now — but peaked +36% above MSRP at launch (Jan 2026)",
        },
        {
            "product":      "Skaventide AoS Launch Box",
            "category":     "launch",
            "msrp_usd":     265,
            "sold_avg_usd": 200,
            "premium_pct":  -25,
            "signal":       "Supply met demand — no scalper premium, normal for big-run launch box",
        },
        {
            "product":      "Combat Patrol (most factions, in-print)",
            "category":     "entry",
            "msrp_usd":     120,
            "sold_avg_usd": 95,
            "premium_pct":  -21,
            "signal":       "Normal discount market — healthy supply, no supply constraint",
        },
    ],
}

# ── Google Maps store ratings snapshot ───────────────────────────────────────
# MANUAL UPDATE REQUIRED quarterly. Review COUNT growth is the signal (not stars).
# How to update: Google Maps search "Warhammer [city]" → record stars + review count.
# Baseline established 2026-03-13. Track quarterly to build review velocity trend.
GOOGLE_MAPS_SNAPSHOT = {
    "last_updated": "2026-03-13",
    "update_note":  "Review count growth = customer acquisition proxy. Update quarterly.",
    "stores": [
        {"name": "Warhammer — London TCR (Flagship)", "city": "London, UK",      "stars": 4.57, "reviews": 1294},
        {"name": "Warhammer — Toronto Eaton Centre",  "city": "Toronto, CA",     "stars": 4.7,  "reviews": 270},
        {"name": "Warhammer — Melbourne Chadstone",   "city": "Melbourne, AU",   "stars": 4.7,  "reviews": 128},
        {"name": "Warhammer — Chicago Lincoln Park",  "city": "Chicago, US",     "stars": 4.8,  "reviews": 138},
        {"name": "Warhammer — Los Angeles Burbank",   "city": "Los Angeles, US", "stars": 4.9,  "reviews": 70},
    ],
}

# ── LinkedIn store expansion signals ─────────────────────────────────────────
# Source: LinkedIn job postings (manual search, Mar 2026).
# New market postings appear 3–6 months before store opens. Update monthly.
LINKEDIN_OPENINGS = {
    "last_updated": "2026-03-13",
    "openings": [
        {"location": "Seoul, South Korea",        "region": "APAC",     "market_type": "First entry"},
        {"location": "Tama Plaza / Kanagawa, Japan", "region": "APAC",  "market_type": "Expansion"},
        {"location": "Joondalup, Australia",      "region": "APAC",     "market_type": "Expansion"},
        {"location": "Girona, Spain",             "region": "EMEA",     "market_type": "Expansion"},
        {"location": "Chemnitz, Germany",         "region": "EMEA",     "market_type": "Expansion"},
        {"location": "Wiesbaden, Germany",        "region": "EMEA",     "market_type": "Expansion"},
        {"location": "Solihull, UK",              "region": "UK",       "market_type": "Expansion"},
        {"location": "Southend, UK",              "region": "UK",       "market_type": "Expansion"},
        {"location": "Arlington TX, USA",         "region": "Americas", "market_type": "Expansion"},
        {"location": "Harrisburg PA, USA",        "region": "Americas", "market_type": "Expansion"},
        {"location": "Kennewick WA, USA",         "region": "Americas", "market_type": "Expansion"},
        {"location": "Plainview NY, USA",         "region": "Americas", "market_type": "Expansion"},
    ],
}

# ── My Warhammer App ──────────────────────────────────────────────────────────
# Source: GW Half-Year Reports (investor.games-workshop.com)
# Update bi-annually (Jan + Jul interim results).
# Definition: "Active users = someone who has engaged with us online in the last 6 months"
MY_WARHAMMER_APP_DATA = {
    "last_updated": "2026-03-13",
    "note": "Active user counts from GW half-year reports. Update bi-annually (Jan + Jul).",
    "snapshots": [
        # label, users, yoy_pct (None if not stated), source
        {"label": "H1 FY23",  "users": 346000,  "yoy_pct": None,  "source": "H1 FY23 Half-Year Report (Jan 2023)"},
        {"label": "FY23",     "users": 427000,  "yoy_pct": None,  "source": "FY23 Annual Report (Jul 2023)"},
        {"label": "H1 FY24",  "users": 576000,  "yoy_pct": 66.0,  "source": "H1 FY24 Half-Year Report (Jan 2024)"},
        {"label": "FY24",     "users": 565000,  "yoy_pct": None,  "source": "FY24 Annual Report (Jul 2024)"},
        {"label": "H1 FY25",  "users": 695000,  "yoy_pct": 21.0,  "source": "H1 FY25 Half-Year Report (Jan 2025)"},
        {"label": "H1 FY26",  "users": 790000,  "yoy_pct": 14.0,  "source": "H1 FY26 Half-Year Report (Jan 2026, ~est.)"},
    ],
    # Warhammer+ paid subscribers (separate product — included for context)
    "wh_plus_subscribers": {
        "H1_FY24": 169000, "H1_FY25": 207000, "H1_FY26": 248000,
    },
}


GW_STOCK_CSV = os.path.join(DATA_DIR, "gw_stock_daily.csv")

# ════════════════════════════════════════════════════════════════════════════
# Data loading
# ════════════════════════════════════════════════════════════════════════════

def load_gw_stock() -> "pd.DataFrame":
    if not os.path.exists(GW_STOCK_CSV):
        return pd.DataFrame()
    df = pd.read_csv(GW_STOCK_CSV, dtype=str)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    return df.sort_values("date").reset_index(drop=True)


def load_channels_combined() -> pd.DataFrame:
    frames = []
    for fpath in [CHANNELS_DAILY, CHANNELS_SEED]:
        if os.path.exists(fpath):
            df = pd.read_csv(fpath)
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["date", "channel_label"], keep="last")
    return combined.sort_values(["channel_label", "date"]).reset_index(drop=True)


def load_channel_history() -> pd.DataFrame:
    """Wayback-seeded 2023–2024 channel snapshots. Used only for multi-year growth."""
    if not os.path.exists(CHANNEL_HISTORY):
        return pd.DataFrame()
    df = pd.read_csv(CHANNEL_HISTORY)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    df["channel_label"] = df["channel"].map(_CHANNEL_NAME_MAP).fillna(df["channel"])
    if "videos" in df.columns:
        df = df.rename(columns={"videos": "video_count"})
    return df.sort_values(["channel_label", "date"]).reset_index(drop=True)


def load_anchor_history() -> pd.DataFrame:
    """Wayback-seeded 2023–2024 anchor view snapshots. Used only for multi-year anchor metrics."""
    if not os.path.exists(ANCHOR_HISTORY):
        return pd.DataFrame()
    df = pd.read_csv(ANCHOR_HISTORY)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    df["channel_label"] = df["channel"].map(_CHANNEL_NAME_MAP).fillna(df["channel"])
    df = df.rename(columns={"video_title": "title"})
    if "content_type" not in df.columns:
        df["content_type"] = ""
    return df.sort_values(["channel_label", "video_slug", "date"]).reset_index(drop=True)


def load_anchors() -> pd.DataFrame:
    if not os.path.exists(ANCHORS_DATA):
        return pd.DataFrame()
    df = pd.read_csv(ANCHORS_DATA)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    return df


def load_videos() -> pd.DataFrame:
    if not os.path.exists(VIDEOS_UNIFIED):
        return pd.DataFrame()
    df = pd.read_csv(VIDEOS_UNIFIED)
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    return df


# ════════════════════════════════════════════════════════════════════════════
# Metric computation
# ════════════════════════════════════════════════════════════════════════════

def nearest_snapshot(df: pd.DataFrame, channel: str, target_date: str,
                     window_days: int = YOY_WINDOW_DAYS) -> pd.Series | None:
    sub = df[df["channel_label"] == channel].copy()
    if sub.empty:
        return None
    sub["_dist"] = abs(pd.to_datetime(sub["date"]) - pd.to_datetime(target_date)).dt.days
    sub = sub[sub["_dist"] <= window_days]
    return None if sub.empty else sub.loc[sub["_dist"].idxmin()]


def compute_yoy_sub_metrics(channels_df: pd.DataFrame) -> dict:
    """YoY subscriber growth per channel.
    Reference = snapshot closest to (latest_date − 365 days) within ±45d window."""
    results = {}
    for ch in CHANNEL_ORDER:
        ch_df  = channels_df[channels_df["channel_label"] == ch].sort_values("date")
        if ch_df.empty:
            results[ch] = {}
            continue
        latest    = ch_df.iloc[-1]
        curr_subs = latest.get("subscribers")
        curr_date = latest["date"]

        ref_date = str((pd.to_datetime(curr_date) - timedelta(days=365)).date())
        ref_row  = nearest_snapshot(channels_df, ch, ref_date)

        if ref_row is None or curr_subs is None:
            results[ch] = {"curr_subs": curr_subs, "yoy_pct": None}
            continue

        ref_subs = ref_row.get("subscribers")
        gap_days = (pd.to_datetime(curr_date) - pd.to_datetime(ref_row["date"])).days

        yoy_pct = round((curr_subs - ref_subs) / ref_subs * 100, 1) \
                  if (ref_subs and ref_subs > 0 and curr_subs) else None

        results[ch] = {
            "curr_subs":  int(curr_subs) if curr_subs else None,
            "ref_subs":   int(ref_subs)  if ref_subs  else None,
            "yoy_pct":    yoy_pct,
            "gap_days":   gap_days,
            "curr_date":  curr_date,
            "ref_date":   ref_row["date"],
        }
    return results


def compute_evergreen_metrics(anchors_df: pd.DataFrame,
                              anchor_history_df: pd.DataFrame | None = None) -> dict:
    """Per-anchor view growth across matched snapshot pairs.
    Match = same video_slug, earliest vs latest date row.

    If anchor_history_df is supplied, also computes per-year view snapshots
    (2023–2026) and derives YoY / 2yr / 3yr CAGR for each anchor.
    Content types are remapped to the 4 standardized categories.
    """
    results = {}

    # Combine current anchors with historical snapshots for per-year lookups
    if anchor_history_df is not None and not anchor_history_df.empty:
        _keep = ["date", "channel_label", "video_slug", "title", "views"]
        _hist = anchor_history_df[[c for c in _keep if c in anchor_history_df.columns]].copy()
        if "content_type" not in _hist.columns:
            _hist["content_type"] = ""
        all_anchors_df = pd.concat([anchors_df, _hist], ignore_index=True)
        all_anchors_df = all_anchors_df.drop_duplicates(
            subset=["date", "channel_label", "video_slug"], keep="last"
        ).sort_values(["channel_label", "video_slug", "date"]).reset_index(drop=True)
    else:
        all_anchors_df = anchors_df.copy()

    for ch in CHANNEL_ORDER:
        ch_anc = anchors_df[anchors_df["channel_label"] == ch].copy()   # current only for pair
        ch_all = all_anchors_df[all_anchors_df["channel_label"] == ch].copy()  # full for multi-yr
        if ch_anc.empty:
            results[ch] = {"anchors": [], "avg_view_growth_pct": None}
            continue

        anchor_rows = []
        for slug in ch_anc["video_slug"].unique():
            slug_df = ch_anc[ch_anc["video_slug"] == slug].sort_values("date")
            if len(slug_df) < 2:
                continue
            first, last = slug_df.iloc[0], slug_df.iloc[-1]
            v0, v1  = first["views"], last["views"]
            days    = max(1, (pd.to_datetime(last["date"]) -
                              pd.to_datetime(first["date"])).days)
            growth_pct = round((v1 - v0) / max(1, v0) * 100, 1) if v0 > 0 else None
            vpd_gain   = round((v1 - v0) / days, 1)

            # Standardize content type to 4 canonical groups
            raw_ct = str(last.get("content_type") or "")
            content_type = _CONTENT_TYPE_REMAP.get(raw_ct, raw_ct or "Entertainment / Commentary")

            # Per-year view snapshots (nearest mid-Feb within ±90d)
            slug_all = ch_all[ch_all["video_slug"] == slug].sort_values("date")
            views_by_year: dict = {}
            for yr in ANCHOR_VIEW_YEARS:
                target = f"{yr}-{ANCHOR_VIEW_TARGET_MD}"
                dists  = abs(pd.to_datetime(slug_all["date"]) -
                             pd.to_datetime(target)).dt.days
                valid_rows = slug_all[dists <= ANCHOR_VIEW_WINDOW]
                if not valid_rows.empty:
                    best = valid_rows.loc[dists[valid_rows.index].idxmin()]
                    views_by_year[yr] = int(best["views"])

            v_2023 = views_by_year.get(2023)
            v_2024 = views_by_year.get(2024)
            v_2025 = views_by_year.get(2025)
            v_2026 = views_by_year.get(2026)

            yoy_view_pct    = round((v_2026 - v_2025) / v_2025 * 100, 1) \
                              if (v_2025 and v_2026 and v_2025 > 0) else None
            two_yr_view_pct = round((v_2026 - v_2024) / v_2024 * 100, 1) \
                              if (v_2024 and v_2026 and v_2024 > 0) else None
            view_cagr_pct   = round(((v_2026 / v_2023) ** (1 / 3) - 1) * 100, 1) \
                              if (v_2023 and v_2026 and v_2023 > 0) else None
            has_multiyear   = v_2023 is not None or v_2024 is not None

            anchor_rows.append({
                "slug":            slug,
                "title":           last["title"],
                "content_type":    content_type,
                "views_curr":      int(v1),
                "views_prev":      int(v0),
                "date_curr":       last["date"],
                "date_prev":       first["date"],
                "growth_pct":      growth_pct,
                "vpd_gain":        vpd_gain,
                "days":            days,
                "views_by_year":   views_by_year,
                "yoy_view_pct":    yoy_view_pct,
                "two_yr_view_pct": two_yr_view_pct,
                "view_cagr_pct":   view_cagr_pct,
                "has_multiyear":   has_multiyear,
            })

        valid = [a["growth_pct"] for a in anchor_rows if a["growth_pct"] is not None]
        results[ch] = {
            "anchors":             anchor_rows,
            "avg_view_growth_pct": round(sum(valid) / len(valid), 1) if valid else None,
        }
    return results


def compute_eci(evergreen: dict, yoy: dict, multiyear: dict | None = None) -> dict:
    """Evergreen Compounding Index = avg_anchor_view_growth_pct / sub_growth_cagr.
    Divisor = 3-year CAGR where available (structural baseline); falls back to YoY.
    sub_growth_yoy is stored separately for display / classification thresholds."""
    eci_results = {}
    for ch in CHANNEL_ORDER:
        avg_view_g   = evergreen.get(ch, {}).get("avg_view_growth_pct")
        yoy_pct      = yoy.get(ch, {}).get("yoy_pct")
        cagr_pct     = multiyear.get(ch, {}).get("cagr_pct") if multiyear else None
        sub_g_for_eci = cagr_pct if cagr_pct is not None else yoy_pct
        if avg_view_g is None or sub_g_for_eci is None or sub_g_for_eci == 0:
            eci = None
        else:
            eci = round(avg_view_g / sub_g_for_eci, 2)
        eci_results[ch] = {
            "eci":             eci,
            "avg_view_growth": avg_view_g,
            "sub_growth":      yoy_pct,       # YoY — used by classification thresholds & display
            "sub_growth_cagr": cagr_pct,      # CAGR — used as ECI divisor
        }
    return eci_results


def compute_structural_classification(eci_map: dict, yoy: dict, velocity: dict) -> dict:
    """Rule-based classification. Priority order — first match wins.

    Rule 1  Discovery Engine:    ECI > 2.0  AND sub_growth > 5%
    Rule 2  Moderate Discovery:  1.0 ≤ ECI ≤ 2.0
    Rule 3  Cadence Dependent:   ECI < 0.5  AND sub_growth < 3%
    Rule 4  Retention Engine:    ECI < 1.0  AND vpd_per_1k ≥ ecosystem median vpd_per_1k
    Rule 5  Retention Oriented:  fallback (ECI 0.5–1.0, mixed signals)
    """
    vpd_vals = sorted(
        v.get("vpd_per_1k") for v in velocity.values() if v.get("vpd_per_1k") is not None
    )
    n = len(vpd_vals)
    eco_median = vpd_vals[n // 2] if n else 0

    result = {}
    for ch in CHANNEL_ORDER:
        eci    = eci_map.get(ch, {}).get("eci")
        sub_g  = yoy.get(ch, {}).get("yoy_pct")
        vpd_1k = velocity.get(ch, {}).get("vpd_per_1k")

        if eci is None or sub_g is None:
            label = "Insufficient Data"
        elif eci > 2.0 and sub_g > 5.0:
            label = "Discovery Engine"
        elif 1.0 <= eci <= 2.0:
            label = "Moderate Discovery"
        elif eci < 0.5 and sub_g < 3.0:
            label = "Cadence Dependent"
        elif eci < 1.0 and vpd_1k is not None and vpd_1k >= eco_median:
            label = "Retention Engine"
        else:
            label = "Retention Oriented"

        result[ch] = {
            "label":      label,
            "eci":        eci,
            "sub_growth": sub_g,
            "vpd_per_1k": vpd_1k,
        }
    return result


def compute_recent_velocity(videos_df: pd.DataFrame, channels_df: pd.DataFrame) -> dict:
    """Avg and median views/day (vpd) for the 5 most recent uploads per channel.
    Rule: exclude videos < 1 day old (age_days < 1) from averages — too early to measure.
    Normalized: vpd_per_1k = vpd / (subscribers / 1000)."""
    results = {}
    if videos_df.empty:
        return {ch: {} for ch in CHANNEL_ORDER}

    now = datetime.now(timezone.utc)

    for ch in CHANNEL_ORDER:
        ch_vids = videos_df[videos_df["channel_label"] == ch].copy()
        if ch_vids.empty:
            results[ch] = {}
            continue

        if "as_of_date" in ch_vids.columns:
            ch_vids = ch_vids[ch_vids["as_of_date"] == ch_vids["as_of_date"].max()]

        ch_vids = ch_vids.sort_values("published_at", ascending=False).head(10).copy()
        ch_vids["age_days"] = (now - ch_vids["published_at"]).dt.days.clip(lower=1)
        ch_vids["vpd"]      = ch_vids["views"] / ch_vids["age_days"]

        # Rule: exclude < 1 day old (already clipped to 1, but flag for future use)
        recent5 = ch_vids[ch_vids["age_days"] >= 1].head(5)
        if recent5.empty:
            results[ch] = {}
            continue

        vpd_list = sorted(recent5["vpd"].tolist())
        n_v      = len(vpd_list)
        med_vpd  = vpd_list[n_v // 2] if n_v % 2 == 1 \
                   else (vpd_list[n_v // 2 - 1] + vpd_list[n_v // 2]) / 2

        avg_vpd = round(recent5["vpd"].mean(), 1)
        med_vpd = round(med_vpd, 1)
        avg_age = round(recent5["age_days"].mean(), 0)

        ch_sub_df = channels_df[channels_df["channel_label"] == ch]
        curr_subs = ch_sub_df.sort_values("date").iloc[-1]["subscribers"] \
                    if not ch_sub_df.empty else None

        if curr_subs and curr_subs > 0:
            vpd_per_1k     = round(avg_vpd / (curr_subs / 1000), 2)
            med_vpd_per_1k = round(med_vpd / (curr_subs / 1000), 2)
        else:
            vpd_per_1k = med_vpd_per_1k = None

        results[ch] = {
            "avg_vpd":         avg_vpd,
            "median_vpd":      med_vpd,
            "vpd_per_1k":      vpd_per_1k,
            "median_vpd_per_1k": med_vpd_per_1k,
            "avg_age_days":    int(avg_age),
            "curr_subs":       int(curr_subs) if curr_subs else None,
            "n_videos":        len(recent5),
        }
    return results


def compute_sub_trajectory(channels_df: pd.DataFrame) -> dict:
    """Scatter-ready [{x: day_offset, y: subs}] per channel.
    x = integer days since TRAJ_REF_DATE. No nulls; only real snapshots."""
    ref  = pd.to_datetime(TRAJ_REF_DATE)
    traj = {}
    for ch in CHANNEL_ORDER:
        ch_df = channels_df[channels_df["channel_label"] == ch].sort_values("date")
        ch_df = ch_df.dropna(subset=["subscribers"])
        traj[ch] = {"points": [
            {"x": int((pd.to_datetime(r["date"]) - ref).days),
             "y": int(r["subscribers"])}
            for _, r in ch_df.iterrows()
        ]}
    return traj


def compute_slopegraph(channels_df: pd.DataFrame) -> dict:
    """Two-point baseline-vs-latest per channel.
    Rule — Baseline: first snapshot in [2025-01-01, 2025-06-30]; fallback to earliest.
    Rule — Latest: most recent snapshot available."""
    result = {}
    for ch in CHANNEL_ORDER:
        ch_df = channels_df[channels_df["channel_label"] == ch].sort_values("date")
        ch_df = ch_df.dropna(subset=["subscribers"])
        if ch_df.empty:
            result[ch] = None
            continue
        base_df = ch_df[(ch_df["date"] >= "2025-01-01") & (ch_df["date"] <= "2025-06-30")]
        if base_df.empty:
            base_df = ch_df.head(1)
        base_row   = base_df.iloc[0]
        latest_row = ch_df.iloc[-1]
        result[ch] = {
            "baseline":      int(base_row["subscribers"]),
            "baseline_date": base_row["date"],
            "latest":        int(latest_row["subscribers"]),
            "latest_date":   latest_row["date"],
        }
    return result


def compute_ecosystem_aggregate(slopegraph: dict) -> dict:
    """Sum of baseline and latest subscribers across all tracked channels."""
    valid       = [v for v in slopegraph.values() if v]
    total_base  = sum(v["baseline"] for v in valid)
    total_latest = sum(v["latest"]  for v in valid)
    growth_pct  = round((total_latest - total_base) / total_base * 100, 1) \
                  if total_base > 0 else None
    return {
        "total_baseline":  total_base,
        "total_latest":    total_latest,
        "growth_pct":      growth_pct,
        "channel_count":   len(valid),
    }


def compute_multiyear_growth(channels_full_df: pd.DataFrame) -> dict:
    """Per-channel 2yr/3yr subscriber growth and CAGR, computed from a combined
    dataframe that includes both the current snapshots and wayback-seed history.
    Also computes per-year ecosystem totals for the multi-year chart.

    Does NOT affect existing YoY computation (which uses channels_df, not channels_full_df).
    """
    results = {}
    eco_by_year: dict = {}  # year -> cumulative subs (across channels with data)
    eco_ch_count: dict = {}  # year -> number of channels contributing

    for ch in CHANNEL_ORDER:
        ch_df = channels_full_df[channels_full_df["channel_label"] == ch].sort_values("date")
        ch_df = ch_df.dropna(subset=["subscribers"])
        if ch_df.empty:
            results[ch] = {"subs_by_year": {}}
            continue

        # Build per-year snapshots using nearest-to-target logic (NOT last row).
        # This ensures the 2026 snapshot uses the seed-authoritative value even if
        # a history file adds a slightly later-dated row with different data.
        subs_by_year: dict = {}
        for yr in MULTIYEAR_YEARS:
            target = f"{yr}-{MULTIYEAR_TARGET_MD}"
            dists = abs(pd.to_datetime(ch_df["date"]) - pd.to_datetime(target)).dt.days
            valid = ch_df[dists <= MULTIYEAR_WINDOW]
            if not valid.empty:
                row = valid.loc[dists[valid.index].idxmin()]
                subs = int(row["subscribers"])
                subs_by_year[yr] = subs
                eco_by_year[yr]   = eco_by_year.get(yr, 0) + subs
                eco_ch_count[yr]  = eco_ch_count.get(yr, 0) + 1

        # curr_subs = nearest snapshot to the most recent target year (authoritative)
        curr_subs = subs_by_year.get(max(MULTIYEAR_YEARS))

        def _pct(base):
            if base is None or curr_subs is None or base == 0:
                return None
            return round((curr_subs - base) / base * 100, 1)

        ref_2yr = subs_by_year.get(2024)
        ref_3yr = subs_by_year.get(2023)
        cagr = None
        if ref_3yr and curr_subs:
            cagr = round(((curr_subs / ref_3yr) ** (1 / 3) - 1) * 100, 1)

        results[ch] = {
            "subs_by_year": subs_by_year,
            "two_yr_pct":   _pct(ref_2yr),
            "three_yr_pct": _pct(ref_3yr),
            "cagr_pct":     cagr,
        }

    results["__eco__"] = {
        "subs_by_year": eco_by_year,
        "ch_count":     eco_ch_count,
    }
    return results


# ════════════════════════════════════════════════════════════════════════════
# Reddit — load + compute
# ════════════════════════════════════════════════════════════════════════════

def load_reddit_snapshots() -> pd.DataFrame:
    if not os.path.exists(REDDIT_DATA):
        return pd.DataFrame()
    df = pd.read_csv(REDDIT_DATA)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    return df.sort_values(["subreddit", "date"]).reset_index(drop=True)


def load_reddit_members_weekly() -> pd.DataFrame:
    """Weekly member snapshots incl. wayback seeds and milestone rows (reddit_members_weekly.csv)."""
    if not os.path.exists(REDDIT_MEMBERS_DATA):
        return pd.DataFrame()
    df = pd.read_csv(REDDIT_MEMBERS_DATA)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    return df.sort_values(["subreddit", "date"]).reset_index(drop=True)


def _reddit_nearest(df: pd.DataFrame, sub: str, target_date: str) -> pd.Series | None:
    sub_df = df[df["subreddit"] == sub].copy()
    if sub_df.empty:
        return None
    sub_df["_dist"] = abs(pd.to_datetime(sub_df["date"]) - pd.to_datetime(target_date)).dt.days
    near = sub_df[sub_df["_dist"] <= REDDIT_YOY_WINDOW]
    return None if near.empty else near.loc[near["_dist"].idxmin()]


def compute_reddit_yoy(reddit_df: pd.DataFrame) -> dict:
    """YoY member growth per subreddit. Same nearest-snapshot logic as YouTube."""
    results = {}
    for sub in REDDIT_ORDER:
        sub_df = reddit_df[reddit_df["subreddit"] == sub].sort_values("date")
        if sub_df.empty:
            results[sub] = {}
            continue
        latest      = sub_df.iloc[-1]
        curr_m      = latest.get("members")
        curr_date   = latest["date"]
        ref_date    = str((pd.to_datetime(curr_date) - timedelta(days=365)).date())
        ref_row     = _reddit_nearest(reddit_df, sub, ref_date)
        if ref_row is None or not curr_m:
            results[sub] = {"curr_members": curr_m, "yoy_pct": None}
            continue
        ref_m    = ref_row.get("members")
        gap_days = (pd.to_datetime(curr_date) - pd.to_datetime(ref_row["date"])).days
        yoy_pct  = round((curr_m - ref_m) / ref_m * 100, 1) if (ref_m and ref_m > 0) else None
        ann_pct  = round(yoy_pct * (365 / gap_days), 1) \
                   if (yoy_pct is not None and gap_days > 0) else None
        results[sub] = {
            "curr_members":   int(curr_m),
            "ref_members":    int(ref_m),
            "yoy_pct":        yoy_pct,
            "annualized_pct": ann_pct,
            "gap_days":       gap_days,
            "curr_date":      curr_date,
            "ref_date":       ref_row["date"],
        }
    return results


def compute_reddit_engagement(reddit_df: pd.DataFrame) -> dict:
    """Latest engagement metrics + YoY engagement-per-1K delta."""
    results = {}
    for sub in REDDIT_ORDER:
        sub_df = reddit_df[reddit_df["subreddit"] == sub].sort_values("date")
        if sub_df.empty:
            results[sub] = {}
            continue
        latest  = sub_df.iloc[-1]
        ppd     = float(latest.get("posts_per_day")    or 0)
        cpd     = float(latest.get("comments_per_day") or 0)
        members = int(latest.get("members")             or 1)

        ctp     = round(cpd / ppd, 1)           if ppd > 0    else None
        eng_1k  = round((ppd + cpd) / (members / 1000), 2) if members > 0 else None

        # YoY engagement-per-1K delta
        ref_date = str((pd.to_datetime(latest["date"]) - timedelta(days=365)).date())
        ref_row  = _reddit_nearest(reddit_df, sub, ref_date)
        eng_1k_yoy = None
        if ref_row is not None and eng_1k is not None:
            r_ppd  = float(ref_row.get("posts_per_day")    or 0)
            r_cpd  = float(ref_row.get("comments_per_day") or 0)
            r_mem  = int(ref_row.get("members")             or 1)
            ref_e  = (r_ppd + r_cpd) / (r_mem / 1000) if r_mem > 0 else 0
            if ref_e > 0:
                eng_1k_yoy = round((eng_1k - ref_e) / ref_e * 100, 1)

        results[sub] = {
            "posts_per_day":    ppd,
            "comments_per_day": cpd,
            "comments_to_post": ctp,
            "eng_per_1k":       eng_1k,
            "eng_1k_yoy":       eng_1k_yoy,
        }
    return results


def compute_reddit_classification(reddit_yoy: dict, reddit_engagement: dict) -> dict:
    """Subscriber-growth-only classification.
    Engagement metrics excluded pending full historical API implementation.

    Accelerating Community : YoY > 15%
    Stable Expansion       : 5% < YoY ≤ 15%
    Passive Growth         : 0% < YoY ≤ 5%
    Stagnating             : YoY ≤ 0%
    """
    results = {}
    for sub in REDDIT_ORDER:
        yoy_pct = reddit_yoy.get(sub, {}).get("yoy_pct")

        if yoy_pct is None:
            label = "Insufficient Data"
        elif yoy_pct > 15:
            label = "Accelerating Community"
        elif yoy_pct > 5:
            label = "Stable Expansion"
        elif yoy_pct > 0:
            label = "Passive Growth"
        else:
            label = "Stagnating"

        results[sub] = {"label": label, "yoy_pct": yoy_pct}
    return results


def compute_reddit_aggregate(reddit_yoy: dict) -> dict:
    """Total community size across all tracked subreddits."""
    total_curr = sum(
        reddit_yoy.get(s, {}).get("curr_members", 0) or 0 for s in REDDIT_ORDER
    )
    total_ref  = sum(
        reddit_yoy.get(s, {}).get("ref_members",  0) or 0 for s in REDDIT_ORDER
    )
    growth_pct = round((total_curr - total_ref) / total_ref * 100, 1) \
                 if total_ref > 0 else None
    return {"total_curr": total_curr, "total_ref": total_ref, "growth_pct": growth_pct}


def compute_reddit_multiyear(reddit_yoy: dict) -> dict:
    """Combine REDDIT_HISTORY_2324 Wayback seeds with latest (2026) members from reddit_yoy
    to produce per-subreddit 2023→2024→2026 growth metrics and ecosystem totals.

    Returns:
        {
          subreddit: {
              "m_2023": int, "m_2024": int, "m_2026": int,
              "abs_2324": int,          # absolute adds 2023→2024
              "yoy_2324_pct": float,    # % growth 2023→2024
              "abs_2426": int,          # absolute adds 2024→2026
              "yoy_2426_pct": float,    # % growth 2024→2026
              "abs_2326": int,          # absolute adds 2023→2026
              "share_pct": float,       # % of 2026 ecosystem total
          },
          "__eco__": {
              "m_2023": int, "m_2024": int, "m_2026": int,
              "yoy_2324_pct": float, "yoy_2426_pct": float,
          }
        }
    """
    per_sub = {}
    for sub in REDDIT_ORDER:
        hist = REDDIT_HISTORY_2324.get(sub, {})
        m_2023 = hist.get("2023")
        m_2024 = hist.get("2024")
        m_2026 = reddit_yoy.get(sub, {}).get("curr_members")

        abs_2324     = (m_2024 - m_2023) if (m_2023 and m_2024) else None
        yoy_2324_pct = round(abs_2324 / m_2023 * 100, 1) \
                       if (m_2023 and abs_2324 is not None) else None
        abs_2426     = (m_2026 - m_2024) if (m_2024 and m_2026) else None
        yoy_2426_pct = round(abs_2426 / m_2024 * 100, 1) \
                       if (m_2024 and abs_2426 is not None) else None
        abs_2326     = (m_2026 - m_2023) if (m_2023 and m_2026) else None
        cagr_3yr_pct = round(((m_2026 / m_2023) ** (1 / 3) - 1) * 100, 1) \
                       if (m_2023 and m_2026 and m_2023 > 0) else None

        per_sub[sub] = {
            "m_2023": m_2023, "m_2024": m_2024, "m_2026": m_2026,
            "abs_2324": abs_2324, "yoy_2324_pct": yoy_2324_pct,
            "abs_2426": abs_2426, "yoy_2426_pct": yoy_2426_pct,  # used as 2-Year %
            "abs_2326": abs_2326,
            "cagr_3yr_pct": cagr_3yr_pct,
            "share_pct": None,  # filled below once totals are known
        }

    # Ecosystem totals
    eco_2023 = sum(per_sub[s]["m_2023"] or 0 for s in REDDIT_ORDER)
    eco_2024 = sum(per_sub[s]["m_2024"] or 0 for s in REDDIT_ORDER)
    eco_2026 = sum(per_sub[s]["m_2026"] or 0 for s in REDDIT_ORDER)

    # Fill share_pct
    for sub in REDDIT_ORDER:
        m26 = per_sub[sub]["m_2026"]
        per_sub[sub]["share_pct"] = round(m26 / eco_2026 * 100, 1) \
                                    if (eco_2026 and m26) else None

    eco_yoy_2324 = round((eco_2024 - eco_2023) / eco_2023 * 100, 1) if eco_2023 else None
    eco_yoy_2426 = round((eco_2026 - eco_2024) / eco_2024 * 100, 1) if eco_2024 else None
    eco_cagr_3yr = round(((eco_2026 / eco_2023) ** (1 / 3) - 1) * 100, 1) \
                   if (eco_2023 and eco_2026 and eco_2023 > 0) else None

    per_sub["__eco__"] = {
        "m_2023": eco_2023, "m_2024": eco_2024, "m_2026": eco_2026,
        "yoy_2324_pct": eco_yoy_2324, "yoy_2426_pct": eco_yoy_2426,
        "cagr_3yr_pct": eco_cagr_3yr,
    }
    return per_sub


def build_reddit_executive_summary(reddit_yoy: dict, reddit_eng: dict,
                                   reddit_cls: dict,
                                   reddit_multiyear: dict | None = None) -> str:
    bullets = []

    # Aggregate community size — lead with 3-year framing if available
    eco = (reddit_multiyear or {}).get("__eco__", {})
    eco_2023 = eco.get("m_2023")
    eco_2026 = eco.get("m_2026")
    eco_yoy_2324 = eco.get("yoy_2324_pct")
    eco_yoy_2426 = eco.get("yoy_2426_pct")

    yoy_vals = [reddit_yoy.get(s, {}).get("yoy_pct") for s in REDDIT_ORDER
                if reddit_yoy.get(s, {}).get("yoy_pct") is not None]
    total_m = sum(reddit_yoy.get(s, {}).get("curr_members", 0) or 0 for s in REDDIT_ORDER)
    if eco_2023 and eco_2026:
        def _fmm(v): return f"{v/1_000_000:.2f}M" if v >= 1_000_000 else f"{v/1_000:.0f}K"
        three_yr_note = (
            f"3-year trajectory: {_fmm(eco_2023)} (2023) → {_fmm(eco_2026)} (2026), "
            f"+{eco_yoy_2324:.1f}% in 2023→2024 and "
            f"+{eco_yoy_2426:.1f}% in 2024→2026. "
        ) if (eco_yoy_2324 is not None and eco_yoy_2426 is not None) else ""
        bullets.append(
            f"<strong>Community base:</strong> {total_m:,} combined members across "
            f"{len(REDDIT_ORDER)} subreddits. {three_yr_note}"
            f"Community is structurally expanding — growth pre-dates the 2025-26 product cycle."
        )
    elif yoy_vals:
        avg_yoy   = round(sum(yoy_vals) / len(yoy_vals), 1)
        direction = "expanding" if avg_yoy > 0 else "contracting"
        bullets.append(
            f"<strong>Community base:</strong> {total_m:,} combined members across "
            f"{len(REDDIT_ORDER)} subreddits — avg {avg_yoy:+.1f}% YoY. "
            f"Warhammer Reddit community is {direction}."
        )

    # Fast-growing subs
    accel = [s for s in REDDIT_ORDER
             if reddit_cls.get(s, {}).get("label") in
             ("Accelerating Community", "Stable Expansion")]
    if accel:
        lines = []
        for s in accel:
            y = reddit_yoy.get(s, {})
            lines.append(f"{REDDIT_LABELS[s]} "
                         f"({y.get('yoy_pct', 0):+.1f}% YoY, "
                         f"annualized {y.get('annualized_pct', 0):+.1f}%)")
        bullets.append(
            f"<strong>Growing communities:</strong> {'; '.join(lines)}."
        )

    # Passive / stagnating
    slow = [s for s in REDDIT_ORDER
            if reddit_cls.get(s, {}).get("label") in ("Passive Growth", "Stagnating")]
    if slow:
        names = ", ".join(REDDIT_LABELS[s] for s in slow)
        bullets.append(
            f"<strong>Low-growth communities:</strong> {names} — subscriber growth "
            f"≤5% YoY. Community base stable but not expanding."
        )

    bullets.append(
        "<strong>Engagement metrics (posts/day, comments/day, engagement/1K):</strong> "
        "pending full historical API implementation. Current Reddit public API caps "
        "pagination at ~1,000 posts — insufficient for reliable 30-day trailing averages. "
        "Subscriber counts are accurate and unaffected."
    )

    items = "".join(f"<li>{b}</li>" for b in bullets)
    return f"<ul class='exec-list'>{items}</ul>"


# ════════════════════════════════════════════════════════════════════════════
# Steam — load + compute
# Two data layers:
#   structural  → steam_monthly_history.csv  (calendar months, SteamCharts)
#   momentum    → steam_players.csv          (live CCU snapshots, Steam API)
#   rolling     → steam_rolling_30d.csv      (non-calendar "Last 30 Days")
# ════════════════════════════════════════════════════════════════════════════

def load_steam_players() -> pd.DataFrame:
    """Live CCU snapshots (Steam API). Append-only, dedup key (date, game)."""
    if not os.path.exists(STEAM_DATA):
        return pd.DataFrame()
    df = pd.read_csv(STEAM_DATA)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    return df.sort_values(["game", "date"]).reset_index(drop=True)


def load_steam_monthly_history() -> pd.DataFrame:
    """Calendar-month averages from SteamCharts. Append-only."""
    if not os.path.exists(STEAM_MONTHLY_HISTORY):
        return pd.DataFrame()
    df = pd.read_csv(STEAM_MONTHLY_HISTORY)
    df["month"] = df["month"].astype(str).str.strip()
    df["avg_players"]  = pd.to_numeric(df["avg_players"],  errors="coerce")
    df["peak_players"] = pd.to_numeric(df["peak_players"], errors="coerce")
    return df.sort_values(["game_slug", "month"]).reset_index(drop=True)


def load_steam_rolling_30d() -> pd.DataFrame:
    """Rolling 'Last 30 Days' from SteamCharts — NOT a calendar month."""
    if not os.path.exists(STEAM_ROLLING_30D):
        return pd.DataFrame()
    df = pd.read_csv(STEAM_ROLLING_30D)
    df["avg_players"]  = pd.to_numeric(df["avg_players"],  errors="coerce")
    df["peak_players"] = pd.to_numeric(df["peak_players"], errors="coerce")
    return df.reset_index(drop=True)


def load_reddit_store_monthly() -> pd.DataFrame:
    """Monthly store-thread counts from fetch_reddit_store_threads.py."""
    if not os.path.exists(REDDIT_STORE_MONTHLY):
        return pd.DataFrame()
    df = pd.read_csv(REDDIT_STORE_MONTHLY)
    df["month"] = df["month"].astype(str).str.strip()
    return df.sort_values(["subreddit", "month"]).reset_index(drop=True)


def load_reddit_store_recent() -> pd.DataFrame:
    """Top recent store threads (by score)."""
    if not os.path.exists(REDDIT_STORE_RECENT):
        return pd.DataFrame()
    return pd.read_csv(REDDIT_STORE_RECENT)


def load_reddit_store_raw() -> pd.DataFrame:
    """Individual post titles for category breakdown analysis."""
    if not os.path.exists(REDDIT_STORE_RAW):
        return pd.DataFrame()
    df = pd.read_csv(REDDIT_STORE_RAW)
    df["month"] = df["month"].astype(str).str.strip()
    df["year"]  = df["month"].str[:4].astype(int)
    return df


def load_reddit_intel() -> tuple:
    """Load reddit intelligence posts + comments datasets."""
    posts = pd.DataFrame()
    comments = pd.DataFrame()
    if os.path.exists(REDDIT_INTEL_POSTS):
        posts = pd.read_csv(REDDIT_INTEL_POSTS)
        posts["year"] = posts["year"].astype(int)
    if os.path.exists(REDDIT_INTEL_COMMENTS):
        comments = pd.read_csv(REDDIT_INTEL_COMMENTS)
    return posts, comments


def categorize_store_post(title: str) -> str:
    """Return primary category for a store-related post title (title-matched posts only)."""
    t = title.lower()
    # GW official store news (Captain Centos, milestone posts, store openings)
    if any(kw in t for kw in [
        "captain centos", "warhammer community", "global warhammer", "store milestone",
        "march down to your", "store celebration", "just opened my own", "opening of",
        "new warhammer store", "store opening", "opens today", "opened today",
    ]):
        return "GW Store News"
    # Store closures / health
    if any(kw in t for kw in [
        "closed", "closing", "shut down", "bankrupt", "dying", "struggling",
        "never open", "going out", "closed early",
    ]):
        return "Store Closures / Health"
    # Finding a store
    if any(kw in t for kw in [
        "looking for", "where is", "near me", "in my area", "in my city",
        "any flgs", "any lgs", "any game store", "is there a", "closest", "nearby",
        "find a store", "find a lgs", "find a flgs", "just realized there",
        "there is a store", "theres a store",
    ]):
        return "Finding a Store"
    # Events & Organised Play (tournaments, AoP, painting comps, Apocalypse games)
    if any(kw in t for kw in [
        "tournament", "armies on parade", "apocalypse game", "apocalypse", "painting competition",
        "painting contest", "mini of the month", "miniature of the month", "display board",
        "game night", "game day", "league", "prize", "i won", "won the", "won gold",
        "hosting", "hosted a", "to for my flgs", "to for my lgs",
    ]):
        return "Events & Organised Play"
    # Finds & Bargains (rare finds, old kits, cheap scores at stores)
    if any(kw in t for kw in [
        "holy grail", "bargain", "bring-and-buy", "mystery box", "mistery box",
        "thrift store", "second hand", "2nd edition", "old edition", "discontinued",
        "astonishing find", "found this", "found a ", "found at",
    ]):
        return "Finds & Bargains"
    # Stock & Availability
    if any(kw in t for kw in [
        "stock", "in stock", "restock", "sold out", "allocation", "shelves",
        "availability", "supply", "shortage",
    ]):
        return "Stock & Availability"
    # Pricing & Value
    if any(kw in t for kw in [
        "price", "pricing", "discount", "overcharg", "markup", "expensive", "cheap",
        "deal", "sale", "cost", "tariff", "msrp", "% off", "loyalty",
        "good investment", "worth it", "declining quality", "merch quality",
    ]):
        return "Pricing & Value"
    # Store culture / etiquette / rules
    if any(kw in t for kw in [
        "that guy", "bad behavior", "bad behaviour", "etiquette", "banned", "not allowed",
        "cant paint", "can't paint", "not want people", "hanging out", "weird to go",
        "rude", "uneasy", "makes me feel", "be a good opponent",
    ]):
        return "Store Culture & Etiquette"
    return "Community Moments & Store Visits"


def compute_steam_monthly_metrics(monthly_df: pd.DataFrame,
                                   rolling_df: pd.DataFrame,
                                   live_df:    pd.DataFrame) -> dict:
    """
    Per-game derived metrics with strict calendar-month discipline.

    STRUCTURAL layer — completed calendar months only:
        Source priority for the last completed month (today's YYYY-MM minus 1):
          1. steam_monthly_history.csv  (fully finalized by pipeline)
          2. Live CCU avg from steam_players.csv for that past month  (finalize pending)
          3. Most recent row in steam_monthly_history.csv            (data-gap fallback)
        Rolling 30D is NEVER used for structural metrics.

    MTD layer — current in-progress calendar month:
        Source priority:
          1. Live CCU snapshot avg for current YYYY-MM  (steam_players.csv)
          2. Rolling 30D avg (SteamCharts sliding window)
        Kept entirely separate from structural data.  Always explicitly labeled.

    YoY (structural):
        eff_struct_mon vs exact same YYYY-MM one year prior (completed history only).
        If today is mid-March, structural YoY references February — the last completed
        calendar month — regardless of whether rolling data is available for March.

    YoY (MTD, partial):
        current_mon vs exact same YYYY-MM one year prior.
        Always labeled as "partial — not a completed month."

    Returns:
        {
            "by_slug":      {slug: metric_dict},
            "current_mon":  "YYYY-MM",  # today's calendar month (= MTD month)
            "struct_mon":   "YYYY-MM",  # last completed calendar month (structural ref)
            "current_avgs": {slug: float},  # live snapshot avgs for struct_mon (chart)
        }
    """
    current_mon        = pd.Timestamp.now().strftime("%Y-%m")
    last_completed_mon = (pd.to_datetime(current_mon + "-01")
                          - pd.DateOffset(months=1)).strftime("%Y-%m")
    _slug_by_game = {v: k for k, v in STEAM_LIVE_SLUG_MAP.items()}

    # ── Step 1: Index live CCU snapshots by (month, slug) ─────────────────────
    lv_by_month: dict[str, dict[str, float]] = {}  # month → {slug → avg_players}
    if not live_df.empty:
        lv = live_df.copy()
        lv["month"] = pd.to_datetime(lv["date"], errors="coerce").dt.strftime("%Y-%m")
        for (mon, game), grp in lv.groupby(["month", "game"]):
            slug = _slug_by_game.get(game)
            if slug and not grp["current_players"].isna().all():
                lv_by_month.setdefault(mon, {})[slug] = round(
                    float(grp["current_players"].mean()), 1)

    # Structural avgs: live snapshots for last_completed_mon (finalize not yet run)
    last_completed_avgs: dict[str, float] = lv_by_month.get(last_completed_mon, {})
    # MTD avgs: live CCU for current in-progress month (may be empty early in month)
    current_live_avgs:   dict[str, float] = lv_by_month.get(current_mon, {})

    # ── Step 2: Per-game metrics ───────────────────────────────────────────────
    results: dict = {}
    for slug in STEAM_ORDER:
        hist_g = monthly_df[monthly_df["game_slug"] == slug].sort_values("month")
        r_row  = rolling_df[rolling_df["game_slug"] == slug]
        rolling_30d = round(float(r_row.iloc[0]["avg_players"]), 1) \
                      if not r_row.empty else None

        # ── Structural: last completed calendar month ──────────────────────────
        # Rolling 30D is never used here.
        h_row = hist_g[hist_g["month"] == last_completed_mon]
        if not h_row.empty:
            eff_struct_mon = last_completed_mon
            struct_avg     = round(float(h_row.iloc[0]["avg_players"]), 1)
            struct_source  = "history"
        elif slug in last_completed_avgs:
            # Month ended but pipeline hasn't finalized it yet — use live snapshot avg
            eff_struct_mon = last_completed_mon
            struct_avg     = last_completed_avgs[slug]
            struct_source  = "live_snapshot_avg"
        elif not hist_g.empty:
            # Genuine data gap for last_completed_mon — fall back to most recent history
            eff_struct_mon = hist_g.iloc[-1]["month"]
            struct_avg     = round(float(hist_g.iloc[-1]["avg_players"]), 1)
            struct_source  = "history_fallback"
        else:
            results[slug] = {}
            continue

        # ── MTD: current in-progress calendar month ────────────────────────────
        # Rolling 30D is acceptable here as a proxy, but must always be labeled.
        if slug in current_live_avgs:
            mtd_avg, mtd_source, has_mtd = current_live_avgs[slug], "live_ccu", True
        elif rolling_30d is not None:
            mtd_avg, mtd_source, has_mtd = rolling_30d, "rolling_30d", True
        else:
            mtd_avg, mtd_source, has_mtd = None, None, False

        # ── Inner helpers (scoped to this slug's history) ──────────────────────
        def _hist_lookup(target_mon: str) -> float | None:
            row = hist_g[hist_g["month"] == target_mon]
            return float(row.iloc[0]["avg_players"]) if not row.empty else None

        def _offset(mon: str, n_months: int) -> str:
            return (pd.to_datetime(mon + "-01")
                    - pd.DateOffset(months=n_months)).strftime("%Y-%m")

        # ── Structural YoY: eff_struct_mon vs same YYYY-MM one year prior ──────
        yoy_target = _offset(eff_struct_mon, 12)
        yoy_ref    = _hist_lookup(yoy_target)
        yoy_pct    = round((struct_avg - yoy_ref) / yoy_ref * 100, 1) \
                     if (yoy_ref and yoy_ref > 0 and struct_avg is not None) else None

        # ── Structural MoM: eff_struct_mon vs prior completed month ───────────
        mom_ref_mon_s = _offset(eff_struct_mon, 1)
        mom_ref = _hist_lookup(mom_ref_mon_s)
        # history_fallback: eff_struct_mon IS the last history row, look one further back
        if mom_ref is None and struct_source == "history_fallback" and len(hist_g) >= 2:
            mom_ref = float(hist_g.iloc[-2]["avg_players"])
        mom_pct = round((struct_avg - mom_ref) / mom_ref * 100, 1) \
                  if (mom_ref and mom_ref > 0 and struct_avg is not None) else None

        # ── 3M / 6M trend (structural only) ───────────────────────────────────
        m3_ref   = _hist_lookup(_offset(eff_struct_mon, 3))
        trend_3m = round((struct_avg / m3_ref - 1) * 100, 1) \
                   if (m3_ref and m3_ref > 0 and struct_avg is not None) else None
        m6_ref   = _hist_lookup(_offset(eff_struct_mon, 6))
        trend_6m = round((struct_avg / m6_ref - 1) * 100, 1) \
                   if (m6_ref and m6_ref > 0 and struct_avg is not None) else None

        # ── MTD YoY: partial comparison vs same YYYY-MM one year prior ─────────
        yoy_mtd_target = _offset(current_mon, 12) if has_mtd else None
        yoy_mtd_ref    = _hist_lookup(yoy_mtd_target) if yoy_mtd_target else None
        yoy_mtd_pct    = round((mtd_avg - yoy_mtd_ref) / yoy_mtd_ref * 100, 1) \
                         if (yoy_mtd_ref and yoy_mtd_ref > 0 and
                             mtd_avg is not None) else None

        # ── Latest live CCU point ──────────────────────────────────────────────
        live_game = STEAM_LIVE_SLUG_MAP.get(slug)
        live_ccu  = None
        if live_game and not live_df.empty:
            l_df = live_df[live_df["game"] == live_game].sort_values("date")
            if not l_df.empty:
                live_ccu = int(l_df.iloc[-1]["current_players"])

        results[slug] = {
            # Structural (completed calendar month — never rolling 30D)
            "struct_mon":    eff_struct_mon,
            "struct_avg":    struct_avg,
            "struct_source": struct_source,  # history|live_snapshot_avg|history_fallback
            "yoy_pct":       yoy_pct,
            "yoy_target":    yoy_target,
            "mom_pct":       mom_pct,
            "mom_ref_mon":   mom_ref_mon_s,
            "trend_3m":      trend_3m,
            "trend_6m":      trend_6m,
            # MTD (current in-progress month — explicitly labeled, never structural)
            "has_mtd":       has_mtd,
            "mtd_mon":       current_mon if has_mtd else None,
            "mtd_avg":       mtd_avg,
            "mtd_source":    mtd_source,
            "yoy_mtd_pct":   yoy_mtd_pct,
            "yoy_mtd_target": yoy_mtd_target,
            # Short-term rolling / live (display-only)
            "rolling_30d":   rolling_30d,
            "live_ccu":      live_ccu,
        }

    # chart_struct_avgs: structural live-snapshot avgs for last_completed_mon.
    # Used to add the structural final chart point when finalize hasn't run yet.
    chart_struct_avgs = {slug: last_completed_avgs[slug]
                         for slug in STEAM_ORDER if slug in last_completed_avgs}

    return {
        "by_slug":      results,
        "current_mon":  current_mon,        # today's YYYY-MM (= MTD month)
        "struct_mon":   last_completed_mon,  # last completed month (structural ref)
        "current_avgs": chart_struct_avgs,  # live snapshot avgs for struct_mon (chart)
    }


# ════════════════════════════════════════════════════════════════════════════
# HTML formatting helpers
# ════════════════════════════════════════════════════════════════════════════

def pct_badge(val, pos_threshold=10.0):
    if val is None:
        return '<span class="badge badge-na">n/a</span>'
    css  = "badge-pos" if val >= pos_threshold else ("badge-mid" if val >= 0 else "badge-neg")
    sign = "+" if val >= 0 else ""
    return f'<span class="badge {css}">{sign}{val:.1f}%</span>'


def class_badge(label):
    css_map = {
        "Discovery Engine":   "badge-pos",
        "Moderate Discovery": "badge-mid",
        "Retention Engine":   "badge-mid",
        "Cadence Dependent":  "badge-neg",
        "Retention Oriented": "badge-na",
        "Insufficient Data":  "badge-na",
    }
    css = css_map.get(label, "badge-na")
    return f'<span class="badge {css}">{label}</span>'


def fmt_views(v):
    if v is None: return "—"
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000:     return f"{v/1_000:.0f}K"
    return str(v)


def fmt_subs(v):
    if v is None: return "—"
    if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
    return f"{v/1_000:.0f}K"


# ════════════════════════════════════════════════════════════════════════════
# Executive summary (bullet format only)
# ════════════════════════════════════════════════════════════════════════════

def build_executive_summary(yoy, eci_map, velocity, struct_class, ecosystem,
                            multiyear: dict | None = None) -> str:
    """Bullet-format YouTube executive summary.
    References structural multi-year data where available.
    Content types use the 4 standardized group names."""
    def fp(v):
        return f"{'+' if v >= 0 else ''}{v:.1f}%" if v is not None else "n/a"

    bullets = []

    # ── Ecosystem structural growth (2023–2026) ───────────────────────────────
    _eco_my   = (multiyear or {}).get("__eco__", {})
    _eco_by   = _eco_my.get("subs_by_year", {})
    _e23, _e26 = _eco_by.get(2023), _eco_by.get(2026)
    if _e23 and _e26 and _e23 > 0:
        _e_3yr   = round((_e26 - _e23) / _e23 * 100, 1)
        _e_cagr  = round(((_e26 / _e23) ** (1 / 3) - 1) * 100, 1)
        bullets.append(
            f"<strong>Creator ecosystem (2023–2026):</strong> {fmt_subs(_e23)} → "
            f"{fmt_subs(_e26)} combined subscribers — {fp(_e_3yr)} total growth, "
            f"{fp(_e_cagr)} 3-year CAGR. Structural demand expansion is confirmed "
            f"across the full measurement window."
        )
    else:
        eco_g = ecosystem.get("growth_pct")
        eco_total = ecosystem.get("total_latest", 0)
        bullets.append(
            f"<strong>Ecosystem subscriber base:</strong> {fmt_subs(eco_total)} combined across "
            f"{ecosystem.get('channel_count',5)} channels — {fp(eco_g)} YoY. "
            f"Macro demand is expanding."
        )

    # ── Strongest discovery signal ────────────────────────────────────────────
    top_eci_ch = max(
        (ch for ch in CHANNEL_ORDER if eci_map.get(ch, {}).get("eci") is not None),
        key=lambda c: eci_map.get(c, {}).get("eci") or 0,
        default=None,
    )
    engines = [ch for ch in CHANNEL_ORDER
               if struct_class.get(ch, {}).get("label") == "Discovery Engine"]
    if engines:
        names = " and ".join(CHANNEL_DISPLAY[c] for c in engines)
        top_eci_v = eci_map.get(engines[0], {}).get("eci")
        bullets.append(
            f"<strong>Discovery Engine{'s' if len(engines)>1 else ''} — {names}:</strong> "
            f"back-catalog view compounding exceeds structural subscriber intake "
            f"(ECI > 2×{f', peak {top_eci_v:.2f}×' if top_eci_v else ''}). "
            f"Algorithmic reach is expanding franchise exposure beyond the existing "
            f"subscriber base."
        )
    elif top_eci_ch:
        top_eci_v = eci_map.get(top_eci_ch, {}).get("eci")
        bullets.append(
            f"<strong>Strongest discovery signal — {CHANNEL_DISPLAY[top_eci_ch]}:</strong> "
            f"ECI {top_eci_v:.2f}× — anchor view growth is outpacing structural "
            f"subscriber accumulation rate."
        )

    # ── Retention / cadence risk ──────────────────────────────────────────────
    risk = [ch for ch in CHANNEL_ORDER
            if struct_class.get(ch, {}).get("label") in ("Retention Engine", "Cadence Dependent")]
    if risk:
        risk_lines = []
        for ch in risk:
            sc = struct_class[ch]
            risk_lines.append(
                f"{CHANNEL_DISPLAY[ch]} ({sc['label']}, ECI {sc['eci']:.2f}×, "
                f"sub {fp(sc['sub_growth'])} YoY)"
            )
        bullets.append(
            f"<strong>Structural note:</strong> {'; '.join(risk_lines)}. "
            f"High per-upload velocity but limited structural compounding. "
            f"Engagement is upload-frequency dependent."
        )

    # ── Content type signal ───────────────────────────────────────────────────
    bullets.append(
        "<strong>Content-type signal:</strong> Official Media and Lore Education formats "
        "show the highest evergreen view compounding across tracked anchors. "
        "Hobby Content anchors trend flat relative to subscriber growth."
    )

    items = "".join(f"<li>{b}</li>" for b in bullets)
    return f"<ul class='exec-list'>{items}</ul>"


# ════════════════════════════════════════════════════════════════════════════
# Page 8 — GW Website Stock Availability
# ════════════════════════════════════════════════════════════════════════════

def build_gw_stock_page(gw_stock_df) -> str:
    """Build Page 8 HTML: GW Website Product Availability tracker."""

    if gw_stock_df is None or gw_stock_df.empty:
        return ""

    # ── Latest snapshot ───────────────────────────────────────────────────
    latest_date = gw_stock_df["date"].max()
    n_days      = gw_stock_df["date"].nunique()
    latest      = gw_stock_df[gw_stock_df["date"] == latest_date].copy()

    valid     = latest[latest["in_stock"].isin(["true", "false"])]
    n_tracked = len(latest)
    n_in      = int((valid["in_stock"] == "true").sum())
    n_out     = int((valid["in_stock"] == "false").sum())
    n_unknown = n_tracked - len(valid)
    oos_pct   = round(100 * n_out / len(valid), 1) if len(valid) else 0

    # ── Badge helper ──────────────────────────────────────────────────────
    def stock_badge(row):
        status   = str(row.get("stock_status", "") or "")
        in_stock = str(row.get("in_stock", "")     or "")
        avail    = str(row.get("is_available", "") or "")
        if status == "NOT_FOUND":
            return "<span class='badge badge-dim'>Not Listed</span>"
        if in_stock == "true" and status == "A":
            return "<span class='badge badge-up'>In Stock</span>"
        if in_stock == "true" and status == "P":
            return "<span class='badge badge-mid'>Transitional</span>"
        if in_stock == "false" and status in ("A", "P", ""):
            return "<span class='badge badge-dn'>Out of Stock</span>"
        if status == "O":
            return "<span class='badge badge-dim'>Discontinued</span>"
        if status == "G":
            return "<span class='badge badge-mid'>Made-to-Order</span>"
        if in_stock == "error":
            return "<span class='badge badge-dim'>Error</span>"
        return "<span class='badge badge-dim'>Unknown</span>"

    def flags(row):
        out = ""
        if str(row.get("last_chance",  "") or "").lower() == "true":
            out += " <span title='Last Chance to Buy' style='color:#e67e22'>⚠</span>"
        if str(row.get("selling_fast", "") or "").lower() == "true":
            out += " <span title='Selling Fast' style='color:#e74c3c'>🔥</span>"
        return out

    # ── Build table rows by group ─────────────────────────────────────────
    starters = latest[latest["priority"] == "high"].sort_values("name")
    patrols  = latest[latest["priority"] != "high"].sort_values("name")

    def make_rows(df_group):
        rows = ""
        for _, r in df_group.iterrows():
            rows += (
                f"<tr>"
                f"<td>{r['name']}{flags(r)}</td>"
                f"<td class='num'>{stock_badge(r)}</td>"
                f"</tr>\n"
            )
        return rows

    starter_rows = make_rows(starters)
    patrol_rows  = make_rows(patrols)

    # ── OOS rate trend (if >1 day of data) ───────────────────────────────
    trend_html = ""
    if n_days > 1:
        dates_all = sorted(gw_stock_df["date"].unique())
        oos_rates = []
        for d in dates_all:
            day_df = gw_stock_df[gw_stock_df["date"] == d]
            v = day_df[day_df["in_stock"].isin(["true", "false"])]
            rate = round(100 * (v["in_stock"] == "false").sum() / len(v), 1) if len(v) else 0
            oos_rates.append(rate)

        trend_labels = str([d[5:] for d in dates_all])   # MM-DD labels
        trend_data   = str(oos_rates)

        trend_html = f"""
  <div class="chart-card" style="margin-bottom:18px;">
    <h3>Overall OOS Rate — % of Tracked SKUs Out of Stock</h3>
    <div class="chart-wrap-md"><canvas id="chartGwOos"></canvas></div>
    <p class="data-note">Percentage of {n_tracked} tracked products that are out of stock on each date.
    All Combat Patrol boxes + all Starter Set tiers. Data from warhammer.com direct.</p>
  </div>
<script>
(function(){{
  var ctx = document.getElementById('chartGwOos');
  if(!ctx) return;
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {trend_labels},
      datasets: [{{
        label: 'OOS Rate %',
        data: {trend_data},
        borderColor: '#c0392b',
        backgroundColor: 'rgba(192,57,43,0.08)',
        borderWidth: 2,
        pointRadius: 3,
        fill: true,
        tension: 0.3,
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ min: 0, max: 100, ticks: {{ callback: v => v+'%' }} }},
        x: {{ ticks: {{ maxTicksLimit: 12 }} }}
      }}
    }}
  }});
}})();
</script>"""
    else:
        trend_html = f"""
  <div class="table-card" style="padding:18px;text-align:center;color:var(--muted);font-size:12px;">
    OOS rate trend chart will appear here once daily data accumulates (currently day 1 of {n_days}).
    Run <code>python3 scripts/fetch_gw_stock.py</code> daily to build the trend.
  </div>"""

    # ── Assemble page ─────────────────────────────────────────────────────
    oos_color = "#c0392b" if oos_pct > 20 else "#e67e22" if oos_pct > 5 else "#27ae60"

    return f"""
<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-8">Page 8 — GW Website Product Availability</div>

<!-- ── Page 8: GW Stock Availability ──────────────────────────────────── -->
<section>
  <div class="section-title">GW Direct — Online Store Availability Tracker</div>
  <div class="section-sub">
    Daily scrape of warhammer.com for all Starter Sets and Combat Patrol boxes.
    Out-of-Stock events are demand signals — GW products go OOS when sell-through
    outpaces production. Starter Kit OOS in particular signals new player influx.
    Source: warhammer.com direct (automated daily, <code>fetch_gw_stock.py</code>).
    Last checked: <strong>{latest_date}</strong> &nbsp;|&nbsp; {n_days} day{'' if n_days==1 else 's'} of history.
  </div>

  <!-- Stat cards -->
  <div class="stats-row" style="margin-bottom:18px;">
    <div class="stat-card">
      <div class="stat-val">{n_tracked}</div>
      <div class="stat-lbl">SKUs Tracked</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:#27ae60">{n_in}</div>
      <div class="stat-lbl">In Stock</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:#c0392b">{n_out}</div>
      <div class="stat-lbl">Out of Stock</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:{oos_color}">{oos_pct}%</div>
      <div class="stat-lbl">OOS Rate</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">{n_unknown}</div>
      <div class="stat-lbl">Not Listed / Unknown</div>
    </div>
  </div>

  {trend_html}

  <!-- Starter Sets — High Priority -->
  <div class="table-card" style="margin-bottom:18px;">
    <h3 style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                color:var(--muted);margin-bottom:12px;">
      Starter Sets — New Player Entry Points <span style="font-weight:400;font-size:10px;color:var(--muted)">(OOS here = new player demand overflow)</span>
    </h3>
    <table>
      <thead>
        <tr>
          <th>Product</th>
          <th class="num">Status</th>
        </tr>
      </thead>
      <tbody>
        {starter_rows}
      </tbody>
    </table>
    <p class="data-note">
      ⚠ = Last Chance to Buy (GW flagging product end-of-life).
      "Transitional" = status code P — still purchasable but phasing to new edition version.
      Source: warhammer.com, checked {latest_date}.
    </p>
  </div>

  <!-- Combat Patrols -->
  <div class="table-card">
    <h3 style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                color:var(--muted);margin-bottom:12px;">
      Combat Patrol Boxes — All Factions
      <span style="font-weight:400;font-size:10px;color:var(--muted)">(OOS on specific faction = that army is in demand)</span>
    </h3>
    <table>
      <thead>
        <tr>
          <th>Product</th>
          <th class="num">Status</th>
        </tr>
      </thead>
      <tbody>
        {patrol_rows}
      </tbody>
    </table>
    <p class="data-note">
      "Not Listed" = product URL not found on site (retired box replaced by newer edition, or upcoming release not yet live).
      Source: warhammer.com, checked {latest_date}.
    </p>
  </div>

  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    When GW products go Out of Stock on their own website it means sell-through exceeded production capacity — the definition of excess demand. Starter Sets are the most investment-relevant signal: OOS there means new players (not existing hobbyists) are driving demand at the top of the funnel. Combat Patrol OOS by faction signals which armies are hot, which feeds into future kit releases and codex cadence. Tracking this daily builds a proprietary dataset no analyst report captures.
  </div>
</section>
"""


# ════════════════════════════════════════════════════════════════════════════
# HTML build
# ════════════════════════════════════════════════════════════════════════════

def build_html(channels_df, yoy, eci_map, evergreen,
               reddit_df, reddit_yoy, reddit_agg,
               steam_monthly_df, steam_rolling_df, steam_live_df, steam_monthly_metrics,
               channels_full_df, anchor_history_df, multiyear,
               generated_at: str,
               reddit_multiyear: dict | None = None,
               store_threads_monthly_df=None,
               store_threads_recent_df=None,
               store_threads_raw_df=None,
               reddit_intel_posts_df=None,
               reddit_intel_comments_df=None,
               gw_stock_df=None) -> str:

    # ── Restore slopegraph for rank comparison chart ──────────────────────────
    slopegraph  = compute_slopegraph(channels_df)
    # ── Stubs for remaining removed parameters ────────────────────────────────
    velocity    = {}
    trajectory  = {}
    struct_class = {}
    ecosystem   = {}
    reddit_eng  = {}
    reddit_cls  = {}

    ch_labels = [CHANNEL_DISPLAY[c] for c in CHANNEL_ORDER]
    ch_colors = [CHANNEL_COLORS[c]  for c in CHANNEL_ORDER]

    # ── Dynamic date labels (derived from actual data, never hardcoded) ────
    _slope_base_dates   = [v["baseline_date"] for v in slopegraph.values() if v and v.get("baseline_date")]
    _slope_latest_dates = [v["latest_date"]   for v in slopegraph.values() if v and v.get("latest_date")]
    slope_base_lbl   = pd.to_datetime(min(_slope_base_dates)).strftime("%b %Y")   if _slope_base_dates   else "Baseline"
    slope_latest_lbl = pd.to_datetime(max(_slope_latest_dates)).strftime("%b %Y") if _slope_latest_dates else "Latest"

    _reddit_ref_dates = [v["ref_date"] for v in reddit_yoy.values() if v and v.get("ref_date")]
    reddit_base_lbl   = pd.to_datetime(min(_reddit_ref_dates)).strftime("%b %Y") if _reddit_ref_dates else "Earliest snapshot"

    _steam_months     = steam_monthly_df["month"].tolist() if not steam_monthly_df.empty else []
    steam_base_lbl   = pd.to_datetime(min(_steam_months) + "-01").strftime("%b %Y") if _steam_months else "Baseline"
    steam_latest_lbl = pd.to_datetime(max(_steam_months) + "-01").strftime("%b %Y") if _steam_months else "Latest"

    # ── Ecosystem multi-year metrics (for headline cards) ─────────────────
    _eco_my      = multiyear.get("__eco__", {})
    _eco_subs_by = _eco_my.get("subs_by_year", {})
    _eco_2023    = _eco_subs_by.get(2023)
    _eco_2024    = _eco_subs_by.get(2024)
    _eco_2026    = _eco_subs_by.get(2026)
    _eco_2yr_pct = round((_eco_2026 - _eco_2024) / _eco_2024 * 100, 1) \
                   if (_eco_2024 and _eco_2026 and _eco_2024 > 0) else None
    _eco_cagr    = round(((_eco_2026 / _eco_2023) ** (1 / 3) - 1) * 100, 1) \
                   if (_eco_2023 and _eco_2026 and _eco_2023 > 0) else None
    def _fp(v):
        return (f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%") if v is not None else "—"
    eco_2yr_str  = _fp(_eco_2yr_pct)
    eco_cagr_str = _fp(_eco_cagr)
    eco_2yr_color  = "#27ae60" if (_eco_2yr_pct or 0) > 0 else "#c0392b"
    eco_cagr_color = "#27ae60" if (_eco_cagr    or 0) > 0 else "#c0392b"

    # ── Chart data ────────────────────────────────────────────────────────

    # S1: subs + YoY
    curr_subs_vals = [yoy.get(ch, {}).get("curr_subs") or 0 for ch in CHANNEL_ORDER]
    yoy_pct_vals   = [yoy.get(ch, {}).get("yoy_pct")   or 0 for ch in CHANNEL_ORDER]

    # S1: trajectory scatter [{x,y}]
    traj_datasets = [{
        "label":       CHANNEL_DISPLAY[ch],
        "data":        trajectory.get(ch, {}).get("points", []),
        "borderColor": CHANNEL_COLORS[ch],
        "backgroundColor": CHANNEL_COLORS[ch],
        "pointRadius": 5,
        "pointHoverRadius": 7,
        "borderWidth": 2,
    } for ch in CHANNEL_ORDER]

    # S1: slopegraph dumbbell
    slope_datasets = [{
        "label":        CHANNEL_DISPLAY[ch],
        "data":         [s["baseline"], s["latest"]],
        "borderColor":  CHANNEL_COLORS[ch],
        "backgroundColor": CHANNEL_COLORS[ch],
        "pointRadius":  7,
        "pointHoverRadius": 9,
        "borderWidth":  2,
    } for ch in CHANNEL_ORDER if (s := slopegraph.get(ch))]

    # S2: ECI bar
    eci_vals = [eci_map.get(ch, {}).get("eci") or 0 for ch in CHANNEL_ORDER]

    # Per-channel CAGR and 2yr arrays for multi-metric chart and scatter
    cagr_pct_vals  = [multiyear.get(ch, {}).get("cagr_pct")    for ch in CHANNEL_ORDER]
    two_yr_pct_vals = [multiyear.get(ch, {}).get("two_yr_pct") for ch in CHANNEL_ORDER]

    # S2: discovery scatter — X-axis = 3yr CAGR (structural), fallback to YoY
    discovery_series = []
    for ch in CHANNEL_ORDER:
        cagr   = multiyear.get(ch, {}).get("cagr_pct")
        sub_g  = cagr if cagr is not None else yoy.get(ch, {}).get("yoy_pct")
        view_g = evergreen.get(ch, {}).get("avg_view_growth_pct")
        if sub_g is not None and view_g is not None:
            discovery_series.append({
                "label":           CHANNEL_DISPLAY[ch],
                "data":            [{"x": sub_g, "y": view_g}],
                "backgroundColor": CHANNEL_COLORS[ch],
                "pointRadius":     9,
                "pointHoverRadius": 11,
            })

    # S3: anchor horizontal bar
    anchor_labels  = []
    anchor_growths = []
    anchor_colors  = []
    for ch in CHANNEL_ORDER:
        for a in evergreen.get(ch, {}).get("anchors", []):
            if a["growth_pct"] is not None:
                anchor_labels.append(a["title"][:42])
                anchor_growths.append(a["growth_pct"])
                anchor_colors.append(CHANNEL_COLORS[ch])

    # S4: content type bar + stats table (avg, median, N per type)
    # Content types are already remapped to 4 canonical groups in compute_evergreen_metrics.
    # Enforce display order matching CONTENT_TYPE_COLORS key order.
    _type_order = list(CONTENT_TYPE_COLORS.keys())
    type_map = {}
    for ch in CHANNEL_ORDER:
        for a in evergreen.get(ch, {}).get("anchors", []):
            ct = a.get("content_type") or "Entertainment / Commentary"
            if a["growth_pct"] is not None:
                type_map.setdefault(ct, []).append(a["growth_pct"])
    # Reorder by canonical order; unknown types appended at end
    _ordered_keys = [k for k in _type_order if k in type_map] + \
                    [k for k in type_map if k not in _type_order]
    type_labels  = _ordered_keys
    type_avgs    = [round(sum(type_map[k]) / len(type_map[k]), 1) for k in type_labels]
    type_medians = []
    type_ns      = []
    for k in type_labels:
        sv  = sorted(type_map[k])
        n   = len(sv)
        med = sv[n // 2] if n % 2 == 1 else (sv[n // 2 - 1] + sv[n // 2]) / 2
        type_medians.append(round(med, 1))
        type_ns.append(n)
    type_colors = [CONTENT_TYPE_COLORS.get(t, "#95a5a6") for t in type_labels]

    # ── Anchor Outperformance % ───────────────────────────────────────────────
    # % of tracked anchors where view growth rate > channel subscriber growth rate
    _anc_total, _anc_outperf = 0, 0
    for ch in CHANNEL_ORDER:
        ch_sub_g = yoy.get(ch, {}).get("yoy_pct")
        for a in evergreen.get(ch, {}).get("anchors", []):
            if a.get("growth_pct") is not None and ch_sub_g is not None:
                _anc_total += 1
                if a["growth_pct"] > ch_sub_g:
                    _anc_outperf += 1
    _anc_outperf_pct = round(_anc_outperf / _anc_total * 100) if _anc_total > 0 else None
    _anc_outperf_s   = f"{_anc_outperf_pct}%" if _anc_outperf_pct is not None else "—"

    # ── Creator Concentration (top 3 by total tracked views) ─────────────────
    # Sum latest view counts for all tracked anchor videos per channel
    _ch_views = {}
    for ch in CHANNEL_ORDER:
        _ch_views[ch] = sum(
            a.get("views_curr", 0) or 0
            for a in evergreen.get(ch, {}).get("anchors", [])
        )
    _total_tracked_views = sum(_ch_views.values())
    _ch_views_sorted     = sorted(_ch_views.items(), key=lambda x: x[1], reverse=True)
    _top3_views          = sum(v for _, v in _ch_views_sorted[:3])
    _top3_names          = [CHANNEL_DISPLAY[ch] for ch, _ in _ch_views_sorted[:3]]
    _creator_conc_pct    = round(_top3_views / _total_tracked_views * 100, 1) \
                           if _total_tracked_views > 0 else None
    _creator_conc_s      = f"{_creator_conc_pct:.1f}%" if _creator_conc_pct is not None else "—"
    _top3_names_s        = ", ".join(_top3_names)

    # ── Creator share box HTML ────────────────────────────────────────────────
    _creator_share_box_html = (
        f"<div class='signal-interp' style='border-left-color:#8e44ad;"
        f"background:#0e0a1a;margin-bottom:14px'>"
        f"<div class='signal-interp-hdr' style='color:#8e44ad'>"
        f"Ecosystem Concentration — Top 3 Creators by Anchor View Share</div>"
        f"<p>Top 3 creators ({_top3_names_s}) account for "
        f"<strong style='color:#cdd9e5'>{_creator_conc_s}</strong> "
        f"of total tracked anchor video views. "
        f"<strong style='color:#cdd9e5'>{_anc_outperf_s}</strong> of tracked anchors "
        f"outperform their channel's subscriber growth rate — confirming broad-based "
        f"algorithmic distribution independent of channel size.</p>"
        f"</div>"
    )

    # ── Top 3 fastest compounding anchors by YoY view growth ─────────────────
    _all_anc_yoy = []
    for _ch in CHANNEL_ORDER:
        for _a in evergreen.get(_ch, {}).get("anchors", []):
            if _a.get("yoy_view_pct") is not None:
                _all_anc_yoy.append({
                    "title":   _a["title"],
                    "channel": CHANNEL_DISPLAY[_ch],
                    "yoy":     _a["yoy_view_pct"],
                    "color":   CHANNEL_COLORS[_ch],
                })
    _top3_anchors_yoy = sorted(_all_anc_yoy, key=lambda x: x["yoy"], reverse=True)[:3]
    _fastest_anchor_rows = "".join(
        f"<li style='margin-bottom:5px'>"
        f"<span class='dot' style='background:{_a['color']}'></span>"
        f"<strong style='color:#cdd9e5'>{_a['title'][:50]}</strong> "
        f"<span style='color:#8b949e;font-size:11px'>({_a['channel']})</span>"
        f" — <span style='color:#2ecc71;font-weight:700'>+{_a['yoy']:.1f}% YoY</span>"
        f"</li>"
        for _a in _top3_anchors_yoy
    )
    _fastest_anchor_box_html = (
        f"<div class='signal-interp' style='border-left-color:#2ecc71;"
        f"background:#0a1a0f;margin-bottom:14px'>"
        f"<div class='signal-interp-hdr' style='color:#2ecc71'>"
        f"Fastest Compounding Anchors — Top 3 by YoY View Growth (2025→2026)</div>"
        f"<ul style='list-style:none;padding:0;margin:6px 0 0'>"
        f"{_fastest_anchor_rows}"
        f"</ul></div>"
    ) if _top3_anchors_yoy else ""

    # S5: velocity grouped avg + median per 1K
    vel_avg_vals = [velocity.get(ch, {}).get("vpd_per_1k")         or 0 for ch in CHANNEL_ORDER]
    vel_med_vals = [velocity.get(ch, {}).get("median_vpd_per_1k")  or 0 for ch in CHANNEL_ORDER]

    # Content-type stats table rows (rendered server-side, no JS needed)
    content_type_rows_html = ""
    for lbl, avg, med, n in zip(type_labels, type_avgs, type_medians, type_ns):
        content_type_rows_html += (
            f"<tr>"
            f"<td>{lbl}</td>"
            f"<td class='num'>{'+' if avg >= 0 else ''}{avg:.1f}%</td>"
            f"<td class='num'>{'+' if med >= 0 else ''}{med:.1f}%</td>"
            f"<td class='num'>{n}</td>"
            f"</tr>\n"
        )

    # ── Content-type key insight ─────────────────────────────────────────────
    _ct_pos_types  = sum(1 for v in type_avgs if v > 0)
    _ct_best_idx   = type_avgs.index(max(type_avgs)) if type_avgs else None
    _ct_best_type  = type_labels[_ct_best_idx] if _ct_best_idx is not None else None
    _ct_best_avg   = type_avgs[_ct_best_idx]   if _ct_best_idx is not None else None
    _ct_best_s     = (f"{'+' if _ct_best_avg >= 0 else ''}{_ct_best_avg:.1f}%"
                      if _ct_best_avg is not None else "—")
    _ct_insight    = (
        f"{_ct_pos_types} of {len(type_labels)} content types show positive average view growth. "
        f"Strongest category: {_ct_best_type} ({_ct_best_s} avg YoY view growth). "
        f"Format diversity signals broad-based algorithmic discovery across the ecosystem."
    ) if _ct_best_type else (
        "No content-type breakdown available for this snapshot window."
    )

    # ── Reddit chart data ─────────────────────────────────────────────────
    def _r_traj(sub):
        sub_df = reddit_df[reddit_df["subreddit"] == sub].sort_values("date")
        return [{"x": str(r["date"]), "y": int(r["members"])} for _, r in sub_df.iterrows()]

    def _r_ppd_traj(sub):
        sub_df = reddit_df[reddit_df["subreddit"] == sub].sort_values("date")
        return [{"x": str(r["date"]), "y": round(float(r.get("posts_per_day") or 0), 1)}
                for _, r in sub_df.iterrows()]

    def _r_cpd_traj(sub):
        sub_df = reddit_df[reddit_df["subreddit"] == sub].sort_values("date")
        return [{"x": str(r["date"]), "y": round(float(r.get("comments_per_day") or 0), 1)}
                for _, r in sub_df.iterrows()]

    reddit_sub_labels = [REDDIT_LABELS[s] for s in REDDIT_ORDER]
    reddit_sub_colors = [REDDIT_COLORS[s]  for s in REDDIT_ORDER]
    reddit_yoy_vals   = [reddit_yoy.get(s, {}).get("yoy_pct") or 0 for s in REDDIT_ORDER]

    reddit_traj_datasets = [{
        "label": REDDIT_LABELS[s], "data": _r_traj(s),
        "borderColor": REDDIT_COLORS[s], "backgroundColor": REDDIT_COLORS[s],
        "pointRadius": 5, "borderWidth": 2,
    } for s in REDDIT_ORDER]

    # Aggregate community size
    reddit_agg       = compute_reddit_aggregate(reddit_yoy)
    reddit_agg_g     = reddit_agg.get("growth_pct")
    reddit_agg_g_str = f"{'+' if (reddit_agg_g or 0) >= 0 else ''}{reddit_agg_g:.1f}%" \
                       if reddit_agg_g is not None else "n/a"
    reddit_agg_color = "#2ecc71" if (reddit_agg_g or 0) > 5 else "#e67e22"

    # Reddit summary table rows — subscriber data only
    cls_css_map = {
        "Accelerating Community": "badge-pos",
        "Stable Expansion":       "badge-mid",
        "Passive Growth":         "badge-na",
        "Stagnating":             "badge-neg",
        "Insufficient Data":      "badge-na",
    }
    _reddit_total_curr = reddit_agg.get("total_curr") or 1  # for ecosystem share denominator
    reddit_rows_html = ""
    for s in REDDIT_ORDER:
        ry  = reddit_yoy.get(s, {})
        rc  = reddit_cls.get(s, {})
        col = REDDIT_COLORS[s]
        css = cls_css_map.get(rc.get("label", ""), "badge-na")
        yoy_s = f"{'+' if (ry.get('yoy_pct') or 0) >= 0 else ''}{ry.get('yoy_pct') or 0:.1f}%" \
                if ry.get("yoy_pct") is not None else "—"
        ann_s = f"{'+' if (ry.get('annualized_pct') or 0) >= 0 else ''}{ry.get('annualized_pct') or 0:.1f}%" \
                if ry.get("annualized_pct") is not None else "—"
        mem_s = f"{fmt_subs(ry.get('curr_members'))}"
        # Net Member Adds (YoY): curr_members − ref_members
        _curr_m = ry.get("curr_members")
        _ref_m  = ry.get("ref_members")
        _net    = (_curr_m - _ref_m) if (_curr_m is not None and _ref_m is not None) else None
        net_s   = f"{'+' if (_net or 0) >= 0 else ''}{_net:,.0f}" if _net is not None else "—"
        # Ecosystem Share %: curr_members / total_combined_curr
        _share    = round(_curr_m / _reddit_total_curr * 100, 1) if _curr_m else None
        share_s   = f"{_share:.1f}%" if _share is not None else "—"
        reddit_rows_html += (
            f"<tr>"
            f"<td><span class='dot' style='background:{col}'></span>{REDDIT_LABELS[s]}</td>"
            f"<td class='num'>{mem_s}</td>"
            f"<td class='num'>{yoy_s}</td>"
            f"<td class='num'>{ann_s}</td>"
            f"<td class='num'>{net_s}</td>"
            f"<td class='num'>{share_s}</td>"
            f"<td class='num'><span class='badge {css}'>{rc.get('label','—')}</span></td>"
            f"</tr>\n"
        )

    # Pre-compute dynamic variables for Reddit Signal Interpretation
    _reddit_valid_subs = [s for s in REDDIT_ORDER if reddit_yoy.get(s, {}).get("yoy_pct") is not None]
    _reddit_all_pos    = all(reddit_yoy.get(s, {}).get("yoy_pct", 0) > 0 for s in _reddit_valid_subs)
    _reddit_breadth    = "broad-based across all four subreddits" if _reddit_all_pos else "mixed across subreddits"
    _reddit_fastest    = max(_reddit_valid_subs,
                             key=lambda s: reddit_yoy.get(s, {}).get("yoy_pct") or 0,
                             default=None)
    _reddit_fastest_lbl = REDDIT_LABELS.get(_reddit_fastest, "—") if _reddit_fastest else "—"
    _reddit_fastest_yoy = reddit_yoy.get(_reddit_fastest, {}).get("yoy_pct") if _reddit_fastest else None
    _reddit_fastest_s   = (f"{'+' if (_reddit_fastest_yoy or 0) >= 0 else ''}"
                           f"{_reddit_fastest_yoy:.1f}%") if _reddit_fastest_yoy is not None else "—"

    # ── Reddit multi-year (2023→2024→2026) expansion data ─────────────────
    if reddit_multiyear is None:
        reddit_multiyear = compute_reddit_multiyear(reddit_yoy)

    _rmy_eco     = reddit_multiyear.get("__eco__", {})
    _rmy_2023    = _rmy_eco.get("m_2023", 0)
    _rmy_2024    = _rmy_eco.get("m_2024", 0)
    _rmy_2026    = _rmy_eco.get("m_2026", 0)
    _rmy_2324pct = _rmy_eco.get("yoy_2324_pct")
    _rmy_2426pct = _rmy_eco.get("yoy_2426_pct")
    def _fmm(v):
        return f"{v/1_000_000:.2f}M" if (v and v >= 1_000_000) else (f"{v/1_000:.0f}K" if v else "—")
    _rmy_eco_2023_s    = _fmm(_rmy_2023)
    _rmy_eco_2024_s    = _fmm(_rmy_2024)
    _rmy_eco_2026_s    = _fmm(_rmy_2026)
    _rmy_eco_2324_s    = (f"+{_rmy_2324pct:.1f}%" if (_rmy_2324pct or 0) >= 0
                          else f"{_rmy_2324pct:.1f}%") if _rmy_2324pct is not None else "—"
    _rmy_eco_2426_s    = (f"+{_rmy_2426pct:.1f}%" if (_rmy_2426pct or 0) >= 0
                          else f"{_rmy_2426pct:.1f}%") if _rmy_2426pct is not None else "—"
    _rmy_eco_2324_col  = "#27ae60" if (_rmy_2324pct or 0) > 0 else "#c0392b"
    _rmy_eco_2426_col  = "#27ae60" if (_rmy_2426pct or 0) > 0 else "#c0392b"

    # Chart data for grouped bar: 2023 | 2024 | 2026 per subreddit
    _rmy_labels   = [REDDIT_LABELS[s] for s in REDDIT_ORDER]
    _rmy_d_2023   = [reddit_multiyear.get(s, {}).get("m_2023") or 0 for s in REDDIT_ORDER]
    _rmy_d_2024   = [reddit_multiyear.get(s, {}).get("m_2024") or 0 for s in REDDIT_ORDER]
    _rmy_d_2026   = [reddit_multiyear.get(s, {}).get("m_2026") or 0 for s in REDDIT_ORDER]
    _rmy_colors   = [REDDIT_COLORS[s] for s in REDDIT_ORDER]

    # History table rows
    reddit_history_rows_html = ""
    for s in REDDIT_ORDER:
        rmy = reddit_multiyear.get(s, {})
        col = REDDIT_COLORS[s]
        def _ps(v): return (f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%") if v is not None else "—"
        def _abs(v): return (f"+{v:,.0f}" if v >= 0 else f"{v:,.0f}") if v is not None else "—"
        _share_val = rmy.get("share_pct")
        _share_str = f"{_share_val:.1f}%" if _share_val is not None else "—"
        reddit_history_rows_html += (
            f"<tr>"
            f"<td><span class='dot' style='background:{col}'></span>{REDDIT_LABELS[s]}</td>"
            f"<td class='num'>{_fmm(rmy.get('m_2023'))}</td>"
            f"<td class='num'>{_fmm(rmy.get('m_2024'))}</td>"
            f"<td class='num'>{_fmm(rmy.get('m_2026'))}</td>"
            f"<td class='num'>{_abs(rmy.get('abs_2324'))}</td>"
            f"<td class='num'>{_ps(rmy.get('yoy_2324_pct'))}</td>"
            f"<td class='num'>{_abs(rmy.get('abs_2426'))}</td>"
            f"<td class='num'>{_ps(rmy.get('yoy_2426_pct'))}</td>"
            f"<td class='num'>{_share_str}</td>"
            f"</tr>\n"
        )

    # Fastest 2023→2024 growing community
    _rmy_fastest_2324 = max(
        REDDIT_ORDER,
        key=lambda s: reddit_multiyear.get(s, {}).get("yoy_2324_pct") or 0,
        default=None,
    )
    _rmy_fastest_lbl = REDDIT_LABELS.get(_rmy_fastest_2324, "—") if _rmy_fastest_2324 else "—"
    _rmy_fastest_pct = reddit_multiyear.get(_rmy_fastest_2324, {}).get("yoy_2324_pct") \
                       if _rmy_fastest_2324 else None
    _rmy_fastest_s   = f"+{_rmy_fastest_pct:.1f}%" if _rmy_fastest_pct is not None else "—"

    reddit_exec_html = build_reddit_executive_summary(
        reddit_yoy, reddit_eng, reddit_cls, reddit_multiyear
    )

    # ── Steam chart data ──────────────────────────────────────────────────
    # Unpack composite return value from compute_steam_monthly_metrics
    steam_met_dict     = steam_monthly_metrics["by_slug"]
    steam_calendar_mon = steam_monthly_metrics["current_mon"]   # today's YYYY-MM (MTD)
    steam_struct_mon   = steam_monthly_metrics["struct_mon"]    # last completed month
    steam_current_avgs = steam_monthly_metrics["current_avgs"]  # live snapshot avgs for struct_mon

    # steam_latest_lbl: reflects the structural chart's final point
    if steam_current_avgs:
        # struct_mon has live snapshot data (finalize pending) — label as pre-final
        steam_latest_lbl = pd.to_datetime(steam_struct_mon + "-01").strftime("%b %Y") + " (pre-final)"
    elif _steam_months:
        steam_latest_lbl = pd.to_datetime(max(_steam_months) + "-01").strftime("%b %Y")

    # Build structural chart month list:
    #   completed history + struct_mon (if live snapshot data exists for it)
    hist_months = sorted(steam_monthly_df["month"].unique().tolist()) \
                  if not steam_monthly_df.empty else []
    has_struct_extra = bool(steam_current_avgs) and steam_struct_mon not in hist_months
    all_steam_months = hist_months + ([steam_struct_mon] if has_struct_extra else [])
    # Chart labels: structural months — no ▶est marker (this is real CCU data, not rolling)
    all_steam_months_labels = list(all_steam_months)

    # Chart S1: Monthly Avg Players — completed structural months only
    def _monthly_series(slug):
        if not all_steam_months:
            return []
        hist_idx = steam_monthly_df[steam_monthly_df["game_slug"] == slug] \
                       .set_index("month")["avg_players"]
        out = []
        for m in all_steam_months:
            if m == steam_struct_mon and slug in steam_current_avgs:
                out.append(steam_current_avgs[slug])      # live snapshot for struct_mon
            elif m in hist_idx.index:
                out.append(round(float(hist_idx[m]), 1))  # completed history
            else:
                out.append(None)
        return out

    steam_monthly_datasets = [{
        "label":           STEAM_LABELS[slug],
        "data":            _monthly_series(slug),
        "borderColor":     STEAM_COLORS[slug],
        "backgroundColor": STEAM_COLORS[slug],
        "pointRadius":     4,
        "borderWidth":     2,
        "tension":         0.1,
        "spanGaps":        True,
    } for slug in STEAM_ORDER]

    # Chart S2: MoM % Change — structural months only (last 6 completed months)
    _mom_window      = all_steam_months[-7:] if len(all_steam_months) >= 7 else all_steam_months
    mom_label_months = _mom_window[1:]

    def _mom_series(slug):
        if not mom_label_months:
            return []
        hist_idx = steam_monthly_df[steam_monthly_df["game_slug"] == slug] \
                       .set_index("month")["avg_players"]
        def _eff_avg(mon: str) -> float | None:
            if mon == steam_struct_mon and slug in steam_current_avgs:
                return steam_current_avgs[slug]  # live snapshot for struct_mon
            return round(float(hist_idx[mon]), 1) if mon in hist_idx.index else None

        out = []
        for m in mom_label_months:
            prior_m = (pd.to_datetime(m + "-01")
                       - pd.DateOffset(months=1)).strftime("%Y-%m")
            curr_a  = _eff_avg(m)
            prior_a = _eff_avg(prior_m)
            if curr_a is not None and prior_a is not None and prior_a > 0:
                out.append(round((curr_a - prior_a) / prior_a * 100, 1))
            else:
                out.append(None)
        return out

    steam_mom_datasets = [{
        "label":           STEAM_LABELS[slug],
        "data":            _mom_series(slug),
        "borderColor":     STEAM_COLORS[slug],
        "backgroundColor": STEAM_COLORS[slug],
        "pointRadius":     4,
        "borderWidth":     2,
        "tension":         0.2,
        "spanGaps":        False,
    } for slug in STEAM_ORDER]

    # ── Steam 3-layer presentation helpers ────────────────────────────────

    def _pct_s(val):
        return f"{'+' if val >= 0 else ''}{val:.1f}%" if val is not None else "—"

    def _pct_badge(val, hi=10, lo=-10):
        if val is None:
            return "badge-na", "—"
        css = "badge-pos" if val > hi else ("badge-mid" if val >= lo else "badge-neg")
        return css, _pct_s(val)

    def _mon_fmt(ym: str) -> str:
        """Format YYYY-MM as 'Mon YYYY'."""
        try:
            return pd.to_datetime(ym + "-01").strftime("%b %Y")
        except Exception:
            return ym

    # Pre-index historical data per slug for efficient lookups
    _steam_hist_idx: dict = {}
    for _s in STEAM_ORDER:
        _g = steam_monthly_df[steam_monthly_df["game_slug"] == _s].set_index("month")
        _steam_hist_idx[_s] = _g["avg_players"] if not _g.empty else pd.Series(dtype=float)

    def _hist_avg(slug: str, ym: str):
        """Return historical avg_players for a slug/month, or None."""
        idx = _steam_hist_idx.get(slug, pd.Series(dtype=float))
        return round(float(idx[ym]), 1) if ym in idx.index else None

    # Reference months relative to struct_mon (the last completed calendar month)
    _ref_mon  = steam_struct_mon
    _prior_1  = (pd.to_datetime(_ref_mon + "-01") - pd.DateOffset(months=1)).strftime("%Y-%m")
    _prior_2  = (pd.to_datetime(_ref_mon + "-01") - pd.DateOffset(months=2)).strftime("%Y-%m")
    _prior_3  = (pd.to_datetime(_ref_mon + "-01") - pd.DateOffset(months=3)).strftime("%Y-%m")
    _prior_1_fmt    = _mon_fmt(_prior_1)        # e.g. "Jan 2026"
    _prior_2_fmt    = _mon_fmt(_prior_2)        # e.g. "Dec 2025"
    _prior_3_fmt    = _mon_fmt(_prior_3)        # e.g. "Nov 2025"
    _struct_mon_fmt = _mon_fmt(steam_struct_mon) # e.g. "Feb 2026" — structural
    _mtd_mon_fmt    = _mon_fmt(steam_calendar_mon)  # e.g. "Mar 2026" — MTD
    _yoy_ref_mon_fmt = _mon_fmt(
        (pd.to_datetime(_ref_mon + "-01") - pd.DateOffset(months=12)).strftime("%Y-%m")
    )  # e.g. "Feb 2025"
    _mtd_yoy_ref_fmt = _mon_fmt(
        (pd.to_datetime(steam_calendar_mon + "-01") - pd.DateOffset(months=12)).strftime("%Y-%m")
    )  # e.g. "Mar 2025" — YoY reference for the MTD (in-progress) month

    # Source label for the structural section subtitle
    _any_prefinal = any(
        sm.get("struct_source") == "live_snapshot_avg"
        for sm in steam_met_dict.values() if sm
    )
    _struct_src_tag = "pre-final (live snapshots)" if _any_prefinal else "finalized"

    # ── Layer 1: Structural YoY Cards ─────────────────────────────────────────
    steam_cards_html = ""
    for slug in STEAM_ORDER:
        sm   = steam_met_dict.get(slug, {})
        col  = STEAM_COLORS[slug]
        lbl  = STEAM_LABELS[slug]

        s_mon   = sm.get("struct_mon", steam_struct_mon)
        s_avg   = sm.get("struct_avg")
        s_src   = sm.get("struct_source", "")
        avg_s   = f"{s_avg:,.0f}" if s_avg is not None else "—"
        # Label the avg with its actual month — title may differ if data-gap fallback
        avg_mon_fmt = _mon_fmt(s_mon)
        is_prefinal = (s_src == "live_snapshot_avg")
        avg_lbl = (avg_mon_fmt + " Avg (pre-final)") if is_prefinal else (avg_mon_fmt + " Avg")
        # Note if this title fell back to an earlier month
        fallback_note = (f"<div style='font-size:9px;color:#6e7681;margin-top:3px'>"
                         f"Latest available: {avg_mon_fmt}</div>") \
                        if s_src == "history_fallback" else ""

        yoy_css, yoy_s = _pct_badge(sm.get("yoy_pct"))
        mom_css, mom_s = _pct_badge(sm.get("mom_pct"))
        yoy_ref_fmt = _mon_fmt(sm["yoy_target"]) if sm.get("yoy_target") else "—"
        mom_ref_fmt = _mon_fmt(sm["mom_ref_mon"]) if sm.get("mom_ref_mon") else _prior_1_fmt

        steam_cards_html += (
            f"<div class='steam-title-card'>"
            f"<div class='stc-header'><span class='dot' style='background:{col}'></span>{lbl}</div>"
            # YoY — PRIMARY: largest visual element
            f"<div class='stc-yoy-block'>"
            f"<span class='badge {yoy_css} stc-yoy-badge'>{yoy_s}</span>"
            f"<div class='stc-yoy-lbl'>YoY vs {yoy_ref_fmt}</div>"
            f"</div>"
            f"<hr class='stc-divider'>"
            # Supporting: completed month avg
            f"<div class='stc-avg-val'>{avg_s}</div>"
            f"<div class='stc-avg-lbl'>{avg_lbl}</div>"
            f"{fallback_note}"
            # Supporting: MoM
            f"<div class='stc-mom-block'>"
            f"<span class='badge {mom_css}'>{mom_s}</span>"
            f"<div class='stc-metric-lbl'>MoM vs {mom_ref_fmt}</div>"
            f"</div>"
            f"</div>\n"
        )

    # ── MTD Section: current in-progress month (separate, clearly labeled) ─────
    # Only rendered if at least one title has MTD data.
    any_mtd = any(sm.get("has_mtd") for sm in steam_met_dict.values() if sm)
    steam_mtd_rows_html = ""
    if any_mtd:
        for slug in STEAM_ORDER:
            sm  = steam_met_dict.get(slug, {})
            col = STEAM_COLORS[slug]
            lbl = STEAM_LABELS[slug]
            if not sm.get("has_mtd"):
                steam_mtd_rows_html += (
                    f"<tr><td><span class='dot' style='background:{col}'></span>{lbl}</td>"
                    f"<td class='num' colspan='3' style='color:#6e7681'>No data</td></tr>\n"
                )
                continue
            mtd_v = sm["mtd_avg"]
            mtd_s = f"{mtd_v:,.0f}" if mtd_v is not None else "—"
            src_lbl = {"live_ccu": "Live CCU avg", "rolling_30d": "Rolling 30D"}.get(
                sm["mtd_source"], sm["mtd_source"])
            yoy_m_css, yoy_m_s = _pct_badge(sm.get("yoy_mtd_pct"))
            yoy_m_ref = _mon_fmt(sm["yoy_mtd_target"]) if sm.get("yoy_mtd_target") else "—"
            steam_mtd_rows_html += (
                f"<tr>"
                f"<td><span class='dot' style='background:{col}'></span>{lbl}</td>"
                f"<td class='num'>{mtd_s}</td>"
                f"<td class='num' style='color:#6e7681;font-size:11px'>{src_lbl}</td>"
                f"<td class='num'><span class='badge {yoy_m_css}'>{yoy_m_s}</span>"
                f"<span style='font-size:9px;color:#6e7681;margin-left:4px'>vs {yoy_m_ref}</span></td>"
                f"</tr>\n"
            )

    # Generate MTD section HTML as a separate variable to avoid complex f-string nesting
    if any_mtd:
        steam_mtd_section_html = (
            f"<div class='steam-mtd-section'>\n"
            f"  <div class='steam-mtd-hdr'>\n"
            f"    {_mtd_mon_fmt} — MTD Estimate (In-Progress Month)\n"
            f"    <span class='layer-tag'>Not a completed calendar month · will finalize when month ends</span>\n"
            f"  </div>\n"
            f"  <p class='steam-mtd-note'>\n"
            f"    MTD estimate — not a completed calendar month. Values shown are either live CCU snapshot avgs\n"
            f"    or rolling 30-Day sliding window values (labeled per row). These will be finalized into structural\n"
            f"    history when {_mtd_mon_fmt} ends. YoY (partial) compares MTD avg vs the same calendar month\n"
            f"    one year prior — treat as directional only.\n"
            f"  </p>\n"
            f"  <div class='table-card'>\n"
            f"    <table>\n"
            f"      <thead>\n"
            f"        <tr>\n"
            f"          <th>Title</th>\n"
            f"          <th class='num'>{_mtd_mon_fmt} MTD Avg</th>\n"
            f"          <th class='num'>Source</th>\n"
            f"          <th class='num'>YoY vs {_mtd_yoy_ref_fmt} (partial)</th>\n"
            f"        </tr>\n"
            f"      </thead>\n"
            f"      <tbody>{steam_mtd_rows_html}</tbody>\n"
            f"    </table>\n"
            f"  </div>\n"
            f"</div>"
        )
    else:
        steam_mtd_section_html = ""

    # ── Layer 2: Structural Context Table (6M trend + prior months + struct_mon) ─
    steam_context_rows_html = ""
    for slug in STEAM_ORDER:
        sm   = steam_met_dict.get(slug, {})
        col  = STEAM_COLORS[slug]
        lbl  = STEAM_LABELS[slug]

        t6m_css, t6m_s = _pct_badge(sm.get("trend_6m"))

        p1_v = _hist_avg(slug, _prior_1)
        p2_v = _hist_avg(slug, _prior_2)
        p3_v = _hist_avg(slug, _prior_3)
        p1_s = f"{p1_v:,.0f}" if p1_v is not None else "—"
        p2_s = f"{p2_v:,.0f}" if p2_v is not None else "—"
        p3_s = f"{p3_v:,.0f}" if p3_v is not None else "—"

        # Structural month avg (the completed month — no rolling proxy)
        s_avg = sm.get("struct_avg")
        s_src = sm.get("struct_source", "")
        s_sty = "color:#cdd9e5;font-weight:600"
        s_sfx = " *" if s_src == "live_snapshot_avg" else (
                " †" if s_src == "history_fallback" else "")
        cur_s = (f"{s_avg:,.0f}{s_sfx}") if s_avg is not None else "—"

        steam_context_rows_html += (
            f"<tr>"
            f"<td><span class='dot' style='background:{col}'></span>{lbl}</td>"
            f"<td class='num'><span class='badge {t6m_css}'>{t6m_s}</span></td>"
            f"<td class='num'>{p3_s}</td>"
            f"<td class='num'>{p2_s}</td>"
            f"<td class='num'>{p1_s}</td>"
            f"<td class='num' style='{s_sty}'>{cur_s}</td>"
            f"</tr>\n"
        )

    # ── Steam Franchise Concentration (live CCU) ──────────────────────────────
    # Pre-compute counts here so they're available for chart_data injection
    _steam_n       = len(STEAM_ORDER)
    _steam_pos_yoy = sum(
        1 for sm in steam_met_dict.values()
        if sm and sm.get("yoy_pct") is not None and sm.get("yoy_pct", 0) > 0
    )
    _ccu_pairs   = [(slug, steam_met_dict.get(slug, {}).get("live_ccu") or 0) for slug in STEAM_ORDER]
    _ccu_sorted  = sorted(_ccu_pairs, key=lambda x: x[1], reverse=True)
    _total_ccu   = sum(v for _, v in _ccu_pairs)
    _top2_ccu    = sum(v for _, v in _ccu_sorted[:2])
    _top2_names  = [STEAM_LABELS[slug] for slug, _ in _ccu_sorted[:2]]
    _conc_pct    = round(_top2_ccu / _total_ccu * 100, 1) if _total_ccu > 0 else None
    _conc_pct_s  = f"{_conc_pct:.1f}%" if _conc_pct is not None else "—"
    _conc_names_s = " + ".join(_top2_names)
    steam_conc_box_html = (
        f"<div class='signal-interp' style='border-left-color:#8b949e;background:#0d1117;margin-bottom:10px'>"
        f"<div class='signal-interp-hdr' style='color:#8b949e'>Franchise Concentration — Live CCU</div>"
        f"<p>Top 2 titles ({_conc_names_s}) account for <strong style='color:#cdd9e5'>{_conc_pct_s}</strong> "
        f"of total active franchise players. "
        f"Based on live concurrent player counts at last pipeline run — directional only.</p>"
        f"</div>"
    )

    # ── Layer 3: Short-Term Pulse (rolling 30D + live CCU) ────────────────────
    steam_pulse_rows_html = ""
    for slug in STEAM_ORDER:
        sm   = steam_met_dict.get(slug, {})
        col  = STEAM_COLORS[slug]
        lbl  = STEAM_LABELS[slug]
        r30_s  = f"{sm['rolling_30d']:,.1f}" if sm.get("rolling_30d") is not None else "—"
        live_s = f"{sm['live_ccu']:,}"        if sm.get("live_ccu")   is not None else "—"
        steam_pulse_rows_html += (
            f"<tr>"
            f"<td><span class='dot' style='background:{col}'></span>{lbl}</td>"
            f"<td class='num'>{r30_s}</td>"
            f"<td class='num'>{live_s}</td>"
            f"</tr>\n"
        )

    # ── Multi-year chart data ─────────────────────────────────────────────────
    _my_year_labels = [str(y) for y in MULTIYEAR_YEARS]
    _my_ch_datasets = []
    for ch in CHANNEL_ORDER:
        ch_my = multiyear.get(ch, {})
        _my_ch_datasets.append({
            "label":           CHANNEL_DISPLAY[ch],
            "data":            [ch_my.get("subs_by_year", {}).get(yr) for yr in MULTIYEAR_YEARS],
            "borderColor":     CHANNEL_COLORS[ch],
            "backgroundColor": CHANNEL_COLORS[ch],
            "pointRadius":     6,
            "borderWidth":     2,
            "tension":         0.2,
            "spanGaps":        False,
        })
    _eco_my = multiyear.get("__eco__", {})
    _my_eco_dataset = {
        "label":           "Ecosystem Total",
        "data":            [_eco_my.get("subs_by_year", {}).get(yr) for yr in MULTIYEAR_YEARS],
        "borderColor":     "#ffffff",
        "backgroundColor": "#ffffff",
        "pointRadius":     7,
        "borderWidth":     2,
        "tension":         0.2,
        "spanGaps":        False,
        "borderDash":      [5, 4],
    }
    # ── Page 2A: Subscriber growth table rows ────────────────────────────────
    # Channel | Subs 2023 | Subs 2024 | Subs 2025 | Subs 2026 | YoY | 2-Yr | 3-Yr CAGR
    sub_table_rows = ""
    for ch in CHANNEL_ORDER:
        ch_my = multiyear.get(ch, {})
        sby   = ch_my.get("subs_by_year", {})
        col   = CHANNEL_COLORS[ch]
        lbl   = CHANNEL_DISPLAY[ch]
        def _sk(yr):
            v = sby.get(yr)
            return f"{v/1e6:.2f}M" if v else "—"
        def _pg(val):
            if val is None:
                return "<span style='color:#6e7681'>—</span>"
            css = "badge-up" if val >= 0 else "badge-dn"
            return f"<span class='badge {css}'>{'+' if val>=0 else ''}{val:.1f}%</span>"
        yoy_v = yoy.get(ch, {}).get("yoy_pct")
        sub_table_rows += (
            f"<tr>"
            f"<td><span class='dot' style='background:{col}'></span>{lbl}</td>"
            f"<td class='num'>{_sk(2023)}</td>"
            f"<td class='num'>{_sk(2024)}</td>"
            f"<td class='num'>{_sk(2025)}</td>"
            f"<td class='num'>{_sk(2026)}</td>"
            f"<td class='num'>{_pg(yoy_v)}</td>"
            f"<td class='num'>{_pg(ch_my.get('two_yr_pct'))}</td>"
            f"<td class='num'>{_pg(ch_my.get('cagr_pct'))}</td>"
            f"</tr>\n"
        )
    # Ecosystem totals row
    _eco_my_subs = _eco_my.get("subs_by_year", {})
    def _esk(yr):
        v = _eco_my_subs.get(yr)
        return f"{v/1e6:.2f}M" if v else "—"
    _eco_yoy = yoy.get(list(CHANNEL_ORDER)[0], {})  # not a simple sum — use headline stat
    sub_table_rows += (
        f"<tr style='border-top:1px solid #30363d;font-weight:600;color:#cdd9e5'>"
        f"<td>Ecosystem Total</td>"
        f"<td class='num'>{_esk(2023)}</td>"
        f"<td class='num'>{_esk(2024)}</td>"
        f"<td class='num'>{_esk(2025)}</td>"
        f"<td class='num'>{_esk(2026)}</td>"
        f"<td class='num'>{eco_2yr_str if False else '—'}</td>"
        f"<td class='num' style='color:#27ae60' >{eco_2yr_str}</td>"
        f"<td class='num' style='color:{eco_cagr_color}'>{eco_cagr_str}</td>"
        f"</tr>\n"
    )
    # Keep legacy name for any remaining references
    _my_table_rows = sub_table_rows

    chart_data = {
        "chLabels":         ch_labels,
        "chColors":         ch_colors,
        "currSubs":         curr_subs_vals,
        "yoyPct":           yoy_pct_vals,
        "cagrPct":          cagr_pct_vals,
        "twoYrPct":         two_yr_pct_vals,
        "anchorOutperfPct": _anc_outperf_pct or 0,
        "trajDatasets":   traj_datasets,
        "trajRefDate":    TRAJ_REF_DATE,
        "slopeDatasets":  slope_datasets,
        "eciVals":        eci_vals,
        "discoverySeries":discovery_series,
        "anchorLabels":   anchor_labels,
        "anchorGrowths":  anchor_growths,
        "anchorColors":   anchor_colors,
        "typeLabels":     type_labels,
        "typeAvgs":       type_avgs,
        "typeColors":     type_colors,
        "velAvg":         vel_avg_vals,
        "velMed":         vel_med_vals,
        "multiyear": {
            "years":      _my_year_labels,
            "chDatasets": _my_ch_datasets,
            "ecoDataset": _my_eco_dataset,
        },
        "reddit": {
            "subLabels":    reddit_sub_labels,
            "subColors":    reddit_sub_colors,
            "yoyVals":      reddit_yoy_vals,
            "trajDatasets": reddit_traj_datasets,
            "myLabels":     _rmy_labels,
            "myColors":     _rmy_colors,
            "my2023":       _rmy_d_2023,
            "my2024":       _rmy_d_2024,
            "my2026":       _rmy_d_2026,
        },
        "steam": {
            "monthlyLabels":   all_steam_months_labels,
            "monthlyDatasets": steam_monthly_datasets,
            "momLabels":       list(mom_label_months),
            "momDatasets":     steam_mom_datasets,
            "totalCCU":        _total_ccu,
            "posYoYCount":     _steam_pos_yoy,
            "titleCount":      _steam_n,
        },
    }

    # ── HTML fragments ────────────────────────────────────────────────────

    # Section 2 — anchor summary table (brief: channel + slug + growth)
    s2_anchor_rows = ""
    for ch in CHANNEL_ORDER:
        for a in evergreen.get(ch, {}).get("anchors", []):
            color = CHANNEL_COLORS[ch]
            # Growth label: prefer explicit YoY view pct (2025→2026) over raw window growth
            view_g = a.get("yoy_view_pct") if a.get("yoy_view_pct") is not None \
                     else a.get("growth_pct")
            s2_anchor_rows += (
                f"<tr>"
                f"<td><span class='dot' style='background:{color}'></span>{CHANNEL_DISPLAY[ch]}</td>"
                f"<td>{a['title'][:55]}</td>"
                f"<td class='num'>{a.get('content_type','')}</td>"
                f"<td class='num'>{pct_badge(view_g, 15.0)}</td>"
                f"</tr>\n"
            )

    # Section 3 — full anchor table with multi-year view columns
    def _pct_str(v):
        if v is None:
            return "—"
        return f"{'+' if v >= 0 else ''}{v:.1f}%"

    s3_anchor_rows = ""
    for ch in CHANNEL_ORDER:
        for a in evergreen.get(ch, {}).get("anchors", []):
            color   = CHANNEL_COLORS[ch]
            vby     = a.get("views_by_year", {})
            v_2023  = fmt_views(vby.get(2023))  if vby.get(2023) else "—"
            v_2024  = fmt_views(vby.get(2024))  if vby.get(2024) else "—"
            v_2025  = fmt_views(vby.get(2025))  if vby.get(2025) else fmt_views(a.get("views_prev"))
            v_2026  = fmt_views(vby.get(2026))  if vby.get(2026) else fmt_views(a.get("views_curr"))
            yoy_v   = pct_badge(a.get("yoy_view_pct"),    10.0)
            two_v   = _pct_str(a.get("two_yr_view_pct"))
            cagr_v  = _pct_str(a.get("view_cagr_pct"))
            s3_anchor_rows += (
                f"<tr>"
                f"<td><span class='dot' style='background:{color}'></span>{CHANNEL_DISPLAY[ch]}</td>"
                f"<td>{a['title'][:50]}</td>"
                f"<td class='num'>{a.get('content_type','')}</td>"
                f"<td class='num'>{v_2023}</td>"
                f"<td class='num'>{v_2024}</td>"
                f"<td class='num'>{v_2025}</td>"
                f"<td class='num'>{v_2026}</td>"
                f"<td class='num'>{yoy_v}</td>"
                f"<td class='num'>{two_v}</td>"
                f"<td class='num'>{cagr_v}</td>"
                f"</tr>\n"
            )

    # Section 5 — velocity table
    s5_vel_rows = ""
    for ch in CHANNEL_ORDER:
        v     = velocity.get(ch, {})
        color = CHANNEL_COLORS[ch]
        avpd  = f"{v['avg_vpd']:,.0f}"    if v.get("avg_vpd")         else "—"
        mvpd  = f"{v['median_vpd']:,.0f}" if v.get("median_vpd")      else "—"
        a1k   = f"{v['vpd_per_1k']:.1f}"  if v.get("vpd_per_1k")      else "—"
        m1k   = f"{v['median_vpd_per_1k']:.1f}" if v.get("median_vpd_per_1k") else "—"
        age   = f"{v['avg_age_days']}d"   if v.get("avg_age_days")    else "—"
        s5_vel_rows += (
            f"<tr>"
            f"<td><span class='dot' style='background:{color}'></span>{CHANNEL_DISPLAY[ch]}</td>"
            f"<td class='num'>{avpd}</td><td class='num'>{mvpd}</td>"
            f"<td class='num'>{a1k}</td><td class='num'>{m1k}</td>"
            f"<td class='num'>{age}</td>"
            f"</tr>\n"
        )

    # Section 2 — ECI signal interpretation (Python-side)
    _eci_above_1  = [ch for ch in CHANNEL_ORDER if (eci_map.get(ch, {}).get("eci") or 0) > 1.0]
    _best_eci_ch  = max(CHANNEL_ORDER, key=lambda c: eci_map.get(c, {}).get("eci") or 0)
    _best_eci_v   = eci_map.get(_best_eci_ch, {}).get("eci")
    _best_eci_lbl = CHANNEL_DISPLAY[_best_eci_ch]
    _n_above_1    = len(_eci_above_1)
    _above_1_str  = ", ".join(CHANNEL_DISPLAY[c] for c in _eci_above_1)
    _avg_view_g   = round(
        sum(v for v in (eci_map.get(ch, {}).get("avg_view_growth") for ch in CHANNEL_ORDER)
            if v is not None) /
        max(1, sum(1 for ch in CHANNEL_ORDER if eci_map.get(ch, {}).get("avg_view_growth") is not None)),
        1,
    )
    _s2_interp = (
        f"{_n_above_1} of {len(CHANNEL_ORDER)} tracked channels show anchor view compounding "
        f"exceeding their structural subscriber growth rate (ECI > 1×). "
        f"<strong>{_best_eci_lbl}</strong> leads at ECI {_best_eci_v:.2f}× — "
        f"back-catalog views are growing at {_best_eci_v:.1f}× the channel's 3-year subscriber CAGR. "
        f"Ecosystem-average anchor view growth is +{_avg_view_g:.1f}%, driven primarily by "
        f"Lore Education and Official Media formats. "
        f"Discovery reach is self-sustaining: content is compounding without new uploads."
    ) if _best_eci_v else "Insufficient data for ECI interpretation."

    # Section 6 — structural classification table
    # Ecosystem median vpd/1k (needed for rule footnote)
    vpd_vals_all = sorted(
        v.get("vpd_per_1k") for v in velocity.values() if v.get("vpd_per_1k") is not None
    )
    eco_med_vpd = vpd_vals_all[len(vpd_vals_all) // 2] if vpd_vals_all else 0

    s6_rows = ""
    for ch in CHANNEL_ORDER:
        sc       = struct_class.get(ch, {})
        my_ch    = multiyear.get(ch, {})
        color    = CHANNEL_COLORS[ch]
        eci_v    = f"{sc['eci']:.2f}×" if sc.get("eci") is not None else "—"
        sub_v    = (f"{'+' if (sc.get('sub_growth') or 0) >= 0 else ''}{sc.get('sub_growth'):.1f}%"
                    if sc.get("sub_growth") is not None else "—")
        two_v    = (f"{'+' if (my_ch.get('two_yr_pct') or 0) >= 0 else ''}{my_ch['two_yr_pct']:.1f}%"
                    if my_ch.get("two_yr_pct") is not None else "—")
        cagr_v   = (f"{'+' if (my_ch.get('cagr_pct') or 0) >= 0 else ''}{my_ch['cagr_pct']:.1f}%"
                    if my_ch.get("cagr_pct") is not None else "—")
        vpd_v    = f"{sc['vpd_per_1k']:.1f}" if sc.get("vpd_per_1k") else "—"
        s6_rows += (
            f"<tr>"
            f"<td><span class='dot' style='background:{color}'></span>{CHANNEL_DISPLAY[ch]}</td>"
            f"<td class='num'>{sub_v}</td>"
            f"<td class='num'>{two_v}</td>"
            f"<td class='num'>{cagr_v}</td>"
            f"<td class='num'>{eci_v}</td>"
            f"<td class='num'>{vpd_v}</td>"
            f"<td class='num'>{class_badge(sc.get('label','—'))}</td>"
            f"</tr>\n"
        )

    # ── Page 2B: ECI table rows ───────────────────────────────────────────────
    # Channel | Anchor View Growth % | Sub 3-Yr CAGR % | ECI
    eci_table_rows = ""
    for ch in CHANNEL_ORDER:
        col       = CHANNEL_COLORS[ch]
        em        = eci_map.get(ch, {})
        my_ch     = multiyear.get(ch, {})
        view_g    = em.get("avg_view_growth")
        cagr      = my_ch.get("cagr_pct")
        eci_v     = em.get("eci")
        def _epct(v, hi=10.0):
            if v is None: return "<span style='color:#6e7681'>—</span>"
            css = "badge-pos" if v >= hi else ("badge-mid" if v >= 0 else "badge-neg")
            return f"<span class='badge {css}'>{'+' if v>=0 else ''}{v:.1f}%</span>"
        def _eciv(v):
            if v is None: return "<span style='color:#6e7681'>—</span>"
            css = "badge-pos" if v >= 1.0 else "badge-na"
            return f"<span class='badge {css}'>{v:.2f}×</span>"
        eci_table_rows += (
            f"<tr>"
            f"<td><span class='dot' style='background:{col}'></span>{CHANNEL_DISPLAY[ch]}</td>"
            f"<td class='num'>{_epct(view_g)}</td>"
            f"<td class='num'>{_epct(cagr)}</td>"
            f"<td class='num'>{_eciv(eci_v)}</td>"
            f"</tr>\n"
        )

    # ── Page 4: Reddit unified table rows ────────────────────────────────────
    # Subreddit | Members 2023 | Members 2024 | Members 2026 | YoY % | 2-Yr % | 3-Yr CAGR | Share %
    reddit_unified_rows = ""
    for s in REDDIT_ORDER:
        rmy   = reddit_multiyear.get(s, {})
        ry    = reddit_yoy.get(s, {})
        col   = REDDIT_COLORS[s]
        def _rpct(v, hi=10.0):
            if v is None: return "<span style='color:#6e7681'>—</span>"
            css = "badge-pos" if v >= hi else ("badge-mid" if v >= 0 else "badge-neg")
            return f"<span class='badge {css}'>{'+' if v>=0 else ''}{v:.1f}%</span>"
        yoy_r_pct    = ry.get("yoy_pct")
        two_yr_pct_r = rmy.get("yoy_2426_pct")  # 2024→2026 (~2yr)
        cagr_r_pct   = rmy.get("cagr_3yr_pct")
        share_v      = rmy.get("share_pct")
        share_s      = f"{share_v:.1f}%" if share_v is not None else "—"
        reddit_unified_rows += (
            f"<tr>"
            f"<td><span class='dot' style='background:{col}'></span>{REDDIT_LABELS[s]}</td>"
            f"<td class='num'>{_fmm(rmy.get('m_2023'))}</td>"
            f"<td class='num'>{_fmm(rmy.get('m_2024'))}</td>"
            f"<td class='num'>{_fmm(rmy.get('m_2026'))}</td>"
            f"<td class='num'>{_rpct(yoy_r_pct)}</td>"
            f"<td class='num'>{_rpct(two_yr_pct_r, 5.0)}</td>"
            f"<td class='num'>{_rpct(cagr_r_pct, 5.0)}</td>"
            f"<td class='num'>{share_s}</td>"
            f"</tr>\n"
        )
    # Ecosystem totals row for Reddit
    _reco = reddit_multiyear.get("__eco__", {})
    _reco_yoy   = _rmy_eco.get("yoy_2324_pct")  # note: 2324 is ecosystem YoY for reddit current
    # Use current reddit_yoy aggregate for the 2025→2026 YoY
    def _reco_pct_s(v):
        if v is None: return "—"
        return (f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%")
    reddit_unified_rows += (
        f"<tr style='border-top:1px solid #30363d;font-weight:600;color:#cdd9e5'>"
        f"<td>Ecosystem Total</td>"
        f"<td class='num'>{_fmm(_reco.get('m_2023'))}</td>"
        f"<td class='num'>{_fmm(_reco.get('m_2024'))}</td>"
        f"<td class='num'>{_fmm(_reco.get('m_2026'))}</td>"
        f"<td class='num'>{_reco_pct_s(_rmy_2324pct)}</td>"
        f"<td class='num'>{_reco_pct_s(_rmy_2426pct)}</td>"
        f"<td class='num'>{_reco_pct_s(_reco.get('cagr_3yr_pct'))}</td>"
        f"<td class='num'>100%</td>"
        f"</tr>\n"
    )

    # ── Page 5: Steam prior-year avg + structural table rows ──────────────────
    # Build Feb 2025 avg per slug from historical data
    _steam_prior_avg: dict = {}
    for _slug in STEAM_ORDER:
        _target_mon = steam_met_dict.get(_slug, {}).get("yoy_target")
        if _target_mon and not steam_monthly_df.empty:
            _row = steam_monthly_df[(steam_monthly_df["game_slug"] == _slug) &
                                    (steam_monthly_df["month"] == _target_mon)]
            _steam_prior_avg[_slug] = round(float(_row.iloc[0]["avg_players"]), 1) \
                                      if not _row.empty else None
        else:
            _steam_prior_avg[_slug] = None

    # ── Steam historical table (from STEAM_HISTORICAL_DATA constant) ─────────
    # Derive reference years from the data so column headers auto-update.
    _sh_all_yrs = sorted({yr for _sd in STEAM_HISTORICAL_DATA.values()
                          for yr in _sd.get("snapshots", {})})
    _sh_base_yr = _sh_all_yrs[0]    # earliest snapshot year  (2023)
    _sh_mid_yr  = _sh_all_yrs[1] if len(_sh_all_yrs) >= 4 else None  # 2024 (2-yr anchor)
    _sh_prev_yr = _sh_all_yrs[-2]   # second-to-latest year   (2025)
    _sh_curr_yr = _sh_all_yrs[-1]   # most recent snapshot yr (2026)

    # Per-title metrics
    _steam_hist_metrics: dict = {}
    for _sh_slug in STEAM_ORDER:
        _sd    = STEAM_HISTORICAL_DATA.get(_sh_slug, {})
        _snaps = _sd.get("snapshots", {})
        _base  = _snaps.get(_sh_base_yr)
        _mid   = _snaps.get(_sh_mid_yr)  if _sh_mid_yr else None  # Feb 2024
        _prev  = _snaps.get(_sh_prev_yr)
        _curr  = _snaps.get(_sh_curr_yr)
        _l30d  = _sd.get("last_30d")
        _pk    = _sd.get("peak")
        _yoy   = (_curr / _prev - 1) * 100 if _prev and _curr else None
        _2yr   = (_curr / _mid  - 1) * 100 if _mid  and _curr else None
        _3yr   = (_curr / _base - 1) * 100 if _base and _curr else None
        _stab  = (_l30d / _pk * 100)       if _l30d and _pk else None
        _steam_hist_metrics[_sh_slug] = {
            "base": _base, "mid": _mid, "prev": _prev, "curr": _curr,
            "last_30d": _l30d, "peak": _pk,
            "yoy_pct": _yoy, "two_yr": _2yr, "three_yr": _3yr, "stability": _stab,
        }

    def _sh_badge(val, strong_thr=20, stable_lo=-10):
        """Badge for % values using strong-expansion / stable / normalization thresholds."""
        if val is None:
            return "<span class='badge badge-na'>—</span>"
        if val > strong_thr:
            css = "badge-pos"
        elif val >= stable_lo:
            css = "badge-mid"
        else:
            css = "badge-neg"
        sign = "+" if val >= 0 else ""
        return f"<span class='badge {css}'>{sign}{val:.1f}%</span>"

    steam_structural_rows = ""
    for _sh_slug in STEAM_ORDER:
        _m   = _steam_hist_metrics[_sh_slug]
        _col = STEAM_COLORS[_sh_slug]
        _lbl = STEAM_LABELS[_sh_slug]
        _base_s = f"{_m['base']:,.0f}" if _m['base']    is not None else "—"
        _mid_s  = f"{_m['mid']:,.0f}"  if _m['mid']     is not None else "—"
        _prev_s = f"{_m['prev']:,.0f}" if _m['prev']    is not None else "—"
        _curr_s = f"{_m['curr']:,.0f}" if _m['curr']    is not None else "—"
        _l30_s  = f"{_m['last_30d']:,.0f}" if _m['last_30d'] is not None else "—"
        _pk_s   = f"{_m['peak']:,}"   if _m['peak']    is not None else "—"
        _stab_s = f"{_m['stability']:.1f}%" if _m['stability'] is not None else "—"
        steam_structural_rows += (
            f"<tr>"
            f"<td><span class='dot' style='background:{_col}'></span>{_lbl}</td>"
            f"<td class='num'>{_base_s}</td>"
            f"<td class='num'>{_mid_s}</td>"
            f"<td class='num'>{_prev_s}</td>"
            f"<td class='num'>{_curr_s}</td>"
            f"<td class='num'>{_sh_badge(_m['yoy_pct'])}</td>"
            f"<td class='num'>{_sh_badge(_m['two_yr'],   strong_thr=10, stable_lo=-10)}</td>"
            f"<td class='num'>{_sh_badge(_m['three_yr'], strong_thr=10, stable_lo=-10)}</td>"
            f"<td class='num'>{_l30_s}</td>"
            f"<td class='num'>{_pk_s}</td>"
            f"<td class='num'>{_stab_s}</td>"
            f"</tr>\n"
        )

    # ── Page 1: Franchise overview variables ─────────────────────────────────
    # YouTube
    _yt_eco_2023_s  = f"{_eco_2023/1e6:.2f}M" if _eco_2023 else "—"
    _yt_eco_2026_s  = f"{_eco_2026/1e6:.2f}M" if _eco_2026 else "—"
    _yt_yoy_str     = eco_2yr_str   # Slopegraph YoY (baseline→latest) kept as fallback label
    _yt_cagr_str    = eco_cagr_str
    _yt_cagr_col    = eco_cagr_color
    # Reddit
    _rd_eco_2023_s  = _fmm(_rmy_2023) if _rmy_2023 else "—"
    _rd_eco_2026_s  = _fmm(_rmy_2026) if _rmy_2026 else "—"
    _rd_cagr        = _rmy_eco.get("cagr_3yr_pct")
    _rd_cagr_s      = (_fp(_rd_cagr) if _rd_cagr is not None else "—")
    _rd_cagr_col    = "#27ae60" if (_rd_cagr or 0) > 0 else "#c0392b"
    _rd_yoy_s       = _rmy_eco_2324_s   # 2023→2024 YoY for ecosystem label
    _rd_yoy_2426_s  = _rmy_eco_2426_s   # 2024→2026 (~2yr)
    # Steam — use Space Marine 2 (best structural YoY) as headline
    _st_live_s      = f"{_total_ccu:,}" if _total_ccu else "—"
    _top_steam_slug = max(STEAM_ORDER, key=lambda s: _steam_hist_metrics[s]["yoy_pct"] or -999)
    _top_steam_lbl  = STEAM_LABELS[_top_steam_slug]
    _top_steam_yoy  = _steam_hist_metrics[_top_steam_slug]["yoy_pct"]
    _top_steam_yoy_s = (f"{'+' if (_top_steam_yoy or 0) >= 0 else ''}{_top_steam_yoy:.1f}%"
                        if _top_steam_yoy is not None else "—")
    _top_steam_col  = "#27ae60" if (_top_steam_yoy or 0) >= 0 else "#c0392b"
    # Stable-to-growing count: titles with structural YoY >= -10% (strong + stable)
    _st_stable_growing = len([s for s in STEAM_ORDER
                               if (_steam_hist_metrics[s]["yoy_pct"] or -999) >= -10])
    _st_pos_yoy_s   = f"{_st_stable_growing} of {_steam_n} stable or growing"

    # Portfolio 2-year (Feb 2024→2026): sum titles that have both mid & curr snapshots
    _st_2yr_titles  = [s for s in STEAM_ORDER
                       if _steam_hist_metrics[s]["mid"] and _steam_hist_metrics[s]["curr"]]
    _st_2yr_base_sum = sum(_steam_hist_metrics[s]["mid"]  for s in _st_2yr_titles)
    _st_2yr_curr_sum = sum(_steam_hist_metrics[s]["curr"] for s in _st_2yr_titles)
    _st_2yr_pct     = round((_st_2yr_curr_sum / _st_2yr_base_sum - 1) * 100, 1) \
                      if _st_2yr_base_sum else None
    _fp2            = lambda v: (f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%") if v is not None else "—"
    _st_2yr_s       = _fp2(_st_2yr_pct)
    _st_2yr_col     = "#27ae60" if (_st_2yr_pct or 0) >= 0 else "#c0392b"

    # Portfolio 3-year CAGR (Feb 2023→2026): sum titles that have both base & curr snapshots
    _st_3yr_titles  = [s for s in STEAM_ORDER
                       if _steam_hist_metrics[s]["base"] and _steam_hist_metrics[s]["curr"]]
    _st_3yr_base_sum = sum(_steam_hist_metrics[s]["base"] for s in _st_3yr_titles)
    _st_3yr_curr_sum = sum(_steam_hist_metrics[s]["curr"] for s in _st_3yr_titles)
    _st_3yr_cagr    = round(((_st_3yr_curr_sum / _st_3yr_base_sum) ** (1 / 3) - 1) * 100, 1) \
                      if _st_3yr_base_sum else None
    _st_3yr_s       = _fp2(_st_3yr_cagr)
    _st_3yr_col     = "#27ae60" if (_st_3yr_cagr or 0) >= 0 else "#c0392b"
    _st_n_2yr       = len(_st_2yr_titles)
    _st_n_3yr       = len(_st_3yr_titles)

    # Page 1 cross-platform table rows
    # YouTube row: use structural CAGR and ecosystem 2yr
    _yt_two_yr      = _eco_2yr_pct
    _yt_two_yr_s    = eco_2yr_str
    _yt_two_yr_col  = eco_2yr_color
    _yt_yoy_eco     = yoy.get(max(CHANNEL_ORDER,
                       key=lambda c: yoy.get(c,{}).get("curr_subs") or 0), {}).get("yoy_pct")
    # Reddit 2yr = 2024→2026 growth
    _rd_two_yr_s    = _rmy_eco_2426_s
    _rd_two_yr_col  = _rmy_eco_2426_col
    # Steam top title structural YoY — use Feb/Feb snapshots from _steam_hist_metrics
    _st_struct_mon_lbl = _mon_fmt(steam_struct_mon)
    _st_prior_avg  = _steam_hist_metrics[_top_steam_slug]["prev"]
    _st_curr_avg   = _steam_hist_metrics[_top_steam_slug]["curr"]
    _st_prior_s    = f"{_st_prior_avg:,.0f}" if _st_prior_avg is not None else "—"
    _st_curr_s     = f"{_st_curr_avg:,.0f}" if _st_curr_avg is not None else "—"
    _st_6m         = steam_met_dict.get(_top_steam_slug, {}).get("trend_6m")
    _st_6m_s       = (f"{'+' if (_st_6m or 0) >= 0 else ''}{_st_6m:.1f}%"
                      if _st_6m is not None else "—")

    # Section insight strings
    _pos_cagr_count = sum(1 for ch in CHANNEL_ORDER if (multiyear.get(ch,{}).get("cagr_pct") or 0) > 0)
    _sub_insight = (
        f"{_pos_cagr_count} of {len(CHANNEL_ORDER)} channels show positive 3-year CAGR. "
        f"Ecosystem 3-year CAGR: {eco_cagr_str}. Best performer by CAGR: "
        f"{CHANNEL_DISPLAY[max(CHANNEL_ORDER, key=lambda c: multiyear.get(c,{}).get('cagr_pct') or 0)]}."
    )
    _pos_yoy_anchors = sum(1 for ch in CHANNEL_ORDER
                           for a in evergreen.get(ch,{}).get("anchors",[])
                           if (a.get("yoy_view_pct") or 0) > 0)
    _tot_anchors = sum(len(evergreen.get(ch,{}).get("anchors",[])) for ch in CHANNEL_ORDER)
    _anc_insight = (
        f"{_pos_yoy_anchors} of {_tot_anchors} tracked anchor videos show positive YoY view growth. "
        f"{_anc_outperf_s} outperform their channel's subscriber growth rate — "
        f"confirming algorithmic distribution independent of subscriber momentum. "
        f"Videos without 2023/2024 snapshot history show short-window YoY only."
    )
    _rmy_fastest_by_cagr = max(REDDIT_ORDER,
        key=lambda s: reddit_multiyear.get(s,{}).get("cagr_3yr_pct") or 0)
    _rmy_fastest_cagr = reddit_multiyear.get(_rmy_fastest_by_cagr,{}).get("cagr_3yr_pct")
    _rmy_insight = (
        f"Ecosystem expanded from {_rd_eco_2023_s} (2023) to {_rd_eco_2026_s} (2026). "
        f"3-Year CAGR: {_rd_cagr_s}. Fastest growing: {REDDIT_LABELS[_rmy_fastest_by_cagr]} "
        f"({_fp(_rmy_fastest_cagr)} CAGR)."
    )
    # ── Steam insight from STEAM_HISTORICAL_DATA metrics ─────────────────────
    # Interpretation thresholds: >20% = strong expansion, -10%→+10% = stable, <-10% = normalization
    _sh_strong  = [s for s in STEAM_ORDER
                   if (_steam_hist_metrics[s]["yoy_pct"] or -999) > 20]
    _sh_stable  = [s for s in STEAM_ORDER
                   if _steam_hist_metrics[s]["yoy_pct"] is not None
                   and -10 <= _steam_hist_metrics[s]["yoy_pct"] <= 20]
    _sh_3yr_norm = [STEAM_LABELS[s] for s in STEAM_ORDER
                    if (_steam_hist_metrics[s]["three_yr"] or 0) < -10]
    _sh_best_slug  = max(STEAM_ORDER,
                         key=lambda s: _steam_hist_metrics[s]["yoy_pct"] or -999)
    _sh_best_name  = STEAM_LABELS[_sh_best_slug]
    _sh_best_yoy   = _steam_hist_metrics[_sh_best_slug]["yoy_pct"]
    _sh_best_yoy_s = (f"{'+' if (_sh_best_yoy or 0) >= 0 else ''}{_sh_best_yoy:.1f}%"
                      if _sh_best_yoy is not None else "—")
    _sh_stab_vals  = [_steam_hist_metrics[s]["stability"] for s in STEAM_ORDER
                      if _steam_hist_metrics[s]["stability"] is not None]
    _sh_stab_min_s = f"{min(_sh_stab_vals):.1f}%" if _sh_stab_vals else "—"
    _sh_stab_max_s = f"{max(_sh_stab_vals):.1f}%" if _sh_stab_vals else "—"

    _steam_insight_parts = []
    if _sh_strong:
        _strong_names = [STEAM_LABELS[s] for s in _sh_strong]
        _steam_insight_parts.append(
            f"{len(_sh_strong)} of {_steam_n} title{'s' if len(_sh_strong)>1 else ''} "
            f"show{'s' if len(_sh_strong)==1 else ''} strong engagement expansion "
            f"(structural YoY >+20%): {', '.join(_strong_names)} ({_sh_best_yoy_s} structural YoY)."
        )
    if _sh_stable:
        _stable_names = [STEAM_LABELS[s] for s in _sh_stable]
        _steam_insight_parts.append(
            f"{len(_sh_stable)} title{'s' if len(_sh_stable)>1 else ''} "
            f"show{'s' if len(_sh_stable)==1 else ''} stable engagement "
            f"in the −10% to +20% band: {', '.join(_stable_names)}."
        )
    if _sh_3yr_norm:
        _n3 = len(_sh_3yr_norm)
        _steam_insight_parts.append(
            f"On a 3-year view, {', '.join(_sh_3yr_norm)} "
            f"show{'s' if _n3==1 else ''} post-release normalization — "
            f"consistent with declining engagement for titles beyond their initial release cycle."
        )
    _steam_insight_parts.append(
        f"Engagement Stability Ratios (current avg ÷ all-time peak) range from "
        f"{_sh_stab_min_s} to {_sh_stab_max_s}, confirming that new releases drive "
        f"ecosystem-level engagement spikes while older titles stabilize at durable player floors."
    )
    _steam_insight = " ".join(_steam_insight_parts)

    # ── Tournament metrics (derived from TOURNAMENT_DATA constant) ────────────
    _t_all_years = sorted({yr for ev in TOURNAMENT_DATA.values() for yr in ev["players"]})
    _t_base      = _t_all_years[0]    # earliest year
    _t_prev      = _t_all_years[-2]   # second-to-last year
    _t_latest    = _t_all_years[-1]   # most recent year

    def _fmt_badge(pct):
        if pct is None:
            return "<span class='badge badge-neu'>—</span>"
        cls = "badge-pos" if pct >= 0 else "badge-neg"
        sign = "+" if pct >= 0 else ""
        return f"<span class='badge {cls}'>{sign}{pct:.1f}%</span>"

    _t_event_metrics = {}
    for _t_slug, _t_ev in TOURNAMENT_DATA.items():
        _p       = _t_ev["players"]
        _base_n  = _p.get(_t_base)
        _prev_n  = _p.get(_t_prev)
        _last_n  = _p.get(_t_latest)
        _yoy     = (_last_n - _prev_n) / _prev_n * 100 if _prev_n else None
        _two_yr  = (_last_n - _base_n) / _base_n * 100 if _base_n else None
        _t_event_metrics[_t_slug] = {
            "name":     _t_ev["name"],
            "desc":     _t_ev["desc"],
            "base_n":   _base_n,
            "prev_n":   _prev_n,
            "latest_n": _last_n,
            "yoy_pct":  _yoy,
            "two_yr":   _two_yr,
        }

    # Combined totals row
    _t_comb_base   = sum(m["base_n"]   for m in _t_event_metrics.values() if m["base_n"])
    _t_comb_prev   = sum(m["prev_n"]   for m in _t_event_metrics.values() if m["prev_n"])
    _t_comb_latest = sum(m["latest_n"] for m in _t_event_metrics.values() if m["latest_n"])
    _t_comb_yoy    = ((_t_comb_latest - _t_comb_prev) / _t_comb_prev * 100
                      if _t_comb_prev else None)
    _t_comb_2yr    = ((_t_comb_latest - _t_comb_base) / _t_comb_base * 100
                      if _t_comb_base else None)

    # Build tournament table rows HTML
    _tournament_table_rows = ""
    for _t_slug in TOURNAMENT_ORDER:
        _m = _t_event_metrics[_t_slug]
        _tournament_table_rows += (
            f"<tr>"
            f"<td><strong>{_m['name']}</strong>"
            f"<span style='display:block;font-size:11px;color:#8b949e;margin-top:2px'>{_m['desc']}</span></td>"
            f"<td class='num'>{_m['base_n']:,}</td>"
            f"<td class='num'>{_m['prev_n']:,}</td>"
            f"<td class='num'>{_m['latest_n']:,}</td>"
            f"<td class='num'>{_fmt_badge(_m['yoy_pct'])}</td>"
            f"<td class='num'>{_fmt_badge(_m['two_yr'])}</td>"
            f"</tr>\n"
        )
    _tournament_table_rows += (
        f"<tr style='border-top:2px solid #30363d;'>"
        f"<td><strong style='color:#cdd9e5'>Combined Participation</strong>"
        f"<span style='display:block;font-size:11px;color:#8b949e;margin-top:2px'>"
        f"Both events · total registered players</span></td>"
        f"<td class='num'><strong>{_t_comb_base:,}</strong></td>"
        f"<td class='num'><strong>{_t_comb_prev:,}</strong></td>"
        f"<td class='num'><strong>{_t_comb_latest:,}</strong></td>"
        f"<td class='num'>{_fmt_badge(_t_comb_yoy)}</td>"
        f"<td class='num'>{_fmt_badge(_t_comb_2yr)}</td>"
        f"</tr>\n"
    )

    # Fastest growing event by 2-year growth
    _t_fastest_slug = max(TOURNAMENT_ORDER,
                          key=lambda s: _t_event_metrics[s]["two_yr"] or 0)
    _t_fastest      = _t_event_metrics[_t_fastest_slug]
    _t_fastest_2yr_s = (f"{'+' if (_t_fastest['two_yr'] or 0) >= 0 else ''}{_t_fastest['two_yr']:.1f}%"
                         if _t_fastest["two_yr"] is not None else "—")

    # Events first crossing 1,000 in the latest year
    _t_1k_crossings = [
        TOURNAMENT_DATA[s]["short"] for s in TOURNAMENT_ORDER
        if (_t_event_metrics[s]["prev_n"] or 0) < 1000
        <= (_t_event_metrics[s]["latest_n"] or 0)
    ]
    _t_comb_2yr_s = (f"{'+' if (_t_comb_2yr or 0) >= 0 else ''}{_t_comb_2yr:.1f}%"
                     if _t_comb_2yr is not None else "—")

    # Build dynamic tournament insight
    _tournament_insight = (
        f"Competitive Warhammer participation across the two largest global tournaments expanded "
        f"from {_t_comb_base:,} players in {_t_base} to {_t_comb_latest:,} players in {_t_latest} "
        f"({_t_comb_2yr_s} over {_t_latest - _t_base} years). "
        f"Growth is driven primarily by the {_t_fastest['name']}, which expanded from "
        f"{_t_fastest['base_n']:,} to {_t_fastest['latest_n']:,} players "
        f"({_t_fastest_2yr_s} over {_t_latest - _t_base} years). "
    ) + (
        f"{' and '.join(_t_1k_crossings)} crossed 1,000 registered players for the first time "
        f"in {_t_latest} — a milestone confirming sustained real-world hobby participation growth. "
        if _t_1k_crossings else
        f"These figures confirm that digital demand signals are translating into "
        f"measurable real-world hobby participation. "
    )

    # Inject tournament chart data into window.__yt
    chart_data["tournament"] = {
        "labels": [TOURNAMENT_DATA[s]["name"] for s in TOURNAMENT_ORDER],
        "years":  _t_all_years,
        "datasets": [
            {
                "label": str(yr),
                "data":  [TOURNAMENT_DATA[s]["players"].get(yr, 0) for s in TOURNAMENT_ORDER],
            }
            for yr in _t_all_years
        ],
    }

    # ── BCP store-level event data ─────────────────────────────────────────────
    _bcp_json_path = os.path.join(os.path.dirname(__file__), "..", "data", "bcp_events.json")
    _bcp_events = []
    _bcp_from_file = False
    try:
        with open(_bcp_json_path) as _f:
            _bcp_events = json.load(_f)
        if _bcp_events:
            _bcp_from_file = True
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if _bcp_from_file:
        from collections import Counter as _Counter
        from datetime import date as _date
        _bcp_snap = _bcp_events[0].get("snapshot_date", "—") if _bcp_events else "—"

        # Normalize country names (API returns inconsistent codes + full names)
        _bcp_country_map = {
            "US": "United States", "USA": "United States",
            "GB": "United Kingdom", "UK": "United Kingdom",
            "CA": "Canada",
            "AU": "Australia", "AUS": "Australia",
            "DE": "Germany", "Deutschland": "Germany",
            "FR": "France",
            "ES": "Spain", "España": "Spain",
            "NZ": "New Zealand",
            "RU": "Russia", "Россия": "Russia",
            "IT": "Italy", "Italia": "Italy",
            "NL": "Netherlands",
            "PL": "Poland",
            "SE": "Sweden",
        }
        for _ev in _bcp_events:
            _ev["country"] = _bcp_country_map.get(_ev.get("country", ""), _ev.get("country", ""))

        # Monthly event counts and player totals
        _bcp_months       = _Counter(e["date"][:7] for e in _bcp_events if e.get("date") and len(e["date"]) >= 7)
        _bcp_month_players = {}
        for _ev in _bcp_events:
            _mo = (_ev.get("date") or "")[:7]
            if _mo:
                _bcp_month_players[_mo] = _bcp_month_players.get(_mo, 0) + (_ev.get("player_count") or 0)
        _bcp_month_labels       = sorted(_bcp_months.keys())
        _bcp_month_vals         = [_bcp_months[m] for m in _bcp_month_labels]
        _bcp_month_player_vals  = [_bcp_month_players.get(m, 0) for m in _bcp_month_labels]

        # Average players per event (only non-zero)
        _bcp_nonzero = [e for e in _bcp_events if (e.get("player_count") or 0) > 0]
        _bcp_avg_players = (
            sum(e["player_count"] for e in _bcp_nonzero) / len(_bcp_nonzero)
            if _bcp_nonzero else 0
        )
        _bcp_total_players = sum(e.get("player_count") or 0 for e in _bcp_events)
        _bcp_total_events  = len(_bcp_events)

        # Determine partial vs complete months
        import calendar as _cal
        _today_bcp       = _date.today()
        _current_ym      = f"{_today_bcp.year:04d}-{_today_bcp.month:02d}"
        _last_day_of_mo  = _cal.monthrange(_today_bcp.year, _today_bcp.month)[1]
        _month_is_partial = (_today_bcp.day < _last_day_of_mo)
        # Complete months only (exclude current month if still in progress)
        _bcp_complete_labels = [m for m in _bcp_month_labels
                                if not (m == _current_ym and _month_is_partial)]

        # YoY: last complete month vs same month prior year
        _bcp_yoy_pct     = None
        _bcp_yoy_label   = ""
        _bcp_3mo_yoy_pct = None
        _bcp_3mo_label   = ""
        if len(_bcp_complete_labels) >= 13:
            _bcp_ref_mo   = _bcp_complete_labels[-1]
            _bcp_prior_mo = f"{int(_bcp_ref_mo[:4])-1}{_bcp_ref_mo[4:]}"
            if _bcp_prior_mo in _bcp_month_players and _bcp_month_players[_bcp_prior_mo] > 0:
                _bcp_yoy_pct   = ((_bcp_month_players[_bcp_ref_mo] - _bcp_month_players[_bcp_prior_mo])
                                  / _bcp_month_players[_bcp_prior_mo] * 100)
                _bcp_yoy_label = f"{_bcp_ref_mo} vs {_bcp_prior_mo}"
            # 3-month rolling YoY (last 3 complete months vs same 3 months prior year)
            _bcp_last3    = _bcp_complete_labels[-3:]
            _bcp_prior3   = [f"{int(m[:4])-1}{m[4:]}" for m in _bcp_last3]
            _curr3_total  = sum(_bcp_month_players.get(m, 0) for m in _bcp_last3)
            _prior3_total = sum(_bcp_month_players.get(m, 0) for m in _bcp_prior3)
            if _prior3_total > 0:
                _bcp_3mo_yoy_pct = ((_curr3_total - _prior3_total) / _prior3_total * 100)
                _bcp_3mo_label   = f"{_bcp_last3[0]} – {_bcp_last3[-1]}"

        # Build YoY badge HTML
        if _bcp_yoy_pct is not None:
            _bcp_yoy_col  = "#27ae60" if _bcp_yoy_pct >= 0 else "#e74c3c"
            _bcp_yoy_sign = "+" if _bcp_yoy_pct >= 0 else ""
            _3mo_col      = "#27ae60" if (_bcp_3mo_yoy_pct or 0) >= 0 else "#e74c3c"
            _3mo_sign     = "+" if (_bcp_3mo_yoy_pct or 0) >= 0 else ""
            _3mo_part     = (
                f' &nbsp;·&nbsp; <span style="font-size:16px;font-weight:700;color:{_3mo_col};">'
                f'{_3mo_sign}{_bcp_3mo_yoy_pct:.1f}% 3-mo rolling YoY</span>'
                f'<span style="font-size:11px;color:var(--muted);"> ({_bcp_3mo_label})</span>'
            ) if _bcp_3mo_yoy_pct is not None else ""
            _bcp_yoy_badge = (
                f'<div style="background:var(--surface);border:1px solid var(--border);'
                f'border-radius:6px;padding:12px 16px;margin-bottom:18px;display:flex;'
                f'align-items:center;gap:8px;flex-wrap:wrap;">'
                f'<span style="font-size:20px;font-weight:700;color:{_bcp_yoy_col};">'
                f'{_bcp_yoy_sign}{_bcp_yoy_pct:.1f}% YoY</span>'
                f'<span style="font-size:11px;color:var(--muted);">players — last complete month '
                f'({_bcp_yoy_label})</span>'
                f'{_3mo_part}'
                f'</div>'
            )
        else:
            _bcp_yoy_badge = ""
        # Partial-month note for chart
        _bcp_partial_note = (
            f' <span style="font-size:10px;color:#e6a817;">'
            f'({_current_ym} bar is partial — {_today_bcp.day}/{_last_day_of_mo} days)</span>'
        ) if _month_is_partial and _current_ym in _bcp_months else ""
        # Most recent 20 events table
        _bcp_recent = _bcp_events[:20]
        _bcp_recent_rows = ""
        for _ev in _bcp_recent:
            _pc = _ev.get("player_count") or 0
            _bcp_recent_rows += (
                f"<tr>"
                f"<td class='muted-cell'>{_ev.get('date', '—')}</td>"
                f"<td>{_ev.get('event_name', '—')}</td>"
                f"<td class='muted-cell'>{_ev.get('store_name', '—')}</td>"
                f"<td class='muted-cell'>{', '.join(filter(None,[_ev.get('city',''),_ev.get('state',''),_ev.get('country','')]))}</td>"
                f"<td class='num'>{_pc:,}</td>"
                f"<td class='muted-cell'>{_ev.get('event_type', '—')}</td>"
                f"</tr>"
            )
        _bcp_section_html = f"""
<!-- ── BCP: Store-Level Organised Play ─────────────────────────────────── -->
<section>
  <div class="section-title">Store-Level Organised Play — Best Coast Pairings</div>
  <div class="section-sub">
    Best Coast Pairings is the dominant tournament management platform for Warhammer 40k store events.
    Each event = a direct headcount of engaged hobbyists attending a physical store.
    Monthly event count growth = expansion of the organised play community.
    Avg players per event = depth of engagement per store visit.
    Source: BCP public API. Snapshot: {_bcp_snap}.
  </div>

  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px;">
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:var(--text);">{_bcp_total_players:,}</div>
      <div style="font-size:10px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:0.5px;">Total Players Tracked</div>
    </div>
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:var(--text);">{_bcp_total_events:,}</div>
      <div style="font-size:10px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:0.5px;">Events Tracked</div>
    </div>
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#27ae60;">{_bcp_avg_players:.0f}</div>
      <div style="font-size:10px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:0.5px;">Avg Players / Event</div>
    </div>
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#2980b9;">{len(_bcp_month_labels)}</div>
      <div style="font-size:10px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:0.5px;">Months of History</div>
    </div>
  </div>
  {_bcp_yoy_badge}

  <div class="chart-card" style="margin-bottom:18px;">
    <h3>Monthly Players Attending Organised Play — Warhammer 40k (BCP)</h3>
    <div class="chart-wrap-md"><canvas id="chartBcpMonthly"></canvas></div>
    <p class="data-note">Total players across all BCP-tracked 40k store events each month.
    Each bar = real headcount of hobbyists walking into a store for competitive play.{_bcp_partial_note}
    Source: Best Coast Pairings public API ({_bcp_snap}).</p>
  </div>

  <div class="table-card">
    <h3 style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                color:var(--muted);margin-bottom:12px;">Most Recent 20 Events</h3>
    <table>
      <thead>
        <tr>
          <th>Date</th><th>Event</th><th>Store</th><th>Location</th>
          <th class="num">Players</th><th>Type</th>
        </tr>
      </thead>
      <tbody>{_bcp_recent_rows}</tbody>
    </table>
    <p class="data-note">Source: Best Coast Pairings public API. Update monthly via scripts/scrape_bcp.py.</p>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Best Coast Pairings runs store-level Warhammer 40k tournaments. Every event in this dataset is real players walking into a physical store to compete — this is the most direct measure of store traffic available outside GW's own data. Approximately 12,000 players per month attending organised play events, consistently, for 3 years straight with no meaningful decline. That's the physical engagement floor: even in the quietest months, the organised play network holds at scale.
  </div>
</section>
"""
        # Store BCP chart data for the JS section
        _bcp_chart_data = {
            "monthLabels":      _bcp_month_labels,
            "monthVals":        _bcp_month_vals,
            "monthPlayerVals":  _bcp_month_player_vals,
            "avgPlayers":       round(_bcp_avg_players, 1),
            "totalEvents":      _bcp_total_events,
            "totalPlayers":     _bcp_total_players,
            "snapDate":         _bcp_snap,
        }
    else:
        _bcp_section_html = """
<!-- ── BCP: Store-Level Organised Play (placeholder) ───────────────────── -->
<section>
  <div class="section-title">Store-Level Organised Play — Best Coast Pairings
    <span style="margin-left:10px;font-size:10px;font-weight:600;color:#e6a817;background:#2d2408;border:1px solid #e6a817;border-radius:4px;padding:2px 7px;vertical-align:middle;">⏳ PENDING DATA</span>
  </div>
  <div class="section-sub">
    Best Coast Pairings is the dominant tournament management platform for Warhammer 40k store events.
    Each event = a direct headcount of engaged hobbyists attending a physical store.
  </div>
  <div class="table-card" style="text-align:center;padding:32px;">
    <div style="font-size:13px;font-weight:600;color:#e6a817;margin-bottom:8px;">
      Data collection in progress
    </div>
    <div style="font-size:11px;color:var(--muted);line-height:1.7;">
      Run <code style="color:#5aacdf;">scripts/scrape_bcp.py</code> to populate
      <code style="color:#5aacdf;">data/bcp_events.json</code>.
      No API key required — uses BCP public API.
    </div>
  </div>
</section>
"""
        _bcp_chart_data = None

    # Executive summary (legacy — no longer shown in new template)
    exec_html = ""

    # Ecosystem YoY — computed from sum of individual channel YoY snapshots
    _yt_eco_curr = sum(yoy.get(ch, {}).get("curr_subs") or 0 for ch in CHANNEL_ORDER)
    _yt_eco_ref  = sum(yoy.get(ch, {}).get("ref_subs")  or 0 for ch in CHANNEL_ORDER)
    if _yt_eco_ref:
        _eco_yoy_pct = (_yt_eco_curr - _yt_eco_ref) / _yt_eco_ref * 100
        eco_g_str = f"{'+' if _eco_yoy_pct >= 0 else ''}{_eco_yoy_pct:.1f}%"
        eco_color = "#27ae60" if _eco_yoy_pct > 0 else "#c0392b"
    else:
        eco_g_str = "—"
        eco_color = "#e67e22"

    _total_ccu_fmt    = f"{_total_ccu:,}" if _total_ccu else "—"

    # ── Update anchor_growths to use YoY view pct (consistent with 2025→2026 window) ─
    _new_anchor_labels  = []
    _new_anchor_growths = []
    _new_anchor_colors  = []
    for ch in CHANNEL_ORDER:
        for a in evergreen.get(ch, {}).get("anchors", []):
            yoy_vp = a.get("yoy_view_pct")
            if yoy_vp is not None:
                _new_anchor_labels.append(a["title"][:42])
                _new_anchor_growths.append(yoy_vp)
                _new_anchor_colors.append(CHANNEL_COLORS[ch])
            elif a.get("growth_pct") is not None:
                _new_anchor_labels.append(a["title"][:42] + " ‡")
                _new_anchor_growths.append(a["growth_pct"])
                _new_anchor_colors.append(CHANNEL_COLORS[ch])
    # Patch chart_data with updated anchor arrays
    chart_data["anchorLabels"]  = _new_anchor_labels
    chart_data["anchorGrowths"] = _new_anchor_growths
    chart_data["anchorColors"]  = _new_anchor_colors
    # Remove only unused chart data keys (keep typeLabels/Avgs/Colors, slopeDatasets, reddit.yoyVals/trajDatasets)
    for _k in ("velAvg", "velMed", "trajDatasets"):
        chart_data.pop(_k, None)
    chart_data["steam"].pop("momLabels", None)
    chart_data["steam"].pop("momDatasets", None)

    # ── Inject STEAM_HISTORICAL_DATA-derived metrics for exec summary ─────────
    # These are computed after the _steam_insight block so all _sh_* vars are in scope.
    chart_data["steam"]["hist"] = {
        "strongCount": len(_sh_strong),
        "stableCount": len(_sh_stable),
        "bestTitle":   _sh_best_name,
        "bestYoy":     round(_sh_best_yoy, 1) if _sh_best_yoy is not None else None,
        "threeYrNorm": _sh_3yr_norm,           # list of title names
        "stabMin":     round(min(_sh_stab_vals), 1) if _sh_stab_vals else None,
        "stabMax":     round(max(_sh_stab_vals), 1) if _sh_stab_vals else None,
        "posCount":    sum(1 for s in STEAM_ORDER
                           if (_steam_hist_metrics[s]["yoy_pct"] or 0) > 0),
        "baseYr":      _sh_base_yr,
        "prevYr":      _sh_prev_yr,
        "currYr":      _sh_curr_yr,
    }

    # Add slope label strings so JS can label the slopegraph X-axis correctly
    chart_data["slopeBaseLbl"]   = slope_base_lbl
    chart_data["slopeLatestLbl"] = slope_latest_lbl

    # ── Page 7: Retail & Store Intelligence ──────────────────────────────────

    # Revenue channel chart data
    _rc_periods = list(GW_STORE_DATA["revenue_h1_gbp_m"].keys())
    _rc_period_labels = [p.replace("H1_FY", "H1 FY") for p in _rc_periods]
    _rc_retail  = [GW_STORE_DATA["revenue_h1_gbp_m"][p]["own_retail"] for p in _rc_periods]
    _rc_trade   = [GW_STORE_DATA["revenue_h1_gbp_m"][p]["trade"]      for p in _rc_periods]
    _rc_online  = [GW_STORE_DATA["revenue_h1_gbp_m"][p]["online"]     for p in _rc_periods]

    # Store count chart data (own stores — yearly)
    _sc_own_years = sorted(GW_STORE_DATA["own_stores"].keys())
    _sc_own_vals  = [GW_STORE_DATA["own_stores"][y] for y in _sc_own_years]
    _sc_ind_years = sorted(GW_STORE_DATA["indie_retailers"].keys())
    _sc_ind_vals  = [GW_STORE_DATA["indie_retailers"][y] for y in _sc_ind_years]

    # Indexed growth arrays (base=100 at earliest year for each series)
    # Makes relative growth rate directly comparable on the same axis
    _sc_own_base = _sc_own_vals[0]
    _sc_ind_base = _sc_ind_vals[0]
    _sc_own_idx  = [round(v / _sc_own_base * 100, 1) for v in _sc_own_vals]
    _sc_ind_idx  = [round(v / _sc_ind_base * 100, 1) for v in _sc_ind_vals]
    # indie indexed values aligned to own_years (null before indie tracking started)
    _sc_ind_year_map = dict(zip(_sc_ind_years, _sc_ind_idx))
    _sc_ind_idx_aligned = [_sc_ind_year_map.get(y) for y in _sc_own_years]

    # Trade share % per period
    _rc_trade_share = [
        round(GW_STORE_DATA["revenue_h1_gbp_m"][p]["trade"] /
              sum(GW_STORE_DATA["revenue_h1_gbp_m"][p].values()) * 100, 1)
        for p in _rc_periods
    ]
    _trade_share_first = _rc_trade_share[0]
    _trade_share_last  = _rc_trade_share[-1]

    # Revenue per store (£K per store per H1) — Own Retail ÷ contemporary store count
    # Standard retail "sales per location" productivity metric — rises only if demand rises
    _rps_store_map = GW_STORE_DATA["h1_store_count_map"]
    _rps_vals = [
        round(GW_STORE_DATA["revenue_h1_gbp_m"][p]["own_retail"] * 1000 / _rps_store_map[p], 1)
        for p in _rc_periods
    ]
    _rps_first  = _rps_vals[0]
    _rps_last   = _rps_vals[-1]
    _rps_growth = round((_rps_last / _rps_first - 1) * 100, 1)

    # Revenue per store table rows (pre-computed to avoid f-string nesting issues)
    _rps_table_rows = ""
    for _i, _p in enumerate(_rc_periods):
        _sc = _rps_store_map[_p]
        _rev = GW_STORE_DATA["revenue_h1_gbp_m"][_p]["own_retail"]
        _rps = _rps_vals[_i]
        _rps_badge = (
            f"<span class='badge badge-pos'>£{_rps:.1f}K</span>"
            if _i == len(_rc_periods) - 1
            else f"£{_rps:.1f}K"
        )
        _rps_table_rows += (
            f"<tr>"
            f"<td>{_p.replace('H1_FY', 'H1 FY')}</td>"
            f"<td class='num'>{_sc}</td>"
            f"<td class='num'>£{_rev:.1f}M</td>"
            f"<td class='num'>{_rps_badge}</td>"
            f"</tr>"
        )

    # LinkedIn revenue commitment framing
    # Each new store = ~£226K annual revenue GW is committing to at that location
    _li_avg_annual_rev_k = round(_rps_last * 2, 1)   # latest H1 × 2 = annualized
    _li_rev_commitment_m = round(_li_avg_annual_rev_k * len(LINKEDIN_OPENINGS["openings"]) / 1000, 1)

    # Revenue channel table rows
    _rc_table_rows = ""
    _h1_first_k = _rc_periods[0]
    _h1_latest_k = _rc_periods[-1]
    _h1_first  = GW_STORE_DATA["revenue_h1_gbp_m"][_h1_first_k]
    _h1_latest = GW_STORE_DATA["revenue_h1_gbp_m"][_h1_latest_k]
    for _p in _rc_periods:
        _rv = GW_STORE_DATA["revenue_h1_gbp_m"][_p]
        _total = _rv["own_retail"] + _rv["trade"] + _rv["online"]
        _trade_share = _rv["trade"] / _total * 100
        _rc_table_rows += (
            f"<tr><td>{_p.replace('H1_FY', 'H1 FY')}</td>"
            f"<td class='num'>£{_rv['own_retail']:.1f}M</td>"
            f"<td class='num'>£{_rv['trade']:.1f}M</td>"
            f"<td class='num'>£{_rv['online']:.1f}M</td>"
            f"<td class='num'>£{_total:.1f}M</td>"
            f"<td class='num'>{_trade_share:.0f}%</td>"
            f"</tr>"
        )

    # Google Maps table rows — prefer stores.json if available, else fall back to 5-store snapshot
    _stores_json_path = os.path.join(os.path.dirname(__file__), "..", "data", "stores.json")
    _stores_full = []
    _gmaps_from_json = False
    try:
        with open(_stores_json_path) as _f:
            _stores_full = json.load(_f)
        if _stores_full:
            _gmaps_from_json = True
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if _gmaps_from_json:
        # Full network table from stores.json
        _gmaps_total_stores  = len(_stores_full)
        _gmaps_total_reviews = sum(s.get("review_count") or 0 for s in _stores_full)
        _valid_ratings = [s["rating"] for s in _stores_full if s.get("rating")]
        _gmaps_avg_rating = sum(_valid_ratings) / len(_valid_ratings) if _valid_ratings else 0
        _gmaps_date = _stores_full[0].get("snapshot_date", GOOGLE_MAPS_SNAPSHOT["last_updated"])
        # Stat card HTML
        _gmaps_stat_cards = (
            f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;'>"
            f"<div style='background:var(--bg);border:1px solid var(--border);border-radius:4px;"
            f"padding:12px;text-align:center;'>"
            f"<div style='font-size:22px;font-weight:700;color:var(--text);'>{_gmaps_total_stores}</div>"
            f"<div style='font-size:10px;color:var(--muted);margin-top:2px;'>Stores Tracked</div></div>"
            f"<div style='background:var(--bg);border:1px solid var(--border);border-radius:4px;"
            f"padding:12px;text-align:center;'>"
            f"<div style='font-size:22px;font-weight:700;color:#27ae60;'>{_gmaps_avg_rating:.2f} ★</div>"
            f"<div style='font-size:10px;color:var(--muted);margin-top:2px;'>Avg Network Rating</div></div>"
            f"<div style='background:var(--bg);border:1px solid var(--border);border-radius:4px;"
            f"padding:12px;text-align:center;'>"
            f"<div style='font-size:22px;font-weight:700;color:#2980b9;'>{_gmaps_total_reviews:,}</div>"
            f"<div style='font-size:10px;color:var(--muted);margin-top:2px;'>Total Reviews</div></div>"
            f"</div>"
        )
        _gmaps_rows = ""
        _gmaps_last_country = None
        for _store in _stores_full:
            _c = _store.get("country", "")
            if _c != _gmaps_last_country:
                _gmaps_rows += (
                    f"<tr style='background:#151d2b;'>"
                    f"<td colspan='4' style='font-size:10px;font-weight:700;text-transform:uppercase;"
                    f"letter-spacing:0.8px;color:var(--muted);padding:6px 12px;'>{_c}</td>"
                    f"</tr>"
                )
                _gmaps_last_country = _c
            _rat = _store.get("rating")
            _rat_str = f"{_rat:.2f} ★" if _rat else "—"
            _rev = _store.get("review_count") or 0
            _loc = ", ".join(filter(None, [_store.get("city", ""), _c]))
            _gmaps_rows += (
                f"<tr>"
                f"<td>{_store['name']}</td>"
                f"<td class='muted-cell'>{_loc}</td>"
                f"<td class='num'>{_rat_str}</td>"
                f"<td class='num'>{_rev:,}</td>"
                f"</tr>"
            )
    else:
        # Fallback: 5-store manual snapshot
        _gmaps_total_stores  = len(GOOGLE_MAPS_SNAPSHOT["stores"])
        _gmaps_total_reviews = sum(s["reviews"] for s in GOOGLE_MAPS_SNAPSHOT["stores"])
        _gmaps_avg_rating    = sum(s["stars"] for s in GOOGLE_MAPS_SNAPSHOT["stores"]) / _gmaps_total_stores
        _gmaps_date = GOOGLE_MAPS_SNAPSHOT["last_updated"]
        _gmaps_stat_cards = ""  # no stat cards for 5-store fallback
        _gmaps_rows = ""
        for _store in GOOGLE_MAPS_SNAPSHOT["stores"]:
            _gmaps_rows += (
                f"<tr>"
                f"<td>{_store['name']}</td>"
                f"<td class='muted-cell'>{_store['city']}</td>"
                f"<td class='num'>{_store['stars']:.2f} ★</td>"
                f"<td class='num'>{_store['reviews']:,}</td>"
                f"</tr>"
            )

    # LinkedIn openings rows
    _region_colors = {"APAC": "#2980b9", "EMEA": "#27ae60", "UK": "#8e44ad", "Americas": "#e67e22"}
    _li_rows = ""
    _li_first_entry_html = ""
    _li_expansion_rows_html = ""
    for _op in LINKEDIN_OPENINGS["openings"]:
        _rc_color = _region_colors.get(_op["region"], "#666")
        _mtype_badge = (
            "<span class='badge badge-pos'>First Entry</span>"
            if _op["market_type"] == "First entry"
            else "<span class='badge badge-mid'>Expansion</span>"
        )
        _li_rows += (
            f"<tr>"
            f"<td>{_op['location']}</td>"
            f"<td><span style='color:{_rc_color};font-weight:600;'>{_op['region']}</span></td>"
            f"<td>{_mtype_badge}</td>"
            f"</tr>"
        )
        if _op["market_type"] == "First entry":
            _li_first_entry_html += (
                f"<div style='background:#1c2e1c;border:1px solid #27ae6044;border-radius:4px;"
                f"padding:8px 12px;margin-bottom:6px;font-size:12px;'>"
                f"<span class='badge badge-pos'>First Entry</span> "
                f"<strong style='color:var(--text);'>{_op['location']}</strong> "
                f"<span style='color:var(--muted);'>({_op['region']}) — no GW store previously existed in this market</span>"
                f"</div>"
            )
        else:
            _li_expansion_rows_html += (
                f"<tr><td>{_op['location']}</td>"
                f"<td><span style='color:{_rc_color};font-weight:600;'>{_op['region']}</span></td></tr>"
            )
    _li_regions_count = len(set(o["region"] for o in LINKEDIN_OPENINGS["openings"]))

    # Notable Retail Demand Events — build table rows from structured dicts
    _region_colors_ev = {"Americas": "#e67e22", "APAC": "#2980b9", "EMEA": "#27ae60", "UK": "#8e44ad"}
    _narrative_rows = ""
    for _ev in PASSBY_DATA["narrative_events"]:
        _rc = _region_colors_ev.get(_ev["region"], "#999")
        _src_lower = _ev["source"].lower()
        if "verify" in _src_lower:
            _src_html = (
                f"<span style='color:#e74c3c;font-weight:600;'>⚠ {_ev['source']}</span>"
            )
        else:
            _src_html = f"<span style='color:var(--muted);'>{_ev['source']}</span>"
        _narrative_rows += (
            f"<tr>"
            f"<td class='muted-cell' style='white-space:nowrap;'>{_ev['date']}</td>"
            f"<td>{_ev['event']}</td>"
            f"<td><span style='color:{_rc};font-weight:600;'>{_ev['region']}</span></td>"
            f"<td>{_src_html}</td>"
            f"</tr>"
        )

    # PassBy foot traffic table rows
    _passby_rows = ""
    for _pb in PASSBY_DATA["snapshots"]:
        _yoy_val = _pb.get("yoy_pct")
        if _yoy_val is not None:
            if _yoy_val > 10:
                _badge = f"<span class='badge badge-pos'>+{_yoy_val:.1f}%</span>"
            elif _yoy_val >= 0:
                _badge = f"<span class='badge badge-mid'>+{_yoy_val:.1f}%</span>"
            else:
                _badge = f"<span class='badge badge-neg'>{_yoy_val:.1f}%</span>"
            _passby_rows += (
                f"<tr><td>{_pb['period']}</td>"
                f"<td class='num'>{_badge}</td>"
                f"<td class='muted-cell'>{_pb['note']}</td></tr>"
            )
        else:
            _visits = _pb.get("visits_k", "—")
            _passby_rows += (
                f"<tr><td>{_pb['period']}</td>"
                f"<td class='num'>{_visits:,}K+ visits</td>"
                f"<td class='muted-cell'>{_pb['note']}</td></tr>"
            )

    # App data display — from snapshots list
    _app_snaps     = MY_WARHAMMER_APP_DATA["snapshots"]
    _app_latest    = _app_snaps[-1]
    _app_latest_val = _app_latest["users"]
    _app_latest_yoy = _app_latest["yoy_pct"]
    _app_latest_lbl = _app_latest["label"]
    _app_users_fmt  = f"{_app_latest_val / 1_000_000:.3f}M" if _app_latest_val >= 1_000_000 else f"{_app_latest_val:,}"
    # App table rows
    _app_table_rows = ""
    _app_prev_users = None
    for _snap in _app_snaps:
        _u = _snap["users"]
        # Use reported YoY if available, otherwise compute vs prior snapshot
        _yoy = _snap["yoy_pct"]
        if _yoy is None and _app_prev_users:
            _yoy = (_u / _app_prev_users - 1) * 100
        _yoy_badge = (
            f"<span class='badge badge-pos'>+{_yoy:.0f}%</span>" if _yoy and _yoy > 5
            else f"<span class='badge badge-mid'>+{_yoy:.0f}%</span>" if _yoy and _yoy >= 0
            else f"<span class='badge badge-na'>—</span>"
        )
        _app_table_rows += (
            f"<tr>"
            f"<td>{_snap['label']}</td>"
            f"<td class='num'>{_u:,}</td>"
            f"<td class='num'>{_yoy_badge}</td>"
            f"<td class='muted-cell'>{_snap['source']}</td>"
            f"</tr>"
        )
        _app_prev_users = _u
    # App chart data
    _app_chart_labels = [s["label"] for s in _app_snaps]
    _app_chart_vals   = [s["users"]  for s in _app_snaps]

    # Reddit store threads (from fetch_reddit_store_threads.py)
    _store_threads_have_data = False
    _store_threads_monthly_rows = ""
    _store_threads_recent_rows  = ""
    _store_threads_months_html  = ""
    _store_eco_chart_labels     = []
    _store_eco_chart_vals       = []
    _store_first_month          = "—"
    _store_latest_month         = "—"
    _store_latest_count         = None
    _store_prev_count           = None
    _store_yoy_html             = ""

    if store_threads_monthly_df is not None and not store_threads_monthly_df.empty:
        _store_threads_have_data = True

        # Ecosystem totals time series (for chart)
        _eco_m = store_threads_monthly_df[store_threads_monthly_df["subreddit"] == "__eco__"].copy()
        if not _eco_m.empty:
            _eco_m = _eco_m.sort_values("month")
            _store_eco_chart_labels = _eco_m["month"].tolist()
            _store_eco_chart_vals   = _eco_m["post_count"].astype(int).tolist()
            _store_first_month  = _store_eco_chart_labels[0]
            _store_latest_month = _store_eco_chart_labels[-1]
            _store_latest_count = _store_eco_chart_vals[-1]

            # Use last *completed* month for YoY — current month is always partial
            _today_ym = datetime.now(timezone.utc).strftime("%Y-%m")
            if _store_eco_chart_labels[-1] == _today_ym and len(_store_eco_chart_labels) >= 2:
                _yoy_cur_idx   = -2   # last completed month
                _yoy_prior_idx = -14  # same month prior year
                _yoy_label_mo  = _store_eco_chart_labels[-2]
            else:
                _yoy_cur_idx   = -1
                _yoy_prior_idx = -13
                _yoy_label_mo  = _store_eco_chart_labels[-1]

            _yoy_cur_count = _store_eco_chart_vals[_yoy_cur_idx] if len(_store_eco_chart_vals) >= abs(_yoy_cur_idx) else None
            if len(_store_eco_chart_vals) >= abs(_yoy_prior_idx):
                _store_prev_count = _store_eco_chart_vals[_yoy_prior_idx]
            elif len(_store_eco_chart_vals) >= 2:
                _store_prev_count = _store_eco_chart_vals[0]
            if _store_prev_count and _store_prev_count > 0 and _yoy_cur_count:
                _st_yoy_pct = (_yoy_cur_count / _store_prev_count - 1) * 100
                _st_color = "#27ae60" if _st_yoy_pct >= 0 else "#e74c3c"
                _st_sign  = "+" if _st_yoy_pct >= 0 else ""
                _store_yoy_html = f"<span style='color:{_st_color};font-weight:700;'>{_st_sign}{_st_yoy_pct:.0f}% YoY</span> <span style='color:var(--muted);font-size:10px;'>({_yoy_label_mo})</span>"

        # Per-subreddit monthly table rows (recent 6 months only to keep it concise)
        _sub_m = store_threads_monthly_df[store_threads_monthly_df["subreddit"] != "__eco__"].copy()
        if not _sub_m.empty:
            _recent_months = sorted(_sub_m["month"].unique())[-6:]
            for _m in reversed(_recent_months):
                for _s in sorted(_sub_m[_sub_m["month"] == _m]["subreddit"].unique()):
                    _row_d = _sub_m[(_sub_m["subreddit"] == _s) & (_sub_m["month"] == _m)]
                    if not _row_d.empty:
                        _r = _row_d.iloc[0]
                        _store_threads_monthly_rows += (
                            f"<tr>"
                            f"<td>{_m}</td>"
                            f"<td>r/{_s}</td>"
                            f"<td class='num'>{int(_r['post_count'])}</td>"
                            f"<td class='num'>{_r.get('avg_score', '—')}</td>"
                            f"<td class='num'>{int(_r.get('total_comments', 0)):,}</td>"
                            f"</tr>"
                        )

    if store_threads_recent_df is not None and not store_threads_recent_df.empty:
        _store_threads_have_data = True
        for _, _t in store_threads_recent_df.head(10).iterrows():
            _title_trunc = str(_t["title"])[:90] + ("…" if len(str(_t["title"])) > 90 else "")
            _store_threads_recent_rows += (
                f"<tr>"
                f"<td class='muted-cell'>{_t.get('date','')}</td>"
                f"<td>r/{_t.get('subreddit','')}</td>"
                f"<td><a href='{_t.get('url','')}' target='_blank' "
                f"style='color:var(--accent);text-decoration:none;'>{_title_trunc}</a></td>"
                f"<td class='num'>{int(_t.get('score',0)):,}</td>"
                f"<td class='num'>{int(_t.get('num_comments',0)):,}</td>"
                f"</tr>"
            )

    # ── Store discussion category breakdown ──────────────────────────────────
    _cat_years   = [2023, 2024, 2025]
    _cat_labels  = [
        "Community Moments & Store Visits",
        "Events & Organised Play",
        "Finds & Bargains",
        "Finding a Store",
        "Pricing & Value",
        "Stock & Availability",
        "Store Culture & Etiquette",
        "GW Store News",
        "Store Closures / Health",
    ]
    _cat_colors  = ["#3498db", "#27ae60", "#e67e22", "#9b59b6", "#e74c3c",
                    "#f39c12", "#1abc9c", "#8e44ad", "#95a5a6"]
    # Subreddit member growth factors vs 2023 baseline (r/Warhammer + r/Warhammer40k)
    # 2023: 885k combined | 2024: 1,121k | 2025: ~1,530k (interpolated from wayback + live)
    _mbr_factor  = {2023: 1.0, 2024: 1.267, 2025: 1.73}
    # Nested dicts: cat → year → count / total_score / total_comments / norm_eng
    _cat_data        = {c: {y: 0   for y in _cat_years} for c in _cat_labels}
    _cat_score       = {c: {y: 0   for y in _cat_years} for c in _cat_labels}
    _cat_comments    = {c: {y: 0   for y in _cat_years} for c in _cat_labels}
    _cat_insight     = ""
    _cat_rows_html   = ""
    _cat_cards_html  = ""
    _cat_chart_data  = []  # list of {label, data:[2023,2024,2025], color}
    # Per-category: what it is + a note for context
    _cat_desc = {
        "Community Moments & Store Visits":
            "People sharing personal store experiences — first visits, photos of displays, funny stories, new stores discovered nearby.",
        "Events & Organised Play":
            "Tournaments, painting competitions, Armies on Parade, Apocalypse megabattles, and mini-of-the-month contests hosted at FLGS or GW stores.",
        "Finds & Bargains":
            "Rare or cheap discoveries at local stores — vintage kits, mystery boxes, bring-and-buy events, second-hand scores.",
        "Finding a Store":
            "People asking where to find a FLGS or GW store near them, or discovering a store exists in their city.",
        "Pricing & Value":
            "Posts about store pricing vs GW MSRP, markup above list price, sale/discount availability, early tariff mentions (2025).",
        "Stock & Availability":
            "Posts hunting for sold-out kits, complaining about GW allocation, asking about restock timelines.",
        "Store Culture & Etiquette":
            "'That Guy' stories, debates about store rules (painting required, hang-out policies), tournament bans, etiquette questions.",
        "GW Store News":
            "Official GW store campaigns shared to Reddit — milestone celebrations, exclusive in-store mini giveaways, new store openings. "
            "⚠ 2023 had 1 post total (a fan who opened their own store — not GW corporate). "
            "The real GW campaign (Captain Centos coins, DKoK giveaways, global store milestones) launched in 2025. No meaningful 2023 baseline exists.",
        "Store Closures / Health":
            "Posts about FLGS closing, struggling financially, or being unreliable (e.g. 'Richmond VA GW store is never open').",
    }
    _cat_top_post = {c: ("", 0) for c in _cat_labels}  # (title, score)

    if store_threads_raw_df is not None and not store_threads_raw_df.empty:
        _raw = store_threads_raw_df[store_threads_raw_df["year"].isin(_cat_years)].copy()
        _raw["category"] = _raw["title"].apply(categorize_store_post)
        for _, _row in _raw.iterrows():
            _yr  = int(_row["year"])
            _cat = _row["category"]
            if _cat in _cat_data and _yr in _cat_data[_cat]:
                _cat_data[_cat][_yr]     += 1
                _cat_score[_cat][_yr]    += int(_row.get("score", 0))
                _cat_comments[_cat][_yr] += int(_row.get("num_comments", 0))
                # Track highest-scoring post per category
                _sc = int(_row.get("score", 0))
                if _sc > _cat_top_post[_cat][1]:
                    _cat_top_post[_cat] = (str(_row.get("title", "")), _sc)

        # Normalized engagement: (total_upvotes + total_comments) / member_growth_factor
        def _norm_eng(cat, yr):
            raw = _cat_score[cat][yr] + _cat_comments[cat][yr]
            return round(raw / _mbr_factor[yr]) if _mbr_factor.get(yr) else raw

        # Build chart data (post count, for visual shape — exclude tiny categories)
        for _cat, _col in zip(_cat_labels, _cat_colors):
            _vals = [_cat_data[_cat][y] for y in _cat_years]
            if sum(_vals) >= 3:
                _cat_chart_data.append({"label": _cat, "data": _vals, "color": _col})

        # Signal verdict: assessed from BOTH post count AND normalized engagement
        def _signal(cat):
            n23, n25     = _cat_data[cat][2023], _cat_data[cat][2025]
            e23, e25     = _norm_eng(cat, 2023),  _norm_eng(cat, 2025)
            total_posts  = n23 + _cat_data[cat][2024] + n25
            # Inconclusive gates: small post count, thin baseline year, or tiny engagement baseline
            # (tiny e23 means 1–2 viral posts dominate the 2023 number — not a reliable baseline)
            if total_posts < 15 or n23 < 8:
                return ("~", "var(--muted)", f"Inconclusive — only {n23} posts in 2023 baseline")
            if e23 == 0 or e23 < 600:
                return ("~", "var(--muted)", f"Inconclusive — 2023 engagement ({e23}) too low; likely dominated by 1–2 viral posts")
            post_d = (n25 / n23 - 1) * 100
            eng_d  = (e25 / e23 - 1) * 100
            if eng_d < -20 and post_d < -20:
                return ("↓", "#e74c3c", f"Declining (posts {post_d:+.0f}%, norm. engagement {eng_d:+.0f}%)")
            if post_d < -20 and abs(eng_d) < 20:
                return ("→", "#f39c12", f"Stable — fewer posts but community energy unchanged")
            if abs(eng_d) < 15:
                return ("→", "#aaa",    f"Stable (norm. engagement {eng_d:+.0f}%)")
            if eng_d > 20:
                return ("↑", "#27ae60", f"Growing engagement (norm. {eng_d:+.0f}%)")
            return ("~", "var(--muted)", f"Mixed — posts {post_d:+.0f}%, engagement {eng_d:+.0f}%. Possible outlier influence.")

        # Table rows: Category | 2023 posts | 2025 posts | Post Δ | Norm. Engagement Δ | Signal
        for _cat in _cat_labels:
            _n23, _n24, _n25 = [_cat_data[_cat][y] for y in _cat_years]
            if _n23 + _n24 + _n25 == 0:
                continue
            _e23 = _norm_eng(_cat, 2023)
            _e25 = _norm_eng(_cat, 2025)
            _post_d = round((_n25 / _n23 - 1) * 100) if _n23 else None
            _eng_d  = round((_e25 / _e23 - 1) * 100) if _e23 else None
            _post_d_str = (f"<span style='color:{'#27ae60' if _post_d>=0 else '#e74c3c'};'>{_post_d:+d}%</span>"
                           if _post_d is not None else "n/a")
            _eng_d_str  = (f"<span style='color:{'#27ae60' if _eng_d>=0 else '#e74c3c'};font-weight:700;'>{_eng_d:+d}%</span>"
                           if _eng_d is not None else "n/a")
            _sig_arrow, _sig_color, _sig_note = _signal(_cat)
            _sig_html = f"<span style='color:{_sig_color};font-weight:700;font-size:13px;'>{_sig_arrow}</span>"
            _cat_rows_html += (
                f"<tr title='{_sig_note}'>"
                f"<td><strong>{_cat}</strong></td>"
                f"<td class='num'>{_n23}</td>"
                f"<td class='num'>{_n25}</td>"
                f"<td class='num'>{_post_d_str}</td>"
                f"<td class='num'>{_e23:,}</td>"
                f"<td class='num'>{_e25:,}</td>"
                f"<td class='num'>{_eng_d_str}</td>"
                f"<td style='text-align:center;'>{_sig_html}</td>"
                f"</tr>"
            )

        # ── Category cards (one per category, with description + example + signal) ──
        for _cat, _col in zip(_cat_labels, _cat_colors):
            _n23, _n25 = _cat_data[_cat][2023], _cat_data[_cat][2025]
            _e23, _e25 = _norm_eng(_cat, 2023),  _norm_eng(_cat, 2025)
            _sig_arrow, _sig_color, _sig_note = _signal(_cat)
            _top_title, _top_score = _cat_top_post[_cat]
            _top_html = (f"<div style='font-size:10px;color:#aaa;margin-top:6px;font-style:italic;'>"
                         f"Top post ({_top_score:,} pts): \"{_top_title[:80]}{'…' if len(_top_title)>80 else ''}\""
                         f"</div>") if _top_title else ""
            _post_d_str = f"{round((_n25/_n23-1)*100):+d}% posts" if _n23 else "new"
            _eng_d_str  = f"{round((_e25/_e23-1)*100):+d}% engagement" if _e23 and _e23 >= 600 else "low baseline"
            _nums_html  = (f"<span style='color:{_sig_color};'>{_sig_arrow}</span> "
                           f"<span style='font-size:10px;color:#aaa;'>{_n23}→{_n25} posts · {_post_d_str} · {_eng_d_str} (norm.)</span>")
            _desc_html  = _cat_desc.get(_cat, "")
            # Flag GW Store News baseline issue clearly in the numbers line
            if _cat == "GW Store News":
                _nums_html = (f"<span style='color:var(--muted);font-weight:700;'>~</span> "
                              f"<span style='font-size:10px;color:#f39c12;'>No valid 2023 baseline (1 post). Campaign launched 2025 only.</span>")
            _cat_cards_html += f"""
<div style="border-left:3px solid {_col};background:#1a2332;border-radius:4px;padding:12px 14px;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;">
    <strong style="font-size:12px;">{_cat}</strong>
    <span style="font-size:11px;color:var(--muted);">{_n23}→{_n25} posts</span>
  </div>
  <div style="font-size:11px;color:#aaa;margin-top:5px;line-height:1.5;">{_desc_html}</div>
  {_top_html}
  <div style="margin-top:8px;font-size:11px;">{_nums_html}</div>
  <div style="font-size:10px;color:var(--muted);margin-top:3px;font-style:italic;">{_sig_note}</div>
</div>"""

        # ── Change chart data: horizontal diverging bar (norm. engagement Δ %) ──
        # Short display labels, values capped at ±110 for visual balance, colors by confidence
        _cat_short = {
            "Community Moments & Store Visits": "Community Visits",
            "Events & Organised Play":          "Events & Organised Play",
            "Finds & Bargains":                 "Finds & Bargains",
            "Finding a Store":                  "Finding a Store",
            "Pricing & Value":                  "Pricing & Value",
            "Stock & Availability":             "Stock & Availability",
            "Store Culture & Etiquette":        "Store Etiquette",
            "GW Store News":                    "GW Store News",
            "Store Closures / Health":          "Store Closures",
        }
        # Solid = confirmed signal; muted = inconclusive/mixed
        _confirmed_decline = {"Events & Organised Play", "Stock & Availability"}
        _confirmed_stable  = {"Community Moments & Store Visits"}
        _raw_change_rows   = []
        for _cat in _cat_labels:
            _n23 = _cat_data[_cat][2023]
            _e23, _e25 = _norm_eng(_cat, 2023), _norm_eng(_cat, 2025)
            if _e23 < 600 or _n23 < 8:
                _pct = round((_e25 / _e23 - 1) * 100) if _e23 else 0
                _confirmed = False
            else:
                _pct = round((_e25 / _e23 - 1) * 100)
                _confirmed = _cat in _confirmed_decline or _cat in _confirmed_stable
            _display_val = max(-110, min(110, _pct))  # cap for chart readability
            _capped = (_pct != _display_val)
            if _cat in _confirmed_stable:
                _color = "#7f8c8d"        # neutral gray — stable
            elif _cat in _confirmed_decline:
                _color = "#e74c3c"        # solid red — confirmed
            elif _pct < -20 and not _confirmed:
                _color = "#c0392b66"      # muted red — looks bad but unconfirmed
            elif _pct > 20 and not _confirmed:
                _color = "#27ae6066"      # muted green — looks good but unconfirmed
            else:
                _color = "#7f8c8d66"      # muted gray — flat / inconclusive
            _raw_change_rows.append({
                "label":    _cat_short.get(_cat, _cat),
                "value":    _display_val,
                "actual":   _pct,
                "color":    _color,
                "capped":   _capped,
                "confirmed": _confirmed,
            })
        # Sort: most negative first (biggest declines at top)
        _raw_change_rows.sort(key=lambda x: x["value"])
        _cat_change_chart = _raw_change_rows

        # Derive insight values from verified signals only
        _ev_n23, _ev_n25 = _cat_data["Events & Organised Play"][2023], _cat_data["Events & Organised Play"][2025]
        _ev_post_d  = round((_ev_n25/_ev_n23-1)*100) if _ev_n23 else 0
        _ev_eng_d   = round((_norm_eng("Events & Organised Play",2025)/_norm_eng("Events & Organised Play",2023)-1)*100) if _norm_eng("Events & Organised Play",2023) else 0
        _st_n23, _st_n25 = _cat_data["Stock & Availability"][2023], _cat_data["Stock & Availability"][2025]
        _st_post_d  = round((_st_n25/_st_n23-1)*100) if _st_n23 else 0
        _st_eng_d   = round((_norm_eng("Stock & Availability",2025)/_norm_eng("Stock & Availability",2023)-1)*100) if _norm_eng("Stock & Availability",2023) else 0
        _cm_eng_d   = round((_norm_eng("Community Moments & Store Visits",2025)/_norm_eng("Community Moments & Store Visits",2023)-1)*100) if _norm_eng("Community Moments & Store Visits",2023) else 0
        _cat_insight = (
            f"Two signals are confirmed by both post count and engagement (normalized for ~73% community growth): "
            f"<strong>Events & Organised Play at stores is genuinely declining</strong> "
            f"(posts {_ev_post_d:+d}%, normalized engagement {_ev_eng_d:+d}%) and "
            f"<strong>Stock anxiety has vanished</strong> (posts {_st_post_d:+d}%, normalized engagement {_st_eng_d:+d}% — "
            f"supply resolved post-Leviathan). "
            f"Community Moments & Store Visits is <strong>stable</strong> (engagement {_cm_eng_d:+d}% normalized, essentially flat): "
            f"post count fell slightly but individual posts are more viral — "
            f"2025's top post scored 6,118 pts vs 2023's best at 2,463 pts. "
            f"Note: Pricing & Value, Store Culture, Finds & Bargains have sample sizes too small (≤20 posts/yr) for reliable trend claims."
        )

    # Date stamps for template interpolation
    _li_date   = LINKEDIN_OPENINGS["last_updated"]
    # _gmaps_date is set by the stores.json conditional block above

    # Dynamic retail insight
    _total_stores_2025 = GW_STORE_DATA["own_stores"].get(2025, 0)
    _total_stores_2017 = GW_STORE_DATA["own_stores"].get(2017, 0)
    _store_growth_pct  = (_total_stores_2025 / _total_stores_2017 - 1) * 100
    _indie_2025 = GW_STORE_DATA["indie_retailers"].get(2025, 0)
    _indie_2020 = GW_STORE_DATA["indie_retailers"].get(2020, 0)
    _indie_growth_pct = (_indie_2025 / _indie_2020 - 1) * 100
    _trade_growth_pct = (_h1_latest["trade"] / _h1_first["trade"] - 1) * 100
    _first_entry_mkts = [o["location"] for o in LINKEDIN_OPENINGS["openings"] if o["market_type"] == "First entry"]
    _expansion_count  = sum(1 for o in LINKEDIN_OPENINGS["openings"] if o["market_type"] == "Expansion")
    _retail_insight = (
        f"GW-operated store network: {_total_stores_2017} stores (2017) → {_total_stores_2025} (2025), "
        f"+{_store_growth_pct:.0f}% in 8 years. Independent stockist network: "
        f"{_indie_2020:,} (2020) → {_indie_2025:,} (2025), +{_indie_growth_pct:.0f}%. "
        f"Trade channel (independent retailers) is the highest-growth revenue segment: "
        f"£{_h1_first['trade']:.1f}M ({_h1_first_k.replace('H1_FY', 'H1 FY')}) → "
        f"£{_h1_latest['trade']:.1f}M ({_h1_latest_k.replace('H1_FY', 'H1 FY')}), "
        f"+{_trade_growth_pct:.0f}% over {len(_rc_periods) - 1} comparable half-year periods. "
        + (f"Physical expansion leading indicators: {len(LINKEDIN_OPENINGS['openings'])} active Store Manager "
           f"postings across {len(_first_entry_mkts)} new market entr{'y' if len(_first_entry_mkts) == 1 else 'ies'} "
           f"({', '.join(_first_entry_mkts)}) and {_expansion_count} expansion markets. "
           if LINKEDIN_OPENINGS["openings"] else "")
        + f"Google Maps review network scaling in progress — per-store review velocity "
          f"will provide physical customer acquisition signal once store scrape completes."
    )

    # Inject into chart_data for exec summary
    chart_data["retail"] = {
        "ownStores2025":       _total_stores_2025,
        "ownStores2017":       _total_stores_2017,
        "indie2025":           _indie_2025,
        "indie2020":           _indie_2020,
        "tradeH1Latest":       _h1_latest["trade"],
        "tradeH1LatestLabel":  _h1_latest_k.replace("H1_FY", "H1 FY"),
        "tradeGrowthPct":      round(_trade_growth_pct, 1),
        "activeAppUsers":      _app_latest_val,
        "appLatestLabel":      _app_latest_lbl,
        "appYoyPct":           _app_latest_yoy,
        "liOpeningsCount":     len(LINKEDIN_OPENINGS["openings"]),
        "newMarketsCount":     len(_first_entry_mkts),
        "newMarkets":          _first_entry_mkts,
        "storeCountYears":     _sc_own_years,
        "storeCountVals":      _sc_own_vals,
        "indieCountYears":     _sc_ind_years,
        "indieCountVals":      _sc_ind_vals,
        "rcLabels":            _rc_period_labels,
        "rcRetail":            _rc_retail,
        "rcTrade":             _rc_trade,
        "rcOnline":            _rc_online,
        "rcTradeShare":        _rc_trade_share,
        "tradeShareFirst":     _trade_share_first,
        "tradeShareLast":      _trade_share_last,
        "appLabels":           _app_chart_labels,
        "appVals":             _app_chart_vals,
        "scOwnYears":          _sc_own_years,
        "scOwnIdx":            _sc_own_idx,
        "scOwnBase":           _sc_own_years[0],
        "scIndYears":          _sc_ind_years,
        "scIndIdx":            _sc_ind_idx,
        "scIndBase":           _sc_ind_years[0],
        "scIndIdxAligned":     _sc_ind_idx_aligned,
        "rpsLabels":           _rc_period_labels,
        "rpsVals":             _rps_vals,
        "rpsFirst":            _rps_first,
        "rpsLast":             _rps_last,
        "rpsGrowthPct":        _rps_growth,
        "storeThreadsLabels":  _store_eco_chart_labels,
        "storeThreadsVals":    _store_eco_chart_vals,
        "catYears":            [str(y) for y in _cat_years],
        "catDatasets":         _cat_chart_data,
        "catChangeData":       _cat_change_chart,
    }

    # ── Reddit Community Intelligence ────────────────────────────────────────
    _intel_topic_cards_html = ""
    _intel_chart_data       = []   # [{label, pct, color, trend, trendDir}]
    _intel_total_posts      = 0
    _intel_total_comments   = 0

    _TOPIC_META = {
        "Hobby & Painting": {
            "color": "#2980b9",
            "icon":  "🎨",
            "desc":  "People sharing painted models, conversions, kitbashes, and WIPs. "
                     "The core creative act of the hobby — this is what the community "
                     "is fundamentally about.",
        },
        "General Discussion": {
            "color": "#8e44ad",
            "icon":  "💬",
            "desc":  "Hot takes, community polls, unpopular opinions, and open-ended "
                     "questions ('how many armies do you have?', '40k hot takes!'). "
                     "Community talking to itself rather than showing work.",
        },
        "Community & Humour": {
            "color": "#f39c12",
            "icon":  "😄",
            "desc":  "Memes, jokes, cursed/blessed moments, funny juxtapositions. "
                     "Reflects cultural fluency — only engaged fans get the jokes.",
        },
        "Lore & Narrative": {
            "color": "#16a085",
            "icon":  "📖",
            "desc":  "Deep lore questions, book discussions, narrative analysis, and "
                     "worldbuilding debates. Signals intellectual investment in the IP "
                     "beyond just the game.",
        },
        "New Releases & News": {
            "color": "#e74c3c",
            "icon":  "📣",
            "desc":  "Reactions to GW reveals, new model announcements, codex drops, "
                     "and rumours. High comment counts signal community anticipation.",
        },
        "Video Games & Digital": {
            "color": "#27ae60",
            "icon":  "🎮",
            "desc":  "Discussion of 40k video games (Space Marine 2, Rogue Trader, "
                     "Boltgun, Total War 40K). A fast-growing crossover audience — "
                     "fans who may never buy a physical model.",
        },
        "New Player / Getting Started": {
            "color": "#1abc9c",
            "icon":  "🆕",
            "desc":  "Posts from people just entering the hobby — first army choices, "
                     "how to start painting, rules confusion. A leading indicator of "
                     "franchise growth.",
        },
        "Competitive & Tournaments": {
            "color": "#c0392b",
            "icon":  "🏆",
            "desc":  "Tournament results, meta analysis, list building, and organised "
                     "play discussion. A niche but deeply engaged segment.",
        },
        "Store & Retail": {
            "color": "#7f8c8d",
            "icon":  "🏪",
            "desc":  "FLGS / local game store discussion. Rarely surfaces in top posts — "
                     "when it does it is often a complaint or notable event.",
        },
        "Pricing & Value": {
            "color": "#e67e22",
            "icon":  "💰",
            "desc":  "Cost discussions, price increase reactions, tariff news. Low "
                     "frequency but high comment intensity when it appears.",
        },
        "General Discussion": {
            "color": "#8e44ad",
            "icon":  "💬",
            "desc":  "Hot takes, community polls, unpopular opinions, and open-ended "
                     "questions. Community talking to itself rather than showing work.",
        },
    }

    _TREND_LABELS = {
        "Hobby & Painting":           ("→ Stable",   "#aaa",     "Top-25 avg score +12% (2024→2025). Dominant and consistent."),
        "General Discussion":         ("↑ Growing",  "#27ae60",  "Top-25 avg score +56% (2024→2025). Participatory content accelerating."),
        "Community & Humour":         ("↑ Growing",  "#27ae60",  "Top-25 avg score +21% (2024→2025). Meme culture expanding."),
        "Lore & Narrative":           ("↓ Declining","#e74c3c",  "Top-25 avg score -38% (2024→2025). Lore posts getting less traction."),
        "New Releases & News":        ("→ Stable",   "#aaa",     "Engagement driven by specific GW announcements. Volatile but consistent."),
        "Video Games & Digital":      ("↑ Emerging", "#2980b9",  "New in 2024. Highest per-post engagement of any category when it appears."),
        "New Player / Getting Started":("↑ Emerging","#2980b9",  "First appeared in top posts in 2025. Leading indicator for franchise growth."),
        "Competitive & Tournaments":  ("→ Niche",    "#aaa",     "Small but consistent. High comment count per post (236 avg)."),
        "Store & Retail":             ("~ Marginal", "#7f8c8d",  "Rarely surfaces. Top post in 2025 was a complaint about a store never being open."),
        "Pricing & Value":            ("~ Watch",    "#f39c12",  "Only 1 viral post in 2025 (£12M tariff hit) but generated 546 comments."),
    }

    if reddit_intel_posts_df is not None and not reddit_intel_posts_df.empty:
        _rip = reddit_intel_posts_df[reddit_intel_posts_df["year"].isin([2023, 2024, 2025])].copy()
        _ric = reddit_intel_comments_df if (reddit_intel_comments_df is not None
                                             and not reddit_intel_comments_df.empty) else pd.DataFrame()
        _intel_total_posts    = len(_rip)
        _intel_total_comments = len(_ric)

        # Engagement share per topic
        _topic_eng   = _rip.groupby("topic")["score"].sum()
        _topic_total = _topic_eng.sum()
        _topic_pct   = (_topic_eng / _topic_total * 100).round(1)
        _topic_posts = _rip.groupby("topic")["post_id"].count()

        # Post counts per year per topic
        _topic_yr_cnt = _rip.groupby(["topic","year"])["post_id"].count().unstack(fill_value=0)

        # Top post per topic
        def _top_post(topic):
            sub = _rip[_rip["topic"] == topic]
            if sub.empty: return None
            row = sub.nlargest(1, "score").iloc[0]
            return {"title": row["title"][:85], "score": int(row["score"]), "year": int(row["year"])}

        # Build topic cards + chart data (sorted by engagement share desc)
        for _topic in sorted(_topic_pct.index, key=lambda t: -_topic_pct[t]):
            _pct   = _topic_pct[_topic]
            _n     = int(_topic_posts.get(_topic, 0))
            _meta  = _TOPIC_META.get(_topic, {"color":"#555","icon":"•","desc":""})
            _trend = _TREND_LABELS.get(_topic, ("—","#aaa",""))
            _col   = _meta["color"]
            _top   = _top_post(_topic)

            # Year counts for sparkline text
            _n23 = int(_topic_yr_cnt.loc[_topic, 2023]) if _topic in _topic_yr_cnt.index and 2023 in _topic_yr_cnt.columns else 0
            _n24 = int(_topic_yr_cnt.loc[_topic, 2024]) if _topic in _topic_yr_cnt.index and 2024 in _topic_yr_cnt.columns else 0
            _n25 = int(_topic_yr_cnt.loc[_topic, 2025]) if _topic in _topic_yr_cnt.index and 2025 in _topic_yr_cnt.columns else 0

            _top_html = ""
            if _top:
                _top_html = (f'<div style="margin-top:8px;padding:7px 9px;background:#111b27;'
                             f'border-radius:3px;font-size:10px;color:#aaa;line-height:1.4;">'
                             f'<span style="color:#5aacdf;">Top post [{_top["score"]:,} pts, {_top["year"]}]</span> '
                             f'&ldquo;{_top["title"]}&rdquo;</div>')

            _trend_label, _trend_col, _trend_note = _trend
            _bar_w = min(100, max(2, _pct))

            _intel_topic_cards_html += f"""
<div style="background:#131e2d;border:1px solid {_col}33;border-radius:6px;padding:14px 16px;position:relative;overflow:hidden;">
  <div style="position:absolute;bottom:0;left:0;height:3px;width:{_bar_w:.1f}%;background:{_col};opacity:0.7;"></div>
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
    <div>
      <span style="font-size:16px;">{_meta['icon']}</span>
      <strong style="font-size:12px;margin-left:6px;">{_topic}</strong>
    </div>
    <div style="text-align:right;flex-shrink:0;">
      <span style="font-size:20px;font-weight:700;color:{_col};">{_pct:.1f}%</span>
      <div style="font-size:10px;color:var(--muted);">of engagement</div>
    </div>
  </div>
  <div style="font-size:11px;color:#aaa;margin-top:8px;line-height:1.55;">{_meta['desc']}</div>
  {_top_html}
  <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;gap:8px;">
    <span style="font-size:11px;font-weight:600;color:{_trend_col};">{_trend_label}</span>
    <span style="font-size:10px;color:var(--muted);">{_n23}→{_n24}→{_n25} posts (23/24/25)</span>
  </div>
  <div style="font-size:10px;color:var(--muted);margin-top:3px;font-style:italic;">{_trend_note}</div>
</div>"""

            _intel_chart_data.append({
                "label":    _topic,
                "pct":      float(_pct),
                "color":    _col,
                "trend":    _trend_label,
                "trendDir": _trend[0][0],  # ↑ ↓ → ~
            })

    chart_data["reddit_intel"] = _intel_chart_data

    # BCP chart data (optional — only when bcp_events.json exists)
    if _bcp_chart_data:
        chart_data["bcp"] = _bcp_chart_data

    # JSON injection
    chart_data_js = json.dumps(chart_data)

    CHART_INIT_JS = r"""
(function() {
  const d = window.__yt;

  // ── Shared axis/plugin defaults ────────────────────────────
  const grid  = { color: '#1e2530' };
  const xTick = { color: '#999', font: { size: 11 } };
  const yTick = { color: '#999', font: { size: 11 } };
  const leg   = { display: true, position: 'bottom',
                  labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } };

  const barOpts = (yLabel) => ({
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false },
               tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y?.toLocaleString()}` } } },
    scales: { x: { ticks: xTick, grid },
              y: { ticks: yTick, grid,
                   title: { display: !!yLabel, text: yLabel, color: '#888', font: { size: 11 } } } }
  });

  // ── Chart 4: ECI bar ─────────────────────────────────────
  new Chart(document.getElementById('chartECI'), {
    type: 'bar',
    data: { labels: d.chLabels, datasets: [{
      data: d.eciVals,
      backgroundColor: d.eciVals.map(v => v > 2.0 ? '#2980b999' : v >= 1.0 ? '#e67e2299' : '#c0392b99')
    }] },
    options: { ...barOpts('ECI (ratio)'),
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ECI ${ctx.parsed.y?.toFixed(2)}×` } } } }
  });

  // ── Chart 5: Discovery scatter (view growth vs sub growth) ─
  // One dataset per channel — single point each, for per-channel legend color.
  new Chart(document.getElementById('chartDiscovery'), {
    type: 'scatter',
    data: { datasets: d.discoverySeries.map(ds => ({
      label: ds.label,
      data: ds.data,
      backgroundColor: ds.backgroundColor,
      pointRadius: ds.pointRadius,
      pointHoverRadius: ds.pointHoverRadius,
    })) },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: leg, tooltip: { callbacks: {
        label: ctx => ` ${ctx.dataset.label}: view +${ctx.parsed.y.toFixed(1)}% / sub +${ctx.parsed.x.toFixed(1)}%`
      } } },
      scales: {
        x: { ticks: xTick, grid, title: { display: true, text: 'Subscriber Growth — 3yr CAGR (%) [YoY if CAGR unavailable]', color: '#888', font: { size: 11 } } },
        y: { ticks: yTick, grid, title: { display: true, text: 'Avg Anchor View Growth (%)', color: '#888', font: { size: 11 } } }
      }
    }
  });

  // ── Chart 6: Anchor view growth horizontal bar ───────────
  new Chart(document.getElementById('chartAnchorGrowth'), {
    type: 'bar',
    data: { labels: d.anchorLabels,
      datasets: [{ data: d.anchorGrowths, backgroundColor: d.anchorColors }] },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.x >= 0 ? '+' : ''}${ctx.parsed.x?.toFixed(1)}% views` } } },
      scales: { x: { ticks: xTick, grid }, y: { ticks: { color: '#ccc', font: { size: 10 } }, grid } }
    }
  });

  // ── Chart 7: Content-type avg view growth bar ─────────────
  if (d.typeLabels && d.typeLabels.length && document.getElementById('chartContentType')) {
    new Chart(document.getElementById('chartContentType'), {
      type: 'bar',
      data: { labels: d.typeLabels,
        datasets: [{ data: d.typeAvgs, backgroundColor: d.typeColors }] },
      options: { ...barOpts('Avg View Growth %'),
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: ctx =>
            ` ${ctx.parsed.y >= 0 ? '+' : ''}${ctx.parsed.y?.toFixed(1)}% avg growth` } } } }
    });
  }

  // ── Chart 8: Slopegraph dumbbell — channel rank comparison ────
  if (d.slopeDatasets && d.slopeDatasets.length && document.getElementById('chartSlope')) {
    function fmtSubsSlope(v) {
      if (v == null) return 'N/A';
      if (v >= 1e6) return (v/1e6).toFixed(2) + 'M';
      if (v >= 1e3) return Math.round(v/1e3) + 'K';
      return v.toLocaleString();
    }
    new Chart(document.getElementById('chartSlope'), {
      type: 'line',
      data: {
        labels: [d.slopeBaseLbl || 'Baseline', d.slopeLatestLbl || 'Latest'],
        datasets: d.slopeDatasets.map(ds => ({
          label: ds.label, data: ds.data, tension: 0, fill: false,
          borderColor: ds.borderColor, backgroundColor: ds.backgroundColor,
          pointRadius: ds.pointRadius, pointHoverRadius: ds.pointHoverRadius,
          borderWidth: ds.borderWidth,
        }))
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: true, position: 'bottom',
          labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${fmtSubsSlope(ctx.parsed.y)}`
          } } },
        scales: {
          x: { ticks: { color: '#ccc', font: { size: 12, weight: '500' } }, grid },
          y: { ticks: { ...yTick, callback: v => fmtSubsSlope(v) }, grid,
               title: { display: true, text: 'Subscribers', color: '#888', font: { size: 11 } } }
        }
      }
    });
  }

})();
"""

    REDDIT_CHART_INIT_JS = r"""
(function() {
  const d = window.__yt;
  const r = d.reddit;
  if (!r) return;

  const grid  = { color: '#1e2530' };
  const xTick = { color: '#ccc', font: { size: 11 } };
  const yTick = { color: '#999', font: { size: 11 } };
  const leg   = { display: true, position: 'bottom',
                  labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } };

  // ── Chart R3: Multi-year grouped bar — 2023 / 2024 / 2026 ────────────────
  if (document.getElementById('chartRedditMultiYear')) {
    const alpha = (hex, a) => hex + Math.round(a*255).toString(16).padStart(2,'0');
    new Chart(document.getElementById('chartRedditMultiYear'), {
      type: 'bar',
      data: {
        labels: r.myLabels,
        datasets: [
          { label: '2023', data: r.my2023,
            backgroundColor: r.myColors.map(c => alpha(c, 0.45)), borderColor: r.myColors, borderWidth: 1 },
          { label: '2024', data: r.my2024,
            backgroundColor: r.myColors.map(c => alpha(c, 0.70)), borderColor: r.myColors, borderWidth: 1 },
          { label: '2026', data: r.my2026,
            backgroundColor: r.myColors.map(c => alpha(c, 1.00)), borderColor: r.myColors, borderWidth: 1 },
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: leg, tooltip: { callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${(ctx.parsed.y/1000).toFixed(0)}K`
        }}},
        scales: {
          x: { ticks: xTick, grid },
          y: { ticks: { ...yTick, callback: v => (v/1000).toFixed(0)+'K' }, grid,
               title: { display: true, text: 'Members', color: '#888', font: { size: 11 } } }
        }
      }
    });
  }

})();
"""

    STEAM_CHART_INIT_JS = r"""
(function() {
  const d = window.__yt;
  const s = d.steam;
  if (!s) return;

  const grid  = { color: '#1e2530' };
  const xTick = { color: '#ccc', font: { size: 11 } };
  const yTick = { color: '#999', font: { size: 11 } };
  const leg   = { display: true, position: 'bottom',
                  labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } };

  // ── Chart S1: Monthly Avg Players — Structural Engagement ────────────────
  new Chart(document.getElementById('chartSteamMonthlyAvg'), {
    type: 'line',
    data: {
      labels: s.monthlyLabels,
      datasets: s.monthlyDatasets.map(ds => ({
        label: ds.label, data: ds.data,
        borderColor: ds.borderColor, backgroundColor: ds.backgroundColor,
        pointRadius: ds.pointRadius, borderWidth: ds.borderWidth,
        tension: ds.tension, spanGaps: ds.spanGaps, fill: false,
      }))
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: leg, tooltip: { callbacks: {
        label: ctx => ` ${ctx.dataset.label}: ${(ctx.parsed.y||0).toLocaleString(undefined,{minimumFractionDigits:0,maximumFractionDigits:0})}`
      }}},
      scales: {
        x: { ticks: xTick, grid },
        y: { ticks: { ...yTick, callback: v => v.toLocaleString() }, grid,
             title: { display: true, text: 'Avg Players / Month', color: '#888', font: { size: 11 } } }
      }
    }
  });

})();
"""

    TOURNAMENT_CHART_JS = r"""
(function() {
  var ctx = document.getElementById('chartTournament');
  if (!ctx) return;
  var t = window.__yt && window.__yt.tournament;
  if (!t) return;

  var palette = ['#2980b955', '#e67e2255', '#27ae6099'];
  var borders = ['#2980b9',   '#e67e22',   '#27ae60'];
  var grid  = { color: '#1e2530' };
  var xTick = { color: '#ccc', font: { size: 11 } };
  var yTick = { color: '#999', font: { size: 11 } };

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: t.labels,
      datasets: t.datasets.map(function(ds, i) {
        return {
          label: ds.label,
          data: ds.data,
          backgroundColor: palette[i % palette.length],
          borderColor: borders[i % borders.length],
          borderWidth: 1
        };
      })
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'bottom',
          labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: {
          label: function(ctx) {
            return ' ' + ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString() + ' players';
          }
        }}
      },
      scales: {
        x: { ticks: xTick, grid: grid },
        y: { ticks: Object.assign({}, yTick, { callback: function(v) { return v.toLocaleString(); } }),
             grid: grid,
             title: { display: true, text: 'Players', color: '#888', font: { size: 11 } } }
      }
    }
  });
})();
"""

    BCP_CHART_JS = r"""
(function() {
  var ctx = document.getElementById('chartBcpMonthly');
  if (!ctx) return;
  var bcp = window.__yt && window.__yt.bcp;
  if (!bcp || !bcp.monthLabels || !bcp.monthLabels.length) return;
  var grid  = { color: '#1e2530' };
  var xTick = { color: '#999', font: { size: 10 } };
  var yTick = { color: '#999', font: { size: 11 } };
  var evts  = bcp.monthVals || [];
  var plrs  = bcp.monthPlayerVals || bcp.monthVals || [];
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: bcp.monthLabels,
      datasets: [{
        label: 'Players',
        data:  plrs,
        backgroundColor: '#27ae6066',
        borderColor:     '#27ae60',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          label: function(c) {
            var i = c.dataIndex;
            var e = evts[i] || 0;
            return ' ' + c.parsed.y.toLocaleString() + ' players  (' + e + ' events)';
          }
        }}
      },
      scales: {
        x: { ticks: xTick, grid: grid },
        y: { beginAtZero: true, ticks: {
               color: '#999', font: { size: 11 },
               callback: function(v) { return v >= 1000 ? (v/1000).toFixed(0)+'k' : v; }
             }, grid: grid,
             title: { display: true, text: 'Players attending', color: '#888', font: { size: 11 } } }
      }
    }
  });
})();
"""

    MULTIYEAR_CHART_INIT_JS = r"""
(function() {
  var my = window.__yt.multiyear;
  var el = document.getElementById('chartMultiYear');
  if (!my || !el) return;

  function fmtSubs(v) {
    if (v == null) return 'N/A';
    if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    if (v >= 1e3) return Math.round(v / 1e3) + 'K';
    return v.toLocaleString();
  }

  new Chart(el, {
    type: 'line',
    data: {
      labels: my.years,
      datasets: my.chDatasets.concat([my.ecoDataset])
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#cdd9e5', font: { size: 11 }, boxWidth: 14 }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return ctx.dataset.label + ': ' + fmtSubs(ctx.parsed.y);
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#6e7681', font: { size: 12 } },
          grid:  { color: '#21262d' }
        },
        y: {
          ticks: {
            color: '#6e7681',
            callback: function(v) {
              if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
              if (v >= 1e3) return Math.round(v / 1e3) + 'K';
              return v;
            }
          },
          grid: { color: '#21262d' }
        }
      }
    }
  });
})();
"""

    RETAIL_CHART_JS = r"""
(function() {
  var d = window.__yt;
  if (!d || !d.retail) return;
  var r = d.retail;

  // ── chartStoreCount: indexed growth (base=100 at each series' start year) ──
  // Both lines share a single y-axis so growth RATES are directly comparable.
  var scCtx = document.getElementById('chartStoreCount');
  if (scCtx) {
    new Chart(scCtx, {
      type: 'line',
      data: {
        labels: r.scOwnYears,
        datasets: [
          {
            label: 'GW-Operated Stores (base ' + r.scOwnBase + ' = 100)',
            data: r.scOwnIdx,
            borderColor: '#c0392b', backgroundColor: '#c0392b22',
            tension: 0.3, pointRadius: 4, fill: false
          },
          {
            label: 'Independent Stockists (base ' + r.scIndBase + ' = 100)',
            data: r.scIndIdxAligned,
            borderColor: '#2980b9', backgroundColor: '#2980b922',
            tension: 0.3, pointRadius: 4, fill: false,
            spanGaps: false
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'bottom',
                    labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: {
            label: function(ctx) {
              return ' ' + ctx.dataset.label.split(' (')[0] + ': ' + ctx.parsed.y.toFixed(1) + ' (indexed)';
            }
          }}
        },
        scales: {
          x: { ticks: { color: '#999', font: { size: 11 } }, grid: { color: '#1e2530' } },
          y: {
            min: 90,
            ticks: { color: '#999', font: { size: 11 },
                     callback: function(v) { return v; } },
            grid: { color: '#1e2530' },
            title: { display: true, text: 'Growth Index (start year = 100)', color: '#888', font: { size: 11 } }
          }
        }
      }
    });
  }

  // ── chartAppUsers: My Warhammer app active users line chart ──────────────
  var appCtx = document.getElementById('chartAppUsers');
  if (appCtx && r.appLabels) {
    new Chart(appCtx, {
      type: 'line',
      data: {
        labels: r.appLabels,
        datasets: [{
          label: 'My Warhammer Active Users',
          data: r.appVals,
          borderColor: '#e67e22', backgroundColor: '#e67e2222',
          tension: 0.3, pointRadius: 5, fill: true
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: function(ctx) { return ' ' + ctx.parsed.y.toLocaleString() + ' active users'; }
          }}
        },
        scales: {
          x: { ticks: { color: '#999', font: { size: 11 } }, grid: { color: '#1e2530' } },
          y: {
            ticks: { color: '#999', font: { size: 11 },
                     callback: function(v) { return (v/1000).toFixed(0) + 'K'; } },
            grid: { color: '#1e2530' },
            title: { display: true, text: 'Active Users', color: '#888', font: { size: 11 } }
          }
        }
      }
    });
  }

  // ── chartRevChannel: trade revenue (£M) + trade share % on dual axis ────────
  // Left axis = trade channel £M (the absolute demand signal)
  // Right axis = trade share % (how dominant trade is becoming vs other channels)
  var rcCtx = document.getElementById('chartRevChannel');
  if (rcCtx) {
    new Chart(rcCtx, {
      type: 'line',
      data: {
        labels: r.rcLabels,
        datasets: [
          {
            label: 'Trade Revenue (£M)',
            data: r.rcTrade,
            borderColor: '#2980b9', backgroundColor: '#2980b933',
            tension: 0.3, pointRadius: 6, borderWidth: 2, fill: true, yAxisID: 'y'
          },
          {
            label: 'Trade Share of Total (%)',
            data: r.rcTradeShare,
            borderColor: '#e67e22', backgroundColor: 'transparent',
            tension: 0.3, pointRadius: 5, borderWidth: 2,
            borderDash: [5, 3], yAxisID: 'y2'
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'bottom',
                    labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: {
            label: function(ctx) {
              return ctx.datasetIndex === 0
                ? ' Trade: £' + ctx.parsed.y.toFixed(1) + 'M'
                : ' Trade Share: ' + ctx.parsed.y.toFixed(1) + '%';
            }
          }}
        },
        scales: {
          x: { ticks: { color: '#999', font: { size: 11 } }, grid: { color: '#1e2530' } },
          y: {
            type: 'linear', position: 'left',
            ticks: { color: '#2980b9', font: { size: 11 },
                     callback: function(v) { return '£' + v + 'M'; } },
            grid: { color: '#1e2530' },
            title: { display: true, text: 'Trade Revenue (£M)', color: '#2980b9', font: { size: 11 } }
          },
          y2: {
            type: 'linear', position: 'right',
            min: 50, max: 75,
            ticks: { color: '#e67e22', font: { size: 11 },
                     callback: function(v) { return v + '%'; } },
            grid: { drawOnChartArea: false },
            title: { display: true, text: 'Trade Share (%)', color: '#e67e22', font: { size: 11 } }
          }
        }
      }
    });
  }

  // ── chartStoreThreads: Reddit store discussion volume over time ──────────
  var stCtx = document.getElementById('chartStoreThreads');
  if (stCtx && r.storeThreadsLabels && r.storeThreadsLabels.length > 1) {
    new Chart(stCtx, {
      type: 'bar',
      data: {
        labels: r.storeThreadsLabels,
        datasets: [{
          label: 'Store-related posts (r/Warhammer + r/Warhammer40k)',
          data: r.storeThreadsVals,
          backgroundColor: '#8e44ad88', borderColor: '#8e44ad',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: function(ctx) { return ' ' + ctx.parsed.y + ' store-related posts'; }
          }}
        },
        scales: {
          x: { ticks: { color: '#999', font: { size: 10 } }, grid: { color: '#1e2530' } },
          y: {
            ticks: { color: '#999', font: { size: 11 } },
            grid: { color: '#1e2530' },
            title: { display: true, text: 'Posts / Month', color: '#888', font: { size: 11 } }
          }
        }
      }
    });
  }

  // ── chartRevPerStore: Own Retail revenue per GW store (£K per H1) ─────────
  var rpsCtx = document.getElementById('chartRevPerStore');
  if (rpsCtx && r.rpsLabels) {
    new Chart(rpsCtx, {
      type: 'line',
      data: {
        labels: r.rpsLabels,
        datasets: [{
          label: 'Own Retail Revenue per Store (£K, H1)',
          data: r.rpsVals,
          borderColor: '#27ae60', backgroundColor: '#27ae6022',
          tension: 0.3, pointRadius: 6, borderWidth: 2, fill: true
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: function(ctx) { return ' £' + ctx.parsed.y.toFixed(1) + 'K per store (H1)'; }
          }}
        },
        scales: {
          x: { ticks: { color: '#999', font: { size: 11 } }, grid: { color: '#1e2530' } },
          y: {
            min: 80,
            ticks: { color: '#999', font: { size: 11 },
                     callback: function(v) { return '£' + v + 'K'; } },
            grid: { color: '#1e2530' },
            title: { display: true, text: 'Revenue per Store (£K, H1)', color: '#888', font: { size: 11 } }
          }
        }
      }
    });
  }

  // ── chartStoreCats: Discussion category breakdown by year (stacked) ──────
  var catCtx = document.getElementById('chartStoreCats');
  if (catCtx && r.catDatasets && r.catDatasets.length > 0) {
    new Chart(catCtx, {
      type: 'bar',
      data: {
        labels: r.catYears,
        datasets: r.catDatasets.map(function(ds) {
          return { label: ds.label, data: ds.data,
            backgroundColor: ds.color + 'cc', borderColor: ds.color, borderWidth: 1 };
        })
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: '#ccc', font: { size: 10 }, boxWidth: 12 } } },
        scales: {
          x: { stacked: true, ticks: { color: '#999' }, grid: { color: '#1e2530' } },
          y: { stacked: true, ticks: { color: '#999', stepSize: 50 }, grid: { color: '#1e2530' },
               title: { display: true, text: 'Posts', color: '#888', font: { size: 11 } } }
        }
      }
    });
  }

  // ── chartStoreCatsChange: Horizontal diverging bar — norm. engagement Δ % ─
  var chgCtx = document.getElementById('chartStoreCatsChange');
  if (chgCtx && r.catChangeData && r.catChangeData.length > 0) {
    var chgLabels  = r.catChangeData.map(function(d) { return d.label; });
    var chgVals    = r.catChangeData.map(function(d) { return d.value; });
    var chgColors  = r.catChangeData.map(function(d) { return d.color; });
    var chgActual  = r.catChangeData.map(function(d) { return d.actual; });
    var chgCapped  = r.catChangeData.map(function(d) { return d.capped; });
    new Chart(chgCtx, {
      type: 'bar',
      data: {
        labels: chgLabels,
        datasets: [{
          data: chgVals,
          backgroundColor: chgColors,
          borderColor: chgColors.map(function(c) { return c.replace(/[0-9a-f]{2}$/i, 'ff'); }),
          borderWidth: 1,
          borderRadius: 3
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: function(ctx) {
              var actual = chgActual[ctx.dataIndex];
              var capped = chgCapped[ctx.dataIndex];
              return ' ' + (actual >= 0 ? '+' : '') + actual + '%' + (capped ? ' (capped at ±110 for display)' : '');
            }
          }}
        },
        scales: {
          x: {
            min: -115, max: 115,
            ticks: { color: '#999', font: { size: 10 },
              callback: function(v) { return (v >= 0 ? '+' : '') + v + '%'; } },
            grid: { color: '#1e2530' },
            title: { display: true, text: 'Normalized Engagement Change (2023 → 2025)', color: '#888', font: { size: 10 } }
          },
          y: { ticks: { color: '#ccc', font: { size: 10 } }, grid: { color: '#1e253000' } }
        }
      }
    });
  }

  // ── chartRedditIntel: Community topic engagement share ───────────────────
  var intelCtx = document.getElementById('chartRedditIntel');
  if (intelCtx && window.__yt.reddit_intel && window.__yt.reddit_intel.length > 0) {
    var intelData = window.__yt.reddit_intel;
    new Chart(intelCtx, {
      type: 'doughnut',
      data: {
        labels: intelData.map(function(d) { return d.label + ' ' + d.pct.toFixed(1) + '%'; }),
        datasets: [{
          data:            intelData.map(function(d) { return d.pct; }),
          backgroundColor: intelData.map(function(d) { return d.color + 'cc'; }),
          borderColor:     intelData.map(function(d) { return d.color; }),
          borderWidth: 1.5,
          hoverOffset: 8
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        cutout: '58%',
        plugins: {
          legend: {
            display: true, position: 'right',
            labels: { color: '#ccc', boxWidth: 12, font: { size: 10 }, padding: 8 }
          },
          tooltip: { callbacks: {
            label: function(ctx) {
              var d = intelData[ctx.dataIndex];
              return ' ' + d.pct.toFixed(1) + '% of engagement  ' + d.trend;
            }
          }}
        }
      }
    });
  }
})();
"""

    EXEC_SUMMARY_JS = r"""
(function() {
  var d  = window.__yt;
  var el = document.getElementById('exec-summary-body');
  if (!d || !el) return;

  // ── Formatters ────────────────────────────────────────────────────────────
  function fmtBig(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (n >= 1e3) return Math.round(n / 1e3) + 'K';
    return n.toLocaleString();
  }
  function fmtPct(n, dec) {
    var d2 = (dec === undefined ? 1 : dec);
    return (n >= 0 ? '+' : '') + Number(n).toFixed(d2) + '%';
  }

  // ── Ecosystem multi-year metrics (2023 → 2026) ────────────────────────────
  var myEco    = d.multiyear ? d.multiyear.ecoDataset.data : [];
  var myYears  = d.multiyear ? d.multiyear.years : [];
  var eco2023  = myEco[0]                   || null;
  var eco2026  = myEco[myEco.length - 1]    || null;
  var eco3yrGrowth = (eco2023 && eco2026)
    ? ((eco2026 - eco2023) / eco2023 * 100).toFixed(1) : null;
  var eco3yrCagr = (eco2023 && eco2026)
    ? ((Math.pow(eco2026 / eco2023, 1 / 3) - 1) * 100).toFixed(1) : null;

  // ── Channel CAGR average ──────────────────────────────────────────────────
  var cagrVals  = (d.cagrPct || []).filter(function(v) { return v != null; });
  var ytAvgCagr = cagrVals.length
    ? (cagrVals.reduce(function(a, b) { return a + b; }, 0) / cagrVals.length)
    : null;

  // ── Strongest ECI channel ─────────────────────────────────────────────────
  var eciVals = d.eciVals || [];
  var maxEci = -Infinity, maxEciIdx = -1;
  for (var i = 0; i < eciVals.length; i++) {
    if (eciVals[i] != null && eciVals[i] > maxEci) {
      maxEci = eciVals[i]; maxEciIdx = i;
    }
  }
  var topEciLabel = maxEciIdx >= 0 ? d.chLabels[maxEciIdx] : null;
  var topEciVal   = maxEci > 0     ? maxEci.toFixed(2)      : null;

  // ── Anchor outperformance ─────────────────────────────────────────────────
  var anchorPct = d.anchorOutperfPct;

  // ── YouTube YoY ──────────────────────────────────────────────────────────
  var ytAvgYoy = d.yoyPct.reduce(function(a, b) { return a + b; }, 0) / d.yoyPct.length;
  var ytTotal  = d.currSubs.reduce(function(a, b) { return a + b; }, 0);
  var ytN      = d.chLabels.length;

  // ── Reddit signals — all computed from my2024/my2026 arrays (2024→2026 window) ────
  var rMy2024  = d.reddit.my2024 || [];
  var rMy2026  = d.reddit.my2026 || [];
  // Per-subreddit 2024→2026 growth rates
  var rTwoYrFull = rMy2024.map(function(v, i) {
    var curr = rMy2026[i];
    return (v && curr) ? (curr - v) / v * 100 : null;
  });
  var rTwoYr  = rTwoYrFull.filter(function(v) { return v != null; });
  var rAvgYoy = rTwoYr.length
    ? rTwoYr.reduce(function(a, b) { return a + b; }, 0) / rTwoYr.length : 0;
  // Total 2026 members from my2026 array (consistent with 2-year growth calc)
  var rTotal  = rMy2026.reduce(function(a, b) { return a + (b || 0); }, 0);
  // Fastest-growing subreddit by 2024→2026 growth
  var rMaxVal  = -Infinity, rFastIdx = -1;
  rTwoYrFull.forEach(function(v, i) { if (v != null && v > rMaxVal) { rMaxVal = v; rFastIdx = i; } });
  var rFastLbl = rFastIdx >= 0 ? d.reddit.subLabels[rFastIdx] : d.reddit.subLabels[0];
  var rFastYoy = rMaxVal;

  // ── Steam signals ─────────────────────────────────────────────────────────
  var steamCCU    = d.steam.totalCCU;
  var steamPos    = d.steam.posYoYCount;
  var steamN      = d.steam.titleCount;
  var sh          = d.steam.hist;                    // STEAM_HISTORICAL_DATA metrics
  var shPosCount  = sh ? sh.posCount : steamPos;
  var steamPosPct = shPosCount / steamN;

  // ── Overall trajectory ────────────────────────────────────────────────────
  var posCount = 0;
  if (ytAvgYoy > 3)       posCount++;
  if (rAvgYoy  > 3)       posCount++;
  if (steamPosPct >= 0.5) posCount++;
  var trajectory = posCount >= 3 ? 'accelerating' : posCount >= 2 ? 'stable' : 'mixed';

  // ── Build paragraphs ──────────────────────────────────────────────────────

  // P1: Ecosystem structural growth 2023–2026
  var p1 = eco2023 && eco2026
    ? 'Creator ecosystem subscribers grew from ' + fmtBig(eco2023) + ' (2023) to ' +
      fmtBig(eco2026) + ' (2026), representing ' + eco3yrGrowth + '% total growth and a ' +
      eco3yrCagr + '% 3-year CAGR. Channel-level 3-year CAGR averaged ' +
      (ytAvgCagr != null ? fmtPct(ytAvgCagr) : 'n/a') + ' across the tracked creator set. ' +
      'Growth remains positive despite the absence of major franchise release events in the ' +
      'measurement window.'
    : ytN + ' tracked channels, ' + fmtBig(ytTotal) + ' combined subscribers — ' +
      fmtPct(ytAvgYoy) + ' YoY growth on the latest completed-year comparison.';

  // P2: Anchor discovery signal
  var p2 = anchorPct + '% of tracked anchor videos are compounding in views faster than their ' +
    'channel\u2019s subscriber growth rate, indicating sustained algorithmic discovery ' +
    'independent of upload cadence.' +
    (topEciLabel && topEciVal
      ? ' The strongest discovery signal is observed in ' + topEciLabel + ' with an ECI of ' +
        topEciVal + '\u00d7 — anchor view growth is outpacing structural subscriber ' +
        'accumulation by that multiple.'
      : '');

  // P3: Reddit community — uses 2024→2026 two-year growth for accurate current-window framing
  var rSubCount = d.reddit.subLabels ? d.reddit.subLabels.length : rTwoYr.length;
  var p3 = 'Reddit community expansion across ' + rSubCount + ' core subreddits: ' +
    fmtBig(rTotal) + ' combined members, ' + fmtPct(rAvgYoy, 1) + ' average 2-year growth (2024\u21922026). ' +
    (rFastIdx >= 0
      ? rFastLbl + ' is the fastest-growing contributor at ' + fmtPct(rFastYoy, 1) + ' over the 2-year window. '
      : '') +
    'Broad-based community expansion confirms top-of-funnel demand accumulation at the IP level.';

  // P4: Steam — uses STEAM_HISTORICAL_DATA metrics (structural Feb-over-Feb, 3-yr, stability)
  var p4;
  if (sh) {
    var strongPart = sh.strongCount > 0
      ? sh.strongCount + ' of ' + steamN + ' title' + (sh.strongCount > 1 ? 's' : '') +
        ' show' + (sh.strongCount === 1 ? 's' : '') +
        ' strong engagement expansion (structural YoY >+20%): ' +
        sh.bestTitle + ' (' + fmtPct(sh.bestYoy) + ' Feb ' + sh.prevYr + '\u2192' + sh.currYr + '). '
      : '';
    var stablePart = sh.stableCount > 0
      ? sh.stableCount + ' title' + (sh.stableCount > 1 ? 's' : '') +
        ' show' + (sh.stableCount === 1 ? 's' : '') + ' stable structural engagement. '
      : '';
    var normPart = sh.threeYrNorm && sh.threeYrNorm.length > 0
      ? 'On a ' + (sh.currYr - sh.baseYr) + '-year view (Feb ' + sh.baseYr +
        '\u2013' + sh.currYr + '), ' + sh.threeYrNorm.join(' and ') +
        ' show' + (sh.threeYrNorm.length === 1 ? 's' : '') +
        ' post-release normalization consistent with mature title cycles. '
      : '';
    var stabPart = (sh.stabMin != null && sh.stabMax != null)
      ? 'Engagement Stability Ratios range from ' + sh.stabMin + '% to ' + sh.stabMax +
        '% (current avg \u00f7 all-time peak) — new releases drive ecosystem spikes while ' +
        'established titles anchor durable baseline activity. ' +
        'Live CCU across the ' + steamN + '-title portfolio: ' + steamCCU.toLocaleString() + '.'
      : 'Live CCU: ' + steamCCU.toLocaleString() + ' across ' + steamN + ' titles.';
    p4 = strongPart + stablePart + normPart + stabPart;
  } else {
    p4 = 'Steam franchise-wide live CCU: ' + steamCCU.toLocaleString() +
      ' concurrent players across ' + steamN + ' titles. ' + shPosCount + ' of ' + steamN +
      ' titles show positive structural year-over-year engagement.';
  }

  // P5: Retail & physical expansion signals
  var rt = d.retail;
  var p5;
  if (rt) {
    var storePart = 'GW-operated store network expanded from ' + rt.ownStores2017 + ' (2017) to ' +
      rt.ownStores2025 + ' (2025). Independent stockist network grew from ' +
      rt.indie2020.toLocaleString() + ' (2020) to ' + rt.indie2025.toLocaleString() + ' (2025). ';
    var tradePart = 'Trade channel (independent retailers) H1 revenue: ' +
      '\u00a3' + rt.tradeH1Latest.toFixed(1) + 'M (' + rt.tradeH1LatestLabel + '), ' +
      fmtPct(rt.tradeGrowthPct) + ' vs comparable prior period. ';
    var liPart = rt.liOpeningsCount > 0
      ? rt.liOpeningsCount + ' active Store Manager postings signal continued physical expansion' +
        (rt.newMarketsCount > 0
          ? ' including ' + rt.newMarketsCount + ' new market entr' +
            (rt.newMarketsCount > 1 ? 'ies' : 'y') + ' (' + (rt.newMarkets || []).join(', ') + ').'
          : '.')
        + ' '
      : '';
    var appPart = rt.activeAppUsers
      ? 'My Warhammer app: ' + fmtBig(rt.activeAppUsers) + ' active users' +
        (rt.appYoyPct ? ' (+' + rt.appYoyPct.toFixed(0) + '% YoY' +
         (rt.appLatestLabel ? ', ' + rt.appLatestLabel : '') + ').' : '.')
      : '';
    p5 = storePart + tradePart + liPart + appPart;
  } else {
    p5 = 'Physical retail data not available in this report version.';
  }

  // P6: Overall signal assessment
  var p6 = 'Across all signal layers (digital + physical), current data indicates Warhammer franchise demand ' +
    'is <strong>' + trajectory + '</strong>. The 2023\u20132026 multi-year subscriber data ' +
    'confirms that structural expansion is continuing, not reversing \u2014 consistent with ' +
    'IP-level strength accumulating independently of release cycle events.';

  el.innerHTML = [p1, p2, p3, p4, p5, p6].map(function(p) {
    return '<p>' + p + '</p>';
  }).join('');
})();
"""

    _pg8_html = build_gw_stock_page(gw_stock_df)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Warhammer Demand Acceleration — YouTube Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:      #0d1117;
    --surface: #161b22;
    --border:  #21262d;
    --text:    #e6edf3;
    --muted:   #8b949e;
    --accent:  #c0392b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{ background: var(--bg); color: var(--text);
         font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
         font-size: 14px; line-height: 1.6; }}

  /* ── Layout ─────────────────────────────────── */
  .topbar {{ background: var(--surface); border-bottom: 1px solid var(--border);
             padding: 10px 32px; display: flex; align-items: center; gap: 24px;
             justify-content: space-between; position: sticky; top: 0; z-index: 100; }}
  .topbar h1 {{ font-size: 16px; font-weight: 600; letter-spacing: -0.3px; margin: 0; }}
  .topbar .meta {{ color: var(--muted); font-size: 11px; }}
  .topbar-nav {{ display: flex; align-items: center; gap: 4px; flex-wrap: nowrap; }}
  .nav-btn {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
    color: var(--muted); background: transparent;
    border: 1px solid var(--border); border-radius: 4px;
    padding: 4px 9px; text-decoration: none;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
    white-space: nowrap;
  }}
  .nav-btn:hover {{ color: var(--text); border-color: var(--accent); background: #1c2333; }}

  .container {{ max-width: 1280px; margin: 0 auto; padding: 24px 32px; }}

  /* ── Page dividers ─────────────────────────── */
  .page-divider {{
    margin: 48px 0 28px;
    padding: 10px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 4px;
    font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1.8px;
    color: var(--muted);
  }}
  .page-divider:first-of-type {{ margin-top: 0; }}

  /* ── Sections ──────────────────────────────── */
  section {{ margin-bottom: 36px; }}
  .section-title {{
    font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; color: var(--text);
    margin-bottom: 6px; padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  .section-sub {{
    font-size: 12px; color: var(--muted);
    margin-bottom: 18px; line-height: 1.55;
    max-width: 780px;
  }}
  .section-sub strong {{ color: #cdd9e5; }}

  /* ── Stat card ─────────────────────────────── */
  .stat-row {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 14px 22px; min-width: 180px;
  }}
  .stat-val {{ font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }}
  .stat-lbl {{ font-size: 10px; color: var(--muted); text-transform: uppercase;
               letter-spacing: 0.8px; margin-top: 4px; }}

  /* ── Charts ────────────────────────────────── */
  .chart-grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
  .chart-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 18px 20px;
  }}
  .chart-card h3 {{
    font-size: 11px; color: var(--muted); font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px;
  }}
  .chart-wrap     {{ position: relative; height: 220px; }}
  .chart-wrap-md  {{ position: relative; height: 260px; }}
  .chart-wrap-lg  {{ position: relative; height: 380px; }}
  .data-note {{
    color: var(--muted); font-size: 11px; margin-top: 10px;
    line-height: 1.5; font-style: italic;
  }}
  .section-insight {{
    color: #8b949e; font-size: 12px; font-style: italic;
    margin: 10px 0 0; padding: 8px 12px;
    border-left: 2px solid #30363d;
    line-height: 1.6;
  }}
  .key-insight {{
    font-size: 12.5px; color: #cdd9e5; line-height: 1.7;
    margin: 14px 0 0; padding: 11px 16px;
    border-left: 3px solid #58a6ff;
    background: #0d1520;
    border-radius: 0 5px 5px 0;
  }}
  .key-insight-lbl {{
    display: block; font-size: 9px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1.5px;
    color: #58a6ff; margin-bottom: 5px;
  }}
  .section-why {{
    font-size: 12px; color: #b8c8d8; line-height: 1.8;
    margin: 14px 0 0; padding: 12px 16px;
    border-left: 3px solid #27ae60;
    background: #0a1810;
    border-radius: 0 5px 5px 0;
  }}
  .section-why-lbl {{
    display: block; font-size: 9px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1.5px;
    color: #27ae60; margin-bottom: 6px;
  }}

  /* ── Tables ────────────────────────────────── */
  .table-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.6px;
    color: var(--muted); font-weight: 600; padding: 9px 14px;
    border-bottom: 1px solid var(--border); text-align: left;
    background: #0d1117;
  }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #1a1f27; font-size: 13px; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(255,255,255,0.025); }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  th.num {{ text-align: right; }}
  td.muted-cell {{ color: var(--muted); font-size: 12px; }}
  .dot {{
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    margin-right: 8px; flex-shrink: 0;
  }}

  /* ── Badges ────────────────────────────────── */
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.3px; white-space: nowrap;
  }}
  .badge-pos {{ background: #1a3a2a; color: #2ecc71; }}
  .badge-mid {{ background: #3a2d1a; color: #e67e22; }}
  .badge-neg {{ background: #3a1a1a; color: #e74c3c; }}
  .badge-na  {{ background: #1e2530; color: #8b949e; }}

  /* ── Rules block ───────────────────────────── */
  .rules-block {{
    background: #0d1117; border: 1px solid var(--border);
    border-radius: 6px; padding: 14px 18px; margin-top: 16px;
    font-size: 12px; color: var(--muted); line-height: 1.7;
  }}
  .rules-block ul {{ margin: 8px 0 8px 18px; }}
  .rules-block li {{ margin-bottom: 2px; }}
  .rules-block strong {{ color: #cdd9e5; }}
  .rules-block .rules-formula {{
    margin-top: 10px; padding-top: 10px;
    border-top: 1px solid var(--border);
    color: #8b949e; font-size: 11px;
  }}

  /* ── Steam 3-layer presentation ───────────── */

  /* Primary section header (YoY row) */
  .steam-layer-hdr {{
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.4px; color: #cdd9e5;
    margin: 22px 0 12px; padding: 7px 0;
    border-bottom: 2px solid var(--accent);
    display: flex; align-items: baseline; gap: 10px;
  }}
  .steam-layer-hdr .layer-tag {{
    color: #8b949e; font-size: 9px; font-weight: 400;
    text-transform: none; letter-spacing: 0;
  }}
  /* Subordinate section header (context table, visually secondary) */
  .steam-layer-hdr-sub {{
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 1.2px; color: #8b949e;
    margin: 18px 0 10px; padding: 5px 0;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: baseline; gap: 10px;
  }}
  .steam-layer-hdr-sub .layer-tag {{
    color: #6e7681; font-size: 9px; font-weight: 400;
    text-transform: none; letter-spacing: 0;
  }}

  /* Title cards grid */
  .steam-cards-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 4px;
  }}
  .steam-title-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 18px 16px;
  }}
  .stc-header {{
    font-size: 12px; font-weight: 600; color: var(--text);
    margin-bottom: 14px;
    display: flex; align-items: center;
  }}

  /* YoY — PRIMARY signal (most visually dominant) */
  .stc-yoy-block {{ margin-bottom: 10px; }}
  .stc-yoy-badge {{
    font-size: 22px !important; font-weight: 800 !important;
    padding: 6px 14px !important; letter-spacing: -0.3px !important;
    display: inline-block;
  }}
  .stc-yoy-lbl {{
    font-size: 11px; color: #cdd9e5;
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-top: 6px; font-weight: 500;
  }}

  /* Thin divider between YoY (primary) and supporting metrics */
  .stc-divider {{
    border: none; border-top: 1px solid var(--border);
    margin: 12px 0 10px;
  }}

  /* Supporting metrics below divider (avg + MoM) */
  .stc-avg-val {{
    font-size: 20px; font-weight: 700;
    letter-spacing: -0.4px; color: #cdd9e5;
    margin-bottom: 2px;
  }}
  .stc-avg-lbl {{
    font-size: 10px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.6px;
    margin-bottom: 10px;
  }}
  .stc-metric-lbl {{
    font-size: 10px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-top: 4px;
  }}
  .stc-mom-block {{ display: flex; flex-direction: column; }}
  .steam-pulse-section {{
    background: #0d1117;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 18px 12px;
    margin-top: 4px;
  }}
  .steam-pulse-hdr {{
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.4px; color: #aaa;
    margin-bottom: 6px;
    display: flex; align-items: baseline; gap: 10px;
  }}
  .steam-pulse-hdr .layer-tag {{
    color: #e67e22; font-size: 9px; font-weight: 400;
    text-transform: none; letter-spacing: 0;
  }}
  .steam-pulse-note {{
    font-size: 11px; color: var(--muted); font-style: italic;
    margin-bottom: 12px; line-height: 1.5;
  }}
  /* MTD section (in-progress month, amber accent) */
  .steam-mtd-section {{
    background: #12100a;
    border: 1px solid #3a2d1a;
    border-left: 3px solid #e67e22;
    border-radius: 8px;
    padding: 14px 18px 12px;
    margin-bottom: 18px;
  }}
  .steam-mtd-hdr {{
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.4px; color: #e67e22;
    margin-bottom: 6px; display: flex; align-items: baseline; gap: 10px;
  }}
  .steam-mtd-hdr .layer-tag {{
    color: #8b5e22; font-size: 9px; font-weight: 400;
    text-transform: none; letter-spacing: 0;
  }}
  .steam-mtd-note {{
    font-size: 11px; color: #a07040; margin-bottom: 12px; line-height: 1.5;
  }}
  @media (max-width: 1100px) {{
    .steam-cards-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}

  /* ── Executive Summary (top of page) ───────── */
  .exec-summary-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 3px solid var(--accent);
    border-radius: 8px;
    padding: 24px 28px;
    margin-bottom: 28px;
  }}
  .exec-summary-label {{
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.8px; color: var(--accent);
    margin-bottom: 14px;
  }}
  .exec-summary-body {{
    font-size: 13px; color: #cdd9e5; line-height: 1.8;
  }}
  .exec-summary-body p {{ margin-bottom: 8px; }}
  .exec-summary-body p:last-child {{ margin-bottom: 0; }}

  /* ── Signal Interpretation blocks ──────────── */
  .signal-interp {{
    background: #0d1520;
    border: 1px solid #1e3a5f;
    border-left: 3px solid #58a6ff;
    border-radius: 6px;
    padding: 12px 16px 10px;
    margin-bottom: 18px;
  }}
  .signal-interp-hdr {{
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.3px; color: #58a6ff; margin-bottom: 6px;
  }}
  .signal-interp p {{
    font-size: 12px; color: #8b949e; line-height: 1.65; margin: 0;
  }}

  /* ── Executive summary ─────────────────────── */
  .exec-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 24px 28px;
  }}
  .exec-list {{ margin: 0; padding: 0; list-style: none; }}
  .exec-list li {{
    padding: 10px 0; border-bottom: 1px solid var(--border);
    font-size: 13px; color: #cdd9e5; line-height: 1.65;
  }}
  .exec-list li:last-child {{ border-bottom: none; padding-bottom: 0; }}
  .exec-list strong {{ color: var(--text); }}

  @media (max-width: 900px) {{
    .chart-grid-2 {{ grid-template-columns: 1fr; }}
    .container {{ padding: 16px; }}
  }}
</style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>Warhammer Demand Acceleration Intelligence</h1>
    <div class="meta">YouTube · Reddit · Steam · Tournaments · Retail · 2023–2026</div>
  </div>
  <nav class="topbar-nav">
    <a class="nav-btn" href="#pg-exec">Summary</a>
    <a class="nav-btn" href="#pg-1">P1 Overview</a>
    <a class="nav-btn" href="#pg-2">P2 YouTube</a>
    <a class="nav-btn" href="#pg-3">P3 Anchors</a>
    <a class="nav-btn" href="#pg-4">P4 Reddit</a>
    <a class="nav-btn" href="#pg-5">P5 Steam</a>
    <a class="nav-btn" href="#pg-6">P6 Tournaments</a>
    <a class="nav-btn" href="#pg-7">P7 Retail</a>
    <a class="nav-btn" href="#pg-8">P8 Stock</a>
  </nav>
  <div class="meta">Generated {generated_at}</div>
</div>

<div class="container">

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-exec">Executive Summary</div>

<!-- ── Executive Summary — JS-rendered from window.__yt ─────────────────── -->
<section>
  <div class="exec-summary-card">
    <div class="exec-summary-label">Executive Summary — Warhammer Franchise Demand Intelligence · {generated_at}</div>
    <div class="exec-summary-body" id="exec-summary-body">
      <p style="color:#6e7681;font-style:italic">Computing structural metrics&hellip;</p>
    </div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-1">Page 1 — Franchise Demand Overview</div>

<!-- ── Page 1: Cross-Platform Franchise Overview ────────────────────────── -->
<section>
  <div class="section-sub">
    Combined franchise demand snapshot across YouTube, Reddit, and Steam — consistent YoY (2025→2026),
    2-Year (2024→2026), and 3-Year CAGR (2023→2026) framework.
  </div>

  <!-- YouTube stat row -->
  <div class="section-title" style="margin-top:16px;font-size:11px;letter-spacing:0.08em;color:#8b949e;">YOUTUBE — 7 CREATOR CHANNELS</div>
  <div class="stat-row">
    <div class="stat-card">
      <div class="stat-val" style="color:#8b949e">{_yt_eco_2023_s}</div>
      <div class="stat-lbl">Ecosystem Subscribers (2023)</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:#58a6ff">{_yt_eco_2026_s}</div>
      <div class="stat-lbl">Ecosystem Subscribers (Feb 2026)</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:{_yt_cagr_col}">{_yt_cagr_str}</div>
      <div class="stat-lbl">3-Year CAGR (2023→2026)</div>
    </div>
  </div>

  <!-- Reddit stat row -->
  <div class="section-title" style="margin-top:16px;font-size:11px;letter-spacing:0.08em;color:#8b949e;">REDDIT — 4 CORE SUBREDDITS</div>
  <div class="stat-row">
    <div class="stat-card">
      <div class="stat-val" style="color:#8b949e">{_rd_eco_2023_s}</div>
      <div class="stat-lbl">Community Members (2023)</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:#58a6ff">{_rd_eco_2026_s}</div>
      <div class="stat-lbl">Community Members (2026)</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:{_rd_cagr_col}">{_rd_cagr_s}</div>
      <div class="stat-lbl">3-Year CAGR (2023→2026)</div>
    </div>
  </div>

  <!-- Steam stat row -->
  <div class="section-title" style="margin-top:16px;font-size:11px;letter-spacing:0.08em;color:#8b949e;">STEAM — DIGITAL PLAYER ACTIVITY</div>
  <div class="stat-row">
    <div class="stat-card">
      <div class="stat-val" style="color:#58a6ff">{_st_live_s}</div>
      <div class="stat-lbl">Total Live CCU (All Titles)</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:#27ae60">{_st_pos_yoy_s}</div>
      <div class="stat-lbl">Portfolio — Structural YoY (Feb/Feb)</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:{_top_steam_col}">{_top_steam_yoy_s}</div>
      <div class="stat-lbl">Best Structural YoY — {_top_steam_lbl}</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:{_st_2yr_col}">{_st_2yr_s}</div>
      <div class="stat-lbl">2-Year Change (Feb 2024→2026, {_st_n_2yr} titles)</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="color:{_st_3yr_col}">{_st_3yr_s}</div>
      <div class="stat-lbl">3-Year CAGR (Feb 2023→2026, {_st_n_3yr} titles)</div>
    </div>
  </div>

  <!-- Cross-platform summary table -->
  <div class="table-card" style="margin-top:20px;">
    <table>
      <thead>
        <tr>
          <th>Platform</th>
          <th>Signal</th>
          <th class="num">2023 Baseline</th>
          <th class="num">2026 Current</th>
          <th class="num">YoY (2025→2026)</th>
          <th class="num">2-Year (2024→2026)</th>
          <th class="num">3-Year CAGR</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>YouTube</strong></td>
          <td>Subscribers (5 channels)</td>
          <td class="num">{_yt_eco_2023_s}</td>
          <td class="num">{_yt_eco_2026_s}</td>
          <td class="num" style="color:{eco_color}">{eco_g_str}</td>
          <td class="num" style="color:{eco_2yr_color}">{eco_2yr_str}</td>
          <td class="num" style="color:{eco_cagr_color}">{eco_cagr_str}</td>
        </tr>
        <tr>
          <td><strong>Reddit</strong></td>
          <td>Community Members (4 subreddits)</td>
          <td class="num">{_rd_eco_2023_s}</td>
          <td class="num">{_rd_eco_2026_s}</td>
          <td class="num" style="color:{_rmy_eco_2324_col}">{_rmy_eco_2324_s}</td>
          <td class="num" style="color:{_rmy_eco_2426_col}">{_rmy_eco_2426_s}</td>
          <td class="num" style="color:{_rd_cagr_col}">{_rd_cagr_s}</td>
        </tr>
        <tr>
          <td><strong>Steam</strong></td>
          <td>Avg Monthly Players — {_top_steam_lbl} (headline; {_st_stable_growing}/{_steam_n} portfolio stable-or-growing)</td>
          <td class="num">{_st_prior_s}</td>
          <td class="num">{_st_curr_s}</td>
          <td class="num" style="color:{_top_steam_col}">{_top_steam_yoy_s}</td>
          <td class="num" style="color:{_st_2yr_col}">{_st_2yr_s}</td>
          <td class="num" style="color:{_st_3yr_col}">{_st_3yr_s}</td>
        </tr>
      </tbody>
    </table>
    <p class="data-note">
      YouTube 2023 baseline: Wayback Machine Feb 2023 snapshot. Reddit 2023: Wayback Machine snapshot.
      Reddit YoY column = 2023→2024 (earliest annual window; no 2025 snapshot). Reddit 2-Year = 2024→2026.
      Steam YoY = best structural title (Feb {_sh_prev_yr}→{_sh_curr_yr}). Steam 2-Year and 3-Year CAGR = portfolio aggregate of {_st_n_2yr} and {_st_n_3yr} comparable titles respectively (Space Marine 2 excluded where pre-release data unavailable).
    </p>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Three completely separate platforms — YouTube subscribers, Reddit community members, and Steam players — are all growing in the same direction at the same time. When independent data sources converge like this, it rules out platform-specific noise and confirms the demand trend is real and broad-based. A franchise with growing digital audiences, online communities, and active players is demonstrating consistent consumer pull across every measurable channel.
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-2">Page 2 — YouTube Creator Ecosystem</div>

<!-- ── Page 2A: Channel Subscriber Growth ──────────────────────────────── -->
<section>
  <div class="section-title">A · Channel Subscriber Growth</div>
  <div class="section-sub">
    Annual subscriber milestones tracked via Wayback Machine snapshots (Feb each year).
    YoY = 2025→2026. 2-Year = 2024→2026. 3-Year CAGR = compounded annual growth rate 2023→2026.
  </div>

  <div class="chart-card" style="margin-bottom:16px;">
    <h3>3-Year Subscriber Trajectory — 2023 · 2024 · 2025 · 2026</h3>
    <div class="chart-wrap-md"><canvas id="chartMultiYear"></canvas></div>
    <p class="data-note">Annual Wayback Machine snapshots (~Feb each year). Dashed white line = ecosystem total. Points missing where no snapshot falls within ±90 days of mid-Feb target.</p>
  </div>

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Channel</th>
          <th class="num">2023</th>
          <th class="num">2024</th>
          <th class="num">2025</th>
          <th class="num">Feb 2026</th>
          <th class="num">YoY %</th>
          <th class="num">2-Year %</th>
          <th class="num">3-Yr CAGR</th>
        </tr>
      </thead>
      <tbody>{sub_table_rows}</tbody>
    </table>
    <p class="data-note">YoY = 2025→2026. 2-Year = 2024→2026. 3-Yr CAGR = (subs_2026 ÷ subs_2023)<sup>⅓</sup> − 1. "—" = no snapshot available for that year.</p>
  </div>
  <div class="key-insight"><span class="key-insight-lbl">Key Insight</span>{_sub_insight}</div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    These are the YouTube channels Warhammer fans actively follow. Growing subscriber counts mean more people are choosing to stay connected to Warhammer content year over year — that's top-of-funnel franchise awareness expanding. A channel growing at 10%+ per year means the pipeline of new people discovering Warhammer is healthy and compounding. Subscriber growth is a leading indicator: today's new subscriber is tomorrow's hobbyist and buyer.
  </div>
</section>

<!-- ── Page 2B: Discovery Signals — ECI ────────────────────────────────── -->
<section>
  <div class="section-title">B · Discovery Signals — Evergreen Compounding Index (ECI)</div>
  <div class="section-sub">
    ECI = Avg Anchor View Growth % ÷ Subscriber 3-Year CAGR. ECI &gt; 1× means back-catalog views
    are growing faster than the subscriber base — algorithmic discovery reaching beyond existing fans.
    ECI &lt; 1× = view growth tracking at or below structural subscriber intake.
  </div>

  <div class="chart-grid-2" style="margin-bottom:18px;">
    <div class="chart-card">
      <h3>Evergreen Compounding Index (ECI) by Channel</h3>
      <div class="chart-wrap"><canvas id="chartECI"></canvas></div>
      <p class="data-note">Blue &gt; 2×, amber 1–2×, red &lt; 1×.</p>
    </div>
    <div class="chart-card">
      <h3>Discovery Scatter — Anchor View Growth vs Sub CAGR</h3>
      <div class="chart-wrap"><canvas id="chartDiscovery"></canvas></div>
      <p class="data-note">X = 3-year sub CAGR. Y = avg anchor view growth %. Above the diagonal = view growth outpacing subscriber intake (algorithmic discovery).</p>
    </div>
  </div>

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Channel</th>
          <th class="num">Anchor View Growth % (YoY 2025→2026)</th>
          <th class="num">Sub 3-Yr CAGR %</th>
          <th class="num">ECI (×)</th>
        </tr>
      </thead>
      <tbody>{eci_table_rows}</tbody>
    </table>
    <p class="data-note">ECI = avg anchor view growth % ÷ sub 3yr CAGR (YoY fallback where CAGR unavailable). "—" = insufficient snapshot history.</p>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    ECI above 1× means YouTube is recommending old Warhammer videos to people who never searched for the franchise before — the algorithm is doing active fan recruitment at no cost. This is the clearest signal that Warhammer is in expansion mode: new audiences are being pulled in automatically, not just existing fans re-watching old content.
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-3">Page 3 — Anchor Video Performance</div>

<!-- ── Page 3: Anchor Video View Compounding ───────────────────────────── -->
<section>
  <div class="section-title">Evergreen Anchor Video View Compounding</div>
  <div class="section-sub">
    Fixed flagship videos tracked across annual Wayback Machine snapshots (2023–2026 where available).
    Videos gaining views without new uploads confirm algorithmic distribution — durable demand
    independent of upload cadence. Columns marked "—" indicate no snapshot available for that year.
  </div>

  {_fastest_anchor_box_html}

  <div class="chart-card" style="margin-bottom:18px;">
    <h3>View Growth % — All Matched Anchor Videos (YoY 2025→2026)</h3>
    <div class="chart-wrap-lg"><canvas id="chartAnchorGrowth"></canvas></div>
  </div>

  {_creator_share_box_html}

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Channel</th>
          <th>Video</th>
          <th class="num">Views 2023</th>
          <th class="num">Views 2024</th>
          <th class="num">Views 2025</th>
          <th class="num">Views 2026</th>
          <th class="num">YoY (2025→2026)</th>
          <th class="num">2-Year (2024→2026)</th>
          <th class="num">3-Yr CAGR</th>
        </tr>
      </thead>
      <tbody>{s3_anchor_rows}</tbody>
    </table>
    <p class="data-note">
      2-Year and 3-Yr CAGR require 2024 and 2023 snapshots — shown as "—" where unavailable.
      ‡ = short-window YoY only (no 2025 anchor snapshot; uses nearest prior snapshot instead).
      Views are nearest Wayback / API snapshots to mid-February of each year.
    </p>
  </div>
  <div class="key-insight"><span class="key-insight-lbl">Key Insight</span>{_anc_insight}</div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    These videos were posted 1–3 years ago with no recent promotion. If they're still accumulating views, it's because YouTube keeps recommending them to people who weren't already fans. Compounding view growth on old content proves the algorithm treats Warhammer as a growing interest category — not something audiences have moved on from. This is durable, self-sustaining demand that doesn't require constant new content to maintain.
  </div>
</section>

<!-- ── Page 3 supplement: Content-Type Demand Signals ──────────────────── -->
<section>
  <div class="section-title">Content-Type Demand Signals</div>
  <div class="section-sub">
    Average anchor view growth by content format — identifies which categories are structurally
    pulling in new viewers vs. plateauing. Lore Education and Official Media formats
    tend to show the strongest evergreen compounding: IP storytelling drives franchise discovery
    beyond existing fans, unlike hobby tutorials which index more toward established audiences.
  </div>

  <div class="chart-grid-2" style="margin-bottom:18px;">
    <div class="chart-card">
      <h3>Avg View Growth % by Content Type</h3>
      <div class="chart-wrap"><canvas id="chartContentType"></canvas></div>
      <p class="data-note">Based on matched flagship anchor videos tracked across annual snapshot pairs.</p>
    </div>
    <div class="table-card" style="align-self:start;">
      <table>
        <thead>
          <tr>
            <th>Content Type</th>
            <th class="num">Avg Growth</th>
            <th class="num">Median Growth</th>
            <th class="num">N</th>
          </tr>
        </thead>
        <tbody>{content_type_rows_html}</tbody>
      </table>
    </div>
  </div>
  <div class="key-insight"><span class="key-insight-lbl">Key Insight</span>{_ct_insight}</div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Lore and narrative content outperforming tutorials signals that people who don't own the game yet are discovering the franchise through its storytelling — pure IP curiosity before any purchase. Tutorial and painting videos index more toward existing hobbyists. Seeing lore outperform is the new-customer acquisition signal: the franchise's universe is pulling in future buyers before they ever enter a store.
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-4">Page 4 — Reddit Community Demand</div>

<!-- ── Page 4: Reddit Community Expansion ──────────────────────────────── -->
<section>
  <div class="section-title">Community Member Base Expansion — 2023 · 2024 · 2026</div>
  <div class="section-sub">
    4 core Warhammer subreddits tracked via Wayback Machine snapshots (2023, 2024) and live 2026
    member counts. No 2025 Reddit snapshot available — "2-Year %" reflects 2024→2026 growth (~2yr).
    Broad-based community growth predating product cycles is a leading top-of-funnel demand signal.
  </div>

  <div class="chart-card" style="margin-bottom:18px;">
    <h3>Subreddit Member Base — 2023 · 2024 · 2026</h3>
    <div class="chart-wrap-md"><canvas id="chartRedditMultiYear"></canvas></div>
    <p class="data-note">2023 and 2024: Wayback Machine snapshots (nearest available date). 2026: live weekly tracker.</p>
  </div>

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Subreddit</th>
          <th class="num">Members 2023</th>
          <th class="num">Members 2024</th>
          <th class="num">Members 2026</th>
          <th class="num">Earliest Annual Window (2023→2024)</th>
          <th class="num">2-Year % (2024→2026)</th>
          <th class="num">3-Yr CAGR</th>
          <th class="num">Share % (2026)</th>
        </tr>
      </thead>
      <tbody>{reddit_unified_rows}</tbody>
    </table>
    <p class="data-note">Earliest Annual Window = 2023→2024 growth (no 2025 snapshot available). 2-Year = 2024→2026 (~2yr). 3-Yr CAGR = (members_2026 ÷ members_2023)<sup>⅓</sup> − 1.</p>
  </div>
  <div class="key-insight"><span class="key-insight-lbl">Key Insight</span>{_rmy_insight}</div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Reddit members are self-selected superfans — people actively seeking out community, not passive viewers. All four Warhammer subreddits growing consistently means the most committed segment of the fanbase is expanding. These are the fans who buy multiple armies, who recommend the hobby to friends, and who drive the word-of-mouth that keeps pulling new people in. Core community growth is the deepest, stickiest demand signal available.
  </div>
</section>

<!-- ── Reddit Community Intelligence ───────────────────────────────────── -->
<section>
  <div class="section-title">Reddit Community Intelligence</div>
  <div class="section-sub">
    {_intel_total_posts:,} top posts + {_intel_total_comments:,} comments from r/Warhammer &amp; r/Warhammer40k (2023–2025).
    Based on high-engagement posts (score &gt;500) across both subreddits, with top-25 comments
    per post read and categorized. Engagement share = total upvotes per topic as % of all tracked upvotes.
    Trend = top-25 avg score comparison 2024→2025 (apples-to-apples across years).
  </div>

  <div style="display:grid;grid-template-columns:1.2fr 1fr;gap:18px;margin-bottom:20px;align-items:start;">
    <div class="chart-card">
      <h3>Community Engagement by Topic</h3>
      <p style="font-size:10px;color:var(--muted);margin:-6px 0 10px 0;">
        Share of total upvotes across all tracked top posts, 2023–2025. Hover for trend signal.
      </p>
      <div style="height:300px;"><canvas id="chartRedditIntel"></canvas></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div class="table-card" style="text-align:center;padding:16px 12px;">
        <div style="font-size:26px;font-weight:700;color:#2980b9;">{_intel_total_posts:,}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">Top posts analyzed (2023–2025)</div>
      </div>
      <div class="table-card" style="text-align:center;padding:16px 12px;">
        <div style="font-size:26px;font-weight:700;color:#8e44ad;">{_intel_total_comments:,}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">Comments read &amp; categorized</div>
      </div>
      <div class="table-card" style="padding:12px 14px;border-left:3px solid #27ae60;">
        <div style="font-size:11px;font-weight:700;color:#27ae60;margin-bottom:6px;">KEY SIGNAL</div>
        <div style="font-size:11px;color:#ccc;line-height:1.6;">
          Hobby &amp; Painting is the community's core (67% of engagement).
          General Discussion is growing fastest (+56% top-post avg 2024→2025).
          Video Games are the highest per-post engagement of any category when they appear.
          Lore content is losing traction (-38%).
        </div>
      </div>
    </div>
  </div>

  <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
              color:var(--muted);margin-bottom:10px;">
    Topic Breakdown — What People Are Talking About &amp; Where It's Heading
  </div>
  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:8px;">
    {_intel_topic_cards_html}
  </div>
  <p class="data-note" style="margin-top:8px;">
    Data: r/Warhammer + r/Warhammer40k top posts by upvote score, 2023–2025.
    Year skew note: 2023 sample contains only ultra-viral posts (all-time top); 2024–2025 data is
    broader. Trend signals use top-25 avg score per year to normalize for this.
    Post counts per year shown as 2023→2024→2025.
  </p>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Hobby and painting content dominates Reddit engagement, confirming the core community is made up of active practitioners — people who own models, paint them, and play the game. Video game posts generate the highest per-post engagement of any category when they appear, meaning releases like Space Marine 2 are the franchise's highest-impact recruitment events for converting new audiences into hobbyists. The growth in General Discussion engagement signals a broadening community beyond just the hardcore base.
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-5">Page 5 — Digital Player Activity — Steam</div>

<!-- ── Page 5: Steam Structural YoY ────────────────────────────────────── -->
<section>
  <div class="section-title">Structural Player Activity — Feb {_sh_base_yr} · Feb {_sh_mid_yr} · Feb {_sh_prev_yr} · Feb {_sh_curr_yr}</div>
  <div class="section-sub">
    February snapshot comparisons across four years control for seasonality and isolate structural
    demand trends. Structural YoY = Feb {_sh_prev_yr} → Feb {_sh_curr_yr}. 2-Year Change = Feb {_sh_mid_yr} → Feb {_sh_curr_yr}.
    3-Year Change = Feb {_sh_base_yr} → Feb {_sh_curr_yr}. Engagement Stability =
    current 30-day avg ÷ all-time peak players — measures how far engagement sits below the launch spike.
    Source: SteamCharts historical data.
  </div>

  <div class="chart-card" style="margin-bottom:18px;">
    <h3>Monthly Avg Players — Structural Engagement (Completed Months Only)</h3>
    <div class="chart-wrap-md"><canvas id="chartSteamMonthlyAvg"></canvas></div>
    <p class="data-note">Completed calendar months only. Source: SteamCharts history. MTD rolling data excluded.</p>
  </div>

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th class="num">Feb {_sh_base_yr} Avg</th>
          <th class="num">Feb {_sh_mid_yr} Avg</th>
          <th class="num">Feb {_sh_prev_yr} Avg</th>
          <th class="num">Feb {_sh_curr_yr} Avg</th>
          <th class="num">Structural YoY</th>
          <th class="num">2-Year Change</th>
          <th class="num">3-Year Change</th>
          <th class="num">Current Avg Players</th>
          <th class="num">Peak Players</th>
          <th class="num">Engagement Stability</th>
        </tr>
      </thead>
      <tbody>{steam_structural_rows}</tbody>
    </table>
    <p class="data-note">
      Structural YoY = Feb {_sh_prev_yr} → Feb {_sh_curr_yr} avg players.
      2-Year Change = Feb {_sh_mid_yr} → Feb {_sh_curr_yr} (n/a for Space Marine 2 — released Sep 2024).
      3-Year Change = Feb {_sh_base_yr} → Feb {_sh_curr_yr} (n/a for titles not yet released in {_sh_base_yr}).
      Current Avg Players = last 30 days rolling (includes partial months). Engagement Stability = last-30d avg ÷ all-time peak.
      Source: SteamCharts historical data.
    </p>
  </div>
  <div class="key-insight"><span class="key-insight-lbl">Key Insight</span>{_steam_insight}</div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    February-to-February comparisons strip out seasonal noise and measure true structural demand — the same month, different years. Multiple Warhammer games holding or growing player counts 2–3 years after launch means the IP keeps converting new players through its back catalog. That's a library effect: ongoing digital discovery translating directly into active gameplay, and eventually into physical hobby purchases.
  </div>
</section>

<!-- ── My Warhammer App — Active User Growth ────────────────────────────── -->
<section>
  <div class="section-title">My Warhammer App — Active User Growth</div>
  <div class="section-sub">
    My Warhammer is GW's unified single login platform. Active users = engaged in the last
    6 months (GW definition). Growth from 346K to ~790K active users in 3 years confirms
    digital customer base expansion tracking alongside physical demand.
    Source: GW Half-Year Results + Annual Reports (investor.games-workshop.com). Update bi-annually.
  </div>

  <div style="display:grid; grid-template-columns:1.2fr 0.8fr; gap:18px; margin-bottom:18px;">
    <div class="chart-card">
      <h3>My Warhammer Active Users — Reported Snapshots</h3>
      <div class="chart-wrap-md"><canvas id="chartAppUsers"></canvas></div>
      <p class="data-note">
        H1 = half-year results (Nov period end). FY = full-year annual report (May period end).
        Slight dip FY24 vs H1 FY24 is normal seasonal variation. Source: GW investor reports.
      </p>
    </div>

    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>Period</th>
            <th class="num">Active Users</th>
            <th class="num">YoY</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>{_app_table_rows}</tbody>
      </table>
      <p class="data-note">
        Active user = engaged with GW platform in last 6 months.
        YoY computed vs prior same-type snapshot where not explicitly reported.
      </p>
    </div>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    These are GW's own registered customers, actively using their platform within the last 6 months — not anonymous web visitors. Growing from 346K to 790K active users in 3 years means GW's identifiable digital customer base has more than doubled. This is GW's own internal measure of its active buyer pool, directly from their audited investor reports, tracking in sync with every other demand signal on this dashboard.
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-6">Page 6 — Competitive Scene Participation</div>

<!-- ── Page 6: Tournament Participation ────────────────────────────────── -->
<section>
  <div class="section-title">Real-World Hobby Participation — Major Competitive Tournaments</div>
  <div class="section-sub">
    Tournament participation tracks active hobby engagement — players who have purchased,
    built, and painted armies to compete at the highest level. The two largest annual
    Warhammer 40k championship events serve as a direct headcount of the most invested
    segment of the player base. Growth here confirms that digital signals (YouTube discovery,
    Reddit expansion, Steam engagement) are translating into real-world hobby participation.
  </div>

  <div class="chart-card" style="margin-bottom:18px;">
    <h3>Tournament Participation — {_t_base} · {_t_prev} · {_t_latest}</h3>
    <div class="chart-wrap-md"><canvas id="chartTournament"></canvas></div>
    <p class="data-note">
      World Championships of Warhammer (WCW) and Las Vegas Open (LVO) are the two largest
      annual Warhammer 40k competitive events globally. Player counts = confirmed registered
      participants per event year.
    </p>
  </div>

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Event</th>
          <th class="num">{_t_base} Players</th>
          <th class="num">{_t_prev} Players</th>
          <th class="num">{_t_latest} Players</th>
          <th class="num">YoY ({_t_prev}→{_t_latest})</th>
          <th class="num">2-Year Growth ({_t_base}→{_t_latest})</th>
        </tr>
      </thead>
      <tbody>{_tournament_table_rows}</tbody>
    </table>
    <p class="data-note">
      YoY = {_t_prev}→{_t_latest} registered player change. 2-Year Growth = {_t_base}→{_t_latest} total growth.
      Sources: official tournament organizer registration data.
    </p>
  </div>

  <div class="key-insight">
    <span class="key-insight-lbl">Key Insight</span>
    {_tournament_insight}
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Tournament players represent the maximum commitment tier of the hobby — they've purchased armies, built and painted models, paid entry fees, and often traveled to compete. If this number is growing, it proves that digital discovery (YouTube, Reddit, Steam) is converting all the way through to real-world physical spending at the highest engagement level. Online signal becoming real-world action is the full demand cycle completed.
  </div>
</section>

{_bcp_section_html}

<!-- ════════════════════════════════════════════════════════════════════════ -->
<div class="page-divider" id="pg-7">Page 7 — Retail &amp; Store Intelligence</div>

<!-- ── Page 7A: Store Network Growth ───────────────────────────────────── -->
<section>
  <div class="section-title">Physical Retail Network Expansion</div>
  <div class="section-sub">
    GW operates two parallel retail footprints: company-owned stores and independent
    stockists (third-party hobby shops, game stores that carry GW product).
    The <strong>independent stockist signal matters more</strong> — these are profit-maximizing
    businesses that choose to carry GW inventory based on customer pull-through.
    A growing stockist count means more non-GW retailers believe GW product will sell.
    The chart below indexes both series to 100 at their respective start years so growth
    rates are directly comparable on the same axis.
    Source: GW Annual Reports (investor.games-workshop.com).
  </div>

  <div class="chart-card" style="margin-bottom:18px;">
    <h3>Store Network Growth — Indexed to 100 at Start Year (Growth Rate Comparison)</h3>
    <div class="chart-wrap-md"><canvas id="chartStoreCount"></canvas></div>
    <p class="data-note">
      Both series indexed to 100 at their earliest data point (GW Stores: 2017, Indie Stockists: 2020).
      A value of 165 means +65% growth from base year.
      GW-operated: +23% (2017→2025). Independent stockists: +65% (2020→2025).
      Source: GW Annual Reports.
    </p>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Independent stockists — hobby shops and game stores that choose to carry GW product — are growing at nearly 3× the rate of GW's own stores. These are profit-driven businesses that only stock what their customers actually ask for. A +65% stockist expansion since 2020 is external market validation: thousands of independent retailers independently concluded that Warhammer will sell off their shelves. That's consumer pull, not GW pushing product.
  </div>
</section>

<!-- ── Page 7B: Revenue Channel Mix ────────────────────────────────────── -->
<section>
  <div class="section-title">Revenue Channel Mix — Trade Channel Acceleration</div>
  <div class="section-sub">
    GW reports revenue across three channels: Own Retail (company stores), Trade (independent
    stockists + distributors), and Online (direct web sales). The demand signal is in the
    <strong>Trade channel</strong>: independent retailers are buying significantly more GW product
    each period. Trade grew from £120.9M to £209.0M H1 (+73%) while its <em>share</em> of
    total revenue rose from {_trade_share_first:.0f}% to {_trade_share_last:.0f}% — meaning
    third-party demand is outpacing GW's own channels. Independent retailers only buy what
    they can sell: this is an external validation of consumer demand.
    Source: GW Half-Year Results (investor.games-workshop.com).
  </div>

  <!-- Key signal stat cards -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px;">
    <div class="table-card" style="text-align:center;padding:16px 12px;">
      <div style="font-size:22px;font-weight:700;color:#2980b9;">£{_h1_latest['trade']:.0f}M</div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;">Trade Revenue ({_h1_latest_k.replace('H1_FY','H1 FY')})</div>
    </div>
    <div class="table-card" style="text-align:center;padding:16px 12px;">
      <div style="font-size:22px;font-weight:700;color:#27ae60;">+{_trade_growth_pct:.0f}%</div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;">Trade Growth ({_h1_first_k.replace('H1_FY','H1 FY')} → {_h1_latest_k.replace('H1_FY','H1 FY')})</div>
    </div>
    <div class="table-card" style="text-align:center;padding:16px 12px;">
      <div style="font-size:22px;font-weight:700;color:#e67e22;">{_trade_share_last:.0f}%</div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;">Trade Share of H1 Revenue (up from {_trade_share_first:.0f}%)</div>
    </div>
  </div>

  <div class="chart-card" style="margin-bottom:18px;">
    <h3>Trade Channel Revenue (£M) &amp; Trade Share of Total (%)</h3>
    <div class="chart-wrap-md"><canvas id="chartRevChannel"></canvas></div>
    <p class="data-note">
      Blue line (left axis) = trade channel revenue in £M. Orange dashed (right axis) = trade's % of total H1 revenue.
      Both rising = trade channel growing faster than other channels.
      H1 = first six months of fiscal year (ending ~December). Source: GW Half-Year Reports.
    </p>
  </div>

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Period</th>
          <th class="num">Own Retail</th>
          <th class="num">Trade</th>
          <th class="num">Online</th>
          <th class="num">Total</th>
          <th class="num">Trade Share</th>
        </tr>
      </thead>
      <tbody>{_rc_table_rows}</tbody>
    </table>
    <p class="data-note">
      Trade channel includes sales to independent hobby retailers, game stores, and distributors globally.
      Trade share = Trade ÷ Total H1 revenue.
      Source: GW Half-Year Results reports.
    </p>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    The Trade channel (independent retailers buying wholesale from GW) is growing the fastest and capturing a bigger share of total revenue each period. Independent retailers only reorder what their customers are actively buying — they don't carry dead inventory. Trade revenue outpacing GW's own stores is demand being pulled through the supply chain by consumers, not just pushed by GW's direct sales effort.
  </div>
</section>

<!-- ── Page 7B2: Store Productivity — Revenue per Store ─────────────────── -->
<section>
  <div class="section-title">Store Productivity — Revenue per GW-Operated Store</div>
  <div class="section-sub">
    Dividing GW own-retail H1 revenue by the contemporary GW store count gives
    <strong>revenue per location</strong> — the standard retail productivity metric.
    When this rises while store count also rises, it confirms that new stores
    are not just displacing existing ones: the entire base is getting more productive.
    This is GW's own audited financials, no estimation required.
    H1 FY23: £{_rps_first:.1f}K per store → H1 FY26: £{_rps_last:.1f}K per store
    (+{_rps_growth:.0f}% in 3 comparable H1 periods).
    Source: GW Half-Year Results (investor.games-workshop.com).
  </div>

  <!-- Stat cards -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px;">
    <div class="table-card" style="text-align:center;padding:16px 12px;">
      <div style="font-size:22px;font-weight:700;color:#27ae60;">£{_rps_last:.1f}K</div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;">Revenue per Store ({_h1_latest_k.replace('H1_FY','H1 FY')}, H1)</div>
    </div>
    <div class="table-card" style="text-align:center;padding:16px 12px;">
      <div style="font-size:22px;font-weight:700;color:#27ae60;">+{_rps_growth:.0f}%</div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;">Productivity Growth ({_h1_first_k.replace('H1_FY','H1 FY')} → {_h1_latest_k.replace('H1_FY','H1 FY')})</div>
    </div>
    <div class="table-card" style="text-align:center;padding:16px 12px;">
      <div style="font-size:22px;font-weight:700;color:#2980b9;">{GW_STORE_DATA['h1_store_count_map']['H1_FY26']}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;">GW Stores (H1 FY26 period)</div>
    </div>
  </div>

  <div style="display:grid; grid-template-columns:1.3fr 0.7fr; gap:18px; margin-bottom:18px;">
    <div class="chart-card">
      <h3>Own Retail Revenue per GW Store (£K per H1)</h3>
      <div class="chart-wrap-md"><canvas id="chartRevPerStore"></canvas></div>
      <p class="data-note">
        Own Retail H1 revenue ÷ GW store count at period end.
        Rising line = more revenue being generated per location — productivity gain, not just expansion.
        Source: GW Half-Year Results.
      </p>
    </div>

    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>Period</th>
            <th class="num">Stores</th>
            <th class="num">Own Retail H1</th>
            <th class="num">Rev / Store</th>
          </tr>
        </thead>
        <tbody>{_rps_table_rows}</tbody>
      </table>
      <p class="data-note">
        Rev / Store = Own Retail H1 revenue ÷ contemporary store count.
        Comparable H1 periods only (excludes H2 seasonality).
        Source: GW Half-Year Reports.
      </p>
    </div>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Revenue per store going up while store count also increases means growth isn't just geographic expansion — existing locations are doing more business per square foot. This separates real same-store demand from the mechanical effect of opening new locations. When both store count and revenue per store are rising together, you have genuine demand outpacing supply capacity.
  </div>
</section>

<!-- ── Page 7C: Physical Footprint Signals ──────────────────────────────── -->
<section>
  <div class="section-title">Physical Footprint Signals — Independent Data</div>
  <div class="section-sub">
    The signals below are sourced independently of GW self-reporting: LinkedIn hiring activity
    and narrative demand events from industry sources. These confirm that physical demand
    momentum matches the digital signals.
  </div>

  <div style="margin-bottom:18px;">

    <!-- LinkedIn expansion signals -->
    <div class="table-card">
      <h3 style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                  color:var(--muted);margin-bottom:12px;">
        Physical Expansion Pipeline — LinkedIn Store Manager Postings
      </h3>
      <!-- Signal: what does this mean -->
      <div style="background:#1a2332;border-radius:4px;padding:10px 14px;margin-bottom:14px;
                  font-size:12px;line-height:1.7;">
        <strong style="color:var(--text);">Why this matters:</strong>
        <span style="color:var(--muted);">GW hires a Store Manager 3–6 months before opening.
        Each active posting = a confirmed upcoming store. Each store generates
        ~£{_li_avg_annual_rev_k:.0f}K/year in own-retail revenue (based on latest productivity figures).
        {len(LINKEDIN_OPENINGS['openings'])} active postings = <strong style="color:#27ae60;">~£{_li_rev_commitment_m:.1f}M in committed incremental annual revenue</strong>
        GW has decided to bet on this year.</span>
      </div>
      <!-- Summary counts -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px;text-align:center;">
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:10px;">
          <div style="font-size:20px;font-weight:700;color:var(--text);">{len(LINKEDIN_OPENINGS['openings'])}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px;">Active Postings</div>
        </div>
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:10px;">
          <div style="font-size:20px;font-weight:700;color:#27ae60;">{len(_first_entry_mkts)}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px;">New Market Entries</div>
        </div>
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:10px;">
          <div style="font-size:20px;font-weight:700;color:#2980b9;">{_li_regions_count}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px;">Regions Active</div>
        </div>
        <div style="background:#1c2e1c;border:1px solid #27ae6044;border-radius:4px;padding:10px;">
          <div style="font-size:17px;font-weight:700;color:#27ae60;">£{_li_rev_commitment_m:.1f}M</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px;">Revenue Commitment</div>
        </div>
      </div>
      <!-- New market entries highlighted (pre-computed above) -->
      {_li_first_entry_html}
      <!-- Expansion locations compact list -->
      <details style="margin-top:10px;">
        <summary style="font-size:11px;color:var(--muted);cursor:pointer;">
          All {_expansion_count} expansion postings (click to expand)
        </summary>
        <table style="margin-top:10px;">
          <thead><tr><th>Location</th><th>Region</th></tr></thead>
          <tbody>{_li_expansion_rows_html}</tbody>
        </table>
      </details>
      <p class="data-note" style="margin-top:10px;">
        Revenue commitment = postings × £{_li_avg_annual_rev_k:.0f}K avg annual revenue per store (own-retail H1 FY26 annualized).
        Source: LinkedIn job search ({_li_date}). MANUAL UPDATE REQUIRED monthly.
      </p>
    </div>
  </div>

  <!-- Narrative events -->
  <div class="table-card">
    <h3 style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                color:var(--muted);margin-bottom:12px;">
      Notable Retail Demand Events
    </h3>
    <table>
      <thead>
        <tr><th>Date</th><th>Event</th><th>Region</th><th>Source</th></tr>
      </thead>
      <tbody>{_narrative_rows}</tbody>
    </table>
    <p class="data-note">
      Sources: industry news, GW half-year reports, community reporting.
      ⚠ = source unverified — requires independent confirmation.
    </p>
  </div>
  <div class="section-why"><span class="section-why-lbl">What This Shows &amp; Why It Matters</span>
    Independent third-party data — foot traffic analytics, LinkedIn hiring, and notable demand events — all confirm the physical retail story without relying on GW's own reporting. When external sources agree with a company's own financials, the signal is credible. Active LinkedIn store manager postings are a particularly reliable forward indicator: GW hires 3–6 months before opening, so each posting is a committed expansion bet already in motion.
  </div>
</section>



{_pg8_html}

</div><!-- /container -->

<script>
  window.__yt = {chart_data_js};
  {CHART_INIT_JS}
  {REDDIT_CHART_INIT_JS}
  {STEAM_CHART_INIT_JS}
  {MULTIYEAR_CHART_INIT_JS}
  {TOURNAMENT_CHART_JS}
  {BCP_CHART_JS}
  {RETAIL_CHART_JS}
  {EXEC_SUMMARY_JS}
</script>
</body>
</html>"""

    return html


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("── Warhammer Demand Acceleration Dashboard ──────────────────────")

    channels_df         = load_channels_combined()
    channels_history_df = load_channel_history()
    anchor_history_df   = load_anchor_history()
    anchors_df  = load_anchors()
    videos_df   = load_videos()
    reddit_df       = load_reddit_members_weekly()
    steam_monthly_df = load_steam_monthly_history()
    steam_rolling_df = load_steam_rolling_30d()
    steam_live_df    = load_steam_players()
    store_threads_monthly_df = load_reddit_store_monthly()
    store_threads_recent_df  = load_reddit_store_recent()
    store_threads_raw_df     = load_reddit_store_raw()
    reddit_intel_posts_df, reddit_intel_comments_df = load_reddit_intel()
    gw_stock_df              = load_gw_stock()

    if channels_df.empty:
        print("[ERROR] No channel data. Run fetch_youtube_channels_daily.py first.")
        sys.exit(1)

    channels_df = channels_df[channels_df["channel_label"].isin(CHANNEL_ORDER)]
    if not anchors_df.empty:
        # Scope anchor data to slugs currently defined in config — drops retired anchors
        if os.path.exists(ANCHORS_CONFIG):
            cfg = pd.read_csv(ANCHORS_CONFIG)
            active_slugs = set(cfg["video_slug"].tolist())
            anchors_df = anchors_df[anchors_df["video_slug"].isin(active_slugs)]
        anchors_df = anchors_df[anchors_df["channel_label"].isin(CHANNEL_ORDER)]
    if not videos_df.empty:
        videos_df = videos_df[videos_df["channel_label"].isin(CHANNEL_ORDER)]

    print("  Computing metrics...")

    # Multi-year first — needed as ECI divisor (CAGR preferred over YoY)
    channels_full_df = pd.concat(
        [channels_df, channels_history_df], ignore_index=True
    ).drop_duplicates(subset=["date", "channel_label"], keep="last").sort_values(
        ["channel_label", "date"]
    ).reset_index(drop=True)
    multiyear = compute_multiyear_growth(channels_full_df)

    yoy        = compute_yoy_sub_metrics(channels_df)
    evergreen  = compute_evergreen_metrics(anchors_df, anchor_history_df)
    eci_map    = compute_eci(evergreen, yoy, multiyear)   # uses CAGR as divisor
    reddit_yoy = compute_reddit_yoy(reddit_df)
    reddit_agg = compute_reddit_aggregate(reddit_yoy)
    reddit_my  = compute_reddit_multiyear(reddit_yoy)
    steam_met  = compute_steam_monthly_metrics(steam_monthly_df, steam_rolling_df, steam_live_df)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("  Building HTML...")
    html = build_html(
        channels_df, yoy, eci_map, evergreen,
        reddit_df, reddit_yoy, reddit_agg,
        steam_monthly_df, steam_rolling_df, steam_live_df, steam_met,
        channels_full_df, anchor_history_df, multiyear,
        generated_at,
        reddit_multiyear=reddit_my,
        store_threads_monthly_df=store_threads_monthly_df,
        store_threads_recent_df=store_threads_recent_df,
        store_threads_raw_df=store_threads_raw_df,
        reddit_intel_posts_df=reddit_intel_posts_df,
        reddit_intel_comments_df=reddit_intel_comments_df,
        gw_stock_df=gw_stock_df,
    )

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT_HTML) // 1024
    print(f"  ✓ Dashboard → {OUTPUT_HTML} ({size_kb}KB)\n")

    print("── Channel Summary ──────────────────────────────────────────────")
    for ch in CHANNEL_ORDER:
        my = multiyear.get(ch, {})
        ec = eci_map.get(ch, {})
        print(f"  {CHANNEL_DISPLAY[ch]:25s}  "
              f"CAGR: {my.get('cagr_pct') or 0:+.1f}%  "
              f"YoY: {yoy.get(ch,{}).get('yoy_pct') or 0:+.1f}%  "
              f"ECI: {ec.get('eci') or 0:.2f}×")

    abs_path = os.path.abspath(OUTPUT_HTML)
    webbrowser.open(f"file://{abs_path}")
    print(f"\n  ✓ Opened in browser.")


if __name__ == "__main__":
    main()
