# Laptop Migration Plan — theVault

**Created:** 2026-04-05 by CLI Opus (Mac Mini)
**Target:** Desktop Claude Code on MacBook Air
**Model:** Sonnet (primary), Haiku for mechanical checks
**Status:** Mac Mini prep COMPLETE — ready for laptop execution

---

## What Was Done on Mac Mini (COMPLETED)

1. ✅ User memory files (23 files) copied to `theVault/.claude/user-memory/` (git-tracked)
2. ✅ `sync_memory_to_repo.sh` created — auto-copies CLI memory to repo on PostToolUse
3. ✅ `check_nas.sh` updated — hostname-aware, skips NAS on non-Mac-Mini machines
4. ✅ PostToolUse hook updated to run memory sync on context file changes
5. ✅ All changes committed and pushed to origin/main
6. ✅ Plan file created at `.agents/LAPTOP_MIGRATION_PLAN.md`

---

## Laptop Execution Steps

### Step 1 — Git Pull + File Verification (Sonnet)

```bash
cd ~/theVault
git pull origin main
```

Then verify:
1. All scripts exist: `find System/Scripts -name "*.py" | wc -l` (should be 30+)
2. `.claude/user-memory/` has 23 .md files
3. `.claude/settings.json` has hooks (NAS check, auto-commit, memory sync)
4. `.agents/SHARED_CONTEXT.md` exists and has recent dates (2026-04-04+)
5. `CLAUDE.md` exists at repo root
6. Scan for hardcoded paths: `grep -rn "/Volumes/home/MacMiniStorage" System/Scripts/ --include="*.py" | grep -v "check_nas"` — these should all be behind Path.home() / NAS_PATH variables, not hardcoded

### Step 2 — Vault Symlink Setup (Sonnet)

The laptop needs `~/theVault/Vault` to resolve to actual vault content, same as Mac Mini.

**Option A — If on same network as NAS:**
```bash
# Same symlink as Mac Mini
ln -s /Volumes/home/MacMiniStorage/Vault ~/theVault/Vault
ln -s /Volumes/home/MacMiniStorage/Inbox ~/theVault/Inbox
ln -s /Volumes/home/MacMiniStorage/Processed ~/theVault/Processed
```

**Option B — If using Obsidian Sync (traveling/remote):**
```bash
# Point to Obsidian Sync's local copy
# Find where Obsidian stores the vault:
find ~/Library/Mobile\ Documents -name "*.md" -path "*Vault*" 2>/dev/null | head -3
# Or check Obsidian settings for vault path

# Create symlink to Obsidian's local vault copy
ln -s /path/to/obsidian/vault ~/theVault/Vault
```

**Option C — If Obsidian vault is already at ~/theVault/Vault (direct open):**
No symlink needed. Obsidian Sync syncs directly into the repo's Vault/ directory.

**IMPORTANT:** The Vault symlink/directory must exist and contain `Daily/`, `Notes/`, `Personal/`, etc. Verify:
```bash
ls ~/theVault/Vault/Daily/ ~/theVault/Vault/Notes/ ~/theVault/Vault/Personal/
```

For Inbox/ and Processed/ on laptop without NAS: create empty local directories:
```bash
mkdir -p ~/theVault/Inbox/Plaud/MarkdownOnly
mkdir -p ~/theVault/Processed/Plaud
```

### Step 3 — Memory File Sync (Sonnet)

1. Copy git-tracked user memory to Claude Code's expected location:
```bash
mkdir -p ~/.claude/projects/-Users-ericmanchester-theVault/memory/
cp ~/theVault/.claude/user-memory/*.md ~/.claude/projects/-Users-ericmanchester-theVault/memory/
```

2. Verify memory loaded correctly — read the MEMORY.md index:
```bash
cat ~/.claude/projects/-Users-ericmanchester-theVault/memory/MEMORY.md
```
Should show 23+ entries covering user profile, feedback, all project files.

3. Verify SHARED_CONTEXT is current:
```bash
head -15 ~/theVault/.agents/SHARED_CONTEXT.md
```
Should show session table with dates from 2026-04-04+.

4. Verify project priorities are current:
```bash
grep "✅" ~/.claude/projects/-Users-ericmanchester-theVault/memory/project_priorities_2026_03.md | wc -l
```
Should show 10+ completed items.

### Step 4 — Python Environment (Sonnet)

```bash
cd ~/theVault

# Check Python version
python3 --version  # Need 3.12.x

# Create venv if not exists
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify core imports
python3 -c "
import fastapi, anthropic, uvicorn, yaml, frontmatter
import faiss, numpy, sklearn
print('✅ Core packages OK')
"

# Verify EventKit (for calendar mapper)
python3 -c "
try:
    from EventKit import EKEventStore
    print('✅ EventKit OK')
except ImportError:
    print('⚠️  EventKit not available — calendar mapper will not work')
"
```

**Do NOT copy FAISS index or SQLite DB.** Mac Mini is the data/indexing server. Laptop is for Obsidian management, daily workflows, and development.

### Step 5 — Environment Variables (Sonnet)

```bash
# Add to ~/.zshrc (or ~/.bash_profile)
export ANTHROPIC_API_KEY='sk-ant-...'  # Get from Mac Mini's .env

# Also create ~/theVault/.env
cat > ~/theVault/.env << 'EOF'
# theVault environment variables
ANTHROPIC_API_KEY=sk-ant-...
EOF

# Reload
source ~/.zshrc
```

### Step 6 — Check NAS Script Validation (Sonnet)

```bash
# This should succeed on laptop (hostname-aware skip)
bash ~/theVault/System/Scripts/check_nas.sh
# Expected: "LAPTOP OK: Vault accessible at /Users/.../theVault/Vault"

# Full laptop check
bash ~/theVault/System/Scripts/check_vault_laptop.sh
```

Fix any failures before proceeding.

### Step 7 — Script Compatibility Scan (Sonnet)

Run each key script in dry-run or check mode to verify no laptop-specific failures:

```bash
source ~/theVault/.venv/bin/activate

# Task normalizer (reads vault markdown, no NAS needed)
python3 -m System.Scripts.task_normalizer --dry-run

# Classification (reads vault files)
python3 System/Scripts/Workflows/classify_content.py --scan --dry-run --source Vault/Notes/Email/ 2>&1 | head -20

# Clean MD processor (checks inbox — will say empty, that's OK)
python3 System/Scripts/clean_md_processor.py --dry-run

# Calendar mapper test
python3 -c "
from System.Scripts.Workflows.calendar_mapper import CalendarMapper
mapper = CalendarMapper('$HOME/theVault/Vault', calendar_name='Work')
print('✅ CalendarMapper initialized')
"
```

**Expected:** Task normalizer and classify should work. Clean MD processor should report empty inbox. Calendar mapper should init (may need calendar permission grant on first run).

### Step 8 — Calendar Permission Grant (Sonnet)

The calendar mapper uses EventKit which requires macOS calendar permission:

1. Run the calendar mapper once — macOS will prompt for calendar access
2. Grant access in System Settings → Privacy & Security → Calendars
3. Verify: `python3 System/Scripts/Workflows/calendar_mapper.py ~/theVault/Vault Work`

This enables the Plaud recording → calendar meeting connection that was deferred.

### Step 9 — End-to-End Validation (Sonnet)

Run this validation checklist and record results:

```bash
echo "=== theVault Laptop Validation ==="

# 1. Vault accessible
[ -d ~/theVault/Vault/Daily ] && echo "✅ Vault/Daily accessible" || echo "❌ Vault/Daily missing"

# 2. Memory files present
MEM_COUNT=$(ls ~/.claude/projects/-Users-ericmanchester-theVault/memory/*.md 2>/dev/null | wc -l)
echo "Memory files: $MEM_COUNT (expect 23+)"

# 3. Git clean and current
cd ~/theVault && git status --short
echo "Branch: $(git branch --show-current)"
echo "Last commit: $(git log --oneline -1)"

# 4. Python env
source .venv/bin/activate
python3 -c "import fastapi, anthropic; print('✅ Python OK')" 2>/dev/null || echo "❌ Python imports failed"

# 5. API key
[ -n "$ANTHROPIC_API_KEY" ] && echo "✅ ANTHROPIC_API_KEY set" || echo "❌ ANTHROPIC_API_KEY missing"

# 6. NAS check (should pass in laptop mode)
bash System/Scripts/check_nas.sh 2>&1

# 7. Hooks configured
[ -f .claude/settings.json ] && echo "✅ Hooks config present" || echo "❌ Hooks config missing"

# 8. Obsidian daily notes current
LATEST_DLY=$(ls -t Vault/Daily/2026/04/*-DLY.md 2>/dev/null | head -1)
echo "Latest daily note: $LATEST_DLY"
```

### Step 10 — Update LAPTOP_SETUP_GUIDE.md (Haiku)

Rewrite the existing guide (dated March 17, very outdated) to reflect:
- Current symlink setup + Obsidian Sync strategy
- Memory sync via git (`.claude/user-memory/` → `~/.claude/projects/`)
- Hostname-aware check_nas.sh
- What runs on laptop vs Mac Mini only
- Calendar mapper setup + EventKit permissions
- Travel workflow: captures via Obsidian → Obsidian Sync → Mac Mini cron processes overnight
- All new scripts built since March (email ingester, classify, evening workflow, vault activity, Reminders sync)

### Step 11 — Update Memory + SHARED_CONTEXT (Haiku)

Update:
- `project_vault_architecture.md` — add laptop setup, symlink strategy, memory sync
- `project_priorities_2026_03.md` — note laptop migration complete
- `.agents/SHARED_CONTEXT.md` — record laptop setup in Active Work table
- Push changes back via git so Mac Mini gets the updates

---

## Architecture After Migration

```
┌──────────────────────────────────┐     ┌──────────────────────────────┐
│         Mac Mini M4              │     │       MacBook Air            │
│                                  │     │                              │
│  Cron Jobs (overnight, morning)  │     │  Claude Code Desktop         │
│  Ollama (qwen2.5:7b, nomic)     │     │  Obsidian + Obsidian Sync    │
│  RAG Server (port 5055)         │     │  Git workflow                │
│  FAISS + SQLite                 │     │  Script development          │
│  NAS symlinks                   │     │  Task management             │
│  Plaud ingest pipeline          │     │  Calendar mapper (EventKit)  │
│  Email ingester                 │     │  classify_content.py         │
│                                  │     │  JD Analyzer                 │
│  ←── Obsidian Sync ───→         │     │  ←── Obsidian Sync ───→     │
│  ←── Git push/pull ───→         │     │  ←── Git push/pull ───→     │
└──────────────────────────────────┘     └──────────────────────────────┘
                  │                                    │
                  └────── NAS (Vault, Inbox, Processed) ┘
                           (Mac Mini always connected;
                            laptop when on home network)
```

## What Does NOT Work on Laptop

- `overnight_processor.py` — Mac Mini cron only (NAS required)
- `morning_workflow.py` — Mac Mini cron only (Plaud inbox on NAS)
- `clean_md_processor.py` (ingest mode) — needs Inbox/ on NAS
- `batch_reindex.py` — FAISS index on Mac Mini only
- RAG search API — no local DB (use Tailscale to Mac Mini later)
- Reminders sync — AppleScript + PyRemindKit tied to Mac Mini's Reminders

## What DOES Work on Laptop

- Obsidian captures, daily notes, all vault reading/writing
- Claude Code with full memory context
- `classify_content.py --scan` (reads vault files via Obsidian Sync)
- `task_normalizer --dry-run` (reads vault markdown)
- `calendar_mapper.py` (EventKit reads local calendar)
- `jd_analyzer.py` (standalone, Anthropic API)
- `email_thread_ingester/` (if Mail.app configured)
- All git operations
- Script development + testing

---

*Ready for laptop execution. Open Claude Code Desktop on the MacBook Air and follow Steps 1-11.*
