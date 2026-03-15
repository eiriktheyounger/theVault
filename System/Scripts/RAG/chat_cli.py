#!/usr/bin/env python
"""
RAG-augmented chat over your Vault index.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np

from .config import NOMIC_EMBED_MODEL, OLLAMA_HOST  # PATCH: import shared host
from .embedder_provider import (
    _pick_embed_model,  # PATCH: centralized embed model picker
)

BASE = Path.home() / "theVault"
RAG_DIR = BASE / "Vault" / "Vault_RAG"
VEC_PATH = RAG_DIR / "vectors.npy"
NORM_PATH = RAG_DIR / "norms.npy"
META_PATH = RAG_DIR / "meta.jsonl"
INFO_PATH = RAG_DIR / "index_info.json"

for p in (VEC_PATH, NORM_PATH, META_PATH, INFO_PATH):
    if not p.exists():
        print("[ERR] Missing index artifacts. Run rag_build.py first.")
        sys.exit(1)

VEC = np.load(VEC_PATH)
NORMS = np.load(NORM_PATH)
META = [json.loads(l) for l in open(META_PATH, "r", encoding="utf-8")]
INFO = json.load(open(INFO_PATH, "r", encoding="utf-8"))

INDEX_MODE = INFO.get("mode", "live")
DIM = int(INFO.get("dim", 0))
CHAT_MODEL = os.getenv("FAST_MODEL", "phi3:mini")
NS_EMBED_MODEL = os.getenv("NS_EMBED_MODEL", NOMIC_EMBED_MODEL)

TOPK = int(os.getenv("NS_CHAT_TOPK", "6"))
MAX_SNIPPET_CHARS = int(os.getenv("NS_CHAT_SNIPPET_CHARS", "1200"))
MAX_TOTAL_CONTEXT = int(os.getenv("NS_CHAT_TOTAL_CONTEXT", "4800"))


def embed_query(q: str) -> np.ndarray:
    if INDEX_MODE == "fake":
        v = np.array([len(q) % 7, len(q) % 11, len(q) % 13], dtype="float32")
    else:
        import httpx

        r = httpx.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": _pick_embed_model(NS_EMBED_MODEL), "input": q},
        )  # PATCH: call embeddings endpoint directly
        r.raise_for_status()
        data = r.json()
        v = np.array((data.get("embedding") or data["data"][0]["embedding"]), dtype="float32")
    if v.ndim != 1:
        v = v.reshape(-1)
    if v.shape[0] != DIM:
        raise SystemExit(
            f"[ERR] Query dim {v.shape[0]} != index dim {DIM} (index mode={INDEX_MODE}). Rebuild to match."
        )
    return v


def retrieve(q: str, k: int = TOPK):
    qv = embed_query(q)
    qn = float(np.linalg.norm(qv))
    if qn == 0.0:
        qn = 1.0
    denom = NORMS.flatten() * qn
    denom[denom == 0.0] = 1.0
    sims = (VEC @ qv) / denom
    idx = sims.argsort()[-k:][::-1]
    return [(float(sims[i]), META[i]["path"]) for i in idx]


def build_context(hits):
    chunks, total = [], 0
    for _, p in hits:
        try:
            t = Path(p).read_text(encoding="utf-8", errors="ignore")[:MAX_SNIPPET_CHARS]
            if total + len(t) > MAX_TOTAL_CONTEXT:
                t = t[: max(0, MAX_TOTAL_CONTEXT - total)]
            if not t:
                continue
            chunks.append(t)
            total += len(t)
            if total >= MAX_TOTAL_CONTEXT:
                break
        except Exception:
            continue
    return "\n\n---\n".join(chunks)


def ollama_generate(prompt: str) -> str:
    import json as pyjson

    import httpx

    with httpx.Client(timeout=60) as c:
        r = c.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": CHAT_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False},
        )  # PATCH: use shared host and new API
        r.raise_for_status()
        try:
            # New API returns message.content instead of response
            data = r.json()
            return (data.get("message", {}).get("content") or "").strip()
        except Exception:
            # Fallback for streaming responses (though stream=False)
            out = []
            for line in r.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = pyjson.loads(line)
                    part = data.get("message", {}).get("content") or data.get("response")
                    if part:
                        out.append(part)
                except Exception:
                    pass
            return "".join(out).strip()


def answer_with_context(q: str, hits):
    if INDEX_MODE == "fake":
        return "stub: ok", hits
    ctx = build_context(hits)
    prompt = f"""You are a helpful assistant. Use the CONTEXT to answer the QUESTION.
If you are uncertain, say so briefly and cite which files you used.

CONTEXT:
{ctx}

QUESTION:
{q}

Answer concisely and directly:"""
    return ollama_generate(prompt), hits


def main():
    if len(sys.argv) < 2:
        print('Usage: python ~/theVault/System/Scripts/RAG/chat_cli.py "your question"')
        sys.exit(1)
    q = sys.argv[1]
    hits = retrieve(q, k=TOPK)
    ans, used = answer_with_context(q, hits)
    print("\n=== Answer ===\n" + ans)
    print("\n=== Sources ===")
    for s, p in used:
        print(f"{s:.4f}  {p}")
    print(f"\n[INFO] index mode={INDEX_MODE} dim={DIM} model={CHAT_MODEL}")


if __name__ == "__main__":
    main()
