#!/usr/bin/env python3
"""
Plaud Processor Handoff — Bridge between plaud-processor and the main ingest workflow.

Moves session files from the standalone plaud-processor into the MarkdownOnly inbox
so the existing consolidation + LLM pipeline can process them into the vault.

What moves:
  FROM plaud-processor/processed/   → *-Enriched_Analysis.md (primary output, no model suffix)
  FROM plaud-processor/inbox/       → all remaining session files (MDs + SRT), no type filter

What does NOT move:
  - Model-specific outputs:    *-Enriched_Analysis_claude_*.md, *-Enriched_Analysis_ollama_*.md
  - Comparison reports:        *-Comparison_Report.md
  - Files that don't match any session found in processed/

After a successful move, source files are removed from plaud-processor/inbox/.
Files in plaud-processor/processed/ are left in place (serve as archive/reference).

Usage:
  python plaud_handoff.py           # Move all ready sessions
  python plaud_handoff.py --dry-run # Preview only, no files moved
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

PLAUD_PROCESSOR_DIR = Path.home() / "theVault" / "plaud-processor"
PLAUD_PROCESSED     = PLAUD_PROCESSOR_DIR / "processed"
PLAUD_INBOX         = PLAUD_PROCESSOR_DIR / "inbox"
MARKDOWNONLY_INBOX  = Path.home() / "theVault" / "Inbox" / "Plaud" / "MarkdownOnly"

# Patterns that identify comparison/model-specific outputs to exclude
_EXCLUDE_PATTERNS = [
    re.compile(r"-Enriched_Analysis_(claude|ollama)_"),
    re.compile(r"-Comparison_Report\.md$"),
]


# ── Session Discovery ─────────────────────────────────────────────────────────

def find_ready_sessions() -> dict[str, Path]:
    """
    Scan plaud-processor/processed/ for primary Enriched_Analysis files.

    A "primary" file is one that matches *-Enriched_Analysis.md but NOT
    any of the model-specific or comparison-report patterns.

    Returns: {session_base: enriched_path}
    """
    if not PLAUD_PROCESSED.exists():
        return {}

    sessions: dict[str, Path] = {}
    for path in sorted(PLAUD_PROCESSED.glob("*-Enriched_Analysis.md")):
        # Skip model-specific outputs
        if any(p.search(path.name) for p in _EXCLUDE_PATTERNS):
            continue
        # Derive session base name: strip "-Enriched_Analysis.md"
        base = path.name[: -len("-Enriched_Analysis.md")]
        sessions[base] = path

    return sessions


def find_inbox_files(session_base: str) -> list[Path]:
    """
    Find all session files (any type) in plaud-processor/inbox/ that belong
    to the given session base name.

    Matches files whose name starts with session_base + "-".
    No file-type restriction — MDs, SRTs, all travel together.
    """
    if not PLAUD_INBOX.exists():
        return []

    prefix = session_base + "-"
    return [f for f in sorted(PLAUD_INBOX.iterdir())
            if f.is_file() and not f.name.startswith(".") and f.name.startswith(prefix)]


# ── Move Logic ────────────────────────────────────────────────────────────────

def move_session(session_base: str, enriched_path: Path, inbox_files: list[Path],
                 dry_run: bool = False) -> dict:
    """
    Move one session's files to the MarkdownOnly inbox.

    Returns a result dict describing what happened.
    """
    result = {
        "session": session_base,
        "moved": [],
        "skipped": [],
        "errors": [],
        "success": False,
    }

    files_to_move: list[tuple[Path, Path]] = []  # (source, destination)

    # 1. Enriched_Analysis from processed/
    dest_enriched = MARKDOWNONLY_INBOX / enriched_path.name
    files_to_move.append((enriched_path, dest_enriched))

    # 2. All session files from inbox/ (MD + SRT, no filter)
    for src in inbox_files:
        dest = MARKDOWNONLY_INBOX / src.name
        files_to_move.append((src, dest))

    if not files_to_move:
        result["errors"].append("No files found to move")
        return result

    if dry_run:
        for src, dst in files_to_move:
            result["moved"].append(f"  {src} → {dst}")
        result["success"] = True
        return result

    # Execute moves — copy enriched (keep original as archive), move inbox files
    MARKDOWNONLY_INBOX.mkdir(parents=True, exist_ok=True)

    for src, dst in files_to_move:
        try:
            # Handle filename collision
            if dst.exists():
                stem = dst.stem
                suffix = dst.suffix
                counter = 1
                while dst.exists():
                    dst = dst.parent / f"{stem}-{counter}{suffix}"
                    counter += 1

            if src.parent == PLAUD_PROCESSED:
                # Copy enriched file — leave original in processed/ as archive
                shutil.copy2(str(src), str(dst))
            else:
                # Move inbox files — clears the plaud-processor inbox
                shutil.move(str(src), str(dst))

            result["moved"].append(dst.name)
        except Exception as exc:
            result["errors"].append(f"{src.name}: {exc}")

    result["success"] = len(result["errors"]) == 0
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def run_handoff(dry_run: bool = False) -> int:
    """Execute the handoff. Returns exit code (0 = success)."""

    print(f"\n{'='*60}")
    print(f"  Plaud Handoff {'(DRY RUN)' if dry_run else ''}")
    print(f"  From : {PLAUD_PROCESSOR_DIR}")
    print(f"  To   : {MARKDOWNONLY_INBOX}")
    print(f"{'='*60}\n")

    sessions = find_ready_sessions()

    if not sessions:
        print("  Nothing to move — no primary Enriched_Analysis files found in processed/")
        print(f"  (looked in: {PLAUD_PROCESSED})\n")
        return 0

    print(f"  Found {len(sessions)} session(s) ready to move:\n")

    total_moved = 0
    total_errors = 0

    for base, enriched_path in sessions.items():
        inbox_files = find_inbox_files(base)

        print(f"  Session: {base}")
        print(f"    Enriched : {enriched_path.name}")
        if inbox_files:
            for f in inbox_files:
                print(f"    Inbox    : {f.name}")
        else:
            print(f"    Inbox    : (no source files found — already cleared?)")

        result = move_session(base, enriched_path, inbox_files, dry_run=dry_run)

        if dry_run:
            for line in result["moved"]:
                print(f"    WOULD MOVE: {line}")
        else:
            for name in result["moved"]:
                print(f"    ✓  {name}")
            for err in result["errors"]:
                print(f"    ✗  {err}")
            total_moved += len(result["moved"])
            total_errors += len(result["errors"])

        print()

    print(f"{'='*60}")
    if dry_run:
        print(f"  Dry run complete — no files were moved")
    else:
        print(f"  Moved  : {total_moved} file(s)")
        if total_errors:
            print(f"  Errors : {total_errors}")
    print(f"{'='*60}\n")

    return 1 if total_errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move plaud-processor output into the MarkdownOnly ingest inbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would move without touching any files",
    )
    args = parser.parse_args()
    sys.exit(run_handoff(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
