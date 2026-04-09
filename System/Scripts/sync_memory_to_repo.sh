#!/bin/bash
# sync_memory_to_repo.sh — Copy CLI user-memory files to git-tracked location
# Called by PostToolUse hook or manually to keep memory in sync across machines.
#
# Source: ~/.claude/projects/-Users-ericmanchester-theVault/memory/ (23 files)
# Target: ~/theVault/.claude/user-memory/ (git-tracked)
#
# Usage:
#   bash ~/theVault/System/Scripts/sync_memory_to_repo.sh

set -euo pipefail

SRC_DIR="${HOME}/.claude/projects/-Users-ericmanchester-theVault/memory"
DST_DIR="${HOME}/theVault/.claude/user-memory"

if [ ! -d "$SRC_DIR" ]; then
    echo "No source memory dir at $SRC_DIR — skipping"
    exit 0
fi

mkdir -p "$DST_DIR"

# Copy only if source is newer than destination
CHANGED=0
for f in "$SRC_DIR"/*.md; do
    [ -f "$f" ] || continue
    base=$(basename "$f")
    if [ ! -f "$DST_DIR/$base" ] || [ "$f" -nt "$DST_DIR/$base" ]; then
        cp "$f" "$DST_DIR/$base"
        CHANGED=$((CHANGED + 1))
    fi
done

if [ "$CHANGED" -gt 0 ]; then
    echo "Synced $CHANGED memory file(s) to repo"
else
    echo "Memory files up to date"
fi
