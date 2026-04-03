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
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load .env from vault root
load_dotenv(Path.home() / 'theVault' / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / 'theVault' / 'System' / 'Logs' / 'overnight.log'),
    ]
)
logger = logging.getLogger('overnight')

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
            model='qwen2.5:7b',
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
    if not captures:
        logger.info("No captures found — skipping processing")
        return

    logger.info(f"Processing {len(captures)} chars of captures")

    # Extract tasks (local LLM) — default due date: note date + 6 days
    note_date = target_date if target_date else datetime.now()
    tasks = extract_tasks_local(captures, note_date=note_date)
    logger.info(f"Tasks extracted: {len(tasks.splitlines())} lines")

    # Summarize (Claude API)
    summary = summarize_with_claude(captures)
    logger.info(f"Summary generated: {len(summary)} chars")

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

    # Build overnight section
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
"""

    # Write back
    new_content = write_section(
        content,
        "<!-- overnight-start -->",
        "<!-- overnight-end -->",
        overnight_content
    )

    note_path.write_text(new_content)
    logger.info(f"Daily note updated: {note_path}")
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
