# System/Scripts/RAG/llm/compose.py
from __future__ import annotations

import http.client
import json
from typing import Any, Dict

from ..config import DEEP_MODEL, FAST_MODEL, OLLAMA_HOST


# Minimal Ollama HTTP client (no external deps)
def _ollama_request(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    host = OLLAMA_HOST.replace("http://", "").replace("https://", "")
    conn = http.client.HTTPConnection(host)
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    conn.request("POST", path, body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    if resp.status != 200:
        raise RuntimeError(f"Ollama {path} HTTP {resp.status}: {data[:200]!r}")
    return json.loads(data.decode("utf-8"))


_SYSTEM_FAST = (
    "You are a helpful assistant. Answer clearly in concise Markdown. "
    "Do NOT output JSON. Use bullet points and short paragraphs."
)

_SYSTEM_DEEP = (
    "You are a thorough technical assistant. Answer in well-structured Markdown. "
    "Do NOT output JSON. Use headings, lists, concise explanations, and include caveats when relevant."
)


def _build_messages(question: str, context: str, deep: bool) -> list[dict]:
    sys = _SYSTEM_DEEP if deep else _SYSTEM_FAST
    prompt = (
        "Question:\n"
        f"{question.strip()}\n\n"
        "Context (snippets from my vault, may be partial or noisy):\n"
        f"{context.strip()}\n\n"
        "Instructions:\n"
        "- Answer **in Markdown text only** (no JSON).\n"
        "- If context is weak or contradictory, say what you can and call out uncertainty.\n"
        "- If the question is ambiguous, state assumptions briefly and continue.\n"
    )
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": prompt},
    ]


def generate_markdown_answer(
    question: str,
    context: str,
    mode: str = "fast",
    temperature: float = 0.2,
    max_tokens: int = 800,
) -> str:
    """
    Returns a plain Markdown string. Never JSON.
    mode: 'fast' -> FAST_MODEL, 'deep' -> DEEP_MODEL
    """
    deep = mode == "deep"
    model = DEEP_MODEL if deep else FAST_MODEL
    messages = _build_messages(question, context, deep)
    resp = _ollama_request(
        "/api/chat",
        {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        },
    )
    # Ollama chat response: {"message": {"content": "..."} , ...}
    msg = resp.get("message", {}) or {}
    content = msg.get("content", "") or ""
    return content.strip()
