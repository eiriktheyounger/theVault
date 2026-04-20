#!/usr/bin/env python3
"""
generate_rolling_dashboard.py — Rolling Dashboard (past/future unified view)

Phases implemented:
  Phase 1 — Deterministic aggregation (DLY/WKY/MTH parsing, EventKit)
  Phase 2 — LLM synthesis (Haiku→Ollama fallback for week synthesis, key moments, day one-liners)

Output: Vault/Dashboard/Rolling_Dashboard.md

Usage:
    python3 System/Scripts/generate_rolling_dashboard.py [--dry-run] [--verbose] [--no-llm]

Public API:
    from System.Scripts.generate_rolling_dashboard import run_dashboard
    result = run_dashboard(dry_run=False, verbose=False, use_llm=True)
    # returns: {sections_built, events_next_7, key_moments_extracted, wrote_path, errors}
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent  # ~/theVault
VAULT_ROOT = PROJECT_ROOT / "Vault"
DAILY_DIR = VAULT_ROOT / "Daily"
DASHBOARD_DIR = VAULT_ROOT / "Dashboard"
DASHBOARD_FILE = DASHBOARD_DIR / "Rolling_Dashboard.md"
ENV_FILE = PROJECT_ROOT / ".env"

# ── LLM Config ────────────────────────────────────────────────────────────────

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_OLLAMA_MODEL = "gemma4:e4b"
_OLLAMA_URL = "http://localhost:11434/api/chat"

log = logging.getLogger("rolling_dashboard")


# ── Environment ───────────────────────────────────────────────────────────────

def _load_dotenv() -> None:
    if not ENV_FILE.exists():
        return
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not os.environ.get(key):
            os.environ[key] = val


# ── File path helpers ─────────────────────────────────────────────────────────

def dly_path(d: date) -> Path:
    return DAILY_DIR / str(d.year) / f"{d.month:02d}" / f"{d.strftime('%Y-%m-%d')}-DLY.md"


def wky_path_for_date(d: date) -> Path:
    """Return the WKY path for the ISO week containing d."""
    week_num = d.isocalendar()[1]
    # WKY file lives in the month of the Monday of that week
    monday = d - timedelta(days=d.weekday())
    return DAILY_DIR / str(monday.year) / f"{monday.month:02d}" / f"{monday.year}-W{week_num:02d}-WKY.md"


def mth_path(year: int, month: int) -> Path:
    return DAILY_DIR / str(year) / f"{month:02d}" / f"{year}-{month:02d}-MTH.md"


def read_dly(d: date) -> str:
    p = dly_path(d)
    if p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except OSError as e:
            log.warning(f"Could not read DLY {p}: {e}")
    return ""


# ── DLY Section Extractors ───────────────────────────────────────────────────

_SECTION_RE = re.compile(r"^#{1,4}\s+(.+?)\s*$", re.MULTILINE)


def _extract_section(content: str, section_name: str, include_header: bool = False) -> str:
    """Extract content of a markdown section by (partial) header name match."""
    # NOTE: curly-brace regex quantifiers must be double-escaped in f-strings
    # (`{{1,4}}` → `{1,4}`). The original `{1,4}` got evaluated as the Python
    # tuple `(1, 4)` and the pattern silently never matched — a preexisting bug.
    pattern = re.compile(
        rf"^(#{{1,4}})\s+{re.escape(section_name)}\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = pattern.search(content)
    if not m:
        return ""
    level = len(m.group(1))
    # Find end: next heading at same level (sibling) OR HTML end marker.
    # NOTE: we do NOT stop at higher-level (fewer-hash) headings because the
    # DLY format sometimes contains stray H1s like "# Day's Summary" as
    # CONTENT inside an H3 block (emitted by overnight_processor's LLM).
    # Stopping at same-level siblings is the right boundary for our files.
    end_pattern = re.compile(
        rf"^#{{{level}}}\s+|^<!--\s*\w[\w-]*-end\s*-->", re.MULTILINE
    )
    start = m.end()
    next_h = end_pattern.search(content, start)
    chunk = content[start: next_h.start()] if next_h else content[start:]
    chunk = chunk.strip()
    if include_header:
        chunk = m.group(0) + "\n" + chunk
    return chunk


def extract_day_summary(content: str) -> str:
    """Pull the ### Day Summary block verbatim (after overnight processing)."""
    chunk = _extract_section(content, "Day Summary")
    if not chunk:
        return ""
    # Strip interior "# Day Summary" sub-header if present (redundant in the block)
    # Strip any interior "# Day Summary" / "# Day's Summary" content-heading
    # emitted by overnight_processor's LLM output.
    chunk = re.sub(r"^#+ Day'?s? Summary\s*\n?", "", chunk, flags=re.IGNORECASE).strip()
    return chunk


def extract_tasks_extracted(content: str) -> list[str]:
    """Pull task lines from ### Tasks Extracted."""
    chunk = _extract_section(content, "Tasks Extracted")
    if not chunk:
        return []
    tasks: list[str] = []
    for line in chunk.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ["):
            tasks.append(stripped)
    return tasks


def extract_open_tasks_with_due(content: str) -> list[str]:
    """Find all open tasks containing a 📅 YYYY-MM-DD due date."""
    tasks: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]") and "📅" in stripped:
            tasks.append(stripped)
    return tasks


def count_open_tasks(content: str) -> int:
    return sum(1 for l in content.splitlines() if l.strip().startswith("- [ ]"))


def count_completed_tasks(content: str) -> int:
    return sum(1 for l in content.splitlines() if re.match(r"\s*- \[x\]", l, re.IGNORECASE))


def extract_vault_activity_files(content: str) -> int:
    """Count linked files from ## Vault Activity."""
    chunk = _extract_section(content, "Vault Activity")
    return sum(1 for l in chunk.splitlines() if re.match(r"^\s*-\s+\[\[", l))


def first_paragraph(text: str, max_chars: int = 800) -> str:
    """Return the first non-empty paragraph, capped at max_chars."""
    for para in re.split(r"\n\n+", text.strip()):
        p = para.strip()
        if len(p) > 20:
            return p[:max_chars].rstrip() + ("…" if len(p) > max_chars else "")
    return text[:max_chars].strip()


# ── Week / Month file finders ─────────────────────────────────────────────────

def find_last_complete_wky(today: date) -> Optional[Path]:
    """Return the WKY file for the most recent fully-complete ISO week."""
    # Last Sunday = most recent week end
    # "Last complete week" = the Mon–Sun block that ended before this Monday
    this_monday = today - timedelta(days=today.weekday())
    last_sunday = this_monday - timedelta(days=1)
    p = wky_path_for_date(last_sunday)
    if p.exists():
        return p
    # Try one more week back
    prev_sunday = last_sunday - timedelta(days=7)
    p2 = wky_path_for_date(prev_sunday)
    if p2.exists():
        return p2
    return None


def find_last_complete_mth(today: date) -> Optional[Path]:
    """Return the MTH file for the most recently completed month."""
    # Previous month
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1
    p = mth_path(year, month)
    if p.exists():
        return p
    # Two months back
    if month == 1:
        year2, month2 = year - 1, 12
    else:
        year2, month2 = year, month - 1
    p2 = mth_path(year2, month2)
    if p2.exists():
        return p2
    return None


# ── Calendar: EventKit via calendar_forward_back ─────────────────────────────

def fetch_forward_events(today: date, days: int) -> list:
    """
    Fetch events in [today, today+days]. Returns list of RangeEvent or [].
    Gracefully returns [] if EventKit is unavailable (CI / sandbox).
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "System" / "Scripts"))
        from calendar_forward_back import fetch_events_in_range
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(today + timedelta(days=days), datetime.max.time())
        events = fetch_events_in_range(start_dt, end_dt)
        return events
    except Exception as e:
        log.debug(f"EventKit unavailable: {e}")
        return []


def format_event_for_dashboard(ev) -> str:
    """Render a single RangeEvent as a dashboard bullet line."""
    try:
        from calendar_forward_back import format_event_line
        line = format_event_line(ev, use_gemma=False)
        if line:
            return line
    except Exception:
        pass
    # Fallback if import or format fails
    t = ev.start.strftime("%H:%M") if hasattr(ev, "start") else "?"
    title = getattr(ev, "title", str(ev))
    cal = getattr(ev, "calendar_name", "")
    return f"- **{t}** — {title} _({cal})_"


# ── Open tasks due in next 7 days (scan recent DLYs) ─────────────────────────

def collect_upcoming_tasks(today: date, days_ahead: int = 7) -> list[tuple[str, str]]:
    """
    Scan past 14 DLYs (plus today) for open tasks due within the next `days_ahead` days.
    Returns list of (due_date_str, task_text).
    """
    window_end = today + timedelta(days=days_ahead)
    due_re = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    for offset in range(-1, 15):  # today + recent 14 days
        d = today - timedelta(days=offset)
        content = read_dly(d)
        if not content:
            continue
        for task in extract_open_tasks_with_due(content):
            m = due_re.search(task)
            if not m:
                continue
            try:
                due = date.fromisoformat(m.group(1))
            except ValueError:
                continue
            if today <= due <= window_end:
                key = task[:120]
                if key not in seen:
                    seen.add(key)
                    results.append((m.group(1), task))

    results.sort(key=lambda x: x[0])
    return results


# ── Open task count (aggregate across recent DLYs) ───────────────────────────

def count_all_open_tasks(today: date, lookback: int = 30) -> tuple[int, int]:
    """
    Scan DLYs for the last `lookback` days. Returns (total_open, overdue_count).
    Deduplicates by task text prefix.
    """
    due_re = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
    seen_tasks: set[str] = set()
    total = 0
    overdue = 0

    for offset in range(lookback):
        d = today - timedelta(days=offset)
        content = read_dly(d)
        if not content:
            continue
        for task in extract_open_tasks_with_due(content):
            key = task[:120]
            if key in seen_tasks:
                continue
            seen_tasks.add(key)
            total += 1
            m = due_re.search(task)
            if m:
                try:
                    due = date.fromisoformat(m.group(1))
                    if due < today:
                        overdue += 1
                except ValueError:
                    pass

    return total, overdue


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _llm_call(prompt: str, max_tokens: int = 400, use_llm: bool = True) -> str:
    """Haiku → Ollama → placeholder."""
    if not use_llm:
        return "_[LLM disabled — run without --no-llm for synthesis]_"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            log.warning(f"Haiku failed: {e}, trying Ollama")

    # Ollama fallback
    try:
        payload = json.dumps({
            "model": _OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            _OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        text = result.get("message", {}).get("content", "").strip()
        # Strip Ollama/Gemma thinking tags
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        return text
    except Exception as e:
        log.warning(f"Ollama failed: {e}")

    return "_[LLM unavailable — synthesis not generated]_"


def _llm_json_call(prompt: str, max_tokens: int = 600, use_llm: bool = True) -> Optional[list]:
    """Haiku → Ollama → None. Returns parsed JSON list or None."""
    if not use_llm:
        return None

    raw = _llm_call(prompt, max_tokens=max_tokens, use_llm=use_llm)
    if raw.startswith("_["):
        return None

    # Strip markdown fences
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "moments" in parsed:
            return parsed["moments"]
    except json.JSONDecodeError:
        log.debug(f"JSON parse failed on LLM output: {text[:200]!r}")
    return None


# ── LLM Synthesis builders ────────────────────────────────────────────────────

def build_week_synthesis(dly_summaries: list[tuple[str, str]], use_llm: bool = True) -> str:
    """Generate 3-5 sentence week-so-far synthesis from DLY summaries."""
    if not dly_summaries:
        return "_No daily summaries available for synthesis._"
    context_parts = []
    for d_str, summary in dly_summaries:
        if summary:
            context_parts.append(f"**{d_str}**: {summary[:600]}")
    if not context_parts:
        return "_No content found in daily summaries._"
    combined = "\n\n".join(context_parts)
    prompt = (
        "You are summarizing the past week for a personal knowledge system. "
        "Write a 3-5 sentence synthesis of what happened this week based on these daily notes. "
        "Be specific and concrete. Focus on decisions, progress, and notable moments. "
        "Do not use generic filler. No preamble — start directly with the summary.\n\n"
        f"Daily notes:\n{combined[:3000]}"
    )
    return _llm_call(prompt, max_tokens=250, use_llm=use_llm)


def build_key_moments(context_text: str, label: str, use_llm: bool = True) -> list[dict]:
    """
    Extract up to 5 key moments from context_text.
    Returns list of {date, moment} dicts.
    """
    if not context_text.strip():
        return []
    prompt = (
        f"Extract up to 5 key moments from these {label} notes. "
        "Key moments = decisions made, breakthroughs, major events, notable conversations, or starts/completions. "
        "Return a JSON array where each item has keys 'date' (YYYY-MM-DD or 'unknown') and 'moment' (one sentence). "
        "Return ONLY valid JSON array. No markdown fences, no extra text.\n\n"
        f"Notes:\n{context_text[:4000]}"
    )
    items = _llm_json_call(prompt, max_tokens=500, use_llm=use_llm)
    if items is None:
        return []
    out = []
    for item in items:
        if isinstance(item, dict) and "moment" in item:
            out.append({"date": item.get("date", "unknown"), "moment": item["moment"]})
    return out[:5]


def build_day_oneliners(dly_summaries: list[tuple[str, str]], use_llm: bool = True) -> dict[str, str]:
    """
    For each day, produce a single sentence one-liner.
    If LLM is off, return first sentence of each Day Summary.
    Returns {date_str: one_liner}.
    """
    if not use_llm:
        result = {}
        for d_str, summary in dly_summaries:
            if summary:
                # First sentence
                first = re.split(r"(?<=[.!?])\s+", summary.strip(), maxsplit=1)[0].strip()
                result[d_str] = first[:120] if first else "_No summary_"
            else:
                result[d_str] = "_No summary_"
        return result

    items_text = "\n".join(
        f"- {d_str}: {summ[:400]}" for d_str, summ in dly_summaries if summ
    )
    if not items_text:
        return {d: "_No summary_" for d, _ in dly_summaries}

    prompt = (
        "For each date below, write ONE sentence (max 20 words) capturing the most important thing that happened. "
        "Return a JSON array where each item has keys 'date' (YYYY-MM-DD) and 'oneliner' (the sentence). "
        "Return ONLY valid JSON array. No markdown fences, no extra text.\n\n"
        f"Daily summaries:\n{items_text[:3000]}"
    )
    items = _llm_json_call(prompt, max_tokens=600, use_llm=use_llm)
    fallback = {}
    for d_str, summ in dly_summaries:
        first = re.split(r"(?<=[.!?])\s+", summ.strip(), maxsplit=1)[0].strip() if summ else ""
        fallback[d_str] = first[:120] if first else "_No summary_"

    if not items:
        return fallback

    result = dict(fallback)  # start with fallbacks
    for item in items:
        if isinstance(item, dict) and "date" in item and "oneliner" in item:
            result[item["date"]] = item["oneliner"]
    return result


# ── Section Renderers ─────────────────────────────────────────────────────────

def render_next_7_days(today: date, errors: list[str]) -> tuple[str, int]:
    """Build ## Next 7 Days section. Returns (markdown, event_count)."""
    lines = [
        f"## 🔮 Next 7 Days — {today.strftime('%b %d')} to {(today + timedelta(days=6)).strftime('%b %d, %Y')}",
        "",
    ]

    # Confirmed events
    events = fetch_forward_events(today, days=7)
    if events:
        lines.append("### Confirmed Events")
        lines.append("")
        by_date: dict[date, list] = {}
        for ev in events:
            by_date.setdefault(ev.start.date(), []).append(ev)
        for d in sorted(by_date.keys()):
            lines.append(f"**{d.strftime('%a %b %d')}**")
            for ev in sorted(by_date[d], key=lambda e: e.start):
                lines.append(format_event_for_dashboard(ev))
            lines.append("")
    else:
        lines.append("### Confirmed Events")
        lines.append("")
        lines.append("_Calendar unavailable in this environment — events not loaded._")
        lines.append("")

    # Open tasks due this window
    upcoming_tasks = collect_upcoming_tasks(today, days_ahead=7)
    lines.append("### Open Tasks Due This Window")
    lines.append("")
    if upcoming_tasks:
        for due_str, task in upcoming_tasks:
            lines.append(task)
    else:
        lines.append("_No open tasks with due dates in next 7 days._")
    lines.append("")

    # Coming up further out (next 30 days)
    far_events = fetch_forward_events(today + timedelta(days=8), days=22)
    lines.append("### Coming Up Further Out (next 30 days, key items only)")
    lines.append("")
    if far_events:
        for ev in far_events[:10]:
            d_str = ev.start.strftime("%b %d")
            title = getattr(ev, "title", str(ev))
            cal = getattr(ev, "calendar_name", "")
            lines.append(f"- **{d_str}** — {title} _({cal})_")
    else:
        lines.append("_Calendar unavailable — far-out events not loaded._")
    lines.append("")

    return "\n".join(lines), len(events)


def render_today_summary(today: date, errors: list[str]) -> str:
    """Build ## Today section — narrative summary only.

    Shows today's Day Summary if overnight has already run; otherwise falls
    back to the most recent prior day that has one. Tasks and calendar are
    intentionally NOT included here — those live on the DLY.
    """
    weekday = today.strftime("%A")
    header = f"## 📅 Today — {weekday}, {today.strftime('%b %d, %Y')}"
    lines = [header, ""]

    # Try today first, then walk backward up to 7 days to find the most recent
    # day summary (handles mornings before overnight has processed yesterday).
    chosen_date: Optional[date] = None
    chosen_summary = ""
    for offset in range(0, 8):
        d = today - timedelta(days=offset)
        content = read_dly(d)
        summary = extract_day_summary(content) if content else ""
        if summary:
            chosen_date = d
            chosen_summary = summary
            break

    if chosen_summary and chosen_date is not None:
        if chosen_date == today:
            prefix = "_Today's summary (from tonight's overnight processing):_"
        else:
            days_back = (today - chosen_date).days
            if days_back == 1:
                prefix = "_Yesterday's summary (most recent completed day):_"
            else:
                prefix = f"_Most recent completed day — {chosen_date.isoformat()} ({days_back} days ago):_"
        lines.append(prefix)
        lines.append("")
        lines.append(chosen_summary)
        lines.append("")
        stem = f"Daily/{chosen_date.year}/{chosen_date.month:02d}/{chosen_date.isoformat()}-DLY"
        lines.append(f"[[{stem}|Full day note →]]")
    else:
        lines.append("_No day summary available in the last 7 days._")
        lines.append("_(Day Summary is generated nightly by `overnight_processor.py` at 10 PM.)_")

    lines.append("")
    return "\n".join(lines)


def render_this_week_so_far(today: date, use_llm: bool, errors: list[str]) -> tuple[str, int]:
    """Build ## This Week So Far section. Returns (markdown, key_moments_count)."""
    lines = [
        f"## 📅 This Week So Far — {(today - timedelta(days=today.weekday())).strftime('%b %d')} to {today.strftime('%b %d, %Y')}",
        "",
    ]

    # Gather last 7 DLYs
    dly_data: list[tuple[str, str, str]] = []  # (date_str, day_summary, raw_content)
    for offset in range(6, -1, -1):
        d = today - timedelta(days=offset)
        content = read_dly(d)
        summary = extract_day_summary(content)
        dly_data.append((d.isoformat(), summary, content))

    # Week synthesis
    summaries = [(d, s) for d, s, _ in dly_data]
    synthesis = build_week_synthesis([(d, s) for d, s in summaries if s], use_llm=use_llm)
    lines.append(synthesis)
    lines.append("")

    # Key moments
    all_summaries_text = "\n\n".join(
        f"[{d}] {s}" for d, s, _ in dly_data if s
    )
    moments = build_key_moments(all_summaries_text, "this-week-so-far", use_llm=use_llm)
    lines.append("### Key Moments")
    lines.append("")
    if moments:
        for m in moments:
            d_str = m.get("date", "unknown")
            moment_text = m.get("moment", "")
            dly_link = ""
            if re.match(r"\d{4}-\d{2}-\d{2}", d_str):
                try:
                    d_obj = date.fromisoformat(d_str)
                    stem = f"Daily/{d_obj.year}/{d_obj.month:02d}/{d_str}-DLY"
                    dly_link = f" [[{stem}|DLY]]"
                except ValueError:
                    pass
            lines.append(f"- **{d_str}** — {moment_text}{dly_link}")
    else:
        lines.append("_No key moments extracted._")
    lines.append("")

    # Day-by-day one-liners
    oneliners = build_day_oneliners([(d, s) for d, s, _ in dly_data], use_llm=use_llm)
    lines.append("### Day-by-Day (last 7 days)")
    lines.append("")
    for d_str, _, raw in dly_data:
        d_obj = date.fromisoformat(d_str)
        weekday = d_obj.strftime("%a")
        oneliner = oneliners.get(d_str, "_No summary_")
        task_count = count_open_tasks(raw)
        vault_files = extract_vault_activity_files(raw)
        stem = f"Daily/{d_obj.year}/{d_obj.month:02d}/{d_str}-DLY"
        meta = f"{task_count} open tasks · {vault_files} vault files"
        lines.append(f"- **{weekday} {d_str}** — {oneliner} · {meta} · [[{stem}|DLY]]")
    lines.append("")

    return "\n".join(lines), len(moments)


def render_last_full_week(today: date, errors: list[str]) -> str:
    """Build ## Last Full Week section."""
    wky = find_last_complete_wky(today)

    # Determine week bounds for header
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = last_monday + timedelta(days=6)
    week_num = last_monday.isocalendar()[1]
    date_range = f"{last_monday.strftime('%b %d')}–{last_sunday.strftime('%b %d, %Y')}"

    lines = [
        f"## 📆 Last Full Week — Week {week_num}, {date_range}",
        "",
    ]

    if wky and wky.exists():
        try:
            wky_content = wky.read_text(encoding="utf-8")
            # Pull the first substantive section (skip frontmatter)
            # Strip YAML frontmatter
            body = re.sub(r"^---.*?---\s*", "", wky_content, flags=re.DOTALL).strip()
            # Use first ~1200 chars (verbatim as plan specifies)
            excerpt = body[:1200].strip()
            if len(body) > 1200:
                excerpt += "\n\n_…[truncated — see full file]_"
            lines.append(excerpt)
        except OSError as e:
            errors.append(f"WKY read failed: {e}")
            lines.append("_Could not read weekly summary file._")
        lines.append("")
        lines.append(f"[[{wky.stem}|Full weekly summary →]]")
    else:
        lines.append("_No weekly summary file found for last week._")
        lines.append("_(WKY file is generated on Sundays by the evening workflow.)_")

    lines.append("")
    return "\n".join(lines)


def render_last_full_month(today: date, use_llm: bool, errors: list[str]) -> tuple[str, int]:
    """Build ## Last Full Month section. Returns (markdown, key_moments_count)."""
    # Determine previous month
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1
    import calendar
    month_name = calendar.month_name[month]

    lines = [
        f"## 🗓️ Last Full Month — {month_name} {year}",
        "",
    ]

    mth = find_last_complete_mth(today)
    key_moments_count = 0

    if mth and mth.exists():
        try:
            mth_content = mth.read_text(encoding="utf-8")
            body = re.sub(r"^---.*?---\s*", "", mth_content, flags=re.DOTALL).strip()
            excerpt = body[:1500].strip()
            if len(body) > 1500:
                excerpt += "\n\n_…[truncated — see full file]_"
            lines.append(excerpt)
        except OSError as e:
            errors.append(f"MTH read failed: {e}")
            lines.append("_Could not read monthly summary file._")
            mth_content = ""
    else:
        lines.append("_No monthly summary file found for last month._")
        lines.append("_(MTH file is generated on the 1st of each month by the overnight processor.)_")
        mth_content = ""

    lines.append("")

    # Eric's 2026-04-20 spec: summary-only. Key-moments extraction removed.
    if mth:
        lines.append(f"[[{mth.stem}|Full monthly summary →]]")
    lines.append("")

    return "\n".join(lines), key_moments_count


def render_at_a_glance(today: date, errors: list[str]) -> str:
    """Build ## At a Glance section (Phase 1: open task count only)."""
    lines = [
        "## 📊 At a Glance",
        "",
    ]

    total, overdue = count_all_open_tasks(today, lookback=30)
    if total > 0:
        lines.append(f"- **Open tasks**: {total} ({overdue} overdue)")
    else:
        lines.append("- **Open tasks**: _no data (task scan covers last 30 DLY files)_")

    # Phase 3 stubs — populated in a later phase
    lines.append("- **Active projects**: _see project_priorities_2026_03.md_")
    lines.append("- **Active job applications**: _Phase 3_")
    lines.append("- **Last RAG index rebuild**: _Phase 3_")
    lines.append("")

    return "\n".join(lines)


# ── Main assembler ────────────────────────────────────────────────────────────

def assemble_dashboard(
    today: date,
    dry_run: bool = False,
    verbose: bool = False,
    use_llm: bool = True,
) -> dict:
    """Build all sections and assemble the final markdown."""
    errors: list[str] = []
    sections_built = 0
    total_key_moments = 0

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    header_lines = [
        f"# Rolling Dashboard — {today.isoformat()}",
        "",
        f"> Auto-generated. Last update: {ts}. "
        f"Regen with `python3 System/Scripts/generate_rolling_dashboard.py`.",
        "",
        "---",
        "",
    ]

    # Eric's 2026-04-20 spec: narrative-only dashboard, 3 sections.
    # Tasks + calendar deliberately NOT on the dashboard (they live on the DLY).

    # Section 1: Today
    log.info("Building: Today")
    today_md = render_today_summary(today, errors)
    sections_built += 1

    # Section 2: Last Full Week
    log.info("Building: Last Full Week")
    last_week_md = render_last_full_week(today, errors)
    sections_built += 1

    # Section 3: Last Full Month
    log.info("Building: Last Full Month")
    last_month_md, _ = render_last_full_month(today, use_llm=use_llm, errors=errors)
    sections_built += 1

    separator = "\n---\n\n"
    full_md = (
        "\n".join(header_lines)
        + today_md + separator
        + last_week_md + separator
        + last_month_md
        + "\n<!-- rolling-dashboard-end -->\n"
    )

    if errors:
        log.warning(f"Completed with {len(errors)} error(s): {errors}")

    return {
        "markdown": full_md,
        "sections_built": sections_built,
        "events_next_7": 0,  # retired — tasks/calendar moved to DLY only
        "key_moments_extracted": total_key_moments,
        "errors": errors,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def run_dashboard(
    dry_run: bool = False,
    verbose: bool = False,
    use_llm: bool = True,
    ref_date: Optional[date] = None,
) -> dict:
    """
    Build the rolling dashboard. Returns result dict.

    Keys: sections_built, events_next_7, key_moments_extracted, wrote_path, errors
    """
    _load_dotenv()
    today = ref_date or date.today()

    result = assemble_dashboard(today, dry_run=dry_run, verbose=verbose, use_llm=use_llm)
    markdown = result.pop("markdown")

    if dry_run:
        print(markdown)
        result["wrote_path"] = "(dry-run — not written)"
        return result

    # Ensure output directory exists
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        DASHBOARD_FILE.write_text(markdown, encoding="utf-8")
        result["wrote_path"] = str(DASHBOARD_FILE)
        log.info(f"Dashboard written to {DASHBOARD_FILE}")
    except OSError as e:
        result["errors"].append(f"Write failed: {e}")
        result["wrote_path"] = f"(write failed: {e})"

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the theVault rolling dashboard (Phase 1+2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print assembled dashboard to stdout without writing to disk",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM calls — use deterministic fallbacks for synthesis sections",
    )
    parser.add_argument(
        "--date",
        help="Reference date (YYYY-MM-DD). Default: today.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    ref_date: Optional[date] = None
    if args.date:
        try:
            ref_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"ERROR: invalid --date format: {args.date!r} (expected YYYY-MM-DD)", file=sys.stderr)
            sys.exit(1)

    result = run_dashboard(
        dry_run=args.dry_run,
        verbose=args.verbose,
        use_llm=not args.no_llm,
        ref_date=ref_date,
    )

    if not args.dry_run:
        print(f"Dashboard written: {result['wrote_path']}")
        print(f"Sections built:    {result['sections_built']}")
        print(f"Events (next 7d):  {result['events_next_7']}")
        print(f"Key moments:       {result['key_moments_extracted']}")
        if result["errors"]:
            print(f"Errors: {result['errors']}", file=sys.stderr)
            sys.exit(1)
    else:
        # dry-run: markdown already printed by run_dashboard; print stats to stderr
        print(f"\n--- DRY RUN STATS ---", file=sys.stderr)
        print(f"Sections built:    {result['sections_built']}", file=sys.stderr)
        print(f"Events (next 7d):  {result['events_next_7']}", file=sys.stderr)
        print(f"Key moments:       {result['key_moments_extracted']}", file=sys.stderr)
        if result["errors"]:
            print(f"Errors: {result['errors']}", file=sys.stderr)


if __name__ == "__main__":
    main()
