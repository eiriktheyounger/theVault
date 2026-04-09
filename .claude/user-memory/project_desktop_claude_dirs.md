---
name: Desktop Claude Code directories
description: Paths for Claude Code Desktop scripts and vault data storage
type: project
---

Scripts live at: `~/theVault/System/Scripts/Claude Code Desktop Specific/`
Vault data/memory lives at: `~/theVault/Vault/System/DesktopClaudeCode/` (NAS-backed, survives reboots)
NAS Vault symlink: `~/theVault/Vault` → `/Volumes/home/MacMiniStorage/Vault` (DS1621plus /home)

**Why:** Eric created these specifically for Desktop Claude Code to keep scripts organized and persist context across sessions.
**How to apply:** Always put Desktop-specific scripts in the Scripts dir above; write session context/memory to the Vault dir above so it persists on NAS.
