# Email Thread Ingester — Build Prompt for Sonnet

**Task**: Build `System/Scripts/email_thread_ingester/` package from the architecture plan.
**Plan file**: `ResumeEngine/.claude/worktrees/naughty-shaw/.claude/plans/delegated-questing-lagoon.md`
**Assigned to**: Sonnet (primary builder) + Haiku (extraction testing, high-volume validation)
**Opus role**: Architecture review only — do NOT run this with Opus CLI

---

## Pre-flight

```bash
# 1. Verify NAS
bash System/Scripts/check_nas.sh

# 2. Activate venv
source .venv/bin/activate

# 3. Check SHARED_CONTEXT
cat .agents/SHARED_CONTEXT.md

# 4. Read the full plan
cat ResumeEngine/.claude/worktrees/naughty-shaw/.claude/plans/delegated-questing-lagoon.md
```

## What to Build

Create `System/Scripts/email_thread_ingester/` with these files, in this order:

### Step 1: `config.py`
- All paths as `Path` objects (VAULT_HOME, EMAIL_DIR, PEOPLE_DIR, etc.)
- Constants: MAX_TRANSCRIPT_CHARS=40000, TOPIC_RULES (copy from `System/Scripts/Claude Code Desktop Specific/gmail/email_to_vault.py` lines 41-49)
- Domain-to-org mapping dict (viewlift.com→ViewLift, harmonic.com→Harmonic, nebius.com→Nebius, etc.)
- Job-related domain list for `--job` mode matching

### Step 2: `tracking_db.py`
- SQLite at `System/Scripts/email_thread_ingester/email_tracking.sqlite3`
- Three tables: `processed_messages`, `threads`, `contacts` (see plan Section 5 for schema)
- CRUD functions: `is_message_processed()`, `mark_message_processed()`, `get_thread()`, `upsert_thread()`, `upsert_contact()`
- Use context manager pattern for connections

### Step 3: `applescript_bridge.py`
- Two functions: `extract_exchange_vault_emails()` and `extract_gmail_vault_emails()`
- Both return `list[dict]` with keys: account, mailbox, subject, sender, recipients, date_received, message_id, in_reply_to, headers, body
- Run AppleScript via `subprocess.run(["osascript", "-e", script])`
- **CRITICAL AppleScript rules** (learned from prior session):
  - Exchange mailbox name is `"Inbox"` (capital I), NOT `"INBOX"`
  - Build results via string concatenation, NOT array append (gets error -10006)
  - Message indices are volatile — always capture message-id
  - Date filtering in AppleScript is unreliable — iterate all messages, filter in Python
  - Use `|` as field delimiter, `\n` as record delimiter
- For `--job` mode: `extract_job_emails(domain: str)` scans ALL mailboxes for matching sender domains
- Parse AppleScript output into Python dicts with proper date parsing

### Step 4: `email_parser.py`
- `pip install email-reply-parser` first
- `clean_body(raw_body: str) -> str`: Strip quotes, signatures, disclaimers
- `strip_subject_prefixes(subject: str) -> str`: Remove Re:, FW:, Fwd:, [EXTERNAL], [EXT]
- `html_to_text(html: str) -> str`: Reuse regex pattern from `email_to_vault.py:decode_body()` (lines 90-97)
- `extract_email_address(header: str) -> str`: Reuse from `email_to_vault.py:extract_email()` (line 69-71)
- `extract_name(header: str) -> str`: Reuse from `email_to_vault.py:extract_name()` (lines 74-81)

### Step 5: `thread_grouper.py`
- Input: `list[dict]` (raw extracted messages)
- Output: `list[EmailThread]` (grouped, sorted)
- Dataclasses: `EmailMessage` and `EmailThread` (see plan Section 3)
- Threading priority: Exchange `thread-topic` header → `In-Reply-To`/`References` chain → normalized subject match
- Fork detection: subject contains parent's normalized subject OR References header overlaps
- Sort messages within each thread newest-first

### Step 6: `topic_router.py`
- `route_thread(thread: EmailThread) -> tuple[str, Path]`: Returns (topic_name, directory_path)
- Reuse TOPIC_RULES from config.py
- For Work topics, sub-route by client domain (e.g., viewlift.com → Work/Clients/ViewLift/)
- For Job Search, sub-route by company (e.g., Job Search/Nebius/)
- Default: General/

### Step 7: `summarizer.py`
- Same dual-LLM pattern as `clean_md_processor.py` (read it first: lines 72-75 for the pattern)
- Primary: Anthropic Haiku API (`claude-haiku-4-5-20251001`)
- Fallback: Ollama `qwen2.5:7b` at `localhost:11434`
- Last resort: placeholder text
- Prompt asks for JSON return: summary, key_points (with message anchors), glossary, action_items
- 40,000 char input cap
- Also provide `summarize_for_daily(body: str) -> str`: one-sentence summary of a single message

### Step 8: `markdown_writer.py`
- `render_thread(thread: EmailThread, summary_data: dict, topic: str) -> str`: Full markdown with frontmatter
- `safe_filename(subject: str) -> str`: Reuse from email_to_vault.py
- Template exactly as specified in plan Section 6
- Anchor links: each message gets `<a id="msg-{hash6}">` where hash6 = first 6 chars of md5(message_id)
- Key points reference these anchors

### Step 9: `contact_tracker.py`
- `update_contact(name, email, thread_subject, vault_path, date)`: Create/update People/ files
- Infer organization from email domain using config.DOMAIN_TO_ORG
- Template as specified in plan Section 8

### Step 10: `job_tracker.py`
- `update_job_index(company, threads, contacts)`: Create/update `Job Search/{Company}/_Index.md`
- Extract company from sender domain
- Template as specified in plan Section 9 (Status, Key Contacts, Email Threads, Timeline)
- Activated automatically when topic_router routes to Job Search/

### Step 11: `daily_note_writer.py`
- `inject_email_activity(threads_processed: list, date: datetime)`: Append to daily note
- Daily note path: `Vault/Daily/YYYY/MM/YYYY-MM-DD-DLY.md`
- Format: `## Email Activity` section with Job Search first, then other topics
- Backlinks use `[[path|display name]]` Obsidian syntax
- If section already exists, replace it (idempotent)

### Step 12: `__init__.py` + `__main__.py`
- `run_orchestration(accounts, job_filter, dry_run, verbose, update_daily) -> dict`
- Pipeline: extract → dedup via tracking_db → group threads → route → summarize → write markdown → update contacts → update job indexes → update daily note → update tracking_db
- CLI with argparse: `--dry-run`, `--account`, `--job`, `--no-daily`, `--verbose`
- Logging same pattern as clean_md_processor.py

## Reference Files to READ Before Coding

| Priority | File | What to learn |
|----------|------|---------------|
| 1 | `System/Scripts/clean_md_processor.py` | Architecture pattern, summarizer pattern, logging |
| 2 | `System/Scripts/Claude Code Desktop Specific/gmail/email_to_vault.py` | TOPIC_RULES, extract_email(), extract_name(), safe_filename(), People/ pattern |
| 3 | `System/Scripts/RAG/retrieval/indexer.py` | How chunking works (paragraph boundaries, 800-char) so you optimize the markdown for RAG |
| 4 | The full plan file (path above) | Complete spec with templates and data models |

## Rules
- Use `Path` objects, not strings
- Validate NAS mount before any vault write
- No hardcoded absolute paths — use env vars or Path.home()
- All files in the package — no standalone scripts
- Follow existing code style (see clean_md_processor.py)
- Test after each major step with `--dry-run`

## Verification (run these after building)
```bash
# Dry run — should show threads, paths, no writes
python -m System.Scripts.email_thread_ingester --dry-run --verbose

# Job import dry run
python -m System.Scripts.email_thread_ingester --job nebius --dry-run

# Single account
python -m System.Scripts.email_thread_ingester --account Exchange --dry-run
```
