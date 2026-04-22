---
name: Rolling Dashboard — past/future unified view
description: SHIPPED 2026-04-20. Narrative-only 3-section dashboard (Today / Last Full Week / Last Full Month), wired into morning_workflow Step 3. Tasks and calendar stay on DLY per Eric's spec change.
type: project
originSessionId: continued-from-d779d3e3
---

# Rolling Dashboard — SHIPPED (2026-04-20)

## Status: Live

- **Script**: `System/Scripts/generate_rolling_dashboard.py` (905 LOC)
- **Output**: `Vault/Dashboard/Rolling_Dashboard.md` (single overwritten file)
- **Wiring**: `morning_workflow.py::_step_create_dashboard()` — step 3 calls `run_dashboard(ref_date=target_date, use_llm=True)` inline. Legacy `generate_daily_dashboard.py` still runs first best-effort; step passes if either succeeds.
- **Scope per Eric's 2026-04-20 revision**: narrative-only 3 sections — Today / Last Full Week / Last Full Month. Tasks and calendar DELIBERATELY excluded (they live on the DLY, not the dashboard).

## Bugs fixed during ship

1. **F-string regex quantifier bug** (`generate_rolling_dashboard.py::_extract_section`). `{1,4}` in f-string evaluated as Python tuple `(1, 4)` not regex quantifier. Day-summary extraction had silently returned `""` for every call. Fixed to `{{1,4}}`. Now extracts 505 chars.
2. **`VAULT_ROOT` path bug** (`generate_weekly_summary.py`). `PROJECT_ROOT = Path(__file__).parent.parent` produced `~/theVault/System/Vault` — wrong. Fixed to `VAULT_ROOT = Path.home() / "theVault" / "Vault"`. Orphan WKY/MTH files moved to correct `~/theVault/Vault/Daily/YYYY/MM/` locations.
3. **`generate_monthly_summary` return-shape mismatch**. Returned bare `Path`; callers (evening_workflow step 5, overnight_processor) called `.get()` on it → `'PosixPath' object has no attribute 'get'`. Fixed to return `{"status": ..., "path": Path(...)}` matching weekly generator shape.
4. **Apostrophe-tolerant day-summary stripper**. `re.sub(r"^#+ Day'?s? Summary\s*\n?", ...)` catches "Day Summary" and "Day's Summary" headings emitted by overnight LLM.
5. **March MTH regenerated**. After path fix, `python3 System/Scripts/generate_weekly_summary.py --monthly --date 2026-03-15` produced 2211 notes / 39 completed tasks aggregated (was 0/0 against wrong root).

## Known-open (follow-up task spawned) — RESOLVED 2026-04-21

- ~~**W16 WKY aggregation**: produces "No daily notes found for this week"~~ — **RESOLVED**. Root cause was NOT an aggregation bug. `generate_weekly_summary.py` lines 209–211 short-circuit with `{"status": "exists"}` if the WKY file already exists. The orphan WKY-16 moved from `System/Vault/...` (buggy output from the wrong-root run) was blocking regeneration. Fix: `rm ~/theVault/Vault/Daily/2026/04/2026-W16-WKY.md`, then re-run `python3 System/Scripts/generate_weekly_summary.py --weekly --date 2026-04-15 --verbose`. Result: 115 notes / 18 completed / 5 open aggregated. Dashboard's "Last Full Week" now shows real LLM-generated narrative. (2026-04-21)

## Known limitations (not bugs)

- **Dashboard pulls entire WKY/MTH content** including empty Calendar Overview tables and truncated Vault Activity. Narrative-only per Eric's spec would trim to just `## Summary`. Minor polish, not blocking.
- **March MTH shows "No weekly summaries found"** in its Weekly Rollup — because March WKY files don't exist (system only started producing WKYs in April; March ones never ran). Would require backfilling March WKYs, out of scope.

## Commit history

- `62b07a0` (auto) — generate_rolling_dashboard.py (+114) and generate_weekly_summary.py (+46) captured the bug fixes
- `c0f9c8e` — "Wire rolling dashboard into morning workflow (Step 3)" — morning_workflow.py wire-in

## Verification

```bash
cd ~/theVault && source .venv/bin/activate
python3 System/Scripts/generate_rolling_dashboard.py
cat ~/theVault/Vault/Dashboard/Rolling_Dashboard.md
# → 3 sections, Today pulls Apr 18 (most recent completed), Month shows 2211 notes
```

Step 3 test:
```bash
python3 -c "import sys; sys.path.insert(0,'System/Scripts'); sys.path.insert(0,'System/Scripts/Workflows'); from morning_workflow import MorningWorkflow; wf=MorningWorkflow(date='2026-04-20'); print('ok' if wf._step_create_dashboard() else 'FAIL')"
# → ok
```

---

## Original plan (archived below for reference)

# Rolling Dashboard — Plan (2026-04-19)

## User intent

Eric wants one view that answers "where am I, where have I been, what's next":
- Last week summary (synthesis) + key moments
- Last month summary (synthesis) + key moments
- **Rolling ±7 days** — 7 days behind (per-day briefs) + 7 days ahead (events, tasks, commitments)

This is a **presentation/aggregation layer**, not new content generation. All sources already exist.

---

## What already exists (no need to rebuild)

| Source | File pattern | Status |
|---|---|---|
| Daily captures + AI summary + tasks | `Vault/Daily/YYYY/MM/YYYY-MM-DD-DLY.md` | Populated nightly by overnight_processor |
| Weekly summary | `Vault/Daily/YYYY/MM/YYYY-WNN-WKY.md` | Generated Sundays by evening_workflow → `generate_weekly_summary.py` |
| Monthly summary | `Vault/Daily/YYYY/MM/YYYY-MM-MTH.md` | Generated 1st of month by overnight_processor |
| Calendar events | macOS EventKit via `calendar_daily_injector.py` | Injects into DLY morning workflow |
| Task inventory | `task_normalizer.py` + Reminders sync | Maintained nightly |
| Vault activity | `daily_vault_activity.py` | Per-DLY `## Vault Activity` section |
| Email activity | `email_thread_ingester/daily_note_writer.py` | Per-DLY `## Email Activity` section |
| Evening reviews | `Vault/TimeTracking/YYYY/MM/Evening_Review_YYYY-MM-DD.md` | Subjective reflections |
| Existing daily dashboard | `generate_daily_dashboard.py` (160 lines) | Minimal — today's open tasks + recent activity only |

**Gap**: Nothing unifies these into a single past/present/future view. WKY and MTH files exist but must be opened individually. No forward-looking aggregation. No "key moments" extraction.

---

## Dashboard structure (the output file)

**Target path**: `Vault/Dashboard/Rolling_Dashboard.md` (single overwritten file) + optionally `Vault/Dashboard/archive/YYYY-MM-DD-dashboard.md` snapshots if Eric wants history.

**Layout**:

```markdown
# Rolling Dashboard — {generated_date}

> Auto-generated. Last update: {timestamp}. Regen with `python System/Scripts/generate_rolling_dashboard.py`.

---

## 🔮 Next 7 Days — {start} to {end}

### Confirmed events
- **{weekday} {date}** — {event title} ({time}) [{calendar}]
- ...

### Open tasks due this window
- [ ] {task} 📅 {due} [[source-DLY]]
- ...

### Coming up further out (next 30 days, key items only)
- {date} — {event or commitment}

---

## 📅 This Week So Far — {monday} to today

{LLM-generated 3-5 sentence synthesis drawn from past 7 DLY summaries + today's captures}

### Key moments
- **{date}** — {one-line highlight} [[DLY]]
- ...

### Day-by-day (last 7 days)
- **{weekday} {date}** — {DLY summary one-liner} · {task count} · {email count}

---

## 📆 Last Full Week — Week {N}, {dates}

{Existing WKY summary pulled in verbatim, or a 2-3 sentence extract if too long}

[[YYYY-WNN-WKY|Full weekly summary]]

---

## 🗓️ Last Full Month — {month name}

{Existing MTH summary pulled in verbatim, or a 3-5 sentence extract}

### Month key moments
- {highlight}
- ...

[[YYYY-MM-MTH|Full monthly summary]]

---

## 📊 At a glance

- **Open tasks**: {N total} ({M overdue})
- **Active projects**: {list from priorities file}
- **Active job applications**: {list from Vault/Notes/Email/Job Search/*/\_Index.md}
- **Last RAG index rebuild**: {timestamp}

---

<!-- rolling-dashboard-end -->
```

---

## Data flow

```
                    ┌──────────────────────────────────┐
                    │  generate_rolling_dashboard.py   │
                    └──────────────────────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
    ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
    │   BACKWARD    │        │    FORWARD    │        │     META      │
    │               │        │               │        │               │
    │ • Last 7 DLY  │        │ • EventKit    │        │ • Task counts │
    │ • Last 30 DLY │        │   (next 7d)   │        │ • Projects    │
    │ • Last WKY    │        │ • EventKit    │        │ • Job apps    │
    │ • Last MTH    │        │   (next 30d)  │        │ • RAG state   │
    │ • Evening     │        │ • Open tasks  │        │               │
    │   Reviews     │        │   with 📅     │        │               │
    └───────┬───────┘        └───────┬───────┘        └───────┬───────┘
            │                        │                        │
            └────────────────────────┼────────────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │   Synthesis (Haiku)              │
                    │   • Week synthesis (3-5 sent)    │
                    │   • Key moments extraction       │
                    │   • One-liner per day            │
                    └──────────────────────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │ Vault/Dashboard/                 │
                    │   Rolling_Dashboard.md           │
                    └──────────────────────────────────┘
```

---

## Implementation phases

### Phase 1 — Scaffolding (no LLM, deterministic only)
Build `System/Scripts/generate_rolling_dashboard.py` that:
- Reads past 7 DLYs, extracts their existing `### Day Summary` and `### Tasks Extracted` sections
- Reads last complete WKY (previous Sunday-ending week) and MTH (previous month)
- Reads EventKit for next 7 days and next 30 days (reuse from `calendar_daily_injector.py`)
- Pulls open tasks with `📅` due dates from all DLYs in next 7 days
- Writes `Vault/Dashboard/Rolling_Dashboard.md` with sections populated from raw source material (no LLM synthesis yet)

**Acceptance**: File generated in < 5 seconds, content is correct raw aggregation, sections may be a bit long/unfiltered.

### Phase 2 — LLM synthesis layer
Add Haiku calls for:
- **Week-so-far synthesis**: 3-5 sentence summary of past 7 DLYs. One call, ~1500 input tokens, ~200 output.
- **Key moments** (last week): Extract up to 5 highlights from past 7 DLYs. Structured output: `[{date, moment, source_file}]`. One call.
- **Key moments** (last month): Same pattern over MTH content. One call.
- **One-liner per day**: For each of the past 7 days, extract a single-sentence summary. Seven calls OR one batched call returning array.

Total: ~3-10 Haiku calls per dashboard run. Cheap (<$0.01).

**Acceptance**: Synthesis is readable, non-repetitive, actually extracts meaningful moments rather than generic summaries.

### Phase 3 — At-a-glance metadata
Add deterministic pulls for:
- Task totals from `task_normalizer` output
- Active projects from `project_priorities_2026_03.md` (parse P0/P1/P2 sections)
- Active job apps by scanning `Vault/Notes/Email/Job Search/*/\_Index.md`
- RAG index freshness from `.rag_last_index.json` or equivalent

**Acceptance**: Metadata section updates without hardcoded values.

### Phase 4 — Scheduling + UI entry points
- Regenerate on every overnight_processor completion (append to existing cron chain, reuse existing state)
- Regenerate on every morning_workflow step 1
- Optional: add to the FastAPI server as `/api/dashboard` endpoint returning markdown, so the existing React UI can render it

**Acceptance**: Dashboard file has timestamp within the last ~12 hours at any given moment.

---

## Token economics

Per dashboard generation:
- Phase 1 aggregation: 0 tokens
- Phase 2 synthesis: ~5k input + ~1k output = **~$0.01 Haiku**
- Phase 3 metadata: 0 tokens

At 2 regenerations/day (overnight + morning), cost = **~$0.02/day** = **~$7/year**. Negligible.

---

## What NOT to do

- **Don't re-summarize DLYs that already have `### Day Summary`.** They were already summarized by overnight_processor. Reuse the existing text. LLM only runs on the *aggregate* (week-so-far synthesis, key moments), not on re-summarizing individual days.
- **Don't rebuild WKY/MTH logic.** Pull the existing files verbatim or extract their first paragraph. `generate_weekly_summary.py` already does the heavy LLM work once per week/month.
- **Don't add new data sources yet.** TimeTracking/ Evening_Review files are a potential Phase 5 input but add complexity. Ship without them first.
- **Don't snapshot daily unless Eric asks.** Single overwritten file is simpler; add archive/ later if trend analysis becomes useful.

---

## Build delegation (optimal token routing)

| Phase | Model | Why | Estimated effort |
|---|---|---|---|
| Phase 1 (scaffolding, file I/O, EventKit reuse, markdown assembly) | **Sonnet** | ~250-350 lines, non-trivial path handling, calendar integration. Worth Sonnet quality. | 1 session |
| Phase 2 (LLM synthesis prompts + output parsing) | **Sonnet** | Prompt design + JSON parsing guards. Can ride alongside Phase 1. | Combined with Phase 1 |
| Phase 3 (metadata pulls — deterministic parsers) | **Haiku** | Mechanical. Each parser is 20-30 lines. | 1 short session after Phase 1/2 land |
| Phase 4 (cron wiring, API endpoint) | **Haiku** | Mechanical integration. | 1 short session |
| Verification (end-to-end dry run, sample output review) | **Haiku** | Run script, check output file, report anomalies. | 1 short session |

**Recommended execution sequence**:
1. Fix the overnight_processor vault_activity bug first (blocks nothing, but running the dashboard on top of a broken overnight is pointless — the DLY summaries won't be fresh).
2. Sonnet builds Phase 1+2 in one session.
3. Review output with Eric before Phase 3.
4. Haiku lands Phase 3+4 in one session.

---

## Prerequisites / prep before build

- Confirm `calendar_daily_injector.py` has a reusable function for "EventKit events in date range" that can be imported by the dashboard. If not, factor it out first.
- Confirm the WKY and MTH file naming convention (`YYYY-WNN-WKY.md` and `YYYY-MM-MTH.md` per `generate_weekly_summary.py` docstring).
- Decide: single overwritten file vs. daily snapshots. Default recommendation: single file, add snapshots later only if Eric asks.
- Decide: Dashboard path. Default recommendation: `Vault/Dashboard/Rolling_Dashboard.md` (new directory, Obsidian-pinnable).

---

## Cross-references

- Overnight processor bug must land first: `project_overnight_processor_bug_2026_04_19.md`
- Weekly/monthly summary generator: `System/Scripts/generate_weekly_summary.py`
- Calendar injection: `System/Scripts/calendar_daily_injector.py`
- Existing minimal dashboard (to be superseded or renamed): `System/Scripts/generate_daily_dashboard.py`
- Priorities source for at-a-glance: `~/.claude/projects/-Users-ericmanchester-theVault/memory/project_priorities_2026_03.md`

---

## Open questions to resolve before Sonnet build

1. **Key moments — definition.** "Breakthrough interview," "decision made," "new project started"? Or just "emotionally-weighted sentence"? Need 1-sentence rubric for the Haiku prompt.
2. **Evening_Review inclusion.** Include Evening_Review files as a synthesis input, or treat them as private and leave out? Default: leave out for now.
3. **Past 30 days context.** Do we want a condensed "last 30 days" bar between "last week" and "last month"? Or is WKY + MTH enough? Default: no, stick to 7d / full-last-week / full-last-month.
4. **Snapshot retention.** If we add daily snapshots later, how long? Default: 90 days rolling.
