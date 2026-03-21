#!/usr/bin/env python3
"""
task_date_assigner.py — Assign due dates to undated vault tasks.

Rules (in priority order):
  1. today / ASAP → today
  2. this week → Friday of current week
  3. next week → Friday of next week
  4. by [day name] → next occurrence from file_modified_date
  5. by [Month] [Day] → parse that date
  6. Plaud meeting file → file_modified_date + 3 business days
  7. Today's daily note → today + 7 days
  8. Default → today + 14 days
  9. File older than 90 days, no date → STALE (no date assigned)

Usage:
    python3 -m System.Scripts.task_date_assigner  (runs self-test)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from System.Scripts.task_scanner import RawTask

STALE_DAYS = 90

PLAUD_SECTION_NAMES = {"action items", "next steps", "pending actions"}

DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


@dataclass
class DateAssignment:
    task: RawTask
    assigned_date: Optional[str]   # YYYY-MM-DD or None
    is_stale: bool
    rule_applied: str


def _add_business_days(start: date, days: int) -> date:
    """Add N business days (Mon–Fri) to a date."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon=0, Fri=4
            added += 1
    return current


def _friday_of_week(ref: date) -> date:
    """Return the Friday of the week containing ref."""
    days_until_friday = (4 - ref.weekday()) % 7
    if days_until_friday == 0 and ref.weekday() == 4:
        days_until_friday = 0
    elif ref.weekday() > 4:
        days_until_friday = 4 + (7 - ref.weekday())
    else:
        days_until_friday = 4 - ref.weekday()
    return ref + timedelta(days=days_until_friday)


def _next_weekday(ref: date, weekday: int) -> date:
    """Return the next occurrence of weekday (0=Mon) on or after ref + 1."""
    days_ahead = weekday - ref.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return ref + timedelta(days=days_ahead)


def _parse_explicit_date(text: str) -> Optional[date]:
    """Try to parse an explicit date from text like 'by March 25' or 'by March 25, 2026'."""
    try:
        from dateutil import parser as dp
        # Look for "by Month Day" or "by Month Day, Year"
        m = re.search(
            r'\bby\s+(January|February|March|April|May|June|July|August|'
            r'September|October|November|December)\s+(\d{1,2})(?:,?\s*(\d{4}))?\b',
            text, re.IGNORECASE
        )
        if m:
            month_str, day_str, year_str = m.group(1), m.group(2), m.group(3)
            year = int(year_str) if year_str else date.today().year
            parsed = dp.parse(f"{month_str} {day_str} {year}")
            return parsed.date()
    except Exception:
        pass
    return None


def _is_plaud_file(task: RawTask) -> bool:
    """Return True if this task appears to be from a Plaud transcript file."""
    source_lower = task.source_file.lower()
    return (
        "plaud" in source_lower
        or task.section_name in PLAUD_SECTION_NAMES
        or task.format_type in ("plaud_attributed", "plaud_tbd")
    )


def _is_todays_daily_note(task: RawTask) -> bool:
    """Return True if this task is from today's daily note."""
    today_str = date.today().strftime("%Y-%m-%d")
    return today_str in task.source_file


def assign_date(task: RawTask) -> DateAssignment:
    """Assign a due date to a task. Returns DateAssignment with result."""
    today = date.today()

    # Skip if already dated or completed
    if task.has_due_date and task.existing_due_date:
        return DateAssignment(task=task, assigned_date=task.existing_due_date,
                              is_stale=False, rule_applied="already_dated")
    if task.is_completed:
        return DateAssignment(task=task, assigned_date=None,
                              is_stale=False, rule_applied="completed_skip")

    # Stale check
    try:
        file_mtime = datetime.fromisoformat(task.file_modified_date).date()
    except Exception:
        file_mtime = today

    age_days = (today - file_mtime).days
    if age_days > STALE_DAYS:
        return DateAssignment(task=task, assigned_date=None,
                              is_stale=True, rule_applied="stale_90_days")

    text_lower = task.normalized_text.lower()

    # Rule 1: today / ASAP
    if re.search(r'\btoday\b|\basap\b', text_lower):
        return DateAssignment(task=task, assigned_date=today.strftime("%Y-%m-%d"),
                              is_stale=False, rule_applied="today_asap")

    # Rule 2: this week
    if re.search(r'\bthis week\b', text_lower):
        friday = _friday_of_week(today)
        return DateAssignment(task=task, assigned_date=friday.strftime("%Y-%m-%d"),
                              is_stale=False, rule_applied="this_week")

    # Rule 3: next week
    if re.search(r'\bnext week\b', text_lower):
        next_week_start = today + timedelta(days=(7 - today.weekday()))
        friday = _friday_of_week(next_week_start)
        return DateAssignment(task=task, assigned_date=friday.strftime("%Y-%m-%d"),
                              is_stale=False, rule_applied="next_week")

    # Rule 4: by [day name]
    day_match = re.search(
        r'\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        text_lower
    )
    if day_match:
        target_weekday = DAY_NAMES[day_match.group(1)]
        next_day = _next_weekday(file_mtime, target_weekday)
        return DateAssignment(task=task, assigned_date=next_day.strftime("%Y-%m-%d"),
                              is_stale=False, rule_applied="by_day_name")

    # Rule 5: by [Month] [Day]
    explicit = _parse_explicit_date(task.normalized_text)
    if explicit:
        return DateAssignment(task=task, assigned_date=explicit.strftime("%Y-%m-%d"),
                              is_stale=False, rule_applied="explicit_date")

    # Rule 6: Plaud meeting file → +3 business days from file mtime
    if _is_plaud_file(task):
        due = _add_business_days(file_mtime, 3)
        return DateAssignment(task=task, assigned_date=due.strftime("%Y-%m-%d"),
                              is_stale=False, rule_applied="plaud_plus3_biz")

    # Rule 7: today's daily note → today + 7
    if _is_todays_daily_note(task):
        due = today + timedelta(days=7)
        return DateAssignment(task=task, assigned_date=due.strftime("%Y-%m-%d"),
                              is_stale=False, rule_applied="daily_note_plus7")

    # Rule 8: default → today + 14
    due = today + timedelta(days=14)
    return DateAssignment(task=task, assigned_date=due.strftime("%Y-%m-%d"),
                          is_stale=False, rule_applied="default_plus14")


def assign_dates_batch(tasks: list[RawTask]) -> list[DateAssignment]:
    """Assign dates to a list of tasks."""
    return [assign_date(t) for t in tasks]


if __name__ == "__main__":
    # Quick self-test
    from datetime import date as _date
    today_str = _date.today().strftime("%Y-%m-%dT00:00:00")

    test_cases = [
        ("Fix this bug today", today_str, False),
        ("Review PR this week", today_str, False),
        ("Submit report by Friday", today_str, False),
        ("Call client next week", today_str, False),
        ("Old lingering task", "2025-06-01T00:00:00", False),
        ("Follow up with recruiter", today_str, False),
    ]

    for text, mtime, has_date in test_cases:
        task = RawTask(
            text=f"- [ ] {text}", normalized_text=text,
            source_file="/Vault/Daily/2026/03/2026-03-21-DLY.md",
            line_number=1, format_type="standard", section_name="captures",
            has_checkbox=True, is_completed=False, has_due_date=has_date,
            existing_due_date=None, has_category_tag=False, existing_category=None,
            file_modified_date=mtime,
        )
        result = assign_date(task)
        stale = " [STALE]" if result.is_stale else ""
        print(f"{result.assigned_date or 'None':12} ({result.rule_applied}){stale} — {text}")
