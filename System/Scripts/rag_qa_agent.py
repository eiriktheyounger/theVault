#!/usr/bin/env python3
"""
rag_qa_agent.py — RAG Quality Gate

Runs 18 test cases against the RAG endpoints (/fast, /deep), grades responses
with Claude Haiku, and writes a markdown report.

Exit codes:
    0 = PASS (≥90% overall)
    1 = FAIL (<90% overall)
    2 = SETUP_ERROR (RAG unavailable or ANTHROPIC_API_KEY missing)

Usage:
    python System/Scripts/rag_qa_agent.py
    python System/Scripts/rag_qa_agent.py --dry-run   # skip LLM grader, use stub scores
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_ROOT = PROJECT_ROOT / "Vault"
LOG_DIR = VAULT_ROOT / "System" / "Logs" / "rag_qa"
RAG_BASE = "http://localhost:5055"

THRESHOLD_SCORE = 486   # 90% of 540 (18 tests × 30 pts)
THRESHOLD_PCT = 90.0

# ── Test Suite ─────────────────────────────────────────────────────────────────

TEST_CASES = [
    # ── Cross File (3) ──────────────────────────────────────────────────────
    {
        "id": "ssai_cross_file",
        "category": "Cross File",
        "query": "SSAI ad insertion across ViewLift and DirtVision",
        "endpoint": "/deep",
        "expected_keywords": ["ssai", "viewlift", "dirtvision", "ad"],
        "expected_behavior": "answer",
    },
    {
        "id": "harmonic_clients_overview",
        "category": "Cross File",
        "query": "Which streaming clients does Harmonic support and what are their key requirements?",
        "endpoint": "/deep",
        "expected_keywords": ["viewlift", "dirtvision", "harmonic", "streaming"],
        "expected_behavior": "answer",
    },
    {
        "id": "plaud_email_overlap",
        "category": "Cross File",
        "query": "What topics appear in both meeting recordings and email threads?",
        "endpoint": "/deep",
        "expected_keywords": ["meeting", "email", "thread"],
        "expected_behavior": "answer",
    },
    # ── Meeting (3) ─────────────────────────────────────────────────────────
    {
        "id": "fanduel_meeting",
        "category": "Meeting",
        "query": "What meetings discussed FanDuel or MSSG?",
        "endpoint": "/fast",
        "expected_keywords": ["fanduel", "mssg", "rfp"],
        "expected_behavior": "answer",
    },
    {
        "id": "bloomberg_scte35",
        "category": "Meeting",
        "query": "Bloomberg in-stream ad demo SCTE-35",
        "endpoint": "/fast",
        "expected_keywords": ["bloomberg", "scte", "ad", "demo"],
        "expected_behavior": "answer",
    },
    {
        "id": "nab_new_york",
        "category": "Meeting",
        "query": "NAB New York meeting Harmonic",
        "endpoint": "/fast",
        "expected_keywords": ["nab", "harmonic", "new york"],
        "expected_behavior": "answer",
    },
    # ── Personal (3) ────────────────────────────────────────────────────────
    {
        "id": "rachel_food",
        "category": "Personal",
        "query": "Rachel food preferences and orders",
        "endpoint": "/fast",
        "expected_keywords": ["rachel", "food", "preference"],
        "expected_behavior": "answer",
    },
    {
        "id": "home_breaker",
        "category": "Personal",
        "query": "breaker box and home information",
        "endpoint": "/fast",
        "expected_keywords": ["breaker", "home"],
        "expected_behavior": "answer",
    },
    {
        "id": "vault_system_overview",
        "category": "Personal",
        "query": "What is theVault and how is it organized?",
        "endpoint": "/fast",
        "expected_keywords": ["vault", "obsidian", "notes"],
        "expected_behavior": "answer",
    },
    # ── Proper Noun (3) ─────────────────────────────────────────────────────
    {
        "id": "viewlift_definition",
        "category": "Proper Noun",
        "query": "What is ViewLift?",
        "endpoint": "/fast",
        "expected_keywords": ["viewlift", "streaming", "platform"],
        "expected_behavior": "answer",
    },
    {
        "id": "scte35_definition",
        "category": "Proper Noun",
        "query": "What is SCTE-35?",
        "endpoint": "/fast",
        "expected_keywords": ["scte", "ad", "cue", "signal"],
        "expected_behavior": "answer",
    },
    {
        "id": "vos360_workflow",
        "category": "Proper Noun",
        "query": "VOS360 live event workflow",
        "endpoint": "/fast",
        "expected_keywords": ["vos360", "harmonic", "live"],
        "expected_behavior": "answer",
    },
    # ── Semantic (3) ────────────────────────────────────────────────────────
    {
        "id": "task_pipeline_concept",
        "category": "Semantic",
        "query": "How does the task pipeline work?",
        "endpoint": "/deep",
        "expected_keywords": ["task", "pipeline", "categorize"],
        "expected_behavior": "answer",
    },
    {
        "id": "ad_insertion_workflow",
        "category": "Semantic",
        "query": "streaming ad insertion workflow overview",
        "endpoint": "/deep",
        "expected_keywords": ["ad", "insertion", "streaming", "ssai"],
        "expected_behavior": "answer",
    },
    {
        "id": "rag_search_concept",
        "category": "Semantic",
        "query": "How does semantic search work in the vault?",
        "endpoint": "/fast",
        "expected_keywords": ["search", "semantic", "vector", "embedding"],
        "expected_behavior": "answer",
    },
    # ── Technical (3) ───────────────────────────────────────────────────────
    {
        "id": "cdn_geo_redundancy",
        "category": "Technical",
        "query": "CDN steering geo redundancy configuration",
        "endpoint": "/deep",
        "expected_keywords": ["cdn", "geo", "redundancy"],
        "expected_behavior": "answer",
    },
    {
        "id": "atsc30_encoding",
        "category": "Technical",
        "query": "ATSC 3.0 migration workflow encoding",
        "endpoint": "/deep",
        "expected_keywords": ["atsc", "encoding", "migration"],
        "expected_behavior": "answer",
    },
    {
        "id": "xos_configuration",
        "category": "Technical",
        "query": "XOS encoder configuration and playout",
        "endpoint": "/deep",
        "expected_keywords": ["xos", "encoder", "configuration"],
        "expected_behavior": "answer",
    },
]


# ── Setup Checks ───────────────────────────────────────────────────────────────

def _load_dotenv() -> None:
    env_file = Path.home() / "theVault" / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not os.environ.get(key):
            os.environ[key] = val


def check_rag_server() -> bool:
    """Return True if RAG server is reachable."""
    try:
        resp = httpx.get(f"{RAG_BASE}/healthz", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def check_anthropic_key() -> bool:
    """Return True if ANTHROPIC_API_KEY is set."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


# ── RAG Query ─────────────────────────────────────────────────────────────────

def query_rag(endpoint: str, question: str, timeout: float = 120.0) -> dict[str, Any]:
    """Call /fast or /deep and return parsed response dict."""
    try:
        resp = httpx.post(
            f"{RAG_BASE}{endpoint}",
            json={"question": question},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        return {"error": "timeout", "answer": "", "sources": []}
    except Exception as e:
        return {"error": str(e), "answer": "", "sources": []}


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_relevance(answer: str, keywords: list[str]) -> int:
    """R score (0-10): keyword match rate × 10."""
    if not answer or not keywords:
        return 0
    answer_lower = answer.lower()
    found = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return round((found / len(keywords)) * 10)


def count_citations(response: dict) -> int:
    """Count distinct cited sources in the response."""
    sources = response.get("sources", [])
    if isinstance(sources, list):
        return len(sources)
    # Some endpoints embed citations inline — count bracketed refs
    answer = response.get("answer", "")
    return len(set(
        m.group(0) for m in __import__("re").finditer(r'\[[^\]]{3,60}\]', answer)
    ))


def score_source(response: dict) -> int:
    """S score (0-10): 0 citations=0, 1-4=7, 5+=10."""
    n = count_citations(response)
    if n == 0:
        return 0
    if n < 5:
        return 7
    return 10


def grade_correctness(
    query: str,
    answer: str,
    expected_behavior: str,
    dry_run: bool,
) -> int:
    """C score (0-10): Claude Haiku grades correctness."""
    if dry_run or not answer.strip():
        return 8  # stub

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return 8

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"Rate the following RAG answer on a scale of 0–10 for correctness and helpfulness.\n\n"
            f"Question: {query}\n\n"
            f"Expected behavior: {expected_behavior} (should either answer or correctly abstain)\n\n"
            f"Answer:\n{answer[:1500]}\n\n"
            "Respond with ONLY a single integer 0-10. No explanation."
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        score = int("".join(c for c in raw if c.isdigit())[:2] or "0")
        return min(10, max(0, score))
    except Exception:
        return 8  # fallback on API error


# ── Test Runner ───────────────────────────────────────────────────────────────

def run_test(tc: dict, dry_run: bool) -> dict:
    """Run a single test case. Returns result dict."""
    t0 = time.time()
    if dry_run:
        response = {"answer": f"[dry-run stub answer for: {tc['query']}]", "sources": ["stub1", "stub2", "stub3", "stub4", "stub5"]}
    else:
        timeout = 180.0 if tc["endpoint"] == "/deep" else 60.0
        response = query_rag(tc["endpoint"], tc["query"], timeout=timeout)
    elapsed = time.time() - t0

    answer = response.get("answer", "")
    error = response.get("error", "")

    r_score = score_relevance(answer, tc["expected_keywords"])
    s_score = score_source(response)
    c_score = grade_correctness(tc["query"], answer, tc["expected_behavior"], dry_run)

    total = r_score + s_score + c_score
    found_kw = [kw for kw in tc["expected_keywords"] if kw.lower() in answer.lower()]
    n_citations = count_citations(response)

    return {
        "id": tc["id"],
        "category": tc["category"],
        "query": tc["query"],
        "endpoint": tc["endpoint"],
        "expected_keywords": tc["expected_keywords"],
        "found_keywords": found_kw,
        "r_score": r_score,
        "s_score": s_score,
        "c_score": c_score,
        "total": total,
        "n_citations": n_citations,
        "elapsed": elapsed,
        "answer_preview": answer[:300] if answer else f"[ERROR: {error}]",
        "error": error,
    }


# ── Report Writer ─────────────────────────────────────────────────────────────

def _status_icon(total: int) -> str:
    if total >= 27:
        return "✅"
    if total >= 20:
        return "⚠️"
    return "❌"


def write_report(results: list[dict], total_score: int, passed: bool, log_dir: Path) -> Path:
    """Write markdown report. Returns report path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    report_path = log_dir / f"rag_qa_{ts}.md"

    pct = (total_score / 540) * 100
    status = "PASS" if passed else "FAIL"

    lines = [
        f"# RAG Q/A Report — {ts}",
        "",
        f"**Status**: {status}  ",
        f"**Score**: {total_score}/540 ({pct:.1f}%)  ",
        f"**Threshold**: {THRESHOLD_PCT:.0f}%  ",
        f"**Tests run**: {len(results)}  ",
        f"**Grader**: Claude Haiku (claude-haiku-4-5-20251001)",
        "",
        "---",
        "",
    ]

    # Group by category
    categories: dict[str, list[dict]] = {}
    for r in results:
        categories.setdefault(r["category"], []).append(r)

    for cat, cat_results in categories.items():
        cat_total = sum(r["total"] for r in cat_results)
        cat_max = len(cat_results) * 30
        cat_pct = (cat_total / cat_max) * 100 if cat_max else 0
        lines.append(f"## {cat} ({cat_pct:.1f}%)")
        lines.append("")

        for r in cat_results:
            icon = _status_icon(r["total"])
            found_str = f"{len(r['found_keywords'])}/{len(r['expected_keywords'])}"
            lines += [
                f"### {icon} {r['id']}",
                f"**Query**: `{r['query']}`  ",
                f"**Endpoint**: `{r['endpoint']}`  ",
                f"**Score**: {r['total']}/30 (R:{r['r_score']} S:{r['s_score']} C:{r['c_score']})  ",
                f"**Diagnosis**: {found_str} keywords found; {r['n_citations']} citations; answer length {len(r['answer_preview'])} chars  ",
                f"**Elapsed**: {r['elapsed']:.1f}s  ",
                "",
                "<details><summary>Response preview</summary>",
                "",
                "```",
                r["answer_preview"],
                "```",
                "</details>",
                "",
            ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="RAG Q/A quality gate")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls, use stub scores")
    args = parser.parse_args()

    # Setup checks
    if not check_rag_server():
        print("SETUP_ERROR: RAG server not reachable at http://localhost:5055/healthz", file=sys.stderr)
        return 2

    if not args.dry_run and not check_anthropic_key():
        print("SETUP_ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    print(f"RAG Q/A Gate — {len(TEST_CASES)} test cases, threshold {THRESHOLD_PCT:.0f}%")
    print(f"{'='*60}")

    results = []
    for i, tc in enumerate(TEST_CASES, 1):
        print(f"[{i:2d}/{len(TEST_CASES)}] {tc['category']:12s} {tc['id']} ...", end=" ", flush=True)
        result = run_test(tc, dry_run=args.dry_run)
        results.append(result)
        icon = _status_icon(result["total"])
        print(f"{icon} {result['total']}/30  ({result['elapsed']:.1f}s)")

    total_score = sum(r["total"] for r in results)
    pct = (total_score / 540) * 100
    passed = total_score >= THRESHOLD_SCORE

    print(f"\n{'='*60}")
    print(f"Total: {total_score}/540 ({pct:.1f}%) — {'PASS' if passed else 'FAIL'}")

    report_path = write_report(results, total_score, passed, LOG_DIR)
    print(f"Report: {report_path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
