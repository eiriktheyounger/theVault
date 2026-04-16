# routes/fast.py — FAST lane with simple Ollama wrapper

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional
from uuid import uuid4

import requests
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ..config import (
    FAST_CTX,
    FAST_MODEL,
    FORCE_NO_ABSTAIN_FAST,
    OLLAMA_HOST,
)
from ..logs.service import write_llm_debug, write_log
from ..logutil import get_logger
from ..retrieval.search_fast import hybrid
from ..storage.chats import (
    append_jsonl,
    ensure_chat_dirs,
    get_pin,
    set_pin,
)
from ..rag.qa import glossary_lookup

from ..llm.contract import make_fallback_envelope, normalize_answer_field
from ..utils.obs import new_event_id, validate_contract, write_event

router = APIRouter()
log = get_logger("route.fast")


def _parse_keep_alive(req: Request) -> str:
    raw = req.query_params.get("keep_alive")
    try:
        seconds = int(raw) if raw is not None else 0
    except ValueError:
        log.warning("keep_alive.invalid", value=raw)
        seconds = 0
    clamped = max(0, min(seconds, 5400))
    if clamped != seconds:
        log.warning("keep_alive.out_of_range", requested=seconds, used=clamped)
    return f"{clamped}s"


def _call_ollama_markdown(*, model: str, prompt: str, keep_alive: str) -> Dict[str, Any]:
    url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"temperature": 0.2, "num_ctx": FAST_CTX},
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        # Extract content from new API format: data["message"]["content"]
        content = data.get("message", {}).get("content", "")
        return {"answer": content.strip(), "raw_model": data}
    except Exception as e:
        # Use logging module directly instead of log.error
        import logging
        logging.error(f"ollama.error: {str(e)}")
        return {"answer": "", "raw_model": {"error": str(e)}}


class FastBody(BaseModel):
    q: str
    cid: Optional[str] = Field(default=None, alias="cid")


@router.post("/fast")
def fast(req: Request, body: FastBody):
    start = time.time()
    q = (body.q or "").strip()
    keep_alive = _parse_keep_alive(req)
    cid = body.cid or uuid4().hex

    path = get_pin(cid)
    if path is None:
        path = ensure_chat_dirs("fast", datetime.now(UTC), cid)
        set_pin(cid, path)

    append_jsonl(
        path,
        {
            "ts": datetime.now(UTC).isoformat(),
            "role": "user",
            "mode": "fast",
            "short": q,
            "long": "",
            "citations": [],
            "fast_answer": None,
            "meta": {},
        },
    )

    # 1) Glossary lookup
    g_hit = glossary_lookup(q)
    if g_hit:
        ans, cite = g_hit
        cite_str = f"{cite['path']}:{cite['lines'][0]}-{cite['lines'][1]}"
        envelope = {
            "answer": ans,
            "abstained": False,
            "citations": [cite_str],
            "raw": {"lane": "FAST", "question": q, "glossary": cite},
        }
        envelope = normalize_answer_field(envelope)
        envelope["contract_version"] = "v2"
        log.info("fast.glossary_hit", question=q, citation=cite_str)
        append_jsonl(
            path,
            {
                "ts": datetime.now(UTC).isoformat(),
                "role": "assistant",
                "mode": "fast",
                "short": ans,
                "long": ans,
                "citations": envelope.get("citations", []),
                "fast_answer": ans,
                "meta": {"retrieval": {"source_mode": "glossary"}},
            },
        )
        end = time.time()
        duration_ms = int((end - start) * 1000)
        event = {
            "event_id": new_event_id(),
            "ts_ms": int(start * 1000),
            "name": "fast",
            "lane": "FAST",
            "model": FAST_MODEL,
            "prompt": "",
            "system_prompt": "",
            "retrieval_paths": [cite_str],
            "source_mode": "glossary",
            "top_k": 0,
            "chunk_size_tokens": None,
            "raw_envelope": envelope,
            "duration_ms": duration_ms,
            "timing": {
                "start_ms": int(start * 1000),
                "end_ms": int(end * 1000),
                "duration_ms": duration_ms,
            },
        }
        validation = validate_contract(envelope)
        event["contract_ok"] = validation["ok"]
        event["contract_reasons"] = validation["reasons"]
        event["envelope_preview"] = json.dumps(
            {
                "answer": envelope.get("answer"),
                "abstained": envelope.get("abstained"),
                "citations": envelope.get("citations"),
            },
            ensure_ascii=False,
        )[:1000]
        write_event(event)
        envelope["cid"] = cid
        return envelope

    # 2) Retrieval
    h: Dict[str, Any] = hybrid(q)
    if h.get("index_updated"):
        write_log("rag_server", "index updated ...")
    ctx = h.get("context", "") or ""
    cites = h.get("citations", []) or []
    retr = h.get("retrieval", {}) or {}
    abstain_hint = bool(h.get("abstain_hint", False))

    # 3) Synthesis
    system_prompt = "You are a concise assistant. Use ONLY the provided context."
    prompt = (
        f"{system_prompt}\n\nQuestion: {q}\n\nContext:\n{ctx}\n\n"
        "Answer clearly. If context is insufficient, state that briefly."
    )

    event = {
        "event_id": new_event_id(),
        "ts_ms": int(start * 1000),
        "name": "fast",
        "lane": "FAST",
        "model": FAST_MODEL,
        "prompt": prompt,
        "system_prompt": system_prompt,
        "retrieval_paths": cites,
        "source_mode": retr.get("source_mode", "vault"),
        "top_k": retr.get("topk"),
        "chunk_size_tokens": retr.get("chunk_size_tokens"),
    }
    forced_abstain = abstain_hint and not FORCE_NO_ABSTAIN_FAST
    ans = ""
    try:
        j = _call_ollama_markdown(model=FAST_MODEL, prompt=prompt, keep_alive=keep_alive)
        ans = (j.get("answer") or "").strip()
        write_llm_debug(
            "llm_server", {"mode": "fast", "q": q, "chat_id": cid, "response_preview": ans[:200]}
        )
        envelope = {
            "answer": ans,
            "abstained": forced_abstain,
            "citations": [],
            "raw": {
                "lane": "FAST",
                "question": q,
                "context": ctx,
                "citations": cites,
                "retrieval": retr,
                "abstain_hint": abstain_hint,
                "ollama": j.get("raw_model"),
            },
        }
    except Exception as e:
        log.error("fast.fallback", error=str(e))
        envelope = make_fallback_envelope("FAST", cites)

    envelope["citations"] = list(dict.fromkeys([*(envelope.get("citations") or []), *cites]))
    envelope = normalize_answer_field(envelope)
    envelope["contract_version"] = "v2"

    log.info(
        "fast.response",
        question=q,
        keep_alive=keep_alive,
        retrieval_summary={"vec_topcos": retr.get("vec_topcos"), "fused": retr.get("fused")},
        citations=len(cites),
        ctx_chars=len(ctx),
        ans_chars=len(ans),
    )

    event["raw_envelope"] = envelope
    end = time.time()
    duration_ms = int((end - start) * 1000)
    event["duration_ms"] = duration_ms
    event["timing"] = {
        "start_ms": int(start * 1000),
        "end_ms": int(end * 1000),
        "duration_ms": duration_ms,
    }
    validation = validate_contract(envelope)
    event["contract_ok"] = validation["ok"]
    event["contract_reasons"] = validation["reasons"]
    event["envelope_preview"] = json.dumps(
        {
            "answer": envelope.get("answer"),
            "abstained": envelope.get("abstained"),
            "citations": envelope.get("citations"),
        },
        ensure_ascii=False,
    )[:1000]
    append_jsonl(
        path,
        {
            "ts": datetime.now(UTC).isoformat(),
            "role": "assistant",
            "mode": "fast",
            "short": ans,
            "long": ans,
            "citations": envelope.get("citations", []),
            "fast_answer": ans,
            "meta": {"retrieval": retr},
        },
    )

    write_event(event)
    envelope["cid"] = cid
    return envelope
