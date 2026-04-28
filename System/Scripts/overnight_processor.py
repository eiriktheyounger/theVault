#!/usr/bin/env python3
"""
theVault Overnight Processor
Runs at 11 PM daily via cron.
Reads today's daily note, extracts tasks, summarizes chats,
updates context files, and indexes new content.
"""

import os
import sys
import json
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))  # System/Scripts/ for clean_md_processor etc.

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / 'theVault' / 'System' / 'Logs' / 'overnight.log'),
    ]
)
logger = logging.getLogger('overnight')

# Load .env from vault root (with override for cron env)
env_file = Path.home() / 'theVault' / '.env'
load_dotenv(env_file, override=True)
logger.info(f"Loaded .env from {env_file}, ANTHROPIC_API_KEY={'SET' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET'}")

VAULT_PATH = Path.home() / 'theVault'
NAS_PATH = Path('/Volumes/home/MacMiniStorage')
DAILY_BASE = VAULT_PATH / 'Vault' / 'Daily'

def check_nas():
    """Verify NAS is mounted before proceeding."""
    if not NAS_PATH.exists():
        logger.error(f"NAS not mounted at {NAS_PATH}")
        sys.exit(1)
    logger.info("NAS mount verified")

def get_today_note_path(target_date=None):
    """Get path to today's daily note or specified date."""
    now = target_date if target_date else datetime.now()
    return DAILY_BASE / now.strftime('%Y') / now.strftime('%m') / f"{now.strftime('%Y-%m-%d')}-DLY.md"

def read_section(content, start_marker, end_marker):
    """Extract text between HTML comment markers or headings."""
    # Special case: if markers are heading-based, use heading extraction
    if start_marker == "## Captures" and end_marker == "## Evening":
        pattern = r'## Captures\s*\n(.*?)(?=\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    # Default: HTML comment markers
    pattern = f"{re.escape(start_marker)}(.*?){re.escape(end_marker)}"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""

def write_section(content, start_marker, end_marker, new_text):
    """Replace text between HTML comment markers."""
    pattern = f"{re.escape(start_marker)}(.*?){re.escape(end_marker)}"
    replacement = f"{start_marker}\n{new_text}\n{end_marker}"
    if re.search(pattern, content, re.DOTALL):
        return re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        return content + f"\n\n{replacement}"

def extract_tasks_local(text, note_date=None):
    """Use local Ollama to extract actionable tasks."""
    from datetime import timedelta
    due_date = ((note_date if note_date else datetime.now()) + timedelta(days=6)).strftime('%Y-%m-%d')
    try:
        import ollama
        response = ollama.chat(
            model='gemma4:e4b',
            messages=[
                {'role': 'system', 'content': 'Extract actionable tasks from the text. Return each as a markdown task: - [ ] task description. Return ONLY the task list, nothing else. If no tasks found, return "No tasks found."'},
                {'role': 'user', 'content': text}
            ],
            options={'temperature': 0},
        )
        raw = response['message']['content']
        # Stamp default due date (note date + 6 days) onto each extracted task line
        lines = []
        for line in raw.splitlines():
            if line.strip().startswith('- [ ]') and '📅' not in line:
                line = line.rstrip() + f' 📅 {due_date}'
            lines.append(line)
        return '\n'.join(lines)
    except Exception as e:
        logger.error(f"Task extraction failed: {e}")
        return "Task extraction failed — Ollama may not be running."

def summarize_with_claude(text):
    """Use Claude Haiku to summarize daily content."""
    try:
        import anthropic
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not found in environment")
            return "Summarization failed — check API key."
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[
                {"role": "user", "content": f"Summarize this day's captures in 3-5 sentences. Group related items. Note any decisions made or commitments given:\n\n{text}"}
            ]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude summarization failed: {e}")
        return "Summarization failed — check API key."

def main(target_date=None):
    logger.info("=== Overnight processing started ===")
    check_nas()

    note_path = get_today_note_path(target_date)
    if not note_path.exists():
        logger.warning(f"No daily note found: {note_path}")
        return

    content = note_path.read_text()
    logger.info(f"Loaded daily note: {note_path} ({len(content)} chars)")

    # Extract captures (from ## Captures heading to ## Evening heading)
    captures = read_section(content, "## Captures", "## Evening")
    note_date = target_date if target_date else datetime.now()
    has_captures = bool(captures)

    if has_captures:
        logger.info(f"Processing {len(captures)} chars of captures")
        # Extract tasks (local LLM) — default due date: note date + 6 days
        tasks = extract_tasks_local(captures, note_date=note_date)
        logger.info(f"Tasks extracted: {len(tasks.splitlines())} lines")

        # Summarize (Claude API)
        summary = summarize_with_claude(captures)
        logger.info(f"Summary generated: {len(summary)} chars")
    else:
        # No captures — still run downstream steps (task_normalizer, vault_activity,
        # inject_recent_context, transcript_repair). Skip only the capture-dependent
        # extract/summarize/write steps. Bug fix 2026-04-27: previous version
        # `return`'d here, which skipped calendar/forward-back refresh on quiet days.
        logger.info("No captures found — skipping extract/summarize, still running downstream steps")
        tasks = ""
        summary = ""

    # Run task normalizer (incremental scan)
    task_report_text = ""
    try:
        from System.Scripts.task_normalizer import run_normalizer, format_report
        logger.info("Running task normalizer...")
        task_report = run_normalizer(full_scan=False, sync_reminders=True)
        task_report_text = "\n\n" + format_report(task_report)
        logger.info(f"Task normalizer complete: {task_report.get('tasks_normalized', 0)} normalized")
    except Exception as e:
        logger.error(f"Task normalizer failed: {e}")
        task_report_text = "\n\n### Task Processing\n- **Error**: normalizer failed — check logs"

    # ── Vault Activity Tracking ────────────────────────────────────────────────
    try:
        from System.Scripts.daily_vault_activity import run_vault_activity
        activity_stats = run_vault_activity(days=1, verbose=False)
        logger.info(f"Vault activity: {activity_stats.get('files_tracked', 0)} files tracked, "
                    f"{activity_stats.get('glossary_terms_added', 0)} glossary terms, "
                    f"{activity_stats.get('tags_enriched', 0)} tags enriched")
    except Exception as e:
        logger.error(f"Vault activity tracking failed: {e}")

    # ── Forward-Back / Past 7 / Recent Context Injection (ADHD/OOSOOM) ────────
    # Re-renders tonight so tomorrow morning the DLY already reflects the
    # latest state (captures processed, tasks extracted, new events, etc.)
    try:
        from inject_recent_context import run_inject
        fb_date = (note_date if isinstance(note_date, datetime) else datetime.combine(note_date, datetime.min.time())).strftime("%Y-%m-%d")
        fb_result = run_inject(
            target_date=fb_date,
            dry_run=False,
            verbose=False,
            use_gemma=True,
        )
        logger.info(
            f"Forward-back: forward_back={fb_result.get('forward_back', {}).get('events', 0)}ev "
            f"past_7={fb_result.get('past_7', {}).get('days', 0)}d "
            f"recent_context={fb_result.get('recent_context', {}).get('items', 0)}"
        )
    except Exception as e:
        logger.error(f"Forward-back injection failed: {e}")

    # ── Plaud Transcript Repair ─────────────────────────────────────────────────
    # Auto-fix any -Full.md files missing collapsible transcript sections
    # (e.g. processed on iOS or before the transcript feature was added)
    repair_text = ""
    try:
        from clean_md_processor import repair_missing_transcripts
        repair_stats = repair_missing_transcripts(dry_run=False)
        repaired = repair_stats.get("repaired", 0)
        if repaired > 0:
            logger.info(f"Transcript repair: {repaired} files fixed")
            repair_text = f"\n- Transcript repair: {repaired} file(s) updated"
        else:
            logger.info("Transcript repair: all files OK")
    except Exception as e:
        logger.error(f"Transcript repair failed: {e}")
        repair_text = f"\n- Transcript repair error: {e}"

    # Build + write overnight section (only when captures existed)
    if has_captures:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        overnight_content = f"""
### Tasks Extracted
{tasks}

### Day Summary
{summary}
{task_report_text}

### Processing Log
- Processed at: {timestamp}
- Captures length: {len(captures)} chars
- Tasks extracted: {len([l for l in tasks.splitlines() if l.strip().startswith('- [')])}
{repair_text}"""

        # Write back (WITH ERROR HANDLING)
        try:
            logger.info(f"🔷 WRITE CHECKPOINT: About to write to {note_path}")
            logger.info(f"🔷 overnight_content length: {len(overnight_content)} chars")
            logger.info(f"🔷 File exists: {note_path.exists()}, file size before: {len(content)} chars")

            new_content = write_section(
                content,
                "<!-- overnight-start -->",
                "<!-- overnight-end -->",
                overnight_content
            )

            logger.info(f"🔷 write_section returned: {len(new_content)} chars")

            note_path.write_text(new_content)

            logger.info(f"🔷 File written successfully, new size: {len(new_content)} chars")
            logger.info(f"Daily note updated: {note_path}")
        except Exception as e:
            logger.error(f"❌ WRITE FAILED: {type(e).__name__}: {e}", exc_info=True)
            logger.error(f"❌ Note path: {note_path}")
            logger.error(f"❌ Path exists: {note_path.exists()}")
            logger.error(f"❌ Parent exists: {note_path.parent.exists()}")
            raise  # Re-raise so we know the process failed
    else:
        logger.info("Skipping overnight section write (no captures to summarize)")

    # ── Monthly Summary (1st of month only) ───────────────────────────────────
    run_date = note_date if isinstance(note_date, datetime) else datetime.combine(note_date, datetime.min.time())
    if run_date.day == 1:
        prev = run_date.replace(day=1) - timedelta(days=1)
        prev_year, prev_month = prev.year, prev.month
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from generate_weekly_summary import generate_monthly_summary
            logger.info(f"Generating monthly summary for {prev_year}-{prev_month:02d}...")
            result = generate_monthly_summary(prev_year, prev_month)
            logger.info(f"Monthly summary: {result.get('status')} → {result.get('path', '')}")
        except Exception as e:
            logger.error(f"Monthly summary generation failed: {e}")

    logger.info("=== Overnight processing complete ===")

if __name__ == "__main__":
    target_date = None
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], '%Y-%m-%d')
        except ValueError:
            logger.error(f"Invalid date format: {sys.argv[1]}. Use YYYY-MM-DD")
            sys.exit(1)
    main(target_date)
