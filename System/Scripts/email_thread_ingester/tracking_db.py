"""
tracking_db.py — SQLite state tracking for email thread ingester

Three tables:
  - processed_messages: dedup guard, one row per message_id
  - threads: tracks vault path and metadata per thread
  - contacts: email address → People/ file mapping
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from . import config

# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_messages (
    message_id      TEXT PRIMARY KEY,
    thread_id       TEXT NOT NULL,
    account         TEXT NOT NULL,
    subject         TEXT,
    sender          TEXT,
    date_received   TEXT,
    processed_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS threads (
    thread_id           TEXT PRIMARY KEY,
    normalized_subject  TEXT NOT NULL,
    vault_path          TEXT NOT NULL,
    message_count       INTEGER DEFAULT 0,
    first_message_date  TEXT,
    last_message_date   TEXT,
    last_updated        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    email           TEXT PRIMARY KEY,
    name            TEXT,
    vault_path      TEXT,
    first_seen      TEXT,
    last_seen       TEXT,
    message_count   INTEGER DEFAULT 0
);
"""

# ── Connection Context Manager ────────────────────────────────────────────────

@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    """Open a connection, ensure schema, yield, commit/close."""
    db_path = config.TRACKING_DB
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── processed_messages ────────────────────────────────────────────────────────

def is_message_processed(message_id: str) -> bool:
    """Return True if this message_id has already been ingested."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?",
            (message_id,)
        ).fetchone()
    return row is not None


def mark_message_processed(
    message_id: str,
    thread_id: str,
    account: str,
    subject: str = "",
    sender: str = "",
    date_received: str = "",
) -> None:
    """Record a message as processed."""
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO processed_messages
               (message_id, thread_id, account, subject, sender, date_received, processed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (message_id, thread_id, account, subject, sender, date_received, _now_iso()),
        )


# ── threads ───────────────────────────────────────────────────────────────────

def get_thread(thread_id: str) -> Optional[dict]:
    """Return thread row as dict, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    return dict(row) if row else None


def upsert_thread(
    thread_id: str,
    normalized_subject: str,
    vault_path: str,
    message_count: int,
    first_message_date: str,
    last_message_date: str,
) -> None:
    """Create or update a thread record."""
    with _connect() as conn:
        conn.execute(
            """INSERT INTO threads
               (thread_id, normalized_subject, vault_path, message_count,
                first_message_date, last_message_date, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(thread_id) DO UPDATE SET
                   normalized_subject  = excluded.normalized_subject,
                   vault_path          = excluded.vault_path,
                   message_count       = excluded.message_count,
                   first_message_date  = excluded.first_message_date,
                   last_message_date   = excluded.last_message_date,
                   last_updated        = excluded.last_updated""",
            (thread_id, normalized_subject, vault_path, message_count,
             first_message_date, last_message_date, _now_iso()),
        )


# ── contacts ──────────────────────────────────────────────────────────────────

def upsert_contact(
    email: str,
    name: str,
    vault_path: str,
) -> None:
    """Create or update a contact record, incrementing message_count."""
    now = _now_iso()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT message_count, first_seen FROM contacts WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE contacts
                   SET name = ?, vault_path = ?, last_seen = ?, message_count = message_count + 1
                   WHERE email = ?""",
                (name, vault_path, now, email),
            )
        else:
            conn.execute(
                """INSERT INTO contacts (email, name, vault_path, first_seen, last_seen, message_count)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (email, name, vault_path, now, now),
            )


def get_contact(email: str) -> Optional[dict]:
    """Return contact row as dict, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM contacts WHERE email = ?", (email,)
        ).fetchone()
    return dict(row) if row else None


# ── Utilities ─────────────────────────────────────────────────────────────────

def filter_new_messages(messages: list[dict]) -> list[dict]:
    """Return only messages whose message_id has not been processed."""
    return [m for m in messages if not is_message_processed(m.get("message_id", ""))]


def init_db() -> None:
    """Ensure the database and schema exist (called at package import)."""
    with _connect():
        pass
