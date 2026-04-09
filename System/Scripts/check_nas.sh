#!/bin/bash
# NAS mount check — call before any cron job or automated process
# On non-Mac-Mini machines (laptop), skips NAS check and validates local Vault symlink instead.

COMPUTER_NAME=$(scutil --get ComputerName 2>/dev/null || hostname)
NAS_PATH="/Volumes/home/MacMiniStorage"
VAULT_HOME="$HOME/theVault"
VAULT_PATH="$VAULT_HOME/Vault"

# ── Laptop mode: skip NAS, check Vault symlink resolves ──────────────────────
if [[ "$COMPUTER_NAME" != *"Mac mini"* && "$COMPUTER_NAME" != *"Mac Mini"* ]]; then
    if [ -d "$VAULT_PATH" ]; then
        echo "LAPTOP OK: Vault accessible at $VAULT_PATH"
        exit 0
    else
        echo "ERROR: Vault not accessible at $VAULT_PATH — check Obsidian Sync or symlink"
        exit 1
    fi
fi

# ── Mac Mini mode: require NAS mount ─────────────────────────────────────────
if [ ! -d "$NAS_PATH" ]; then
    echo "ERROR: NAS not mounted at $NAS_PATH"
    exit 1
fi

if [ ! -d "$VAULT_PATH" ]; then
    echo "ERROR: Vault directory not found at $VAULT_PATH"
    exit 1
fi

echo "NAS OK: $NAS_PATH"
echo "Vault OK: $(ls $VAULT_PATH | wc -l) items"
exit 0
