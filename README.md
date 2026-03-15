# theVault

Local-first AI knowledge management system on Mac Mini M4. Combines Python FastAPI backend (RAG, LLM integration, Ollama), React frontend, SQLite semantic search, and Obsidian vault stored on NAS.

**Status**: Production (Phases 1-4 complete as of March 15, 2026)

## Quick Links

- **Architecture & Development**: See [`CLAUDE.md`](CLAUDE.md) for complete setup, paths, and development guidelines
- **Laptop Setup**: See [`LAPTOP_SETUP_GUIDE.md`](LAPTOP_SETUP_GUIDE.md) for multi-machine sync configuration
- **System Overview**: [`System/Scripts/RAG/`](System/Scripts/RAG/) contains RAG server, LLM routes, and indexing

## Core Features

- **RAG Search**: SQLite + HNSW vector index with 41,976 indexed chunks
- **LLM Chat**: Local Ollama (qwen2.5:7b) + Claude API integration
- **Obsidian Vault**: 1,881+ markdown files organized on NAS (`/Volumes/home/MacMiniStorage/Vault`)
- **Automation**: Morning/evening workflows, overnight processor, calendar sync
- **Multi-Machine**: Git + NAS symlinks enable seamless sync between Mac Mini and MacBook Pro

## Quick Start

### Mac Mini (Production)
```bash
cd ~/theVault
source .venv/bin/activate
npm run rag &    # RAG server (port 5055)
npm run llm &    # LLM server (port 5111)
npm run dev &    # UI (port 5173)
```

### MacBook Pro (Development)
See [`LAPTOP_SETUP_GUIDE.md`](LAPTOP_SETUP_GUIDE.md) for complete setup (Prerequisites, Clone, NAS Symlinks, Python, Database Copy, Verification, Configuration).

## Project Structure

```
theVault/
├── System/Scripts/RAG/           # RAG & search server
│   ├── rag_data/                 # SQLite (41,976 chunks) + HNSW index
│   ├── routes/                   # API endpoints (chat, search, index, ingest)
│   ├── retrieval/                # Indexing & chunking
│   └── app.py                    # FastAPI application
├── ui/                           # React 19.1.1 frontend (Vite)
├── System/Scripts/Workflows/     # Morning/evening automation
├── Vault/ (symlink)              # → /Volumes/home/MacMiniStorage/Vault
├── Inbox/ (symlink)              # → /Volumes/home/MacMiniStorage/Inbox
├── Processed/ (symlink)          # → /Volumes/home/MacMiniStorage/Processed
├── CLAUDE.md                     # Complete architecture & dev guide
└── LAPTOP_SETUP_GUIDE.md         # Multi-machine setup instructions
```

## Architecture

| Component | Port | Status |
|-----------|------|--------|
| Ollama | 11434 | Local LLM backend |
| RAG Server | 5055 | FastAPI search & chat |
| LLM Server | 5111 | Claude API proxy |
| UI | 5173 | React frontend |

**Storage**:
- SQLite + HNSW: `System/Scripts/RAG/rag_data/` (208 MB)
- Vault: NAS symlink (`/Volumes/home/MacMiniStorage/Vault/`)
- Code: Git repository

## Development

**Before coding**: See [`CLAUDE.md`](CLAUDE.md) for rules, paths, and verification steps

```bash
# Python
source .venv/bin/activate
~/NeroSpicy/.venv/bin/python -m pytest
~/NeroSpicy/.venv/bin/python -m ruff check .

# UI
npm run typecheck
npm run lint
npm run test
```

**Key files**:
- RAG routes: `System/Scripts/RAG/routes/`
- UI pages: `ui/src/pages/`
- Workflows: `System/Scripts/Workflows/`
- Database: `System/Scripts/RAG/rag_data/chunks.sqlite3`

## Data Organization

**Vault** (on NAS):
- `Vault/Daily/YYYY/MM/YYYY-MM-DD-DLY.md` - Daily notes
- `Vault/Notes/` - Processed content
- `Vault/Meetings/` - Meeting notes
- `Vault/System/` - Configuration, glossary, logs

**Inbox** (on NAS):
- `Inbox/Email/` - Processed emails
- `Inbox/Plaud/MarkdownOnly/` - Meeting transcripts
- `Inbox/Images/` - Captured screenshots
- `Inbox/PDFs/` - Documents

**Processed** (on NAS):
- Archive of ingested content

## Known Issues

See [`CLAUDE.md`](CLAUDE.md) for current limitations and workarounds.

## Multi-Machine Sync

Both Mac Mini and MacBook Pro pull from:
1. **Code**: GitHub (git pull)
2. **Vault Content**: NAS symlinks (auto-synced)
3. **RAG Index**: Option A (scp from Mac Mini), Option B (NAS backup), Option C (rebuild fresh)

Full setup guide: [`LAPTOP_SETUP_GUIDE.md`](LAPTOP_SETUP_GUIDE.md)

## Maintenance

**Daily**:
- Overnight processor runs at 10 PM (cron): `System/Scripts/overnight_processor.py`
- Extracts tasks, summarizes captures, updates indexes

**Weekly**:
- Monitor RAG index health
- Check NAS backup status
- Review logs: `System/Logs/`

**Monthly**:
- Full vault reindex (if needed)
- Update dependencies: `pip list --outdated`

## Support

For issues, check:
1. [`CLAUDE.md`](CLAUDE.md) - Architecture & development guide
2. [`LAPTOP_SETUP_GUIDE.md`](LAPTOP_SETUP_GUIDE.md) - Multi-machine setup
3. Logs: `System/Logs/` or `/tmp/*.log`
4. Database integrity: `sqlite3 System/Scripts/RAG/rag_data/chunks.sqlite3 "SELECT COUNT(*) FROM chunks;"`

---

**Last Updated**: March 15, 2026
**Phases Completed**: 1 (Foundation), 1.1 (UI), 2 (RAG), 3 (Automation), 4 (Multi-Machine Sync)
