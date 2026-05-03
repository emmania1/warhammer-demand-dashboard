"""
Warhammer Demand Intelligence — Weekly Pipeline Runner

Execution order:
  1. Reddit: engagement posts + member counts
  2. YouTube: channel stats, videos, evergreen anchors, beginner funnel, retail signals
  3. Steam: player counts + SteamSpy owner estimates
  4. WarCom: GW news article cadence
  5. Competitive events (BCP/Longshanks)
  6. Generate ecosystem summary → demand report → HTML report → YouTube dashboard

Google Trends removed (Phase 3 structural pivot — no short-term noise).
YouTube dashboard added (Phase 4 — franchise demand intelligence, 5-channel scope).
"""

import os

print("── Reddit snapshots (members + engagement) ──────")
os.system("python scripts/fetch_reddit_snapshots.py")

print("── Reddit store thread tracker ──────────────────")
os.system("python scripts/fetch_reddit_store_threads.py")

print("── YouTube channel stats ────────────────────────")
os.system("python scripts/fetch_youtube_channels_daily.py")

print("── YouTube videos ───────────────────────────────")
os.system("python scripts/fetch_youtube_videos_unified.py")

print("── Evergreen anchor views ────────────────────────")
os.system("python scripts/fetch_youtube_evergreen_anchors.py")

print("── Beginner funnel signals (new player inflow) ──")
os.system("python scripts/fetch_beginner_funnel_signals.py")

print("── Retail signals (YouTube keyword scan) ────────")
os.system("python scripts/fetch_retail_signals.py")

print("── Steam player counts ──────────────────────────")
os.system("python scripts/fetch_steam_players.py")

print("── Warhammer Community news ─────────────────────")
os.system("python scripts/fetch_warcom_news.py")

print("── Competitive events ────────────────────────────")
os.system("python scripts/fetch_competitive_data.py")

print("── GW.com stock snapshot (Algolia) ──────────────")
os.system("python scripts/fetch_gw_stock.py")

print("── Element Games stock snapshot (UK indie) ──────")
os.system("python scripts/fetch_element_games_stock.py")

print("── Building ecosystem summary ────────────────────")
os.system("python scripts/generate_ecosystem_summary.py")

print("── Generating analyst report (Claude) ───────────")
os.system("python scripts/generate_demand_report.py")

print("── Generating HTML report ────────────────────────")
os.system("python scripts/generate_html_report.py")

print("── Generating YouTube demand dashboard ──────────")
os.system("python scripts/generate_youtube_dashboard.py")

print("")
print("✓ Weekly pipeline complete.")
print("  → demand_report.html opened in browser")
print("  → youtube_dashboard.html opened in browser")