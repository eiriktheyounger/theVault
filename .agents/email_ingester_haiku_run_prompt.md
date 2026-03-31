# Haiku Run Prompt: Email Thread Ingester — Production Run

## Who You Are
You are a **CLI Haiku session** running in `~/theVault`. Your job is to execute the Email Thread Ingester in production and verify results. You have full context access via memory files. Do not over-explain — log what you do and report stats at the end.

## Step 1: Read Context (do this first)

Read these memory files before doing anything else:
- `~/.claude/projects/-Users-ericmanchester-theVault/memory/MEMORY.md` — index
- `~/.claude/projects/-Users-ericmanchester-theVault/memory/project_email_ingester.md` — package status + known issues
- `~/.claude/projects/-Users-ericmanchester-theVault/memory/project_applescript_bridge_test.md` — test history + what flags to use
- `~/.claude/projects/-Users-ericmanchester-theVault/memory/project_priorities_2026_03.md` — confirm P1 #6 is the target

Read `.agents/SHARED_CONTEXT.md` to confirm no other session is actively writing to email files.

## Step 2: Pre-flight Checks

Run all four checks. Abort with a clear message if any fail.

```bash
# 1. NAS
bash ~/theVault/System/Scripts/check_nas.sh

# 2. Venv
cd ~/theVault && source .venv/bin/activate && python --version

# 3. Ollama (fallback if Haiku unavailable)
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; t=json.load(sys.stdin); print('Ollama OK:', [m['name'] for m in t.get('models',[])])"

# 4. ANTHROPIC_API_KEY
python3 -c "import os; k=os.environ.get('ANTHROPIC_API_KEY',''); print('Haiku:', 'SET ('+k[:8]+'...)' if k else 'NOT SET — will use Ollama fallback')"
```

**If ANTHROPIC_API_KEY is not set:** Ollama fallback will run automatically. Summaries will use qwen2.5:7b. This is acceptable — do not abort. Note it in your report.

**If NAS is not mounted:** Abort. Run `bash System/Scripts/check_nas.sh` and ask Eric to remount before retrying.

## Step 3: Dry Run First (verify routing before writing)

```bash
cd ~/theVault && source .venv/bin/activate
python -m System.Scripts.email_thread_ingester \
  --start-date 2026-03-01 \
  --limit 200 \
  --dry-run \
  --verbose \
  2>&1 | tee /tmp/email_ingester_dryrun.log
```

Review the dry-run output for:
- Any routing errors (messages going to `General` that should be `Job Search`)
- Any `[ERROR]` lines
- Stats line at the bottom — confirm extracted/threads/errors look reasonable

**If 0 messages extracted:** Either `_VAULT_IMPORT` mailbox is empty (Gmail) or no vault-tagged Exchange messages since `--start-date`. Check Mail.app and confirm. Do not proceed to production if extracted=0 unless you've verified the mailboxes are actually empty.

**If errors > 0:** Read the error lines. If they are contact/job-tracker errors, those are non-blocking. If they are extraction or write errors, abort and report.

## Step 4: Production Run

Only proceed if dry-run shows 0 errors (or only non-blocking contact/job errors).

```bash
cd ~/theVault && source .venv/bin/activate
python -m System.Scripts.email_thread_ingester \
  --start-date 2026-03-01 \
  --limit 200 \
  --verbose \
  2>&1 | tee /tmp/email_ingester_production.log
```

**Do NOT add `--dry-run`.** This writes real files to Vault.

**Expected runtime:** ~18–25 min if Ollama fallback is active (29s/thread avg × ~50 threads). ~5–8 min if Haiku API is running.

**Monitor:** The log will show `[Finance]`, `[Job Search]`, `[Work]`, `[General]` lines as threads process. Each thread writes one `.md` file. You'll see the summary line at the end:
```
Done. N written, N threads, N errors.
Stats: N extracted | N new | N threads | N written | N errors
```

## Step 5: Verify Output

After production run completes, verify the key outputs:

```bash
# Check files were written
ls ~/theVault/Vault/Email/Job\ Search/ 2>/dev/null
ls ~/theVault/Vault/Email/Finance/ 2>/dev/null
ls ~/theVault/Vault/Email/Work/ 2>/dev/null

# Check today's daily note was updated
cat "$(python3 -c "from datetime import date; d=date.today(); print(f'$HOME/theVault/Vault/Daily/{d.year}/{d.month:02d}/{d.strftime(\"%Y-%m-%d\")}-DLY.md')")" | grep -A 30 "## Email Activity"

# Check contact files were created
ls ~/theVault/Vault/Email/People/ | head -20

# Check job index files
find ~/theVault/Vault/Email/Job\ Search -name "_Index.md" 2>/dev/null
```

If no `## Email Activity` section exists in today's daily note, that's a bug — report it.

## Step 6: Update Shared State

After a successful run, update these two files:

### `.agents/SHARED_CONTEXT.md`
Append to the **Decisions Made** section:
```
- **2026-03-31**: Email Thread Ingester FIRST PRODUCTION RUN — [N] messages extracted, [N] threads written, [N] errors. Summarizer: [Haiku|Ollama]. Vault/Email/Job Search and Vault/Email/Finance populated.
```

Update the **Active Work** table — set CLI Haiku row to reflect completed run.

### Memory file `project_email_ingester.md`
Add a **Production Run History** section at the bottom:
```markdown
**Production Run History:**
- **2026-03-31 (Haiku):** N extracted, N threads, N errors. Summarizer: Haiku/Ollama. Flags: --start-date 2026-03-01 --limit 200.
```

## What NOT to Do
- Do NOT modify any module files (`config.py`, `applescript_bridge.py`, etc.)
- Do NOT run without `--start-date` — Exchange will time out on 2,327 messages
- Do NOT delete or overwrite existing `.md` files in Vault/Email — the writer is idempotent, re-running is safe
- Do NOT run if another session is actively writing to email files (check SHARED_CONTEXT first)

## Error Reference

| Error | Meaning | Action |
|-------|---------|--------|
| `NAS vault not mounted` | NAS down | Abort, ask Eric to remount |
| `AppleScript timed out after 240s` | Exchange ran without `--start-date` | Add `--start-date` |
| `ANTHROPIC_API_KEY not set` | Haiku skipped | OK, Ollama fallback runs |
| `_VAULT_IMPORT mailbox not found` | Gmail mailbox missing | Check Mail.app, not a blocker if Exchange works |
| `No Exchange account found` | Exchange not in Mail.app | Check Mail.app accounts |
| `Could not parse date` | Malformed date in one message | Non-blocking, message skipped |

## Reporting

When done, report to Eric:
1. Stats line (extracted / new / threads / written / errors)
2. Which summarizer ran (Haiku API or Ollama)
3. Any routing decisions that look wrong (threads in wrong category)
4. Whether daily note was updated
5. Whether job index files were created for active companies (DraftKings, Nebius, TCGplayer)
