---
name: Plaud inbox processor (clean_md_processor.py)
description: Design, behavior, and operational notes for the Plaud file consolidation pipeline built 2026-03-25
type: project
---

**Built:** 2026-03-25 at `System/Scripts/clean_md_processor.py`

**What it does:** Scans `Inbox/Plaud/MarkdownOnly/`, groups files by session base name, generates an AI summary from the SRT transcript, assembles a consolidated `-Full.md` note, writes it to `Vault/Notes/`, and moves all source files to `Processed/Plaud/`.

**Grouping logic:** Split on LAST `-` in filename stem to get (session_base, suffix_type). Known suffix types with internal hyphens (e.g., `Scene-Based Script Summary`) are matched first (longest-match, from SECTION_ORDER) before falling back to last-dash split — this prevents `Scene-Based Script Summary` from being split at its internal hyphen.

**LLM strategy:** Anthropic API (`claude-haiku-4-5-20251001`, max_tokens=1024) → Ollama (`qwen2.5:7b`) fallback → placeholder text. Transcript capped at 40,000 chars before sending.

**Output format:** YAML frontmatter + `# Title` + `## AI Summary` + ordered note sections (SECTION_ORDER priority) + `---` dividers + collapsible `<details>` Full Transcript section (starts collapsed). Transcript includes absolute datetime stamps (`2026-04-01 00:23 → 00:30`) derived from filename date + SRT timestamps. Quality gate: sessions with fewer than 5 substantive segments skip the transcript section.

**Idempotency:** Skips sessions whose `{base_name}-Full.md` already exists in `Vault/Notes/`. Safe to re-run.

**Reprocess mode (`--reprocess`):** Reads source files from `Processed/Plaud/` instead of inbox. Sets `force=True` (overwrites existing `-Full.md`) and `move_sources=False` (leaves sources in place). Filtered to sessions that already have an existing `-Full.md` directly in `Vault/Notes/` — sessions without output or whose output was relocated to a subdirectory are skipped. Use case: re-run AI summarization after fixing API key.

**Public API:** `run_orchestration(session_filter=None, dry_run=False, reprocess=False) -> dict` — used by `morning_workflow.py` and intended for `routes/ingest.py` (once `orchestration_system_start.py` is built).

**CLI flags:** `--dry-run`, `--session FILTER`, `--reprocess`, `--repair`, `--verbose`

**Repair mode (`--repair`):** Scans all of `Vault/**/*-Full.md` recursively (excluding System/, Templates/, Daily/) for files missing the `<details>` transcript section. Finds matching SRT in `Processed/Plaud/`, formats with absolute timestamps, and appends. Idempotent — skips files that already have a transcript. Quality gate applied. Called automatically by `overnight_processor.py` every night to catch files processed on iOS or before the feature existed.

**stdout markers for morning_workflow.py parser:**
- `📭 No files found in inbox` — empty inbox
- `📊 Summary: / • Input: / • Groups: / • Output:` — completion stats

**Run history:**
- **2026-03-25 (first run):** 20 sessions, 73 source files. NAS `Errno 57` socket drop at session 12 failed 9 sessions; re-run after NAS reconnected processed all 10 remaining cleanly. All inbox files cleared.
- **2026-03-31 (Haiku test):** 28 sessions, 0 errors, 28 summaries written, all files moved to Processed/Plaud. Took ~75 min.
- **2026-03-31 (Haiku production run):** 0 sessions pending (inbox empty). Pipeline idempotent and ready for daily scheduling.
- **2026-04-04 (transcript feature):** Added collapsible `<details>` Full Transcript with absolute datetime stamps. Verified on 04-01 Channel Assembly session. 4 of 5 existing Full.md files need `--reprocess` to get transcript sections. 86 SRT sessions in Processed/ are candidates for reprocess.

**Pending action:** Run `python System/Scripts/clean_md_processor.py --repair` on Mac Mini to backfill transcripts on ~80 relocated Full.md files (recursive scan now covers all of Vault/). The 5 sessions in Vault/Notes/ were already reprocessed 2026-04-04 with fresh AI summaries + transcripts.

**Why:** `morning_workflow.py` referenced this script at line 391 but it never existed. 73 Plaud files had been sitting in the inbox unprocessed.

**How to apply:** When inbox has Plaud files, run `python System/Scripts/clean_md_processor.py` from `~/theVault` with venv active. If it fails partway, just re-run — idempotency handles it.
