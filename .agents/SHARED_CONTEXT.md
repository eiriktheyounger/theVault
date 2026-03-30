# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
| CLI Opus | Priority plan, file organization, classifier design | memory files, CLAUDE.md, SHARED_CONTEXT.md | 2026-03-30 |
| Sonnet Desktop | **Building classify_content.py** | System/Scripts/Workflows/classify_content.py, rag_data/classification.db | 2026-03-30 |

## Decisions Made

- **2026-03-26**: Gmail pipeline remaining build work → Sonnet Desktop (Pro plan, not CLI API). Full context at `Vault/System/DesktopClaudeCode/gmail_pipeline_context.md`

## Handoffs

- **Gmail pipeline → Sonnet Desktop**: Test with real emails, run inbox_processor.py, backdate summaries. Read `gmail_pipeline_context.md` first.
