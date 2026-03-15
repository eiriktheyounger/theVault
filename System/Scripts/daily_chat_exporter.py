#!/usr/bin/env python3
"""
daily_chat_exporter.py — Export Claude.ai conversations for a given date to vault-ready markdown.

Reads conversation data via the Claude.ai web API using the locally stored session cookie.
Cookie decryption uses macOS Keychain (same mechanism as the desktop app).

Usage:
    python daily_chat_exporter.py [--date YYYY-MM-DD] [--output-dir /path/to/dir]

Output:
    {output_dir}/{date}_daily_chat.md

Requirements:
    - macOS (uses Keychain for cookie decryption)
    - cryptography package (already in venv)
    - requests package (already in venv)
    - Claude.ai desktop app must have been opened recently (active session)
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import date as Date, datetime, timezone
from pathlib import Path

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ── constants ─────────────────────────────────────────────────────────────────
COOKIES_DB = Path.home() / "Library/Application Support/Claude/Cookies"
LOCAL_STORAGE_DB = Path.home() / "Library/Application Support/Claude/Local Storage/leveldb"
KEYCHAIN_SERVICE = "Claude Safe Storage"
API_BASE = "https://claude.ai/api"
DEFAULT_OUTPUT_DIR = Path.home() / "theVault/Inbox/Markdown"
PAGE_SIZE = 50

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Claude/1.1.3363 Chrome/144.0.7559.173 Electron/40.4.1 Safari/537.36"
    ),
    "anthropic-client-sha": "1.1.3363",
}


# ── cookie decryption ─────────────────────────────────────────────────────────

def _get_safe_storage_key() -> bytes:
    """Get the AES key material from macOS Keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not read '{KEYCHAIN_SERVICE}' from Keychain. "
            "Is the Claude desktop app installed?"
        )
    raw = result.stdout.strip().strip("'")
    return raw.encode("utf-8")


def _derive_aes_key(password: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=16,
        salt=b"saltysalt",
        iterations=1003,
        backend=default_backend(),
    )
    return kdf.derive(password)


def _decrypt_cookie(enc_value: bytes, key: bytes) -> str | None:
    """Decrypt a Chromium v10/v11 encrypted cookie value."""
    if len(enc_value) <= 3:
        return None
    prefix = enc_value[:3]
    if prefix not in (b"v10", b"v11"):
        try:
            return enc_value.decode("utf-8")
        except Exception:
            return None
    encrypted = enc_value[3:]
    iv = b" " * 16
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    try:
        decrypted = decryptor.update(encrypted) + decryptor.finalize()
    except Exception:
        return None
    pad_len = decrypted[-1]
    if 1 <= pad_len <= 16:
        decrypted = decrypted[:-pad_len]
    clean = re.sub(r"[^\x20-\x7E]", "", decrypted.decode("utf-8", errors="replace"))
    # Strip AES garbage prefix (everything up to and including backtick separator)
    if "`" in clean:
        clean = clean.split("`", 1)[1]
    return clean.strip() or None


def load_cookies() -> dict[str, str]:
    """Decrypt and return all Claude.ai cookies keyed by name."""
    if not COOKIES_DB.exists():
        raise FileNotFoundError(
            f"Claude cookies database not found at {COOKIES_DB}. "
            "Is the Claude desktop app installed?"
        )
    aes_key = _derive_aes_key(_get_safe_storage_key())
    conn = sqlite3.connect(str(COOKIES_DB))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'"
    )
    rows = cursor.fetchall()
    conn.close()

    cookies: dict[str, str] = {}
    for name, enc in rows:
        val = _decrypt_cookie(enc, aes_key)
        if val:
            cookies[name] = val
    return cookies


# ── org ID discovery ──────────────────────────────────────────────────────────

def _get_org_id_from_local_storage() -> str | None:
    """Try to read the org ID from Claude's Local Storage LevelDB strings."""
    try:
        import glob
        ldb_files = glob.glob(str(LOCAL_STORAGE_DB / "*.ldb")) + glob.glob(
            str(LOCAL_STORAGE_DB / "*.log")
        )
        uuid_pattern = re.compile(
            rb"organization.*?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
        )
        for fpath in ldb_files:
            with open(fpath, "rb") as f:
                data = f.read()
            m = uuid_pattern.search(data)
            if m:
                return m.group(1).decode("ascii")
    except Exception:
        pass
    return None


def get_org_id(session: requests.Session) -> str:
    """Resolve the organisation ID for the current user."""
    # Try reading from local storage first (fast, no network)
    org_id = _get_org_id_from_local_storage()
    if org_id:
        return org_id
    # Fallback: ask the API
    resp = session.get(f"{API_BASE}/auth/current_account", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    memberships = data.get("account", {}).get("memberships", [])
    if memberships:
        return memberships[0]["organization"]["uuid"]
    raise RuntimeError("Could not determine organisation ID")


# ── API helpers ───────────────────────────────────────────────────────────────

def build_session(cookies: dict[str, str]) -> requests.Session:
    sess = requests.Session()
    for name, val in cookies.items():
        sess.cookies.set(name, val, domain=".claude.ai")
    return sess


def list_conversations_for_date(
    session: requests.Session, org_id: str, target_date: Date
) -> list[dict]:
    """
    Fetch all conversations whose created_at or updated_at falls on target_date (UTC).
    Paginates until conversations are older than target_date.
    """
    target_str = target_date.isoformat()
    matching = []
    offset = 0

    while True:
        resp = session.get(
            f"{API_BASE}/organizations/{org_id}/chat_conversations"
            f"?limit={PAGE_SIZE}&offset={offset}",
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break

        found_any_candidate = False
        for conv in page:
            created = conv.get("created_at", "")[:10]
            updated = conv.get("updated_at", "")[:10]
            if created == target_str or updated == target_str:
                matching.append(conv)
                found_any_candidate = True
            # Conversations are in reverse chronological order by updated_at.
            # Once we see an updated_at earlier than our target, stop.
            elif updated < target_str and created < target_str:
                return matching

        if not found_any_candidate and offset > 0:
            # No matches in this page and we've passed the target date
            break

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return matching


def fetch_messages(
    session: requests.Session, org_id: str, conv_uuid: str
) -> list[dict]:
    """Fetch all messages for a conversation."""
    resp = session.get(
        f"{API_BASE}/organizations/{org_id}/chat_conversations/{conv_uuid}",
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("chat_messages", [])


# ── markdown rendering ────────────────────────────────────────────────────────

def _extract_text(text_field: str | None) -> str:
    """Clean up message text for markdown output."""
    if not text_field:
        return ""
    # Collapse excessive blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text_field.strip())
    return text


def _format_time(iso_ts: str) -> str:
    """Convert ISO timestamp to HH:MM local time string."""
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%H:%M")
    except Exception:
        return iso_ts[:16]


def render_conversation(conv: dict, messages: list[dict], index: int) -> str:
    """Render a single conversation as a markdown section."""
    title = conv.get("name") or "(untitled)"
    created_ts = conv.get("created_at", "")
    time_str = _format_time(created_ts) if created_ts else "??"
    msg_count = len(messages)

    lines: list[str] = []
    lines.append(f"## Conversation {index}: {title}")
    lines.append(f"*{time_str} — {msg_count} message{'s' if msg_count != 1 else ''}*")
    lines.append("")

    for msg in messages:
        sender = msg.get("sender", "unknown")
        text = _extract_text(msg.get("text"))
        if not text:
            continue
        label = "**Eric:**" if sender == "human" else "**Claude:**"
        lines.append(f"{label} {text}")
        lines.append("")

    return "\n".join(lines)


def render_markdown(target_date: Date, conversations: list[tuple[dict, list[dict]]]) -> str:
    """Render the full export file as markdown."""
    date_str = target_date.isoformat()
    yyyy_mm = date_str[:7]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    frontmatter = "\n".join([
        "---",
        f"tags: [daily-chat, claude-export, {yyyy_mm}]",
        f"date: {date_str}",
        "type: daily-chat",
        "source: claude-app",
        "---",
    ])

    header = f"# Daily Claude.ai Conversations — {date_str}"

    sections: list[str] = [frontmatter, "", header, ""]

    if not conversations:
        sections.append("*No Claude.ai conversations found for this date.*")
        sections.append("")
    else:
        for i, (conv, messages) in enumerate(conversations, start=1):
            sections.append(render_conversation(conv, messages, i))
            sections.append("---")
            sections.append("")

    sections.extend([
        f"*Exported: {now}*",
        "*Source: Claude.ai desktop app*",
        "",
    ])

    return "\n".join(sections)


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Claude.ai conversations for a date to vault markdown."
    )
    parser.add_argument(
        "--date",
        default=Date.today().isoformat(),
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        target_date = Date.fromisoformat(args.date)
    except ValueError:
        print(f"ERROR: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir).expanduser()
    output_file = output_dir / f"{target_date.isoformat()}_daily_chat.md"

    print(f"Exporting Claude.ai conversations for {target_date.isoformat()}...")

    # ── authenticate ──────────────────────────────────────────────────────────
    try:
        cookies = load_cookies()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if "sessionKey" not in cookies:
        print(
            "ERROR: No sessionKey cookie found. Open the Claude desktop app and sign in.",
            file=sys.stderr,
        )
        return 1

    session = build_session(cookies)

    # ── resolve org ID ────────────────────────────────────────────────────────
    try:
        org_id = get_org_id(session)
    except Exception as e:
        print(f"ERROR: Could not resolve org ID: {e}", file=sys.stderr)
        return 1

    print(f"  Org ID: {org_id}")

    # ── fetch conversations ───────────────────────────────────────────────────
    try:
        conv_list = list_conversations_for_date(session, org_id, target_date)
    except requests.HTTPError as e:
        print(
            f"ERROR: Claude.ai API returned {e.response.status_code}. "
            "Session may have expired — open the Claude desktop app to refresh it.",
            file=sys.stderr,
        )
        # Write stub so downstream pipeline has something to index
        output_dir.mkdir(parents=True, exist_ok=True)
        stub = render_markdown(target_date, [])
        output_file.write_text(stub, encoding="utf-8")
        print(f"  Wrote stub (API error): {output_file}")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to fetch conversations: {e}", file=sys.stderr)
        return 1

    print(f"  Found {len(conv_list)} conversation(s) on {target_date.isoformat()}")

    # ── fetch messages for each conversation ──────────────────────────────────
    conversations_with_messages: list[tuple[dict, list[dict]]] = []
    total_messages = 0

    for conv in conv_list:
        conv_uuid = conv["uuid"]
        try:
            messages = fetch_messages(session, org_id, conv_uuid)
        except Exception as e:
            print(f"  WARNING: Could not fetch messages for '{conv.get('name')}': {e}")
            messages = []
        conversations_with_messages.append((conv, messages))
        total_messages += len(messages)
        print(f"  • {conv.get('name', '(untitled)')[:60]} — {len(messages)} messages")

    # ── write output ──────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(target_date, conversations_with_messages)
    output_file.write_text(markdown, encoding="utf-8")

    print(f"\nDone: {len(conv_list)} conversations, {total_messages} messages")
    print(f"Output: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
