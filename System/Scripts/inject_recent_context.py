#!/usr/bin/env python3
"""
inject_recent_context.py — Inject temporal-context sections into today's DLY.

Injects THREE sections (in this top-to-bottom order), each independently
idempotent via its own marker pair:

  1. ## 🎯 Today — Forward-Back (next 14 days)    [forward-back-start/end]
  2. ## 📅 Past 7 Days                              [past-7-start/end]
  3. ## Recent Context (last week + last month)    [recent-context-start/end]

Placement: before the first of ## Captures, ## Email Activity,
## Vault Activity, ## Navigation.

Each section is built by its own function; a section that fails (e.g.,
EventKit unavailable) leaves the others unaffected.

ADHD/OOSOOM-first design:
  Forward prep, rolling week, and last-completed-period context live
  INLINE in the daily note Eric opens every morning — not hidden behind
  Obsidian backlinks.

What gets injected:
  ## Recent Context
  <!-- recent-context-start -->

  ### 📆 Last Week — W{NN} ({monday} → {sunday})
  {one-paragraph compressed summary extracted from the WKY file, or the
   file's `## Summary` section verbatim if short, or a fallback message
   "(weekly summary not yet generated — runs Sunday evening)"}

  ### 🗓️ Last Month — {Month YYYY}
  {one-paragraph compressed summary extracted from the MTH file, or the
   file's `## Summary` section verbatim if short, or a fallback message
   "(monthly summary not yet generated — runs on the 1st)"}

  <!-- recent-context-end -->

Idempotent: safe to run repeatedly. The second run replaces the block rather
than appending a duplicate.

Sources (read-only):
  - Vault/Daily/YYYY/MM/YYYY-WNN-WKY.md  — previous ISO week
  - Vault/Daily/YYYY/MM/YYYY-MM-MTH.md   — previous calendar month

Does NOT generate WKY/MTH content — that's owned by generate_weekly_summary.py.
This script only compresses and injects what already exists.

Usage:
    python System/Scripts/inject_recent_context.py                # today
    python System/Scripts/inject_recent_context.py --date 2026-04-19
    python System/Scripts/inject_recent_context.py --dry-run --verbose

Called from: overnight_processor.py (end of run) and morning_workflow.py
(step 1, before Eric opens the DLY).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Sibling import for calendar forward-back + past-7-days renderers.
# Tolerated-missing so this script still runs (with degraded output) if the
# calendar module is absent or broken.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
try:
    import calendar_forward_back as _cfb  # type: ignore
except Exception as _cfb_err:  # pragma: no cover
    _cfb = None
    _cfb_import_err = _cfb_err

# ── Paths ─────────────────────────────────────────────────────────────────────
VAULT_ROOT = Path(os.environ.get("VAULT_ROOT", Path.home() / "theVault"))
DAILY_DIR = VAULT_ROOT / "Vault" / "Daily"

# ── Section markers (ADHD-inline, idempotent) ────────────────────────────────
_SECTION_HEADER = "## Recent Context"
_START_MARKER = "<!-- recent-context-start -->"
_END_MARKER = "<!-- recent-context-end -->"

# Match the whole block including header + markers, up to end marker OR next
# top-level `##` heading (defensive against a stripped end-marker).
_SECTION_RE = re.compile(
    r"## Recent Context\n<!-- recent-context-start -->.*?<!-- recent-context-end -->\n?",
    re.DOTALL,
)
_FALLBACK_SECTION_RE = re.compile(
    r"## Recent Context\n.*?(?=\n## |\Z)",
    re.DOTALL,
)

# Compression: take ~first N chars of the Summary section, or the first
# 3-4 sentences, whichever yields a readable paragraph. Long WKY/MTH summaries
# run multi-paragraph; we want the top.
MAX_SUMMARY_CHARS = 900  # ~150-170 words; fits above-the-fold in Obsidian

log = logging.getLogger("inject_recent_context")


# ── Path helpers ──────────────────────────────────────────────────────────────

def dly_path(d: date) -> Path:
    return DAILY_DIR / str(d.year) / f"{d.month:02d}" / f"{d.strftime('%Y-%m-%d')}-DLY.md"


def previous_week_wky_path(today: date) -> tuple[Path, int, date, date]:
    """
    Return (path, week_num, monday, sunday) for the ISO week BEFORE `today`'s week.
    Eric explicitly wants last COMPLETED week, not in-progress.
    """
    # Monday of this week
    this_monday = today - timedelta(days=today.weekday())
    # Monday/Sunday of previous week
    prev_monday = this_monday - timedelta(days=7)
    prev_sunday = prev_monday + timedelta(days=6)
    week_num = prev_monday.isocalendar()[1]
    # WKY file lives under the month of the ISO-week anchor. generate_weekly_summary
    # uses the reference date's year/month. We follow the same convention by placing
    # it under the Monday's year/month (which matches the generator's output).
    path = DAILY_DIR / str(prev_monday.year) / f"{prev_monday.month:02d}" / f"{prev_monday.year}-W{week_num:02d}-WKY.md"
    return path, week_num, prev_monday, prev_sunday


def previous_month_mth_path(today: date) -> tuple[Path, int, int]:
    """
    Return (path, year, month) for the calendar month BEFORE `today`'s month.
    """
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1
    path = DAILY_DIR / str(year) / f"{month:02d}" / f"{year}-{month:02d}-MTH.md"
    return path, year, month


# ── Content extraction ────────────────────────────────────────────────────────

_SUMMARY_HEADING_RE = re.compile(
    r"^##\s+(Summary|AI Summary|Narrative|Highlights)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter if present."""
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            return content[end + 5:]
    return content


def _extract_summary(content: str) -> str | None:
    """
    Pull the first summary-like section from a WKY/MTH file. Tolerant of
    variations: `## Summary`, `## AI Summary`, `## Narrative`, `## Highlights`.
    Falls back to the first non-empty paragraph after frontmatter if no heading
    matches.
    """
    body = _strip_frontmatter(content)
    m = _SUMMARY_HEADING_RE.search(body)
    if m:
        start = m.end()
        # Read until the next `## ` heading or end of file
        rest = body[start:]
        next_h = re.search(r"\n## ", rest)
        chunk = rest[: next_h.start()] if next_h else rest
        return chunk.strip() or None

    # Fallback: first prose paragraph (skip `# Title` line)
    lines = [ln for ln in body.splitlines() if ln.strip()]
    prose = []
    for ln in lines:
        if ln.startswith("#"):
            continue
        if ln.startswith("<!--") or ln.startswith("|") or ln.startswith("-"):
            continue
        prose.append(ln)
        # Gather up to a blank-line worth of paragraph
        if len(" ".join(prose)) > 200:
            break
    return " ".join(prose).strip() or None


def _compress(text: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """Trim to ~max_chars at a sentence boundary when possible."""
    if len(text) <= max_chars:
        return text
    # Find last sentence-ending punctuation before the cap
    window = text[:max_chars]
    for punct in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
        idx = window.rfind(punct)
        if idx > max_chars * 0.5:
            return window[: idx + 1].rstrip() + " …"
    # Otherwise hard-cut at cap with ellipsis
    return window.rstrip() + " …"


def _read_if_exists(path: Path) -> str | None:
    try:
        if path.exists() and path.stat().st_size > 0:
            return path.read_text(encoding="utf-8")
    except OSError as e:
        log.warning(f"  Could not read {path}: {e}")
    return None


# ── Section builder ───────────────────────────────────────────────────────────

def _build_week_block(today: date) -> str:
    path, week_num, monday, sunday = previous_week_wky_path(today)
    content = _read_if_exists(path)
    heading = f"### 📆 Last Week — W{week_num:02d} ({monday.isoformat()} → {sunday.isoformat()})"
    link = f"[[{path.stem}|Full weekly summary]]"

    if content is None:
        body = "_(weekly summary not yet generated — runs Sunday evening via `evening_workflow.py` → `generate_weekly_summary.py --weekly`)_"
        return f"{heading}\n\n{body}\n"

    summary = _extract_summary(content)
    if not summary:
        body = f"_(weekly file exists but no `## Summary` section found — see {link})_"
        return f"{heading}\n\n{body}\n"

    return f"{heading}\n\n{_compress(summary)}\n\n{link}\n"


def _build_month_block(today: date) -> str:
    path, year, month = previous_month_mth_path(today)
    month_name = datetime(year, month, 1).strftime("%B %Y")
    content = _read_if_exists(path)
    heading = f"### 🗓️ Last Month — {month_name}"
    link = f"[[{path.stem}|Full monthly summary]]"

    if content is None:
        body = "_(monthly summary not yet generated — runs on the 1st via `overnight_processor.py` → `generate_weekly_summary.py --monthly`)_"
        return f"{heading}\n\n{body}\n"

    summary = _extract_summary(content)
    if not summary:
        body = f"_(monthly file exists but no `## Summary` section found — see {link})_"
        return f"{heading}\n\n{body}\n"

    return f"{heading}\n\n{_compress(summary)}\n\n{link}\n"


def _build_section(today: date) -> str:
    parts = [
        _SECTION_HEADER,
        _START_MARKER,
        "",
        _build_week_block(today),
        _build_month_block(today),
        _END_MARKER,
    ]
    return "\n".join(parts).rstrip() + "\n"


# ── Forward-Back (14 days) + Past 7 Days builders ────────────────────────────

_FB_HEADER = "## 🎯 Today — Forward-Back (next 14 days)"
_FB_START = "<!-- forward-back-start -->"
_FB_END = "<!-- forward-back-end -->"
_FB_RE = re.compile(
    r"## 🎯 Today — Forward-Back \(next 14 days\)\n<!-- forward-back-start -->.*?<!-- forward-back-end -->\n?",
    re.DOTALL,
)
_FB_FALLBACK_RE = re.compile(
    r"## 🎯 Today — Forward-Back[^\n]*\n.*?(?=\n## |\Z)",
    re.DOTALL,
)

_P7_HEADER = "## 📅 Past 7 Days"
_P7_START = "<!-- past-7-start -->"
_P7_END = "<!-- past-7-end -->"
_P7_RE = re.compile(
    r"## 📅 Past 7 Days\n<!-- past-7-start -->.*?<!-- past-7-end -->\n?",
    re.DOTALL,
)
_P7_FALLBACK_RE = re.compile(
    r"## 📅 Past 7 Days\n.*?(?=\n## |\Z)",
    re.DOTALL,
)


def _build_forward_back(today: date, use_gemma: bool = True) -> str:
    """Render the 🎯 section via calendar_forward_back. Fails soft."""
    if _cfb is None:
        return (
            f"{_FB_HEADER}\n{_FB_START}\n\n"
            f"_(calendar module unavailable: {_cfb_import_err})_\n\n"
            f"{_FB_END}\n"
        )
    try:
        return _cfb.render_forward_back_section(
            today,
            horizon_days=14,
            use_gemma=use_gemma,
            dly_reader=_dly_reader,  # enables 72h gap detection for P0 events
        )
    except Exception as e:
        log.warning(f"Forward-back render failed: {e}")
        return (
            f"{_FB_HEADER}\n{_FB_START}\n\n"
            f"_(calendar render failed: {e})_\n\n"
            f"{_FB_END}\n"
        )


def _wky_path_for(d: date) -> Path:
    """WKY path covering ISO-week of `d`."""
    monday = d - timedelta(days=d.weekday())
    week_num = monday.isocalendar()[1]
    return DAILY_DIR / str(monday.year) / f"{monday.month:02d}" / f"{monday.year}-W{week_num:02d}-WKY.md"


def _dly_reader(d: date) -> str | None:
    p = dly_path(d)
    try:
        if p.exists() and p.stat().st_size > 0:
            return p.read_text(encoding="utf-8")
    except OSError:
        pass
    return None


def _build_past_7_days(today: date) -> str:
    if _cfb is None:
        return (
            f"{_P7_HEADER}\n{_P7_START}\n\n"
            f"_(calendar module unavailable — past-7-days extractor lives there)_\n\n"
            f"{_P7_END}\n"
        )
    try:
        return _cfb.render_past_7_days_section(today, _dly_reader, _wky_path_for)
    except Exception as e:
        log.warning(f"Past 7 days render failed: {e}")
        return (
            f"{_P7_HEADER}\n{_P7_START}\n\n"
            f"_(past-7-days render failed: {e})_\n\n"
            f"{_P7_END}\n"
        )


# ── Injection ─────────────────────────────────────────────────────────────────

def _insert_before_anchors(existing: str, section: str, anchors: list[str]) -> str:
    """
    Insert `section` into `existing` immediately before the earliest of
    `anchors` (top-of-file-wise). If no anchor found, append to end.
    """
    earliest = None
    for a in anchors:
        i = existing.find("\n" + a)
        if i != -1 and (earliest is None or i < earliest):
            earliest = i
    if earliest is None:
        return existing.rstrip() + "\n\n" + section
    return existing[:earliest].rstrip() + "\n\n" + section + "\n" + existing[earliest + 1:]


def _inject_one(
    existing: str,
    section: str,
    header: str,
    start_marker: str,
    end_marker: str,
    strict_re: re.Pattern,
    fallback_re: re.Pattern,
    insertion_anchors: list[str],
) -> str:
    """Replace in place if markers exist; else insert above the first anchor."""
    if start_marker in existing and end_marker in existing:
        updated = strict_re.sub(section, existing, count=1)
        if updated == existing:
            updated = fallback_re.sub(section, existing, count=1)
        return updated
    if header in existing:
        return fallback_re.sub(section, existing, count=1)
    return _insert_before_anchors(existing, section, insertion_anchors)


def inject_recent_context(
    target_date: date,
    dry_run: bool = False,
    use_gemma: bool = True,
    sections: tuple[str, ...] = ("forward_back", "past_7", "recent_context"),
) -> Path:
    """
    Inject the three temporal-context sections into today's DLY.
    Each section is idempotent via its own marker pair.

    Top-to-bottom order in the DLY:
      ## 🎯 Today — Forward-Back (next 14 days)
      ## 📅 Past 7 Days
      ## Recent Context  (last completed week + last completed month)
    """
    note_path = dly_path(target_date)

    # Build whichever sections were requested
    fb_section = _build_forward_back(target_date, use_gemma=use_gemma) if "forward_back" in sections else None
    p7_section = _build_past_7_days(target_date) if "past_7" in sections else None
    rc_section = _build_section(target_date) if "recent_context" in sections else None

    if dry_run:
        log.info(f"[dry-run] Would update {note_path}")
        preview_parts = [s for s in (fb_section, p7_section, rc_section) if s]
        log.info("Combined preview:\n" + "\n".join(preview_parts))
        return note_path

    if not note_path.exists():
        log.warning(f"DLY not found: {note_path} — skipping (morning_workflow creates it first)")
        return note_path

    existing = note_path.read_text(encoding="utf-8")
    updated = existing

    # Insertion order matters: insert Recent Context first (bottom of stack),
    # then Past 7 (which will land above Recent Context via its anchor list),
    # then Forward-Back (which lands above both).
    default_anchors = ["## Captures", "## Email Activity", "## Vault Activity", "## Navigation"]

    if rc_section:
        updated = _inject_one(
            updated, rc_section,
            _SECTION_HEADER, _START_MARKER, _END_MARKER,
            _SECTION_RE, _FALLBACK_SECTION_RE,
            insertion_anchors=default_anchors,
        )

    if p7_section:
        updated = _inject_one(
            updated, p7_section,
            _P7_HEADER, _P7_START, _P7_END,
            _P7_RE, _P7_FALLBACK_RE,
            insertion_anchors=[_SECTION_HEADER] + default_anchors,
        )

    if fb_section:
        updated = _inject_one(
            updated, fb_section,
            _FB_HEADER, _FB_START, _FB_END,
            _FB_RE, _FB_FALLBACK_RE,
            insertion_anchors=[_P7_HEADER, _SECTION_HEADER] + default_anchors,
        )

    if updated == existing:
        log.info(f"  No change needed: {note_path}")
        return note_path

    note_path.write_text(updated, encoding="utf-8")
    log.info(f"  Updated: {note_path}")
    return note_path


# ── Public API ────────────────────────────────────────────────────────────────

def run_inject(
    target_date: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    use_gemma: bool = True,
    sections: tuple[str, ...] = ("forward_back", "past_7", "recent_context"),
) -> dict:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    if target_date:
        d = datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        d = date.today()

    log.info(
        f"Injecting context into DLY for {d.isoformat()} "
        f"(sections={list(sections)}, dry_run={dry_run}, gemma={use_gemma})"
    )
    path = inject_recent_context(d, dry_run=dry_run, use_gemma=use_gemma, sections=sections)

    return {
        "target_date": d.isoformat(),
        "dly_path": str(path),
        "dly_exists": path.exists(),
        "dry_run": dry_run,
        "sections": list(sections),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inject 🎯 Forward-Back + 📅 Past 7 Days + Recent Context blocks into today's DLY"
    )
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--no-gemma", action="store_true", help="Hard-truncate event notes instead of Gemma4 summary")
    parser.add_argument("--no-forward-back", action="store_true", help="Skip 🎯 section")
    parser.add_argument("--no-past-7", action="store_true", help="Skip 📅 section")
    parser.add_argument("--no-recent-context", action="store_true", help="Skip last-week/last-month section")
    args = parser.parse_args(argv)

    sections = []
    if not args.no_forward_back:
        sections.append("forward_back")
    if not args.no_past_7:
        sections.append("past_7")
    if not args.no_recent_context:
        sections.append("recent_context")

    try:
        result = run_inject(
            target_date=args.date,
            dry_run=args.dry_run,
            verbose=args.verbose,
            use_gemma=not args.no_gemma,
            sections=tuple(sections),
        )
    except Exception as e:
        log.error(f"Failed: {e}", exc_info=args.verbose)
        return 1

    log.info(f"Result: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
