# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
| CLI Opus (naughty-shaw) | Built auto-sync system: sync_session_state.sh, PostToolUse/Stop hooks, SESSION_STATE.md. Updated all 4 sync points. | settings.json, sync_session_state.sh, CLAUDE.md, CONTEXT.md, SESSION_STATE.md | 2026-03-30 |
| CLI Sonnet (condescending-mccarthy) | OPERATIONS-INDEX.md updates, RAG full rebuild (53,381 vectors, 95.8%) | OPERATIONS-INDEX.md, memory files, SHARED_CONTEXT.md | 2026-03-30 |
| Sonnet Desktop | **Building classify_content.py** | System/Scripts/Workflows/classify_content.py, rag_data/classification.db | 2026-03-30 |

## Decisions Made

- **2026-03-26**: Gmail pipeline remaining build work → Sonnet Desktop (Pro plan, not CLI API). Full context at `Vault/System/DesktopClaudeCode/gmail_pipeline_context.md`
- **2026-03-30**: Post-ingest file organization DONE — 47 files organized from Notes/ into HarmonicInternal/, Personal/, Knowledge/, Reference/
- **2026-03-30**: Content classifier (classify_content.py) design locked — Haiku API, SQLite DB, markdown manifest review, learning feedback loop
- **2026-03-30**: repair_embeddings.py built — fixes ~5,200 orphan chunks missing FAISS vectors. Run from ~/theVault: `python3 -m System.Scripts.RAG.repair_embeddings --dry-run`
- **2026-03-30**: Vault file organization pattern established: `Space/FocusedSpace/[data-driven breakdown]/file`. HarmonicInternal uses `HarmonicInternal/{Client}/{Project}/`
- **2026-03-30**: RAG full rebuild DONE — 53,381 vectors in FAISS (up from 42,293, +26%). Coverage 95.8% (passes threshold). batch_reindex.py 10/10 batches. Q/A gate still missing (rag_qa_agent.py not found).
- **2026-03-30**: OPERATIONS-INDEX.md updated — added Ingest section, RAG Indexing section, File Classification section; marked classify_content.py live, toc_generator.py EOL'd.

## Handoffs

- **Gmail pipeline → Sonnet Desktop**: Test with real emails, run inbox_processor.py, backdate summaries. Read `gmail_pipeline_context.md` first.
- **classify_content.py → Sonnet Desktop**: Full build spec provided in chat. DB at rag_data/classification.db, manifest at Vault/System/ClassificationReview.md. See prompt in Opus CLI session for full spec.
