"""
markdown_writer.py — Render EmailThread + summary to Obsidian-flavored markdown

render_thread(thread, summary_data, topic, vault_path) -> str
write_thread(thread, summary_data, topic, dest_dir, dry_run) -> Path
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .email_parser import safe_filename
from .thread_grouper import EmailThread

log = logging.getLogger("email_thread_ingester.markdown_writer")


# ── Frontmatter ───────────────────────────────────────────────────────────────

def _frontmatter(thread: EmailThread, topic: str, vault_path: str) -> str:
    first_str = thread.first_date.strftime("%Y-%m-%d") if thread.first_date else ""
    last_str  = thread.last_date.strftime("%Y-%m-%d") if thread.last_date else ""
    participants_yaml = "\n".join(f"  - {p}" for p in thread.participants)
    return f"""---
type: email-thread
subject: "{thread.normalized_subject.replace('"', "'")}"
topic: {topic}
participants:
{participants_yaml}
message_count: {thread.message_count}
first_message: {first_str}
last_message: {last_str}
thread_id: {thread.thread_id}
vault_path: "{vault_path}"
tags: [email, {topic.lower().replace(" ", "-")}]
---"""


# ── Summary Section ───────────────────────────────────────────────────────────

def _summary_section(summary: dict) -> str:
    lines = ["## Summary", "", summary.get("summary", ""), ""]

    key_points = summary.get("key_points", [])
    if key_points:
        lines.append("### Key Points")
        lines.append("")
        for kp in key_points:
            lines.append(f"- {kp}")
        lines.append("")

    action_items = summary.get("action_items", [])
    if action_items:
        lines.append("### Action Items")
        lines.append("")
        for ai in action_items:
            lines.append(f"- [ ] {ai}")
        lines.append("")

    glossary = summary.get("glossary", {})
    if glossary:
        lines.append("### Glossary")
        lines.append("")
        for term, definition in glossary.items():
            lines.append(f"**{term}**: {definition}")
        lines.append("")

    return "\n".join(lines)


# ── Participant Table ─────────────────────────────────────────────────────────

def _participants_section(thread: EmailThread) -> str:
    lines = ["## Participants", "", "| Name | Email |", "|------|-------|"]
    seen: set[str] = set()
    for msg in thread.messages:
        email = msg.sender_email
        if email and email not in seen:
            seen.add(email)
            name = msg.sender_name or email
            lines.append(f"| {name} | {email} |")
    lines.append("")
    return "\n".join(lines)


# ── Message Thread ────────────────────────────────────────────────────────────

def _messages_section(thread: EmailThread) -> str:
    lines = ["## Messages", ""]
    for msg in thread.sorted_messages:
        # Anchor div for key_point references
        lines.append(f'<a id="msg-{msg.anchor_id}"></a>')
        lines.append("")
        lines.append(f"### {msg.subject}")
        lines.append("")
        lines.append(f"**From**: {msg.sender}  ")
        lines.append(f"**Date**: {msg.date_str}  ")
        if msg.recipients:
            recips = ", ".join(msg.recipients[:5])
            lines.append(f"**To**: {recips}  ")
        if msg.in_reply_to:
            lines.append(f"**In-Reply-To**: `{msg.in_reply_to}`  ")
        lines.append("")
        body = msg.body.strip() if msg.body else "_No body_"
        lines.append(body)
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


# ── Full Template ─────────────────────────────────────────────────────────────

def render_thread(thread: EmailThread, summary_data: dict, topic: str, vault_path: str = "") -> str:
    """Return complete markdown string for the thread."""
    sections = [
        _frontmatter(thread, topic, vault_path),
        "",
        f"# {thread.normalized_subject.title()}",
        "",
        _summary_section(summary_data),
        _participants_section(thread),
        _messages_section(thread),
    ]
    return "\n".join(sections)


def write_thread(
    thread: EmailThread,
    summary_data: dict,
    topic: str,
    dest_dir: Path,
    dry_run: bool = False,
) -> Path:
    """
    Write thread markdown to dest_dir/{filename}.md.
    Returns the destination path (even in dry_run).
    """
    date_prefix = ""
    if thread.first_date:
        date_prefix = thread.first_date.strftime("%Y-%m-%d") + "-"

    filename = safe_filename(thread.normalized_subject, maxlen=50)
    dest_path = dest_dir / f"{date_prefix}{filename}.md"
    # Build vault-relative path for Obsidian wikilinks (strip everything up to and including "Vault/")
    abs_str = str(dest_path)
    if "/Vault/" in abs_str:
        vault_path = abs_str.split("/Vault/", 1)[1]
        # Drop .md extension for cleaner wikilinks
        if vault_path.endswith(".md"):
            vault_path = vault_path[:-3]
    else:
        vault_path = abs_str  # fallback

    content = render_thread(thread, summary_data, topic, vault_path)

    if dry_run:
        log.info(f"  [dry-run] Would write: {dest_path}")
        return dest_path

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(content, encoding="utf-8")
    log.info(f"  Wrote: {dest_path}")
    return dest_path
