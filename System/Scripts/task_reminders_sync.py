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
import re
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

    Queries completed reminders from the "Vault" list that have a Key: hash
    in their notes. For each match, finds the source file and flips the
    `- [ ]` line to `- [x] ✅ YYYY-MM-DD`.

    Returns count of vault task lines updated.
    """
    if not _PYREMINDKIT_AVAILABLE:
        logger.info("PyRemindKit not available — skipping completion sync.")
        return 0

    from datetime import date as _date
    from pyremindkit import RemindKit  # type: ignore

    rk = RemindKit()

    # Resolve "Vault" list id
    vault_list_id = None
    for cal in rk.calendars.list():
        if cal.name == "Vault":
            vault_list_id = cal.id
            break

    if vault_list_id is None:
        logger.warning("sync_completions_from_reminders: 'Vault' list not found")
        return 0

    # Fetch completed reminders from the Vault list
    try:
        completed_reminders = [
            r for r in rk.get_reminders(calendar_id=vault_list_id, is_completed=True)
            if r.notes and "Key:" in r.notes
        ]
    except Exception as e:
        logger.warning(f"sync_completions_from_reminders: failed to fetch reminders: {e}")
        return 0

    if not completed_reminders:
        logger.info("sync_completions_from_reminders: no completed reminders with Key found")
        return 0

    logger.info(f"sync_completions_from_reminders: {len(completed_reminders)} completed reminders to process")

    updated = 0
    for reminder in completed_reminders:
        # Parse Source and Key from notes
        source_path = None
        key_hash = None
        for line in reminder.notes.splitlines():
            if line.startswith("Source: "):
                source_path = line[8:].strip()
            elif line.startswith("Key: "):
                key_hash = line[5:].strip()

        if not source_path or not key_hash:
            continue

        vault_file = Path(source_path)
        if not vault_file.exists():
            logger.debug(f"sync_completions_from_reminders: source file not found: {source_path}")
            continue

        # Determine completion date from reminder modified_date or today
        try:
            completion_date = reminder.modified_date.date().isoformat()
        except Exception:
            completion_date = _date.today().isoformat()

        # Scan file for matching unchecked task line
        try:
            text = vault_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"sync_completions_from_reminders: cannot read {source_path}: {e}")
            continue

        lines = text.splitlines(keepends=True)
        file_changed = False
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if not stripped.startswith("- [ ] "):
                continue
            # Extract task text (everything after "- [ ] ", strip metadata tags/dates)
            raw_task_text = stripped[6:].rstrip("\n")
            # Strip Obsidian metadata (📅 date, #tag) for key computation
            clean_text = re.sub(r'\s*📅\s*\S+', '', raw_task_text)
            clean_text = re.sub(r'\s*#\S+', '', clean_text).strip()
            computed_key = _task_key(clean_text, str(vault_file))
            if computed_key == key_hash:
                indent = line[: len(line) - len(stripped)]
                # Preserve everything after "- [ ] " (including metadata), append ✅
                new_line = f"{indent}- [x] {raw_task_text} ✅ {completion_date}\n"
                lines[i] = new_line
                file_changed = True
                logger.info(f"sync_completions_from_reminders: ✅ {clean_text[:60]} in {vault_file.name}")
                break  # one key per reminder

        if file_changed:
            try:
                tmp = vault_file.with_suffix(".tmp_rsync")
                tmp.write_text("".join(lines), encoding="utf-8")
                tmp.replace(vault_file)
                updated += 1
            except Exception as e:
                logger.warning(f"sync_completions_from_reminders: failed to write {source_path}: {e}")

    logger.info(f"sync_completions_from_reminders: updated {updated} task lines")
    return updated


def sync_completions_to_reminders(tasks: list = None) -> int:
    """
    Delete reminders whose corresponding vault task has been completed.

    Walks all incomplete reminders in the "Vault" list that have a Source: + Key:
    in their notes. For each, reads the source vault file and checks whether the
    task line is now `- [x]`. If so, deletes the reminder (Obsidian is source of
    truth — completed tasks don't need to live in Reminders).

    Returns count of reminders deleted.
    """
    if not _PYREMINDKIT_AVAILABLE:
        logger.info("PyRemindKit not available — skipping completion push to Reminders.")
        return 0

    import re as _re
    from pyremindkit import RemindKit  # type: ignore

    rk = RemindKit()

    # Resolve "Vault" list
    vault_list_id = None
    for cal in rk.calendars.list():
        if cal.name == "Vault":
            vault_list_id = cal.id
            break

    if vault_list_id is None:
        logger.warning("sync_completions_to_reminders: 'Vault' list not found")
        return 0

    try:
        open_reminders = [
            r for r in rk.get_reminders(calendar_id=vault_list_id, is_completed=False)
            if r.notes and "Key:" in r.notes and "Source:" in r.notes
        ]
    except Exception as e:
        logger.warning(f"sync_completions_to_reminders: failed to fetch reminders: {e}")
        return 0

    if not open_reminders:
        logger.info("sync_completions_to_reminders: no tracked reminders to check")
        return 0

    logger.info(f"sync_completions_to_reminders: checking {len(open_reminders)} open reminders")
    deleted = 0

    for reminder in open_reminders:
        source_path = None
        key_hash = None
        for line in reminder.notes.splitlines():
            if line.startswith("Source: "):
                source_path = line[8:].strip()
            elif line.startswith("Key: "):
                key_hash = line[5:].strip()

        if not source_path or not key_hash:
            continue

        vault_file = Path(source_path)
        if not vault_file.exists():
            continue

        # Check if the task line in the source file is now completed
        try:
            text = vault_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Search for a completed line matching this key
        task_completed = False
        for line in text.splitlines():
            stripped = line.lstrip()
            if not stripped.startswith("- [x] ") and not stripped.startswith("- [X] "):
                continue
            raw_text = stripped[6:].rstrip("\n")
            # Strip ✅ date suffix added by Phase 1
            clean_text = _re.sub(r'\s*✅\s*\S+$', '', raw_text)
            clean_text = _re.sub(r'\s*📅\s*\S+', '', clean_text)
            clean_text = _re.sub(r'\s*#\S+', '', clean_text).strip()
            if _task_key(clean_text, str(vault_file)) == key_hash:
                task_completed = True
                break

        if task_completed:
            try:
                rk.delete_reminder(reminder.id)
                logger.info(f"sync_completions_to_reminders: 🗑 {reminder.title[:60]}")
                deleted += 1
            except Exception as e:
                logger.warning(f"sync_completions_to_reminders: delete failed for '{reminder.title[:50]}': {e}")

    logger.info(f"sync_completions_to_reminders: deleted {deleted} completed reminders")
    return deleted


def sync_new_tasks_from_reminders(vault_path: Optional[Path] = None) -> int:
    """
    Pull tasks created natively in Reminders (no Source/Key) into today's DLY note.

    For each incomplete reminder in the "Vault" list without a Key: in notes:
    - Formats as `- [ ] title 📅 YYYY-MM-DD` (due date included if set)
    - Injects/replaces `## From Reminders` section in today's DLY file
    - Updates the reminder's notes with Source: + Key: so it won't be re-imported
      and will be picked up by the outbound sync on the next run

    Returns count of tasks written to DLY.
    """
    if not _PYREMINDKIT_AVAILABLE:
        logger.info("PyRemindKit not available — skipping new task import.")
        return 0

    from datetime import date as _date, datetime as _datetime
    from pyremindkit import RemindKit  # type: ignore

    rk = RemindKit()

    # Resolve "Vault" list
    vault_list_id = None
    for cal in rk.calendars.list():
        if cal.name == "Vault":
            vault_list_id = cal.id
            break

    if vault_list_id is None:
        logger.warning("sync_new_tasks_from_reminders: 'Vault' list not found")
        return 0

    # Fetch incomplete reminders without a Key (native Reminders tasks)
    try:
        new_reminders = [
            r for r in rk.get_reminders(calendar_id=vault_list_id, is_completed=False)
            if not r.notes or "Key:" not in r.notes
        ]
    except Exception as e:
        logger.warning(f"sync_new_tasks_from_reminders: failed to fetch reminders: {e}")
        return 0

    if not new_reminders:
        logger.info("sync_new_tasks_from_reminders: no new reminders to import")
        return 0

    logger.info(f"sync_new_tasks_from_reminders: {len(new_reminders)} new reminders to import")

    # Resolve today's DLY path
    if vault_path is None:
        vault_path = Path.home() / "theVault" / "Vault"

    today = _date.today()
    dly_path = (
        vault_path / "Daily"
        / today.strftime("%Y")
        / today.strftime("%m")
        / f"{today.strftime('%Y-%m-%d')}-DLY.md"
    )

    if not dly_path.exists():
        logger.warning(f"sync_new_tasks_from_reminders: DLY not found: {dly_path}")
        return 0

    # Build task lines
    task_lines = []
    for r in new_reminders:
        line = f"- [ ] {r.title}"
        if r.due_date:
            try:
                due_str = r.due_date.strftime("%Y-%m-%d")
                line += f" 📅 {due_str}"
            except Exception:
                pass
        task_lines.append((r, line))

    # Build section content (idempotent markers)
    section_lines = ["## From Reminders", "<!-- from-reminders-start -->", ""]
    for _, line in task_lines:
        section_lines.append(line)
    section_lines += ["", "<!-- from-reminders-end -->"]
    section_content = "\n".join(section_lines)

    # Inject/replace in DLY
    existing = dly_path.read_text(encoding="utf-8")
    section_re = re.compile(
        r"## From Reminders\n<!-- from-reminders-start -->.*?<!-- from-reminders-end -->",
        re.DOTALL,
    )

    if section_re.search(existing):
        updated = section_re.sub(section_content, existing)
    else:
        nav_match = re.search(r"\n## Navigation", existing)
        if nav_match:
            updated = existing[:nav_match.start()] + "\n\n" + section_content + existing[nav_match.start():]
        else:
            updated = existing.rstrip() + "\n\n" + section_content + "\n"

    tmp = dly_path.with_suffix(".tmp_rimport")
    tmp.write_text(updated, encoding="utf-8")
    tmp.replace(dly_path)
    logger.info(f"sync_new_tasks_from_reminders: wrote {len(task_lines)} tasks to {dly_path.name}")

    # Tag each reminder with Source + Key so it won't be re-imported
    for r, line in task_lines:
        task_text = r.title
        key = _task_key(task_text, str(dly_path))
        new_notes = f"Source: {dly_path}\nKey: {key}"
        try:
            rk.update_reminder(r.id, notes=new_notes)
            logger.debug(f"sync_new_tasks_from_reminders: tagged reminder '{task_text[:50]}'")
        except Exception as e:
            logger.warning(f"sync_new_tasks_from_reminders: failed to tag reminder '{task_text[:50]}': {e}")

    return len(task_lines)


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
    calendars = list(rk.calendars.list())
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
        from pyremindkit import RemindKit  # type: ignore
        rk = RemindKit()
        lists = list(rk.calendars.list())
        print(f"PyRemindKit: OK — {len(lists)} lists found")
        list_names = [l.name for l in lists]
        for required in ["Vault", "Do Today!!!!"]:
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
