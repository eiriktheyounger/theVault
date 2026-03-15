"""In-memory chat session store with JSONL transcript persistence.

This module provides a very small abstraction for storing short-lived chat
sessions.  Each session tracks up to 10 conversational turns (20 messages) and
is discarded once ended or after being idle for a period of time.

When a session ends its transcript is written to
``VAULT_ROOT/System/Ops/Chats/Deep`` using the JSONL schema handled by
:mod:`System.Scripts.RAG.storage.chats`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from .storage import chats as storage


@dataclass
class ChatSession:
    """Container for a single chat session."""

    messages: List[Dict[str, str]] = field(default_factory=list)
    last_used: datetime = field(default_factory=lambda: datetime.now(UTC))
    title: Optional[str] = None  # first user message
    path: Path | None = None  # JSONL transcript path


class ChatStore:
    """Manage active chat sessions and write transcripts on completion."""

    def __init__(self) -> None:
        self._sessions: Dict[str, ChatSession] = {}

    def new_chat(self) -> str:
        """Return a new chat identifier and prepare its storage path."""

        chat_id = uuid4().hex
        ts = datetime.now(UTC)
        path = storage.ensure_chat_dirs("deep", ts, chat_id)
        storage.set_pin(chat_id, path)
        self._sessions[chat_id] = ChatSession(path=path)
        return chat_id

    def get(self, chat_id: str) -> List[Dict[str, str]]:
        """Return a copy of messages for *chat_id* or an empty list."""

        session = self._sessions.get(chat_id)
        if not session:
            return []
        return list(session.messages)

    def append(self, chat_id: str, role: str, content: str) -> None:
        """Append a message to *chat_id* creating the session if needed."""

        session = self._sessions.setdefault(chat_id, ChatSession())
        ts = datetime.now(UTC).isoformat()
        session.messages.append({"role": role, "content": content, "ts": ts})
        # Keep only last 20 messages (~10 turns)
        if len(session.messages) > 20:
            del session.messages[:-20]
        if role == "user" and not session.title:
            session.title = content
        session.last_used = datetime.now(UTC)

    def end(self, chat_id: str) -> None:
        """Persist and remove *chat_id* if it exists."""

        session = self._sessions.pop(chat_id, None)
        if session:
            self._write_transcript(chat_id, session)
            storage.unpin(chat_id)

    def cleanup_idle(self, max_age: int = 1800) -> None:
        """End sessions idle for more than *max_age* seconds."""

        cutoff = datetime.now(UTC) - timedelta(seconds=max_age)
        for cid, sess in list(self._sessions.items()):
            if sess.last_used < cutoff:
                self.end(cid)

    # ------------------------------------------------------------------
    def _write_transcript(self, cid: str, session: ChatSession) -> None:
        """Write *session* to its JSONL transcript."""

        path = session.path
        if path is None:
            ts = datetime.now(UTC)
            path = storage.ensure_chat_dirs("deep", ts, cid)
        for msg in session.messages:
            record = {
                "ts": msg.get("ts") or datetime.now(UTC).isoformat(),
                "role": msg.get("role", ""),
                "mode": "deep",
                "text": msg.get("content", ""),
                "meta": {},
            }
            storage.append_jsonl(path, record)
        self._prune_history(path.parent)

    @staticmethod
    def _prune_history(directory: Path, max_files: int = 15) -> None:
        files = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        for p in files[:-max_files]:
            try:
                p.unlink()
            except Exception:
                pass


CHAT_STORE = ChatStore()
