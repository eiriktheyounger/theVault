from __future__ import annotations

import json
from typing import Any, Dict, List


def normalize_answer_field(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarantee that envelope['answer'] is always an OBJECT with keys:
      answer (str or {short/long}), citations (list), abstained (bool) present.
    Merge/dedupe top-level and inner citations.
    """
    top_cites: List[str] = envelope.get("citations") or []

    ans = envelope.get("answer")
    if isinstance(ans, dict):
        inner = ans
    elif isinstance(ans, str):
        # Attempt to parse stringified JSON
        try:
            maybe = json.loads(ans)
            inner = maybe if isinstance(maybe, dict) else {"answer": ans}
        except Exception:
            inner = {"answer": ans}
    else:
        inner = {"answer": "" if ans is None else str(ans)}

    inner.setdefault("answer", "")
    inner.setdefault("abstained", envelope.get("abstained", False))

    inner_cites = inner.get("citations") or []
    merged = list(dict.fromkeys([*top_cites, *inner_cites]))
    inner["citations"] = merged

    envelope["answer"] = inner
    envelope["citations"] = merged
    return envelope


def make_fallback_envelope(mode: str, context_paths: List[str]) -> Dict[str, Any]:
    """Return a v2 contract envelope representing a fallback abstention.

    ``context_paths`` are deduplicated and used as citations. Both the
    inner answer object and the envelope copy these citations. ``mode`` is
    included under ``raw`` for debugging.
    """
    cites = list(dict.fromkeys(context_paths or []))
    answer = {
        "short_summary": "",
        "long_summary": "",
        "abstained": True,
        "citations": cites,
    }
    envelope: Dict[str, Any] = {
        "answer": answer,
        "abstained": True,
        "citations": cites,
        "raw": {"mode": mode, "context_paths": cites},
        "contract_version": "v2",
    }
    return envelope
