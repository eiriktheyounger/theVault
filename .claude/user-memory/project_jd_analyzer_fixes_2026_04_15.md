---
name: ResumeEngine jd_analyzer.py fixes (2026-04-15)
description: Phase 1-3 hardening complete. Dynamic max_tokens, retry wrapper, raw-response logging, fmt_items truncation fix, degraded-parse alert, batch error logs, dotenv override=True. Validated 3/3 JDs.
type: project
originSessionId: d779d3e3-81e8-4d10-bd15-33a7d93732e7
---

# ResumeEngine jd_analyzer.py — Phase 1-3 Hardening (2026-04-15)

## Root cause of the original failure

Batch processing hit `json.JSONDecodeError: Unterminated string starting at: line N col M` on the `projects` scoring call. 18 projects × ~50 output tokens per entry = ~925 tokens, but `max_tokens=1024` left no headroom and truncated mid-reason-string. Haiku returned valid-looking JSON up to the cut point.

## Phase 1 — Dynamic token budgets

| Function | Before | After | Rationale |
|----------|--------|-------|-----------|
| `parse_jd` | 1024 | 2048 | Long JDs yield many skills/keywords |
| `score_category` | 1024 | `max(1024, len(items)*80 + 150)` capped at 8192 | Scales with item count |
| `generate_resume` | 4096 | 8192 | Full resumes hit 5-6k tokens |
| `fix_banned_words` | 4096 | 8192 | Mechanical substitution on full resume |

## Phase 2 — Resilience

### `_call_with_retry(client, *, model, max_tokens, messages, label, max_attempts=3)`

- Exponential backoff: 5s, 10s, 20s with jitter
- Retries on `RateLimitError`, `APIConnectionError`, `APITimeoutError`, and `APIStatusError` with status `429` or `>=500`
- Fails fast on `400/401/403` — no point retrying auth or bad request errors
- All four call sites wrapped: `parse_jd`, `score_category`, `generate_resume`, `fix_banned_words`

### `_log_raw_failure(category, raw, exc)`

Writes to `ResumeEngine/output/_debug/{category}_{timestamp}.txt` with:
- error message
- raw response length
- last 400 chars of the raw response (repr-escaped)
- full raw payload

Enables offline post-mortem without re-running the failing JD.

### `_extract_text(response)`

Guards against empty `response.content` lists. Returns `""` if content missing — lets callers distinguish "empty rewrite" from normal output.

### Dict-wrapped response unwrap

Haiku occasionally returns `{"scores": [...]}` instead of the requested raw array. `score_category` now unwraps any of: `scores`, `items`, `results`, `data`. Raises `ValueError` if dict has none → caught, logged via `_log_raw_failure`, falls through to neutral 50/score fallback.

### Batch error log

In `run_batch`, on any exception: writes `{jd_stem}_error.log` next to the failed JD in `jds/failed/` with timestamp, error message, and full traceback. Stays in version control as a historical record of what went wrong.

## Phase 3 — Prompt quality + degraded-parse alerts

### `fmt_items` truncation caps raised

Original caps were starving Sonnet:
| Category | Before | After |
|----------|--------|-------|
| Roles | 2000 | 12000 |
| Projects | 1500 | 6000 |
| Skills | 1200 | 4000 |
| Awards | 800 | 2000 |
| Patents | 800 | 3000 |

At 2000 chars for roles, the prompt included only ~1 role (role files average ~1800 chars each). Raising to 12000 lets all 6 top-scored roles fit. Total prompt growth is bounded (still well under Sonnet's context window).

### `_degraded: True` flag on parse failure

When `parse_jd` hits `JSONDecodeError`, the fallback dict now carries `_degraded: True`. 

- **Batch mode (`process_single_jd`)**: raises `RuntimeError` → JD moves to `failed/` with error log. Prevents silent generic-resume generation.
- **Single-JD mode (`main`)**: prints loud stderr warning `⚠️ JD PARSE DEGRADED` but continues.

## Environment fix — `load_dotenv(override=True)`

Discovered during validation: shell was exporting `ANTHROPIC_API_KEY=''` (empty string, likely from `.bash_profile`). `load_dotenv` without `override=True` respects the empty value, so the SDK got `''` and failed with `Could not resolve authentication method`.

Fix:
```python
load_dotenv(Path(__file__).parent / ".env", override=True)
load_dotenv(Path(__file__).parent.parent / ".env", override=False)
```

ResumeEngine's own `.env` wins over the shell; the vault-root `.env` fills in anything missing without overwriting the first.

## Validation (2026-04-15 12:10-12:14)

Ran `python3 ResumeEngine/jd_analyzer.py --batch --verbose` against 3 JDs:

- **Advisor360_TechLead.txt** ✓ 116 lines
- **AirBNB_BackEnd_MediaIngest.txt** ✓ 134 lines  
- **Akamai_PrinTechSolArch.txt** ✓ 153 lines

0 JSON parse errors. 0 `output/_debug/` files (no fallbacks triggered). All 5 scoring categories (roles/projects/skills/awards/patents) × 3 JDs = 15 scoring calls, all parsed cleanly at first attempt.

Runtimes: ~80-90s per JD (parse + 5 scoring + Sonnet generation + optional banned-words fix).

## Fast-follow: Gemma 4 E4B scoring migration

Already logged as **priority #16** in `project_priorities_2026_03.md`. The scoring step (`score_category`) is the highest-volume Haiku call (~30 per batch across 3 JDs × 5 categories). Migrating to local Ollama `gemma4:e4b`:
- eliminates API dependency for highest-volume step
- free inference, survives API outages
- keeps Haiku budget for `parse_jd` + `fix_banned_words` (where correctness matters)
- Sonnet stays for `generate_resume` (creative writing)

Acceptance: ≥80% overlap in top-5 items per category vs Haiku baseline, 0 JSON parse failures across 15 scoring calls.

Scope: replace one `client.messages.create` call with `/api/chat` to `localhost:11434`, reuse `_strip_thinking()` from `System/Scripts/RAG/llm/server.py`. ~40 lines.
