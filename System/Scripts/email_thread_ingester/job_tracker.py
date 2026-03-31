"""
job_tracker.py — Create/update Job Search company index files

update_job_index(company, threads, contacts):
  Creates or updates Vault/Email/Job Search/{Company}/_Index.md
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config
from .email_parser import safe_filename

log = logging.getLogger("email_thread_ingester.job_tracker")


def _index_path(company: str) -> Path:
    company_dir = config.EMAIL_DIR / "Job Search" / safe_filename(company, maxlen=50)
    return company_dir / "_Index.md"


def _build_index(
    company: str,
    threads: list[dict],
    contacts: list[dict],
    status: str = "Active",
) -> str:
    thread_lines = "\n".join(
        f"- [[{t['vault_path']}|{t['subject']}]] — {t['date']}"
        for t in threads
    )
    contact_lines = "\n".join(
        f"- [[{c['vault_path']}|{c['name']}]] ({c['email']})"
        for c in contacts
    )
    timeline_lines = "\n".join(
        f"- {t['date']}: {t['subject']}"
        for t in sorted(threads, key=lambda x: x.get("date", ""))
    )
    return f"""---
type: job-index
company: "{company}"
status: {status}
tags: [job-search, company-index]
---

# {company} — Job Search Index

## Status

{status}

## Key Contacts

{contact_lines or "_No contacts yet_"}

## Email Threads

{thread_lines or "_No threads yet_"}

## Timeline

{timeline_lines or "_No activity yet_"}
"""


def _append_thread_to_index(existing: str, thread_subject: str, vault_path: str, date: str) -> str:
    """Idempotently add a thread link to an existing index."""
    link = f"- [[{vault_path}|{thread_subject}]] — {date}"
    if vault_path in existing:
        return existing

    # Append under ## Email Threads section
    section = "## Email Threads"
    if section in existing:
        idx = existing.index(section) + len(section)
        return existing[:idx] + "\n\n" + link + existing[idx:]
    return existing.rstrip() + f"\n\n## Email Threads\n\n{link}\n"


def _append_timeline_entry(existing: str, entry: str, date: str) -> str:
    """Idempotently add a timeline entry."""
    if entry in existing:
        return existing
    line = f"- {date}: {entry}"
    section = "## Timeline"
    if section in existing:
        idx = existing.index(section) + len(section)
        return existing[:idx] + "\n\n" + line + existing[idx:]
    return existing.rstrip() + f"\n\n## Timeline\n\n{line}\n"


def update_job_index(
    company: str,
    threads: list[dict],   # list of {vault_path, subject, date}
    contacts: list[dict],  # list of {vault_path, name, email}
    dry_run: bool = False,
) -> Path:
    """
    Create or update the Job Search company index.
    Returns the path to the index file.
    """
    if not company:
        return config.EMAIL_DIR / "Job Search" / "General" / "_Index.md"

    index_path = _index_path(company)

    if dry_run:
        log.info(f"  [dry-run] Would update job index: {index_path}")
        return index_path

    index_path.parent.mkdir(parents=True, exist_ok=True)

    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        for t in threads:
            existing = _append_thread_to_index(existing, t["subject"], t["vault_path"], t["date"])
            existing = _append_timeline_entry(existing, t["subject"], t["date"])
        index_path.write_text(existing, encoding="utf-8")
        log.info(f"  Updated job index: {index_path}")
    else:
        content = _build_index(company, threads, contacts)
        index_path.write_text(content, encoding="utf-8")
        log.info(f"  Created job index: {index_path}")

    return index_path
