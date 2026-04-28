"""routes/query.py — Unified /query endpoint with multi-model + context mode support."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import VAULT_ROOT
from ..llm.claude_client import claude_generate
from ..retrieval.entity_detector import detect_entities, load_entity_names
from ..retrieval.entity_graph import get_connections, get_entity_context, get_graph
from ..retrieval.query_log import calculate_cost, log_query
from ..retrieval.search_fast import hybrid

router = APIRouter(prefix="/api/query", tags=["query"])


# ---- Request/Response Models ----


class QueryRequest(BaseModel):
    question: str
    model: str = "gemma4:e4b"
    context_mode: str = "auto"  # 'off', 'auto', 'full'
    conversation_id: Optional[str] = None


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    use_case: str
    speed: str
    cost_per_query: str
    supports_context: bool


class Citation(BaseModel):
    title: str
    path: str
    score: float


class DiscoveryLink(BaseModel):
    title: str
    path: str
    relevance_pct: float
    obsidian_uri: str


class QueryResponse(BaseModel):
    answer: str
    model: str
    context_mode: str
    entities_detected: List[str]
    citations: List[Citation]
    discovery: List[DiscoveryLink]
    tokens: Dict[str, int]
    latency_ms: int
    cost_usd: float
    conversation_id: Optional[str] = None


# ---- Helpers ----


def _require_graph(request: Request):
    """Return entity graph from app state or module cache."""
    graph = getattr(request.app.state, "entity_graph", None)
    if graph is None:
        graph = get_graph()
    return graph


def _get_entity_context_blocks(graph, detected_ids: List[str]) -> str:
    """Build context blocks from detected entities."""
    if not detected_ids or not graph:
        return ""

    blocks = []
    for entity_id in detected_ids:
        try:
            ctx = get_entity_context(graph, entity_id)
            blocks.append(ctx)
        except Exception:
            pass

    return "\n\n".join(blocks)


def _read_entity_files(graph, detected_ids: List[str]) -> str:
    """Read context .md files for detected entities."""
    if not detected_ids or not graph:
        return ""

    blocks = []
    for entity_id in detected_ids:
        try:
            node_data = graph.nodes.get(entity_id, {})
            path_str = node_data.get("path", "")
            if not path_str:
                continue

            entity_path = VAULT_ROOT / path_str
            if entity_path.exists():
                text = entity_path.read_text(encoding="utf-8", errors="ignore")
                # Use first 2000 chars
                excerpt = text[:2000]
                blocks.append(f"### {entity_id}\n\n{excerpt}")
        except Exception:
            pass

    return "\n\n".join(blocks)


def _apply_recency_boost(
    citations: List[Dict[str, Any]], chunk_metadata: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Apply recency multiplier to citation scores (simplified version).

    For now, return citations as-is since chunk_metadata parsing would require
    accessing the full chunk store. This is a placeholder for future enhancement.
    """
    return citations


def _parse_citation_string(cit: str) -> Dict[str, str]:
    """Parse 'Title (path/to/file.md)' citation string from hybrid()."""
    import re
    m = re.match(r'^(.+?)\s*\((.+)\)$', cit)
    if m:
        return {"title": m.group(1).strip(), "path": m.group(2).strip()}
    return {"title": cit, "path": ""}


def _build_discovery_links(
    citations: List[Any],
    results: List[Dict[str, Any]] | None = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Extract top vault files from citations as discovery links.

    Citations from hybrid() are strings like 'Title (path/to/file.md)'.
    When results (the per-item list from hybrid()) is provided, use the real
    cosine value to compute relevance_pct instead of a rank-position estimate.
    """
    # Build a path→cosine lookup from results if available
    cosine_by_path: Dict[str, float | None] = {}
    if results:
        for r in results:
            p = r.get("path", "")
            if p:
                cosine_by_path[p] = r.get("cosine")

    discovery = []
    total = min(len(citations), limit)
    for i, citation in enumerate(citations[:limit]):
        if isinstance(citation, str):
            parsed = _parse_citation_string(citation)
            title = parsed["title"].replace(".md", "")
            path = parsed["path"]
        else:
            title = citation.get("title", "").replace(".md", "")
            path = citation.get("path", "")

        # Use real cosine if available; fall back to rank-position estimate
        cosine = cosine_by_path.get(path)
        if cosine is not None:
            relevance_pct = int(round(max(0.0, cosine) * 100))
        else:
            relevance_pct = round(max(10.0, 100.0 - (i * (90.0 / max(total, 1)))), 1)

        obsidian_uri = f"obsidian://open?vault=Vault&file={path.replace('.md', '')}"

        discovery.append(
            {
                "title": title,
                "path": path,
                "cosine": round(cosine, 4) if cosine is not None else None,
                "relevance_pct": relevance_pct,
                "obsidian_uri": obsidian_uri,
            }
        )

    return discovery


async def _call_ollama_generate(
    model: str, prompt: str, system: str = "", max_tokens: int = 2048
) -> Dict[str, Any]:
    """Call Ollama generate function from server.py."""
    try:
        from ..llm.server import generate

        result = await generate(model, prompt, system)
        return result
    except Exception as exc:
        return {
            "ok": False,
            "response": "",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "error": str(exc),
        }


# ---- Endpoints ----


@router.post("", response_model=QueryResponse)
async def query_endpoint(body: QueryRequest, request: Request) -> QueryResponse:
    """Unified query endpoint with multi-model + context mode support.

    context_mode:
      - 'off': No RAG, pure LLM
      - 'auto': Entity detection + vector search
      - 'full': Entity detection + expanded graph + boosted retrieval
    """
    start_time = time.time()
    question = body.question.strip()
    model = body.model.strip()
    context_mode = body.context_mode.strip()
    conversation_id = body.conversation_id

    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    if context_mode not in ("off", "auto", "full"):
        raise HTTPException(
            status_code=400,
            detail="context_mode must be 'off', 'auto', or 'full'",
        )

    # Validate model
    VALID_MODELS = {
        "gemma4:e4b",
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
    }
    if model not in VALID_MODELS:
        raise HTTPException(
            status_code=400, detail=f"Unknown model: {model}. Valid: {VALID_MODELS}"
        )

    # Entity detection + context
    entities_detected: List[str] = []
    entity_context = ""
    entity_files = ""
    graph = _require_graph(request)

    if context_mode in ("auto", "full") and graph:
        entity_names = load_entity_names(graph)
        entities_detected = detect_entities(question, entity_names)

        # Build entity context blocks (depth=1 for auto, depth=2 for full)
        entity_context = _get_entity_context_blocks(graph, entities_detected)

        # Read entity .md files (first 2000 chars each)
        entity_files = _read_entity_files(graph, entities_detected)

    # Vector search (if not in 'off' mode)
    citations: List[Dict[str, Any]] = []
    search_context = ""

    search_results: List[Dict[str, Any]] = []
    if context_mode in ("auto", "full"):
        try:
            result = hybrid(question)
            search_context = result.get("context", "")
            citations = result.get("citations", []) or []
            search_results = result.get("results", []) or []
        except Exception as exc:
            # Log but don't fail
            pass

    # Build final context for LLM
    context_parts = []
    if entity_context:
        context_parts.append(entity_context)
    if entity_files:
        context_parts.append(entity_files)
    if search_context:
        context_parts.append(search_context)

    final_context = "\n\n---\n\n".join(context_parts)

    # Build system prompt
    system_prompt = "You are a helpful assistant with access to a personal knowledge vault."
    if final_context:
        system_prompt += f"\n\nHere is relevant context from your vault:\n\n{final_context}"

    # Call LLM
    input_tokens = 0
    output_tokens = 0
    answer = ""
    error_msg = None

    if model.startswith("claude-"):
        # Use Claude API
        result = await claude_generate(
            model=model,
            prompt=question,
            system=system_prompt,
            max_tokens=2048,
        )
        if result["ok"]:
            answer = result.get("response", "")
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
        else:
            error_msg = result.get("error", "Claude API error")
            answer = f"Error: {error_msg}"
    else:
        # Use Ollama
        result = await _call_ollama_generate(
            model=model,
            prompt=question,
            system=system_prompt,
            max_tokens=2048,
        )
        if result.get("ok"):
            answer = result.get("response", "")
            usage = result.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        else:
            error_msg = result.get("error", "Ollama error")
            answer = f"Error: {error_msg}"

    # Calculate cost and latency
    cost_usd = calculate_cost(model, input_tokens, output_tokens)
    latency_ms = int((time.time() - start_time) * 1000)

    # Log query
    try:
        log_query(
            model=model,
            context_mode=context_mode,
            question=question,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            entities_detected=entities_detected,
            citations_count=len(citations),
        )
    except Exception:
        pass  # Don't fail if logging fails

    # Build discovery links (with real cosine from search_results)
    discovery = _build_discovery_links(citations, results=search_results, limit=10)

    # Build response
    return QueryResponse(
        answer=answer,
        model=model,
        context_mode=context_mode,
        entities_detected=entities_detected,
        citations=[
            Citation(
                **_parse_citation_string(c),
                score=round(
                    next(
                        (r["cosine"] for r in search_results
                         if r.get("path") == _parse_citation_string(c).get("path")
                         and r.get("cosine") is not None),
                        0.0,
                    ),
                    4,
                ),
            ) if isinstance(c, str) else Citation(
                title=c.get("title", ""),
                path=c.get("path", ""),
                score=c.get("score", 0.0),
            )
            for c in citations[:5]
        ],
        discovery=discovery,
        tokens={"input": input_tokens, "output": output_tokens},
        latency_ms=latency_ms,
        cost_usd=round(cost_usd, 6),
        conversation_id=conversation_id,
    )


@router.get("/models")
async def get_models() -> Dict[str, List[ModelInfo]]:
    """Return available models with metadata."""
    models = [
        ModelInfo(
            id="gemma4:e4b",
            name="Gemma 4 E4B",
            provider="ollama",
            use_case="Advanced reasoning with vault knowledge",
            speed="2-4s",
            cost_per_query="$0.00",
            supports_context=True,
        ),
        ModelInfo(
            id="claude-haiku-4-5-20251001",
            name="Claude Haiku",
            provider="anthropic",
            use_case="Smart analysis at minimal cost",
            speed="1-2s",
            cost_per_query="~$0.001",
            supports_context=True,
        ),
        ModelInfo(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet",
            provider="anthropic",
            use_case="Deep reasoning & complex questions",
            speed="2-5s",
            cost_per_query="~$0.012",
            supports_context=True,
        ),
        ModelInfo(
            id="claude-opus-4-20250514",
            name="Claude Opus",
            provider="anthropic",
            use_case="Maximum intelligence for critical analysis",
            speed="5-15s",
            cost_per_query="~$0.063",
            supports_context=True,
        ),
    ]
    return {"models": models}


@router.get("/usage")
async def get_usage(days: int = 30) -> Dict[str, Any]:
    """Return usage statistics from query log."""
    try:
        from ..retrieval.query_log import get_usage_stats

        stats = get_usage_stats(days=min(days, 365))
        return stats
    except Exception as exc:
        return {
            "error": str(exc),
            "total_queries": 0,
            "total_cost_usd": 0.0,
            "by_model": {},
            "by_context_mode": {},
        }
