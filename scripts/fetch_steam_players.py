"""
Fetch Steam player counts for tracked Warhammer digital titles.

Appends one row per game per run to data/steam_players.csv.
Dedup key: (date, game) — safe to re-run same day.

Sources:
  current_players : Steam API ISteamUserStats/GetNumberOfCurrentPlayers (real-time CCU)
  peak_24h        : SteamSpy ccu field (peak CCU proxy — best available without OAuth)
  avg_30d         : Computed from stored daily snapshots (rolling 30-day mean)

peak_24h via Steam's official API requires OAuth and is not publicly accessible.
SteamSpy ccu is used as the best available proxy; labeled accordingly in source column.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR              = "data"
CONFIG_DIR            = "config"
OUTPUT_CSV            = os.path.join(DATA_DIR,   "steam_players.csv")
GAMES_CSV             = os.path.join(CONFIG_DIR, "steam_games.csv")
STEAM_MONTHLY_HISTORY = os.path.join(DATA_DIR,   "steam_monthly_history.csv")

# ── Month-finalization config ─────────────────────────────────────────────────
# Maps the `game` column in steam_players.csv → (game_slug, game_name)
# used when promoting past-month live snapshots into steam_monthly_history.csv
GAME_SLUG_MAP = {
    "TW_Warhammer3":  ("tw_wh3",         "Total War: WH3"),
    "Space_Marine_2": ("space_marine_2",  "Space Marine 2"),
    "Darktide":       ("darktide",        "Darktide"),
    "Vermintide_2":   ("vermintide_2",    "Vermintide 2"),
}

MONTHLY_SCHEMA = ["month", "game_slug", "game_name", "avg_players",
                  "peak_players", "source", "as_of_date"]

# ── API endpoints ─────────────────────────────────────────────────────────────
STEAM_CCU_URL  = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
STEAMSPY_URL   = "https://steamspy.com/api.php"
SLEEP_SEC      = 1.5   # SteamSpy rate limit: ~1 req/sec

SCHEMA = ["date", "game", "appid", "current_players", "peak_24h", "avg_30d", "source"]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "WarhammerdDemandTracker/1.0"})


# ── API helpers ───────────────────────────────────────────────────────────────

def get_steam_ccu(appid: int) -> int | None:
    """Real-time concurrent players from Steam official API."""
    try:
        r = SESSION.get(STEAM_CCU_URL, params={"appid": appid}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("response", {}).get("result") == 1:
            return int(data["response"]["player_count"])
    except Exception as e:
        print(f"    [Steam API error] {e}")
    return None


def get_steamspy_ccu(appid: int) -> int | None:
    """SteamSpy ccu — peak concurrent proxy (best available without OAuth)."""
    try:
        r = SESSION.get(STEAMSPY_URL, params={"request": "appdetails", "appid": appid}, timeout=20)
        r.raise_for_status()
        return int(r.json().get("ccu", 0)) or None
    except Exception as e:
        print(f"    [SteamSpy error] {e}")
    return None


def compute_avg_30d(df: pd.DataFrame, game: str, as_of_date: str) -> float | None:
    """Rolling 30-day average of current_players from stored snapshots."""
    cutoff = str((pd.to_datetime(as_of_date) - timedelta(days=30)).date())
    window = df[(df["game"] == game) & (df["date"] >= cutoff)]
    return round(window["current_players"].mean(), 0) if not window.empty else None


# ── Month finalization ────────────────────────────────────────────────────────

def finalize_past_months() -> None:
    """
    Scan steam_players.csv for calendar months that are now fully in the past
    (YYYY-MM strictly less than the current calendar month). For each past month
    not already recorded in steam_monthly_history.csv, compute:

        avg_players  = mean(current_players) across all snapshots in that month
        peak_players = max(current_players)  [lower-bound proxy; true peak from
                        SteamCharts is more accurate but not available here]

    Appends new rows to steam_monthly_history.csv. Append-only — existing rows
    are never modified. Safe to call on every pipeline run.
    """
    if not os.path.exists(OUTPUT_CSV):
        return

    live_df = pd.read_csv(OUTPUT_CSV)
    live_df["date"]  = pd.to_datetime(live_df["date"], errors="coerce")
    live_df          = live_df.dropna(subset=["date"])
    live_df["month"] = live_df["date"].dt.strftime("%Y-%m")

    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    past_df       = live_df[live_df["month"] < current_month]

    if past_df.empty:
        print("  [finalize] No past-month snapshots to promote.")
        return

    # Load (or create) history; build a set of already-finalized (month, slug) keys
    if os.path.exists(STEAM_MONTHLY_HISTORY):
        hist_df       = pd.read_csv(STEAM_MONTHLY_HISTORY)
        existing_keys = set(zip(hist_df["month"].astype(str),
                                hist_df["game_slug"].astype(str)))
    else:
        hist_df       = pd.DataFrame(columns=MONTHLY_SCHEMA)
        existing_keys = set()

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_rows  = []

    for (month, game), grp in past_df.groupby(["month", "game"]):
        if game not in GAME_SLUG_MAP:
            continue
        slug, game_name = GAME_SLUG_MAP[game]
        if (month, slug) in existing_keys:
            continue                                # already finalized — skip

        avg_p  = round(float(grp["current_players"].mean()), 1)
        peak_p = int(grp["current_players"].max())

        new_rows.append({
            "month":        month,
            "game_slug":    slug,
            "game_name":    game_name,
            "avg_players":  avg_p,
            "peak_players": peak_p,
            "source":       "live_snapshot_finalized",
            "as_of_date":   today_str,
        })

    if new_rows:
        hist_df = pd.concat([hist_df, pd.DataFrame(new_rows)], ignore_index=True)
        hist_df = hist_df.sort_values(["game_slug", "month"]).reset_index(drop=True)
        hist_df.to_csv(STEAM_MONTHLY_HISTORY, index=False)
        print(f"  [finalize] ✓ Promoted {len(new_rows)} past-month rows "
              f"→ {STEAM_MONTHLY_HISTORY}")
    else:
        print("  [finalize] All past months already recorded — nothing to promote.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("── Steam Player Tracker ────────────────────────────────────────")

    if not os.path.exists(GAMES_CSV):
        print(f"[ERROR] Missing {GAMES_CSV}")
        return

    cfg      = pd.read_csv(GAMES_CSV)
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Load existing data; strip today's rows so re-run is idempotent
    if os.path.exists(OUTPUT_CSV):
        df = pd.read_csv(OUTPUT_CSV)
        df = df[df["date"] != today]
    else:
        df = pd.DataFrame(columns=SCHEMA)

    new_rows = []
    print(f"  Fetching {len(cfg)} games → {today}\n")

    for _, row in cfg.iterrows():
        appid = int(row["appid"])
        game  = row["game"]
        label = row["label"]

        print(f"  {label} (appid {appid})")

        curr = get_steam_ccu(appid)
        time.sleep(SLEEP_SEC)
        spy_ccu = get_steamspy_ccu(appid)
        time.sleep(SLEEP_SEC)

        avg_30d = compute_avg_30d(df, game, today)

        new_rows.append({
            "date":            today,
            "game":            game,
            "appid":           appid,
            "current_players": curr     or 0,
            "peak_24h":        spy_ccu  or 0,
            "avg_30d":         avg_30d  or curr or 0,
            "source":          "api",
        })

        print(f"    current: {(curr or 0):>7,}  "
              f"peak_24h (spy ccu): {(spy_ccu or 0):>7,}  "
              f"avg_30d: {int(avg_30d or curr or 0):>7,}")

    if not new_rows:
        print("  [WARN] No data fetched.")
        return

    df_new = pd.DataFrame(new_rows)
    df     = pd.concat([df, df_new], ignore_index=True)
    df     = df.sort_values(["game", "date"]).reset_index(drop=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\n── Snapshot Summary: {today} ────────────────────────────────────")
    for r in new_rows:
        print(f"  {r['game']:20s}  current: {r['current_players']:>7,}  "
              f"peak_24h: {r['peak_24h']:>7,}  avg_30d: {int(r['avg_30d']):>7,}")

    print(f"\n  ✓ {len(new_rows)} rows saved → {OUTPUT_CSV}  (total: {len(df)})")

    # Promote any now-completed calendar months into steam_monthly_history.csv
    print("\n── Month Finalization ──────────────────────────────────────────")
    finalize_past_months()


if __name__ == "__main__":
    main()
