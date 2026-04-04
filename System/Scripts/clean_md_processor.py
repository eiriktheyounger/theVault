#!/usr/bin/env python3
"""
clean_md_processor.py — Plaud Inbox Consolidation

Scans Inbox/Plaud/MarkdownOnly/ for session files, groups them by session base
name, generates an AI summary from the SRT transcript (Anthropic API first,
Ollama fallback), then writes a single consolidated -Full.md to Vault/Notes/.

Source files are moved to Processed/Plaud/ after successful processing.

File naming convention in inbox:
    [MM-DD] [Title]-[TypeSuffix].(md|srt)

Examples:
    03-24 Meeting_ ViewLift Channel Assembly POC-Summary.md
    03-24 Meeting_ ViewLift Channel Assembly POC-Meeting Minutes.md
    03-24 Meeting_ ViewLift Channel Assembly POC-transcript.srt

Output:
    Vault/Notes/03-24 Meeting_ ViewLift Channel Assembly POC-Full.md

Usage:
    python System/Scripts/clean_md_processor.py             # process all
    python System/Scripts/clean_md_processor.py --dry-run   # preview only
    python System/Scripts/clean_md_processor.py --session "03-24 Meeting_"
    python System/Scripts/clean_md_processor.py --verbose
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("clean_md_processor")

# ── Paths ─────────────────────────────────────────────────────────────────────

VAULT_HOME      = Path.home() / "theVault"
INBOX_DIR       = VAULT_HOME / "Inbox" / "Plaud" / "MarkdownOnly"
PROCESSED_DIR   = VAULT_HOME / "Processed" / "Plaud"
VAULT_NOTES_DIR = VAULT_HOME / "Vault" / "Notes"

# ── Section ordering ──────────────────────────────────────────────────────────

# Known Plaud output types in the preferred display order after the AI summary.
# Anything not in this list still appears — just sorted alphabetically at the end.
SECTION_ORDER = [
    "Summary",
    "Meeting Minutes",
    "Meeting Highlights",
    "Meeting Report",
    "Meeting Effectiveness",
    "Quantitative Data",
    "Reasoning Summary",
    "Scene-Based Script Summary",
    "Transcript to Script and Key Points Generator",
]

# Maximum transcript characters passed to the LLM.
# A 1-hr meeting SRT is typically 60–80k chars; we cap at 40k to stay within
# context limits for every model tier.
MAX_TRANSCRIPT_CHARS = 40_000

# Minimum substantive segments to include transcript in output.
# Sessions below this threshold (e.g. "Null Signal" recordings with only coughs
# and filler words) are too noisy for the vault or RAG indexing.
MIN_TRANSCRIPT_SEGMENTS = 5

# ── SRT Parsing ───────────────────────────────────────────────────────────────

def parse_srt(content: str) -> str:
    """Strip SRT timestamps and sequence numbers, returning clean text."""
    text_lines: list[str] = []
    for line in content.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip sequence number lines (lone integers)
        if re.fullmatch(r"\d+", stripped):
            continue
        # Skip timestamp lines  00:00:00,000 --> 00:00:00,000
        if re.fullmatch(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", stripped):
            continue
        text_lines.append(stripped)
    return "\n".join(text_lines)


_TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),\d{3}\s*-->\s*(\d{2}):(\d{2}):(\d{2}),\d{3}"
)


def _fmt_ts(h: str, m: str, s: str) -> str:
    """Format HH:MM:SS, dropping leading hour if zero."""
    if h == "00":
        return f"{m}:{s}"
    return f"{h}:{m}:{s}"


def _extract_session_date(base_name: str) -> str:
    """
    Extract an ISO date (YYYY-MM-DD) from the session base name.

    Filename convention is 'MM-DD Title...' — we combine with the current year.
    Returns empty string if no date pattern found.
    """
    date_match = re.match(r"^(\d{2})-(\d{2})\s", base_name)
    if date_match:
        year = datetime.now().year
        return f"{year}-{date_match.group(1)}-{date_match.group(2)}"
    return ""


def format_srt_as_markdown(content: str, session_date: str = "") -> str:
    """
    Convert raw SRT content into a readable markdown transcript.

    If session_date is provided (e.g. '2026-03-24'), timestamps become absolute:
        **[2026-03-24 01:23 → 01:45]** **Speaker Name:** Dialogue text here.

    Otherwise falls back to relative timestamps:
        **[01:23 → 01:45]** **Speaker Name:** Dialogue text here.

    Segments are separated by blank lines for readability.
    """
    segments: list[str] = []
    current_ts = ""
    current_text_lines: list[str] = []
    date_prefix = f"{session_date} " if session_date else ""

    def _flush():
        if current_text_lines:
            text = " ".join(current_text_lines)
            if current_ts:
                segments.append(f"{current_ts} {text}")
            else:
                segments.append(text)

    for line in content.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Skip sequence number lines
        if re.fullmatch(r"\d+", stripped):
            continue

        # Timestamp line — flush previous segment and start new one
        ts_match = _TS_RE.fullmatch(stripped)
        if ts_match:
            _flush()
            current_text_lines = []
            start = _fmt_ts(ts_match.group(1), ts_match.group(2), ts_match.group(3))
            end = _fmt_ts(ts_match.group(4), ts_match.group(5), ts_match.group(6))
            current_ts = f"**[{date_prefix}{start} → {end}]**"
            continue

        # Text line — bold the speaker label if present
        speaker_match = re.match(r"^([^:]{1,50}):\s*", stripped)
        if speaker_match:
            speaker = speaker_match.group(1)
            rest = stripped[speaker_match.end():]
            current_text_lines.append(f"**{speaker}:** {rest}")
        else:
            current_text_lines.append(stripped)

    _flush()

    return "\n\n".join(segments)


def _count_substantive_segments(content: str) -> int:
    """Count SRT segments that contain more than filler/non-lexical content."""
    filler_re = re.compile(
        r"^(mm-?hmm|uh-?huh|yeah|um|oh|hmm|cough|ahem|shhh|thank you|"
        r"thanks for watching|i know|go|all right)[\.\!\?]?$",
        re.IGNORECASE,
    )
    count = 0
    for line in content.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        if _TS_RE.fullmatch(stripped):
            continue
        # Strip speaker label before checking
        speaker_match = re.match(r"^[^:]{1,50}:\s*", stripped)
        text = stripped[speaker_match.end():] if speaker_match else stripped
        text = text.strip()
        if text and not filler_re.fullmatch(text):
            count += 1
    return count


# ── Session Grouping ──────────────────────────────────────────────────────────

def split_base_and_suffix(stem: str) -> tuple[str, str]:
    """
    Split a filename stem into (session_base, suffix_type).

    First tries to match a known SECTION_ORDER suffix (longest first) so that
    hyphenated types like 'Scene-Based Script Summary' are not cut at their
    internal hyphen.  Falls back to splitting on the last '-' for unknown types
    (e.g. 'transcript') and bare duplicate files.

    Trailing duplicate markers like ' (1)' are stripped from the suffix.

    Examples:
        '03-19 Interview_ Eric Manchester - Architect-Meeting Highlights'
            → ('03-19 Interview_ Eric Manchester - Architect', 'Meeting Highlights')

        '02-19 Analysis-Scene-Based Script Summary'
            → ('02-19 Analysis', 'Scene-Based Script Summary')

        '03-24 Meeting_ Foo-transcript (1)'
            → ('03-24 Meeting_ Foo', 'transcript')
    """
    # Strip trailing duplicate marker before matching
    clean = re.sub(r"\s*\(\d+\)\s*$", "", stem).strip()

    # Try known suffixes longest-first so 'Scene-Based Script Summary' wins
    # over a shorter accidental match
    for known in sorted(SECTION_ORDER, key=len, reverse=True):
        candidate = f"-{known}"
        if clean.endswith(candidate):
            base = clean[: -len(candidate)]
            return base, known

    # Unknown suffix type — split on last '-'
    idx = clean.rfind("-")
    if idx == -1:
        return stem, ""
    return clean[:idx], clean[idx + 1:].strip()


def group_sessions(inbox: Path) -> dict[str, dict[str, list[Path]]]:
    """
    Scan inbox directory and return sessions grouped by base name.

    Returns:
        { session_base: { suffix_type: [Path, ...] } }

    Multiple paths per suffix handle duplicate files (e.g. transcript (1)).
    """
    sessions: dict[str, dict[str, list[Path]]] = {}
    for path in sorted(inbox.iterdir()):
        if path.name.startswith("."):
            continue
        if path.suffix not in (".md", ".srt"):
            continue
        base, suffix = split_base_and_suffix(path.stem)
        if not base:
            continue
        sessions.setdefault(base, {}).setdefault(suffix, []).append(path)
    return sessions


# ── LLM Summary Generation ────────────────────────────────────────────────────

_SUMMARY_PROMPT = """\
You are summarizing a transcript captured by a Plaud recording device.
The recording may be a meeting, interview, voice note, or personal reflection.

Generate a concise but complete summary with the following sections.
Include only sections where you have something meaningful to say.

**Overview** — 2–4 sentences: what this recording is about and its context.

**Key Topics** — Bullet list of main subjects discussed.

**Decisions & Action Items** — Decisions made or follow-up actions required.

**Notable Insights** — Significant quotes, observations, or conclusions.

Be specific. Avoid generic filler. Write in plain markdown. No preamble.

TRANSCRIPT:
{transcript}
"""


def _summarize_anthropic(transcript: str) -> Optional[str]:
    """Try Anthropic API (Claude Haiku). Returns None on any failure."""
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": _SUMMARY_PROMPT.format(transcript=transcript)}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        log.warning(f"  Anthropic API error: {e}")
        return None


def _summarize_ollama(transcript: str) -> Optional[str]:
    """Try local Ollama (qwen2.5:7b). Returns None on any failure."""
    try:
        import ollama
        resp = ollama.chat(
            model="qwen2.5:7b",
            messages=[{"role": "user", "content": _SUMMARY_PROMPT.format(transcript=transcript)}],
            options={"temperature": 0.3},
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        log.warning(f"  Ollama error: {e}")
        return None


def generate_summary(transcript_text: str) -> str:
    """
    Generate AI summary. Tries Anthropic first, then Ollama, then placeholder.
    Truncates transcript if over MAX_TRANSCRIPT_CHARS.
    """
    text = transcript_text
    truncated = len(text) > MAX_TRANSCRIPT_CHARS
    if truncated:
        text = text[:MAX_TRANSCRIPT_CHARS]
        log.info(f"  Transcript truncated to {MAX_TRANSCRIPT_CHARS:,} chars for LLM")

    summary = _summarize_anthropic(text) or _summarize_ollama(text)

    if summary is None:
        log.warning("  No LLM available — using placeholder")
        summary = (
            "_AI summary unavailable. No LLM service responded. "
            "Re-run with `ANTHROPIC_API_KEY` set or Ollama running._"
        )

    if truncated:
        summary += (
            "\n\n> **Note:** Transcript exceeded 40,000 characters and was truncated "
            "before summarization. Full transcript is in the SRT source file."
        )

    return summary


# ── Output Assembly ───────────────────────────────────────────────────────────

def _build_frontmatter(base_name: str, processed_date: str) -> str:
    """Build YAML frontmatter block for the consolidated note."""
    year = datetime.now().year
    date_match = re.match(r"^(\d{2})-(\d{2})\s", base_name)
    if date_match:
        month, day = date_match.group(1), date_match.group(2)
        note_date = f"{year}-{month}-{day}"
    else:
        note_date = processed_date

    # Strip leading MM-DD prefix from display title
    title = base_name[6:].strip() if date_match else base_name
    # Escape any double quotes in title
    title_escaped = title.replace('"', '\\"')

    return (
        f'---\n'
        f'title: "{title_escaped}"\n'
        f'date: {note_date}\n'
        f'processed: {processed_date}\n'
        f'source: plaud\n'
        f'tags: [plaud, meeting, transcript]\n'
        f'---'
    )


def _read_md_body(path: Path) -> str:
    """Read markdown file and strip YAML frontmatter if present."""
    content = path.read_text(encoding="utf-8", errors="replace").strip()
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[end + 4:].strip()
    return content


def build_output(
    base_name: str,
    ai_summary: Optional[str],
    note_files: dict[str, list[Path]],
    processed_date: str,
    transcript_md: Optional[str] = None,
) -> str:
    """
    Assemble the consolidated -Full.md document.

    Document order:
        YAML frontmatter
        # Title
        ## AI Summary      ← generated from SRT (if available)
        ---
        ## Summary         ← from -Summary.md
        ---
        ## Meeting Minutes ← from -Meeting Minutes.md
        ... (remaining sections in SECTION_ORDER, then alphabetical)
        ---
        <details> Full Transcript (collapsed) </details>
    """
    date_match = re.match(r"^(\d{2})-(\d{2})\s", base_name)
    title = base_name[6:].strip() if date_match else base_name

    parts: list[str] = [
        _build_frontmatter(base_name, processed_date),
        "",
        f"# {title}",
        "",
    ]

    if ai_summary:
        parts += ["## AI Summary", "", ai_summary, "", "---", ""]

    # Order sections: known types first (in SECTION_ORDER), then rest alphabetically
    seen: set[str] = set()
    ordered_keys: list[str] = []
    for key in SECTION_ORDER:
        if key in note_files:
            ordered_keys.append(key)
            seen.add(key)
    for key in sorted(note_files):
        if key not in seen and key != "transcript":
            ordered_keys.append(key)

    for key in ordered_keys:
        paths = note_files[key]
        # Merge duplicate files for the same section type
        body_parts = [_read_md_body(p) for p in sorted(paths)]
        body = ("\n\n---\n\n").join(body_parts) if len(body_parts) > 1 else body_parts[0]
        parts += [f"## {key}", "", body, "", "---", ""]

    # ── Collapsible full transcript (from SRT) ────────────────────────────
    if transcript_md:
        parts += [
            "<details>",
            "<summary><strong>Full Transcript</strong></summary>",
            "",
            transcript_md,
            "",
            "</details>",
            "",
        ]

    return "\n".join(parts)


# ── Core Processing ───────────────────────────────────────────────────────────

def process_session(
    base_name: str,
    files: dict[str, list[Path]],
    dry_run: bool = False,
    force: bool = False,
    move_sources: bool = True,
) -> str:
    """
    Process one session. Returns 'processed', 'skipped', or 'failed'.

    force=True  — overwrite existing output even if it already exists.
    move_sources=False — skip moving source files to Processed/ (use when
                         they are already there, e.g. --reprocess mode).
    """
    output_path = VAULT_NOTES_DIR / f"{base_name}-Full.md"

    if output_path.exists() and not force:
        log.info(f"  Already exists — skipping")
        return "skipped"

    processed_date = datetime.now().strftime("%Y-%m-%d")

    # ── SRT → AI summary + formatted transcript ────────────────────────────
    ai_summary: Optional[str] = None
    transcript_md: Optional[str] = None
    srt_paths = files.get("transcript", [])

    if srt_paths:
        raw_srt = "\n\n".join(
            p.read_text(encoding="utf-8", errors="replace") for p in sorted(srt_paths)
        )
        transcript_text = parse_srt(raw_srt)

        if transcript_text.strip():
            char_count = len(transcript_text)
            log.info(f"  SRT: {char_count:,} chars, {len(srt_paths)} file(s)")

            # Quality gate: skip transcript if mostly filler/noise
            substantive = _count_substantive_segments(raw_srt)
            if substantive >= MIN_TRANSCRIPT_SEGMENTS:
                transcript_md = format_srt_as_markdown(raw_srt)
                log.info(f"  Transcript formatted: {len(transcript_md):,} chars ({substantive} substantive segments)")
            else:
                log.info(f"  Transcript below quality threshold ({substantive} < {MIN_TRANSCRIPT_SEGMENTS} substantive segments) — skipping append")

            if dry_run:
                ai_summary = "_[DRY RUN — AI summary would be generated here]_"
            else:
                log.info("  Generating AI summary...")
                ai_summary = generate_summary(transcript_text)
        else:
            log.warning("  SRT parsed to empty — skipping AI summary")
    else:
        log.info("  No SRT transcript — skipping AI summary")

    # ── Validate we have something to write ───────────────────────────────────
    note_files = {k: v for k, v in files.items() if k != "transcript"}
    if not ai_summary and not note_files:
        log.warning("  No content to write — skipping")
        return "failed"

    # ── Write output ──────────────────────────────────────────────────────────
    content = build_output(base_name, ai_summary, note_files, processed_date, transcript_md)

    if dry_run:
        section_names = (["AI Summary"] if ai_summary else []) + list(note_files.keys())
        log.info(f"  [DRY RUN] Would write: {output_path.name}")
        log.info(f"  Sections: {section_names}")
    else:
        VAULT_NOTES_DIR.resolve().mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        log.info(f"  Written: Vault/Notes/{output_path.name}")

    # ── Move source files to Processed ───────────────────────────────────────
    all_sources = [p for paths in files.values() for p in paths]

    if not move_sources:
        log.info(f"  Source files already in Processed/ — not moving")
    elif dry_run:
        log.info(f"  [DRY RUN] Would move {len(all_sources)} source file(s) → Processed/Plaud/")
    else:
        PROCESSED_DIR.resolve().mkdir(parents=True, exist_ok=True)
        moved = 0
        for src in all_sources:
            dest = PROCESSED_DIR / src.name
            if dest.exists():
                stem, ext = dest.stem, dest.suffix
                counter = 1
                while dest.exists():
                    dest = PROCESSED_DIR / f"{stem}-dup{counter}{ext}"
                    counter += 1
            shutil.move(str(src), str(dest))
            moved += 1
        log.info(f"  Moved {moved} source file(s) → Processed/Plaud/")

    return "processed"


# ── Main Orchestration ────────────────────────────────────────────────────────

def run_orchestration(
    session_filter: Optional[str] = None,
    dry_run: bool = False,
    reprocess: bool = False,
) -> dict:
    """
    Public entry point used by morning_workflow.py and routes/ingest.py.

    Returns:
        {
            "groups": int,        # sessions found
            "succeeded": int,
            "skipped": int,
            "failed": int,
        }
    """
    source_dir = PROCESSED_DIR if reprocess else INBOX_DIR
    source_label = "Processed/Plaud" if reprocess else "Inbox"

    if not source_dir.exists():
        log.error(f"{source_label} not found: {source_dir}")
        return {"error": f"{source_label} not found", "groups": 0, "succeeded": 0, "skipped": 0, "failed": 0}

    sessions = group_sessions(source_dir)

    if not sessions:
        print(f"📭 No files found in {source_label}")
        return {"groups": 0, "succeeded": 0, "skipped": 0, "failed": 0}

    if session_filter:
        sessions = {k: v for k, v in sessions.items() if session_filter.lower() in k.lower()}
        if not sessions:
            log.warning(f"No sessions matching filter: {session_filter!r}")
            return {"groups": 0, "succeeded": 0, "skipped": 0, "failed": 0}

    # In reprocess mode, only touch sessions whose output already exists directly
    # in Vault/Notes/ (not in subdirectories). Prevents accidentally processing
    # sessions that were never run or whose output has been relocated.
    if reprocess:
        before = len(sessions)
        sessions = {
            k: v for k, v in sessions.items()
            if (VAULT_NOTES_DIR / f"{k}-Full.md").exists()
        }
        filtered = before - len(sessions)
        if filtered:
            log.info(f"  Reprocess filter: {filtered} session(s) have no existing output in Vault/Notes/ — skipping")

    total     = len(sessions)
    succeeded = 0
    skipped   = 0
    failed    = 0

    log.info(f"Found {total} session(s) in inbox")
    if dry_run:
        log.info("DRY RUN — no files will be written or moved")

    for i, (base_name, files) in enumerate(sorted(sessions.items()), 1):
        suffix_summary = ", ".join(
            f"{k}×{len(v)}" for k, v in sorted(files.items())
        )
        log.info(f"\n[{i}/{total}] {base_name}")
        log.info(f"  Files: {suffix_summary}")

        try:
            result = process_session(
                base_name, files,
                dry_run=dry_run,
                force=reprocess,
                move_sources=not reprocess,
            )
        except Exception as e:
            log.error(f"  FAILED: {e}", exc_info=True)
            result = "failed"

        if result == "processed":
            succeeded += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

    print(f"\n📊 Summary:")
    print(f"  • Input:   {total} session(s)")
    print(f"  • Groups:  {total}")
    print(f"  • Output:  {succeeded} written")
    print(f"  • Skipped: {skipped} (already processed)")
    if failed:
        print(f"  • Failed:  {failed}")

    return {
        "groups": total,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process Plaud inbox files into consolidated vault notes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be processed — no writes, no moves")
    parser.add_argument("--session", metavar="FILTER",
                        help="Process only sessions whose name contains FILTER (case-insensitive)")
    parser.add_argument("--reprocess", action="store_true",
                        help="Re-run already-processed sessions from Processed/Plaud/ — "
                             "overwrites existing output, does not move source files")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    result = run_orchestration(
        session_filter=args.session,
        dry_run=args.dry_run,
        reprocess=args.reprocess,
    )
    return 1 if result.get("failed", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
