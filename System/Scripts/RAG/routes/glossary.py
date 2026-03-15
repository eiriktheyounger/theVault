from __future__ import annotations

import re
import shutil
from typing import Any, Dict, List

from fastapi import APIRouter, Body

from ..config import GLOSSARY_MD, OLD_GLOSSARY_MD
from ...utils import _norm_str

router = APIRouter(prefix="/glossary", tags=["glossary"])


def _parse_glossary_md(text: str) -> List[Dict[str, str]]:
    terms: List[Dict[str, str]] = []
    # patterns: "- Term: definition" or "* Term — definition" or "Term: definition" lines
    for line in text.splitlines():
        ln = line.strip()
        if not ln or ln.startswith("#"):
            continue
        m = re.match(r"^(?:[-*]\s*)?([^:—]+)\s*[:—]\s*(.+)$", ln)
        if m:
            term = m.group(1).strip()
            desc = m.group(2).strip()
            if term and desc:
                terms.append({"term": term, "definition": desc})
    return terms


def _render_glossary_md(items: List[Dict[str, str]]) -> str:
    lines = ["# Glossary", ""]
    for it in items:
        t = str(it.get("term", "")).strip()
        d = str(it.get("definition", "")).strip()
        if not t or not d:
            continue
        lines.append(f"- {t}: {d}")
    lines.append("")
    return "\n".join(lines)


@router.get("")
def get_glossary() -> Dict[str, Any]:
    text = GLOSSARY_MD.read_text(encoding="utf-8") if GLOSSARY_MD.exists() else ""
    items = _parse_glossary_md(text)
    return {"ok": True, "count": len(items), "terms": items}


@router.post("/upsert")
def upsert_glossary(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    terms_in = payload.get("terms")
    if not isinstance(terms_in, list):
        return {"ok": False, "error": "terms must be an array"}
    incoming: List[Dict[str, str]] = []
    for it in terms_in:
        if not isinstance(it, dict):
            continue
        t = str(it.get("term", "")).strip()
        d = str(it.get("definition", "")).strip()
        if t and d:
            incoming.append({"term": t, "definition": d})
    # Load current
    current_text = GLOSSARY_MD.read_text(encoding="utf-8") if GLOSSARY_MD.exists() else ""
    current = _parse_glossary_md(current_text)
    # Merge (upsert by term, case-insensitive)
    by_key: Dict[str, Dict[str, str]] = {}
    for it in current:
        if not isinstance(it, dict):
            continue
        key = _norm_str(it.get("term"))
        if key:
            by_key[key] = it
    for it in incoming:
        key = _norm_str(it.get("term"))
        if key:
            by_key[key] = it
    merged = list(by_key.values())
    # Backup existing file
    try:
        if GLOSSARY_MD.exists():
            shutil.copyfile(GLOSSARY_MD, OLD_GLOSSARY_MD)
    except Exception:
        pass
    # Write merged
    text_out = _render_glossary_md(merged)
    GLOSSARY_MD.write_text(text_out, encoding="utf-8")
    return {"ok": True, "count": len(merged)}
