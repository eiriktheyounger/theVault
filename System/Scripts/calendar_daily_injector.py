#!/usr/bin/env python3
"""
calendar_daily_injector.py — Multi-calendar EventKit → Daily Notes

Part A: Inject calendar events into DLY ### Calendar section (8 calendars)
Part C: Inject rolling 7-back/7-forward ### Week at a Glance section

Usage:
    python System/Scripts/calendar_daily_injector.py                      # today
    python System/Scripts/calendar_daily_injector.py --date 2026-04-13   # specific date
    python System/Scripts/calendar_daily_injector.py --dry-run --verbose  # preview
    python System/Scripts/calendar_daily_injector.py --start-date 2026-04-01 --end-date 2026-04-13  # backfill

Called from morning_workflow.py Step 2.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# ── EventKit ───────────────────────────────────────────────────────────────────

try:
    from EventKit import EKEventStore, EKEntityTypeEvent, EKAuthorizationStatusAuthorized
    from Foundation import NSDate
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False

# ── icalPal fallback ──────────────────────────────────────────────────────────

try:
    # Allow import whether invoked from System/Scripts/ or from the vault root
    try:
        from calendar_icalpal import fetch_icalpal_events, icalpal_available
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from calendar_icalpal import fetch_icalpal_events, icalpal_available
    ICALPAL_AVAILABLE_IMPORT = True
except ImportError:
    ICALPAL_AVAILABLE_IMPORT = False

# Backend selection via THEVAULT_CALENDAR_BACKEND: eventkit | icalpal | auto
CALENDAR_BACKEND = os.environ.get("THEVAULT_CALENDAR_BACKEND", "auto").lower()

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_ROOT = PROJECT_ROOT / "Vault"
DAILY_DIR = VAULT_ROOT / "Daily"

# ── Config ────────────────────────────────────────────────────────────────────

TARGET_CALENDARS = [
    "ExchangeCalendar",
    "eric.manchester@gmail.com",
    "Bella",
    "Alyssa Manchester",
    "Lulu",
    "Rachel",
    "Class Schedule",
    "Holidays in United States",
]

# Map calendar name → display group
CALENDAR_GROUPS = {
    "ExchangeCalendar": "Work",
    "eric.manchester@gmail.com": "Personal",
    "Bella": "Family",
    "Alyssa Manchester": "Family",
    "Lulu": "Family",
    "Rachel": "Family",
    "Class Schedule": "Classes",
    "Holidays in United States": "Holidays",
}

GROUP_ORDER = ["Work", "Personal", "Family", "Classes", "Holidays"]

# Idempotent marker regexes
CALENDAR_RE = re.compile(r"<!-- calendar-start -->.*?<!-- calendar-end -->", re.DOTALL)
WEEK_GLANCE_RE = re.compile(r"<!-- week-glance-start -->.*?<!-- week-glance-end -->", re.DOTALL)
CALENDAR_PLACEHOLDER_RE = re.compile(r"<!-- For now, manually add today's meetings here -->")

log = logging.getLogger("calendar_daily_injector")


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    calendar_name: str
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    all_day: bool = False

    @property
    def group(self) -> str:
        return CALENDAR_GROUPS.get(self.calendar_name, "Other")

    @property
    def time_str(self) -> str:
        if self.all_day:
            return "All Day"
        return f"{self.start.strftime('%H:%M')}–{self.end.strftime('%H:%M')}"


# ── EventKit Access ───────────────────────────────────────────────────────────

_store: Optional["EKEventStore"] = None


def _get_store() -> Optional["EKEventStore"]:
    global _store
    if _store is not None:
        return _store
    if not EVENTKIT_AVAILABLE:
        log.warning("EventKit not available on this platform")
        return None

    store = EKEventStore.alloc().init()
    status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)

    if status == EKAuthorizationStatusAuthorized:
        _store = store
        return _store

    # Request access
    granted = [False]
    done = [False]

    def handler(g, e):
        granted[0] = g
        done[0] = True

    store.requestAccessToEntityType_completion_(EKEntityTypeEvent, handler)

    deadline = time.time() + 10
    while not done[0] and time.time() < deadline:
        time.sleep(0.1)

    if granted[0]:
        _store = store
        return _store

    log.warning("Calendar access not granted")
    return None


def _fetch_via_eventkit(target_date: date, calendars: list[str]) -> list[CalendarEvent] | None:
    """EventKit path. Returns None if unauthorized/unavailable, [] on error,
    list on success."""
    store = _get_store()
    if not store:
        return None

    try:
        all_calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
        target_cals = [c for c in all_calendars if c.title() in calendars]
        if not target_cals:
            log.warning(f"None of the target calendars found: {calendars}")
            return []

        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time().replace(microsecond=0))
        ns_start = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
        ns_end = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())

        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            ns_start, ns_end, target_cals
        )
        events = store.eventsMatchingPredicate_(predicate)

        result: list[CalendarEvent] = []
        for ev in events:
            cal_title = ev.calendar().title() if ev.calendar() else "Unknown"
            attendees: list[str] = []
            if ev.attendees():
                for att in ev.attendees():
                    name = att.name()
                    if name:
                        attendees.append(name)
            result.append(CalendarEvent(
                title=ev.title() or "(no title)",
                start=datetime.fromtimestamp(ev.startDate().timeIntervalSince1970()),
                end=datetime.fromtimestamp(ev.endDate().timeIntervalSince1970()),
                calendar_name=cal_title,
                location=ev.location() or "",
                attendees=attendees,
                all_day=bool(ev.isAllDay()),
            ))

        result.sort(key=lambda e: e.start)
        log.info(f"[EventKit] Fetched {len(result)} events for {target_date}")
        return result

    except Exception as exc:
        log.error(f"EventKit fetch failed: {exc}")
        return []


def _fetch_via_icalpal(target_date: date, calendars: list[str]) -> list[CalendarEvent]:
    """icalPal path — reads Calendar sqlite directly."""
    if not ICALPAL_AVAILABLE_IMPORT or not icalpal_available():
        return []

    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time().replace(microsecond=0))
    raw = fetch_icalpal_events(start_dt, end_dt, calendars=calendars)

    result: list[CalendarEvent] = []
    for row in raw:
        result.append(CalendarEvent(
            title=row["title"],
            start=row["start"],
            end=row["end"],
            calendar_name=row["calendar_name"],
            location=row["location"],
            attendees=row["attendees"],
            all_day=row["all_day"],
        ))
    result.sort(key=lambda e: e.start)
    log.info(f"[icalPal] Fetched {len(result)} events for {target_date}")
    return result


def fetch_events_for_date(target_date: date, calendars: list[str] = TARGET_CALENDARS) -> list[CalendarEvent]:
    """Fetch all events on target_date across the named calendars.

    Backend selection via THEVAULT_CALENDAR_BACKEND env var:
        eventkit | icalpal | auto (default)
    """
    backend = CALENDAR_BACKEND

    if backend == "icalpal":
        return _fetch_via_icalpal(target_date, calendars)

    if backend == "eventkit":
        result = _fetch_via_eventkit(target_date, calendars)
        return result or []

    # auto: EventKit first, icalPal fallback
    ek_result = _fetch_via_eventkit(target_date, calendars)
    if ek_result is None:
        log.info("EventKit unavailable; trying icalPal fallback")
        return _fetch_via_icalpal(target_date, calendars)
    if ek_result:
        return ek_result
    if ICALPAL_AVAILABLE_IMPORT and icalpal_available():
        log.info("EventKit returned 0 events; cross-checking with icalPal")
        ical_result = _fetch_via_icalpal(target_date, calendars)
        if ical_result:
            return ical_result
    return ek_result


# ── Formatting ────────────────────────────────────────────────────────────────

def _format_events_block(events: list[CalendarEvent], include_attendees_for: set[str] = None) -> str:
    """Format events grouped by calendar group."""
    if include_attendees_for is None:
        include_attendees_for = {"Work"}

    by_group: dict[str, list[CalendarEvent]] = {}
    for ev in events:
        by_group.setdefault(ev.group, []).append(ev)

    if not by_group:
        return "_No events today._\n"

    lines: list[str] = []
    for group in GROUP_ORDER:
        if group not in by_group:
            continue
        lines.append(f"\n#### {group}")
        for ev in by_group[group]:
            lines.append(f"- **{ev.time_str}** — {ev.title}")
            if ev.location:
                lines.append(f"  - _Location: {ev.location}_")
            if ev.attendees and ev.group in include_attendees_for:
                lines.append(f"  - _Attendees: {', '.join(ev.attendees[:6])}_")

    return "\n".join(lines) + "\n"


def _format_calendar_section(events: list[CalendarEvent]) -> str:
    body = _format_events_block(events)
    return f"<!-- calendar-start -->\n{body}\n<!-- calendar-end -->"


# ── DLY Path ──────────────────────────────────────────────────────────────────

def _dly_path(target_date: date) -> Path:
    return DAILY_DIR / str(target_date.year) / f"{target_date.month:02d}" / f"{target_date.strftime('%Y-%m-%d')}-DLY.md"


# ── Injection ─────────────────────────────────────────────────────────────────

def inject_calendar_into_dly(
    target_date: date,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Part A: Inject calendar events into DLY ### Calendar section."""
    dly = _dly_path(target_date)
    if not dly.exists():
        log.warning(f"DLY not found: {dly}")
        return {"status": "skipped", "reason": "DLY not found"}

    events = fetch_events_for_date(target_date)
    if verbose:
        log.info(f"{len(events)} events found for {target_date}")

    new_block = _format_calendar_section(events)
    content = dly.read_text(encoding="utf-8")
    original = content

    if CALENDAR_RE.search(content):
        content = CALENDAR_RE.sub(new_block, content)
    elif CALENDAR_PLACEHOLDER_RE.search(content):
        content = CALENDAR_PLACEHOLDER_RE.sub(new_block, content)
    else:
        # Append block after '### Calendar' line
        content = re.sub(
            r"(### Calendar\n)",
            f"\\1{new_block}\n",
            content,
            count=1,
        )

    if content == original:
        log.info(f"No change for {target_date}")
        return {"status": "unchanged", "events": len(events)}

    if not dry_run:
        dly.write_text(content, encoding="utf-8")
        log.info(f"✓ Injected {len(events)} events into {dly.name}")
    else:
        if verbose:
            print(f"[dry-run] Would write {len(events)} events to {dly.name}")

    return {"status": "dry-run" if dry_run else "updated", "events": len(events)}


# ── Week at a Glance ──────────────────────────────────────────────────────────

def _count_vault_files_on_date(target_date: date) -> int:
    """Count .md files in Vault with mtime on target_date."""
    start = datetime.combine(target_date, datetime.min.time()).timestamp()
    end = datetime.combine(target_date, datetime.max.time().replace(microsecond=0)).timestamp()
    count = 0
    for p in VAULT_ROOT.rglob("*.md"):
        try:
            mtime = p.stat().st_mtime
            if start <= mtime <= end:
                count += 1
        except OSError:
            pass
    return count


def _format_week_glance(center_date: date) -> str:
    """Format a 15-day rolling window (7 back + today + 7 forward)."""
    past_lines = ["#### Past 7 Days", "| Date | Calendar Events | Notes Created |", "|------|----------------|---------------|"]
    future_lines = ["#### Next 7 Days", "| Date | Calendar Events |", "|------|----------------|"]

    for offset in range(-7, 0):
        d = center_date + timedelta(days=offset)
        events = fetch_events_for_date(d)
        event_str = ", ".join(f"{e.time_str} {e.title[:30]}" for e in events[:3]) or "—"
        note_count = _count_vault_files_on_date(d)
        note_str = str(note_count) if note_count else "—"
        label = d.strftime("%b %-d (%a)")
        past_lines.append(f"| {label} | {event_str} | {note_str} |")

    for offset in range(1, 8):
        d = center_date + timedelta(days=offset)
        events = fetch_events_for_date(d)
        event_str = ", ".join(f"{e.time_str} {e.title[:30]}" for e in events[:3]) or "—"
        label = d.strftime("%b %-d (%a)")
        future_lines.append(f"| {label} | {event_str} |")

    body = "\n".join(past_lines) + "\n\n" + "\n".join(future_lines) + "\n"
    return f"<!-- week-glance-start -->\n{body}\n<!-- week-glance-end -->"


def inject_week_glance(
    target_date: date,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Part C: Inject rolling week at a glance into DLY."""
    dly = _dly_path(target_date)
    if not dly.exists():
        return {"status": "skipped", "reason": "DLY not found"}

    new_block = _format_week_glance(target_date)
    content = dly.read_text(encoding="utf-8")
    original = content

    if WEEK_GLANCE_RE.search(content):
        content = WEEK_GLANCE_RE.sub(new_block, content)
    else:
        # Insert after ### Calendar section end marker or after ### Calendar header
        if "<!-- calendar-end -->" in content:
            content = content.replace(
                "<!-- calendar-end -->",
                f"<!-- calendar-end -->\n\n### Week at a Glance\n{new_block}",
                1,
            )
        else:
            # Append before ### Tasks Due Today
            content = re.sub(
                r"(### Tasks Due Today)",
                f"### Week at a Glance\n{new_block}\n\n\\1",
                content,
                count=1,
            )

    if content == original:
        return {"status": "unchanged"}

    if not dry_run:
        dly.write_text(content, encoding="utf-8")
        log.info(f"✓ Injected week glance into {dly.name}")
    elif verbose:
        print(f"[dry-run] Would inject week glance into {dly.name}")

    return {"status": "dry-run" if dry_run else "updated"}


# ── Public API (for morning_workflow import) ──────────────────────────────────

def run_for_date(target_date: date, dry_run: bool = False, verbose: bool = False) -> dict:
    """Inject calendar + week glance into DLY. Called by morning_workflow."""
    cal_result = inject_calendar_into_dly(target_date, dry_run=dry_run, verbose=verbose)
    glance_result = inject_week_glance(target_date, dry_run=dry_run, verbose=verbose)
    return {"calendar": cal_result, "week_glance": glance_result}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Inject calendar events into daily notes")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--start-date", help="Backfill start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Backfill end date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--no-week-glance", action="store_true", help="Skip week at a glance injection")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine date range
    if args.start_date and args.end_date:
        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)
        dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    elif args.date:
        dates = [date.fromisoformat(args.date)]
    else:
        dates = [date.today()]

    total_updated = 0
    for d in dates:
        cal = inject_calendar_into_dly(d, dry_run=args.dry_run, verbose=args.verbose)
        if not args.no_week_glance:
            inject_week_glance(d, dry_run=args.dry_run, verbose=args.verbose)
        if cal.get("status") == "updated":
            total_updated += 1
        if args.verbose:
            print(f"{d}: calendar={cal.get('status')} events={cal.get('events', 0)}")

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}Done: {len(dates)} date(s) processed, {total_updated} DLY files updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
