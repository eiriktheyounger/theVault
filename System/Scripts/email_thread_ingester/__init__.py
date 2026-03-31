"""
email_thread_ingester — Extract, thread, and archive email to Obsidian vault

Usage:
  python -m System.Scripts.email_thread_ingester [options]

Options:
  --account {Exchange,Gmail,both}  Which accounts to pull from (default: both)
  --job DOMAIN                     Scan all mailboxes for sender domain (job mode)
  --dry-run                        Show what would be written, no disk writes
  --no-daily                       Skip daily note injection
  --verbose                        Debug-level logging
"""

from .tracking_db import init_db

# Ensure DB exists on first import
init_db()
