#!/usr/bin/env python3
"""
calendar_forward_back.py — Per-calendar extraction, VC detection, range fetching
for the ADHD/OOSOOM-first `## 🎯 Today — Forward-Back` DLY section.

Design rules (locked by Eric 2026-04-19):

  P0 calendars (full extraction):
    - eric.manchester@gmail.com
    - ExchangeCalendar

  P1 family calendars:
    - Rachel               (title + time + note)
    - Alyssa Manchester    (title + time + note)  ┐
    - Lulu                 (title + time + note)  ┘ Merged under "Alyssa"
    - Class Schedule       (short title + time)
    - Bella                (title + time)

  Excluded:
    - Holidays in United States

VC handling (never send VC boilerplate through an LLM):
  - Location is a URL → identify VC provider (Zoom / Teams / Meet / Webex / …)
  - Location blank + notes has VC URL → "VC URL: True"
  - Notes are pure VC boilerplate → drop, mark "VC URL: True"
  - Notes have real content → truncate to 200 chars, or Gemma4-local one-line
    summarize (never Haiku)

Range fetch reuses the existing stable calendar_daily_injector pattern but
adds its own fetch loop so notes() can be captured per event.

Does NOT modify calendar_daily_injector.py. Imports only constants.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

log = logging.getLogger("calendar_forward_back")

# ── EventKit (optional — only on macOS) ──────────────────────────────────────
try:
    from EventKit import EKEventStore, EKEntityTypeEvent, EKAuthorizationStatusAuthorized
    from Foundation import NSDate
    EVENTKIT_AVAILABLE = True
except ImportError:  # pragma: no cover — non-macOS dev environments
    EVENTKIT_AVAILABLE = False

# ── icalPal fallback (TCC-bypass via Ruby gem reading Calendar sqlite) ───────
try:
    from calendar_icalpal import fetch_icalpal_events, icalpal_available
    ICALPAL_AVAILABLE_IMPORT = True
except ImportError:  # pragma: no cover
    ICALPAL_AVAILABLE_IMPORT = False

# Backend selection: "eventkit" (default), "icalpal", "auto" (try EK then icalPal)
# Set via env var THEVAULT_CALENDAR_BACKEND
CALENDAR_BACKEND = os.environ.get("THEVAULT_CALENDAR_BACKEND", "auto").lower()

# ── Config: per-calendar extraction rules ────────────────────────────────────
# keyed by the exact EventKit calendar title

CALENDAR_RULES: dict[str, dict] = {
    "eric.manchester@gmail.com": dict(group="Eric Personal", priority="P0", extract="full",             emoji="🔵"),
    "ExchangeCalendar":          dict(group="Eric Work",     priority="P0", extract="full",             emoji="💼"),
    "Rachel":                    dict(group="Rachel",        priority="P1", extract="title_time_note",  emoji="💗"),
    "Alyssa Manchester":         dict(group="Alyssa",        priority="P1", extract="title_time_note",  emoji="🧒"),
    "Lulu":                      dict(group="Alyssa",        priority="P1", extract="title_time_note",  emoji="🧒"),
    "Class Schedule":            dict(group="Alyssa Classes",priority="P1", extract="short_title_time", emoji="📚"),
    "Bella":                     dict(group="Bella",         priority="P1", extract="title_time",       emoji="👧"),
    "Holidays in United States": dict(group=None,            priority=None, extract="skip",             emoji=""),
}

INCLUDED_CALENDARS: list[str] = [
    name for name, rule in CALENDAR_RULES.items() if rule["extract"] != "skip"
]

# Display-order: P0 work/personal first, then family groups
GROUP_ORDER = ["Eric Work", "Eric Personal", "Rachel", "Alyssa", "Alyssa Classes", "Bella"]

CLASS_TITLE_MAX = 40
MAX_NOTES_CHARS = 200

# ── VC detection ─────────────────────────────────────────────────────────────

_VC_PATTERNS: dict[str, re.Pattern] = {
    "Zoom":        re.compile(r"zoom\.us",              re.I),
    "Teams":       re.compile(r"teams\.microsoft\.com", re.I),
    "Google Meet": re.compile(r"meet\.google\.com",     re.I),
    "Webex":       re.compile(r"webex\.com",            re.I),
    "GoToMeeting": re.compile(r"gotomeeting\.com",      re.I),
    "BlueJeans":   re.compile(r"bluejeans\.com",        re.I),
    "Hangouts":    re.compile(r"hangouts\.google",      re.I),
}
_URL_RE = re.compile(r"https?://\S+")

# VC boilerplate lines — dropped before we decide if notes have real content
_VC_BOILERPLATE_RE = re.compile(
    r"(join\s+zoom|zoom\s+meeting|meeting\s+id|passcode|password|"
    r"join\s+the\s+meeting|click\s+to\s+join|dial[- ]?in|one\s+tap\s+mobile|"
    r"microsoft\s+teams\s+meeting|teams\s+meeting|join\s+microsoft\s+teams|"
    r"join\s+on\s+your\s+computer|phone\s+conference|phone\s+number|"
    r"meeting\s+options|learn\s+more\s+about\s+teams|help\s+\|\s+meeting\s+options|"
    r"_{3,})",
    re.I,
)


def detect_vc(text: str | None) -> str | None:
    """Return a known VC provider name, or 'VC URL' for generic, or None."""
    if not text:
        return None
    for name, pat in _VC_PATTERNS.items():
        if pat.search(text):
            return name
    if _URL_RE.search(text):
        return "VC URL"
    return None


def _strip_vc_noise(text: str) -> str:
    """Remove URLs + known VC boilerplate lines. Returns what remains."""
    cleaned = _URL_RE.sub("", text)
    lines_out: list[str] = []
    for line in cleaned.splitlines():
        if _VC_BOILERPLATE_RE.search(line):
            continue
        lines_out.append(line)
    return re.sub(r"\n{2,}", "\n", "\n".join(lines_out)).strip()


def process_notes(notes: str | None, use_gemma: bool = True) -> tuple[str, Optional[str]]:
    """
    Return (clean_notes, vc_flag).

    - clean_notes is '' when the notes were pure VC boilerplate
    - vc_flag is the VC provider name, or 'VC URL' generic, or None
    - Notes longer than MAX_NOTES_CHARS get one-line Gemma4-local summary
      (never Haiku). If Gemma4 is unreachable → hard-truncate with `…`.
    """
    if not notes:
        return "", None
    text = notes.strip()
    vc = detect_vc(text)

    stripped = _strip_vc_noise(text)
    if not stripped:
        return "", vc  # pure VC boilerplate

    if len(stripped) <= MAX_NOTES_CHARS:
        return stripped, vc

    if use_gemma:
        one_line = _gemma_one_line_summary(stripped)
        if one_line:
            return one_line, vc

    return stripped[:MAX_NOTES_CHARS].rstrip() + "…", vc


_OLLAMA_URL = "http://localhost:11434/api/chat"
_GEMMA_MODEL = "gemma4:e4b"
_GEMMA_TIMEOUT = 30  # sec — keep tight; calendar run must not stall workflow


def _gemma_one_line_summary(text: str) -> str | None:
    """
    One-line (≤ ~100 chars) summary of calendar event notes via local Ollama
    Gemma4. Returns None on any failure — caller falls back to hard truncation.
    """
    try:
        payload = {
            "model": _GEMMA_MODEL,
            "messages": [{
                "role": "user",
                "content": (
                    "Summarize this calendar event note in ONE short line under "
                    "90 characters. No preamble, no quotes — just the summary:\n\n"
                    + text[:2000]
                ),
            }],
            "stream": False,
            "options": {"num_ctx": 2048, "temperature": 0.2, "num_predict": 80},
        }
        req = urllib.request.Request(
            _OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=_GEMMA_TIMEOUT) as resp:
            data = json.loads(resp.read())
        content = (data.get("message") or {}).get("content", "").strip()
        # Strip Gemma thinking tags + code fences
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        content = re.sub(r"^```.*?\n|\n```$", "", content, flags=re.DOTALL).strip()
        # First line only, capped
        content = content.split("\n", 1)[0][:120].strip().strip('"\'')
        return content or None
    except Exception as e:
        log.debug(f"Gemma4 unavailable for notes summary: {e}")
        return None


# ── Title shortening for Class Schedule ──────────────────────────────────────

def short_class_title(title: str | None) -> str:
    if not title:
        return "(untitled class)"
    t = title.strip()
    return t if len(t) <= CLASS_TITLE_MAX else t[:CLASS_TITLE_MAX].rstrip() + "…"


# ── Event dataclass (richer than calendar_daily_injector's — adds notes) ─────

@dataclass
class RangeEvent:
    title: str
    start: datetime
    end: datetime
    calendar_name: str
    location: str = ""
    notes: str = ""
    attendees: list[str] = field(default_factory=list)
    all_day: bool = False
    url: str = ""
    uid: str = ""

    @property
    def rule(self) -> dict:
        return CALENDAR_RULES.get(self.calendar_name, {"group": "Other", "extract": "title_time", "emoji": ""})

    @property
    def group(self) -> str:
        return self.rule.get("group") or "Other"

    @property
    def priority(self) -> str | None:
        return self.rule.get("priority")

    @property
    def time_str(self) -> str:
        if self.all_day:
            return "All Day"
        return f"{self.start.strftime('%H:%M')}–{self.end.strftime('%H:%M')}"


# ── EventKit fetch (range-aware, notes-capturing) ────────────────────────────

_store = None


def _get_store():
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
    # Request access (async in theory; we poll briefly)
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


def _fetch_via_eventkit(
    start_dt: datetime,
    end_dt: datetime,
    calendars: list[str],
) -> list[RangeEvent] | None:
    """EventKit path. Returns None if EventKit is unavailable/unauthorized,
    [] on error, or a list of RangeEvents on success."""
    store = _get_store()
    if not store:
        return None

    try:
        all_cals = store.calendarsForEntityType_(EKEntityTypeEvent)
        target_cals = [c for c in all_cals if c.title() in calendars]
        if not target_cals:
            log.warning(f"None of the target calendars found: {calendars}")
            return []

        ns_start = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
        ns_end = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            ns_start, ns_end, target_cals
        )
        events = store.eventsMatchingPredicate_(predicate)

        out: list[RangeEvent] = []
        for ev in events:
            cal_title = ev.calendar().title() if ev.calendar() else "Unknown"
            attendees: list[str] = []
            if ev.attendees():
                for att in ev.attendees():
                    nm = att.name()
                    if nm:
                        attendees.append(str(nm))
            notes = ""
            try:
                n = ev.notes()
                if n:
                    notes = str(n)
            except Exception:
                pass
            url = ""
            try:
                u = ev.URL()
                if u:
                    url = str(u.absoluteString()) if hasattr(u, "absoluteString") else str(u)
            except Exception:
                pass
            uid = ""
            try:
                ext_id = ev.calendarItemExternalIdentifier()
                if ext_id:
                    uid = str(ext_id)
                else:
                    item_id = ev.calendarItemIdentifier()
                    if item_id:
                        uid = str(item_id)
            except Exception:
                pass

            out.append(RangeEvent(
                title=ev.title() or "(no title)",
                start=datetime.fromtimestamp(ev.startDate().timeIntervalSince1970()),
                end=datetime.fromtimestamp(ev.endDate().timeIntervalSince1970()),
                calendar_name=cal_title,
                location=ev.location() or "",
                notes=notes,
                attendees=attendees,
                all_day=bool(ev.isAllDay()),
                url=url,
                uid=uid,
            ))

        out.sort(key=lambda e: e.start)
        log.info(f"[EventKit] Fetched {len(out)} events from {start_dt.date()} to {end_dt.date()}")
        return out
    except Exception as exc:
        log.error(f"EventKit range fetch failed: {exc}", exc_info=True)
        return []


def _fetch_via_icalpal(
    start_dt: datetime,
    end_dt: datetime,
    calendars: list[str],
) -> list[RangeEvent]:
    """icalPal path. Reads Calendar.app sqlite DB directly, bypassing TCC.
    Parent process needs Full Disk Access."""
    if not ICALPAL_AVAILABLE_IMPORT or not icalpal_available():
        log.debug("icalPal not available (binary missing or import failed)")
        return []

    raw_events = fetch_icalpal_events(start_dt, end_dt, calendars=calendars)
    out: list[RangeEvent] = []
    for row in raw_events:
        out.append(RangeEvent(
            title=row["title"],
            start=row["start"],
            end=row["end"],
            calendar_name=row["calendar_name"],
            location=row["location"],
            notes=row["notes"],
            attendees=row["attendees"],
            all_day=row["all_day"],
            url=row["url"],
            uid=row.get("uid", ""),
        ))
    out.sort(key=lambda e: e.start)
    log.info(f"[icalPal] Fetched {len(out)} events from {start_dt.date()} to {end_dt.date()}")
    return out


def _dedupe_events(events: list[RangeEvent]) -> list[RangeEvent]:
    """Collapse duplicate rows produced when a single event is subscribed to
    via multiple accounts (shared family CalDAV calendars, Gmail auto-events
    syncing to multiple stores) or when icalPal emits per-day expansions of
    the same multi-day all-day event. Prefer UID; fall back to the
    (title, start, end, all_day) tuple."""
    seen: set = set()
    deduped: list[RangeEvent] = []
    for ev in events:
        key = ev.uid or (
            ev.title,
            ev.start.isoformat(),
            ev.end.isoformat(),
            ev.all_day,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ev)
    if len(deduped) != len(events):
        log.info(f"Deduped {len(events) - len(deduped)} duplicate event rows")
    return deduped


def fetch_events_in_range(
    start_dt: datetime,
    end_dt: datetime,
    calendars: list[str] = None,
) -> list[RangeEvent]:
    """
    Fetch events in [start_dt, end_dt] across `calendars`. Defaults to
    INCLUDED_CALENDARS. Captures notes/location/url/attendees.

    Backend selection via THEVAULT_CALENDAR_BACKEND:
        "eventkit"  — EventKit only (error if unauthorized)
        "icalpal"   — icalPal only (requires FDA on parent process)
        "auto"      — try EventKit, fall back to icalPal if it returns None
                      (unauthorized) or [] with no target calendars found
        Default: "auto"
    """
    if calendars is None:
        calendars = INCLUDED_CALENDARS

    backend = CALENDAR_BACKEND

    if backend == "icalpal":
        return _dedupe_events(_fetch_via_icalpal(start_dt, end_dt, calendars))

    if backend == "eventkit":
        result = _fetch_via_eventkit(start_dt, end_dt, calendars)
        return _dedupe_events(result or [])

    # auto: try EventKit first; fall through to icalPal if EK is unauthorized
    # or returned empty AND icalPal is available
    ek_result = _fetch_via_eventkit(start_dt, end_dt, calendars)
    if ek_result is None:
        # EK unavailable/unauthorized — try icalPal
        log.info("EventKit unavailable; trying icalPal fallback")
        return _dedupe_events(_fetch_via_icalpal(start_dt, end_dt, calendars))
    if ek_result:
        return _dedupe_events(ek_result)
    # EK returned [] — could mean TCC denied in sandbox, or legitimately no events.
    # Only fall back to icalPal if it's available, to avoid needless subprocess call.
    if ICALPAL_AVAILABLE_IMPORT and icalpal_available():
        log.info("EventKit returned 0 events; cross-checking with icalPal")
        ical_result = _fetch_via_icalpal(start_dt, end_dt, calendars)
        if ical_result:
            return _dedupe_events(ical_result)
    return _dedupe_events(ek_result)


# ── Event formatter (one line per extraction mode) ───────────────────────────

def _location_text(ev: RangeEvent) -> str:
    # Check location first, then URL field, then notes for VC hints
    loc = ev.location or ""
    vc = detect_vc(loc) or detect_vc(ev.url)
    if vc and vc != "VC URL":
        return f"📍 {vc}"
    if vc == "VC URL":
        return "📍 VC URL: True"
    if loc:
        return f"📍 {loc}"
    # Notes may still carry the VC URL
    notes_vc = detect_vc(ev.notes)
    if notes_vc and notes_vc != "VC URL":
        return f"📍 {notes_vc}"
    if notes_vc == "VC URL":
        return "📍 VC URL: True"
    return ""


def _group_tag(group: str) -> str:
    """Calendar-label suffix placed at the end of each event's head line."""
    return f" _({group})_" if group else ""


def format_event_line(ev: RangeEvent, use_gemma: bool = True) -> str | None:
    """
    Render one event per its calendar's extraction rule. Returns None to skip.

    Layout (Eric's call 2026-04-20): events are mixed across calendars and
    sorted by time within each day. The calendar group appears as an italic
    suffix at the end of the head line: `… · 📍 Zoom _(Eric Personal)_`.
    The leading emoji is preserved as a quick visual tag.
    """
    rule = ev.rule
    mode = rule.get("extract", "title_time")
    if mode == "skip":
        return None

    t = ev.time_str
    title = ev.title
    emoji = rule.get("emoji", "")
    group = rule.get("group", "")

    if mode == "short_title_time":
        return f"- {emoji} **{t}** — {short_class_title(title)}{_group_tag(group)}"

    if mode == "title_time":
        return f"- {emoji} **{t}** — {title}{_group_tag(group)}"

    if mode == "title_time_note":
        notes_text, notes_vc = process_notes(ev.notes, use_gemma=use_gemma)
        line = f"- {emoji} **{t}** — {title}"
        loc = _location_text(ev)
        if loc and len(loc) < 60:
            line += f" · {loc}"
        line += _group_tag(group)
        if notes_text:
            line += f"\n   _{notes_text}_"
        elif notes_vc and not notes_text:
            line += f"\n   _VC URL: True_"
        return line

    # mode == "full" — P0 (Eric's own calendars)
    notes_text, notes_vc = process_notes(ev.notes, use_gemma=use_gemma)
    loc = _location_text(ev)
    head = f"- {emoji} **{t}** — {title}"
    if loc:
        head += f" · {loc}"
    head += _group_tag(group)
    vc_in_header = bool(notes_vc and notes_vc in loc)
    extras: list[str] = []
    if notes_text:
        notes_suffix = ""
        if notes_vc and notes_vc != "VC URL" and not vc_in_header:
            notes_suffix = f" ({notes_vc})"
        elif notes_vc == "VC URL" and not vc_in_header:
            notes_suffix = " (VC URL: True)"
        extras.append(f"   _{notes_text}{notes_suffix}_")
    elif notes_vc and not notes_text and not vc_in_header:
        extras.append(f"   _(VC only)_")
    if ev.attendees:
        names = ev.attendees[:8]
        more = "" if len(ev.attendees) <= 8 else f" +{len(ev.attendees)-8}"
        extras.append(f"   👥 {', '.join(names)}{more}")
    if extras:
        return head + "\n" + "\n".join(extras)
    return head


# ── Gap detection (P0 events within 72h with zero prep mentions) ─────────────

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "with", "for", "to", "in", "on",
    "at", "by", "from", "re", "mtg", "meeting", "call", "sync", "review",
    "update", "standup", "stand-up", "all-hands", "1:1", "1:1s", "session",
}


def _search_terms_for_event(ev: RangeEvent) -> list[str]:
    """
    Build a small set of distinctive search terms from an event's title and
    attendee last names. Stopwords + numbers stripped. Terms lowercased.
    """
    terms: set[str] = set()
    # Title tokens
    title = re.sub(r"[^\w\s-]", " ", ev.title or "")
    for tok in re.split(r"\s+", title):
        t = tok.strip().lower()
        if len(t) >= 4 and t not in _STOPWORDS and not t.isdigit():
            terms.add(t)
    # Attendee last names
    for name in ev.attendees:
        parts = [p for p in re.split(r"\s+", name.strip()) if p]
        if parts:
            last = re.sub(r"[^\w]", "", parts[-1]).lower()
            if len(last) >= 3:
                terms.add(last)
    return sorted(terms)


def detect_prep_gap(
    ev: RangeEvent,
    today: date,
    dly_reader,          # callable: date -> str | None
    lookback_days: int = 14,
    gap_window_hours: int = 72,
) -> bool:
    """
    Return True if:
      - event is within `gap_window_hours` of today, AND
      - event's calendar is P0, AND
      - zero distinctive terms from the event appear in the last
        `lookback_days` DLYs.

    Returns False otherwise (event not close enough / not P0 / prep found).
    """
    if ev.rule.get("priority") != "P0":
        return False
    hours_until = (ev.start - datetime.combine(today, datetime.min.time())).total_seconds() / 3600.0
    if hours_until > gap_window_hours or hours_until < 0:
        return False

    terms = _search_terms_for_event(ev)
    if not terms:
        return False  # nothing distinctive to search for; don't cry wolf

    # Scan the last N DLYs; any single hit clears the gap
    for offset in range(1, lookback_days + 1):
        d = today - timedelta(days=offset)
        content = dly_reader(d)
        if not content:
            continue
        lc = content.lower()
        for term in terms:
            if term in lc:
                return False
    return True  # high-stakes event, no prep mentions anywhere recent


# ── Section renderer: 🎯 Today — Forward-Back (next 14 days) ─────────────────

def render_forward_back_section(
    today: date,
    horizon_days: int = 14,
    gap_window_hours: int = 72,
    use_gemma: bool = True,
    dly_reader=None,
) -> str:
    """
    Render the `## 🎯 Today — Forward-Back` block.

    Events time-sorted within each day (mixed across calendars). Calendar
    label at the end of each line.

    If `dly_reader` is provided, P0 events within `gap_window_hours` get a
    gap-detection check: if no distinctive terms from the event appear in
    the last 14 DLYs, a ⚠️ prep-nudge task is appended under the event.
    """
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today + timedelta(days=horizon_days), datetime.max.time())

    events = fetch_events_in_range(start_dt, end_dt)

    lines: list[str] = [
        "## 🎯 Today — Forward-Back (next 14 days)",
        "<!-- forward-back-start -->",
        "",
        f"_Looking {horizon_days} days ahead → surfacing prep actions for today._",
        "",
    ]

    if not events:
        lines += ["_No events in the next 14 days (or EventKit unavailable)._", ""]
        lines.append("<!-- forward-back-end -->")
        return "\n".join(lines) + "\n"

    # Group by date
    by_date: dict[date, list[RangeEvent]] = {}
    for ev in events:
        by_date.setdefault(ev.start.date(), []).append(ev)

    for d in sorted(by_date.keys()):
        day_events = by_date[d]
        weekday = d.strftime("%a")
        month_day = d.strftime("%b %d")
        if d == today:
            day_label = f"### 🟥 TODAY — {weekday} {month_day}"
        elif (d - today).days <= 3:
            day_label = f"### 🟨 {weekday} {month_day}"
        else:
            day_label = f"### 🟩 {weekday} {month_day}"
        lines.append(day_label)
        lines.append("")

        # Events MIXED across calendars and sorted by start time within the day.
        # Calendar group is shown as a trailing `_(group)_` label on each line.
        rendered: list[str] = []
        for ev in sorted(day_events, key=lambda e: e.start):
            if ev.rule.get("extract") == "skip":
                continue
            line = format_event_line(ev, use_gemma=use_gemma)
            if not line:
                continue
            # Gap detection for P0 events within the 72h window
            if dly_reader is not None:
                try:
                    is_gap = detect_prep_gap(
                        ev, today, dly_reader,
                        lookback_days=14,
                        gap_window_hours=gap_window_hours,
                    )
                except Exception as e:
                    log.debug(f"Gap detection failed for '{ev.title}': {e}")
                    is_gap = False
                if is_gap:
                    gap_note = (
                        f"   ⚠️ **Gap detected** — no prep mentions in last 14 DLYs. "
                        f"- [ ] Block 30 min today to prep 📅 {today.isoformat()}"
                    )
                    line = line + "\n" + gap_note
            rendered.append(line)
        if not rendered:
            # Whole day had nothing renderable — drop the day header
            lines.pop()  # trailing blank
            lines.pop()  # the day header itself
            continue
        lines.extend(rendered)
        lines.append("")

    lines.append("<!-- forward-back-end -->")
    return "\n".join(lines).rstrip() + "\n"


# ── Past 7 Days renderer ─────────────────────────────────────────────────────

def render_past_7_days_section(
    today: date,
    dly_reader,  # callable: date -> str (DLY file content) or None
    wky_path_fn, # callable: date -> Path to the WKY file covering that day
) -> str:
    """
    Render the `## 📅 Past 7 Days` block.

    Each day: `- Weekday MM-DD — entry1 | entry2 | entry3 · [[WKY]]`
    Entries come from that day's DLY in creation order (top-of-file first);
    up to 3 items, each trimmed to ~30 chars.
    """
    lines: list[str] = [
        "## 📅 Past 7 Days",
        "<!-- past-7-start -->",
        "",
    ]

    last_wky_seen = None
    for offset in range(7, 0, -1):
        d = today - timedelta(days=offset)
        content = dly_reader(d)
        entries = _extract_day_entries(content)
        weekday = d.strftime("%a")
        md = d.strftime("%m-%d")

        wky = wky_path_fn(d)
        wky_link = ""
        if wky and wky != last_wky_seen:
            # Display label = "Week NN" extracted from the WKY stem
            m = re.search(r"-W(\d+)", wky.stem)
            label = f"Week {m.group(1)}" if m else wky.stem
            wky_link = f" · [[{wky.stem}|{label}]]"
            last_wky_seen = wky
        body = " | ".join(entries) if entries else "_(no entries)_"
        lines.append(f"- **{weekday} {md}** — {body}{wky_link}")

    lines.append("")
    lines.append("<!-- past-7-end -->")
    return "\n".join(lines) + "\n"


_DAY_SUMMARY_RE = re.compile(
    r"^##+\s+(?:Day Summary|AI Summary|Summary)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CAPTURE_LINE_RE = re.compile(r"^\s*[-*]\s+(.{4,})$")


def _extract_day_entries(dly_content: str | None, max_entries: int = 3, max_chars: int = 30) -> list[str]:
    """
    Pull up to 3 short entries from a DLY. Order: top-of-file first
    (creation order). Sources: Day Summary sentence fragments first,
    then Captures bullets.

    Each entry is trimmed to ~max_chars.
    """
    if not dly_content:
        return []

    entries: list[str] = []

    # 1. Day Summary section → split first sentence on ", " or "; " or "."
    m = _DAY_SUMMARY_RE.search(dly_content)
    if m:
        rest = dly_content[m.end():]
        next_h = re.search(r"\n##+\s", rest)
        chunk = rest[: next_h.start()] if next_h else rest
        # First paragraph
        first_para = chunk.strip().split("\n\n", 1)[0].strip()
        # Split on clause boundaries
        fragments = re.split(r"(?<=[.!?])\s+|;\s+|,\s+(?=[A-Z])", first_para)
        for frag in fragments:
            f = frag.strip().rstrip(".;,")
            if 3 < len(f) < 120:
                entries.append(_trim(f, max_chars))
            if len(entries) >= max_entries:
                return entries

    # 2. Captures section bullets
    cap_match = re.search(r"^##+\s+Captures\s*$(.*?)(?=^##+\s|\Z)", dly_content,
                           re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if cap_match:
        for line in cap_match.group(1).splitlines():
            cm = _CAPTURE_LINE_RE.match(line)
            if cm:
                entries.append(_trim(cm.group(1).strip(), max_chars))
                if len(entries) >= max_entries:
                    break

    return entries[:max_entries]


def _trim(text: str, cap: int) -> str:
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)  # wikilink → label
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)             # bare wikilink
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= cap:
        return text
    return text[:cap].rstrip() + "…"


# ── CLI for quick inspection ─────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Preview 🎯 Today forward-back section")
    parser.add_argument("--date", help="YYYY-MM-DD, default today")
    parser.add_argument("--days", type=int, default=14, help="Horizon days (default 14)")
    parser.add_argument("--no-gemma", action="store_true", help="Hard-truncate notes instead of Gemma4 summary")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    d = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    print(render_forward_back_section(d, horizon_days=args.days, use_gemma=not args.no_gemma))
