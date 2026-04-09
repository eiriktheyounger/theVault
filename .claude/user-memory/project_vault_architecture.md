---
name: theVault system architecture
description: Ports, services, key paths, and technical stack for theVault RAG/knowledge system
type: project
---

**Active project directory:** `~/theVault` (migrated from `~/NeroSpicy` on ~2026-03-17)

**Services:**
- RAG server: FastAPI, port 5055, started via `bash System/Scripts/start_server.sh`
- LLM server: FastAPI, port 5111 (Ollama proxy) — separate service per CLAUDE.md
- Ollama: port 11434, models: `qwen2.5:7b` (fast/default), `gemma3:4b` (fastest), `nomic-embed-text` (embeddings). `llama3.1:8b` and several others **removed** 2026-04-02 (~57GB reclaimed).
- Services manager: `System/Scripts/Services/` — `start_all.py`, `stop_all.py`, `emergency_kill.py` (built 2026-04-02)

**Database:**
- SQLite FTS5: `System/Scripts/RAG/rag_data/chunks.sqlite3`
- FAISS vector index: `System/Scripts/RAG/rag_data/chunks_hnsw.bin` (768-dim, IndexIDMap2/IndexFlatIP)
- Despite the filename `chunks_hnsw.bin`, backend is FAISS — do NOT import hnswlib
- Query log: `System/Scripts/RAG/rag_data/query_log.sqlite3` (cost tracking, added 2026-04-02)

**Paths:**
- Vault: `~/theVault/Vault` → symlink to `/Volumes/home/MacMiniStorage/Vault`
- Inbox: `~/theVault/Inbox` → NAS symlink
- Processed: `~/theVault/Processed` → NAS symlink
- RAG routes: `System/Scripts/RAG/routes/` (chat.py, fast.py, query.py [added 2026-04-02])
- Workflows: `System/Scripts/Workflows/`
- Daily notes: `Vault/Daily/YYYY/MM/YYYY-MM-DD-DLY.md`

**Chunk/vector counts (as of 2026-03-30):** 47,496 chunks in SQLite / 53,381 vectors in FAISS (95.8% coverage after full rebuild)

**Why:** Local-first AI knowledge management; NAS-backed vault for persistence and Obsidian sync.

**How to apply:** Always start server from `~/theVault` root with full package path. Never use hnswlib. Use absolute paths for NAS traversal.
