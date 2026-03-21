#!/usr/bin/env python3
"""
task_dedup.py — Deduplicate vault tasks using fuzzy text matching.

Uses difflib.SequenceMatcher at 0.85 threshold. Handles both same-file
(Plaud transcript vs. structured section) and cross-file duplicates.

Usage:
    python3 -m System.Scripts.task_dedup [--dry-run]
"""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from System.Scripts.task_scanner import RawTask, scan_vault, STATE_FILE

SIMILARITY_THRESHOLD = 0.85

# Sections considered "structured" (win over transcript sections)
STRUCTURED_SECTIONS = {
    "action items", "next steps", "pending actions", "tasks extracted",
    "tasks", "to do", "todo",
}

TRANSCRIPT_SECTIONS = {"transcript", "transcription", "raw transcript"}


@dataclass
class DeduplicationAction:
    keep: RawTask
    remove: list[RawTask]
    similarity: float
    reason: str


def strip_task_metadata(text: str) -> str:
    """Remove dates, emoji, category tags, and checkbox markers for comparison."""
    t = re.sub(r'📅\s*\d{4}-\d{2}-\d{2}', '', text)
    t = re.sub(r'✅\s*\d{4}-\d{2}-\d{2}', '', t)
    t = re.sub(r'➕\s*\d{4}-\d{2}-\d{2}', '', t)
    t = re.sub(r'#(work|personal|career|tech|vault)\b', '', t)
    t = re.sub(r'^\s*-\s*\[[ x/\-]\]\s*', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip().lower()


def is_duplicate(task_a: RawTask, task_b: RawTask, threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """Return True if two tasks are likely duplicates."""
    clean_a = strip_task_metadata(task_a.normalized_text)
    clean_b = strip_task_metadata(task_b.normalized_text)
    if not clean_a or not clean_b:
        return False
    return SequenceMatcher(None, clean_a, clean_b).ratio() >= threshold


def _similarity(task_a: RawTask, task_b: RawTask) -> float:
    clean_a = strip_task_metadata(task_a.normalized_text)
    clean_b = strip_task_metadata(task_b.normalized_text)
    if not clean_a or not clean_b:
        return 0.0
    return SequenceMatcher(None, clean_a, clean_b).ratio()


def _score_task(task: RawTask) -> tuple:
    """Higher score = better candidate to keep. Returns tuple for sorting."""
    is_structured = task.section_name in STRUCTURED_SECTIONS
    is_transcript = task.section_name in TRANSCRIPT_SECTIONS
    has_date = task.has_due_date
    has_category = task.has_category_tag
    text_len = len(task.normalized_text)
    # Higher file mtime = more recent
    mtime = task.file_modified_date

    return (
        not is_transcript,   # structured wins over transcript
        is_structured,       # structured is best
        has_date,            # tasks with dates are better
        has_category,        # categorized is better
        text_len,            # more detail is better
        mtime,               # newer is better
    )


def _pick_winner(cluster: list[RawTask]) -> tuple[RawTask, str]:
    """Pick the best task from a duplicate cluster. Returns (winner, reason)."""
    scored = sorted(cluster, key=_score_task, reverse=True)
    winner = scored[0]

    reasons = []
    if winner.section_name in STRUCTURED_SECTIONS:
        reasons.append("structured section preferred over transcript")
    if winner.has_due_date:
        reasons.append("has due date")
    if winner.has_category_tag:
        reasons.append("has category tag")
    if not reasons:
        reasons.append("more recent file / longer description")

    return winner, "; ".join(reasons)


def find_duplicates(tasks: list[RawTask]) -> list[DeduplicationAction]:
    """
    Find all duplicate clusters and return dedup actions.
    Err on the side of NOT merging — threshold 0.85 is conservative.
    """
    actions: list[DeduplicationAction] = []
    used: set[int] = set()  # indices already assigned to a cluster

    for i, task_a in enumerate(tasks):
        if i in used:
            continue
        cluster = [task_a]
        for j, task_b in enumerate(tasks):
            if j <= i or j in used:
                continue
            sim = _similarity(task_a, task_b)
            if sim >= SIMILARITY_THRESHOLD:
                cluster.append(task_b)
                used.add(j)

        if len(cluster) > 1:
            used.add(i)
            winner, reason = _pick_winner(cluster)
            losers = [t for t in cluster if t is not winner]
            max_sim = max(_similarity(winner, r) for r in losers)
            actions.append(DeduplicationAction(
                keep=winner,
                remove=losers,
                similarity=round(max_sim, 3),
                reason=reason,
            ))

    return actions


def apply_dedup(actions: list[DeduplicationAction], dry_run: bool = False) -> int:
    """
    Apply dedup actions to source files.
    - Same-file transcript duplicates: prepend %% (Obsidian comment)
    - Cross-file duplicates: change - [ ] to - [-] and append duplicate note
    Returns count of changes made.
    """
    if dry_run:
        for action in actions:
            print(f"KEEP: {action.keep.source_file}:{action.keep.line_number} — {action.keep.normalized_text[:60]}")
            for r in action.remove:
                print(f"  REMOVE: {r.source_file}:{r.line_number} — {r.normalized_text[:60]}")
                print(f"  Reason: {action.reason} (similarity={action.similarity})")
        return len(actions)

    # Group changes by file
    file_changes: dict[str, dict[int, str]] = {}  # file -> {lineno: new_line}

    for action in actions:
        winner_file = action.keep.source_file
        winner_stem = Path(winner_file).stem

        for loser in action.remove:
            loser_file = loser.source_file
            loser_lineno = loser.line_number

            if loser_file not in file_changes:
                file_changes[loser_file] = {}

            same_file = loser_file == winner_file
            loser_in_transcript = loser.section_name in TRANSCRIPT_SECTIONS

            if same_file and loser_in_transcript:
                # Comment out with Obsidian %% syntax
                file_changes[loser_file][loser_lineno] = f"%% {loser.text} %%"
            else:
                # Mark as cancelled with duplicate link
                base = re.sub(r'^(\s*)-\s*\[[ /\-]\]', r'\1- [-]', loser.text)
                if not base.startswith('- [-]') and not re.match(r'^\s*- \[-\]', base):
                    base = f"- [-] {loser.normalized_text}"
                base = base.rstrip()
                file_changes[loser_file][loser_lineno] = f"{base} (duplicate — see [[{winner_stem}]])"

    # Write changes atomically per file
    changes_made = 0
    for file_path, line_changes in file_changes.items():
        path = Path(file_path)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            for lineno, new_text in line_changes.items():
                idx = lineno - 1
                if 0 <= idx < len(lines):
                    # Preserve trailing newline
                    ending = '\n' if lines[idx].endswith('\n') else ''
                    lines[idx] = new_text.rstrip('\n') + ending

            tmp = path.with_suffix('.tmp_dedup')
            tmp.write_text(''.join(lines), encoding="utf-8")
            tmp.replace(path)
            changes_made += len(line_changes)
        except Exception as e:
            print(f"ERROR writing {file_path}: {e}", file=sys.stderr)

    return changes_made


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Deduplicate vault tasks")
    ap.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    ap.add_argument("--full", action="store_true", help="Scan all files")
    args = ap.parse_args()

    tasks = scan_vault(full=args.full)
    print(f"Scanned {len(tasks)} tasks", file=sys.stderr)

    actions = find_duplicates(tasks)
    print(f"Found {len(actions)} duplicate clusters", file=sys.stderr)

    changed = apply_dedup(actions, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"Applied {changed} changes", file=sys.stderr)


if __name__ == "__main__":
    main()
