---
name: Project priorities 2026 Q1/Q2
description: Locked priority map (P0-P3) for all active theVault projects. Updated 2026-04-13. P0-P2 complete. Active: Gemma 4 integration (6 build sessions). Open: RAG Q/A gate.
type: project
originSessionId: d779d3e3-81e8-4d10-bd15-33a7d93732e7
---
## Project Priority Map — Updated 2026-04-13

### P0 — Must proceed ASAP

1. **Overnight processor stabilization + expansion** — ✅ STABLE as of 2026-04-03
   - ✅ Fix: sys.path missing cwd → task_normalizer import (fixed 2026-03-28)
   - ✅ Fix: ## Captures regex wrong lookahead → now captures to end-of-file (fixed 2026-03-28)
   - ✅ Fix: task_reminders_sync.py Phase 1 bidirectional sync BUILT 2026-04-04. `sync_completions_from_reminders()` implemented + wired into task_normalizer.py Step 7.5.
   - ✅ Cron: reminders sync runs 4x daily at midnight, 6am, noon, 6pm
   - ✅ Fix: ANTHROPIC_API_KEY added to crontab + .bash_profile + .env files (fixed 2026-04-01)
   - ✅ Expand scan: `daily_vault_activity.py` BUILT 2026-04-01 — scans all Vault/ directories, Plaud date backdating solves creation-date challenge
   - ✅ Fix: morning_workflow.py loads `~/theVault/.env` at module top via `_load_dotenv()` (fixed 2026-04-03) — fixes "No LLM service responded" errors in subprocess spawns

2. ✅ **Resume Engine / JD Analyzer** — BUILT 2026-03-28. `jd_analyzer.py` in condescending-mccarthy worktree. DraftKings: ready to run. See `project_jd_analyzer.md`.

3. ✅ **clean_md_processor.py real-run validation** — DONE 2026-03-31. Initial: 20 sessions (2026-03-25, NAS error fixed by re-run). Follow-up: 28 sessions (2026-03-31 Haiku). Total: 48 Plaud sessions processed, 0 errors.

4. ✅ **orchestration_system_start.py** — BUILT 2026-04-02. Runs Plaud + email ingest pipelines. Import fixed in routes/ingest.py.

5. ✅ **Post-ingest file organization** — DONE 2026-03-30. 47 files organized from Notes/ into HarmonicInternal/ (by client/project), Personal/ (interviews by company, finance, family, reflections, stories), Knowledge/Strategy/, Reference/. Organization pattern: `Space/FocusedSpace/[data-driven breakdown]/file`. Notes/ now clean (landing zone only).

### P1 — Enables daily workflows (sequenced)

6. ✅ **Email Thread Ingester** — BUILT 2026-03-31 + FIRST PRODUCTION RUN 2026-04-01. 156 msgs → 53 threads, 0 errors. Output: `Vault/Notes/Email/`. Job indexes for TCGplayer, DraftKings, Nebius. See `project_email_ingester.md`.
6b. ✅ **Exchange AppleScript timeout** — RESOLVED 2026-03-31 via `--start-date` + AppleScript early-exit (Mail.app newest-first). Use `--start-date YYYY-MM-DD --limit 200` for monthly Exchange batches.
6c. ✅ **Daily Vault Activity Tracker** — BUILT 2026-04-01. `daily_vault_activity.py` scans all Vault/ changes, extracts glossary, enriches tags via LLM, injects `## Vault Activity` into DLY files. Wired into overnight_processor.py + morning_workflow.py.
6d. ✅ **ANTHROPIC_API_KEY** — Added to crontab + .bash_profile + .env files (2026-04-01). All cron jobs and scripts now have access.
7. ✅ **Services/ directory** — BUILT 2026-04-02. start_all.py, stop_all.py, emergency_kill.py. Manages Ollama + RAG server.
8. **Calendar sync** (sync_calendar.py) — DEFERRED. Morning workflow Step 2 now gracefully skips when missing. Re-add when calendar integration is needed.
9. ✅ **Daily dashboard** (generate_daily_dashboard.py) — BUILT 2026-04-02. Aggregates open tasks + vault activity into TimeTracking/.

### P2 — Important, build incrementally

10. ✅ **Bidirectional Reminders sync** — COMPLETE + PRODUCTION TESTED 2026-04-04. Steps 7.5/7.6/7.7 in task_normalizer.py. Reminders done→Obsidian ✅, new Reminders→DLY, Obsidian done→delete Reminder. Runs 4x daily.

11. ✅ **ML content organization pipeline** — PRODUCTION TEST COMPLETE 2026-04-04. 98 files classified: 92 ACCEPT, 6 REVIEW. Manifest reviewed by user — Final paths corrected on ~90 rows (receipts → `Personal/Finance/Receipt/YYYY/MM`, Anthropic emails → `Personal/Nouns/Anthropic/Email/`, therapist → `Personal/Health/Mental/Doctors/Jessica`, etc.). Sonnet verified all 98 rows parse correctly, all source files exist, special chars safe. 4 REVIEW rows still need Final paths. Ready for `--apply` which logs all corrections to classification.db for ML learning loop.

11. ✅ **RAG full rebuild** — DONE 2026-03-30. 53,381 vectors in FAISS (up from 42,293, +26%). Coverage 95.8%. batch_reindex.py, 10/10 batches clean. Q/A gate still missing (rag_qa_agent.py not found).

12. ✅ **RAG Q/A gate** — BUILT 2026-04-14. `System/Scripts/rag_qa_agent.py` with 18 test cases, Haiku grader, markdown report, exit codes (0/1/2). Quality gate ready for production.

13. ✅ **RAG index rebuild (100%)** — DONE 2026-04-13. 61,903/61,903 chunks (100% coverage). Root cause: EMBED_CTX context window. Solution: EMBED_CTX=512. Previous 95.8% coverage superseded.

### ✅ COMPLETE — Gemma 4 Integration (6 build sessions)

**Status:** ALL 6 SESSIONS COMPLETE (2026-04-14). Validated by Opus (Session 6), 52 capabilities verified, 0 regressions.
**Details:** `project_gemma4_integration.md` + `Vault/Sessions/gemma4-integration/build-plan.md`

### P3 — Valuable, not blocking

14. **LinkedIn Content Strategy** — 7 pillars mapped, Pillar 7 (neurodivergence) research done. Files: `Vault/Knowledge/Plans for writing/LinkedIn/`. Needs brain dump session when ready. Sonnet Desktop for writing.
15. **RAG Q/A gate** — Still missing. Defer until after Gemma 4.

### P2 FAST-FOLLOW — ResumeEngine scoring migration to Gemma 4 (added 2026-04-15)

16. **Migrate `jd_analyzer.py` `score_category()` from Haiku → Gemma 4 E4B (local Ollama)** — Part of theVault project. Scoring is numerical relevance (0-100 + one-line reason), doesn't need Haiku-level intelligence. Benefits: (a) eliminates API dependency for highest-volume step (~30 calls per JD batch), (b) free inference, (c) unattended batches survive API outages, (d) keeps Haiku budget for JD parse + banned-word rewrites and Sonnet for resume generation.
    - **Scope**: Replace `score_category()` API call with Ollama `/api/chat` call to `gemma4:e4b` at `http://localhost:11434`. Keep same JSON output contract. Add `_strip_thinking()` for Gemma 4 thinking-tag removal (already exists in `System/Scripts/RAG/llm/server.py`).
    - **Prerequisites**: Phase 1-3 fixes complete (done 2026-04-15 — token budget, retry, logging, fmt_items, batch-failure log). Those give resilience; migration builds on that baseline.
    - **Who**: Sonnet Desktop or Sonnet CLI (code change ~40 lines plus structured output parsing guard)
    - **Test plan**: Run all 3 JDs in `ResumeEngine/jds/` after migration, compare top-5 scored roles/projects/skills vs Haiku baseline. Acceptance: ≥80% overlap in top-5 items per category, no JSON parse failures across all 5 categories × 3 JDs = 15 scoring calls.
    - **Keep Haiku for**: `parse_jd()` (structured JD extraction), `fix_banned_words()` (mechanical substitution — Haiku correctness matters for voice compliance).
    - **Keep Sonnet for**: `generate_resume()` (creative writing, voice matching).

### Parking Lot — Ideas to keep, not act on yet

_This is the "distraction catcher." Good ideas that would pull focus from active work. Review monthly._

- LinkedIn article writing / Substack
- Plaud/ directory buildout (empty, unclear need)
- Morning workflow `_step_organize_files` (disabled)
- **PDF/PowerPoint Slide Processor** — E4B vision, ~300 lines, makes presentations searchable (spec at `Post-Gemma4-Integration.md`)
- **Speechify-like TTS reader** — macOS `say` / Whisper / Coqui TTS for reading documents + web pages. Word/sentence highlighting for follow-along. Simple, document-focused variant (not full Speechify clone). Explore: macOS AVSpeechSynthesizer (free, built-in), or whisper.cpp for higher quality.
- Photo/screenshot/receipt inbox processing (vision API pattern)
- Whiteboard capture → diagrams + action items
- **Tailscale remote control page** — once Tailscale is running, build a simple authenticated web page to trigger major processes (morning, evening, ingest, reindex, sync) from phone/laptop remotely

**Why this structure:** Eric tends to rabbit-hole on interesting ideas. Parking lot prevents losing them while keeping execution focused on what moves the needle.

**How to apply:** When Eric brings up a new idea, check if it fits an existing priority or belongs in the parking lot. Don't start new work outside P0-P1 without explicit decision to reprioritize.
