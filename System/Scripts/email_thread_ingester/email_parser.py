"""
email_parser.py — Body cleaning and header parsing utilities

Functions:
  - clean_body(raw_body): Strip quoted text, signatures, disclaimers
  - strip_subject_prefixes(subject): Remove Re:, FW:, Fwd:, [EXTERNAL], etc.
  - html_to_text(html): Convert HTML to plain text via regex
  - extract_email_address(header): Pull bare email from "Name <email>" format
  - extract_name(header): Pull display name from "Name <email>" format
  - safe_filename(text, maxlen): Sanitize string for use as filename
"""

from __future__ import annotations

import re

try:
    from email_reply_parser import EmailReplyParser
    _HAS_REPLY_PARSER = True
except ImportError:
    _HAS_REPLY_PARSER = False


# ── HTML → Text ──────────────────────────────────────────────────────────────

def html_to_text(html: str) -> str:
    """Convert HTML to plain text using regex stripping."""
    if not html:
        return ""
    # Remove style and script blocks
    html = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block elements with newlines
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", html, flags=re.IGNORECASE)
    # Strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # Decode common HTML entities
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    # Collapse whitespace
    html = re.sub(r"\n{3,}", "\n\n", html)
    html = re.sub(r"[ \t]+", " ", html)
    return html.strip()


# ── Body Cleaning ─────────────────────────────────────────────────────────────

_DISCLAIMER_PATTERNS = [
    re.compile(r"This (e-?mail|message) (and any attachments )?is (intended|confidential).*", re.IGNORECASE | re.DOTALL),
    re.compile(r"CONFIDENTIALITY NOTICE.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"DISCLAIMER.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"This transmission.*may contain.*privileged.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"^Sent from my (iPhone|iPad|Android|Samsung|mobile device).*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Get Outlook for (iOS|Android).*$", re.IGNORECASE | re.MULTILINE),
]

_QUOTE_PATTERNS = [
    # "On Mon, Jan 1 2024, John wrote:" style
    re.compile(r"\nOn .{5,80} wrote:\s*\n", re.DOTALL),
    # "From: ... Sent: ... To: ... Subject:" block
    re.compile(r"\nFrom:.*?Subject:.*?\n", re.DOTALL),
    # "-------- Original Message --------"
    re.compile(r"\n-{3,}\s*(Original Message|Forwarded Message|Begin forwarded message)\s*-{3,}.*", re.DOTALL | re.IGNORECASE),
    # "> quoted line" style
    re.compile(r"(\n>.*)+", re.MULTILINE),
]


def clean_body(raw_body: str) -> str:
    """
    Strip quoted text, signatures, and disclaimers from email body.
    Falls back to regex patterns if email-reply-parser is not installed.
    """
    if not raw_body:
        return ""

    # Convert HTML if needed
    if re.search(r"<html|<body|<div|<p>", raw_body, re.IGNORECASE):
        raw_body = html_to_text(raw_body)

    # Use email-reply-parser if available
    if _HAS_REPLY_PARSER:
        text = EmailReplyParser.parse_reply(raw_body)
    else:
        text = raw_body
        # Fallback: strip quoted blocks
        for pattern in _QUOTE_PATTERNS:
            text = pattern.sub("", text)

    # Strip disclaimers (run after quote removal)
    for pattern in _DISCLAIMER_PATTERNS:
        text = pattern.sub("", text)

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Subject Normalization ────────────────────────────────────────────────────

_SUBJECT_PREFIX = re.compile(
    r"^(Re|RE|FW|FWD|Fwd|AW|WG|SV|TR):\s*",
    re.IGNORECASE,
)
_SUBJECT_TAG = re.compile(r"^\[.{1,30}\]\s*")  # [EXTERNAL], [EXT], [BULK], etc.


def strip_subject_prefixes(subject: str) -> str:
    """Remove Re:, FW:, Fwd:, [EXTERNAL], [EXT] and similar prefixes."""
    if not subject:
        return ""
    # Strip bracketed tags first, then reply/forward prefixes (may be multiple layers)
    prev = None
    while subject != prev:
        prev = subject
        subject = _SUBJECT_TAG.sub("", subject)
        subject = _SUBJECT_PREFIX.sub("", subject)
    return subject.strip()


# ── Header Parsing ────────────────────────────────────────────────────────────

def extract_email_address(header: str) -> str:
    """Extract bare email address from 'Display Name <email@domain.com>' format."""
    if not header:
        return ""
    m = re.search(r"<([^>]+)>", header)
    if m:
        return m.group(1).strip().lower()
    # Plain address with no display name
    return header.strip().lower()


def extract_name(header: str) -> str:
    """Extract display name from 'Display Name <email@domain.com>' format."""
    if not header:
        return ""
    m = re.match(r'^"?([^"<]+)"?\s*<', header)
    if m:
        name = m.group(1).strip().strip('"')
        if name:
            return name
    # Fall back to local part of email
    email = extract_email_address(header)
    if "@" in email:
        return email.split("@")[0].replace(".", " ").title()
    return email


# ── Filename Sanitization ────────────────────────────────────────────────────

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


def safe_filename(text: str, maxlen: int = 60) -> str:
    """Sanitize text for use as a filesystem filename (no extension)."""
    if not text:
        return "untitled"
    text = _ILLEGAL_CHARS.sub("", text)
    text = _WHITESPACE.sub("-", text.strip())
    text = re.sub(r"-{2,}", "-", text)
    text = text[:maxlen].rstrip("-")
    return text or "untitled"
