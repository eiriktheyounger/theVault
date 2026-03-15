#!/bin/bash
# NAS mount check — call before any cron job or automated process
NAS_PATH="/Volumes/home/MacMiniStorage"
VAULT_PATH="$NAS_PATH/Vault"

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
