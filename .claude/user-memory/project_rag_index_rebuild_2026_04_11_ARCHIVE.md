# ⚠️ ARCHIVED — RAG Index Rebuild Attempt (April 11, 2026)

**Status:** Previous iteration. Superseded by final successful rebuild (April 13, 2026 — 100% coverage).
**Kept for reference:** Use this to understand the debug process that led to identifying EMBED_CTX as the bottleneck.

See [project_rag_index_rebuild_2026_04_13.md](project_rag_index_rebuild_2026_04_13.md) for current production configuration.

---

# RAG Index Rebuild — April 11, 2026

## Summary
Full FAISS vector index rebuild completed 2026-04-11 19:20:26 UTC. Coverage: **94.8%** (58,469/61,704 chunks indexed successfully). Below 95% target by 149 chunks.

## Execution Details
- **Command**: `python3 -m System.Scripts.RAG.retrieval.indexer --verbose`
- **Duration**: ~56 minutes (18:24:46 → 19:20:26 UTC)
- **Embedding model**: nomic-embed-text (768-dim)
- **Embedding mode**: Batch with per-text fallback on timeout

## Results
| Metric | Value |
|--------|-------|
| Total chunks in database | 61,704 |
| Successfully indexed | 58,469 |
| Failed (skip) | 3,235 (5.2%) |
| FAISS index file size | 172 MB |
| Target threshold (95%) | 58,618 chunks |
| **Shortfall** | 149 chunks (0.24%) |

## Failure Root Cause
3,235 chunks failed during embedding due to timeout/resource constraints on nomic-embed-text model running via Ollama. Both batch embedding and per-text fallback modes timed out on these chunks. Likely causes:
1. Particularly long/complex chunks hitting model timeout limits
2. Ollama memory pressure during parallel processing
3. Batch size (64 items) too aggressive for certain content

## Path to >95% Coverage
Need to successfully index ≥149 additional chunks from the 3,235 failed set. Options:
1. **Reduce batch size** (64 → 32) to allow model more time per chunk
2. **Increase timeout** in indexer config (default appears ~30s)
3. **Reduce embedding dimension** if supported (768 → lower)
4. **Target retry** of failed chunks only (need to track which ones)
5. **Chunk preprocessing** — split overly long chunks before re-embedding

## Indexer Code Reference
File: `/Users/ericmanchester/theVault/System/Scripts/RAG/retrieval/indexer.py`
- Batch embedding happens in retrieval pipeline
- Per-text fallback uses per-chunk embeddings when batch timeout occurs
- Config flags: `--incremental`, `--verbose`, `--rebuild` (none support targeted retry)

## System Status
- FAISS index is functional at 94.8% coverage
- Vector search queries will work but ~5.2% of vault content unreachable via semantic search
- Full-text and entity detection unaffected
- Production use acceptable if semantic coverage gap tolerable

## Next Actions
1. Inspect indexer.py for embedding timeout/batch size knobs
2. Implement retry strategy (smaller batches or higher timeout)
3. Re-run indexer with optimized settings to capture the 149+ failing chunks
4. Verify final count reaches ≥58,618 (95% threshold)
