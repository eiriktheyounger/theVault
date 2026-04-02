#!/usr/bin/env python3
"""generate_daily_dashboard.py — Create daily dashboard for morning workflow.

Called by morning_workflow.py Step 3.
Aggregates: open tasks, recent vault activity, ingest stats.
Output: TimeTracking/YYYY/MM/Daily_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

VAULT_ROOT = Path.home() / "theVault" / "Vault"
TRACKING_ROOT = VAULT_ROOT / "TimeTracking"


def _today_str() -> str:
    return date.today().isoformat()


def _get_daily_note_path(date_str: str) -> Path:
    """Get path to the DLY file for a given date."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return VAULT_ROOT / "Daily" / str(dt.year) / f"{dt.month:02d}" / f"{date_str}-DLY.md"


def _get_open_tasks(date_str: str) -> list[str]:
    """Extract unchecked tasks from today's DLY file."""
    dly = _get_daily_note_path(date_str)
    if not dly.exists():
        return []

    tasks = []
    try:
        text = dly.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                tasks.append(stripped)
    except Exception:
        pass
    return tasks


def _get_recent_activity(date_str: str) -> list[str]:
    """Pull recent vault activity section from DLY if it exists."""
    dly = _get_daily_note_path(date_str)
    if not dly.exists():
        return []

    try:
        text = dly.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        in_section = False
        activity = []
        for line in lines:
            if "## Vault Activity" in line or "## Email Activity" in line:
                in_section = True
                activity.append(line)
                continue
            if in_section:
                if line.startswith("## ") and "Activity" not in line:
                    break
                if line.strip():
                    activity.append(line)
        return activity
    except Exception:
        return []


def generate_dashboard(date_str: str) -> str:
    """Generate dashboard markdown content."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%A")

    tasks = _get_open_tasks(date_str)
    activity = _get_recent_activity(date_str)

    lines = [
        f"---",
        f"type: daily-dashboard",
        f"date: {date_str}",
        f"tags: [dashboard, daily]",
        f"---",
        f"",
        f"# Daily Dashboard — {day_name}, {date_str}",
        f"",
    ]

    # Tasks section
    lines.append("## Open Tasks")
    if tasks:
        for t in tasks[:20]:
            lines.append(t)
    else:
        lines.append("_No open tasks found in today's daily note._")
    lines.append("")

    # Activity section
    lines.append("## Recent Activity")
    if activity:
        for a in activity:
            lines.append(a)
    else:
        lines.append("_No vault activity recorded yet today._")
    lines.append("")

    # Quick links
    lines.append("## Quick Links")
    lines.append(f"- [[Daily/{dt.year}/{dt.month:02d}/{date_str}-DLY|Today's Daily Note]]")
    lines.append(f"- [[System/ClassificationReview|Classification Review]]")
    lines.append("")

    return "\n".join(lines)


def write_dashboard(date_str: str, dry_run: bool = False) -> Path:
    """Write dashboard file and return its path."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    out_dir = TRACKING_ROOT / str(dt.year) / f"{dt.month:02d}"
    out_path = out_dir / f"Daily_{date_str}.md"

    content = generate_dashboard(date_str)

    if dry_run:
        print(f"DRY RUN — would write to {out_path}")
        print(content)
        return out_path

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    log.info(f"Dashboard written to {out_path}")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily dashboard")
    parser.add_argument("date", nargs="?", default=_today_str(), help="Date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        path = write_dashboard(args.date, dry_run=args.dry_run)
        print(f"Dashboard created for {args.date}")
        print(f"Saved to TimeTracking/{args.date[:4]}/{args.date[5:7]}/Daily_{args.date}.md")
        return 0
    except Exception as e:
        print(f"Failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
