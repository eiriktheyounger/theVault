# theVault

**PRIMARY PROJECT** — Local-first AI knowledge management system on Mac Mini M4. Python 3.12.5, FastAPI, SQLite+HNSW, Obsidian vault on NAS.

## Migration Notice (March 17, 2026)
**Active development has migrated from ~/NeroSpicy to ~/theVault.** This is now the primary project directory.
- **Old project**: ~/NeroSpicy (archived, read-only reference)
- **New project**: ~/theVault (active development)
- Both share the same NAS-backed Vault, Inbox, and Processed directories
- All new work goes in ~/theVault/

## Architecture
- API server: FastAPI on port 5055 (RAG search, chat, ingest)
- LLM server: FastAPI on port 5111 (Ollama proxy)
- Ollama: port 11434 (qwen2.5:7b, nomic-embed-text)
- Database: SQLite (chunks.sqlite3) + HNSW (chunks_hnsw.bin), 768-dim embeddings
- Vector index: FAISS (IndexIDMap2/IndexFlatIP), saved as chunks_hnsw.bin
- Vault: ~/theVault/Vault → NAS symlink (/Volumes/home/MacMiniStorage/Vault)
- Inbox: ~/theVault/Inbox → NAS symlink
- Processed: ~/theVault/Processed → NAS symlink

## Before You Code
1. Verify vault: bash System/Scripts/check_vault_laptop.sh (laptop) or check_nas.sh (Mac Mini)
2. Activate venv: source .venv/bin/activate
3. Check Ollama: curl -s http://localhost:11434/api/tags | head -5

## Server Startup — IMPORTANT
Always start the server from ~/theVault root using the full package path:
  python3 -m uvicorn System.Scripts.RAG.llm.server:app --host 0.0.0.0 --port 5055

Do NOT start from inside System/Scripts/RAG — relative imports will break:
  ❌ cd System/Scripts/RAG && python3 -m uvicorn llm.server:app  (breaks imports)

## Key Paths
- RAG server: System/Scripts/RAG/
- Routes: System/Scripts/RAG/routes/ (chat.py, fast.py)
- Indexer: System/Scripts/RAG/retrieval/indexer.py
- Databases: System/Scripts/RAG/rag_data/
- Workflows: System/Scripts/Workflows/
- Daily notes: Vault → Daily/YYYY/MM/YYYY-MM-DD-DLY.md
- Laptop setup: LAPTOP_SETUP_GUIDE.md (Obsidian Sync + QuickAdd for secondary machine)
- Laptop checks: System/Scripts/check_vault_laptop.sh

## Rules
- Use Path objects, not strings, for all file paths
- Validate NAS mount before any vault write
- Never hardcode absolute paths — use environment variables or relative paths
- Test every change against the existing 41,976 chunks
- Do not modify production endpoints without creating a backup route first
- One agent writes code at a time — no parallel sessions editing the same files
- The vector index uses FAISS, not hnswlib — do not import hnswlib for search

## What NOT to Do
- Do not install Docker or reference Docker configs
- Do not use ChromaDB — the database is SQLite + HNSW
- Do not reference PostgreSQL or pgvector
- Do not create microservice directories — this is a monolithic FastAPI app
- Do not copy Vault/ Inbox/ or Processed/ to local disk — they live on NAS
- Do not use hnswlib for search — the index is FAISS despite the filename
