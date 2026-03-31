"""
contact_tracker.py — Create/update People/ contact files

update_contact(name, email, thread_subject, vault_path, date):
  Creates or updates Vault/Email/People/{Name}.md with thread history.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from . import config, tracking_db
from .email_parser import safe_filename

log = logging.getLogger("email_thread_ingester.contact_tracker")


def _org_from_email(email: str) -> str:
    """Infer organization name from email domain."""
    if "@" not in email:
        return ""
    domain = email.split("@", 1)[1].lower()
    if domain in config.DOMAIN_TO_ORG:
        return config.DOMAIN_TO_ORG[domain]
    # Capitalize the domain root (e.g. "acme.com" → "Acme")
    return domain.split(".")[0].title()


def _contact_path(name: str, email: str) -> Path:
    """Return the vault path for a contact's People/ file."""
    if name and name != email:
        fname = safe_filename(name, maxlen=50)
    else:
        local = email.split("@")[0] if "@" in email else email
        fname = safe_filename(local, maxlen=50)
    return config.PEOPLE_DIR / f"{fname}.md"


def _build_contact_note(
    name: str,
    email: str,
    org: str,
    threads: list[dict],
) -> str:
    """Render a People/ markdown file from scratch."""
    thread_lines = "\n".join(
        f"- [[{t['vault_path']}|{t['subject']}]] — {t['date']}"
        for t in threads
    )
    return f"""---
type: person
name: "{name}"
email: {email}
organization: "{org}"
tags: [person, contact]
---

# {name}

**Email**: {email}
**Organization**: {org}

## Email Threads

{thread_lines or "_No threads yet_"}
"""


def _append_thread_to_note(existing: str, thread_subject: str, vault_path: str, date: str) -> str:
    """
    Idempotently add a thread link to an existing People/ note.
    If a link to this vault_path already exists, skip.
    """
    link = f"- [[{vault_path}|{thread_subject}]] — {date}"
    if vault_path in existing:
        return existing  # already present

    # Find the "## Email Threads" section and append
    section_marker = "## Email Threads"
    if section_marker in existing:
        idx = existing.index(section_marker) + len(section_marker)
        return existing[:idx] + "\n\n" + link + existing[idx:]
    # No section found, append at end
    return existing.rstrip() + f"\n\n## Email Threads\n\n{link}\n"


def update_contact(
    name: str,
    email: str,
    thread_subject: str,
    vault_path: str,
    date: datetime,
    dry_run: bool = False,
) -> Path:
    """
    Create or update the People/ file for this contact.
    Returns the path to the contact file.
    """
    if not email:
        return config.PEOPLE_DIR / "unknown.md"

    contact_path = _contact_path(name, email)
    org = _org_from_email(email)
    date_str = date.strftime("%Y-%m-%d") if date else ""

    # Update tracking DB
    if not dry_run:
        tracking_db.upsert_contact(
            email=email,
            name=name,
            vault_path=str(contact_path),
        )

    if dry_run:
        log.info(f"  [dry-run] Would update contact: {contact_path}")
        return contact_path

    config.PEOPLE_DIR.mkdir(parents=True, exist_ok=True)

    if contact_path.exists():
        existing = contact_path.read_text(encoding="utf-8")
        updated = _append_thread_to_note(existing, thread_subject, vault_path, date_str)
        if updated != existing:
            contact_path.write_text(updated, encoding="utf-8")
            log.info(f"  Updated contact: {contact_path.name}")
    else:
        threads = [{"vault_path": vault_path, "subject": thread_subject, "date": date_str}]
        content = _build_contact_note(name or email, email, org, threads)
        contact_path.write_text(content, encoding="utf-8")
        log.info(f"  Created contact: {contact_path.name}")

    return contact_path


def update_thread_contacts(
    thread,  # EmailThread — avoid circular import
    vault_path: str,
    dry_run: bool = False,
) -> None:
    """Update contact files for all participants in a thread."""
    seen: set[str] = set()
    for msg in thread.messages:
        email = msg.sender_email
        if not email or email in seen:
            continue
        seen.add(email)
        update_contact(
            name=msg.sender_name,
            email=email,
            thread_subject=thread.normalized_subject,
            vault_path=vault_path,
            date=msg.date_received,
            dry_run=dry_run,
        )
