# Build Prompt: Add Date Range + Limit to Email Thread Ingester

## Task
Add `--start-date`, `--end-date`, and `--limit` parameters to the email thread ingester so Eric can control batch size and date windows. This prevents Exchange AppleScript timeouts by limiting iteration scope.

## Files to Modify (2 files only)

### 1. `System/Scripts/email_thread_ingester/applescript_bridge.py`

**Changes needed:**

A) Update `extract_exchange_vault_emails()` signature:
```python
def extract_exchange_vault_emails(
    start_date: str | None = None,   # "YYYY-MM-DD"
    end_date: str | None = None,     # "YYYY-MM-DD"
    max_messages: int = 99999,
) -> list[dict]:
```

B) Update `extract_gmail_vault_emails()` with same signature.

C) Update `extract_job_emails()` with same signature.

D) Modify `_EXCHANGE_SCRIPT` AppleScript template to accept these as injected variables. The key optimization: **Mail.app returns messages newest-first, so once we hit a message with `date received` before `start_date`, we can `exit repeat`** — this is what kills the timeout.

Template approach — replace the hardcoded scripts with a function that builds the script string:

```python
def _build_exchange_script(start_date: str | None, end_date: str | None, max_messages: int) -> str:
    # Inject AppleScript date variables at the top of the script
    date_filter_setup = ""
    date_check_before = ""
    date_check_after = ""

    if start_date:
        # AppleScript date comparison: "date \"2026-03-01\""
        date_filter_setup += f'    set startDate to date "{start_date}"\n'
        # Since messages are newest-first, once we pass start_date, stop
        date_check_before = """
            set msgDate to date received of theMsg
            if msgDate < startDate then exit repeat
"""

    if end_date:
        date_filter_setup += f'    set endDate to date "{end_date}"\n'
        date_check_after = """
            if msgDate > endDate then
                -- Skip messages newer than end_date (keep iterating)
            else
"""

    counter_setup = f"    set msgCount to 0\n    set maxMsgs to {max_messages}\n"
    counter_check = """
            set msgCount to msgCount + 1
            if msgCount > maxMsgs then exit repeat
"""
    # ... build the full script with these injected
```

**IMPORTANT AppleScript date gotcha**: AppleScript date parsing from strings is locale-dependent. The safest format is `date "YYYY-MM-DD"` but test this. If it fails, use:
```applescript
set startDate to current date
set year of startDate to 2026
set month of startDate to 3
set day of startDate to 1
set hours of startDate to 0
set minutes of startDate to 0
set seconds of startDate to 0
```

E) Apply same pattern to `_GMAIL_SCRIPT` and `_JOB_SCAN_SCRIPT_TEMPLATE`. For Gmail (`_VAULT_IMPORT` is small), the date filter is for controlling what gets processed, not performance. For job scan, it prevents scanning ancient emails.

F) Update `_run_applescript()` — increase timeout dynamically based on limit:
```python
timeout = min(240, max(60, max_messages // 10))  # Scale timeout with batch size
```
Actually, keep 240s as the ceiling. The date-based early exit is the real fix.

### 2. `System/Scripts/email_thread_ingester/__main__.py`

**Changes needed:**

A) Add CLI args to `_build_parser()`:
```python
p.add_argument(
    "--start-date",
    metavar="YYYY-MM-DD",
    default=None,
    help="Only process emails received on or after this date",
)
p.add_argument(
    "--end-date",
    metavar="YYYY-MM-DD",
    default=None,
    help="Only process emails received on or before this date",
)
p.add_argument(
    "--limit",
    type=int,
    default=99999,
    help="Max messages to extract per account (default: 99999)",
)
```

B) Update `run_orchestration()` signature:
```python
def run_orchestration(
    accounts: list[str] = ("Exchange", "Gmail"),
    job_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    max_messages: int = 99999,
    dry_run: bool = False,
    verbose: bool = False,
    update_daily: bool = True,
) -> dict:
```

C) Pass through to extraction calls in Step 1:
```python
if "Exchange" in accounts:
    raw_messages.extend(
        applescript_bridge.extract_exchange_vault_emails(
            start_date=start_date, end_date=end_date, max_messages=max_messages
        )
    )
if "Gmail" in accounts:
    raw_messages.extend(
        applescript_bridge.extract_gmail_vault_emails(
            start_date=start_date, end_date=end_date, max_messages=max_messages
        )
    )
```

D) Wire CLI args in `main()`:
```python
stats = run_orchestration(
    accounts=accounts,
    job_filter=args.job,
    start_date=args.start_date,
    end_date=args.end_date,
    max_messages=args.limit,
    dry_run=args.dry_run,
    verbose=args.verbose,
    update_daily=not args.no_daily,
)
```

E) Validate date format in `main()` before calling orchestration:
```python
import re
for date_arg, name in [(args.start_date, "--start-date"), (args.end_date, "--end-date")]:
    if date_arg and not re.match(r"\d{4}-\d{2}-\d{2}$", date_arg):
        parser.error(f"{name} must be YYYY-MM-DD format")
```

## Testing

After building, test with:

```bash
cd ~/theVault && source .venv/bin/activate

# Gmail with date range (should work fast, small mailbox)
python -m System.Scripts.email_thread_ingester --account Gmail --start-date 2026-03-01 --end-date 2026-03-31 --dry-run --verbose

# Exchange with limit (the real test — should NOT timeout)
python -m System.Scripts.email_thread_ingester --account Exchange --start-date 2026-03-01 --limit 200 --dry-run --verbose

# Both with date range
python -m System.Scripts.email_thread_ingester --start-date 2026-03-01 --dry-run --verbose
```

## Do NOT modify
- Any other files in the package
- config.py, tracking_db.py, thread_grouper.py, etc.
- CLAUDE.md or memory files

## Reference
- Full architecture plan: `ResumeEngine/.claude/worktrees/naughty-shaw/.claude/plans/delegated-questing-lagoon.md`
- Current applescript_bridge.py and __main__.py are the only files to touch
