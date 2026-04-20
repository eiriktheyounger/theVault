---
name: Update ALL shared memory locations when asked
description: When told to update memory, must update CLI memory + SHARED_CONTEXT + Desktop context (DesktopClaudeCode/) + CLAUDE.md — not just CLI-side files
type: feedback
---

"Update memory" means update ALL cross-session sync points, not just CLI memory files.

**Why:** Eric runs three Desktop sessions (Opus, Sonnet, Haiku) plus CLI. CLI memory files are invisible to Desktop sessions. If only CLI memory is updated, Desktop sessions operate on stale context — defeating the entire purpose of the cross-session architecture.

**How to apply:** When Eric says "update memory" or "update memory files as appropriate," touch ALL of these:
1. CLI memory (`~/.claude/projects/-Users-emanches-theVault/memory/`) — relevant memory files
2. `.agents/SHARED_CONTEXT.md` — active work, decisions, handoffs
3. `Vault/System/DesktopClaudeCode/CONTEXT.md` — Desktop-facing session context
4. `CLAUDE.md` (at repo root) — if any sections are stale (priorities, missing scripts, stats, key paths)

**Note:** On laptop (lap3071), the username is `emanches` (not `ericmanchester`). Memory path: `~/.claude/projects/-Users-emanches-theVault/memory/`. On Mac Mini the path uses the same `emanches` username.

Check each one. Don't assume "memory" means only the CLI memory directory.
