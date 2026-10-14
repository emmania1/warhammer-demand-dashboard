#!/bin/bash
# Warhammer Demand Tracker — Weekly refresh + publish
# Installed by setup_cron.sh → runs Sundays 9:00 AM (daily stock data comes from GitHub Actions).
#
#   1. Fetch YouTube channel stats + topic videos (needs YOUTUBE_API_KEY in .env)
#   2. Regenerate index.html from all CSVs (picks up the week's stock data)
#   3. Commit + push → GitHub Pages redeploys the live site
#
# Reddit members, Steam history and the Page 6/7 constants are still manual.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

echo "════ Weekly pipeline — $(date '+%Y-%m-%d %H:%M') ════"

source "$SCRIPT_DIR/venv/bin/activate"
set -a
source "$SCRIPT_DIR/.env" 2>/dev/null
set +a

echo "── Syncing stock data from GitHub ───────────────"
# Daily data and index.html are written by the GitHub Action (.github/workflows/daily_stock.yml);
# the remote copy is authoritative, so drop any local edits to them before pulling.
git -C "$SCRIPT_DIR" checkout -- data/gw_stock_daily.csv data/gw_stock_summary.csv data/element_games_stock_daily.csv \
    data/gw_paint_stock_daily.csv data/gw_paint_stock_summary.csv data/gw_paint_oos_episodes.csv \
    data/gw_storefinder_summary.csv data/gw_storefinder_country.csv data/gw_storefinder_roster.csv \
    data/gw_storefinder_changes.csv data/indie_paint_panel_daily.csv data/indie_paint_panel_summary.csv \
    data/indie_paint_panel_runs.csv data/indie_paint_panel_unmatched.csv \
    data/indie_paint_panel_qty_series.csv data/indie_paint_panel_qty_summary.csv \
    data/prev_run_snapshot.json index.html 2>/dev/null
git -C "$SCRIPT_DIR" pull -q --rebase origin main || { echo "✗ git pull failed — not publishing"; exit 1; }

echo ""
echo "── YouTube channel stats ────────────────────────"
python scripts/fetch_youtube_channels_daily.py || echo "⚠ YouTube fetch failed — continuing with existing data"

echo ""
echo "── YouTube topic videos (Tone Pro etc.) ─────────"
python scripts/fetch_youtube_topic_videos.py || echo "⚠ Topic video fetch failed — continuing with existing data"

echo ""
echo "── Regenerating dashboard ───────────────────────"
NO_BROWSER=1 python scripts/generate_youtube_dashboard.py || { echo "✗ Generator failed — not publishing"; exit 1; }

echo ""
echo "── Publishing ───────────────────────────────────"
git -C "$SCRIPT_DIR" add index.html data/
if git -C "$SCRIPT_DIR" diff --cached --quiet; then
    echo "No changes to publish."
else
    git -C "$SCRIPT_DIR" commit -q -m "Weekly refresh $(date +%Y-%m-%d): YouTube stats + topic videos" \
        -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    git -C "$SCRIPT_DIR" push -q origin main && echo "✓ Pushed — GitHub Pages will redeploy." \
        || echo "✗ Push failed — commit is local; run 'git push' manually."
fi

echo "✓ Weekly pipeline complete."
