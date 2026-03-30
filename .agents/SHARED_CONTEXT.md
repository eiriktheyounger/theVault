# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
| CLI Opus | Priority plan, file organization, classifier design | memory files, CLAUDE.md, SHARED_CONTEXT.md | 2026-03-30 |
| Sonnet Desktop | **Building classify_content.py** | System/Scripts/Workflows/classify_content.py, rag_data/classification.db | 2026-03-30 |

## Decisions Made

- **2026-03-26**: Gmail pipeline remaining build work → Sonnet Desktop (Pro plan, not CLI API). Full context at `Vault/System/DesktopClaudeCode/gmail_pipeline_context.md`
- **2026-03-30**: Post-ingest file organization DONE — 47 files organized from Notes/ into HarmonicInternal/, Personal/, Knowledge/, Reference/
- **2026-03-30**: Content classifier (classify_content.py) design locked — Haiku API, SQLite DB, markdown manifest review, learning feedback loop

## Handoffs

- **Gmail pipeline → Sonnet Desktop**: Test with real emails, run inbox_processor.py, backdate summaries. Read `gmail_pipeline_context.md` first.
- **classify_content.py → Sonnet Desktop**: Full build spec provided in chat. DB at rag_data/classification.db, manifest at Vault/System/ClassificationReview.md. See prompt in Opus CLI session for full spec.
