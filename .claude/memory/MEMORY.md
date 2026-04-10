# MEMORY.md — theVault Session Memory Index
# Auto-loaded at session start. Keep under 200 lines.
# Topic files in .claude/memory/ hold detailed context.
# Last consolidated: 2026-04-10

## Owner
Eric Manchester. Principal Solutions Architect at Harmonic Inc. (remote, Rockville MD).
26 years streaming media/broadcast/ad tech. 4 Engineering Emmys. 10 patents granted, 3 pending.
Actively job searching: $208K+ base, IC only, hybrid DC or remote. Startup risk acceptable if comp fits.
ADHD — needs external scaffolding, not willpower. Kintsugi philosophy. Direct communication preferred.

## Active Job Search
- TCGplayer: REJECTED 2026-03-23
- DraftKings: All rounds complete, awaiting decision
- 12 Labs: Interview scheduled (as of Apr 2026)
- C2C position: Interview completed
- Nebius: Ghosted
- Akamai Principal TSA: #1 ranked from evaluation batch (6 JDs evaluated 2026-04-01)
- ResumeEngine: ~/theVault/ResumeEngine/ — jd_analyzer.py built, batch mode working
- See: .claude/memory/job-search.md

## System State (2026-04-10)
- RAG server: WORKING (port 5055, unified /api/query, multi-model Ollama+Claude)
- Task pipeline: WORKING (6 modules, cron at 11 PM, bidirectional Reminders sync 4x daily)
- Evening workflow: WORKING (4 steps, production tested Apr 4-8, 0 errors)
- Overnight processor: WORKING (task extraction, Plaud transcript repair, fixed Apr 9)
- Morning workflow: WORKING (loads .env, daily vault activity, Plaud ingest)
- Ingest pipeline: WORKING (clean_md_processor.py, 48+ sessions processed, --reprocess mode)
- Service management: WORKING (Services/start_all.py, stop_all.py, emergency_kill.py)
- Content classifier: WORKING (classify_content.py, 98 files classified, hostname-aware)
- Email ingester: WORKING (12-module package, 156 msgs -> 53 threads production run)
- Daily vault activity: WORKING (scan->glossary->tags->daily injection)
- Calendar sync: DEFERRED (morning workflow gracefully skips when missing)
- RAG Q/A gate: MISSING (rag_qa_agent.py not found, quality gate always skipped)
- Multi-machine: COMPLETE (Mac Mini + MacBook Air, 12/12 E2E tests passing)

## Current Priorities (2026-04-10)
1. ~~Build clean_md_processor.py~~ DONE
2. ~~Build orchestration_system_start.py~~ DONE
3. ~~Build Services/*.py~~ DONE
4. ~~Resume Engine JD analyzer~~ DONE
5. ~~Laptop migration~~ COMPLETE 2026-04-10
6. ~~Bidirectional Reminders sync~~ COMPLETE 2026-04-04
7. RAG Q/A gate (rag_qa_agent.py) — still missing
8. Send job applications (Akamai, new postings)
9. LinkedIn Content Strategy (parking lot)
See: .claude/user-memory/project_priorities_2026_03.md for full priority map

## Key Decisions Made
- 2026-04-10: Laptop migration COMPLETE — E2E validated, classify_content.py hostname-aware
- 2026-04-09: Evening workflow Apr 4-8 production run COMPLETE, overnight processor race condition resolved
- 2026-04-04: Bidirectional Reminders sync COMPLETE + production tested
- 2026-04-04: Stale task cleanup (576 tasks/76 files, >10 days -> `-- text`)
- 2026-04-02: Services/, orchestration, dashboard, chatbot rebuild, query endpoint all built
- 2026-04-01: Email ingester first production run (156->53 threads, 0 errors)
- 2026-04-01: Daily vault activity tracker built
- 2026-03-31: Email Thread Ingester built (supersedes old Gmail pipeline)
- 2026-03-30: RAG full rebuild (53,381 vectors, 95.8% coverage)
- 2026-03-30: Post-ingest file organization (47 files organized)
- 2026-03-28: JD Analyzer built
- 2026-03-25: clean_md_processor.py built, system audit completed
- Architecture: SQLite + FAISS, no Docker, no PostgreSQL, Ollama for local, Claude API for quality

## Topic Files (detailed context in .claude/memory/)
- job-search.md — interview history, application status, pipeline
- vault-architecture.md — system design, what works, multi-machine setup
- resume-engine.md — JD analyzer design, context file structure
- personal-context.md — Rachel, Bella, family situation, health priorities
- session-log.md — append-only log of what each session did

## Planning Documents (in vault)
- Vault/System/OPERATIONS-INDEX.md
- Vault/System/WORKFLOW-MAP.md
- Vault/System/SYSTEM-AUDIT-2026-03-25.md (historical reference)
- LAPTOP_SETUP_GUIDE.md (rewritten 2026-04-10)
- .agents/LAPTOP_MIGRATION_PLAN.md (reference)
- .agents/SHARED_CONTEXT.md (cross-session sync)

## Eric's Working Style
- Direct communication, peer-level technical collaboration
- Finish current work before starting new threads
- Accuracy and stability over cost savings
- No cheerleading or validation at expense of accuracy
- "State it, don't prove it" — avoid justification mode under pressure
- ADHD pattern: do great -> overcommit -> crash -> nuke -> restart. External scaffolding breaks the cycle.
- Shiny object awareness: if Eric starts a new thread mid-task, gently redirect to current priority

## Session Coordination
- Read .agents/SHARED_CONTEXT.md at session start
- Append your session summary before ending
- Check for active edits before modifying shared files
- Opus decides architecture. Sonnet builds. Haiku extracts and processes.
