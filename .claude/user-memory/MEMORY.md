# Memory Index

## User
- [user_profile.md](user_profile.md) — Eric, power user building local-first AI knowledge system; deep familiarity with the codebase; prefers direct, autonomous execution over check-ins
- [user_job_search_criteria.md](user_job_search_criteria.md) — Active job search: IC only, $208K+ base, escape Harmonic ASAP, coding is a stretch, travel fine, startup risk acceptable if comp fits

## Feedback
- [feedback_style.md](feedback_style.md) — Batch approvals, autonomous execution, terse output, absolute NAS paths, NAS Errno 57 re-run strategy
- [feedback_focus.md](feedback_focus.md) — Eric rabbit-holes on interesting ideas; use parking lot pattern, keep execution on locked priorities
- [feedback_memory_sync.md](feedback_memory_sync.md) — "Update memory" means ALL sync points: CLI memory, SHARED_CONTEXT, Desktop context, CLAUDE.md — not just CLI-side
- [feedback_model_delegation.md](feedback_model_delegation.md) — Opus plans/orchestrates, Sonnet builds complex code, Haiku handles mechanical edits + verification. Minimize token cost.
- [feedback_haiku_session_end.md](feedback_haiku_session_end.md) — Don't ask "what next?" at session end; wait for explicit direction or execute autonomously on P0/P1 work

## Project
- [project_priorities_2026_03.md](project_priorities_2026_03.md) — **Locked priority map (P0-P3) + parking lot.** Most P0-P2 done. Laptop migration COMPLETE 2026-04-10. Open: rag_qa_agent.py. Updated 2026-04-10.
- [project_vault_architecture.md](project_vault_architecture.md) — theVault system architecture, key paths, ports, services. Multi-machine setup COMPLETE 2026-04-10: Mac Mini + MacBook Air (lap3071). Updated 2026-04-10.
- [project_cleanup_2026_03.md](project_cleanup_2026_03.md) — March 2026 cleanup: what's archived, what's canonical, gap status (updated as gaps close)
- [project_plaud_processor.md](project_plaud_processor.md) — clean_md_processor.py: Plaud inbox pipeline built 2026-03-25, design, first-run notes, remaining gaps
- [project_jd_analyzer.md](project_jd_analyzer.md) — ResumeEngine JD Analyzer built 2026-03-28: CLI, models, context structure, worktree location
- [project_email_ingester.md](project_email_ingester.md) — Email Thread Ingester BUILT + PRODUCTION RUN COMPLETE 2026-04-01: 156 msgs → 53 threads, 0 errors. Exchange timeout resolved. ANTHROPIC_API_KEY now set.
- [project_applescript_bridge_test.md](project_applescript_bridge_test.md) — AppleScript Mail.app extraction test (2026-03-31): Gmail ✅, Exchange ✅ (resolved via --start-date early-exit). Both accounts: 188 msgs → 61 threads, 0 errors.
- [project_repeating_tasks.md](project_repeating_tasks.md) — Repeating tasks draft list (daily, weekly, 1-2wk): home, gym, networking. Needs clarification + scheduling.
- [project_vault_activity_tracker.md](project_vault_activity_tracker.md) — Daily Vault Activity Tracker BUILT 2026-04-01: scan→glossary→tags→daily injection. Email ingester moved to Vault/Notes/Email/.

- [project_task_management.md](project_task_management.md) — Stale task cleanup rule (>10 days → `-- text`, applied 2026-04-04: 112 tasks/20 files) + bidirectional Reminders sync Phase 1 proposal
- [project_evening_workflow_2026_04_09.md](project_evening_workflow_2026_04_09.md) — Evening workflow production run April 4-8 COMPLETE: 5 dates, 0 errors, Evening_Review files generated. Overnight processor task extraction issues resolved (Ollama timing, April 8 race condition).
- [project_rag_index_rebuild_2026_04_13.md](project_rag_index_rebuild_2026_04_13.md) — **✅ CURRENT** RAG index rebuild COMPLETE 2026-04-13: 61,903/61,903 chunks (100% coverage). Root cause: EMBED_CTX context window was primary bottleneck. Solution: EMBED_CTX=512 (down from 1024) → 0% skip rate. Previous attempt (94.8%) archived as reference.

## Project (Desktop Claude Code)
- [project_desktop_claude_dirs.md](project_desktop_claude_dirs.md) — Scripts dir and Vault data dir for Desktop Claude Code sessions
- [project_gmail_pipeline.md](project_gmail_pipeline.md) — SUPERSEDED 2026-03-31 by Email Thread Ingester. Old gmail/ scripts kept as reference only.

## Project (Job Search)
- [project_job_eval_batch_2026_04_01.md](project_job_eval_batch_2026_04_01.md) — First batch: 6 JDs evaluated. Akamai Principal TSA #1, TwelveLabs SA #2, Paramount passed. Rankings + action items.

- [project_chatbot_rebuild.md](project_chatbot_rebuild.md) — Chatbot rebuild 2026-04-02: unified /api/query, multi-model (Ollama+Claude), OpenDyslexic UI, entity graph wired in
- [project_gemma4_integration.md](project_gemma4_integration.md) — Gemma 4 E4B integration: Session 0 planning COMPLETE (9 docs), 6 build sessions planned, memory optimizations, PDF vision post-build

## Reference
- [ref_key_files.md](ref_key_files.md) — Authoritative files and their locations in theVault. Updated 2026-04-03: added Services/, orchestration, dashboard, query endpoint, Claude API client.
