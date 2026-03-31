"""
summarizer.py — LLM-based email thread summarization

Dual-LLM pattern (same as clean_md_processor.py):
  1. Anthropic Haiku API (claude-haiku-4-5-20251001)
  2. Ollama qwen2.5:7b at localhost:11434
  3. Placeholder text (last resort)

Returns JSON dict with keys: summary, key_points, glossary, action_items
Key points include message anchor references (msg-{anchor_id}).
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

from . import config
from .thread_grouper import EmailThread

log = logging.getLogger("email_thread_ingester.summarizer")

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_OLLAMA_MODEL = "qwen2.5:7b"
_OLLAMA_URL   = "http://localhost:11434/api/chat"


# ── Prompt Builder ────────────────────────────────────────────────────────────

def _build_transcript(thread: EmailThread, max_chars: int = config.MAX_TRANSCRIPT_CHARS) -> str:
    """Build a condensed transcript string from thread messages."""
    parts: list[str] = []
    for msg in thread.sorted_messages:
        header = f"[msg-{msg.anchor_id}] {msg.date_str} | From: {msg.sender} | Subject: {msg.subject}"
        parts.append(f"{header}\n{msg.body[:2000]}")

    transcript = "\n\n---\n\n".join(parts)
    return transcript[:max_chars]


def _build_prompt(thread: EmailThread, transcript: str) -> str:
    anchor_index = "\n".join(
        f"  - msg-{m.anchor_id}: {m.subject} ({m.date_str})"
        for m in thread.sorted_messages
    )
    return f"""Analyze this email thread and return a JSON object with exactly these keys:

- "summary": 2-3 sentence overview of the thread
- "key_points": list of 3-8 bullet points; each should reference the relevant message anchor like [msg-abc123]
- "glossary": dict of technical terms or proper nouns needing context (may be empty {{}} )
- "action_items": list of follow-up actions, deadlines, or decisions needed (may be empty [])

Message anchors:
{anchor_index}

Email thread:
{transcript}

Return ONLY valid JSON. No markdown fences, no extra text."""


# ── LLM Backends ─────────────────────────────────────────────────────────────

def _summarize_anthropic(prompt: str) -> Optional[dict]:
    """Call Anthropic Haiku API. Returns parsed JSON dict or None."""
    try:
        import os
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            log.debug("ANTHROPIC_API_KEY not set, skipping Haiku summarizer")
            return None
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return json.loads(text)
    except ImportError:
        log.debug("anthropic SDK not installed, skipping")
        return None
    except Exception as e:
        log.warning(f"Anthropic summarizer failed: {e}")
        return None


def _summarize_ollama(prompt: str) -> Optional[dict]:
    """Call local Ollama. Returns parsed JSON dict or None."""
    try:
        payload = json.dumps({
            "model": _OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        }).encode()
        req = urllib.request.Request(
            _OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        text = result.get("message", {}).get("content", "").strip()
        return json.loads(text)
    except Exception as e:
        log.warning(f"Ollama summarizer failed: {e}")
        return None


def _placeholder_summary(thread: EmailThread) -> dict:
    """Minimal placeholder when both LLM backends fail."""
    return {
        "summary": f"Email thread: {thread.normalized_subject} ({thread.message_count} messages)",
        "key_points": [f"[msg-{m.anchor_id}] {m.subject}" for m in thread.sorted_messages[:5]],
        "glossary": {},
        "action_items": [],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def summarize_thread(thread: EmailThread) -> dict:
    """
    Summarize an email thread.
    Returns dict with keys: summary, key_points, glossary, action_items.
    """
    transcript = _build_transcript(thread)
    prompt = _build_prompt(thread, transcript)

    result = _summarize_anthropic(prompt)
    if result is None:
        log.debug("Falling back to Ollama for summarization")
        result = _summarize_ollama(prompt)
    if result is None:
        log.debug("Both LLM backends failed, using placeholder")
        result = _placeholder_summary(thread)

    # Ensure all expected keys exist
    result.setdefault("summary", "")
    result.setdefault("key_points", [])
    result.setdefault("glossary", {})
    result.setdefault("action_items", [])
    return result


def summarize_for_daily(body: str) -> str:
    """
    One-sentence summary of a single email message body.
    Used by daily_note_writer for brief activity log.
    """
    if not body:
        return "Email received."
    prompt = (
        "Summarize this email in one sentence (max 20 words). "
        "Return only the sentence, no quotes or punctuation at the end:\n\n"
        + body[:2000]
    )
    try:
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip().rstrip(".")
    except Exception:
        pass
    # Fallback: first 100 chars of body
    first_line = body.strip().split("\n")[0][:100]
    return first_line or "Email received"
