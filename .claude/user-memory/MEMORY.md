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
- [feedback_log_standards.md](feedback_log_standards.md) — New log files go in Vault/System/Logs/ (NAS-backed, Obsidian-readable, synced remotely). Do NOT retroactively move old logs.
- [feedback_research_first.md](feedback_research_first.md) — **Research-first rule (2026-04-21)**: Before touching a new external resource OR when hitting persistent issues (TCC walls, rate limits, brittle workarounds), search PyPI/GitHub/recent blog posts for well-maintained alternatives. Record the evaluation in project memory under `## Libraries evaluated`. Triggered by Calendar TCC issue — icalPal/Ruby reads Calendar sqlite directly, bypasses TCC entirely.

## Project
- [project_priorities_2026_03.md](project_priorities_2026_03.md) — **Locked priority map (P0-P3) + parking lot.** All P0-P2 complete, Gemma 4 complete. Open: scoring→E4B migration (#16). V2 rebuild in parking lot.
- [project_vault_architecture.md](project_vault_architecture.md) — theVault system architecture, key paths, ports, and services. Ollama models updated (llama3.1:8b removed 2026-04-02). Services/ dir added.
- [project_cleanup_2026_03.md](project_cleanup_2026_03.md) — March 2026 cleanup: what's archived, what's canonical, gap status (updated as gaps close)
- [project_plaud_processor.md](project_plaud_processor.md) — clean_md_processor.py: Plaud inbox pipeline built 2026-03-25, design, first-run notes, remaining gaps
- [project_jd_analyzer.md](project_jd_analyzer.md) — ResumeEngine JD Analyzer: CLI, batch mode, 48 context files, Haiku+Sonnet pipeline
- [project_jd_analyzer_fixes_2026_04_15.md](project_jd_analyzer_fixes_2026_04_15.md) — Phase 1-3 hardening (2026-04-15): dynamic max_tokens, retry+backoff, raw-response logging, fmt_items raised, degraded-parse alert. 3/3 JDs validated.
- [project_resume_engine_phase4_2026_04_16.md](project_resume_engine_phase4_2026_04_16.md) — **Phase 4 (2026-04-16)**: Anti-fabrication — two-stage generator, canonical.yaml, hallucination scanner (caught 69 violations), docx renderer, sanitizer. End-to-end validated. Batch re-run pending API credits.
- [project_email_ingester.md](project_email_ingester.md) — Email Thread Ingester BUILT + PRODUCTION RUN COMPLETE 2026-04-01: 156 msgs → 53 threads, 0 errors. Exchange timeout resolved. ANTHROPIC_API_KEY now set.
- [project_applescript_bridge_test.md](project_applescript_bridge_test.md) — AppleScript Mail.app extraction test (2026-03-31): Gmail ✅, Exchange ✅. Both accounts: 188 msgs → 61 threads, 0 errors.
- [project_repeating_tasks.md](project_repeating_tasks.md) — Repeating tasks draft list (daily, weekly, 1-2wk): home, gym, networking. Needs clarification + scheduling.
- [project_vault_activity_tracker.md](project_vault_activity_tracker.md) — Daily Vault Activity Tracker BUILT 2026-04-01: scan→glossary→tags→daily injection. Email ingester moved to Vault/Notes/Email/.
- [project_task_management.md](project_task_management.md) — Stale task cleanup rule (>10 days → `-- text`, applied 2026-04-04: 112 tasks/20 files) + bidirectional Reminders sync Phase 1 proposal
- [project_evening_workflow_2026_04_09.md](project_evening_workflow_2026_04_09.md) — Evening workflow production run April 4-8 COMPLETE: 5 dates, 0 errors, Evening_Review files generated. Overnight task extraction issues resolved.
- [project_rag_index_rebuild_2026_04_13.md](project_rag_index_rebuild_2026_04_13.md) — **✅ CURRENT** RAG index rebuild COMPLETE 2026-04-13: 61,903/61,903 chunks (100%). EMBED_CTX=512 is the key config.
- [project_chatbot_rebuild.md](project_chatbot_rebuild.md) — Chatbot rebuild 2026-04-02: unified /api/query, multi-model (Ollama+Claude), OpenDyslexic UI, entity graph wired in
- [project_gemma4_integration.md](project_gemma4_integration.md) — Gemma 4 E4B integration: ALL 6 SESSIONS COMPLETE (2026-04-14). 52 capabilities verified, 0 regressions. gemma4:e4b is default model.
- [project_autonomous_ops_2026_04_15.md](project_autonomous_ops_2026_04_15.md) — **Autonomous Mac Mini ops (2026-04-15)**: preflight.sh closes heavy apps, mounts NAS, starts Ollama, creates DLY. All cron entries route through it.
- [project_nas_mount_fix_2026_04_17.md](project_nas_mount_fix_2026_04_17.md) — **NAS unattended remount fix (2026-04-17)**: replaced Finder `open smb://` with `mount_smbfs` + macOS Keychain. Keychain entry confirmed.
- [project_thevault_v2_proposal.md](project_thevault_v2_proposal.md) — **V2 rebuild vision (2026-04-17)**: Proposal #19 at Vault/System/Proposals/19-theVault-V2-Rebuild-Plan.md. Multi-model routing, offline queue, Opus checkpoint. Parking lot — do NOT start without explicit go-ahead.
- [project_overnight_processor_bug_2026_04_19.md](project_overnight_processor_bug_2026_04_19.md) — **Overnight bug diagnosis (2026-04-19)**: Not a silent write failure — vault_activity feedback loop + stale state cursor. `days` param ignored when state exists; state only saves at end-of-run; tag enrichment advances mtime on scanned files. Three-edit Haiku fix documented.
- [project_rolling_dashboard_2026_04_19.md](project_rolling_dashboard_2026_04_19.md) — **Rolling Dashboard SHIPPED 2026-04-20**: narrative-only 3 sections (Today/Last Full Week/Last Full Month) per Eric's scope revision. Tasks+calendar stay on DLY. Wired into morning_workflow Step 3 via `run_dashboard(ref_date, use_llm=True)`. Fixed `generate_weekly_summary.py` VAULT_ROOT path bug + `generate_monthly_summary` return-shape bug. March MTH regenerated (2211 notes/39 tasks). Open: weekly DLY aggregation bug (separate chip).
- [project_forward_back_2026_04_20.md](project_forward_back_2026_04_20.md) — **ADHD/OOSOOM Phase 1b SHIPPED (2026-04-20)**: Forward-Back + Past 7 Days + Recent Context three-section DLY injection with gap detection (72h threshold, P0 events). Wired into morning_workflow + overnight_processor cron. Live EventKit verified by Eric.
- [project_calendar_icalpal_2026_04_21.md](project_calendar_icalpal_2026_04_21.md) — **icalPal fallback SHIPPED (2026-04-21)**: TCC-bypass calendar fetch via Ruby gem (reads Calendar sqlite directly). `calendar_icalpal.py` wrapper + EventKit→icalPal auto-fallback in `calendar_forward_back.py` and `calendar_daily_injector.py`. `THEVAULT_CALENDAR_BACKEND` env override. Requires FDA on parent process (cron/Terminal), not per-app Calendar permission.

## Project (Desktop Claude Code)
- [project_desktop_claude_dirs.md](project_desktop_claude_dirs.md) — Scripts dir and Vault data dir for Desktop Claude Code sessions
- [project_gmail_pipeline.md](project_gmail_pipeline.md) — SUPERSEDED 2026-03-31 by Email Thread Ingester. Old gmail/ scripts kept as reference only.

## Project (Job Search)
- [project_job_eval_batch_2026_04_01.md](project_job_eval_batch_2026_04_01.md) — First batch: 6 JDs evaluated. Akamai Principal TSA #1, TwelveLabs SA #2, Paramount passed. Rankings + action items.
- [project_nebius_interview.md](project_nebius_interview.md) — Nebius AI HM interview pipeline: Josh Liss (founder with exit), prep doc 2026-04-03, founder-to-founder framing required.

## Reference
- [ref_key_files.md](ref_key_files.md) — Authoritative files and their locations in theVault. Updated 2026-04-03: added Services/, orchestration, dashboard, query endpoint, Claude API client.
