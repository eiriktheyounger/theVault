# Dashboard + Weekly/Monthly Rollup — Proposal

**Created:** 2026-04-09 by CLI Opus (Mac Mini)
**Status:** PROPOSAL — awaiting Eric's answers on 5 questions before build
**Build Model:** Sonnet (script), Haiku (integration)

---

## Concept

Three layers of time-based aggregation in theVault:

### Layer 1: Enhanced Daily Notes (rolling window)
Each daily note gets two new sections:
- **7-Day Lookback**: Key completions, decisions, patterns from past week — distilled, linked
- **Forward View**: Calendar events, task due dates, known deadlines for next 3-5 days

### Layer 2: Weekly Standalone Files
`Vault/Daily/YYYY/MM/WK-##-YYYY-MM-DD-WEEK.md` (ISO week number, Monday start date)
- Aggregates all 7 dailies into key points, key tasks, key decisions
- Links back to each daily note
- Week-over-week trends (tasks completed vs created, meetings, etc.)

### Layer 3: Monthly Standalone Files
`Vault/Daily/YYYY/MM/YYYY-MM-MONTH.md`
- Aggregates weekly files
- Higher-level: themes, project progress, job search pipeline status
- Links back to weeks and notable dailies

### Dashboard Section (in today's daily)
Top of current day's DLY:
- **This week so far** (rolling Mon→today)
- **Last week summary** (links to WEEK.md)
- **Last month summary** (links to MONTH.md)

---

## LLM Strategy (Two-Stage)

**Stage 1 — Ollama qwen2.5:7b (local, $0):**
- Extract key events, decisions, tasks from each daily note
- Pull calendar entries for forward view
- Pull completed/created task counts
- Output: structured JSON per day (~200 tokens each)

**Stage 2 — Claude Haiku API (~$0.01-0.03/week):**
- Takes 7 structured JSONs → weekly narrative + key points
- Takes 4-5 weekly JSONs → monthly narrative
- Pattern recognition: "3 interviews this week", "task backlog grew 15%"
- Fallback: Ollama can do this too, just less insightful

---

## Data Sources

| Source | Location | What It Gives |
|--------|----------|---------------|
| Daily notes | `Vault/Daily/YYYY/MM/*-DLY.md` | Tasks, summaries, vault activity, email activity |
| Evening Reviews | `Vault/TimeTracking/YYYY/MM/Evening_Review_*` | End-of-day reflections, tomorrow priorities |
| Calendar | EventKit via `calendar_mapper.py` | Forward-looking meetings, interviews |
| Task files | `Vault/**/*.md` with `- [ ]` items | Open tasks with `📅` due dates |
| Reminders | PyRemindKit sync | Active reminders with due dates |
| Email threads | `Vault/Notes/Email/**/*.md` | Recent email activity, job search updates |
| Plaud transcripts | `Vault/Notes/**/*-Full.md` | Meeting outcomes, action items |
| Overnight processor logs | Daily task extraction output | What got processed overnight |

---

## Forward View Example

```markdown
### → Next 3 Days
**Thursday Apr 10**
- 📅 3 tasks due (linked)
- 🗓 10:00 AM — Standup (Work calendar)
- 🗓 2:00 PM — Nebius HM Interview with Josh Liss

**Friday Apr 11**
- 📅 1 task due
- 🗓 No meetings scheduled

**Weekend Apr 12-13**
- 📅 Weekly review (repeating)
- No meetings
```

Sources: calendar mapper for meetings, task scanner for 📅 dates, Reminders for due items. All local, no LLM needed — pure data assembly.

---

## Open Questions (Need Eric's Input)

1. **Week start day** — Monday (ISO) or Sunday?
2. **Generation timing** — Weekly file: generated once Sunday night? Or rolling/rebuilt daily? Monthly on the 1st?
3. **Dashboard placement** — Top of daily file (before tasks) or after existing sections?
4. **Forward view horizon** — 3 days? 5 days? Rest of current week?
5. **Forward view density** — Tight links only (`🗓 2PM Nebius HM → [[link]]`) or sentence of context per item?

---

## Build Plan (After Questions Answered)

| Step | Model | What |
|------|-------|------|
| 1 | Sonnet | Create `System/Scripts/weekly_monthly_generator.py` (~400-500 lines) |
| 2 | Sonnet | Add "next N days" query to `calendar_mapper.py` |
| 3 | Sonnet | Enhance daily note template with lookback + forward sections |
| 4 | Haiku | Wire into overnight_processor.py (weekly on Sunday, monthly on 1st) |
| 5 | Haiku | Wire forward view into morning_workflow.py |
| 6 | Haiku | Verification + fixes |

---

*Saved so Desktop Claude Code on laptop can continue this conversation.*
