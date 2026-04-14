#!/usr/bin/env python3
"""
generate_weekly_summary.py — Weekly (WKY) and Monthly (MTH) Summary Generator

Part D: Weekly summaries — aggregates 7 DLYs + EventKit + vault scan + LLM
Part E: Monthly summaries — aggregates WKY files + calendar stats + LLM

Files written:
    Vault/Daily/YYYY/MM/YYYY-WNN-WKY.md   (weekly)
    Vault/Daily/YYYY/MM/YYYY-MM-MTH.md    (monthly)

Usage:
    python System/Scripts/generate_weekly_summary.py --weekly              # current week
    python System/Scripts/generate_weekly_summary.py --weekly --date 2026-04-13
    python System/Scripts/generate_weekly_summary.py --monthly             # previous month
    python System/Scripts/generate_weekly_summary.py --monthly --date 2026-04-01
    python System/Scripts/generate_weekly_summary.py --dry-run --verbose

Called from: evening_workflow.py (Sunday) and overnight_processor.py (1st of month).
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

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_ROOT = PROJECT_ROOT / "Vault"
DAILY_DIR = VAULT_ROOT / "Daily"

# ── LLM Config ────────────────────────────────────────────────────────────────

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_OLLAMA_MODEL = "gemma4:e4b"
_OLLAMA_URL = "http://localhost:11434/api/chat"

log = logging.getLogger("generate_weekly_summary")


# ── LLM Helpers (Haiku → Ollama fallback) ────────────────────────────────────

def _load_dotenv() -> None:
    env_file = Path.home() / "theVault" / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not os.environ.get(key):
            os.environ[key] = val


def _llm_summarize(prompt: str, max_tokens: int = 512) -> str:
    """Call Haiku, fallback to Ollama. Returns plain text summary."""
    # Try Haiku
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

    # Fallback: Ollama
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
        return result.get("message", {}).get("content", "").strip()
    except Exception as e:
        log.warning(f"Ollama failed: {e}")

    return "_(LLM unavailable — summary not generated)_"


# ── Date Helpers ──────────────────────────────────────────────────────────────

def week_bounds(ref_date: date) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week containing ref_date."""
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def dly_path(d: date) -> Path:
    return DAILY_DIR / str(d.year) / f"{d.month:02d}" / f"{d.strftime('%Y-%m-%d')}-DLY.md"


def wky_path(d: date) -> Path:
    week_num = d.isocalendar()[1]
    return DAILY_DIR / str(d.year) / f"{d.month:02d}" / f"{d.year}-W{week_num:02d}-WKY.md"


def mth_path(year: int, month: int) -> Path:
    return DAILY_DIR / str(year) / f"{month:02d}" / f"{year}-{month:02d}-MTH.md"


# ── DLY Parsing ───────────────────────────────────────────────────────────────

def _read_dly(d: date) -> str:
    p = dly_path(d)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def _extract_tasks(content: str) -> tuple[list[str], list[str]]:
    """Return (completed_tasks, open_tasks) from DLY content."""
    completed, open_tasks = [], []
    for line in content.splitlines():
        if re.match(r"\s*- \[x\]", line, re.IGNORECASE):
            completed.append(line.strip())
        elif re.match(r"\s*- \[ \]", line):
            open_tasks.append(line.strip())
    return completed, open_tasks


def _extract_key_events(content: str) -> list[str]:
    """Extract notable lines from ## Overnight Processing or ## Vault Activity."""
    events: list[str] = []
    in_section = False
    for line in content.splitlines():
        if re.match(r"^#{1,3}\s+(Overnight|Vault Activity)", line):
            in_section = True
            continue
        if in_section and re.match(r"^#{1,3}\s+", line):
            in_section = False
        if in_section and line.strip().startswith("-") and len(line.strip()) > 5:
            events.append(line.strip())
    return events[:5]


def _count_vault_files_in_range(start: date, end: date, subdir: Optional[str] = None) -> int:
    """Count .md files in Vault with mtime in [start, end]."""
    root = VAULT_ROOT / subdir if subdir else VAULT_ROOT
    ts_start = datetime.combine(start, datetime.min.time()).timestamp()
    ts_end = datetime.combine(end, datetime.max.time().replace(microsecond=0)).timestamp()
    count = 0
    for p in root.rglob("*.md"):
        try:
            mtime = p.stat().st_mtime
            if ts_start <= mtime <= ts_end:
                count += 1
        except OSError:
            pass
    return count


def _count_plaud_in_range(start: date, end: date) -> int:
    plaud_dir = VAULT_ROOT / "Notes" / "Plaud"
    if not plaud_dir.exists():
        return 0
    ts_start = datetime.combine(start, datetime.min.time()).timestamp()
    ts_end = datetime.combine(end, datetime.max.time().replace(microsecond=0)).timestamp()
    return sum(
        1 for p in plaud_dir.rglob("*.md")
        if ts_start <= p.stat().st_mtime <= ts_end
    )


# ── Weekly Summary (Part D) ───────────────────────────────────────────────────

def generate_weekly_summary(
    ref_date: date,
    dry_run: bool = False,
    verbose: bool = False,
) -> Optional[Path]:
    """Generate WKY file for the ISO week containing ref_date."""
    monday, sunday = week_bounds(ref_date)
    week_num = ref_date.isocalendar()[1]
    year = monday.year

    output_path = wky_path(ref_date)
    if output_path.exists() and not dry_run:
        log.info(f"WKY already exists: {output_path.name}")

    # Gather data from 7 DLY files
    all_completed: list[str] = []
    all_open: list[str] = []
    all_key_events: list[str] = []
    dly_contents: list[str] = []

    for offset in range(7):
        d = monday + timedelta(days=offset)
        content = _read_dly(d)
        dly_contents.append(content)
        done, open_t = _extract_tasks(content)
        all_completed.extend(done)
        all_open.extend(open_t)
        all_key_events.extend(_extract_key_events(content))

    # Vault activity
    total_notes = _count_vault_files_in_range(monday, sunday)
    plaud_count = _count_plaud_in_range(monday, sunday)

    # Calendar events (via calendar_daily_injector)
    try:
        from calendar_daily_injector import fetch_events_for_date, CALENDAR_GROUPS
        cal_rows: list[str] = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for offset in range(7):
            d = monday + timedelta(days=offset)
            events = fetch_events_for_date(d)
            work = [e.title for e in events if CALENDAR_GROUPS.get(e.calendar_name) == "Work"]
            personal = [e.title for e in events if CALENDAR_GROUPS.get(e.calendar_name) == "Personal"]
            family = [e.title for e in events if CALENDAR_GROUPS.get(e.calendar_name) == "Family"]
            cal_rows.append(
                f"| {day_names[offset]} {d.strftime('%b %-d')} "
                f"| {', '.join(work[:3]) or '—'} "
                f"| {', '.join(personal[:2]) or '—'} "
                f"| {', '.join(family[:2]) or '—'} |"
            )
        cal_table = (
            "| Day | Work Meetings | Personal | Family |\n"
            "|-----|--------------|----------|--------|\n"
            + "\n".join(cal_rows)
        )
    except Exception as exc:
        log.warning(f"Calendar fetch failed: {exc}")
        cal_table = "_Calendar data unavailable_"

    # LLM summary
    combined_text = "\n\n".join(c[:800] for c in dly_contents if c)[:4000]
    if combined_text:
        summary_prompt = (
            f"Write a 3-5 sentence overview of this week (Week {week_num}, "
            f"{monday.strftime('%b %-d')}–{sunday.strftime('%b %-d, %Y')}) "
            f"based on the following daily notes:\n\n{combined_text}"
        )
        llm_summary = _llm_summarize(summary_prompt, max_tokens=200)
    else:
        llm_summary = "_No daily notes found for this week._"

    # Format completed/open tasks (deduplicate)
    seen: set[str] = set()
    unique_completed: list[str] = []
    for t in all_completed:
        if t not in seen:
            seen.add(t)
            unique_completed.append(t)

    unique_open: list[str] = []
    for t in all_open:
        if t not in seen:
            seen.add(t)
            unique_open.append(t)

    # Navigation links
    prev_week_date = monday - timedelta(days=7)
    next_week_date = monday + timedelta(days=7)
    prev_wky = wky_path(prev_week_date)
    next_wky = wky_path(next_week_date)
    prev_link = f"[[Daily/{prev_week_date.year}/{prev_week_date.month:02d}/{prev_wky.stem}|Last Week]]"
    next_link = f"[[Daily/{next_week_date.year}/{next_week_date.month:02d}/{next_wky.stem}|Next Week]]"

    week_label = f"{monday.strftime('%B %-d')}–{sunday.strftime('%-d, %Y')}"

    content = f"""---
date: {monday.isoformat()}
type: weekly-summary
week: {week_num}
year: {year}
tags: [weekly, summary]
---

# Week {week_num} — {week_label}

## Summary
{llm_summary}

## Calendar Overview
{cal_table}

## Vault Activity
- **Notes created:** {total_notes}
- **Plaud transcripts processed:** {plaud_count}

## Tasks

### Completed This Week
{chr(10).join(unique_completed[:20]) or "_None recorded_"}

### Open / Carried Forward
{chr(10).join(unique_open[:20]) or "_None recorded_"}

## Key Events
{chr(10).join(f"- {e}" for e in all_key_events[:10]) or "_None recorded_"}

## Navigation
<< {prev_link} | {next_link} >>
"""

    if verbose:
        print(f"WKY week {week_num}: {total_notes} notes, {len(unique_completed)} completed, {len(unique_open)} open")

    if dry_run:
        print(f"[dry-run] Would write {output_path}")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    log.info(f"✓ Written: {output_path}")
    return output_path


# ── Monthly Summary (Part E) ──────────────────────────────────────────────────

def generate_monthly_summary(
    year: int,
    month: int,
    dry_run: bool = False,
    verbose: bool = False,
) -> Optional[Path]:
    """Generate MTH file for the given year/month."""
    output_path = mth_path(year, month)

    # Find first and last day of month
    from calendar import monthrange
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    # Collect WKY files that overlap with this month
    wky_contents: list[str] = []
    wky_summaries: list[tuple[int, str]] = []  # (week_num, path_stem)

    d = first_day
    seen_weeks: set[int] = set()
    while d <= last_day:
        week_num = d.isocalendar()[1]
        if week_num not in seen_weeks:
            seen_weeks.add(week_num)
            wp = wky_path(d)
            if wp.exists():
                text = wp.read_text(encoding="utf-8")
                wky_contents.append(text)
                wky_summaries.append((week_num, wp.stem))
        d += timedelta(days=7)

    # Overall stats
    total_notes = _count_vault_files_in_range(first_day, last_day)
    plaud_count = _count_plaud_in_range(first_day, last_day)

    # Task rollup across all DLY files in month
    all_completed: list[str] = []
    all_open: list[str] = []
    d = first_day
    while d <= last_day:
        content = _read_dly(d)
        done, open_t = _extract_tasks(content)
        all_completed.extend(done)
        all_open.extend(open_t)
        d += timedelta(days=1)

    seen: set[str] = set()
    unique_completed = [t for t in all_completed if t not in seen and not seen.add(t)]  # type: ignore[func-returns-value]
    unique_open = [t for t in all_open if t not in seen and not seen.add(t)]

    # Weekly rollup table
    week_rows: list[str] = []
    for week_num, stem in wky_summaries:
        wp = DAILY_DIR / str(year) / f"{month:02d}" / f"{stem}.md"
        focus = "—"
        if wp.exists():
            text = wp.read_text(encoding="utf-8")
            m = re.search(r"^## Summary\n(.+)", text, re.MULTILINE)
            if m:
                focus = m.group(1)[:60].strip()
        week_rows.append(f"| W{week_num:02d} | {focus} |")

    week_table = "| Week | Focus |\n|------|-------|\n" + "\n".join(week_rows) if week_rows else "_No weekly summaries available_"

    # LLM summary
    combined = "\n\n---\n\n".join(wky_contents)[:4000]
    month_name = first_day.strftime("%B %Y")
    if combined:
        summary_prompt = (
            f"Write a 4-6 sentence overview of {month_name} based on these weekly summaries. "
            f"Focus on themes, accomplishments, and trajectory:\n\n{combined}"
        )
        llm_summary = _llm_summarize(summary_prompt, max_tokens=300)
    else:
        llm_summary = "_No weekly summaries found — run weekly summaries first._"

    # Navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    prev_stem = f"{prev_year}-{prev_month:02d}-MTH"
    next_stem = f"{next_year}-{next_month:02d}-MTH"
    prev_link = f"[[Daily/{prev_year}/{prev_month:02d}/{prev_stem}|Last Month]]"
    next_link = f"[[Daily/{next_year}/{next_month:02d}/{next_stem}|Next Month]]"

    content = f"""---
date: {first_day.isoformat()}
type: monthly-summary
month: {month}
year: {year}
tags: [monthly, summary]
---

# {month_name}

## Summary
{llm_summary}

## Weekly Rollup
{week_table}

## Vault Growth
- **Notes created:** {total_notes}
- **Plaud transcripts:** {plaud_count}

## Task Throughput
- **Completed:** {len(unique_completed)}
- **Open / carried forward:** {len(unique_open)}

## Navigation
<< {prev_link} | {next_link} >>
"""

    if verbose:
        print(f"MTH {year}-{month:02d}: {total_notes} notes, {len(unique_completed)} completed tasks, {len(wky_summaries)} WKY files aggregated")

    if dry_run:
        print(f"[dry-run] Would write {output_path}")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    log.info(f"✓ Written: {output_path}")
    return output_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    _load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Generate weekly and monthly vault summaries")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--weekly", action="store_true", help="Generate WKY for the week containing --date")
    mode.add_argument("--monthly", action="store_true", help="Generate MTH for the month containing --date")
    parser.add_argument("--date", help="Reference date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    ref = date.fromisoformat(args.date) if args.date else date.today()

    if args.weekly:
        result = generate_weekly_summary(ref, dry_run=args.dry_run, verbose=args.verbose)
        print(f"{'[dry-run] ' if args.dry_run else ''}WKY: {result or '(no write)'}")
    else:
        result = generate_monthly_summary(ref.year, ref.month, dry_run=args.dry_run, verbose=args.verbose)
        print(f"{'[dry-run] ' if args.dry_run else ''}MTH: {result or '(no write)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
