"""
Warhammer Steam games metrics tracker.

Fetches current player counts and review stats for games listed in
config/steam_games.csv. No API key required.

Appends to data/steam_metrics_daily.csv, deduplicating on (date, app_id).
"""

import csv, time, requests
import pandas as pd
from pathlib import Path
from datetime import date

GAMES_CFG = Path("config/steam_games.csv")
OUT       = Path("data/steam_metrics_daily.csv")
OUT.parent.mkdir(exist_ok=True)

today = str(date.today())

games = []
with open(GAMES_CFG, newline="") as f:
    for row in csv.DictReader(f):
        games.append({
            "app_id": int(row["app_id"]),
            "name":   row["name"].strip(),
            "label":  row["label"].strip(),
        })

print(f"Fetching Steam stats for {len(games)} games...")
rows = []

for g in games:
    app_id = g["app_id"]
    print(f"  {g['label']} ({app_id})")

    current_players = None
    total_reviews   = None
    positive_pct    = None
    peak_players_24h = None

    # ── Current players ────────────────────────────────────────────────────────
    try:
        r = requests.get(
            "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
            params={"appid": app_id},
            timeout=15,
        )
        current_players = r.json().get("response", {}).get("player_count")
    except Exception as e:
        print(f"    player count error: {e}")

    # ── Review summary ─────────────────────────────────────────────────────────
    try:
        r2 = requests.get(
            f"https://store.steampowered.com/appreviews/{app_id}",
            params={
                "json": 1, "num_per_page": 0,
                "language": "all", "purchase_type": "all",
            },
            headers={"User-Agent": "warhammer-demand-tracker"},
            timeout=15,
        )
        qs = r2.json().get("query_summary", {})
        total_reviews = qs.get("total_reviews", 0)
        total_pos     = qs.get("total_positive", 0)
        positive_pct  = round(total_pos / total_reviews * 100, 1) if total_reviews else None
    except Exception as e:
        print(f"    review error: {e}")

    # ── SteamSpy: owners estimate + 2-week engagement ─────────────────────────
    owners_low      = None
    owners_high     = None
    avg_playtime_2w = None
    ccu_spy         = None
    try:
        r_spy = requests.get(
            "https://steamspy.com/api.php",
            params={"request": "appdetails", "appid": app_id},
            timeout=15,
        )
        spy = r_spy.json()
        owners_str = spy.get("owners", "")
        if owners_str and ".." in owners_str:
            parts = [p.strip().replace(",", "") for p in owners_str.split("..")]
            owners_low  = int(parts[0]) if parts[0].isdigit() else None
            owners_high = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        avg_playtime_2w = spy.get("average_2weeks")   # avg minutes played last 2 weeks
        ccu_spy         = spy.get("ccu")              # current CCU per SteamSpy
    except Exception as e:
        print(f"    SteamSpy error: {e}")

    rows.append({
        "date":                today,
        "app_id":              app_id,
        "label":               g["label"],
        "current_players":     current_players,
        "total_reviews":       total_reviews,
        "positive_pct":        positive_pct,
        "owners_low":          owners_low,
        "owners_high":         owners_high,
        "avg_playtime_2w_min": avg_playtime_2w,
        "ccu_spy":             ccu_spy,
    })

    owners_str_fmt = f"  owners:{owners_low:,}–{owners_high:,}" if owners_low else ""
    print(f"    players:{current_players or '?':}  reviews:{total_reviews or '?'}  "
          f"pos:{positive_pct or '?'}%  2w_playtime:{avg_playtime_2w or '?'}min{owners_str_fmt}")
    time.sleep(1.5)   # polite gap (Steam + SteamSpy)

df_new = pd.DataFrame(rows)

if OUT.exists():
    df_old = pd.read_csv(OUT)
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["date", "app_id"], keep="last")
else:
    df = df_new

df.to_csv(OUT, index=False)
print(f"\nSaved → {OUT} | rows: {len(df)}")
