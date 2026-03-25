#!/usr/bin/env python3
"""
email_to_vault.py
-----------------
Polls Gmail for messages labeled _VAULT_IMPORT, converts each to a .md file,
places it in the Vault/Email/ hierarchy, stamps _VAULT_PROCESSED.

Usage:
    python email_to_vault.py              # process all pending
    python email_to_vault.py --dry-run    # preview only, no writes
    python email_to_vault.py --limit 10   # process at most 10

Vault structure produced:
    Vault/Email/Inbox/YYYY-MM-DD - Subject - Sender.md
    Vault/Email/People/Sender Name.md      (index per sender, appended)
    Vault/Email/Archive/YYYY/MM/           (after manual review)
"""

import re
import sys
import time
import base64
import argparse
import textwrap
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from gmail_auth import get_service

# ── PATHS ────────────────────────────────────────────────────────────────────
VAULT = Path.home() / "theVault/Vault"
EMAIL_INBOX  = VAULT / "Email/Inbox"
EMAIL_PEOPLE = VAULT / "Email/People"
EMAIL_TOPICS = VAULT / "Email/Topics"

IMPORT_LABEL   = "_VAULT_IMPORT"
PROCESSED_LABEL = "_VAULT_PROCESSED"

# ── TOPIC ROUTING ─────────────────────────────────────────────────────────────
TOPIC_RULES = [
    ("Job Search",  ["linkedin", "greenhouse", "lever.co", "workday", "icims",
                     "smartrecruiters", "recruiter", "interview", "hiring"]),
    ("Finance",     ["invoice", "receipt", "payment", "billing", "statement",
                     "stripe", "paypal", "amazon.com"]),
    ("Work",        ["harmonic", "confluence", "jira", "slack"]),
    ("Newsletter",  ["newsletter", "digest", "weekly", "roundup", "edition"]),
    ("Personal",    ["family", "mom", "dad", "personal"]),
]

# ── HELPERS ──────────────────────────────────────────────────────────────────

def get_or_create_label(svc, name):
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    for lbl in labels:
        if lbl["name"] == name:
            return lbl["id"]
    body = {"name": name, "labelListVisibility": "labelShow",
            "messageListVisibility": "show"}
    return svc.users().labels().create(userId="me", body=body).execute()["id"]


def safe_filename(text, maxlen=60):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:maxlen]


def extract_email(header):
    m = re.search(r'<(.+?)>', header)
    return m.group(1).lower() if m else header.lower().strip()


def extract_name(header):
    m = re.match(r'^"?([^"<]+)"?\s*<', header)
    if m:
        return m.group(1).strip().strip('"')
    m2 = re.search(r'<(.+?)>', header)
    if m2:
        return m2.group(1).split('@')[0].replace('.', ' ').title()
    return header.strip().split('@')[0].title()


def decode_body(payload):
    """Recursively extract plain text from message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # Strip tags simply
            clean = re.sub(r'<[^>]+>', ' ', html)
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean
    for part in payload.get("parts", []):
        result = decode_body(part)
        if result:
            return result
    return ""


def infer_topic(subject, sender_email):
    text = (subject + " " + sender_email).lower()
    for topic, keywords in TOPIC_RULES:
        if any(k in text for k in keywords):
            return topic
    return None


def fetch_full_message(svc, msg_id):
    return svc.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()


def message_to_md(msg):
    headers = {h["name"]: h["value"]
               for h in msg.get("payload", {}).get("headers", [])}
    subject    = headers.get("Subject", "(no subject)")
    from_hdr   = headers.get("From", "")
    to_hdr     = headers.get("To", "")
    date_hdr   = headers.get("Date", "")
    msg_id_hdr = headers.get("Message-ID", msg["id"])

    sender_email = extract_email(from_hdr)
    sender_name  = extract_name(from_hdr)

    ts = int(msg.get("internalDate", 0)) / 1000
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    date_str  = dt.strftime("%Y-%m-%d")
    dt_str    = dt.strftime("%Y-%m-%d %H:%M UTC")

    body = decode_body(msg.get("payload", {}))
    body_trimmed = textwrap.fill(body[:3000], width=100) if body else "(no body)"

    topic = infer_topic(subject, sender_email)
    topic_tag = f"Email/{topic}" if topic else "Email"

    fname = safe_filename(f"{date_str} - {subject} - {sender_name}")

    frontmatter = f"""---
type: email
date: {date_str}
datetime: {dt_str}
from: "{from_hdr.replace('"', "'")}"
from_email: {sender_email}
from_name: "{sender_name}"
to: "{to_hdr[:120].replace('"', "'")}"
subject: "{subject.replace('"', "'")}"
message_id: "{msg_id_hdr}"
gmail_id: {msg["id"]}
tags: [email, {topic_tag.lower().replace('/', '-')}]
---"""

    people_link = f"[[Email/People/{safe_filename(sender_name)}]]"
    topic_link  = f"[[Email/Topics/{topic}/_Index]]" if topic else ""

    body_section = f"""
# {subject}

**From:** {from_hdr}
**To:** {to_hdr}
**Date:** {dt_str}
**Sender note:** {people_link}{' | **Topic:** ' + topic_link if topic_link else ''}

---

{body_trimmed}
"""
    return fname, frontmatter + body_section, sender_name, sender_email, dt, topic


def update_people_note(sender_name, sender_email, subject, date_str, email_fname):
    path = EMAIL_PEOPLE / f"{safe_filename(sender_name)}.md"
    link = f"- [[Email/Inbox/{email_fname}]] — {subject} ({date_str})"
    if not path.exists():
        path.write_text(f"""---
type: person-email-index
name: "{sender_name}"
email: {sender_email}
---

# {sender_name}

## Emails
{link}
""")
    else:
        content = path.read_text()
        if "## Emails" in content:
            content = content.replace("## Emails\n", f"## Emails\n{link}\n")
        else:
            content += f"\n## Emails\n{link}\n"
        path.write_text(content)


def update_topic_index(topic, subject, date_str, email_fname):
    topic_dir = EMAIL_TOPICS / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    index = topic_dir / "_Index.md"
    link = f"- [[Email/Inbox/{email_fname}]] — {subject} ({date_str})"
    if not index.exists():
        index.write_text(f"""---
type: email-topic-index
topic: {topic}
---

# Email Topic: {topic}

## Emails
{link}
""")
    else:
        content = index.read_text()
        if "## Emails" in content:
            content = content.replace("## Emails\n", f"## Emails\n{link}\n")
        else:
            content += f"\n## Emails\n{link}\n"
        index.write_text(content)


# ── MAIN ─────────────────────────────────────────────────────────────────────

def run(dry_run=False, limit=None):
    svc = get_service()

    import_id    = get_or_create_label(svc, IMPORT_LABEL)
    processed_id = get_or_create_label(svc, PROCESSED_LABEL)

    # Fetch all messages with _VAULT_IMPORT that don't have _VAULT_PROCESSED
    results = svc.users().messages().list(
        userId="me",
        q=f"label:{IMPORT_LABEL} -label:{PROCESSED_LABEL}",
        maxResults=limit or 500
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        print("No messages pending import.")
        return

    print(f"Found {len(messages)} message(s) to import.")
    imported = []

    for i, m in enumerate(messages):
        msg = fetch_full_message(svc, m["id"])
        fname, content, sender_name, sender_email, dt, topic = message_to_md(msg)

        out_path = EMAIL_INBOX / f"{fname}.md"

        # Avoid collisions
        if out_path.exists():
            out_path = EMAIL_INBOX / f"{fname}-{m['id'][:6]}.md"

        if dry_run:
            print(f"  [DRY] Would write: {out_path.name}")
            print(f"        From: {sender_email} | Topic: {topic}")
        else:
            out_path.write_text(content)
            update_people_note(sender_name, sender_email,
                               msg.get("payload", {}).get("headers", [{}])[0].get("value", ""),
                               dt.strftime("%Y-%m-%d"), fname)
            if topic:
                update_topic_index(topic, fname, dt.strftime("%Y-%m-%d"), fname)

            # Stamp processed
            svc.users().messages().modify(
                userId="me", id=m["id"],
                body={"addLabelIds": [processed_id]}
            ).execute()
            print(f"  ✓ [{i+1}/{len(messages)}] {fname[:70]}")
            imported.append({"fname": fname, "sender": sender_name,
                             "date": dt.strftime("%Y-%m-%d")})
            time.sleep(0.1)

    if not dry_run:
        print(f"\n✓ Imported {len(imported)} email(s) to Vault/Email/Inbox/")
    return imported


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)
