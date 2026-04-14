# Sonnet Session Briefing — RAG Q/A Gate + Calendar Integration

**Date:** 2026-04-14
**Prepared by:** Opus (orchestrator)
**Your role:** Two sequential tasks. Complete Task 1 first, then Task 2.

---

## Task 1: Build `rag_qa_agent.py`

### What It Does

A standalone quality gate script that runs after RAG index rebuilds. It queries the RAG endpoints with test cases and uses Claude Haiku to grade responses. Produces a markdown report and exits with a pass/fail code.

### Location

`System/Scripts/rag_qa_agent.py`

### Interface (must match existing call in batch_reindex.py:179-199)

```python
# Called as: python System/Scripts/rag_qa_agent.py
# From cwd: ~/theVault
# Exit codes: 0=PASS, 1=FAIL, 2=SETUP_ERROR
```

### Requirements

1. **18 test cases across 6 categories** (3 per category):
   - Cross File — multi-document queries
   - Meeting — meeting notes retrieval
   - Personal — personal knowledge queries
   - Proper Noun — named entity recognition (ViewLift, theVault, etc.)
   - Semantic — conceptual understanding
   - Technical — technical documentation

2. **Each test case** has:
   - `query`: the question to send
   - `endpoint`: `/fast` or `/deep`
   - `expected_keywords`: list of terms that should appear in the answer
   - `expected_behavior`: "answer" or "abstain" (some questions should correctly abstain)

3. **Scoring** (per test, 30 points max):
   - R (Relevance, 10): keyword match rate
   - S (Source/Citation, 10): citation quality
   - C (Correctness, 10): Claude Haiku grades answer correctness

4. **Grading**: Use Claude Haiku (`claude-haiku-4-5-20251001`) via `ANTHROPIC_API_KEY` env var. If key not available, exit code 2.

5. **Threshold**: 90% overall (486/540)

6. **Report output**: `Vault/System/Logs/rag_qa/rag_qa_YYYY-MM-DD_HH-MM.md`
   - See existing example at `Vault/System/Logs/rag_qa/rag_qa_2026-03-11_14-08.md` for format

### Test Cases — Use These

Design 18 test cases that test real content in the vault. Good queries to use:
- "What is theVault?" (Proper Noun, /fast)
- "How does the task pipeline work?" (Technical, /deep)
- "What is ViewLift?" (Proper Noun, /fast)
- "SSAI ad insertion across ViewLift and DirtVision" (Cross File, /deep)
- "What meetings about FanDuel?" (Meeting, /fast)
- "What is SCTE-35?" (Technical, /fast)

For the remaining 12, create queries that test entity recognition, semantic understanding, cross-file retrieval, and personal knowledge. The vault has content about: Harmonic work, ViewLift/DirtVision streaming clients, Plaud meeting notes, email threads, task management, daily notes.

### Key Files to Reference

- `batch_reindex.py:179-199` — the calling code (don't modify this)
- `Vault/System/Logs/rag_qa/rag_qa_2026-03-11_14-08.md` — old report format
- RAG endpoints: POST `/fast` with `{"question": "..."}`, POST `/deep` with `{"question": "..."}`
- Server runs on port 5055

### Constraints

- The RAG server must be running for tests (check /healthz first, exit 2 if not)
- Use `httpx` for HTTP calls (already in venv)
- Use `anthropic` SDK for Haiku grading (already in venv)
- Create `Vault/System/Logs/rag_qa/` directory if it doesn't exist
- Keep it under 400 lines

---

## Task 2: Calendar Integration + Weekly/Monthly Summaries

### Full Spec

Read the complete plan at:
`Vault/Sessions/gemma4-integration/calendar-and-summaries-plan.md`

Build all three parts:
- **Part A:** `System/Scripts/calendar_daily_injector.py` — EventKit multi-calendar → DLY `### Calendar` section
- **Part B:** Weekly summary generation (WKY files)
- **Part C:** Monthly summary generation (MTH files)

### Key Details from the Plan

- 8 target calendars (ExchangeCalendar, Gmail, Bella, Alyssa, Lulu, Rachel, Class Schedule, Holidays)
- Reuse `CalendarMapper._get_calendar_events()` pattern from `Workflows/calendar_mapper.py`
- DLY files at `Vault/Daily/YYYY/MM/YYYY-MM-DD-DLY.md`
- WKY files at `Vault/Daily/YYYY/MM/YYYY-WNN-WKY.md` (or per the plan)
- MTH files at `Vault/Daily/YYYY/MM/YYYY-MM-MTH.md` (or per the plan)
- Wire into morning_workflow.py Step 2 (replace the missing sync_calendar.py call)

### When Done

Update `.agents/SHARED_CONTEXT.md` after each task completes.

---

## Context Files

- SHARED_CONTEXT: `.agents/SHARED_CONTEXT.md`
- CLAUDE.md: `~/theVault/CLAUDE.md`
- Calendar plan: `Vault/Sessions/gemma4-integration/calendar-and-summaries-plan.md`
- Old Q/A report: `Vault/System/Logs/rag_qa/rag_qa_2026-03-11_14-08.md`
- batch_reindex.py: `System/Scripts/batch_reindex.py`
