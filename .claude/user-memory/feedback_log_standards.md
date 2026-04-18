---
name: Log file standards — Obsidian-readable, Vault-stored
description: Future log files should be Markdown in /Vault so they're readable in Obsidian and accessible via Obsidian sync when away from Mac Mini
type: feedback
---

Log files should be stored in `~/theVault/Vault/` (NAS-backed), written as Markdown, and structured so they render well in Obsidian.

**Why:** Obsidian sync makes Vault files accessible remotely. Local `System/Logs/` files are invisible when away from the Mac Mini.

**How to apply:**
- New log files go in `~/theVault/Vault/System/Logs/` (not `~/theVault/System/Logs/`)
- Write as `.md` with human-readable formatting (headers, bullet lists, or simple tables)
- Do NOT retroactively move existing logs — apply going forward only
- Also ensure RAG indexer excludes the Vault logs directory from chunking (it's operational noise, not knowledge)
