#!/usr/bin/env python3
"""
calendar_icalpal.py — icalPal (Ruby gem) bridge for macOS Calendar access.

Purpose
-------
Provides a TCC-bypass fallback for calendar fetches when EventKit is blocked
by macOS permission walls. icalPal reads Calendar.app's sqlite database
directly — it only needs Full Disk Access granted to the *parent* process
(Terminal / cron / launchd), not per-app Calendar permission.

This wrapper shells out to the icalPal Ruby binary, parses its JSON output,
and returns event objects with the **same shape** as the EventKit fetchers in
calendar_forward_back.py and calendar_daily_injector.py, so callers can swap
backends transparently.

Public API
----------
    fetch_icalpal_events(start_dt, end_dt, calendars=None) -> list[dict]
        Returns normalized event dicts with keys:
            title, start, end, calendar_name, location, notes,
            attendees, all_day, url, uid
        Start/end are timezone-naive datetime objects (local time),
        matching the EventKit fetchers.

    icalpal_available() -> bool
        Whether the `icalPal` binary is on PATH or in the default gem location.

Environment
-----------
    ICALPAL_BIN            Explicit path to icalPal binary (optional)
    ICALPAL_GEM_HOME       GEM_HOME if icalPal is in a non-standard gem dir
    ICALPAL_EXTRA_ARGS     Additional CLI args (space-separated)

Notes
-----
* icalPal returns dates as Ruby DateTime strings (ISO 8601 w/ offset).
* Multi-day events are pre-expanded to per-day occurrences by icalPal.
* Recurring events are expanded within the requested window.
* Canceled events are filtered by icalPal before emission.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger("calendar_icalpal")


# ── Binary discovery ──────────────────────────────────────────────────────────

_DEFAULT_GEM_BIN_DIRS = [
    Path.home() / ".gem" / "bin",
    Path.home() / ".local" / "share" / "gem" / "ruby" / "4.0.0" / "bin",
    Path("/opt/homebrew/lib/ruby/gems/4.0.0/bin"),
    Path("/usr/local/lib/ruby/gems/4.0.0/bin"),
]


def _find_icalpal_binary() -> Optional[Path]:
    """Locate icalPal binary. Respects ICALPAL_BIN env var."""
    override = os.environ.get("ICALPAL_BIN")
    if override:
        p = Path(override).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return p
        log.warning(f"ICALPAL_BIN={override} not executable")

    # PATH lookup
    found = shutil.which("icalPal")
    if found:
        return Path(found)

    # Check known gem bin dirs
    for d in _DEFAULT_GEM_BIN_DIRS:
        candidate = d / "icalPal"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    return None


_BINARY_CACHE: Optional[Path] = None


def icalpal_available() -> bool:
    """Return True if icalPal binary is reachable."""
    global _BINARY_CACHE
    if _BINARY_CACHE is not None:
        return True
    found = _find_icalpal_binary()
    if found:
        _BINARY_CACHE = found
        return True
    return False


def _icalpal_bin() -> Path:
    global _BINARY_CACHE
    if _BINARY_CACHE is None:
        found = _find_icalpal_binary()
        if not found:
            raise FileNotFoundError(
                "icalPal binary not found. Install with:\n"
                "  export PATH=\"/opt/homebrew/opt/ruby/bin:$PATH\"\n"
                "  export GEM_HOME=\"$HOME/.gem\"\n"
                "  gem install icalPal\n"
            )
        _BINARY_CACHE = found
    return _BINARY_CACHE


# ── Subprocess invocation ─────────────────────────────────────────────────────

def _build_env() -> dict:
    """Build env dict for the icalPal subprocess."""
    env = os.environ.copy()

    # If the user used --user-install to avoid permission errors, they need
    # GEM_HOME pointing at ~/.gem so Ruby can find the gem dependencies.
    gem_home = os.environ.get("ICALPAL_GEM_HOME") or str(Path.home() / ".gem")
    if Path(gem_home).exists():
        env["GEM_HOME"] = gem_home
        env["GEM_PATH"] = gem_home

    # Ensure Homebrew Ruby is on PATH — icalPal requires Ruby 3.0+
    brew_ruby = Path("/opt/homebrew/opt/ruby/bin")
    if brew_ruby.exists():
        env["PATH"] = f"{brew_ruby}:{env.get('PATH', '')}"

    return env


def _run_icalpal(args: list[str], timeout: int = 30) -> str:
    """Run icalPal and return stdout. Raises on failure."""
    cmd = [str(_icalpal_bin())] + args

    extra = os.environ.get("ICALPAL_EXTRA_ARGS", "").split()
    if extra:
        cmd.extend(extra)

    log.debug("icalPal cmd: %s", " ".join(cmd))

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_build_env(),
    )

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        # Surface FDA hints up to caller
        if "Full Disk Access" in stderr or "Operation not permitted" in stderr:
            raise PermissionError(
                "icalPal could not read the Calendar database. The parent "
                "process needs Full Disk Access in System Settings. "
                f"stderr:\n{stderr}"
            )
        raise RuntimeError(
            f"icalPal exited {proc.returncode}. stderr:\n{stderr}"
        )

    return proc.stdout


# ── Date/time parsing ─────────────────────────────────────────────────────────

def _parse_ical_datetime(raw) -> Optional[datetime]:
    """Parse icalPal's DateTime output into a naive local datetime.

    icalPal emits several date representations per event:
      * sseconds / eseconds  — Unix epoch integers (most reliable)
      * sctime / ectime      — "YYYY-MM-DD HH:MM:SS ±HHMM" with offset
      * sdate / edate        — human-friendly ("today", "yesterday",
                               "May 4, 2026") — NOT parseable; ignored here
      * start_date / end_date — iCal reference seconds (since 2001-01-01 UTC)

    This helper accepts all of the above except sdate/edate.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        # Heuristic: iCal reference epoch starts 2001-01-01. Values under
        # ~1 billion are iCal seconds; values over are Unix epoch.
        # 2001-01-01 UTC = 978307200 Unix. icalPal's start_date field is
        # iCal seconds; sseconds is Unix seconds.
        try:
            if raw < 978307200:  # iCal reference epoch offset
                return datetime.fromtimestamp(raw + 978307200)
            return datetime.fromtimestamp(raw)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(raw, str):
        return None

    s = raw.strip()
    if not s:
        return None

    # Try ISO 8601 first (fromisoformat handles colon offsets in 3.7+)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        pass

    # icalPal sctime/ectime format: "2026-04-21 09:00:00 -0400"
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except ValueError:
            continue

    # Human strings ("today", "tomorrow", "Jan 4, 2026") are intentionally
    # not parsed — caller should use sseconds/eseconds for those rows.
    return None


# ── Row → normalized dict ─────────────────────────────────────────────────────

def _normalize_row(row: dict) -> Optional[dict]:
    """Convert one icalPal JSON row into the shared event shape.

    Date resolution priority (most → least reliable):
      1. sseconds / eseconds  — Unix epoch integers
      2. sctime / ectime      — ISO-ish strings with offset
      3. start_date / end_date — iCal reference seconds (since 2001-01-01)
    sdate / edate are intentionally skipped — they contain human strings
    like "today" that can't be parsed.
    """
    def _resolve(row, keys):
        for k in keys:
            v = row.get(k)
            if v is None:
                continue
            dt = _parse_ical_datetime(v)
            if dt is not None:
                return dt
        return None

    start = _resolve(row, ("sseconds", "sctime", "start_date"))
    end = _resolve(row, ("eseconds", "ectime", "end_date"))

    if not start:
        return None
    if not end:
        # Fall back to a 30-minute block if the end date is unparseable
        end = start + timedelta(minutes=30)

    title = row.get("title") or row.get("summary") or "(no title)"
    calendar_name = (row.get("calendar") or "Unknown").strip()

    # Map icalPal's raw sqlite calendar names to the EventKit display names
    # used in calendar_forward_back.INCLUDED_CALENDARS and
    # calendar_daily_injector.TARGET_CALENDARS.
    store = (row.get("store") or row.get("account") or "").strip()
    if store == "Exchange" and calendar_name == "Calendar":
        calendar_name = "ExchangeCalendar"

    # Skip Reminders/tasks that sometimes appear in the events stream
    if calendar_name in ("Scheduled Reminders",) or store == "Reminders":
        return None

    location = row.get("location") or ""
    address = row.get("address") or ""
    # icalPal sometimes merges address into location via its accessor. If the
    # raw row has a separate address, join them.
    if location and address and address != location:
        location = f"{location} {address}".strip()
    elif address and not location:
        location = address

    notes = row.get("notes") or row.get("description") or ""
    url = row.get("url") or ""

    attendees_raw = row.get("attendees") or []
    if isinstance(attendees_raw, str):
        # Shouldn't happen with JSON output, but be defensive
        try:
            attendees_raw = json.loads(attendees_raw)
        except json.JSONDecodeError:
            attendees_raw = []
    attendees = [str(a) for a in attendees_raw if a]

    all_day = bool(row.get("all_day"))

    return {
        "title": title,
        "start": start,
        "end": end,
        "calendar_name": calendar_name,
        "location": location,
        "notes": notes.strip() if isinstance(notes, str) else "",
        "attendees": attendees,
        "all_day": all_day,
        "url": url,
    }


# ── Public fetch API ──────────────────────────────────────────────────────────

def fetch_icalpal_events(
    start_dt: datetime | date,
    end_dt: datetime | date,
    calendars: list[str] | None = None,
    timeout: int = 30,
) -> list[dict]:
    """
    Fetch events between start_dt and end_dt via icalPal.

    Returns normalized event dicts matching the EventKit fetcher shape:
        {title, start, end, calendar_name, location, notes, attendees,
         all_day, url}

    `calendars` restricts to the given calendar titles (passed to --ic).
    Defaults to all calendars.
    """
    if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
        start_dt = datetime.combine(start_dt, datetime.min.time())
    if isinstance(end_dt, date) and not isinstance(end_dt, datetime):
        end_dt = datetime.combine(end_dt, datetime.max.time().replace(microsecond=0))

    # icalPal's `events` command with --from/--to takes YYYY-MM-DD
    from_s = start_dt.strftime("%Y-%m-%d")
    # --to is exclusive in some icalPal versions; use +1 day to be safe then filter
    to_s = (end_dt.date() + timedelta(days=1)).strftime("%Y-%m-%d")

    args = [
        "events",
        "--from", from_s,
        "--to", to_s,
        "-o", "json",
    ]

    # We do NOT pass --ic to icalPal. The raw sqlite calendar titles can
    # differ from EventKit display names ("Calendar" vs "ExchangeCalendar",
    # trailing whitespace on "Lulu "). Instead, normalize in _normalize_row
    # and filter in Python below.

    try:
        raw = _run_icalpal(args, timeout=timeout)
    except FileNotFoundError:
        log.info("icalPal binary not found; fallback unavailable")
        return []
    except PermissionError as exc:
        log.warning("icalPal permission denied: %s", exc)
        return []
    except subprocess.TimeoutExpired:
        log.warning("icalPal timed out after %ss", timeout)
        return []
    except RuntimeError as exc:
        log.warning("icalPal failed: %s", exc)
        return []

    if not raw.strip():
        return []

    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("icalPal returned non-JSON output: %s", exc)
        log.debug("raw stdout: %r", raw[:500])
        return []

    if not isinstance(rows, list):
        log.error("icalPal JSON was %s, expected list", type(rows).__name__)
        return []

    # Build a set of permitted calendar names for Python-side filtering.
    # We accept exact matches against the caller's list (which uses
    # EventKit display names), since _normalize_row already maps
    # "Calendar" → "ExchangeCalendar" and trims whitespace.
    allowed = set(c.strip() for c in calendars) if calendars else None

    events: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_row(row)
        if not normalized:
            continue

        # Calendar filter (post-normalization)
        if allowed is not None and normalized["calendar_name"] not in allowed:
            continue

        # Drop events strictly outside the window
        if normalized["end"] < start_dt or normalized["start"] > end_dt:
            continue
        events.append(normalized)

    events.sort(key=lambda e: e["start"])
    log.info(
        "icalPal fetched %d events from %s to %s",
        len(events), start_dt.date(), end_dt.date(),
    )
    return events


# ── CLI smoke test ────────────────────────────────────────────────────────────

def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="icalPal calendar fetch smoke test")
    ap.add_argument("--days", type=int, default=1, help="look ahead this many days")
    ap.add_argument("--calendar", action="append", help="restrict to calendar title (repeatable)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not icalpal_available():
        print("icalPal binary NOT found. Set ICALPAL_BIN or install the gem.")
        return 2

    start = datetime.now()
    end = start + timedelta(days=args.days)
    events = fetch_icalpal_events(start, end, args.calendar)

    print(f"Found {len(events)} events between {start:%Y-%m-%d %H:%M} and {end:%Y-%m-%d %H:%M}")
    for ev in events:
        print(
            f"  {ev['start']:%Y-%m-%d %H:%M} — {ev['title']} "
            f"({ev['calendar_name']})"
            + (f"  📍 {ev['location']}" if ev["location"] else "")
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(_cli())
