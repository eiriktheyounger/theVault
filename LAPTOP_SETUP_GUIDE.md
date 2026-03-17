# theVault Laptop Setup Guide

**Status**: MacBook Air as secondary development machine
**Primary Machine**: Mac Mini M4 (~/theVault production, overnight processor)
**Sync Strategy**: Obsidian Sync (vault) + Git (code) + NAS symlinks (if available)
**Setup Time**: 20-30 minutes
**Date**: March 17, 2026

---

## Quick Overview

### What Works on Laptop
- ✓ Obsidian daily notes (via Obsidian Sync)
- ✓ QuickAdd captures (Cmd+Shift+C)
- ✓ RAG server search (optional, with Ollama)
- ✓ Code development and git workflow
- ✓ Claude Code vault-aware editing

### What Does NOT Run on Laptop
- ✗ Overnight processor (Mac Mini only, 10 PM cron)
- ✗ Plaud pipeline (NAS-dependent)
- ✗ Full re-indexing (no database by default)

---

## Prerequisites Checklist

- [ ] GitHub access (`git@github.com:eiriktheyounger/theVault.git`)
- [ ] SSH key configured for GitHub
- [ ] ~3 GB free disk space (code + Python venv)
- [ ] Python 3.12.5 (via pyenv or installed)
- [ ] Obsidian installed (latest version)
- [ ] macOS 11+ (Intel or Apple Silicon)

---

## STEP 1: Clone GitHub Repository

```bash
cd ~
git clone git@github.com:eiriktheyounger/theVault.git
cd ~/theVault
git status
```

Expected output:
```
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

**Troubleshooting:**
- "Permission denied (publickey)": Configure SSH key: `ssh-keygen -t ed25519 && ssh-add ~/.ssh/id_ed25519`
- Already cloned? Just update: `cd ~/theVault && git pull origin main`

---

## STEP 2: Set Up Python Environment

```bash
# Verify Python version
python3 --version
# Expected: Python 3.12.5

# Create and activate venv
cd ~/theVault
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify key packages
python3 -c "import fastapi, anthropic, uvicorn; print('✓ Core packages OK')"
```

Expected: Installation completes without errors (15-30 seconds).

---

## STEP 3: Create Python Virtual Environment & Install Dependencies

### Commands
```bash
cd ~/theVault

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Verify installation
python3 -c "import fastapi, anthropic, ollama; print('✓ All imports OK')"
deactivate
```

### Expected Results
```
✓ All imports OK
Successfully installed fastapi uvicorn anthropic ollama ... (30 packages)
```

### Troubleshooting
| Issue | Fix |
|-------|-----|
| "python3: command not found" | Install Python: `brew install python@3.9` or use pyenv |
| "Requirement already satisfied" messages (harmless) | Normal - pip skips installed packages |
| "No matching distribution found for numpy>=2.1.0" | Already fixed in requirements.txt (uses numpy<2.0.0) |
| "ERROR: pip's legacy resolver does not work this way" | Run `pip install --upgrade pip` first |
| Import errors after install | Verify venv is activated: `which python3` should show `~/.venv/bin/python3` |

---

## STEP 4: Copy RAG Databases from Mac Mini

The RAG database (41,976 chunks) and HNSW index (114 MB) must be synced to laptop.

### Option A: SCP from Mac Mini (Recommended - Fastest)

**Setup once** (on laptop):
```bash
# Add Mac Mini to ~/.ssh/config
cat >> ~/.ssh/config << 'EOF'
Host macmini
    HostName 192.168.1.210     # Replace with actual IP
    User ericmanchester
    IdentityFile ~/.ssh/id_ed25519
EOF
```

**Copy databases** (from laptop):
```bash
scp -r macmini:~/theVault/System/Scripts/RAG/rag_data/ ~/theVault/System/Scripts/RAG/
# Expected: downloads chunks.sqlite3 (141 MB), chunks_hnsw.bin (114 MB), meta.csv (53 MB)
# Time: ~2-3 minutes on 1 Gbps network
```

### Option B: NAS Backup (if Mac Mini has backup scheduled)

```bash
ls /Volumes/home/MacMiniStorage/Backups/thevault-rag-data-*.tar.gz
tar xzf /Volumes/home/MacMiniStorage/Backups/thevault-rag-data-LATEST.tar.gz -C ~/theVault/System/Scripts/RAG/
```

### Option C: Rebuild Fresh from Vault (if no backup available)

```bash
cd ~/theVault
source .venv/bin/activate
python3 System/Scripts/batch_reindex.py --batch-size 150
# Time: ~10-15 minutes; generates fresh HNSW index from vault files
deactivate
```

**Choose ONE option:**
- **Option A (scp)**: 2-3 minutes, most reliable
- **Option B (backup)**: 1-2 minutes, requires backup exists
- **Option C (rebuild)**: 10-15 minutes, works offline but slow

---

## STEP 5: Verify Setup

Run these 5 checks in order:

### Check 1: Virtual Environment
```bash
source ~/theVault/.venv/bin/activate
python3 --version      # Should show Python 3.9+
which python3          # Should show ~/.venv/bin/python3
pip list | grep fastapi # Should show fastapi==0.112.2
deactivate
```

### Check 2: NAS Symlinks
```bash
ls ~/theVault/Vault | head -5      # Should list directory contents
ls ~/theVault/Inbox | head -5      # Should list inbox items
[ -L ~/theVault/Vault ] && echo "✓ Symlink OK" || echo "✗ Not a symlink"
```

### Check 3: Database Integrity
```bash
cd ~/theVault
source .venv/bin/activate

# SQLite check
sqlite3 System/Scripts/RAG/rag_data/chunks.sqlite3 "SELECT COUNT(*) FROM chunks;"
# Should return: 41976

# HNSW index check (optional)
python3 -c "import hnswlib; idx = hnswlib.Index(space='cosine', dim=768); idx.load_index('System/Scripts/RAG/rag_data/chunks_hnsw.bin'); print(f'✓ HNSW loaded: {idx.get_current_count()} vectors')"

deactivate
```

### Check 4: Git Status
```bash
cd ~/theVault
git status              # Should show "nothing to commit, working tree clean"
git log --oneline -5   # Should show recent commits
```

### Check 5: File Structure
```bash
# Verify key directories exist
[ -d ~/theVault/System/Scripts/RAG ] && echo "✓ RAG scripts"
[ -d ~/theVault/ui ] && echo "✓ UI"
[ -d ~/theVault/System/Scripts/Workflows ] && echo "✓ Workflows"
[ -f ~/theVault/requirements.txt ] && echo "✓ Requirements"
```

---

## STEP 6: Laptop-Specific Configuration

### Port Availability Checks
```bash
# Verify ports are free (same as Mac Mini)
for port in 5055 5111 5173; do
  nc -zv localhost $port 2>/dev/null && echo "⚠️  Port $port in use" || echo "✓ Port $port available"
done
```

### Ollama Status (Laptop)
```bash
# Check if Ollama is running
pgrep -f "ollama" && echo "✓ Ollama running" || echo "○ Ollama not running"

# If not running, start it
# ollama serve > /tmp/ollama.log 2>&1 &

# Verify models are downloaded
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys, json; tags = json.load(sys.stdin)['models']; print('Models:', [m['name'] for m in tags])"
```

### Environment Variables (Optional)
Create `~/theVault/.env.laptop` with laptop-specific settings:
```bash
# .env.laptop
VAULT_PATH=~/theVault/Vault
RAG_MODE=REAL
OLLAMA_HOST=http://127.0.0.1:11434
CLAUDE_API_KEY=sk-...  # If using Claude API features
```

Then when running services on laptop:
```bash
export $(cat ~/theVault/.env.laptop | xargs)
```

---

## STEP 7: Sync Strategy & Troubleshooting

### Sync Philosophy
- **Code**: Git-based (pull latest, push experimental branches)
- **Vault Content**: NAS symlink (same path on both machines)
- **RAG Index**: Periodic sync (scp after major ingest, or rebuild fresh)
- **Databases**: Rebuild locally if needed, or copy from Mac Mini

### Daily Workflow
```bash
# Monday-Friday morning (laptop)
cd ~/theVault
git pull origin main          # Get latest code
# Vault content auto-syncs via NAS
source .venv/bin/activate
npm run dev                   # Start UI
npm run rag                   # Start RAG (if testing search)
```

### Troubleshooting Table

| Problem | Symptom | Solution |
|---------|---------|----------|
| **NAS Mounts But Files Missing** | `ls ~/theVault/Vault/` is empty or errors | Mac Mini not running NAS share; wake NAS or check Mac Mini SMB daemon |
| **"Permission denied" on NAS** | Can see `/Volumes/home/MacMiniStorage` but can't read Vault | NAS has read-only permissions; reconnect with credentials: `mount_smbfs //User:Pass@192.168.1.X/home /Volumes/home` |
| **RAG server crashes on startup** | "cannot open shared object file: No such file or directory" | HNSW index corrupted; rebuild: `python3 System/Scripts/batch_reindex.py --batch-size 150` |
| **Port 5055 already in use** | "Address already in use" when starting RAG | Kill existing process: `lsof -i :5055 \| grep -v PID \| awk '{print $2}' \| xargs kill -9` |
| **UI won't load on localhost:5173** | "Connection refused" | Start UI dev server: `npm run dev` (not `npm run build:prod`) |
| **Git pull conflicts** | "CONFLICT (content merge)" | Stash local changes: `git stash`, then `git pull`, then `git stash pop` |
| **Ollama models missing on laptop** | "model not found: qwen2.5:7b" | Pull models: `ollama pull qwen2.5:7b && ollama pull nomic-embed-text` |
| **API calls timeout** | Requests to localhost:5055 hang >30s | Check Mac Mini is running RAG server; or increase timeout in ui/src/lib/api.ts |
| **Database integrity error** | "database disk image is malformed" | Re-copy from Mac Mini: `scp -r macmini:~/theVault/System/Scripts/RAG/rag_data/ ~/theVault/System/Scripts/RAG/` |
| **Git status shows "ahead by X commits"** | Laptop has experimental commits not on Mac Mini | Push branch: `git push -u origin feature-branch` or reset: `git reset --hard origin/main` |

### Post-Setup Next Steps

1. **Test Vault Access**: Open a random file from ~/theVault/Vault in Obsidian
2. **Verify RAG Index**:
   ```bash
   curl http://localhost:5055/healthz | python3 -m json.tool
   ```
3. **Sync Confirmation**: Check git status and NAS access before doing any development
4. **Schedule Backup**: If laptop will run overnight services, add cronjob to backup rag_data to NAS

---

## Quick Reference Commands

```bash
# Activate venv
source ~/theVault/.venv/bin/activate

# Start all services (from ~/theVault)
npm run rag & npm run llm & npm run dev

# Check service status
curl http://localhost:5055/healthz   # RAG
curl http://localhost:5111/health    # LLM
# UI: http://localhost:5173

# Sync from NAS (Vault auto-synced via symlink)
git pull origin main

# Rebuild index (slow, 10-15 min)
python3 System/Scripts/batch_reindex.py --batch-size 150

# Copy fresh databases from Mac Mini
scp -r macmini:~/theVault/System/Scripts/RAG/rag_data/ ~/theVault/System/Scripts/RAG/

# Check database integrity
sqlite3 System/Scripts/RAG/rag_data/chunks.sqlite3 "SELECT COUNT(*) FROM chunks;"
```

---

## Support

**For issues**, check:
1. This guide's Troubleshooting section (Step 7)
2. `~/theVault/CLAUDE.md` for architecture overview
3. `~/theVault/System/Scripts/check_nas.sh` to verify NAS mount
4. Logs: `tail -f /tmp/ollama.log` (Ollama), `~/.npm/_logs/` (npm)

**For data loss or corruption**, restore from:
- Vault: NAS backup (symlinked)
- RAG index: Mac Mini (scp) or rebuild
- Code: GitHub (git pull)

---

*Last Updated: March 15, 2026*
