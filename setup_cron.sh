#!/bin/bash
# Sets up cron jobs for the Warhammer demand pipeline.
#
# Installs two jobs:
#   1. Daily 8:00 AM  — stock-only snapshots (GW.com + Element Games OOS)
#   2. Weekly Sunday 9:00 AM — full pipeline (YouTube, Reddit, Steam, reports)
#
# Run once:  bash setup_cron.sh
# Remove:    bash setup_cron.sh --remove
# Status:    bash setup_cron.sh --status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEEKLY_PIPELINE="$SCRIPT_DIR/run_pipeline.sh"
DAILY_STOCK="$SCRIPT_DIR/run_daily_stock.sh"
LOG_WEEKLY="$SCRIPT_DIR/pipeline.log"
LOG_DAILY="$SCRIPT_DIR/stock_daily.log"

CRON_TAG_WEEKLY="warhammer-demand-weekly"
CRON_TAG_DAILY="warhammer-demand-daily-stock"

# Daily 8am (stock only)
CRON_DAILY="0 8 * * * $DAILY_STOCK >> $LOG_DAILY 2>&1  # $CRON_TAG_DAILY"
# Sunday 9am (full pipeline — includes stock run too, but daily ensures no gaps)
CRON_WEEKLY="0 9 * * 0 $WEEKLY_PIPELINE >> $LOG_WEEKLY 2>&1  # $CRON_TAG_WEEKLY"

# ── Remove ─────────────────────────────────────────────────────────────────────
if [ "$1" == "--remove" ]; then
    crontab -l 2>/dev/null \
        | grep -v "$CRON_TAG_WEEKLY" \
        | grep -v "$CRON_TAG_DAILY" \
        | crontab -
    echo "✓ Both cron jobs removed."
    exit 0
fi

# ── Status ─────────────────────────────────────────────────────────────────────
if [ "$1" == "--status" ]; then
    echo "Installed cron jobs:"
    crontab -l 2>/dev/null | grep -E "$CRON_TAG_WEEKLY|$CRON_TAG_DAILY" \
        || echo "  (none installed)"
    exit 0
fi

# ── Make scripts executable ────────────────────────────────────────────────────
chmod +x "$DAILY_STOCK"
chmod +x "$WEEKLY_PIPELINE"

# ── Install daily stock job ────────────────────────────────────────────────────
CURRENT=$(crontab -l 2>/dev/null)

if echo "$CURRENT" | grep -q "$CRON_TAG_DAILY"; then
    echo "Daily stock cron already installed — skipping."
else
    (echo "$CURRENT"; echo "$CRON_DAILY") | crontab -
    CURRENT=$(crontab -l 2>/dev/null)
    echo "✓ Daily stock cron installed (8:00 AM every day)."
fi

# ── Install weekly pipeline job ────────────────────────────────────────────────
if echo "$CURRENT" | grep -q "$CRON_TAG_WEEKLY"; then
    echo "Weekly pipeline cron already installed — skipping."
else
    (echo "$CURRENT"; echo "$CRON_WEEKLY") | crontab -
    echo "✓ Weekly pipeline cron installed (9:00 AM every Sunday)."
fi

echo ""
echo "  Daily stock   : every day at 08:00  →  $LOG_DAILY"
echo "  Weekly full   : every Sunday 09:00  →  $LOG_WEEKLY"
echo ""
echo "  To check : bash setup_cron.sh --status"
echo "  To remove: bash setup_cron.sh --remove"
echo "  Log tail : tail -f $LOG_DAILY"
