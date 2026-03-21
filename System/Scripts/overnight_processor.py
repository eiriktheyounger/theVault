#!/usr/bin/env python3
"""
theVault Overnight Processor
Runs at 10 PM daily via cron.
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

def get_today_note_path():
    """Get path to today's daily note."""
    now = datetime.now()
    return DAILY_BASE / now.strftime('%Y') / now.strftime('%m') / f"{now.strftime('%Y-%m-%d')}-DLY.md"

def read_section(content, start_marker, end_marker):
    """Extract text between HTML comment markers or headings."""
    # Special case: if markers are heading-based, use heading extraction
    if start_marker == "## Captures" and end_marker == "## Evening":
        pattern = r'## Captures\s*\n(.*?)(?=\n## Evening)'
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

def extract_tasks_local(text):
    """Use local Ollama to extract actionable tasks."""
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
        return response['message']['content']
    except Exception as e:
        logger.error(f"Task extraction failed: {e}")
        return "Task extraction failed — Ollama may not be running."

def summarize_with_claude(text):
    """Use Claude Haiku to summarize daily content."""
    try:
        import anthropic
        client = anthropic.Anthropic()
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

def main():
    logger.info("=== Overnight processing started ===")
    check_nas()

    note_path = get_today_note_path()
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

    # Extract tasks (local LLM)
    tasks = extract_tasks_local(captures)
    logger.info(f"Tasks extracted: {len(tasks.splitlines())} lines")

    # Summarize (Claude API)
    summary = summarize_with_claude(captures)
    logger.info(f"Summary generated: {len(summary)} chars")

    # Build overnight section
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    overnight_content = f"""
### Tasks Extracted
{tasks}

### Day Summary
{summary}

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
    main()
