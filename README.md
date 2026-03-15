# theVault

Local-first AI knowledge management system.

## Quick Start
```bash
cd ~/theVault
source .venv/bin/activate
bash System/Scripts/check_nas.sh
python3 -m uvicorn System.Scripts.RAG.rag:app --port 5055
```

## Architecture

- **API**: FastAPI (port 5055) — RAG search, chat, ingest
- **Database**: SQLite + HNSW (768-dim, nomic-embed-text)
- **LLM**: Ollama (qwen2.5:7b) on port 11434
- **Vault**: Obsidian vault on NAS via symlink
- **Daily Notes**: Daily/YYYY/MM/YYYY-MM-DD-DLY.md

## Directory Structure

```
~/theVault/
├── System/Scripts/         Python backend
│   ├── RAG/               RAG server, routes, retrieval
│   ├── Workflows/         Morning/evening automation
│   └── overnight_processor.py
├── ui/                    React frontend
├── Vault/ → NAS           Obsidian vault (symlink)
├── Inbox/ → NAS           Ingest inbox (symlink)
├── Processed/ → NAS       Processed files (symlink)
├── .claude/               Skills, agents, hooks
├── CLAUDE.md              Project config for Claude Code
└── requirements.txt       Python dependencies
```

## NAS Requirement

This system requires the Synology DS1621+ NAS mounted at:
```
/Volumes/home/MacMiniStorage/
```

Run `bash System/Scripts/check_nas.sh` to verify.

## Multi-Machine

Clone this repo on any Mac with access to the same NAS.
Create identical symlinks. See docs/laptop-setup.md.
