#!/usr/bin/env python3
"""
task_scanner.py — Scan the vault for task-like lines in any format.

Detects standard Obsidian checkboxes, Plaud attributed/TBD formats,
bare list items in task sections, and numbered action items.

Usage:
    python3 -m System.Scripts.task_scanner [--full] [--path vault_path]
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

VAULT_PATH = Path.home() / "theVault" / "Vault"
STATE_FILE = Path.home() / "theVault" / "System" / "Scripts" / ".task_normalizer_state.json"

# Sections the Tasks plugin (and normalizer) skip
SKIP_DIRS = {"Templates", "_templates", "System", "Plugin Test", "Dashboards"}

# Section headings that contain task-like content
TASK_SECTION_NAMES = {
    "action items", "next steps", "pending actions", "tasks",
    "tasks extracted", "to do", "todo", "follow up", "follow-up",
}

# Regex: standard Obsidian checkbox
RE_CHECKBOX = re.compile(r'^(\s*)- \[([ x/\-])\] (.+)$')

# Regex: Plaud attributed — [Name]: text — Timeline: date/TBD
RE_PLAUD_ATTR = re.compile(
    r'^\[([A-Za-z][^\]]*)\]:\s*(.+?)(?:\s*[—\-]+\s*Timeline:\s*(.+))?$'
)

# Regex: Plaud TBD inline — text - [TBD] or text - [Today/TBD]
RE_PLAUD_TBD = re.compile(r'^(.+?)\s*-\s*\[(Today/TBD|TBD|Today)\]\s*$')

# Regex: due date emoji 📅 YYYY-MM-DD
RE_DUE_DATE = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')

# Regex: category tag
RE_CATEGORY = re.compile(r'#(work|personal|career|tech|vault)\b')

# Regex: numbered list item (digits + period)
RE_NUMBERED = re.compile(r'^(\s*)\d+\.\s+(.+)$')

# Regex: bare list item (dash, no checkbox)
RE_BARE_LIST = re.compile(r'^(\s*)- (?!\[)(.+)$')

# Regex: code fence
RE_CODE_FENCE = re.compile(r'^```')


@dataclass
class RawTask:
    text: str                          # original line text (stripped)
    normalized_text: str               # cleaned task description
    source_file: str                   # absolute path string
    line_number: int                   # 1-based
    format_type: str                   # standard | plaud_attributed | plaud_tbd | bare_list | numbered
    section_name: str                  # markdown section heading (lowercased)
    has_checkbox: bool
    is_completed: bool
    has_due_date: bool
    existing_due_date: Optional[str]   # YYYY-MM-DD if present
    has_category_tag: bool
    existing_category: Optional[str]   # e.g. "#work"
    file_modified_date: str            # ISO format


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _is_in_skip_dir(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False


def _parse_plaud_date(text: str) -> Optional[str]:
    """Try to parse a date from Plaud timeline text."""
    if not text or text.strip().upper() in ("TBD", "TODAY/TBD"):
        return None
    try:
        from dateutil import parser as dateparser
        dt = dateparser.parse(text.strip(), fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def scan_file(file_path: Path) -> list[RawTask]:
    """Scan a single markdown file and return all detected tasks."""
    tasks: list[RawTask] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return tasks

    mtime = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
    lines = content.splitlines()

    current_section = ""
    in_code_block = False
    in_task_section = False

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Track code fences
        if RE_CODE_FENCE.match(stripped):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Track section headings
        heading_match = re.match(r'^#{1,6}\s+(.+)$', stripped)
        if heading_match:
            current_section = heading_match.group(1).strip()
            in_task_section = current_section.lower() in TASK_SECTION_NAMES
            continue

        # Skip blockquotes (unless in a task section)
        if stripped.startswith('>') and not in_task_section:
            continue

        task = _detect_task(line, stripped, file_path, lineno, current_section, in_task_section, mtime)
        if task:
            tasks.append(task)

    return tasks


def _detect_task(
    line: str,
    stripped: str,
    file_path: Path,
    lineno: int,
    section: str,
    in_task_section: bool,
    mtime: str,
) -> Optional[RawTask]:
    """Try to detect a task from a single line. Returns None if not a task."""

    # ── Format A: standard Obsidian checkbox ──
    m = RE_CHECKBOX.match(line)
    if m:
        status_char = m.group(2)
        desc = m.group(3).strip()
        is_completed = status_char.lower() == 'x'
        due_match = RE_DUE_DATE.search(desc)
        cat_match = RE_CATEGORY.search(desc)
        # Clean normalized text: remove date emoji+date, category tags, done emoji
        norm = re.sub(r'📅\s*\d{4}-\d{2}-\d{2}', '', desc)
        norm = re.sub(r'✅\s*\d{4}-\d{2}-\d{2}', '', norm)
        norm = re.sub(r'#(work|personal|career|tech|vault)\b', '', norm).strip()
        return RawTask(
            text=stripped,
            normalized_text=norm,
            source_file=str(file_path),
            line_number=lineno,
            format_type="standard",
            section_name=section.lower(),
            has_checkbox=True,
            is_completed=is_completed,
            has_due_date=bool(due_match),
            existing_due_date=due_match.group(1) if due_match else None,
            has_category_tag=bool(cat_match),
            existing_category=cat_match.group(0) if cat_match else None,
            file_modified_date=mtime,
        )

    # Only look for non-standard formats inside task sections
    if not in_task_section:
        return None

    # ── Format B: Plaud attributed — [Name]: text — Timeline: ... ──
    m = RE_PLAUD_ATTR.match(stripped)
    if m:
        _speaker = m.group(1)
        desc = m.group(2).strip()
        timeline_raw = m.group(3)
        parsed_date = _parse_plaud_date(timeline_raw) if timeline_raw else None
        return RawTask(
            text=stripped,
            normalized_text=desc,
            source_file=str(file_path),
            line_number=lineno,
            format_type="plaud_attributed",
            section_name=section.lower(),
            has_checkbox=False,
            is_completed=False,
            has_due_date=bool(parsed_date),
            existing_due_date=parsed_date,
            has_category_tag=False,
            existing_category=None,
            file_modified_date=mtime,
        )

    # ── Format B2: Plaud TBD inline — text - [TBD] ──
    m = RE_PLAUD_TBD.match(stripped)
    if m:
        desc = m.group(1).strip()
        return RawTask(
            text=stripped,
            normalized_text=desc,
            source_file=str(file_path),
            line_number=lineno,
            format_type="plaud_tbd",
            section_name=section.lower(),
            has_checkbox=False,
            is_completed=False,
            has_due_date=False,
            existing_due_date=None,
            has_category_tag=False,
            existing_category=None,
            file_modified_date=mtime,
        )

    # ── Format C: bare list item in task section ──
    m = RE_BARE_LIST.match(line)
    if m:
        desc = m.group(2).strip()
        if not desc:
            return None
        # Exclude lines that look like section content (e.g. "- See also:")
        if len(desc) < 5:
            return None
        return RawTask(
            text=stripped,
            normalized_text=desc,
            source_file=str(file_path),
            line_number=lineno,
            format_type="bare_list",
            section_name=section.lower(),
            has_checkbox=False,
            is_completed=False,
            has_due_date=False,
            existing_due_date=None,
            has_category_tag=False,
            existing_category=None,
            file_modified_date=mtime,
        )

    # ── Format D: numbered action item in task section ──
    m = RE_NUMBERED.match(line)
    if m:
        desc = m.group(2).strip()
        if not desc or len(desc) < 5:
            return None
        return RawTask(
            text=stripped,
            normalized_text=desc,
            source_file=str(file_path),
            line_number=lineno,
            format_type="numbered",
            section_name=section.lower(),
            has_checkbox=False,
            is_completed=False,
            has_due_date=False,
            existing_due_date=None,
            has_category_tag=False,
            existing_category=None,
            file_modified_date=mtime,
        )

    return None


def scan_vault(vault_path: Path = VAULT_PATH, full: bool = False) -> list[RawTask]:
    """Scan the vault and return all detected tasks."""
    state = _load_state()
    last_run_ts: Optional[float] = None

    if not full and "last_run" in state:
        try:
            last_run_ts = datetime.fromisoformat(state["last_run"]).timestamp()
        except Exception:
            last_run_ts = None

    all_tasks: list[RawTask] = []
    files_scanned = 0

    for md_file in sorted(vault_path.rglob("*.md")):
        if _is_in_skip_dir(md_file.relative_to(vault_path)):
            continue
        if last_run_ts and md_file.stat().st_mtime < last_run_ts:
            continue
        tasks = scan_file(md_file)
        all_tasks.extend(tasks)
        files_scanned += 1

    return all_tasks


def _summary(tasks: list[RawTask]) -> dict:
    fmt_counts: dict[str, int] = {}
    for t in tasks:
        fmt_counts[t.format_type] = fmt_counts.get(t.format_type, 0) + 1
    return {
        "total": len(tasks),
        "by_format": fmt_counts,
        "needs_checkbox": sum(1 for t in tasks if not t.has_checkbox),
        "needs_date": sum(1 for t in tasks if not t.has_due_date and not t.is_completed),
        "needs_category": sum(1 for t in tasks if not t.has_category_tag and not t.is_completed),
        "completed": sum(1 for t in tasks if t.is_completed),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Scan vault for task-like lines")
    ap.add_argument("--full", action="store_true", help="Scan all files, not just recently modified")
    ap.add_argument("--path", default=str(VAULT_PATH), help="Vault path to scan")
    args = ap.parse_args()

    vault = Path(args.path)
    tasks = scan_vault(vault, full=args.full)
    summary = _summary(tasks)
    print(json.dumps(summary, indent=2))
    print(f"\nScanned {len(tasks)} tasks from {vault}", file=sys.stderr)


if __name__ == "__main__":
    main()
