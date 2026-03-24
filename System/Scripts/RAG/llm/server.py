# System/Scripts/RAG/llm/server.py
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import deep_llama, fast_phi3

# ---- Local imports ----
from ..retrieval import search_deep, search_fast

# Import deep history routes
# Import route modules
from ..routes import health as health_routes
from ..routes import graph as graph_routes

# ---- Logger setup ----
log = logging.getLogger(__name__)

# Import vault organizer API
try:
    from ...vault_organizer.api import app as organizer_app
    ORGANIZER_AVAILABLE = True
except ImportError:
    ORGANIZER_AVAILABLE = False
    log.warning("Vault organizer API not available")

from .contract import (
    make_fallback_envelope,
)
from .contract import (
    normalize_answer_field as _normalize_answer_field,
)

# -----------------------

load_dotenv()

log = logging.getLogger("llm.server")
logging.basicConfig(level=logging.INFO)

FAST_MODEL_DEFAULT = "qwen2.5:7b"
DEEP_MODEL_DEFAULT = "llama3.1:8b"

# ---- Runtime configuration ----
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "30"))
FAST_MODEL = os.getenv("FAST_MODEL", FAST_MODEL_DEFAULT)
DEEP_MODEL = os.getenv("DEEP_MODEL", DEEP_MODEL_DEFAULT)
MODEL_CTX = int(os.getenv("MODEL_CTX", os.getenv("NEROSPICY_CTX_TOKENS", "4096")))
ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

log.info(
    "OLLAMA_HOST=%s FAST_MODEL=%s (default=%s) DEEP_MODEL=%s (default=%s)",
    OLLAMA_HOST,
    FAST_MODEL,
    FAST_MODEL_DEFAULT,
    DEEP_MODEL,
    DEEP_MODEL_DEFAULT,
)

# Shared HTTP client for all Ollama requests
CLIENT = httpx.AsyncClient(timeout=float(os.getenv("OLLAMA_TIMEOUT_S", "60")))

# In-memory record of pinned chats
PINNED_CHATS: set[str] = set()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Lifespan startup/shutdown (replaces deprecated on_event hooks)."""
    # Startup: glossary warm + Ollama connectivity
    base = OLLAMA_HOST.rstrip("/")
    try:
        from ..config import GLOSSARY_MD

        gtext = ""
        gterms: list[tuple[str, str]] = []
        if GLOSSARY_MD.exists():
            raw = GLOSSARY_MD.read_text(encoding="utf-8")
            for line in raw.splitlines():
                ln = line.strip()
                if not ln or ln.startswith("#"):
                    continue
                m = re.match(r"^(?:[-*]\s*)?([^:—]+)\s*[:—]\s*(.+)$", ln)
                if m:
                    ks = m.group(1).strip()
                    vs = m.group(2).strip()
                    if ks and vs:
                        gterms.append((ks, vs))
                        if len(gterms) <= 30:
                            gtext += ("\n" if gtext else "Glossary\n") + f"- {ks}: {vs}"
        app.state.glossary_terms = gterms
        app.state.glossary_warm = gtext
    except Exception:
        app.state.glossary_terms = []
        app.state.glossary_warm = ""
    version_url = f"{base}/api/version"

    if "PYTEST_CURRENT_TEST" in os.environ:
        log.info("Skipping Ollama connectivity check during tests")
        app.state.ollama_ok = False
        app.state.ollama_version = None
        app.state.models = []
        app.state.fast_model_ok = False
        app.state.deep_model_ok = False
    else:
        max_attempts = int(os.getenv("OLLAMA_CONNECT_RETRIES", "5"))
        delay = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                v_resp = await CLIENT.get(version_url)
                v_resp.raise_for_status()
                tags = await ollama_tags()
                if tags.get("error"):
                    raise RuntimeError(tags["error"])
                version_data = v_resp.json()
                models = [m.get("model") or m.get("name") for m in tags.get("models", []) or []]
                app.state.ollama_ok = True
                app.state.ollama_version = version_data.get("version")
                app.state.models = models
                app.state.fast_model_ok = FAST_MODEL in models
                app.state.deep_model_ok = DEEP_MODEL in models
                break
            except Exception as exc:
                log.warning(
                    "ollama.startup_failed attempt %s/%s: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt >= max_attempts:
                    log.error(
                        "Failed to connect to %s. Is `ollama serve` running?",
                        OLLAMA_HOST,
                    )
                    app.state.ollama_ok = False
                    app.state.ollama_version = None
                    app.state.models = []
                    app.state.fast_model_ok = False
                    app.state.deep_model_ok = False
                else:
                    await asyncio.sleep(delay)
                    delay *= 2

    # Build entity graph from vault (offloaded to thread to avoid blocking event loop)
    try:
        from ..retrieval.entity_graph import build_graph
        from ..config import VAULT_ROOT
        import asyncio

        loop = asyncio.get_event_loop()
        graph = await loop.run_in_executor(None, build_graph, VAULT_ROOT)
        app.state.entity_graph = graph
        log.info(
            "Entity graph built: %d nodes, %d edges",
            graph.number_of_nodes(),
            graph.number_of_edges(),
        )
    except Exception as _graph_exc:
        log.warning("entity_graph.build_failed: %s", _graph_exc)
        app.state.entity_graph = None

    try:
        yield
    finally:
        try:
            await CLIENT.aclose()
        except Exception:
            pass


# ---------- FastAPI app ----------
app = FastAPI(title="theVault LLM Server", version="1.0.0", lifespan=_lifespan)

# Include routers
app.include_router(health_routes.router)
app.include_router(graph_routes.router)

# Mount vault organizer API as sub-application
if ORGANIZER_AVAILABLE:
    # Share Ollama configuration with organizer
    from ...vault_organizer.api import set_ollama_config, state
    set_ollama_config(
        host=OLLAMA_HOST,
        model=FAST_MODEL,  # Use fast model for organizer
        timeout=OLLAMA_TIMEOUT_S
    )
    
    app.mount("/organizer", organizer_app)
    log.info("Mounted Vault Organizer API at /organizer")
    
    # Initialize organizer state (sub-app startup events don't fire automatically)
    try:
        state.initialize()
        log.info("Vault Organizer state initialized")
    except Exception as e:
        log.error(f"Failed to initialize Vault Organizer: {e}")

# Allow requests from any origin
ALLOWED_ORIGINS = ["*"]

# Allow Vite dev (5173) and preview/prod (4173)
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

## (removed duplicate early /healthz and /about; single definitions live later)


# Where to search for log files
LOG_ROOTS = [
    Path("Vault/System/Logs/llm_debug"),
    Path("Vault/System/Logs"),
]


# Startup/shutdown handled via lifespan above


# ---------- Helpers ----------
def _get_q(data: Dict[str, Any]) -> str:
    """Return a trimmed question value from common keys."""
    if not isinstance(data, dict):
        return ""
    for key in ("question", "q", "prompt", "text"):
        value = data.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
    return ""


def _clip(text: str, max_chars: int) -> str:
    """Truncate *text* to at most *max_chars* characters."""
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def _model_ready(model: str) -> bool:
    models = getattr(app.state, "models", [])
    return model in models and bool(getattr(app.state, "ollama_ok", False))


async def ollama_tags() -> Dict[str, Any]:
    """Return model tags from Ollama or an error payload."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
    try:
        resp = await CLIENT.get(url)
    except httpx.RequestError as exc:
        return {
            "models": [],
            "error": {"type": "upstream_error", "status_code": None, "body": str(exc)},
        }
    if resp.status_code != 200:
        snippet = _clip(resp.text or "", 200)
        err_type = "model_not_available" if resp.status_code == 404 else "upstream_error"
        return {
            "models": [],
            "error": {"type": err_type, "status_code": resp.status_code, "body": snippet},
        }
    try:
        data = resp.json()
    except Exception:
        snippet = _clip(resp.text or "", 200)
        return {
            "models": [],
            "error": {"type": "upstream_error", "status_code": resp.status_code, "body": snippet},
        }
    return {"models": data.get("models", []), "error": None}


async def generate(model: str, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    """Call Ollama /api/chat (migrated from deprecated /api/generate) and return JSON or structured error."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
    # Convert prompt to messages format for new API
    messages = [{"role": "user", "content": _clip(prompt, MODEL_CTX)}]
    payload: Dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if system:
        # System message goes at the beginning in chat format
        messages.insert(0, {"role": "system", "content": system})
        payload["messages"] = messages
    try:
        resp = await CLIENT.post(url, json=payload)
    except httpx.TimeoutException:
        return {
            "ok": False,
            "error": {"type": "upstream_error", "status_code": None, "body": "timeout"},
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "error": {"type": "upstream_error", "status_code": None, "body": str(exc)},
        }
    if resp.status_code != 200:
        snippet = _clip(resp.text or "", 200)
        err_type = "model_not_available" if resp.status_code == 404 else "upstream_error"
        return {
            "ok": False,
            "error": {"type": err_type, "status_code": resp.status_code, "body": snippet},
        }
    try:
        data = resp.json()
    except Exception:
        snippet = _clip(resp.text or "", 200)
        return {
            "ok": False,
            "error": {"type": "upstream_error", "status_code": resp.status_code, "body": snippet},
        }
    text = data.get("response") or data.get("message", {}).get("content", "")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else ZERO_USAGE.copy()
    return {"ok": True, "response": text, "usage": usage, "error": None}


async def chat(
    model: str, messages: List[Dict[str, str]], system: Optional[str] = None
) -> Dict[str, Any]:
    """Call Ollama /api/chat and return JSON or structured error."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
    payload: Dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if system:
        payload["system"] = system
    try:
        resp = await CLIENT.post(url, json=payload)
    except httpx.TimeoutException:
        return {
            "ok": False,
            "error": {"type": "upstream_error", "status_code": None, "body": "timeout"},
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "error": {"type": "upstream_error", "status_code": None, "body": str(exc)},
        }
    if resp.status_code != 200:
        snippet = _clip(resp.text or "", 200)
        err_type = "model_not_available" if resp.status_code == 404 else "upstream_error"
        return {
            "ok": False,
            "error": {"type": err_type, "status_code": resp.status_code, "body": snippet},
        }
    try:
        data = resp.json()
    except Exception:
        snippet = _clip(resp.text or "", 200)
        return {
            "ok": False,
            "error": {"type": "upstream_error", "status_code": resp.status_code, "body": snippet},
        }
    text = data.get("message", {}).get("content") or data.get("response", "")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else ZERO_USAGE.copy()
    return {"ok": True, "response": text, "usage": usage, "error": None}


async def embed(model: str, prompt: str) -> Dict[str, Any]:
    """Call Ollama /api/embeddings and return JSON or structured error."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/embeddings"
    payload = {"model": model, "prompt": prompt}
    try:
        resp = await CLIENT.post(url, json=payload)
    except httpx.TimeoutException:
        return {
            "embedding": [],
            "usage": ZERO_USAGE.copy(),
            "error": {"type": "upstream_error", "status_code": None, "body": "timeout"},
        }
    except httpx.RequestError as exc:
        return {
            "embedding": [],
            "usage": ZERO_USAGE.copy(),
            "error": {"type": "upstream_error", "status_code": None, "body": str(exc)},
        }
    if resp.status_code != 200:
        snippet = _clip(resp.text or "", 200)
        err_type = "model_not_available" if resp.status_code == 404 else "upstream_error"
        return {
            "embedding": [],
            "usage": ZERO_USAGE.copy(),
            "error": {"type": err_type, "status_code": resp.status_code, "body": snippet},
        }
    try:
        data = resp.json()
    except Exception:
        snippet = _clip(resp.text or "", 200)
        return {
            "embedding": [],
            "usage": ZERO_USAGE.copy(),
            "error": {"type": "upstream_error", "status_code": resp.status_code, "body": snippet},
        }
    if not isinstance(data.get("usage"), dict):
        data["usage"] = ZERO_USAGE.copy()
    if not isinstance(data.get("embedding"), list):
        data["embedding"] = []
    data["error"] = None
    return data


# Backwards compatibility for tests
ollama_generate = generate
ollama_chat = chat


class ChatMessage(BaseModel):
    role: str
    content: str


class DeepRequest(BaseModel):
    # Accept both "q" and legacy "question" fields
    q: Optional[str] = None
    question: Optional[str] = None
    prompt: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    system: Optional[str] = None
    chat_id: Optional[str] = None


# ---------- Logs ----------
@app.get("/logs")
def list_logs() -> List[str]:
    files: List[tuple[float, str]] = []
    for root in LOG_ROOTS:
        if not root.exists():
            continue
        for p in root.glob("*"):
            if p.is_file() and p.suffix.lower() in {".md", ".log"}:
                try:
                    files.append((p.stat().st_mtime, p.name))
                except OSError:
                    pass
    files.sort(reverse=True)
    seen = set()
    result: List[str] = []
    for _, name in files:
        if name in seen:
            continue
        result.append(name)
        seen.add(name)
        if len(result) >= 100:
            break
    return result


@app.get("/logs/{name}")
def fetch_log(name: str) -> Response:
    if Path(name).name != name:
        raise HTTPException(status_code=404)
    for root in LOG_ROOTS:
        if not root.exists():
            continue
        path = root / name
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8")
            return Response(text, media_type="text/plain")
    raise HTTPException(status_code=404)


# ---------- Health/About ----------
@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"service": "llm", "endpoints": ["/fast", "/deep"], "ok": True}


@app.get("/about")
def about(request: Request) -> Dict[str, Any]:
    """Live test compatibility: report service name at /about."""
    return {"service": "llm", "ok": True}


@app.get("/health/ollama")
async def health_ollama() -> Dict[str, Any]:
    """Check connectivity to the configured Ollama instance."""
    base = OLLAMA_HOST.rstrip("/")
    version_url = f"{base}/api/version"
    tags_url = f"{base}/api/tags"
    try:
        v_resp = await CLIENT.get(version_url)
        v_resp.raise_for_status()
        t_resp = await CLIENT.get(tags_url)
        t_resp.raise_for_status()
        version = v_resp.json().get("version")
        tags = t_resp.json()
        return {"ok": True, "version": version, "tags": tags}
    except Exception as err:  # pragma: no cover - defensive
        log.warning("ollama.health_failed: %s", err)
        raise HTTPException(status_code=503, detail={"ok": False, "error": str(err)})


# ---------- Endpoints ----------
@app.post("/chats/pin")
async def pin_chat(cid: str | None = None) -> Dict[str, Any]:
    """Pin a chat id in memory for the duration of the process."""
    if not cid:
        raise HTTPException(status_code=400, detail="cid required")
    PINNED_CHATS.add(cid)
    return {"ok": True}


@app.post("/fast")
async def fast_endpoint(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        body = {}
    q = _get_q(body)
    if not q:
        # Contract: explicit error when missing question
        envelope = _normalize_answer_field(
            {
                "id": uuid4().hex,
                "mode": "fast",
                "answer": "",
                "abstained": True,
                "citations": [],
                "usage": ZERO_USAGE.copy(),
                "error": "missing question",
            }
        )
        envelope["contract_version"] = "v2"
        return envelope
    q = re.sub(r"\n{3,}", "\n\n", q)
    system = body.get("system")
    if isinstance(system, str) and system.strip():
        system = system.strip()
    else:
        system = None
    if not _model_ready(FAST_MODEL):
        envelope = _normalize_answer_field(
            {
                "id": uuid4().hex,
                "mode": "fast",
                "answer": "",
                "abstained": True,
                "citations": [],
                "usage": ZERO_USAGE.copy(),
                "error": None,
            }
        )
        envelope["contract_version"] = "v2"
        envelope["text"] = " I do not know "
        return envelope
    context_paths: List[str] = []
    try:
        # 1) Glossary-first attempt
        import re as _re

        tokens = [t.lower() for t in _re.findall(r"[A-Za-z0-9_]+", q or "") if len(t) >= 3]
        terms: list[tuple[str, str]] = getattr(app.state, "glossary_terms", [])
        # Score glossary by fuzzy similarity against the query (term and definition)
        scored: list[tuple[float, str, str]] = []
        for term, desc in terms:
            try:
                s1 = difflib.SequenceMatcher(None, q.lower(), term.lower()).ratio()
                s2 = difflib.SequenceMatcher(None, q.lower(), desc.lower()).ratio()
                score = max(s1, s2)
                # Also quick token overlap boost
                if tokens and (
                    any(t in term.lower() for t in tokens) or any(t in desc.lower() for t in tokens)
                ):
                    score = max(score, 0.66)
                if score >= 0.5:
                    scored.append((score, term, desc))
            except Exception:
                continue
        scored.sort(reverse=True)
        selected = [(t, d) for _sc, t, d in scored[:12]]
        if selected:
            gtext = "Glossary\n" + "\n".join(f"- {t}: {d}" for t, d in selected)
            g_prompt = fast_phi3.prompt(context=gtext, question=q)
            log.info("LLM call (glossary-first): mode=%s model=%s", "fast", FAST_MODEL)
            j = await ollama_generate(FAST_MODEL, g_prompt, system)
            if j.get("ok") is True:
                raw = (j.get("response") or j.get("message", {}).get("content") or "").strip()
                try:
                    ans = json.loads(raw)
                except Exception:
                    ans = raw
                usage = j.get("usage") or ZERO_USAGE.copy()
                citations = ["Glossary (Vault/System/glossary.md)"]
                abstained = False
                confidence = None
                reasoning = None
                if isinstance(ans, dict):
                    abstained = bool(ans.pop("abstained", False))
                    confidence = ans.pop("confidence", None)
                    reasoning = ans.pop("reasoning", None)
                payload: Dict[str, Any] = {
                    "id": uuid4().hex,
                    "mode": "fast",
                    "answer": ans if isinstance(ans, str) else "",
                    "abstained": abstained,
                    "citations": citations,
                    "usage": usage if isinstance(usage, dict) else ZERO_USAGE.copy(),
                    "error": None,
                }
                if confidence is not None:
                    payload["confidence"] = confidence
                if reasoning is not None:
                    payload["reasoning"] = reasoning
                doc = _normalize_answer_field(payload)
                if isinstance(ans, dict):
                    doc["answer"].update(ans)
                    doc = _normalize_answer_field(doc)
                # Provide a top-level 'text'
                try:
                    if isinstance(ans, str) and ans.strip():
                        doc["text"] = ans.strip()
                    elif isinstance(ans, dict):
                        txt = (
                            (ans.get("answer") if isinstance(ans.get("answer"), str) else None)
                            or (
                                ans.get("long_summary")
                                if isinstance(ans.get("long_summary"), str)
                                else None
                            )
                            or (
                                ans.get("short_summary")
                                if isinstance(ans.get("short_summary"), str)
                                else None
                            )
                            or ""
                        )
                        doc["text"] = txt
                except Exception:
                    pass
                doc["contract_version"] = "v2"
                return doc

        # 2) Fallback: Vault retrieval (optionally prepend relevant glossary)
        result = search_fast.hybrid(q)
        context = result.get("context", "") or ""
        if not context.strip():
            # Fall back to model call with question only (no context)
            prompt = fast_phi3.prompt(context="", question=q)
            log.info("LLM call: mode=%s model=%s (no-context)", "fast", FAST_MODEL)
            j = await ollama_generate(FAST_MODEL, prompt, system)
            if j.get("ok") is False:
                envelope = _normalize_answer_field(
                    {
                        "id": uuid4().hex,
                        "mode": "fast",
                        "answer": "",
                        "abstained": True,
                        "citations": [],
                        "usage": j.get("usage")
                        if isinstance(j.get("usage"), dict)
                        else ZERO_USAGE.copy(),
                        "error": j.get("error"),
                    }
                )
                envelope["contract_version"] = "v2"
                return envelope
            raw = (j.get("response") or j.get("message", {}).get("content") or "").strip()
            try:
                ans = json.loads(raw)
            except Exception:
                ans = raw
            usage = j.get("usage") or ZERO_USAGE.copy()
            citations: list[str] = []
            abstained = False
            payload: Dict[str, Any] = {
                "id": uuid4().hex,
                "mode": "fast",
                "answer": ans if isinstance(ans, str) else "",
                "abstained": abstained,
                "citations": citations,
                "usage": usage if isinstance(usage, dict) else ZERO_USAGE.copy(),
                "error": None,
            }
            doc = _normalize_answer_field(payload)
            if isinstance(ans, dict):
                doc["answer"].update(ans)
                doc = _normalize_answer_field(doc)
            doc["contract_version"] = "v2"
            return doc
        # If we found retrieval, optionally add a small filtered glossary
        if selected:
            gtext = "Glossary\n" + "\n".join(f"- {t}: {d}" for t, d in selected[:6])
            context = f"{gtext}\n\n---\n\n{context}"
        context_paths = result.get("citations", []) or []
        prompt = fast_phi3.prompt(context=context, question=q)
        log.info("LLM call: mode=%s model=%s", "fast", FAST_MODEL)
        j = await ollama_generate(FAST_MODEL, prompt, system)
        if j.get("ok") is False:
            envelope = _normalize_answer_field(
                {
                    "id": uuid4().hex,
                    "mode": "fast",
                    "answer": "",
                    "abstained": True,
                    "citations": [],
                    "usage": j.get("usage")
                    if isinstance(j.get("usage"), dict)
                    else ZERO_USAGE.copy(),
                    "error": j.get("error"),
                }
            )
            envelope["contract_version"] = "v2"
            envelope["text"] = ""
            return envelope
        raw = (j.get("response") or j.get("message", {}).get("content") or "").strip()
        try:
            ans = json.loads(raw)
        except Exception:
            ans = raw
        usage = j.get("usage") or ZERO_USAGE.copy()
        citations = result.get("citations", []) or []
        abstained = False
        confidence = None
        reasoning = None
        ans_citations: List[str] = []
        if isinstance(ans, dict):
            abstained = bool(ans.pop("abstained", False))
            ans_citations = ans.pop("citations", []) or []
            confidence = ans.pop("confidence", None)
            reasoning = ans.pop("reasoning", None)
            if ans_citations:
                citations.extend([c for c in ans_citations if c not in citations])
        payload: Dict[str, Any] = {
            "id": uuid4().hex,
            "mode": "fast",
            "answer": ans if isinstance(ans, str) else "",
            "abstained": abstained,
            "citations": citations,
            "usage": usage if isinstance(usage, dict) else ZERO_USAGE.copy(),
            "error": None,
        }
        if confidence is not None:
            payload["confidence"] = confidence
        if reasoning is not None:
            payload["reasoning"] = reasoning
        doc = _normalize_answer_field(payload)
        if isinstance(ans, dict):
            doc["answer"].update(ans)
            doc = _normalize_answer_field(doc)
        # Provide a top-level 'text' field for UI compatibility
        try:
            if isinstance(ans, str) and ans.strip():
                doc["text"] = ans.strip()
            elif isinstance(ans, dict):
                txt = (
                    (ans.get("answer") if isinstance(ans.get("answer"), str) else None)
                    or (
                        ans.get("long_summary")
                        if isinstance(ans.get("long_summary"), str)
                        else None
                    )
                    or (
                        ans.get("short_summary")
                        if isinstance(ans.get("short_summary"), str)
                        else None
                    )
                    or ""
                )
                doc["text"] = txt
        except Exception:
            pass
        doc["contract_version"] = "v2"
        return doc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        envelope = make_fallback_envelope("fast", context_paths)
        envelope.update(
            {
                "id": uuid4().hex,
                "mode": "fast",
                "usage": ZERO_USAGE.copy(),
                "error": str(exc),
            }
        )
        return envelope


@app.post("/deep")
async def deep_endpoint(payload: DeepRequest) -> Dict[str, Any]:
    # Normalize q from either field name
    raw_q = (
        payload.q
        if isinstance(payload.q, str)
        else (payload.question if isinstance(payload.question, str) else payload.prompt)
    )
    q = (raw_q or "").strip() if isinstance(raw_q, str) else ""
    messages = payload.messages or []
    if not q and not messages:
        raise HTTPException(
            status_code=400,
            detail="Either 'q' (string) or 'messages' (array of chat messages) is required.",
        )
    system = (
        payload.system.strip()
        if isinstance(payload.system, str) and payload.system.strip()
        else None
    )
    cid = payload.chat_id or uuid4().hex
    if messages:
        try:
            if not _model_ready(DEEP_MODEL):
                raise HTTPException(
                    status_code=503, detail={"error": f"model '{DEEP_MODEL}' unavailable"}
                )
            j = await ollama_chat(DEEP_MODEL, [m.model_dump() for m in messages], system)
            log.debug(f"ollama_chat response: ok={j.get('ok')}, has_response={('response' in j)}, response_len={len(j.get('response', ''))}")
            if j.get("ok") is False:
                raise HTTPException(status_code=502, detail=j.get("error"))
            text = (j.get("response") or "").strip()
            if not text:
                log.warning(f"Empty response from ollama_chat, returning error. Full response: {j}")
                raise HTTPException(status_code=502, detail={"error": "Empty response from LLM"})
            # UI expects a JSON string with { cid, message: { content }, sources? }
            wrapped = json.dumps({"cid": cid, "message": {"content": text}})
            log.info(f"✅ Returning wrapped response, text length={len(text)}, cid={cid}")
            result = {"text": wrapped, "mode": "deep"}
            log.info(f"✅ Result keys: {list(result.keys())}")
            return result
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Error in /deep endpoint with messages: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail={"error": str(e)})
    q = re.sub(r"\n{3,}", "\n\n", q)
    if not _model_ready(DEEP_MODEL):
        raise HTTPException(status_code=503, detail={"error": f"model '{DEEP_MODEL}' unavailable"})
    try:
        result = search_deep.hybrid(q)
        context = result.get("context", "") or ""
        citations = result.get("citations", []) or []
        # If no context from Vault, fall back to a model call with the question only
        if not context.strip():
            j = await ollama_generate(DEEP_MODEL, deep_llama.prompt(context="", question=q), system)
            if j.get("ok") is False:
                wrapped = json.dumps(
                    {"cid": cid, "message": {"content": " I do not know "}, "sources": []}
                )
                return {"text": wrapped, "mode": "deep", "citations": []}
            raw = (j.get("response") or j.get("message", {}).get("content") or "").strip()
            return {"text": raw, "mode": "deep", "citations": []}
        prompt = deep_llama.prompt(context=context, question=q)
        log.info("LLM call: mode=%s model=%s", "deep", DEEP_MODEL)
        j = await ollama_generate(DEEP_MODEL, prompt, system)
        if j.get("ok") is False:
            raise HTTPException(
                status_code=502,
                detail={"error": j.get("error"), "usage": j.get("usage")},
            )
        raw = (j.get("response") or j.get("message", {}).get("content") or "").strip()
        try:
            ans = json.loads(raw)
        except Exception:
            ans = raw
        if isinstance(ans, dict):
            ans_citations = ans.pop("citations", []) or []
            if ans_citations:
                citations.extend([c for c in ans_citations if c not in citations])
            text = json.dumps(ans)
        else:
            text = ans
        # Wrap for UI chat transcript expectations
        wrapped = json.dumps({"cid": cid, "message": {"content": text}, "sources": citations})
        return {"text": wrapped, "mode": "deep", "citations": citations}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.post("/chat")
async def chat_endpoint(request: Request) -> Dict[str, Any]:
    """Conversational RAG endpoint for the Chat UI.

    Accepts: {message, conversation_history?, search_limit?}
    Returns: {answer, references, obsidian_links, confidence, took_ms, documents_retrieved}
    """
    import time

    t0 = time.monotonic()
    try:
        body = await request.json()
    except Exception:
        body = {}

    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    history = body.get("conversation_history") or []

    # 1. Retrieve context via hybrid search
    try:
        result = search_fast.hybrid(message)
        context = result.get("context", "") or ""
        raw_citations: list = result.get("citations", [])
    except Exception as exc:
        log.warning("chat hybrid search failed: %s", exc)
        context = ""
        raw_citations = []

    # 2. Build messages for Ollama /api/chat
    system_prompt = (
        "You are a personal knowledge assistant. "
        "Answer the user's question using only the context provided below. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"CONTEXT:\n{context}" if context else
        "You are a personal knowledge assistant. "
        "Answer based on your best understanding; no vault context was found for this query."
    )

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for h in history:
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    # 3. Call Ollama
    j = await ollama_chat(FAST_MODEL, messages)
    took_ms = int((time.monotonic() - t0) * 1000)

    if j.get("ok") is False:
        raise HTTPException(status_code=502, detail=j.get("error", "Ollama error"))

    answer_text = (
        j.get("message", {}).get("content")
        or j.get("response")
        or ""
    ).strip()

    # 4. Build references from citations — format: "Title (path)"
    references = []
    obsidian_links = []
    for cit in raw_citations:
        cit_str = str(cit)
        # Parse "Title (path)" format
        paren = cit_str.rfind("(")
        if paren != -1 and cit_str.endswith(")"):
            file_path = cit_str[paren + 1 : -1]
            file_name = cit_str[:paren].strip()
        else:
            file_path = cit_str
            file_name = cit_str.split("/")[-1]
        references.append({
            "file_path": file_path,
            "file_name": file_name,
            "relevance_score": 1.0,
        })
        obsidian_links.append(f"obsidian://open?vault=Vault&file={file_path}")

    confidence = "high" if context else "low"
    return {
        "answer": answer_text,
        "references": references,
        "obsidian_links": obsidian_links,
        "confidence": confidence,
        "took_ms": took_ms,
        "documents_retrieved": len(references),
    }


@app.get("/contract")
def contract() -> Dict[str, Any]:
    schema = {
        "fast": {
            "answer": {
                "short_summary": "string",
                "long_summary": "string",
                "abstained": "boolean",
                "citations": ["string"],
                "confidence?": "high|medium|low",
                "reasoning?": "string",
            }
        },
        "deep": {
            "answer": {
                "short_summary": "string",
                "long_summary": "string",
                "abstained": "boolean",
                "citations": ["string"],
                "confidence?": "high|medium|low",
                "reasoning?": "string",
            }
        },
    }
    return {
        "mode": None,
        "usage": ZERO_USAGE.copy(),
        "error": None,
        "schema": schema,
    }


# ---- Static file hosting ----------------------------------------------------
UI_DIST = Path(__file__).resolve().parents[4] / "ui" / "dist"
if UI_DIST.exists():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:  # pragma: no cover - file serving
        return FileResponse(UI_DIST / "index.html")


# Optional: allow running this module directly for quick tests
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("System.Scripts.RAG.llm.server:app", host="127.0.0.1", port=5111, reload=True)
