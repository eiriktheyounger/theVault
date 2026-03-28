#!/bin/bash
# Manual trigger: sync vault tasks to Apple Reminders now.
# Run directly, via Shortcuts app, or from Spotlight.
#
# To add a keyboard shortcut:
#   1. Open Shortcuts app → New Shortcut
#   2. Add action: "Run Shell Script"
#   3. Paste: bash /Users/ericmanchester/theVault/System/Scripts/sync_reminders_now.sh
#   4. Assign a keyboard shortcut in Shortcut Details

cd /Users/ericmanchester/theVault || exit 1
source .venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Manual reminders sync started"
python3 -m System.Scripts.task_normalizer 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done"
