#!/usr/bin/env python3
"""
task_reminders_sync.py — Sync vault tasks to Apple Reminders via PyRemindKit.

PyRemindKit is not currently available via pip. This module stubs gracefully
and logs a clear message. When PyRemindKit becomes available, implement the
functions below.

Install when available:
    pip install pyremindkit

Usage:
    python3 -m System.Scripts.task_reminders_sync --check
    python3 -m System.Scripts.task_reminders_sync --sync
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from System.Scripts.task_scanner import RawTask
    from System.Scripts.task_date_assigner import DateAssignment

logger = logging.getLogger(__name__)

_PYREMINDKIT_AVAILABLE = False
try:
    import pyremindkit  # type: ignore
    _PYREMINDKIT_AVAILABLE = True
except ImportError:
    pass


def _task_key(task_text: str, source_file: str) -> str:
    """Stable composite key for deduplication in Reminders."""
    raw = f"{task_text.lower().strip()}|{Path(source_file).name}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def sync_tasks_to_reminders(
    tasks: list,
    cat_map: dict[int, str],
    date_by_task_id: dict[int, "DateAssignment"],
) -> int:
    """
    Push vault tasks to Apple Reminders.
    Returns count of tasks synced.
    """
    if not _PYREMINDKIT_AVAILABLE:
        logger.info("PyRemindKit not available — skipping Apple Reminders sync.")
        logger.info("Install with: pip install pyremindkit")
        return 0

    from datetime import date
    today = date.today().isoformat()
    synced = 0

    for i, task in enumerate(tasks):
        if task.is_completed:
            continue

        da = date_by_task_id.get(id(task))
        if not da or da.is_stale or not da.assigned_date:
            continue

        category = cat_map.get(i, "#personal")
        due_date = da.assigned_date
        key = _task_key(task.normalized_text, task.source_file)

        try:
            # Primary sync → "Vault" list
            _upsert_reminder(
                title=task.normalized_text,
                due_date=due_date,
                notes=f"Source: {task.source_file}\nKey: {key}",
                list_name="Vault",
            )
            synced += 1

            # Mirror to "Do Today" if due today or overdue
            if due_date <= today:
                _upsert_reminder(
                    title=task.normalized_text,
                    due_date=due_date,
                    notes=f"Source: {task.source_file}\nKey: {key}",
                    list_name="Do Today!!!!",
                )
        except Exception as e:
            logger.warning(f"Failed to sync task to Reminders: {e}")

    logger.info(f"Synced {synced} tasks to Apple Reminders")
    return synced


def sync_completions_from_reminders() -> int:
    """
    Check Reminders for completed items and mark matching vault tasks as done.
    Returns count of vault files updated.
    """
    if not _PYREMINDKIT_AVAILABLE:
        logger.info("PyRemindKit not available — skipping completion sync.")
        return 0

    # TODO: implement when pyremindkit is available
    # 1. Get completed reminders from "Vault" list
    # 2. For each, find matching vault file by source note
    # 3. Update - [ ] → - [x] on matching line
    logger.warning("sync_completions_from_reminders: not yet implemented")
    return 0


def clear_do_today() -> None:
    """Remove completed/stale items from the Do Today list."""
    if not _PYREMINDKIT_AVAILABLE:
        return
    # TODO: implement when pyremindkit is available
    logger.warning("clear_do_today: not yet implemented")


def _upsert_reminder(title: str, due_date: str, notes: str, list_name: str) -> None:
    """Create or update a reminder in the named Reminders list."""
    from datetime import datetime
    from pyremindkit import RemindKit, Reminder  # type: ignore

    rk = RemindKit()

    # Resolve list_id by name
    calendars = rk.calendars.list()
    list_id = None
    for cal in calendars:
        if cal.name == list_name:
            list_id = cal.id
            break

    # Extract the Key hash from notes for dedup search
    key_hash = None
    for line in notes.splitlines():
        if line.startswith("Key: "):
            key_hash = line[5:].strip()
            break

    # Convert ISO date string to datetime at midnight local time
    due_dt = datetime.fromisoformat(due_date).replace(hour=0, minute=0, second=0, microsecond=0)

    # Search for existing reminder by Key hash
    existing = None
    if key_hash:
        for reminder in rk.search_reminders(key_hash):
            if not reminder.completed:
                existing = reminder
                break

    if existing is not None:
        rk.update_reminder(existing.id, title=title, due_date=due_dt)
    else:
        create_kwargs: dict = dict(title=title, notes=notes, due_date=due_dt)
        if list_id is not None:
            create_kwargs["list_id"] = list_id
        rk.create_reminder(**create_kwargs)


def check() -> bool:
    """Verify PyRemindKit is installed and can access Reminders."""
    if not _PYREMINDKIT_AVAILABLE:
        print("PyRemindKit: NOT INSTALLED")
        print("Install with: pip install pyremindkit")
        return False
    try:
        lists = pyremindkit.get_lists()  # type: ignore
        print(f"PyRemindKit: OK — {len(lists)} lists found")
        list_names = [l.name for l in lists]
        for required in ["Vault", "Do Today"]:
            status = "✓" if required in list_names else "✗ (will be created)"
            print(f"  {required}: {status}")
        return True
    except Exception as e:
        print(f"PyRemindKit: ERROR — {e}")
        return False


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Apple Reminders sync for vault tasks")
    ap.add_argument("--check", action="store_true", help="Verify PyRemindKit setup")
    ap.add_argument("--sync", action="store_true", help="Run manual sync")
    args = ap.parse_args()

    if args.check:
        check()
    elif args.sync:
        print("Manual sync requires running through task_normalizer.")
        print("Use: python3 -m System.Scripts.task_normalizer --no-reminders=false")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
