"""
llm/deep_llama.py — DEEP lane prompt with richer JSON structure.

Schema: {
  "short_summary": string,
  "long_summary": string,
  "abstained": bool,
  "citations": string[],
  "confidence": "high"|"medium"|"low",
  "reasoning": string
}
"""

from __future__ import annotations


def prompt(context: str, question: str) -> str:
    return f"""Answer using ONLY the CONTEXT. If insufficient, set "abstained": true.
Return valid JSON:
{{
  "short_summary": string,
  "long_summary": string,
  "abstained": boolean,
  "citations": string[],
  "confidence": "high"|"medium"|"low",
  "reasoning": string
}}

CONTEXT:
{context}

QUESTION: {question}
"""
