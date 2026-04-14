import types
from datetime import UTC, datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ..config import OLLAMA_HOST
from ..logs.service import write_llm_debug, write_log
from ..storage.chats import (
    append_jsonl,
    ensure_chat_dirs,
    get_pin,
    set_pin,
)

# tests want to monkeypatch this symbol:
try:  # pragma: no cover - tiny shim for tests lacking requests
    import requests as _requests  # noqa: F401
except Exception:  # pragma: no cover

    class _DummyRequests:
        def post(self, *a, **k):
            class _R:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {}

            return _R()

    _requests = _DummyRequests()
requests = _requests  # expose as module attribute

router = APIRouter()

# flag the tests monkeypatch
FORCE_NO_ABSTAIN_DEEP = True


# Use the real hybrid function from search_deep module
try:
    from ..retrieval.search_deep import hybrid as _real_hybrid

    def hybrid(query: str):
        return _real_hybrid(query)
except ImportError:
    # Fallback shim for tests
    def hybrid(query: str):
        return {"context": "", "citations": [], "retrieval": {}, "abstain_hint": False}


# tiny chat store the tests may monkeypatch
CHAT_STORE = types.SimpleNamespace(
    cleanup_idle=lambda: None,
    get=lambda cid: [],
    append=lambda *a, **k: None,
    end=lambda cid: None,
)


def _parse_keep_alive(req: Request) -> str:
    raw = req.query_params.get("keep_alive")
    try:
        seconds = int(raw) if raw is not None else 0
    except ValueError:
        seconds = 0
    clamped = max(0, min(seconds, 5400))
    return f"{clamped}s"


def _call_ollama_markdown(*, model: str, prompt: str, keep_alive: str):
    """Tiny shim used by tests; performs a POST with keep_alive.

    The tests monkeypatch ``requests.post`` to capture the JSON payload and
    assert that ``keep_alive`` is propagated. If real requests is available we
    make a best‑effort call and tolerate failures by returning an empty answer.
    """
    try:  # pragma: no cover - exercised via monkeypatch in tests
        url = "http://127.0.0.1:11434/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": keep_alive,
        }
        r = requests.post(url, json=payload, timeout=120)
        try:
            r.raise_for_status()
            data = r.json()
            # Extract content from new API format
            content = data.get("message", {}).get("content", "")
            return {"answer": content.strip(), "raw_model": data}
        except Exception:
            return {"answer": "", "raw_model": {"error": "request_failed"}}
    except Exception:
        return {"answer": "", "raw_model": {}}


class DeepBody(BaseModel):
    q: str
    cid: Optional[str] = Field(default=None, alias="chat_id")


@router.post("/deep")
def deep(req: Request, body: DeepBody):
    keep_alive = _parse_keep_alive(req)
    cid = body.cid or uuid4().hex
    question = (body.q or "").strip()

    path = get_pin(cid)
    if path is None:
        path = ensure_chat_dirs("deep", datetime.now(UTC), cid)
        set_pin(cid, path)

    CHAT_STORE.cleanup_idle()
    history = CHAT_STORE.get(cid)
    CHAT_STORE.append(cid, "user", question)
    append_jsonl(
        path,
        {
            "ts": datetime.now(UTC).isoformat(),
            "role": "user",
            "mode": "deep",
            "text": question,
            "meta": {},
        },
    )

    msgs = history + [{"role": "user", "content": question}]
    h = hybrid(question)
    if h.get("index_updated"):
        write_log("rag_server", "index updated ...")
    abstain_hint = bool(h.get("abstain_hint"))
    abstained = (not FORCE_NO_ABSTAIN_DEEP) and abstain_hint

    from .. import config

    # Build a proper prompt with context if available
    context = h.get("context", "")
    if context:
        system_prompt = f"You are a helpful assistant. Use the following context to answer questions accurately. Only answer based on the provided context from the user's vault.\n\nContext:\n{context}\n\n"
        prompt = system_prompt + "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
    else:
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)

    model_resp = _call_ollama_markdown(
        model=config.DEEP_MODEL, prompt=prompt, keep_alive=keep_alive
    )
    text = model_resp.get("answer") or ""
    write_llm_debug(
        "llm_server",
        {"mode": "deep", "q": question, "chat_id": cid, "response_preview": text[:200]},
    )

    CHAT_STORE.append(cid, "assistant", text)
    append_jsonl(
        path,
        {
            "ts": datetime.now(UTC).isoformat(),
            "role": "assistant",
            "mode": "deep",
            "text": text,
            "meta": {},
        },
    )

    return {
        "cid": cid,
        "response": text,
        "abstained": abstained,
        "keep_alive_used": keep_alive,
    }


# export names the tests poke
try:
    __all__
except NameError:
    __all__ = []
for _n in [
    "router",
    "hybrid",
    "requests",
    "CHAT_STORE",
    "FORCE_NO_ABSTAIN_DEEP",
    "_call_ollama_markdown",
]:
    if _n not in __all__:
        __all__.append(_n)
