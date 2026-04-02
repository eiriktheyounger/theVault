"""claude_client.py — Async Claude API client for unified /query endpoint.

Supports Claude models with token tracking and cost calculation.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from anthropic import Anthropic, AsyncAnthropic

# Ensure ANTHROPIC_API_KEY is loaded (override=True in case env has empty value)
_env_path = Path(__file__).resolve().parents[4] / ".env"  # theVault/.env
load_dotenv(_env_path, override=True)

# Client instances (created lazily)
_sync_client: Anthropic | None = None
_async_client: AsyncAnthropic | None = None


def _get_sync_client() -> Anthropic:
    """Get or create sync Anthropic client."""
    global _sync_client
    if _sync_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
        _sync_client = Anthropic(api_key=api_key)
    return _sync_client


async def _get_async_client() -> AsyncAnthropic:
    """Get or create async Anthropic client."""
    global _async_client
    if _async_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
        _async_client = AsyncAnthropic(api_key=api_key)
    return _async_client


async def claude_generate(
    model: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    """Generate response from Claude API (async).

    Args:
        model: Model ID (e.g., "claude-haiku-4-5-20251001")
        prompt: User prompt/question
        system: System prompt (optional)
        max_tokens: Max tokens in response

    Returns:
        {
            "response": str,
            "input_tokens": int,
            "output_tokens": int,
            "model": str,
            "ok": bool,
            "error": str | None,
        }
    """
    try:
        client = await _get_async_client()

        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)

        text = ""
        if response.content:
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    break

        return {
            "response": text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": model,
            "ok": True,
            "error": None,
        }
    except Exception as exc:
        return {
            "response": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "model": model,
            "ok": False,
            "error": str(exc),
        }
