---
name: Daily Vault Activity Tracker
description: daily_vault_activity.py built 2026-04-01 — scan vault changes, extract glossary, enrich tags, inject into daily notes. Email ingester moved to Vault/Notes/Email/.
type: project
---

## Daily Vault Activity Tracker — BUILT 2026-04-01

**File**: `System/Scripts/daily_vault_activity.py` (~855 lines)

### What It Does (3 phases)
1. **SCAN**: Walk `Vault/` for `.md` files modified since last run (`.vault_activity_state.json`)
2. **POST-PROCESS**: Glossary extraction → merge into `Vault/System/glossary.md`. Tag enrichment via LLM → update frontmatter + `System/Config/tags.yaml`. Action item extraction.
3. **INJECT**: `## Vault Activity` section with `<!-- vault-activity-start/end -->` markers into DLY files

### Key Design Decisions
- Plaud files: backdate to frontmatter `date:` field (meeting date), not processing date
- Email threads: post-processed for glossary/tags but OMITTED from backlinks (already in `## Email Activity`)
- Dual-LLM: Anthropic Haiku → Ollama qwen2.5:7b → skip
- Max 10 tags per file, priority-ordered, matched against growing registry
- Action items stamped with `📅 {date + 7 days}`

### Email Ingester Changes (same session)
- `config.EMAIL_DIR` changed: `Vault/Email/` → `Vault/Notes/Email/`
- Added existing-thread vault_path check in `_process_thread()` before routing
- All wikilinks and downstream paths auto-update from config

### Integration
- `overnight_processor.py`: calls `run_vault_activity(days=1)` after existing processing
- `morning_workflow.py`: calls `run_vault_activity(days=1, extract_tasks=False)` in step 4

### CLI
```bash
python System/Scripts/daily_vault_activity.py --dry-run --verbose --days 7
python System/Scripts/daily_vault_activity.py --start-date 2026-03-01 --end-date 2026-03-31
python System/Scripts/daily_vault_activity.py --no-tasks --no-tags
```

### Known Issues
- ✅ `ANTHROPIC_API_KEY` now set in crontab + .bash_profile + .env (2026-04-01). Next runs will use Haiku.
- Ollama occasionally returns malformed JSON (non-fatal, graceful skip)
- Bug fixed: LLM tasks list could contain ints → `str()` cast added

**Why:** Fills three gaps: no vault-wide activity in daily notes, no glossary pipeline, no tag enrichment. `morning_workflow.py` had placeholder "Extracting tags and glossary terms..." label with no implementation.

**How to apply:** This is the post-processing pipeline. Any new content type that enters the vault gets glossary/tags/daily-note coverage automatically by writing `.md` files to `Vault/`.
