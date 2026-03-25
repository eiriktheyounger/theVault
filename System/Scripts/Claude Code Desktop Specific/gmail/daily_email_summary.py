#!/usr/bin/env python3
"""
daily_email_summary.py
-----------------------
Reads all emails imported to Vault/Email/Inbox/ for a given date,
calls Ollama (qwen2.5:7b) to summarize, and injects an ## Email section
into the day's daily note.

Usage:
    python daily_email_summary.py                    # today
    python daily_email_summary.py --date 2026-03-24  # specific date (backfill)
    python daily_email_summary.py --dry-run          # print, don't write
"""

import sys
import json
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime, date

VAULT      = Path.home() / "theVault/Vault"
EMAIL_INBOX = VAULT / "Email/Inbox"
DAILY_ROOT  = VAULT / "Daily"
OLLAMA_URL  = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"

SECTION_START = "<!-- email-summary-start -->"
SECTION_END   = "<!-- email-summary-end -->"


def daily_note_path(target_date: date) -> Path:
    return DAILY_ROOT / str(target_date.year) / f"{target_date.month:02d}" / \
           f"{target_date.strftime('%Y-%m-%d')}-DLY.md"


def emails_for_date(target_date: date) -> list[Path]:
    prefix = target_date.strftime("%Y-%m-%d")
    return sorted(EMAIL_INBOX.glob(f"{prefix}*.md"))


def read_email_content(path: Path) -> dict:
    text = path.read_text()
    lines = text.splitlines()
    subject, sender = path.stem, "Unknown"
    for line in lines:
        if line.startswith("subject:"):
            subject = line.split(":", 1)[1].strip().strip('"')
        if line.startswith("from_name:"):
            sender = line.split(":", 1)[1].strip().strip('"')
    # Get body (after second ---)
    parts = text.split("---", 2)
    body = parts[2][:800] if len(parts) >= 3 else text[:800]
    return {"path": path, "subject": subject, "sender": sender, "body": body}


def ollama_summarize(emails: list[dict]) -> str:
    if not emails:
        return "No emails imported today."

    email_text = ""
    for e in emails:
        email_text += f"\n### From: {e['sender']}\nSubject: {e['subject']}\n{e['body'][:400]}\n"

    prompt = f"""You are summarizing emails imported into a personal knowledge base for today.
Be concise. Write 3-5 sentences max. Focus on action items, key decisions, and important information.
Do not list every email — synthesize the themes and what matters.

Emails:
{email_text}

Summary:"""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 300}
    }).encode()

    req = urllib.request.Request(OLLAMA_URL, data=payload,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except Exception as e:
        return f"(Summary unavailable: {e})"


def build_section(target_date: date, emails: list[dict], summary: str) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    links = ""
    for e in emails:
        fname = e["path"].stem
        links += f"- [[Email/Inbox/{fname}]] — {e['subject']} *(from {e['sender']})*\n"

    if not links:
        links = "_No emails imported today._\n"

    return f"""## Email
{SECTION_START}
### Imported {date_str} ({len(emails)} email{"s" if len(emails) != 1 else ""})
{links}
### Summary
> {summary}

{SECTION_END}"""


def inject_into_daily(note_path: Path, section: str, dry_run: bool):
    if not note_path.exists():
        print(f"  ⚠ Daily note not found: {note_path}")
        print("  Section that would be written:")
        print(section)
        return

    content = note_path.read_text()

    # Replace existing section if present
    if SECTION_START in content and SECTION_END in content:
        before = content[:content.index(SECTION_START) - len("## Email\n")]
        after  = content[content.index(SECTION_END) + len(SECTION_END):]
        new_content = before + section + after
    else:
        # Append before last line or at end
        new_content = content.rstrip() + "\n\n" + section + "\n"

    if dry_run:
        print(f"\n── Would write to {note_path} ──")
        print(section)
    else:
        note_path.write_text(new_content)
        print(f"  ✓ Injected email summary into {note_path.name}")


def run(target_date: date, dry_run: bool):
    print(f"Daily email summary for {target_date}")
    emails = emails_for_date(target_date)
    print(f"  Found {len(emails)} imported email(s)")

    email_data = [read_email_content(p) for p in emails]

    print("  Calling Ollama for summary...")
    summary = ollama_summarize(email_data)

    section = build_section(target_date, email_data, summary)
    note_path = daily_note_path(target_date)
    inject_into_daily(note_path, section, dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    run(target, args.dry_run)
