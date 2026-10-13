#!/bin/bash
# Warhammer Demand Tracker — Daily stock snapshot runner
# Runs every morning to capture GW.com + Element Games OOS state.
# Lightweight: no YouTube/Reddit API calls, no HTML regeneration.
#
# Manual/local use only — the scheduled daily run is .github/workflows/daily_stock.yml.
# Sunday 9:00 AM run_pipeline.sh then regenerates + publishes index.html.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/venv/bin/activate"

set -a
source "$SCRIPT_DIR/.env" 2>/dev/null
set +a

echo "── GW.com stock snapshot (Algolia) ──────────────"
python scripts/fetch_gw_stock.py

echo ""
echo "── Paint SKU stock snapshot ─────────────────────"
python scripts/fetch_gw_paint_stock.py

echo ""
echo "── Element Games stock snapshot (UK indie) ──────"
python scripts/fetch_element_games_stock.py

echo ""
echo "✓ Daily stock snapshots complete."
