"""entity_graph.py — NetworkX-based wikilink graph over the Vault.

Built once at server startup, held in a module-level variable.
Call build_graph() to populate; call get_graph() to access.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import networkx as nx

# ---- Module-level graph cache ------------------------------------------------
_GRAPH: nx.DiGraph | None = None

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

# Top-level vault folders excluded from graph (legacy/dupe/system content)
# Updated 2026-04-27: HarmonicInternal moved out-of-vault; _Dupes/_archive excluded.
_EXCLUDE_TOP_LEVEL: set[str] = {
    "_Dupes",
    "_archive",
    "HarmonicInternal",  # safety: even after move, exclude in case legacy paths re-appear
    ".obsidian",
    ".trash",
}

# Mapping from vault folder name → entity type
_FOLDER_TYPE_MAP: dict[str, str] = {
    "Context_People": "person",
    "Context_Companies": "company",
    "Context_Technology": "technology",
    "Context_Places": "place",
}


def _is_excluded(rel_path: Path) -> bool:
    """Return True if the file's top-level folder is in the exclude set."""
    parts = rel_path.parts
    return bool(parts) and parts[0] in _EXCLUDE_TOP_LEVEL


def _node_type(rel_path: Path) -> str:
    """Derive the entity type from the relative vault path."""
    parts = rel_path.parts
    if len(parts) >= 2:
        folder = parts[0]
        if folder in _FOLDER_TYPE_MAP:
            return _FOLDER_TYPE_MAP[folder]
        if folder == "Daily" or (len(parts) >= 3 and parts[0] == "Daily"):
            return "daily"
    # Also catch Daily notes nested under Daily/YYYY/MM/...
    if "Daily" in parts:
        return "daily"
    return "note"


def build_graph(vault_path: str | Path) -> nx.DiGraph:
    """Scan all markdown files in *vault_path*, build and return a directed graph.

    Each node is a file identified by its stem (filename without .md).
    Each edge is a [[wikilink]] from one file to another.
    """
    global _GRAPH
    vault = Path(vault_path)
    g: nx.DiGraph = nx.DiGraph()

    # First pass: register all nodes
    for md_file in vault.rglob("*.md"):
        try:
            rel = md_file.relative_to(vault)
        except ValueError:
            continue
        if _is_excluded(rel):
            continue
        stem = md_file.stem
        ntype = _node_type(rel)
        if stem not in g:
            g.add_node(stem, type=ntype, path=str(rel), title=stem)
        else:
            # Node already added via a wikilink reference; fill in attributes
            g.nodes[stem]["type"] = ntype
            g.nodes[stem]["path"] = str(rel)
            g.nodes[stem]["title"] = stem

    # Second pass: extract wikilinks and add edges
    for md_file in vault.rglob("*.md"):
        try:
            rel = md_file.relative_to(vault)
        except ValueError:
            continue
        if _is_excluded(rel):
            continue
        source_stem = md_file.stem
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in WIKILINK_RE.finditer(text):
            target = match.group(1).strip().lstrip("[")
            # Strip any path prefix (e.g. [[Folder/Note]] → "Note")
            target_stem = Path(target).stem
            if not target_stem:
                continue
            # Ensure target node exists (may not have a .md file)
            if target_stem not in g:
                g.add_node(target_stem, type="note", path="", title=target_stem)
            if source_stem != target_stem:
                g.add_edge(source_stem, target_stem, source_path=str(rel), weight=1)

    _GRAPH = g
    return g


def get_graph() -> nx.DiGraph | None:
    """Return the cached graph (None if not yet built)."""
    return _GRAPH


def get_entity(graph: nx.DiGraph, name: str) -> dict[str, Any] | None:
    """Fuzzy lookup: find a node matching *name*.

    Priority:
    1. Exact match on node id (case-insensitive)
    2. Exact match on title attribute (case-insensitive)
    3. Substring match — node id starts with or contains the name
    """
    name_lower = name.strip().lower()
    if not name_lower:
        return None

    # 1. Exact match on node id
    for node_id, data in graph.nodes(data=True):
        if node_id.lower() == name_lower:
            return {"id": node_id, **data}

    # 2. Exact first-token match (e.g. "Rachel" → "Rachel_Manchester")
    for node_id, data in graph.nodes(data=True):
        parts = re.split(r"[_\s]+", node_id.lower())
        if parts and parts[0] == name_lower:
            return {"id": node_id, **data}

    # 3. Substring match (node id contains the name)
    candidates = [
        (node_id, data)
        for node_id, data in graph.nodes(data=True)
        if name_lower in node_id.lower()
    ]
    if candidates:
        # Prefer context-file nodes
        for node_id, data in candidates:
            if data.get("type") in ("person", "company", "technology", "place"):
                return {"id": node_id, **data}
        node_id, data = candidates[0]
        return {"id": node_id, **data}

    return None


def get_connections(
    graph: nx.DiGraph, name: str, depth: int = 2
) -> list[dict[str, Any]]:
    """Return all nodes within *depth* hops of the named entity.

    Uses the undirected view of the graph so links in both directions count.
    """
    entity = get_entity(graph, name)
    if entity is None:
        return []

    source_id = entity["id"]
    ug = graph.to_undirected()

    results: list[dict[str, Any]] = []
    visited: dict[str, int] = {source_id: 0}
    queue: list[tuple[str, int, list[str]]] = [(source_id, 0, [])]

    while queue:
        current, hop, path = queue.pop(0)
        if hop >= depth:
            continue
        for neighbor in ug.neighbors(current):
            if neighbor in visited:
                continue
            visited[neighbor] = hop + 1
            ndata = graph.nodes[neighbor]
            results.append(
                {
                    "name": neighbor,
                    "type": ndata.get("type", "note"),
                    "path": ndata.get("path", ""),
                    "hop_distance": hop + 1,
                    "connecting_nodes": path + [current],
                }
            )
            queue.append((neighbor, hop + 1, path + [current]))

    return results


def get_entity_context(graph: nx.DiGraph, name: str) -> str:
    """Return a formatted text block summarising the entity and its connections.

    Format:
        Entity: Rachel_Manchester (person)
        Direct connections: Eric_Manchester (person), Alyssa (person)
        Related notes: 2026-03-16-DLY, 2026-03-15-DLY
    """
    entity = get_entity(graph, name)
    if entity is None:
        return f"Entity '{name}' not found in graph."

    entity_id = entity["id"]
    entity_type = entity.get("type", "note")
    lines: list[str] = [f"Entity: {entity_id} ({entity_type})"]

    direct = get_connections(graph, name, depth=1)
    non_daily = [c for c in direct if c.get("type") != "daily"]
    daily = [c for c in direct if c.get("type") == "daily"]

    if non_daily:
        conn_str = ", ".join(
            f"{c['name']} ({c['type']})" for c in non_daily[:15]
        )
        lines.append(f"Direct connections: {conn_str}")

    if daily:
        note_str = ", ".join(c["name"] for c in daily[:10])
        lines.append(f"Related notes: {note_str}")

    return "\n".join(lines)
