---
name: Gmail pipeline build
description: SUPERSEDED 2026-03-31 by Email Thread Ingester (System/Scripts/email_thread_ingester/). Old scripts kept as reference only.
type: project
---

**⚠️ SUPERSEDED 2026-03-31** — The Email Thread Ingester (`System/Scripts/email_thread_ingester/`) handles both Gmail and Exchange with threading, job tracking, and daily backlinks. Use that instead. See `project_email_ingester.md`.

**Status as of 2026-03-26 (archived):** Pipeline designed and smoke-tested, not yet used with real emails.

**Full context doc:** `Vault/System/DesktopClaudeCode/gmail_pipeline_context.md` — read this first, it has script locations, auth details, Gmail label IDs, Vault/Email directory structure, workflow hooks, and next steps.

**Scripts location:** `~/theVault/System/Scripts/Claude Code Desktop Specific/gmail/` (4 scripts: gmail_auth.py, email_to_vault.py, daily_email_summary.py, inbox_processor.py)

**What's left:**
1. Test with real emails — label a few with `_VAULT_IMPORT`, run email_to_vault.py, verify .md output
2. Run inbox_processor.py for interactive inbox zero session
3. Backdate daily summaries once Vault/Email has content
4. Iterate on edge cases (HTML emails, encoding, attachments)

**Build decision (2026-03-26):** Use Sonnet Desktop (Pro plan, flat rate) for all remaining build work — it's interactive test/tweak/retest, no architectural complexity. Do NOT use CLI API sessions for this. Runtime cost is near-zero: email import has no LLM, daily summary uses Ollama local (qwen2.5:7b), Haiku API is fallback only.

**Why:** Minimize API spend. Desktop Pro tokens are sunk cost; CLI tokens are metered. Reserve CLI Opus for cross-repo coordination and architecture decisions.

**How to apply:** When picking up Gmail pipeline work, read the full context doc first, then start testing with real emails in a Sonnet Desktop session.
