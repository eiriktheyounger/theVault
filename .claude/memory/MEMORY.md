# MEMORY.md — theVault Session Memory Index
# Auto-loaded at session start. Keep under 200 lines.
# Topic files in .claude/memory/ hold detailed context.
# Last consolidated: 2026-03-25

## Owner
Eric Manchester. Principal Solutions Architect at Harmonic Inc. (remote, Rockville MD).
26 years streaming media/broadcast/ad tech. 4 Engineering Emmys. 10 patents granted, 3 pending.
Actively job searching: $220K+ base, Principal/Distinguished Engineer IC roles, hybrid DC or remote.
ADHD — needs external scaffolding, not willpower. Kintsugi philosophy. Direct communication preferred.

## Active Job Search
- TCGplayer: REJECTED 2026-03-23
- DraftKings: All rounds complete, awaiting decision (only active opportunity)
- Pipeline critically thin — need to send applications NOW
- Akamai Principal TSA is highest priority from maybe pile (still posted on LinkedIn as of 2026-03-25)
- ResumeEngine being built at ~/theVault/ResumeEngine/
- See: .claude/memory/job-search.md

## System State (2026-03-25)
- RAG server: WORKING (port 5055, all search/chat endpoints functional)
- Task pipeline: WORKING (6 modules, cron at 10 PM)
- Evening workflow: WORKING (self-contained)
- Morning workflow: BROKEN (steps 1-4 missing scripts, only steps 6-7 run)
- Ingest pipeline: MISSING (clean_md_processor.py never built, 65 Plaud sessions waiting)
- Service management: MISSING (entire Services/ directory absent)
- Calendar sync: MISSING (Calendar/ directory absent)
- TOC generation: EOL as of 2026-03-25 (disabled, do not re-enable)
- Full details: Vault/System/SYSTEM-AUDIT-2026-03-25.md

## Current Priorities (in order)
1. Build clean_md_processor.py (unblocks 65 Plaud sessions + resume story bank)
2. Build orchestration_system_start.py (connects /ingest/start API)
3. Build Services/*.py (start_all, stop_all, emergency_kill)
4. Resume Engine JD analyzer (semi-automated resume generation)
5. Send job applications (Akamai, CVS Health, new postings)
6. NAS backup to cloud + Rachel's photo backup (data protection)

## Key Decisions Made
- 2026-03-25: TOC generation permanently disabled
- 2026-03-25: System audit completed — 8 missing scripts, 3 broken scripts identified
- 2026-03-24: All pre-migration proposals (00-18) triaged — most archived as completed
- 2026-03-24: Use case framework adopted (UC-1 through UC-11) replacing proposal system
- 2026-03-24: ResumeEngine directory created at ~/theVault/ResumeEngine/ (parallel to Vault, not inside it)
- 2026-03-22: NeroSpicy to theVault migration confirmed complete
- Architecture: SQLite + FAISS, no Docker, no PostgreSQL, Ollama for local, Claude API for quality

## Topic Files (detailed context in .claude/memory/)
- job-search.md — interview history, application status, pipeline
- vault-architecture.md — system design decisions, what works, what doesn't
- resume-engine.md — Proposal 16 + delta, context file structure, JD analyzer design
- personal-context.md — Rachel, Bella, family situation, health priorities
- session-log.md — append-only log of what each session did

## Planning Documents (in vault)
- Vault/System/2026_3_24 New Architecture Plans/theVault-Consolidated-Planning-Hub.md
- Vault/System/OPERATIONS-INDEX.md
- Vault/System/WORKFLOW-MAP.md
- Vault/System/SYSTEM-AUDIT-2026-03-25.md
- Vault/System/theVault-Assessment-and-Forward-Plan-2026-03-25.md

## Eric's Working Style
- Direct communication, peer-level technical collaboration
- Finish current work before starting new threads
- Accuracy and stability over cost savings
- No cheerleading or validation at expense of accuracy
- "State it, don't prove it" — avoid justification mode under pressure
- ADHD pattern: do great → overcommit → crash → nuke → restart. External scaffolding breaks the cycle.
- Shiny object awareness: if Eric starts a new thread mid-task, gently redirect to current priority

## Session Coordination
- Read .agents/SHARED_CONTEXT.md at session start
- Append your session summary before ending
- Check for active edits before modifying shared files
- Opus decides architecture. Sonnet builds. Haiku extracts and processes.
