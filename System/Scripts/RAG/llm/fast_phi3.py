"""
llm/fast_phi3.py — FAST lane prompt with compact JSON structure.

Schema: {"short_summary": string, "long_summary": string, "abstained": bool, "citations": string[]}
"""

from __future__ import annotations


def prompt(context: str, question: str) -> str:
    return f"""Answer ONLY using the CONTEXT. If the context is insufficient, set "abstained": true.
Return exactly this JSON schema (and nothing else):
{{"short_summary": string, "long_summary": string, "abstained": boolean, "citations": string[]}}

CONTEXT:
{context}

QUESTION: {question}
"""
