# theVault Laptop Setup Guide

**Status**: MacBook Air (lap3071) — secondary development & capture machine
**Primary Machine**: Mac Mini M4 (~/theVault production, overnight processor, RAG server, Ollama)
**Sync Strategy**: Obsidian Sync (vault content) + Git (code + memory) + Local stubs (Inbox/Processed)
**Last Updated**: April 10, 2026

---

## Architecture Overview

```
Mac Mini M4                              MacBook Air (lap3071)
-----------------------------            ----------------------------
Cron jobs (overnight, morning)           Claude Code Desktop (Opus)
Ollama (qwen2.5:7b, nomic)              Obsidian + Obsidian Sync
RAG Server (port 5055)                   Git workflow
FAISS + SQLite (chunks.sqlite3)          Script development & testing
NAS symlinks (always connected)          Task management (dry-run)
Plaud ingest pipeline                    Calendar mapper (EventKit)
Email ingester                           classify_content.py
Reminders sync (AppleScript)             JD Analyzer
                                         Email thread ingester (Mail.app)
       <---- Obsidian Sync ---->
       <---- Git push/pull ---->
```

---

## What Works on Laptop

- Obsidian daily notes & captures (via Obsidian Sync)
- QuickAdd captures (Cmd+Shift+C)
- Claude Code with full memory context (23 user + 6 project memory files)
- `classify_content.py --scan` (reads vault files)
- `task_normalizer --dry-run` (reads vault markdown)
- `jd_analyzer.py` (Anthropic API)
- `email_thread_ingester/` (if Mail.app configured)
- `calendar_mapper.py` (EventKit reads local calendar)
- All git operations (push/pull syncs with Mac Mini)
- Script development & testing

## What Stays on Mac Mini Only

- `overnight_processor.py` — 10 PM cron, requires NAS + Ollama
- `morning_workflow.py` — cron, requires NAS + Plaud Inbox
- `clean_md_processor.py` (ingest mode) — needs Inbox/ on NAS
- `batch_reindex.py` — FAISS index lives on Mac Mini
- RAG search API — no local DB (future: Tailscale to Mac Mini)
- `task_reminders_sync.py` — AppleScript + PyRemindKit tied to Mac Mini Reminders
- Ollama inference (qwen2.5:7b, nomic-embed-text)

---

## Setup Steps (Fresh Install)

### Step 1: Clone Repository

```bash
cd ~
git clone git@github.com:eiriktheyounger/theVault.git
cd ~/theVault
git status
```

If already cloned:
```bash
cd ~/theVault && git pull origin main
```

**Troubleshooting:**
- "Permission denied (publickey)": `ssh-keygen -t ed25519 && ssh-add ~/.ssh/id_ed25519`

### Step 2: Python Environment

```bash
cd ~/theVault
python3 --version          # Need 3.12.x
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify
python3 -c "import fastapi, anthropic, uvicorn, yaml, frontmatter, faiss, numpy; print('Core packages OK')"
```

### Step 3: Vault Symlink

Obsidian Sync delivers vault content to `~/NeroSpicy/Vault` on this laptop. The symlink makes theVault code work identically to Mac Mini:

```bash
cd ~/theVault
# If Vault is a broken symlink (points to NAS), fix it:
rm Vault 2>/dev/null
ln -s /Users/emanches/NeroSpicy/Vault Vault

# Verify
ls Vault/Daily/2026/04/ | tail -3
```

**Important:** The Vault directory must contain `Daily/`, `Notes/`, `Personal/`, etc.

### Step 4: Inbox & Processed (Local Stubs)

The laptop doesn't have NAS. Create local stub directories so scripts don't crash:

```bash
cd ~/theVault
rm Inbox Processed 2>/dev/null   # Remove broken NAS symlinks
mkdir -p Inbox/Plaud/MarkdownOnly
mkdir -p Processed/Plaud
```

These are empty local dirs. Plaud ingest and overnight processing happen on Mac Mini only.

### Step 5: API Key

```bash
# Add to ~/.zshrc
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
source ~/.zshrc

# Also create .env (git-ignored)
cat > ~/theVault/.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
EOF

# Verify
python3 -c "import anthropic; c=anthropic.Anthropic(); print(c.messages.create(model='claude-haiku-4-5-20251001', max_tokens=10, messages=[{'role':'user','content':'hi'}]).content[0].text)"
```

### Step 6: Claude Code Memory Sync

The Mac Mini pushes 23 user memory files to `.claude/user-memory/` in git. On the laptop, copy them to Claude Code's expected location:

```bash
mkdir -p ~/.claude/projects/-Users-emanches-theVault/memory/
cp ~/theVault/.claude/user-memory/*.md ~/.claude/projects/-Users-emanches-theVault/memory/

# Verify
ls ~/.claude/projects/-Users-emanches-theVault/memory/ | wc -l   # Expect 23
```

**To refresh memory** (after Mac Mini pushes updates):
```bash
cd ~/theVault && git pull origin main
cp .claude/user-memory/*.md ~/.claude/projects/-Users-emanches-theVault/memory/
```

### Step 7: Obsidian Sync Setup

1. Open Obsidian
2. Open folder as vault: `~/NeroSpicy/Vault` (or wherever Obsidian Sync delivers)
3. Enable Obsidian Sync: Settings -> Core plugins -> Sync -> ON
4. Sign in and wait for initial sync (2-3 minutes)
5. Install community plugins: Tasks, QuickAdd, Dataview, Templater, etc.

Verify: Check `Vault/Daily/2026/04/` has recent daily notes.

### Step 8: QuickAdd Configuration

1. Settings -> Community plugins -> QuickAdd -> Gear icon
2. Create macro "Capture to Daily"
3. Append to daily note under `## Captures`
4. Bind to Cmd+Shift+C
5. Test: Press Cmd+Shift+C, type "Test capture", verify in daily note

### Step 9: Validate

```bash
cd ~/theVault
bash System/Scripts/check_vault_laptop.sh
```

Or run the full validation:
```bash
echo "=== theVault Laptop Validation ==="

# Vault accessible
[ -d ~/theVault/Vault/Daily ] && echo "OK Vault/Daily" || echo "FAIL Vault/Daily missing"

# Memory files
MEM=$(ls ~/.claude/projects/-Users-emanches-theVault/memory/*.md 2>/dev/null | wc -l)
echo "Memory files: $MEM (expect 23)"

# Git current
echo "Branch: $(git branch --show-current)"
echo "Last commit: $(git log --oneline -1)"

# Python
source .venv/bin/activate
python3 -c "import fastapi, anthropic; print('OK Python')" 2>/dev/null || echo "FAIL Python"

# API key
[ -n "$ANTHROPIC_API_KEY" ] && echo "OK API key" || echo "FAIL API key missing"

# NAS check (laptop mode)
bash System/Scripts/check_nas.sh 2>&1

# Hooks
[ -f .claude/settings.json ] && echo "OK Hooks config" || echo "FAIL Hooks missing"

# Latest daily note
echo "Latest: $(ls -t Vault/Daily/2026/04/*-DLY.md 2>/dev/null | head -1)"
```

---

## Hooks & Auto-Commit

The project has Claude Code hooks in `.claude/settings.json`:

- **PreToolUse (Bash|Write|Edit)**: Runs `check_nas.sh` — on laptop this returns "LAPTOP OK" immediately (hostname-aware skip)
- **PostToolUse (Write|Edit)**: Auto-commits changes with timestamp (`auto: YYYY-MM-DD_HH:MM:SS`)

These work on the laptop without modification.

**Note:** `settings.local.json` (user-level, not git-tracked) is optional. Only needed for laptop-specific Bash permissions or overrides.

---

## Memory Architecture

Two layers of Claude Code memory, both synced via git:

| Layer | Location | In Git? | Purpose |
|-------|----------|---------|---------|
| Project memory (6 files) | `theVault/.claude/memory/` | Yes | Core architecture, job search, resume engine |
| User memory (23 files) | `theVault/.claude/user-memory/` | Yes | Priorities, feedback, all project context |
| Local copy | `~/.claude/projects/-Users-emanches-theVault/memory/` | No | Claude Code reads from here |

**Sync flow:** Mac Mini → git push → laptop git pull → `cp .claude/user-memory/* ~/.claude/projects/.../memory/`

The Mac Mini runs `sync_memory_to_repo.sh` on PostToolUse to keep the git-tracked copy current.

---

## Daily Workflow

### Morning
```bash
cd ~/theVault
git pull origin main                     # Get Mac Mini's overnight work
cp .claude/user-memory/*.md ~/.claude/projects/-Users-emanches-theVault/memory/  # Refresh memory (if changed)
source .venv/bin/activate                # For any development
```

### Capturing Ideas
Press **Cmd+Shift+C** in Obsidian. Captures auto-sync to Mac Mini via Obsidian Sync. The overnight processor extracts tasks and generates summaries from your captures.

### Development
Edit scripts, test with `--dry-run`, commit and push. Mac Mini pulls automatically or on next session.

### Travel Mode
When away from home network:
- Captures work via Obsidian Sync (internet required)
- Git push/pull works normally
- NAS-dependent scripts won't run (that's fine — Mac Mini handles them on cron)
- Everything you capture syncs back and gets processed overnight

---

## Key Scripts Available on Laptop

| Script | Command | Notes |
|--------|---------|-------|
| Task normalizer | `python3 -m System.Scripts.task_normalizer --dry-run` | Reads vault markdown |
| Content classifier | `python3 System/Scripts/Workflows/classify_content.py --scan --dry-run --source Vault/Notes/Email/` | Reads vault files |
| JD Analyzer | `python3 ResumeEngine/jd_analyzer.py` | Needs ANTHROPIC_API_KEY |
| Calendar mapper | `python3 System/Scripts/Workflows/calendar_mapper.py ~/theVault/Vault Work` | Needs EventKit permission |
| Vault check | `bash System/Scripts/check_vault_laptop.sh` | Full validation |
| NAS check | `bash System/Scripts/check_nas.sh` | Returns "LAPTOP OK" |

**Server startup** (if ever needed locally):
```bash
python3 -m uvicorn System.Scripts.RAG.llm.server:app --host 0.0.0.0 --port 5055
```
Always start from `~/theVault` root. Never cd into `System/Scripts/RAG/` first.

---

## Troubleshooting

**Vault symlink broken after git pull?**
Git may update the symlink to NAS. Fix:
```bash
cd ~/theVault && rm Vault && ln -s /Users/emanches/NeroSpicy/Vault Vault
```

**check_nas.sh failing?**
Should say "LAPTOP OK". If it fails, verify:
- `scutil --get ComputerName` doesn't contain "Mac mini"
- `~/theVault/Vault` directory exists and is accessible

**Memory stale?**
```bash
git pull origin main
cp .claude/user-memory/*.md ~/.claude/projects/-Users-emanches-theVault/memory/
```

**Hooks blocking edits?**
The NAS pre-check hook is hostname-aware and skips on laptop. If issues persist, check `.claude/settings.json` hooks section.

**Inbox/Processed errors?**
Ensure local stub directories exist:
```bash
mkdir -p ~/theVault/Inbox/Plaud/MarkdownOnly ~/theVault/Processed/Plaud
```

**Python import errors?**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**Calendar mapper permission denied?**
Grant calendar access: System Settings -> Privacy & Security -> Calendars -> Allow terminal/Python.

---

## File Reference

| Path | Purpose |
|------|---------|
| `CLAUDE.md` | Project instructions for Claude Code |
| `LAPTOP_SETUP_GUIDE.md` | This file |
| `.agents/LAPTOP_MIGRATION_PLAN.md` | Original migration plan (Mac Mini authored) |
| `.agents/SHARED_CONTEXT.md` | Cross-session sync between all Claude instances |
| `.agents/SESSION_STATE.md` | Current session state |
| `.claude/settings.json` | Hooks and env config |
| `.claude/memory/` | Project-level memory (6 files) |
| `.claude/user-memory/` | User-level memory (23 files, git-tracked) |
| `System/Scripts/check_vault_laptop.sh` | Laptop validation script |
| `System/Scripts/check_nas.sh` | NAS check (hostname-aware) |
| `System/Scripts/sync_memory_to_repo.sh` | Memory auto-sync (Mac Mini) |

---

*Last Updated: April 10, 2026*
