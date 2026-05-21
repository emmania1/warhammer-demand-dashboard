#!/bin/bash
# Warhammer Demand Tracker — one-command pipeline runner
# Usage: ./run_pipeline.sh            (full pipeline + report → opens browser)
#        ./run_pipeline.sh --report   (regenerate report only, opens browser)
#        ./run_pipeline.sh --html     (just open the last HTML report)
#        ./run_pipeline.sh --youtube  (regenerate YouTube dashboard only)
#        ./run_pipeline.sh --ask      (chat with your data via Claude)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv
source "$SCRIPT_DIR/venv/bin/activate"

# Load env vars
set -a
source "$SCRIPT_DIR/.env" 2>/dev/null
set +a

if [ "$1" == "--report" ]; then
    echo "Regenerating report from existing data..."
    python scripts/generate_ecosystem_summary.py
    python scripts/generate_demand_report.py
    python scripts/generate_html_report.py
    echo ""
    echo "→ Report opened in browser: demand_report.html"

elif [ "$1" == "--html" ]; then
    echo "Opening last HTML report..."
    open demand_report.html 2>/dev/null || xdg-open demand_report.html 2>/dev/null

elif [ "$1" == "--youtube" ]; then
    echo "Regenerating YouTube demand dashboard..."
    python scripts/generate_youtube_dashboard.py
    echo ""
    echo "→ Dashboard opened in browser: youtube_dashboard.html"

elif [ "$1" == "--ask" ]; then
    python scripts/ask_claude.py

else
    echo "╔══════════════════════════════════════════════╗"
    echo "║   WARHAMMER DEMAND TRACKER — WEEKLY PIPELINE ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    python run_weekly_pipeline.py
    echo ""
    echo "→ HTML report opened in browser: demand_report.html"
fi
