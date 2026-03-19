"""entity_detector.py — Detect entity names in a search query.

Loads known entity names from the graph and matches them against queries
using case-insensitive substring matching.
"""
from __future__ import annotations

import re

import networkx as nx

# Entity types that live in Context_* folders
_CONTEXT_TYPES = {"person", "company", "technology", "place"}


def load_entity_names(graph: nx.DiGraph) -> dict[str, str]:
    """Return a mapping of {lowercase_name: node_id} for all context-file nodes.

    Includes both full node names and first-name tokens so that queries like
    "What is Rachel doing?" match "Rachel_Manchester".
    """
    mapping: dict[str, str] = {}
    for node_id, data in graph.nodes(data=True):
        if data.get("type") not in _CONTEXT_TYPES:
            continue
        # Full name (lowercased, underscores replaced with spaces)
        full_lower = node_id.lower()
        mapping[full_lower] = node_id
        # Also map with underscores converted to spaces
        spaced = full_lower.replace("_", " ")
        if spaced != full_lower:
            mapping[spaced] = node_id
        # First token (first name / short name)
        first = re.split(r"[_\s]+", node_id)[0].lower()
        if first and first not in mapping:
            mapping[first] = node_id

    return mapping


def detect_entities(query: str, entity_names: dict[str, str]) -> list[str]:
    """Return a deduplicated list of node IDs detected in *query*.

    Matching is case-insensitive substring search. Longer names are checked
    first to prevent a short first-name alias from shadowing a full name.
    """
    query_lower = query.lower()
    matched_ids: dict[str, int] = {}  # node_id → match_length (keep longest)

    for name, node_id in entity_names.items():
        if name in query_lower:
            prev = matched_ids.get(node_id, 0)
            if len(name) > prev:
                matched_ids[node_id] = len(name)

    # Return unique node IDs, sorted by match length descending (most specific first)
    return [nid for nid, _ in sorted(matched_ids.items(), key=lambda x: -x[1])]
