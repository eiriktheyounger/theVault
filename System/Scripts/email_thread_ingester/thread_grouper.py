"""
thread_grouper.py — Group raw email messages into threads

Threading priority:
  1. Exchange thread-topic header (most reliable)
  2. In-Reply-To / References chain
  3. Normalized subject fallback

Fork detection: a message forks if its subject normalizes to match the
parent thread's subject OR its References header overlaps with any
existing message-id in the thread.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .email_parser import extract_email_address, extract_name, strip_subject_prefixes

log = logging.getLogger("email_thread_ingester.thread_grouper")


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class EmailMessage:
    message_id: str
    subject: str
    sender: str
    sender_email: str
    sender_name: str
    recipients: list[str]
    date_received: datetime
    date_str: str
    in_reply_to: Optional[str]
    references: list[str]          # parsed from headers
    thread_topic: Optional[str]    # Exchange X-Thread-Topic header
    headers: str
    body: str
    account: str
    # Derived
    normalized_subject: str = field(default="")
    anchor_id: str = field(default="")

    def __post_init__(self):
        if not self.normalized_subject:
            self.normalized_subject = _normalize_subject(self.subject)
        if not self.anchor_id:
            self.anchor_id = hashlib.md5(self.message_id.encode()).hexdigest()[:6]


@dataclass
class EmailThread:
    thread_id: str
    normalized_subject: str
    messages: list[EmailMessage] = field(default_factory=list)
    # Derived from messages
    first_date: Optional[datetime] = None
    last_date: Optional[datetime] = None
    participants: list[str] = field(default_factory=list)

    def add(self, msg: EmailMessage) -> None:
        self.messages.append(msg)
        self._update_derived(msg)

    def _update_derived(self, msg: EmailMessage) -> None:
        d = msg.date_received
        if self.first_date is None or d < self.first_date:
            self.first_date = d
        if self.last_date is None or d > self.last_date:
            self.last_date = d
        if msg.sender_email and msg.sender_email not in self.participants:
            self.participants.append(msg.sender_email)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def sorted_messages(self) -> list[EmailMessage]:
        """Messages sorted newest-first."""
        return sorted(self.messages, key=lambda m: m.date_received, reverse=True)


# ── Subject Normalization ─────────────────────────────────────────────────────

def _normalize_subject(subject: str) -> str:
    """Strip prefixes, lowercase, collapse whitespace."""
    s = strip_subject_prefixes(subject)
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── Header Parsing Helpers ────────────────────────────────────────────────────

def _parse_references(headers: str) -> list[str]:
    """Extract message-ids from References header."""
    m = re.search(r"^References:\s*(.+?)(?:\n\S|\Z)", headers, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    raw = m.group(1).replace("\n", " ").replace("\r", "")
    return [r.strip().strip("<>") for r in re.split(r"\s+", raw) if r.strip()]


def _parse_thread_topic(headers: str) -> Optional[str]:
    """Extract X-Thread-Topic or Thread-Topic header (Exchange threading)."""
    m = re.search(r"^(?:X-)?Thread-Topic:\s*(.+)$", headers, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _parse_in_reply_to(raw: Optional[str], headers: str) -> Optional[str]:
    """Get In-Reply-To message-id, cleaned."""
    if raw and raw.strip():
        return raw.strip().strip("<>")
    # Also check headers directly
    m = re.search(r"^In-Reply-To:\s*<?([\w.@+\-]+)>?", headers, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


# ── Message Construction ──────────────────────────────────────────────────────

def _make_message(raw: dict) -> EmailMessage:
    """Convert a raw dict from applescript_bridge into an EmailMessage."""
    sender_raw  = raw.get("sender", "")
    sender_email = extract_email_address(sender_raw)
    sender_name  = extract_name(sender_raw)
    headers = raw.get("headers", "")

    date = raw.get("date_received")
    if not isinstance(date, datetime):
        date = datetime.now(timezone.utc)

    return EmailMessage(
        message_id       = raw.get("message_id", ""),
        subject          = raw.get("subject", ""),
        sender           = sender_raw,
        sender_email     = sender_email,
        sender_name      = sender_name,
        recipients       = raw.get("recipients", []),
        date_received    = date,
        date_str         = raw.get("date_str", ""),
        in_reply_to      = _parse_in_reply_to(raw.get("in_reply_to"), headers),
        references       = _parse_references(headers),
        thread_topic     = _parse_thread_topic(headers),
        headers          = headers,
        body             = raw.get("body", ""),
        account          = raw.get("account", ""),
    )


# ── Thread Grouping ───────────────────────────────────────────────────────────

def group_messages(raw_messages: list[dict]) -> list[EmailThread]:
    """
    Group raw message dicts into EmailThread objects.

    Priority:
      1. Exchange thread-topic → same topic = same thread
      2. In-Reply-To / References chain → message-id lookup
      3. Normalized subject fallback
    """
    if not raw_messages:
        return []

    messages = [_make_message(r) for r in raw_messages]

    # Index: message_id → thread_id
    msg_to_thread: dict[str, str] = {}
    # Index: thread_id → EmailThread
    threads: dict[str, EmailThread] = {}
    # Index: thread_topic → thread_id (Exchange)
    topic_to_thread: dict[str, str] = {}
    # Index: normalized_subject → thread_id
    subject_to_thread: dict[str, str] = {}

    # Sort oldest-first so replies find their parents
    for msg in sorted(messages, key=lambda m: m.date_received):
        thread_id = _find_thread(msg, msg_to_thread, topic_to_thread, subject_to_thread)

        if thread_id is None:
            # New thread
            thread_id = _make_thread_id(msg)
            thread = EmailThread(
                thread_id=thread_id,
                normalized_subject=msg.normalized_subject,
            )
            threads[thread_id] = thread

            # Register indexes
            if msg.thread_topic:
                topic_to_thread[msg.thread_topic.lower()] = thread_id
            if msg.normalized_subject:
                subject_to_thread[msg.normalized_subject] = thread_id

        threads[thread_id].add(msg)
        msg_to_thread[msg.message_id] = thread_id

        # Also register this message's ID so future replies find it
        for ref_id in msg.references:
            if ref_id and ref_id not in msg_to_thread:
                msg_to_thread[ref_id] = thread_id

    result = list(threads.values())
    log.debug(f"Grouped {len(messages)} message(s) into {len(result)} thread(s)")
    return result


def _find_thread(
    msg: EmailMessage,
    msg_to_thread: dict[str, str],
    topic_to_thread: dict[str, str],
    subject_to_thread: dict[str, str],
) -> Optional[str]:
    """Return existing thread_id that best matches this message, or None."""

    # 1. Exchange thread-topic (most reliable)
    if msg.thread_topic:
        key = msg.thread_topic.lower()
        if key in topic_to_thread:
            return topic_to_thread[key]

    # 2. In-Reply-To chain
    if msg.in_reply_to and msg.in_reply_to in msg_to_thread:
        return msg_to_thread[msg.in_reply_to]

    # 3. References chain
    for ref_id in msg.references:
        if ref_id in msg_to_thread:
            return msg_to_thread[ref_id]

    # 4. Subject fallback
    if msg.normalized_subject and msg.normalized_subject in subject_to_thread:
        return subject_to_thread[msg.normalized_subject]

    return None


def _make_thread_id(msg: EmailMessage) -> str:
    """Generate a stable thread_id from the message."""
    # Use first message_id of the thread as the anchor
    return hashlib.md5(msg.message_id.encode()).hexdigest()[:16]
