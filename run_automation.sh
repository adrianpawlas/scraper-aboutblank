#!/bin/bash
# Automation script for About Blank Scraper
# Runs on Monday and Friday at midnight via launchd/cron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/scraper.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting About Blank scraper..."

# Install dependencies if needed
if ! python3 -c "import playwright" 2>/dev/null; then
    log "Installing dependencies..."
    pip3 install -q -r requirements.txt
    python3 -m playwright install chromium 2>/dev/null
fi

# Run the scraper
log "Running scraper..."
python3 main.py 2>&1 | tee -a "$LOG_FILE"

log "Scraper finished."
