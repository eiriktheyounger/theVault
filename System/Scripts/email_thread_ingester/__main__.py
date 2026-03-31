"""
__main__.py — Orchestration pipeline + CLI entry point

Pipeline:
  extract → dedup → group threads → route → summarize →
  write markdown → update contacts → update job indexes →
  update daily note → mark processed in tracking_db
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import applescript_bridge, tracking_db
from .contact_tracker import update_thread_contacts
from .daily_note_writer import inject_email_activity
from .email_parser import clean_body
from .job_tracker import update_job_index
from .markdown_writer import write_thread
from .summarizer import summarize_for_daily, summarize_thread
from .thread_grouper import EmailThread, group_messages
from .topic_router import route_thread

log = logging.getLogger("email_thread_ingester")


# ── NAS Validation ────────────────────────────────────────────────────────────

def _check_nas() -> bool:
    """Return True if the NAS vault is mounted."""
    from . import config
    return (config.VAULT_ROOT).exists()


# ── Body Cleaning Pass ────────────────────────────────────────────────────────

def _clean_messages(raw_messages: list[dict]) -> list[dict]:
    """Clean body text of all messages in-place (returns same list)."""
    for msg in raw_messages:
        msg["body"] = clean_body(msg.get("body", ""))
    return raw_messages


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_orchestration(
    accounts: list[str] = ("Exchange", "Gmail"),
    job_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    max_messages: int = 99999,
    dry_run: bool = False,
    verbose: bool = False,
    update_daily: bool = True,
) -> dict:
    """
    Run the full email ingestion pipeline.

    Returns stats dict: {extracted, new, threads, written, errors}
    """
    stats = {"extracted": 0, "new": 0, "threads": 0, "written": 0, "errors": 0}

    if not _check_nas():
        log.error("NAS vault not mounted — aborting. Run check_nas.sh to diagnose.")
        return stats

    # ── Step 1: Extract ───────────────────────────────────────────────────────
    raw_messages: list[dict] = []

    if job_filter:
        log.info(f"Job mode: scanning all mailboxes for domain '{job_filter}'")
        raw_messages = applescript_bridge.extract_job_emails(
            job_filter, start_date=start_date, end_date=end_date, max_messages=max_messages
        )
    else:
        if "Exchange" in accounts:
            raw_messages.extend(
                applescript_bridge.extract_exchange_vault_emails(
                    start_date=start_date, end_date=end_date, max_messages=max_messages
                )
            )
        if "Gmail" in accounts:
            raw_messages.extend(
                applescript_bridge.extract_gmail_vault_emails(
                    start_date=start_date, end_date=end_date, max_messages=max_messages
                )
            )

    stats["extracted"] = len(raw_messages)
    log.info(f"Extracted {len(raw_messages)} message(s)")

    # ── Step 2: Dedup ─────────────────────────────────────────────────────────
    new_messages = tracking_db.filter_new_messages(raw_messages)
    stats["new"] = len(new_messages)
    log.info(f"  {len(new_messages)} new (skipping {len(raw_messages) - len(new_messages)} already processed)")

    if not new_messages:
        log.info("Nothing new to process.")
        return stats

    # ── Step 3: Clean bodies ──────────────────────────────────────────────────
    new_messages = _clean_messages(new_messages)

    # ── Step 4: Group into threads ────────────────────────────────────────────
    threads = group_messages(new_messages)
    stats["threads"] = len(threads)
    log.info(f"  Grouped into {len(threads)} thread(s)")

    # ── Step 5–10: Per-thread processing ─────────────────────────────────────
    threads_for_daily: list[dict] = []
    job_threads_by_company: dict[str, list] = {}

    for thread in threads:
        try:
            _process_thread(
                thread=thread,
                job_filter=job_filter,
                dry_run=dry_run,
                stats=stats,
                threads_for_daily=threads_for_daily,
                job_threads_by_company=job_threads_by_company,
            )
        except Exception as e:
            log.error(f"  Error processing thread '{thread.normalized_subject}': {e}")
            stats["errors"] += 1

    # ── Step 11: Job indexes ──────────────────────────────────────────────────
    for company, thread_entries in job_threads_by_company.items():
        try:
            update_job_index(
                company=company,
                threads=thread_entries,
                contacts=[],
                dry_run=dry_run,
            )
        except Exception as e:
            log.error(f"  Error updating job index for {company}: {e}")

    # ── Step 12: Daily note ───────────────────────────────────────────────────
    if update_daily and threads_for_daily:
        try:
            inject_email_activity(threads_for_daily, datetime.now(timezone.utc), dry_run=dry_run)
        except Exception as e:
            log.error(f"  Error updating daily note: {e}")

    log.info(
        f"Done. {stats['written']} written, {stats['threads']} threads, "
        f"{stats['errors']} errors."
    )
    return stats


def _process_thread(
    thread: EmailThread,
    job_filter: str | None,
    dry_run: bool,
    stats: dict,
    threads_for_daily: list,
    job_threads_by_company: dict,
) -> None:
    """Process a single thread through routing → summarize → write → track."""
    from . import config

    # Route
    topic, dest_dir = route_thread(thread)
    if job_filter:
        topic = "Job Search"
        # Detect company from domain
        company = _company_from_domain(job_filter)
        dest_dir = config.EMAIL_DIR / "Job Search" / company

    # Summarize
    log.info(f"  [{topic}] '{thread.normalized_subject}' ({thread.message_count} msg(s))")
    summary = summarize_thread(thread)

    # Write markdown
    vault_path = write_thread(thread, summary, topic, dest_dir, dry_run=dry_run)
    vault_path_str = str(vault_path)
    stats["written"] += 1

    # Update contacts
    update_thread_contacts(thread, vault_path_str, dry_run=dry_run)

    # Mark messages processed in tracking DB
    if not dry_run:
        for msg in thread.messages:
            tracking_db.mark_message_processed(
                message_id=msg.message_id,
                thread_id=thread.thread_id,
                account=msg.account,
                subject=msg.subject,
                sender=msg.sender_email,
                date_received=msg.date_str,
            )
        tracking_db.upsert_thread(
            thread_id=thread.thread_id,
            normalized_subject=thread.normalized_subject,
            vault_path=vault_path_str,
            message_count=thread.message_count,
            first_message_date=thread.first_date.strftime("%Y-%m-%dT%H:%M:%SZ") if thread.first_date else "",
            last_message_date=thread.last_date.strftime("%Y-%m-%dT%H:%M:%SZ") if thread.last_date else "",
        )

    # Collect daily note data
    first_msg = thread.sorted_messages[-1] if thread.messages else None
    one_liner = summarize_for_daily(first_msg.body) if first_msg else ""
    date_str = thread.first_date.strftime("%Y-%m-%d") if thread.first_date else ""
    threads_for_daily.append({
        "vault_path": vault_path_str,
        "subject": thread.normalized_subject,
        "topic": topic,
        "date": date_str,
        "message_count": thread.message_count,
        "one_liner": one_liner,
    })

    # Collect job tracker data
    if topic == "Job Search":
        company = _company_from_thread(thread) or "General"
        job_threads_by_company.setdefault(company, []).append({
            "vault_path": vault_path_str,
            "subject": thread.normalized_subject,
            "date": date_str,
        })


def _company_from_domain(domain: str) -> str:
    """Convert a domain string to a company name."""
    from . import config
    if domain in config.DOMAIN_TO_ORG:
        return config.DOMAIN_TO_ORG[domain]
    return domain.split(".")[0].title()


def _company_from_thread(thread: EmailThread) -> str | None:
    """Detect company name from thread participants."""
    from . import config
    from .topic_router import _extract_domain
    for p in thread.participants:
        domain = _extract_domain(p)
        if domain:
            if domain in config.DOMAIN_TO_ORG:
                return config.DOMAIN_TO_ORG[domain]
            if domain in config.JOB_RELATED_DOMAINS:
                return domain.split(".")[0].title()
    return None


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="email_thread_ingester",
        description="Extract and archive email threads to Obsidian vault",
    )
    p.add_argument(
        "--account",
        choices=["Exchange", "Gmail", "both"],
        default="both",
        help="Which accounts to pull from (default: both)",
    )
    p.add_argument(
        "--job",
        metavar="DOMAIN",
        default=None,
        help="Job mode: scan ALL mailboxes for emails from this sender domain",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written, no disk writes",
    )
    p.add_argument(
        "--no-daily",
        action="store_true",
        help="Skip daily note injection",
    )
    p.add_argument(
        "--start-date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Only process emails received on or after this date",
    )
    p.add_argument(
        "--end-date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Only process emails received on or before this date",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=99999,
        help="Max messages to extract per account (default: 99999)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    accounts: list[str]
    if args.account == "both":
        accounts = ["Exchange", "Gmail"]
    else:
        accounts = [args.account]

    stats = run_orchestration(
        accounts=accounts,
        job_filter=args.job,
        dry_run=args.dry_run,
        verbose=args.verbose,
        update_daily=not args.no_daily,
    )

    print(
        f"\nStats: {stats['extracted']} extracted | "
        f"{stats['new']} new | "
        f"{stats['threads']} threads | "
        f"{stats['written']} written | "
        f"{stats['errors']} errors"
    )
    if args.dry_run:
        print("[dry-run mode — no files written]")


if __name__ == "__main__":
    main()
