#!/usr/bin/env python3
"""
task_normalizer.py — Main orchestrator for the theVault task normalization pipeline.

Scans vault → deduplicates → categorizes → assigns dates → writes back in-place.
Generates stale task triage file and a processing report for overnight_processor.

Usage:
    python3 -m System.Scripts.task_normalizer                      # incremental
    python3 -m System.Scripts.task_normalizer --full               # full vault scan
    python3 -m System.Scripts.task_normalizer --scan-only          # report, no writes
    python3 -m System.Scripts.task_normalizer --scan-only --full
    python3 -m System.Scripts.task_normalizer --dedup-only --dry-run
    python3 -m System.Scripts.task_normalizer --no-reminders
"""

from __future__ import annotations

import json
import logging
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("task_normalizer")

VAULT_PATH = Path.home() / "theVault" / "Vault"
STATE_FILE = Path.home() / "theVault" / "System" / "Scripts" / ".task_normalizer_state.json"
STALE_TRIAGE_PATH = VAULT_PATH / "Dashboards" / "Task_Triage_Stale.md"

from System.Scripts.task_scanner import RawTask, scan_vault, _summary
from System.Scripts.task_dedup import find_duplicates, apply_dedup
from System.Scripts.task_categorizer import categorize_batch
from System.Scripts.task_date_assigner import assign_dates_batch, DateAssignment


# ── Line rewriter ─────────────────────────────────────────────────────────────

def normalize_line(task: RawTask, category: str, due_date: Optional[str]) -> str:
    """Build the normalized task line for a given task."""
    # Start with the clean description
    desc = task.normalized_text.strip()
    if not desc:
        desc = task.text.strip()

    # Build canonical form: - [ ] desc 📅 YYYY-MM-DD #category
    parts = ["- [ ]", desc]
    if due_date:
        parts.append(f"📅 {due_date}")
    if category:
        parts.append(category)

    # Preserve original indentation
    indent_match = re.match(r'^(\s+)', task.text)
    indent = indent_match.group(1) if indent_match else ""

    return indent + " ".join(parts)


def _write_file_changes(file_path: Path, line_changes: dict[int, str]) -> bool:
    """Atomically rewrite specific lines in a file. Returns True on success."""
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        for lineno, new_text in line_changes.items():
            idx = lineno - 1
            if 0 <= idx < len(lines):
                ending = "\n" if lines[idx].endswith("\n") else ""
                lines[idx] = new_text.rstrip("\n") + ending

        tmp = file_path.with_suffix(".tmp_norm")
        tmp.write_text("".join(lines), encoding="utf-8")
        tmp.replace(file_path)
        return True
    except Exception as e:
        logger.error(f"Failed to write {file_path}: {e}")
        return False


def _write_stale_triage(stale_assignments: list[DateAssignment]) -> None:
    """Write the stale task triage file."""
    if not stale_assignments:
        content = "## Stale Tasks\n\nNo stale tasks found.\n"
    else:
        lines = [
            "---",
            "type: dashboard",
            "title: Task Triage — Stale",
            "---",
            "",
            "# 🧟 Stale Tasks",
            "",
            "Tasks from files older than 90 days with no due date.",
            "Review and either assign a date, mark `- [-]` (cancelled), or `- [x]` (done).",
            "",
            f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
            "",
            "---",
            "",
        ]
        for da in stale_assignments:
            t = da.task
            file_stem = Path(t.source_file).stem
            mtime_short = t.file_modified_date[:10]
            lines.append(
                f"- [ ] {t.normalized_text} — from [[{file_stem}]] (last modified: {mtime_short})"
            )

        content = "\n".join(lines) + "\n"

    try:
        STALE_TRIAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STALE_TRIAGE_PATH.write_text(content, encoding="utf-8")
        logger.info(f"Stale triage written: {len(stale_assignments)} tasks → {STALE_TRIAGE_PATH}")
    except Exception as e:
        logger.error(f"Failed to write stale triage: {e}")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        logger.warning(f"Could not save state: {e}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_normalizer(
    full_scan: bool = False,
    scan_only: bool = False,
    dedup_only: bool = False,
    dry_run: bool = False,
    sync_reminders: bool = True,
) -> dict:
    """
    Run the full normalization pipeline.
    Returns a processing report dict suitable for overnight_processor.
    """
    report: dict = {
        "tasks_scanned": 0,
        "files_scanned": 0,
        "tasks_normalized": 0,
        "duplicates_found": 0,
        "duplicates_resolved": 0,
        "categories_assigned": 0,
        "dates_assigned": 0,
        "stale_flagged": 0,
        "completed_today": 0,
        "completed_today_list": [],
        "completions_from_reminders": 0,
        "new_tasks_from_reminders": 0,
        "synced_to_reminders": 0,
        "errors": [],
        "format_breakdown": {},
    }

    # ── Step 1: Scan ──
    logger.info(f"Scanning vault {'(full)' if full_scan else '(incremental)'}...")
    tasks = scan_vault(VAULT_PATH, full=full_scan)
    report["tasks_scanned"] = len(tasks)

    summary = _summary(tasks)
    report["format_breakdown"] = summary.get("by_format", {})

    # Count unique files
    unique_files = len(set(t.source_file for t in tasks))
    report["files_scanned"] = unique_files

    logger.info(f"Found {len(tasks)} tasks across {unique_files} files")
    logger.info(f"Format breakdown: {summary['by_format']}")
    logger.info(
        f"Needs work: {summary['needs_checkbox']} missing checkbox, "
        f"{summary['needs_date']} missing date, "
        f"{summary['needs_category']} missing category"
    )

    # Completed today
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")
    completed_today = [
        t for t in tasks
        if t.is_completed and today_str in (t.file_modified_date or "")
    ]
    report["completed_today"] = len(completed_today)
    report["completed_today_list"] = [t.normalized_text for t in completed_today[:10]]

    if scan_only:
        logger.info("--scan-only: no writes performed")
        return report

    # ── Step 2: Dedup ──
    logger.info("Finding duplicates...")
    active_tasks = [t for t in tasks if not t.is_completed]
    dedup_actions = find_duplicates(active_tasks)
    report["duplicates_found"] = len(dedup_actions)
    logger.info(f"Found {len(dedup_actions)} duplicate clusters")

    if dedup_actions:
        if dedup_only and dry_run:
            apply_dedup(dedup_actions, dry_run=True)
            return report
        changed = apply_dedup(dedup_actions, dry_run=dry_run)
        report["duplicates_resolved"] = changed
        logger.info(f"Resolved {changed} duplicates")

    if dedup_only:
        return report

    # ── Step 3: Filter tasks needing work ──
    work_tasks = [
        t for t in tasks
        if not t.is_completed and (
            not t.has_checkbox
            or not t.has_due_date
            or not t.has_category_tag
            or t.format_type != "standard"
        )
    ]
    logger.info(f"{len(work_tasks)} tasks need normalization")

    if not work_tasks:
        logger.info("Nothing to normalize")
        _save_state({
            **_load_state(),
            "last_run": datetime.now().isoformat(),
            "tasks_processed": len(tasks),
        })
        # Still run Reminders sync even when no normalization needed
        if sync_reminders:
            try:
                from System.Scripts.task_reminders_sync import sync_completions_from_reminders
                report["completions_from_reminders"] = sync_completions_from_reminders()
            except Exception as e:
                logger.warning(f"Completions sync failed: {e}")
            try:
                from System.Scripts.task_reminders_sync import sync_completions_to_reminders
                report["completions_to_reminders"] = sync_completions_to_reminders(tasks)
            except Exception as e:
                logger.warning(f"Completion push to Reminders failed: {e}")
            try:
                from System.Scripts.task_reminders_sync import sync_new_tasks_from_reminders
                report["new_tasks_from_reminders"] = sync_new_tasks_from_reminders(VAULT_PATH)
            except Exception as e:
                logger.warning(f"New task import failed: {e}")
            try:
                from System.Scripts.task_reminders_sync import sync_tasks_to_reminders
                report["synced_to_reminders"] = sync_tasks_to_reminders(tasks, {}, {})
            except Exception as e:
                logger.warning(f"Reminders sync failed: {e}")
        return report

    # ── Step 4: Categorize ──
    logger.info("Categorizing tasks...")
    cat_map = categorize_batch(work_tasks)
    new_cats = sum(1 for i, t in enumerate(work_tasks) if not t.has_category_tag)
    report["categories_assigned"] = new_cats

    # ── Step 5: Assign dates ──
    logger.info("Assigning due dates...")
    date_assignments = assign_dates_batch(work_tasks)
    stale = [da for da in date_assignments if da.is_stale]
    dated = [da for da in date_assignments if da.assigned_date and not da.is_stale and not da.task.has_due_date]
    report["stale_flagged"] = len(stale)
    report["dates_assigned"] = len(dated)
    logger.info(f"Assigned {len(dated)} dates, flagged {len(stale)} stale")

    # ── Step 6: Write stale triage ──
    _write_stale_triage(stale)

    # ── Step 7: Write normalized lines back to source files ──
    date_by_task_id = {id(da.task): da for da in date_assignments}
    file_changes: dict[str, dict[int, str]] = {}

    for i, task in enumerate(work_tasks):
        if task.is_completed:
            continue

        category = cat_map.get(i, "#personal")
        da = date_by_task_id.get(id(task))
        due_date = (da.assigned_date if da and not da.is_stale else task.existing_due_date)

        new_line = normalize_line(task, category, due_date)

        # Only write if something actually changed
        if new_line.strip() == task.text.strip():
            continue

        src = task.source_file
        if src not in file_changes:
            file_changes[src] = {}
        file_changes[src][task.line_number] = new_line

    logger.info(f"Writing changes to {len(file_changes)} files...")
    files_written = 0
    for file_path_str, changes in file_changes.items():
        if _write_file_changes(Path(file_path_str), changes):
            files_written += 1
            report["tasks_normalized"] += len(changes)
        else:
            report["errors"].append(f"Failed to write: {file_path_str}")

    logger.info(f"Normalized {report['tasks_normalized']} tasks across {files_written} files")

    # ── Step 7.5: Pull completions from Reminders → vault (before outbound push) ──
    if sync_reminders:
        try:
            from System.Scripts.task_reminders_sync import sync_completions_from_reminders
            completions_synced = sync_completions_from_reminders()
            report["completions_from_reminders"] = completions_synced
        except ImportError:
            logger.info("Completions sync skipped (module not available)")
        except Exception as e:
            logger.warning(f"Completions sync failed: {e}")
            report["errors"].append(f"Completions sync: {e}")

    # ── Step 7.6: Import new Reminders tasks → today's DLY ──
    if sync_reminders:
        try:
            from System.Scripts.task_reminders_sync import sync_new_tasks_from_reminders
            new_imported = sync_new_tasks_from_reminders(VAULT_PATH)
            report["new_tasks_from_reminders"] = new_imported
        except ImportError:
            logger.info("New task import skipped (module not available)")
        except Exception as e:
            logger.warning(f"New task import failed: {e}")
            report["errors"].append(f"New task import: {e}")

    # ── Step 8: Apple Reminders sync ──
    if sync_reminders:
        try:
            from System.Scripts.task_reminders_sync import sync_tasks_to_reminders
            synced = sync_tasks_to_reminders(work_tasks, cat_map, date_by_task_id)
            report["synced_to_reminders"] = synced
        except ImportError:
            logger.info("Reminders sync skipped (module not available)")
        except Exception as e:
            logger.warning(f"Reminders sync failed: {e}")
            report["errors"].append(f"Reminders sync: {e}")

    # ── Step 9: Update state ──
    state = _load_state()
    _save_state({
        **state,
        "last_run": datetime.now().isoformat(),
        "tasks_processed": len(tasks),
        "duplicates_found": report["duplicates_found"],
        "categories_assigned": report["categories_assigned"],
        "dates_assigned": report["dates_assigned"],
    })

    logger.info("Normalization complete.")
    return report


def format_report(report: dict) -> str:
    """Format the processing report for inclusion in daily note."""
    lines = [
        "### Task Processing",
        f"- **Scanned**: {report.get('files_scanned', 0)} files, {report.get('tasks_scanned', 0)} tasks",
        f"- **Normalized**: {report.get('tasks_normalized', 0)} format changes",
        f"- **Deduplicated**: {report.get('duplicates_resolved', 0)} duplicates resolved",
        f"- **Categorized**: {report.get('categories_assigned', 0)} newly categorized",
        f"- **Dated**: {report.get('dates_assigned', 0)} due dates assigned",
        f"- **Stale**: {report.get('stale_flagged', 0)} flagged for review → [[Task_Triage_Stale]]",
        f"- **Completed today**: {report.get('completed_today', 0)}",
    ]
    for task_text in report.get("completed_today_list", []):
        lines.append(f"  - {task_text}")
    lines.append(f"- **Completions from Reminders**: {report.get('completions_from_reminders', 0)}")
    lines.append(f"- **New tasks from Reminders**: {report.get('new_tasks_from_reminders', 0)}")
    lines.append(f"- **Synced to Reminders**: {report.get('synced_to_reminders', 0)}")

    if report.get("errors"):
        lines.append(f"- **Errors**: {len(report['errors'])}")
        for err in report["errors"][:3]:
            lines.append(f"  - {err}")

    return "\n".join(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Normalize vault tasks")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--scan-only", action="store_true")
    ap.add_argument("--dedup-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-reminders", action="store_true")
    args = ap.parse_args()

    report = run_normalizer(
        full_scan=args.full,
        scan_only=args.scan_only,
        dedup_only=args.dedup_only,
        dry_run=args.dry_run,
        sync_reminders=not args.no_reminders,
    )
    print("\n" + format_report(report))


if __name__ == "__main__":
    main()
