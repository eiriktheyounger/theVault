"""routes/graph.py — Entity graph search and query endpoints.

New endpoints (do NOT modify existing /fast or /deep routes):
  POST /graph/search        — entity-augmented semantic search
  GET  /graph/entity/{name} — entity info and connections
  GET  /graph/stats         — graph statistics
  GET  /graph/rebuild       — rebuild graph from vault
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import VAULT_ROOT
from ..retrieval.entity_detector import detect_entities, load_entity_names
from ..retrieval.entity_graph import (
    build_graph,
    get_connections,
    get_entity,
    get_entity_context,
    get_graph,
)

router = APIRouter(prefix="/graph", tags=["graph"])


# ---------- helpers -----------------------------------------------------------


def _require_graph(request: Request):
    """Return the entity graph from app state or module cache."""
    graph = getattr(request.app.state, "entity_graph", None)
    if graph is None:
        graph = get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Entity graph not yet built.")
    return graph


# ---------- request / response models ----------------------------------------


class GraphSearchRequest(BaseModel):
    question: str
    limit: int = 5


# ---------- POST /graph/search -----------------------------------------------


@router.post("/search")
def graph_search(body: GraphSearchRequest, request: Request) -> dict[str, Any]:
    graph = _require_graph(request)
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    # 1. Detect entities in the query
    entity_names = load_entity_names(graph)
    detected_ids = detect_entities(question, entity_names)

    # 2. Build entity context blocks
    entity_context_parts: list[str] = []
    for node_id in detected_ids:
        ctx = get_entity_context(graph, node_id)
        entity_context_parts.append(ctx)
    entity_context = "\n\n".join(entity_context_parts)

    # 3. Run vector search (reuse existing fast search logic)
    search_results: dict[str, Any] = {}
    try:
        from ..retrieval.search_fast import hybrid

        result = hybrid(question)
        search_results = {
            "context": result.get("context", ""),
            "citations": result.get("citations", []),
        }
    except Exception as exc:
        search_results = {"context": "", "citations": [], "error": str(exc)}

    # 4. Combine entity context + vector search context
    vector_ctx = search_results.get("context", "") or ""
    if entity_context and vector_ctx:
        combined = f"{entity_context}\n\n---\n\n{vector_ctx}"
    elif entity_context:
        combined = entity_context
    else:
        combined = vector_ctx

    return {
        "entities_detected": detected_ids,
        "entity_context": entity_context,
        "search_results": search_results,
        "combined_context": combined,
    }


# ---------- GET /graph/entity/{name} -----------------------------------------


@router.get("/entity/{name}")
def graph_entity(name: str, request: Request) -> dict[str, Any]:
    graph = _require_graph(request)
    entity = get_entity(graph, name)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity '{name}' not found.")

    connections = get_connections(graph, entity["id"], depth=1)
    conn_list = [
        {
            "name": c["name"],
            "type": c["type"],
            "relationship": "linked",
            "path": c["path"],
        }
        for c in connections
    ]
    return {
        "name": entity["id"],
        "type": entity.get("type", "note"),
        "path": entity.get("path", ""),
        "connections": conn_list,
    }


# ---------- GET /graph/stats -------------------------------------------------


@router.get("/stats")
def graph_stats(request: Request) -> dict[str, Any]:
    graph = _require_graph(request)
    type_counts = Counter(
        data.get("type", "unknown") for _, data in graph.nodes(data=True)
    )
    degree_seq = sorted(graph.degree(), key=lambda x: x[1], reverse=True)
    most_connected = [
        {"name": node, "degree": deg} for node, deg in degree_seq[:10]
    ]
    return {
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "nodes_by_type": dict(type_counts),
        "most_connected": most_connected,
    }


# ---------- GET /graph/rebuild -----------------------------------------------


@router.get("/rebuild")
def graph_rebuild(request: Request) -> dict[str, Any]:
    graph = build_graph(VAULT_ROOT)
    request.app.state.entity_graph = graph
    type_counts = Counter(
        data.get("type", "unknown") for _, data in graph.nodes(data=True)
    )
    return {
        "ok": True,
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "nodes_by_type": dict(type_counts),
    }
