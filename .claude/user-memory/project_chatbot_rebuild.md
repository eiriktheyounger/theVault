---
name: Chatbot UI + Backend Rebuild
description: Major chatbot rebuild 2026-04-02 — unified /api/query endpoint, multi-model support (Ollama + Claude API), ADHD/dyslexia-friendly UI with OpenDyslexic font
type: project
---

## Chatbot Rebuild (2026-04-02)

**Status**: DONE — fully operational 2026-04-02. All 5 models verified, Claude API key fix applied.

### What Changed

**Backend (new files)**:
- `System/Scripts/RAG/routes/query.py` — Unified `/api/query` endpoint replacing fast/deep split
  - POST `/api/query` — accepts `{question, model, context_mode}`, routes to Ollama or Claude API
  - GET `/api/query/models` — returns available models with metadata
  - GET `/api/query/usage` — usage stats from query log for cost estimator
- `System/Scripts/RAG/llm/claude_client.py` — Async Anthropic API client
- `System/Scripts/RAG/retrieval/query_log.py` — SQLite query logging + cost calculation

**Backend (updated)**:
- `config.py` — fixed stale defaults: FAST_MODEL→gemma3:4b, DEEP_MODEL→qwen2.5:7b, INGEST_MODEL→qwen2.5:7b
- `server.py` — fixed model defaults, registered query_routes router

**Frontend (rebuilt)**:
- `ui/src/pages/Chat.tsx` — Complete rewrite with:
  - Always-visible model selector cards (5 models: gemma3:4b, qwen2.5:7b, haiku, sonnet, opus)
  - Radio buttons for context mode (Off/Auto/Full)
  - Tab bar for multiple chat windows
  - Discovery links (top 10 vault pages by relevance %, small font)
  - Collapsible citations
  - Scroll-to-response-start behavior
  - Calls new `/api/query` endpoint on port 5055
- `ui/src/pages/Settings.tsx` — cost estimator table added, stale model defaults fixed
- `ui/src/index.css` — OpenDyslexic @font-face declarations
- `ui/tailwind.config.js` — OpenDyslexic as primary font-family
- `ui/public/fonts/` — OpenDyslexic OTF files (Regular, Bold, Italic, Bold-Italic)

### Models Available
| Model | Provider | Speed | Cost/query |
|-------|----------|-------|------------|
| gemma3:4b | Ollama | < 0.25s | $0.00 |
| qwen2.5:7b | Ollama | 1-3s | $0.00 |
| claude-haiku-4-5-20251001 | Anthropic | 1-2s | ~$0.001 |
| claude-sonnet-4-20250514 | Anthropic | 2-5s | ~$0.012 |
| claude-opus-4-20250514 | Anthropic | 5-15s | ~$0.063 |

### Context Modes
- **Off**: Raw LLM, no vault context (pure discovery)
- **Auto**: Entity detection + hybrid vector search + context files
- **Full**: Expanded graph (depth 2) + doubled retrieval limits

### Architecture Notes
- Existing /fast, /deep, /chat endpoints preserved — no breakage
- Entity graph wired into /api/query via entity_detector + entity_graph imports
- Recency boost placeholder in query.py (needs chunk metadata date parsing)
- Query logging to `rag_data/query_log.sqlite3` with cost tracking
- `claude_client.py` loads `.env` with `override=True` (fixes empty ANTHROPIC_API_KEY in shell env)
- Citation parsing handles hybrid() string format `"Title (path/to/file.md)"`

### Remaining Gaps
- Recency boost: placeholder only, needs date parsing from chunk metadata
- Min chunk filter: not yet applied in search_fast.py hybrid()
- Multi-window: tabs work but no persistence across page refreshes
- Cost estimator in Settings: static table only, not wired to actual usage API yet
- Ollama model cleanup completed: removed phi3:mini, llama3.1:8b, mixtral, mistral, qwen2.5:14b, deepseek-r1:14b (~57GB reclaimed)

**Why:** Eric needs ADHD/dyslexia-friendly UI, per-query model selection for cost control, and entity graph integration for better search results.

**How to apply:** The /api/query endpoint is now the canonical search path. Old /fast and /deep still work but are legacy. All new features should target /api/query.
