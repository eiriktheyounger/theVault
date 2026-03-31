"""
topic_router.py — Route email threads to vault directory paths

route_thread(thread) -> (topic_name, directory_path)

Routing priority:
  1. TOPIC_RULES: first match against (subject + sender_email).lower()
  2. Work subtopic: routed to Email/Work/Clients/{OrgName}/ by sender domain
  3. Job Search subtopic: Email/Job Search/{CompanyName}/ by sender domain
  4. Default: Email/General/
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from . import config
from .thread_grouper import EmailThread

log = logging.getLogger("email_thread_ingester.topic_router")


def route_thread(thread: EmailThread) -> tuple[str, Path]:
    """
    Return (topic_name, directory_path) for the given thread.
    directory_path is absolute, under config.EMAIL_DIR.
    """
    # Build probe string from subject + all participant emails
    subject = thread.normalized_subject.lower()
    senders = " ".join(p.lower() for p in thread.participants)
    probe = f"{subject} {senders}"

    # Check JOB_RELATED_DOMAINS before generic TOPIC_RULES
    # (company domains like nebius.com won't appear in keyword list)
    if _has_job_domain(thread):
        topic = "Job Search"
    else:
        topic = _match_topic_rules(probe)

    if topic == "Work":
        dir_path = _work_subdir(thread)
    elif topic == "Job Search":
        dir_path = _job_search_subdir(thread)
    elif topic == "Finance":
        dir_path = config.EMAIL_DIR / "Finance"
    elif topic == "Newsletter":
        dir_path = config.EMAIL_DIR / "Newsletters"
    elif topic == "Personal":
        dir_path = config.EMAIL_DIR / "Personal"
    else:
        dir_path = config.EMAIL_DIR / "General"

    log.debug(f"Routed '{thread.normalized_subject}' → {topic}: {dir_path}")
    return topic, dir_path


def _match_topic_rules(probe: str) -> str:
    """Return first matching topic name, or 'General'."""
    for topic_name, keywords in config.TOPIC_RULES:
        for kw in keywords:
            if kw.lower() in probe:
                return topic_name
    return "General"


def _work_subdir(thread: EmailThread) -> Path:
    """Route Work emails: Email/Work/Clients/{OrgName}/ or Email/Work/Internal/."""
    base = config.EMAIL_DIR / "Work"
    org = _detect_org(thread)
    if org:
        return base / "Clients" / org
    return base / "Internal"


def _job_search_subdir(thread: EmailThread) -> Path:
    """Route Job Search emails: Email/Job Search/{CompanyName}/."""
    base = config.EMAIL_DIR / "Job Search"
    company = _detect_company(thread)
    if company:
        return base / company
    return base / "General"


def _detect_org(thread: EmailThread) -> str | None:
    """Look up known org from participant email domains."""
    for email in thread.participants:
        domain = _extract_domain(email)
        if domain and domain in config.DOMAIN_TO_ORG:
            return config.DOMAIN_TO_ORG[domain]
    # Also check sender of first/last message
    for msg in thread.messages:
        domain = _extract_domain(msg.sender_email)
        if domain and domain in config.DOMAIN_TO_ORG:
            return config.DOMAIN_TO_ORG[domain]
    return None


def _detect_company(thread: EmailThread) -> str | None:
    """
    Detect company for Job Search routing.
    Uses DOMAIN_TO_ORG first, then capitalizes domain root as fallback.
    """
    for email in thread.participants:
        domain = _extract_domain(email)
        if not domain:
            continue
        if domain in config.DOMAIN_TO_ORG:
            return config.DOMAIN_TO_ORG[domain]
        if domain in config.JOB_RELATED_DOMAINS:
            # e.g. greenhouse.io → Greenhouse
            root = domain.split(".")[0].title()
            return root
    return None


def _extract_domain(email: str) -> str | None:
    """Return domain from 'user@domain.com', or None."""
    if "@" in email:
        return email.split("@", 1)[1].lower()
    return None
