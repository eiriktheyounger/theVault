---
name: Collaboration style preferences
description: How Eric likes to work — batch approvals, autonomous execution, terse output
type: feedback
---

Execute large tasks autonomously and report at natural milestones, not at every sub-step.

**Why:** Eric gives multi-step instructions and approves them in bulk. He does not want to be asked for confirmation at each stage once he's given go-ahead.

**How to apply:** When given a multi-step plan with approval, execute all approved steps fully before reporting. Flag only true blockers (missing files, ambiguous decisions) — not routine progress updates.

---

Do not recap or summarize what was just done at the end of a response unless explicitly asked.

**Why:** "I can read the diff" — Eric reads output directly.

**How to apply:** End responses after the last meaningful action. Skip trailing "Here's what I did" summaries.

---

Use full absolute paths (`/Users/ericmanchester/...`), not `~`, when traversing NAS symlinks in shell commands.

**Why:** `~` expansion does not follow NAS symlinks in the theVault setup; silently returns no results with `find`, and `grep` may also miss files.

**How to apply:** Always expand `~` to `/Users/ericmanchester/` in any shell commands touching `~/theVault/Vault`, `~/theVault/Inbox`, or `~/theVault/Processed`.

---

NAS `Errno 57` (Socket is not connected) during long script runs: just re-run.

**Why:** The Inbox and Processed dirs are NAS-backed symlinks. SMB socket can drop mid-run (observed 2026-03-25 during clean_md_processor first run — failed sessions 12-20 at 12:53:53). All files remain intact on NAS after reconnect.

**How to apply:** If a script reports `[Errno 57] Socket is not connected` for NAS paths, wait for NAS to reconnect and re-run. Scripts with idempotency (like clean_md_processor) will skip already-completed work automatically.
