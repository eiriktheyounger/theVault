#!/bin/bash
# preflight.sh — Autonomous environment preparation for theVault cron jobs.
#
# Run before any scheduled workflow to:
#   1. Free RAM by closing heavy GUI apps (Chrome, Slack, Zoom, etc.)
#   2. Re-mount the NAS if disconnected
#   3. Validate Vault/Inbox/Processed symlinks
#   4. Start Ollama if not running
#   5. Create today's DLY note from template if missing (NEVER overwrites)
#   6. Source .env so workflows have ANTHROPIC_API_KEY and Ollama tuning
#
# Exit 0 on success, 1 on failure. Safe to call as `bash preflight.sh`.
# Designed for unattended overnight/morning operation on Mac Mini M4 16GB.

set -uo pipefail

VAULT_HOME="$HOME/theVault"
NAS_PATH="/Volumes/home/MacMiniStorage"
LOG="$VAULT_HOME/System/Logs/preflight.log"

mkdir -p "$VAULT_HOME/System/Logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

log "──── preflight start ────"

# ── Step 1: Close heavy GUI apps to free RAM ─────────────────────────────────
# Use osascript "quit" — graceful, saves state. Never SIGKILL.
# DO NOT close: Finder, Mail (needs to be open for email fetch), Reminders,
#               Calendar (EventKit doesn't need app, but no harm leaving),
#               Obsidian (you may be using it), Claude.
HEAVY_APPS=(
    "Google Chrome"
    "Safari"
    "Firefox"
    "Slack"
    "Discord"
    "Spotify"
    "zoom.us"
    "Microsoft Teams"
    "Preview"
    "TextEdit"
    "Numbers"
    "Pages"
    "Keynote"
)
freed_count=0
for app in "${HEAVY_APPS[@]}"; do
    if pgrep -fi "/Applications/${app}.app" > /dev/null 2>&1; then
        osascript -e "tell application \"$app\" to quit" 2>/dev/null && \
            log "  Closed: $app" && freed_count=$((freed_count + 1))
    fi
done
log "Step 1: Closed $freed_count heavy app(s)"
sleep 2

# ── Step 2: Mount NAS if not mounted ─────────────────────────────────────────
NAS_USER="ericmanchester"
NAS_HOST="DS1621plus._smb._tcp.local"
NAS_SHARE="home"

NAS_TOUCH_LOG="$VAULT_HOME/Vault/System/Logs/Touch/NAS Check.md"

nas_write_check() {
    # Prove the mount is alive and writable by appending a canary entry.
    # Returns 0 on success, 1 on failure.
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    printf -- "- %s — NAS check good\n" "$ts" >> "$NAS_TOUCH_LOG" 2>/dev/null
}

if [ ! -d "$NAS_PATH" ]; then
    log "Step 2: NAS not mounted — attempting unattended remount via mount_smbfs..."

    # Pull credentials from macOS Keychain (stored when you last manually mounted)
    NAS_PASS=$(security find-internet-password -s "$NAS_HOST" -a "$NAS_USER" -w 2>/dev/null)

    if [ -z "$NAS_PASS" ]; then
        log "ERROR: No keychain entry for $NAS_USER@$NAS_HOST — cannot remount unattended"
        log "  Fix: security add-internet-password -s '$NAS_HOST' -a '$NAS_USER' -w 'YOUR_PASSWORD'"
        exit 1
    fi

    mkdir -p "$NAS_PATH"
    # URL-encode the password in case it contains special characters
    NAS_PASS_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$NAS_PASS")
    mount_smbfs "//${NAS_USER}:${NAS_PASS_ENC}@${NAS_HOST}/${NAS_SHARE}" "$NAS_PATH" 2>/dev/null

    if [ ! -d "$NAS_PATH" ] || ! ls "$NAS_PATH" > /dev/null 2>&1; then
        log "ERROR: NAS remount failed — aborting"
        exit 1
    fi
    log "  NAS remounted successfully (unattended)"
else
    log "Step 2: NAS already mounted at $NAS_PATH"
fi

# Live write-check: proves mount is responsive and writable, not just present as a directory.
if nas_write_check; then
    log "  NAS write-check OK (Touch/NAS Check.md)"
else
    log "ERROR: NAS write-check failed — mount may be stale, aborting"
    exit 1
fi

# Validate symlinks point to NAS (laptop migration can corrupt these)
for link in Vault Inbox Processed; do
    target=$(readlink "$VAULT_HOME/$link" 2>/dev/null)
    if [ -z "$target" ] || [ ! -d "$VAULT_HOME/$link" ]; then
        log "ERROR: $link symlink broken (target: '$target') — aborting"
        exit 1
    fi
    case "$target" in
        /Volumes/home/MacMiniStorage/*) ;;  # OK
        *) log "WARN: $link points to unexpected target: $target" ;;
    esac
done
log "  Symlinks OK: Vault, Inbox, Processed"

# ── Step 3: Ensure Ollama is running ─────────────────────────────────────────
if ! pgrep -x ollama > /dev/null 2>&1; then
    log "Step 3: Ollama not running — starting via brew services..."
    brew services start ollama > /dev/null 2>&1
    sleep 5
    if ! pgrep -x ollama > /dev/null 2>&1; then
        log "ERROR: Ollama failed to start"
        exit 1
    fi
    log "  Ollama started"
else
    log "Step 3: Ollama already running"
fi

# ── Step 4: Ensure today's DLY exists (NEVER overwrite) ──────────────────────
TODAY=$(date +%Y-%m-%d)
YEAR=$(date +%Y)
MONTH=$(date +%m)
DAY_NAME=$(date +%A)
WEEK=$(date +%V)
LONG_DATE=$(date +"%B %d, %Y")
YESTERDAY=$(date -v-1d +%Y-%m-%d)
TOMORROW=$(date -v+1d +%Y-%m-%d)
DLY_DIR="$VAULT_HOME/Vault/Daily/$YEAR/$MONTH"
DLY_FILE="$DLY_DIR/$TODAY-DLY.md"

mkdir -p "$DLY_DIR"

if [ -f "$DLY_FILE" ]; then
    log "Step 4: DLY exists — not touching: $DLY_FILE"
else
    log "Step 4: Creating DLY: $DLY_FILE"
    cat > "$DLY_FILE" <<TEMPLATE
---
date: $TODAY
day: $DAY_NAME
week: $WEEK
tags: [daily]
energy:
focus:
---

# $DAY_NAME, $LONG_DATE

## Morning
<!-- morning-start -->

### Calendar
<!-- For now, manually add today's meetings here -->

### Tasks Due Today

\`\`\`tasks

not done

due today

sort by priority

\`\`\`

### Overdue Tasks

\`\`\`tasks

not done

due before today

sort by due

\`\`\`

### Next 7 Days
\`\`\`tasks

not done

due after today

due before in 7 days

sort by due

\`\`\`


### Overnight Results
<!-- Populated by overnight_processor.py at 11 PM -->

<!-- morning-end -->

---

## Evening
<!-- evening-start -->

### Reflection


### Tomorrow


<!-- evening-end -->

---

## Overnight Processing
<!-- overnight-start -->
<!-- overnight-end -->

---

## Navigation
<< [[Daily/$YEAR/$MONTH/$YESTERDAY-DLY|Yesterday]] | [[Daily/$YEAR/$MONTH/$TOMORROW-DLY|Tomorrow]] >>

---

## Captures

TEMPLATE
fi

# ── Step 5: Source environment ───────────────────────────────────────────────
if [ -f "$VAULT_HOME/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$VAULT_HOME/.env"
    set +a
    log "Step 5: .env sourced (ANTHROPIC_API_KEY + OLLAMA_* exported)"
else
    log "Step 5: WARN — no .env file at $VAULT_HOME/.env"
fi

log "──── preflight OK ────"
exit 0
