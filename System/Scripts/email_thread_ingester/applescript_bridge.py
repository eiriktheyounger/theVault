"""
applescript_bridge.py — Extract emails from Mail.app via AppleScript

Two extraction modes:
  - exchange_vault_emails(): Inbox messages with `keywords: vault` category (green)
  - gmail_vault_emails(): Messages in the _VAULT_IMPORT mailbox
  - job_emails(domain): All mailboxes, filtered by sender domain (--job mode)

Critical AppleScript rules (learned from prior sessions):
  - Exchange mailbox name is "Inbox" (capital I), NOT "INBOX"
  - Build results via string concatenation, NOT array append (gets error -10006)
  - Message indices are volatile — always capture message-id
  - Date filtering in AppleScript is unreliable — iterate all, filter in Python
  - Use "|" as field delimiter, "\n" as record delimiter
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Optional

from . import config

log = logging.getLogger("email_thread_ingester.applescript")

# Field separator used in AppleScript output
_SEP = "|"
_REC_SEP = "\n---RECORD---\n"

# ── AppleScript Templates ─────────────────────────────────────────────────────

_EXCHANGE_SCRIPT = r"""
tell application "Mail"
    set resultText to ""
    set targetAccount to missing value
    repeat with acct in accounts
        if name of acct contains "Exchange" or name of acct contains "Harmonic" then
            set targetAccount to acct
            exit repeat
        end if
    end repeat
    if targetAccount is missing value then
        return "ERROR: No Exchange account found"
    end if
    set targetMailbox to missing value
    repeat with mb in mailboxes of targetAccount
        if name of mb is "Inbox" then
            set targetMailbox to mb
            exit repeat
        end if
    end repeat
    if targetMailbox is missing value then
        return "ERROR: No Inbox mailbox found"
    end if
    set msgList to messages of targetMailbox
    repeat with theMsg in msgList
        try
            -- Quick check: subject or sender contains "vault" (avoid reading all headers for 2300+ msgs)
            set msgSubject to subject of theMsg
            set msgSender to sender of theMsg
            set subjectLower to do shell script "echo " & quoted form of msgSubject & " | tr '[:upper:]' '[:lower:]'"
            set senderLower to do shell script "echo " & quoted form of msgSender & " | tr '[:upper:]' '[:lower:]'"

            set isVault to false
            if subjectLower contains "vault" or senderLower contains "vault" then
                set isVault to true
            else
                -- Only read headers if quick check fails
                set msgHeaders to ""
                try
                    set msgHeaders to all headers of theMsg
                end try
                if msgHeaders is not "" then
                    set headerLower to do shell script "echo " & quoted form of msgHeaders & " | tr '[:upper:]' '[:lower:]'"
                    if headerLower contains "vault" then
                        set isVault to true
                    end if
                end if
            end if

            if isVault then
                set msgDate to date received of theMsg
                set msgID to message id of theMsg
                set msgBody to content of theMsg
                set msgHeaders to ""
                try
                    set msgHeaders to all headers of theMsg
                end try
                set recipientList to ""
                repeat with r in to recipients of theMsg
                    if recipientList is "" then
                        set recipientList to address of r
                    else
                        set recipientList to recipientList & "," & address of r
                    end if
                end repeat
                -- Get In-Reply-To from headers
                set inReplyTo to ""
                if msgHeaders contains "In-Reply-To:" then
                    try
                        set inReplyTo to do shell script "echo " & quoted form of msgHeaders & " | grep -i 'in-reply-to:' | head -1 | sed 's/[Ii]n-[Rr]eply-[Tt]o: //'"
                    end try
                end if
                set dateStr to (year of msgDate as string) & "-" & text -2 thru -1 of ("0" & (month of msgDate as integer)) & "-" & text -2 thru -1 of ("0" & (day of msgDate as string)) & "T" & text -2 thru -1 of ("0" & (hours of msgDate as string)) & ":" & text -2 thru -1 of ("0" & (minutes of msgDate as string)) & ":00Z"
                set oneRecord to msgID & "|" & msgSubject & "|" & msgSender & "|" & recipientList & "|" & dateStr & "|" & inReplyTo & "|" & msgHeaders & "|" & msgBody
                if resultText is "" then
                    set resultText to oneRecord
                else
                    set resultText to resultText & "\n---RECORD---\n" & oneRecord
                end if
            end if
        end try
    end repeat
    return resultText
end tell
"""

_GMAIL_SCRIPT = r"""
tell application "Mail"
    set resultText to ""
    set targetMailbox to missing value
    repeat with acct in accounts
        repeat with mb in mailboxes of acct
            if name of mb is "_VAULT_IMPORT" then
                set targetMailbox to mb
                exit repeat
            end if
        end repeat
        if targetMailbox is not missing value then exit repeat
    end repeat
    if targetMailbox is missing value then
        return "ERROR: _VAULT_IMPORT mailbox not found"
    end if
    set msgList to messages of targetMailbox
    repeat with theMsg in msgList
        try
            set msgSubject to subject of theMsg
            set msgSender to sender of theMsg
            set msgDate to date received of theMsg
            set msgID to message id of theMsg
            set msgBody to content of theMsg
            set msgHeaders to ""
            try
                set msgHeaders to all headers of theMsg
            end try
            set recipientList to ""
            repeat with r in to recipients of theMsg
                if recipientList is "" then
                    set recipientList to address of r
                else
                    set recipientList to recipientList & "," & address of r
                end if
            end repeat
            set inReplyTo to ""
            if msgHeaders contains "In-Reply-To:" then
                try
                    set inReplyTo to do shell script "echo " & quoted form of msgHeaders & " | grep -i 'in-reply-to:' | head -1 | sed 's/[Ii]n-[Rr]eply-[Tt]o: //'"
                end try
            end if
            set dateStr to (year of msgDate as string) & "-" & text -2 thru -1 of ("0" & (month of msgDate as integer)) & "-" & text -2 thru -1 of ("0" & (day of msgDate as string)) & "T" & text -2 thru -1 of ("0" & (hours of msgDate as string)) & ":" & text -2 thru -1 of ("0" & (minutes of msgDate as string)) & ":00Z"
            set oneRecord to msgID & "|" & msgSubject & "|" & msgSender & "|" & recipientList & "|" & dateStr & "|" & inReplyTo & "|" & msgHeaders & "|" & msgBody
            if resultText is "" then
                set resultText to oneRecord
            else
                set resultText to resultText & "\n---RECORD---\n" & oneRecord
            end if
        end try
    end repeat
    return resultText
end tell
"""

_JOB_SCAN_SCRIPT_TEMPLATE = r"""
tell application "Mail"
    set resultText to ""
    set domainFilter to "{domain}"
    repeat with acct in accounts
        repeat with mb in mailboxes of acct
            try
                set msgList to messages of mb
                repeat with theMsg in msgList
                    try
                        set msgSender to sender of theMsg
                        if msgSender contains domainFilter then
                            set msgSubject to subject of theMsg
                            set msgDate to date received of theMsg
                            set msgID to message id of theMsg
                            set msgBody to content of theMsg
                            set msgHeaders to ""
                            try
                                set msgHeaders to all headers of theMsg
                            end try
                            set recipientList to ""
                            repeat with r in to recipients of theMsg
                                if recipientList is "" then
                                    set recipientList to address of r
                                else
                                    set recipientList to recipientList & "," & address of r
                                end if
                            end repeat
                            set inReplyTo to ""
                            if msgHeaders contains "In-Reply-To:" then
                                try
                                    set inReplyTo to do shell script "echo " & quoted form of msgHeaders & " | grep -i 'in-reply-to:' | head -1 | sed 's/[Ii]n-[Rr]eply-[Tt]o: //'"
                                end try
                            end if
                            set dateStr to (year of msgDate as string) & "-" & text -2 thru -1 of ("0" & (month of msgDate as integer)) & "-" & text -2 thru -1 of ("0" & (day of msgDate as string)) & "T" & text -2 thru -1 of ("0" & (hours of msgDate as string)) & ":" & text -2 thru -1 of ("0" & (minutes of msgDate as string)) & ":00Z"
                            set acctName to name of acct
                            set oneRecord to msgID & "|" & msgSubject & "|" & msgSender & "|" & recipientList & "|" & dateStr & "|" & inReplyTo & "|" & msgHeaders & "|" & msgBody & "|" & acctName
                            if resultText is "" then
                                set resultText to oneRecord
                            else
                                set resultText to resultText & "\n---RECORD---\n" & oneRecord
                            end if
                        end if
                    end try
                end repeat
            end try
        end repeat
    end repeat
    return resultText
end tell
"""

# ── AppleScript Runner ────────────────────────────────────────────────────────

def _run_applescript(script: str) -> Optional[str]:
    """Run AppleScript, return stdout string or None on error."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            log.error(f"AppleScript error: {result.stderr.strip()}")
            return None
        output = result.stdout.strip()
        if output.startswith("ERROR:"):
            log.error(f"AppleScript returned error: {output}")
            return None
        return output
    except subprocess.TimeoutExpired:
        log.error("AppleScript timed out after 120s")
        return None
    except Exception as e:
        log.error(f"Failed to run AppleScript: {e}")
        return None


# ── Output Parser ─────────────────────────────────────────────────────────────

def _parse_output(raw: str, account: str, has_account_field: bool = False) -> list[dict]:
    """
    Parse pipe-delimited AppleScript output into list of message dicts.

    Fields: message_id | subject | sender | recipients | date | in_reply_to | headers | body
    Optional 9th field (has_account_field=True): account_name
    """
    messages = []
    if not raw:
        return messages

    for record in raw.split(_REC_SEP):
        record = record.strip()
        if not record:
            continue
        parts = record.split(_SEP, 8 if has_account_field else 7)
        if len(parts) < 7:
            log.debug(f"Skipping malformed record ({len(parts)} fields)")
            continue

        try:
            msg_id    = parts[0].strip()
            subject   = parts[1].strip()
            sender    = parts[2].strip()
            recips    = [r.strip() for r in parts[3].split(",") if r.strip()]
            date_str  = parts[4].strip()
            in_reply  = parts[5].strip()
            headers   = parts[6].strip()
            body      = parts[7].strip() if len(parts) > 7 else ""
            acct_name = parts[8].strip() if has_account_field and len(parts) > 8 else account

            # Parse date
            date_received = _parse_date(date_str)

            messages.append({
                "message_id":  msg_id or f"unknown-{hash(record)}",
                "subject":     subject,
                "sender":      sender,
                "recipients":  recips,
                "date_received": date_received,
                "date_str":    date_str,
                "in_reply_to": in_reply or None,
                "headers":     headers,
                "body":        body,
                "account":     acct_name,
            })
        except Exception as e:
            log.debug(f"Failed to parse record: {e}")
            continue

    return messages


def _parse_date(date_str: str) -> datetime:
    """Parse ISO datetime string, falling back to now."""
    if not date_str:
        return datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(fmt)])
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    log.debug(f"Could not parse date: {date_str!r}")
    return datetime.now(timezone.utc)


# ── Public Extraction Functions ───────────────────────────────────────────────

def extract_exchange_vault_emails() -> list[dict]:
    """
    Extract Exchange Inbox messages tagged with `keywords: vault`.
    Returns list of message dicts.
    """
    log.info("Extracting Exchange vault-tagged emails...")
    raw = _run_applescript(_EXCHANGE_SCRIPT)
    if raw is None:
        log.warning("Exchange extraction returned nothing")
        return []
    messages = _parse_output(raw, account=config.EXCHANGE_ACCOUNT)
    log.info(f"  Found {len(messages)} Exchange message(s)")
    return messages


def extract_gmail_vault_emails() -> list[dict]:
    """
    Extract Gmail messages in the _VAULT_IMPORT mailbox.
    Returns list of message dicts.
    """
    log.info("Extracting Gmail _VAULT_IMPORT emails...")
    raw = _run_applescript(_GMAIL_SCRIPT)
    if raw is None:
        log.warning("Gmail extraction returned nothing")
        return []
    messages = _parse_output(raw, account=config.GMAIL_ACCOUNT)
    log.info(f"  Found {len(messages)} Gmail message(s)")
    return messages


def extract_job_emails(domain: str) -> list[dict]:
    """
    Scan ALL mailboxes for messages from the given domain.
    Used by --job mode to bulk-import job application emails.
    Returns list of message dicts.
    """
    log.info(f"Scanning all mailboxes for emails from domain: {domain}")
    script = _JOB_SCAN_SCRIPT_TEMPLATE.replace("{domain}", domain)
    raw = _run_applescript(script)
    if raw is None:
        log.warning(f"Job domain scan for {domain!r} returned nothing")
        return []
    messages = _parse_output(raw, account="unknown", has_account_field=True)
    log.info(f"  Found {len(messages)} message(s) matching {domain!r}")
    return messages
