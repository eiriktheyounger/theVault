"""
daily_note_writer.py — Inject/replace ## Email Activity section in daily notes

inject_email_activity(threads_processed, date):
  Appends or replaces the ## Email Activity section in Vault/Daily/YYYY/MM/YYYY-MM-DD-DLY.md
  Idempotent — safe to run multiple times per day.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config

log = logging.getLogger("email_thread_ingester.daily_note_writer")

_SECTION_HEADER = "## Email Activity"
_SECTION_RE = re.compile(
    r"## Email Activity\n.*?(?=\n## |\Z)",
    re.DOTALL,
)


def _daily_note_path(date: datetime) -> Path:
    """Return the expected daily note path for the given date."""
    year  = date.strftime("%Y")
    month = date.strftime("%m")
    fname = date.strftime("%Y-%m-%d") + "-DLY.md"
    return config.DAILY_DIR / year / month / fname


def _build_section(threads_processed: list[dict]) -> str:
    """
    Build the ## Email Activity section content.

    threads_processed is a list of dicts:
      {vault_path, subject, topic, date, message_count, one_liner}
    Job Search threads appear first.
    """
    job_threads = [t for t in threads_processed if t.get("topic") == "Job Search"]
    other_threads = [t for t in threads_processed if t.get("topic") != "Job Search"]

    lines = [_SECTION_HEADER, ""]

    def _add_group(label: str, items: list[dict]) -> None:
        if not items:
            return
        lines.append(f"### {label}")
        lines.append("")
        for t in items:
            path   = t.get("vault_path", "")
            subj   = t.get("subject", "Email")
            date   = t.get("date", "")
            count  = t.get("message_count", 1)
            liner  = t.get("one_liner", "")
            # Obsidian wikilink
            link = f"[[{path}|{subj}]]" if path else subj
            suffix = f" — {liner}" if liner else ""
            lines.append(f"- {link} ({count} msg{'s' if count != 1 else ''}, {date}){suffix}")
        lines.append("")

    _add_group("Job Search", job_threads)
    _add_group("Other", other_threads)

    return "\n".join(lines)


def inject_email_activity(
    threads_processed: list[dict],
    date: datetime,
    dry_run: bool = False,
) -> Path:
    """
    Inject or replace the ## Email Activity section in the daily note.
    Returns the daily note path.
    """
    if not threads_processed:
        log.debug("No threads to inject into daily note")
        return _daily_note_path(date)

    note_path = _daily_note_path(date)
    section_content = _build_section(threads_processed)

    if dry_run:
        log.info(f"  [dry-run] Would update daily note: {note_path}")
        log.debug(f"  Section preview:\n{section_content}")
        return note_path

    if not note_path.exists():
        log.warning(f"Daily note not found: {note_path} — creating minimal note")
        note_path.parent.mkdir(parents=True, exist_ok=True)
        date_str = date.strftime("%Y-%m-%d")
        note_path.write_text(f"# {date_str}\n\n{section_content}\n", encoding="utf-8")
        return note_path

    existing = note_path.read_text(encoding="utf-8")

    if _SECTION_HEADER in existing:
        # Replace existing section
        updated = _SECTION_RE.sub(section_content, existing)
        if updated == existing:
            # Regex didn't match (edge case) — append
            updated = existing.rstrip() + "\n\n" + section_content + "\n"
    else:
        # Append new section
        updated = existing.rstrip() + "\n\n" + section_content + "\n"

    note_path.write_text(updated, encoding="utf-8")
    log.info(f"  Updated daily note: {note_path}")
    return note_path
