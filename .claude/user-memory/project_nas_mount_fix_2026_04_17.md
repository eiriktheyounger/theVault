---
name: NAS Unattended Mount Fix (2026-04-17)
description: NAS dropped overnight on 2026-04-17; old remount used Finder GUI (interactive prompt); fixed to use mount_smbfs + macOS Keychain for fully unattended operation
type: project
---

NAS dropped its SMB connection overnight on 2026-04-17. The 06:00 preflight run failed because the existing remount logic used `open "smb://..."`, which triggers a Finder dialog asking for credentials — blocking unattended operation and generating the login prompt Eric saw.

**Fix applied 2026-04-17:** `preflight.sh` Step 2 now uses `mount_smbfs` with the password pulled from macOS Keychain via `security find-internet-password`. No GUI, no prompt, fully unattended.

Keychain entry details:
- Server: `DS1621plus._smb._tcp.local`
- Account: `ericmanchester`
- Created: 2025-02-18 (from first manual mount)
- Retrievable headlessly: confirmed ✅

If NAS password changes, update keychain:
```
security add-internet-password -s "DS1621plus._smb._tcp.local" -a "ericmanchester" -w "NEW_PASSWORD"
```

**Why:** NAS connections can drop during idle overnight periods (sleep, network hiccup). The system must remount without any user present — especially critical when Eric is traveling.

**How to apply:** If preflight NAS remount fails again, first check keychain entry exists and is correct before investigating anything else. If it's a new Mac or keychain was reset, the entry needs to be re-added manually once.
