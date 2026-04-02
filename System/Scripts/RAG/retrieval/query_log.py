"""query_log.py — SQLite logging for query metrics and cost tracking."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from ..config import RAG_DATA_DIR

QUERY_LOG_DB = RAG_DATA_DIR / "query_log.sqlite3"

# Model pricing (input_tokens/M -> output_tokens/M)
MODEL_PRICING: Dict[str, tuple[float, float]] = {
    "gemma3:4b": (0.00, 0.00),
    "qwen2.5:7b": (0.00, 0.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}


def _init_db() -> None:
    """Create query_log table if it doesn't exist."""
    with sqlite3.connect(QUERY_LOG_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                model TEXT NOT NULL,
                context_mode TEXT NOT NULL,
                question TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                latency_ms INTEGER,
                cost_usd REAL,
                entities_detected TEXT,
                citations_count INTEGER
            )
            """
        )
        conn.commit()


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a query based on model and token counts."""
    if model not in MODEL_PRICING:
        return 0.0
    input_price, output_price = MODEL_PRICING[model]
    # Prices are per million tokens
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return input_cost + output_cost


def log_query(
    model: str,
    context_mode: str,
    question: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    cost_usd: float | None = None,
    entities_detected: List[str] | None = None,
    citations_count: int = 0,
) -> int:
    """Log a query to the database.

    Args:
        model: Model ID
        context_mode: 'off', 'auto', or 'full'
        question: The question/prompt
        input_tokens: Input token count
        output_tokens: Output token count
        latency_ms: Query latency in milliseconds
        cost_usd: Cost (auto-calculated if None)
        entities_detected: List of detected entity IDs
        citations_count: Number of citations in response

    Returns:
        Row ID of inserted query
    """
    _init_db()

    if cost_usd is None:
        cost_usd = calculate_cost(model, input_tokens, output_tokens)

    entities_json = json.dumps(entities_detected or [])

    with sqlite3.connect(QUERY_LOG_DB) as conn:
        cursor = conn.execute(
            """
            INSERT INTO query_log
            (model, context_mode, question, input_tokens, output_tokens,
             latency_ms, cost_usd, entities_detected, citations_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model,
                context_mode,
                question,
                input_tokens,
                output_tokens,
                latency_ms,
                cost_usd,
                entities_json,
                citations_count,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_usage_stats(days: int = 30) -> Dict[str, Any]:
    """Get usage statistics for the past N days.

    Returns:
        {
            "total_queries": int,
            "total_cost_usd": float,
            "avg_latency_ms": float,
            "by_model": {
                "model_id": {
                    "count": int,
                    "cost_usd": float,
                    "avg_latency_ms": float,
                }
            },
            "by_context_mode": {
                "off": {...},
                "auto": {...},
                "full": {...}
            },
            "daily_average": float,
        }
    """
    _init_db()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    with sqlite3.connect(QUERY_LOG_DB) as conn:
        conn.row_factory = sqlite3.Row

        # Overall stats
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total_queries,
                SUM(cost_usd) as total_cost,
                AVG(latency_ms) as avg_latency
            FROM query_log
            WHERE timestamp >= ?
            """,
            (cutoff,),
        ).fetchone()

        total_queries = row["total_queries"] or 0
        total_cost = row["total_cost"] or 0.0
        avg_latency = row["avg_latency"] or 0.0

        # By model
        by_model = {}
        model_rows = conn.execute(
            """
            SELECT
                model,
                COUNT(*) as count,
                SUM(cost_usd) as cost,
                AVG(latency_ms) as avg_latency
            FROM query_log
            WHERE timestamp >= ?
            GROUP BY model
            """,
            (cutoff,),
        ).fetchall()

        for mrow in model_rows:
            by_model[mrow["model"]] = {
                "count": mrow["count"],
                "cost_usd": mrow["cost"] or 0.0,
                "avg_latency_ms": mrow["avg_latency"] or 0.0,
            }

        # By context mode
        by_context_mode = {}
        context_rows = conn.execute(
            """
            SELECT
                context_mode,
                COUNT(*) as count,
                SUM(cost_usd) as cost,
                AVG(latency_ms) as avg_latency
            FROM query_log
            WHERE timestamp >= ?
            GROUP BY context_mode
            """,
            (cutoff,),
        ).fetchall()

        for crow in context_rows:
            by_context_mode[crow["context_mode"]] = {
                "count": crow["count"],
                "cost_usd": crow["cost"] or 0.0,
                "avg_latency_ms": crow["avg_latency"] or 0.0,
            }

        daily_average = total_cost / max(days, 1)

    return {
        "total_queries": total_queries,
        "total_cost_usd": round(total_cost, 4),
        "avg_latency_ms": round(avg_latency, 1),
        "by_model": by_model,
        "by_context_mode": by_context_mode,
        "daily_average": round(daily_average, 4),
        "period_days": days,
    }
