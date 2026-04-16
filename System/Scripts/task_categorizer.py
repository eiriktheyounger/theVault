#!/usr/bin/env python3
"""
task_categorizer.py — 4-layer cascade categorization for vault tasks.

Layer 1: File path rules (fastest)
Layer 2: Entity detection via entity graph
Layer 3: Keyword counting
Layer 4: Ollama classification (qwen2.5:7b, fallback to #personal)

Usage:
    python3 -m System.Scripts.task_categorizer  (runs self-test)
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from System.Scripts.task_scanner import RawTask

logger = logging.getLogger(__name__)

CATEGORIES = ["#work", "#personal", "#career", "#tech", "#vault"]
DEFAULT_CATEGORY = "#personal"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4:e4b"
OLLAMA_TIMEOUT = 10

# ── Layer 1: File path rules ──────────────────────────────────────────────────

PATH_CATEGORY_MAP: list[tuple[str, str]] = [
    ("HarmonicInternal/", "#work"),
    ("Harmonic/", "#work"),
    ("Work/", "#work"),
    ("Personal/", "#personal"),
    ("JobSearch/", "#career"),
    ("Career/", "#career"),
    ("Interview/", "#career"),
    ("Projects/theVault", "#vault"),
    ("System/", "#vault"),
    ("Dashboards/", "#vault"),
    ("Projects/", "#tech"),
]

# ── Layer 2: Entity → category ────────────────────────────────────────────────

ENTITY_CATEGORY_MAP: dict[str, str] = {
    # Personal
    "rachel": "#personal", "bella": "#personal", "papa": "#personal",
    "adi": "#personal", "myra": "#personal", "doug": "#personal",
    "alyssa": "#personal",
    # Work
    "harmonic": "#work", "viewlift": "#work",
    # Career
    "tcgplayer": "#career", "draftKings": "#career", "oracle": "#career",
    "cloudwalk": "#career", "akamai": "#career",
    "ron forrester": "#career", "callum": "#career",
}

# ── Layer 3: Keyword lists ─────────────────────────────────────────────────────

KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "#career": [
        "resume", "interview", "prep", "recruiter", "offer", "compensation",
        "job search", "linkedin", "cover letter", "portfolio", "salary",
        "hiring manager", "negotiate", "background check", "onboarding",
        "job", "application", "referral",
    ],
    "#personal": [
        "groceries", "doctor", "dentist", "pharmacy", "birthday",
        "anniversary", "dinner", "restaurant", "appointment", "jewel",
        "jewelry", "ring", "silver", "health", "gym", "workout", "errands",
        "family", "wedding", "gift", "travel", "vacation",
    ],
    "#work": [
        "demo", "presales", "customer", "client", "harmonic", "commission",
        "quota", "pipeline", "viewlift", "meeting", "sales", "deck",
        "presentation", "proposal", "contract", "renewal",
    ],
    "#tech": [
        "code", "script", "server", "api", "endpoint", "bug", "feature",
        "deploy", "git", "faiss", "rag", "model", "embedding", "ollama",
        "python", "fastapi", "database", "sqlite", "hnsw", "fix", "build",
        "test", "refactor", "install", "upgrade",
    ],
    "#vault": [
        "vault", "obsidian", "template", "dashboard", "plugin", "overnight",
        "processor", "daily note", "index", "rag server", "normalizer",
        "cron", "theVault",
    ],
}


def _layer1_path(source_file: str) -> Optional[str]:
    """Return category if file path matches a known prefix."""
    # Normalize to use forward slashes for matching
    path_str = source_file.replace("\\", "/")
    for prefix, cat in PATH_CATEGORY_MAP:
        if prefix in path_str:
            return cat
    return None


def _layer2_entities(task_text: str) -> Optional[str]:
    """Return category if a known entity is mentioned in the task text."""
    text_lower = task_text.lower()
    for entity, cat in ENTITY_CATEGORY_MAP.items():
        if entity.lower() in text_lower:
            return cat
    return None


def _layer3_keywords(task_text: str) -> Optional[str]:
    """Count keyword hits per category. Return highest-scoring category."""
    text_lower = task_text.lower()
    scores: dict[str, int] = {cat: 0 for cat in KEYWORD_CATEGORIES}
    for cat, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in text_lower:
                scores[cat] += 1

    best_cat = max(scores, key=lambda c: scores[c])
    if scores[best_cat] > 0:
        return best_cat
    return None


def _layer4_ollama(task_text: str, source_file: str) -> str:
    """Ask Ollama to classify. Returns category or DEFAULT_CATEGORY on failure."""
    prompt = (
        f'Classify this task into exactly one category.\n\n'
        f'Categories:\n'
        f'- work: Employment duties, client work, Harmonic Inc tasks\n'
        f'- personal: Life admin, family, health, errands, social\n'
        f'- career: Job search, interviews, resume, networking\n'
        f'- tech: Software development, side projects, coding\n'
        f'- vault: Obsidian vault maintenance, dashboard updates, system config\n\n'
        f'Task: "{task_text}"\n'
        f'Source file: "{Path(source_file).name}"\n\n'
        f'Respond with ONLY the category name (work/personal/career/tech/vault):'
    )
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            result = json.loads(resp.read())
            raw = result.get("response", "").strip().lower()
            for cat in ["work", "personal", "career", "tech", "vault"]:
                if cat in raw:
                    return f"#{cat}"
    except Exception as e:
        logger.warning(f"Ollama categorization failed: {e}")

    return DEFAULT_CATEGORY


def categorize(task: RawTask) -> str:
    """Run the 4-layer cascade and return a category string like '#work'."""
    # Already has a category — return it
    if task.has_category_tag and task.existing_category:
        return task.existing_category

    # Layer 1: path
    cat = _layer1_path(task.source_file)
    if cat:
        logger.debug(f"Layer1 match: {task.normalized_text[:40]} → {cat}")
        return cat

    # Layer 2: entities
    cat = _layer2_entities(task.normalized_text)
    if cat:
        logger.debug(f"Layer2 match: {task.normalized_text[:40]} → {cat}")
        return cat

    # Layer 3: keywords
    cat = _layer3_keywords(task.normalized_text)
    if cat:
        logger.debug(f"Layer3 match: {task.normalized_text[:40]} → {cat}")
        return cat

    # Layer 4: Ollama
    cat = _layer4_ollama(task.normalized_text, task.source_file)
    logger.debug(f"Layer4 (Ollama): {task.normalized_text[:40]} → {cat}")
    return cat


def categorize_batch(tasks: list[RawTask]) -> dict[int, str]:
    """
    Categorize a list of tasks. Returns dict of {task index: category}.
    Uses Ollama as little as possible by processing layers 1-3 first.
    """
    results: dict[int, str] = {}
    ollama_needed: list[tuple[int, RawTask]] = []

    for i, task in enumerate(tasks):
        if task.has_category_tag and task.existing_category:
            results[i] = task.existing_category
            continue
        cat = _layer1_path(task.source_file)
        if cat:
            results[i] = cat
            continue
        cat = _layer2_entities(task.normalized_text)
        if cat:
            results[i] = cat
            continue
        cat = _layer3_keywords(task.normalized_text)
        if cat:
            results[i] = cat
            continue
        ollama_needed.append((i, task))

    # Batch Ollama calls
    for i, task in ollama_needed:
        results[i] = _layer4_ollama(task.normalized_text, task.source_file)

    return results


if __name__ == "__main__":
    # Quick self-test
    test_cases = [
        ("Follow up with recruiter about timeline", "Vault/JobSearch/notes.md"),
        ("Buy groceries for dinner", "Vault/Personal/weekly.md"),
        ("Fix RAG server endpoint", "Vault/Projects/theVault/bugs.md"),
        ("Prepare ViewLift demo", "Vault/HarmonicInternal/demos.md"),
        ("Call Rachel about birthday plans", "Vault/Daily/2026/03/2026-03-21-DLY.md"),
    ]
    for text, path in test_cases:
        from dataclasses import dataclass
        task = RawTask(
            text=f"- [ ] {text}", normalized_text=text, source_file=path,
            line_number=1, format_type="standard", section_name="tasks",
            has_checkbox=True, is_completed=False, has_due_date=False,
            existing_due_date=None, has_category_tag=False, existing_category=None,
            file_modified_date="2026-03-21T10:00:00",
        )
        cat = categorize(task)
        print(f"{cat:12} — {text}")
