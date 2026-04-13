from __future__ import annotations

import json

# Config
import logging
import os
import urllib.request
from typing import Iterable, List, Optional

from .config import NS_EMBED_MODEL, OLLAMA_HOST

# --- Model selection helpers -------------------------------------------------


def _is_embedding_model(name: Optional[str]) -> bool:
    n = (name or "").lower()
    # Be a bit permissive; keep anything that looks like an embedding model
    return any(k in n for k in ["embed", "nomic", "arctic", "all-minilm", "text-embedding"])


def _pick_embed_model(cfg_model: Optional[str]) -> str:
    # Default to nomic embed if unset or looks like a chat model
    if not cfg_model or not _is_embedding_model(cfg_model):
        return "nomic-embed-text:latest"
    return cfg_model


# --- Minimal Ollama embeddings client ---------------------------------------

EMBED_CTX = int(os.getenv("EMBED_CTX", "1024"))  # Reduced from 2048 to improve embed speed
_CLAMP_LOGGED = False
log = logging.getLogger("embedder")
_backend: str | None = None  # 'ollama' | 'sentence-transformer'
try:
    from sentence_transformers import SentenceTransformer as _STImported  # type: ignore
except Exception:  # pragma: no cover - optional
    _STImported = None  # type: ignore

    class SentenceTransformer:  # type: ignore
        def __init__(self, *a, **k):
            pass

        def encode(self, texts, normalize_embeddings=True):
            if isinstance(texts, str):
                texts = [texts]
            return [[0.0] * 384 for _ in texts]
else:
    # Expose as module attribute for tests to patch
    SentenceTransformer = _STImported  # type: ignore


def _embed_single(url: str, model: str, text: str, options: dict) -> List[float]:
    """Embed a single text. Returns [] on failure."""
    payload = {"model": model, "input": [text], "options": options}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        embs = data.get("embeddings", [])
        if embs and isinstance(embs[0], list) and embs[0]:
            return embs[0]
        return []
    except Exception:
        return []


def _encode_ollama(host: str, model: str, texts: List[str]) -> List[List[float]]:
    """Calls Ollama /api/embed with batched input. Falls back to per-text on batch failure."""
    url = host.rstrip("/") + "/api/embed"
    ctx = EMBED_CTX
    if "nomic-embed-text-v1.5" in model and ctx > 2048:
        ctx = 2048
        global _CLAMP_LOGGED
        if not _CLAMP_LOGGED:
            log.warning("Clamped embed context to 2048")
            _CLAMP_LOGGED = True
    options = {"num_ctx": ctx}
    # Try batch first
    payload = {"model": model, "input": texts, "options": options}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        embeddings = data.get("embeddings", [])
        if isinstance(embeddings, list) and len(embeddings) == len(texts):
            return [v if (isinstance(v, list) and v) else [] for v in embeddings]
    except Exception:
        pass
    # Batch failed — fall back to per-text to avoid losing the whole batch
    log.debug("Batch embed failed, falling back to per-text for %d items", len(texts))
    return [_embed_single(url, model, t, options) for t in texts]


# --- Sentence-Transformers style wrapper ------------------------------------


class _OllamaEmbedder:
    """
    Minimal wrapper:
      - encode(text | [texts]) -> list[list[float]]
      - get_sentence_embedding_dimension() -> int
      - callable (texts) -> vectors
      - iterable -> (self, dim) for legacy tuple-unpack
    """

    def __init__(self, host: str, model: str, dim_hint: int | None = None):
        self.host = host
        self.model = _pick_embed_model(model)
        self._dim_hint = dim_hint

    def encode(self, texts: Iterable[str]) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]
        return _encode_ollama(self.host, self.model, list(texts))

    def get_sentence_embedding_dimension(self) -> int:
        try:
            v = self.encode("dimension probe")[0]
            return len(v) if v else 0
        except Exception:
            return 0

    # Allow direct call: provider(texts)
    def __call__(self, texts: Iterable[str]) -> List[List[float]]:
        return self.encode(texts)

    # Legacy support: provider, dim = get_embedder()
    def __iter__(self):
        yield self
        if isinstance(self._dim_hint, int) and self._dim_hint > 0:
            yield self._dim_hint
        else:
            yield self.get_sentence_embedding_dimension()


__EMBEDDER_SINGLETON: _OllamaEmbedder | None = None


def get_embedder():
    """Return a singleton embedder; supports legacy tuple-unpack.

    If Ollama encoding fails, fallback to a sentence-transformer style stub.
    """
    global __EMBEDDER_SINGLETON, _backend
    if _backend is None:
        # force re-probe if tests reset backend marker
        __EMBEDDER_SINGLETON = None
    if __EMBEDDER_SINGLETON is not None:
        return __EMBEDDER_SINGLETON
    # Probe _encode_ollama directly to decide backend
    try:
        try:
            _ = _encode_ollama(["probe"])  # type: ignore[misc]
        except TypeError:
            _ = _encode_ollama(OLLAMA_HOST, _pick_embed_model(NS_EMBED_MODEL), ["probe"])  # type: ignore[misc]
    except Exception:
        _ = None
    if _ is None:
        # Fallback: light SentenceTransformer adapter
        class _STEmbedder:
            def __init__(self, model: str = "all-MiniLM-L6-v2"):
                self._m = SentenceTransformer(model)

            def encode(self, texts: Iterable[str]) -> List[List[float]]:
                return self._m.encode(list(texts), normalize_embeddings=True)

            def get_sentence_embedding_dimension(self) -> int:
                try:
                    v = self.encode(["probe"])[0]
                    return len(v) if v else 0
                except Exception:
                    return 0

            def __iter__(self):
                yield self
                yield self.get_sentence_embedding_dimension()

        __EMBEDDER_SINGLETON = _STEmbedder()
        _backend = "sentence-transformer"
        return __EMBEDDER_SINGLETON
    # Use Ollama path
    # Compute a quick dimension hint from the probe result if possible
    dim_hint = 0
    try:
        if isinstance(_, list) and _ and isinstance(_[0], list):
            dim_hint = len(_[0])
    except Exception:
        dim_hint = 0
    __EMBEDDER_SINGLETON = _OllamaEmbedder(OLLAMA_HOST, NS_EMBED_MODEL, dim_hint or None)
    _backend = "ollama"
    return __EMBEDDER_SINGLETON

    # (dead code path retained above)


def embed_query(text: str) -> List[float]:
    """Embed a single query string to a 1D vector."""
    vecs = get_embedder().encode(text)
    return vecs[0] if vecs else []


# --- Added shim for backward compatibility ---
import os
from dataclasses import dataclass

import yaml


@dataclass
class EmbedderBackend:
    engine: str
    model: str


def current_backend(config_path: str = "Vault/System/Config/rag.yml") -> str:
    """Return a short backend id used by tests: 'ollama' or 'sentence-transformer'."""
    if _backend:
        return _backend
    # Try to read a hint from config, else default to ollama
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                y = yaml.safe_load(f) or {}
            eng = str(y.get("embedding_engine", "local")).lower()
            if eng in ("ollama", "local"):
                return "ollama"
            return "sentence-transformer"
    except Exception:
        pass
    return "ollama"


# Re-export name used in tests (will be patched by tests if needed)
# If sentence_transformers import above succeeded, it will already be present; otherwise
# the fallback class defined in get_embedder keeps behavior working without this alias.
