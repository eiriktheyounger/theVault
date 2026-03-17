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

## STEP 3: Set Up Obsidian Sync

1. **Open Obsidian**
2. **Open folder as vault** → Choose `~/theVault/Vault`
3. **Trust the vault** when prompted
4. **Enable Obsidian Sync:**
   - Go to Settings → Obsidian Sync → Sign In
   - Use your Anthropic account credentials
   - Wait 2-3 minutes for initial sync
5. **Install community plugins:**
   - Settings → Community plugins → "Obsidian Sync" → Install
   - Settings → Community plugins → "QuickAdd" → Install
6. **Enable plugins:**
   - Settings → Community plugins → Toggle "Obsidian Sync" ON
   - Settings → Community plugins → Toggle "QuickAdd" ON

Verify sync is working: Check if daily notes appear in `Vault/Daily/YYYY/MM/` directory.

**Troubleshooting:**
- Vault not showing files? Wait 2-3 minutes and restart Obsidian
- Plugins not installing? Try enabling "Community plugins" in Settings
- Sync not starting? Restart Obsidian and check Settings → Obsidian Sync

---

## STEP 4: Configure QuickAdd for Captures

1. In Obsidian, go to **Settings → Community plugins → QuickAdd**
2. Click the "Gear" icon to open QuickAdd settings
3. **Create a new macro:**
   - Click "Manage Macros"
   - Click "Add Macro"
   - Name it "Capture to Daily"
4. **Set up the capture action:**
   - Template: Use the format: `HH:MM Capture text`
   - Append to: Daily note under "## Captures" heading
5. **Bind keyboard shortcut:**
   - In QuickAdd settings, set trigger to "Cmd+Shift+C"

**Test it:**
```bash
# Press Cmd+Shift+C in Obsidian, type something like "09:30 Test capture"
# Verify it appears in today's daily note under ## Captures
```

---

## STEP 5: Set ANTHROPIC_API_KEY

Add to `~/.zshrc`:

```bash
export ANTHROPIC_API_KEY='sk-ant-...'  # Your actual API key
```

Then reload:
```bash
source ~/.zshrc
echo $ANTHROPIC_API_KEY  # Verify it's set
```

---

## STEP 6: Run Vault Check Script

```bash
bash ~/theVault/System/Scripts/check_vault_laptop.sh
```

This verifies:
- ✓ Vault accessibility (symlink or local)
- ✓ Obsidian plugins installed
- ✓ Python environment OK
- ✓ Git configuration
- ✓ API keys set
- ✓ RAG server requirements

Fix any ✗ issues shown before proceeding.

---

## STEP 7: Optional — Set Up RAG Server Locally

If you want search functionality on the laptop (requires Ollama):

```bash
# Install Ollama
# Download from https://ollama.ai and install

# Pull models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Start RAG server
cd ~/theVault/System/Scripts/RAG
source ~/theVault/.venv/bin/activate
python3 -m uvicorn llm.server:app --port 5055

# In another terminal, test:
curl -X POST http://localhost:5055/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'
```

**Note:** RAG server requires a FAISS index. On laptop, search will work against your synced vault copy.

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
