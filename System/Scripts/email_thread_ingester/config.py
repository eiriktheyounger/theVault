"""
config.py — Email Thread Ingester configuration

All paths as Path objects. Constants and lookup tables used across modules.
"""

from pathlib import Path

# ── Base Paths ────────────────────────────────────────────────────────────────

VAULT_HOME  = Path.home() / "theVault"
VAULT_ROOT  = VAULT_HOME / "Vault"

EMAIL_DIR   = VAULT_ROOT / "Email"
PEOPLE_DIR  = EMAIL_DIR / "People"

# Tracking DB lives next to the package, not in Vault
PACKAGE_DIR = Path(__file__).parent
TRACKING_DB = PACKAGE_DIR / "email_tracking.sqlite3"

# Daily notes
DAILY_DIR   = VAULT_ROOT / "Daily"

# Maximum email thread content passed to the LLM (chars)
MAX_TRANSCRIPT_CHARS = 40_000

# ── Topic Routing Rules ───────────────────────────────────────────────────────
# First match wins. Checked against (subject + sender_email).lower()

TOPIC_RULES = [
    ("Job Search",  ["linkedin", "greenhouse", "lever.co", "workday", "icims",
                     "smartrecruiters", "recruiter", "interview", "hiring",
                     "application", "opportunity", "talent"]),
    ("Finance",     ["invoice", "receipt", "payment", "billing", "statement",
                     "stripe", "paypal", "amazon.com", "refund", "tax"]),
    ("Work",        ["harmonic", "confluence", "jira", "slack", "viewlift",
                     "mobii", "tegna", "comcast", "nbcu"]),
    ("Newsletter",  ["newsletter", "digest", "weekly", "roundup", "edition",
                     "unsubscribe"]),
    ("Personal",    ["family", "mom", "dad", "personal"]),
]

# ── Domain → Organization Mapping ────────────────────────────────────────────

DOMAIN_TO_ORG = {
    "viewlift.com":     "ViewLift",
    "harmonic.com":     "Harmonic",
    "nebius.com":       "Nebius",
    "tcgplayer.com":    "TCGplayer",
    "draftkings.com":   "DraftKings",
    "nbcuni.com":       "NBCUniversal",
    "nbcuniversal.com": "NBCUniversal",
    "comcast.com":      "Comcast",
    "tegna.com":        "Tegna",
    "mobii.tv":         "Mobii",
    "akamai.com":       "Akamai",
    "microsoft.com":    "Microsoft",
    "google.com":       "Google",
    "amazon.com":       "Amazon",
    "apple.com":        "Apple",
    "linkedin.com":     "LinkedIn",
    "greenhouse.io":    "Greenhouse",
    "lever.co":         "Lever",
    "workday.com":      "Workday",
}

# ── Job-Related Domains ───────────────────────────────────────────────────────
# Used by --job mode to match sender domains when scanning all mailboxes

JOB_RELATED_DOMAINS = {
    "nebius.com",
    "tcgplayer.com",
    "draftkings.com",
    "greenhouse.io",
    "lever.co",
    "workday.com",
    "icims.com",
    "smartrecruiters.com",
    "linkedin.com",
    "jobvite.com",
    "taleo.net",
}

# ── Mail.app Account Names ────────────────────────────────────────────────────

EXCHANGE_ACCOUNT = "Exchange"
GMAIL_ACCOUNT    = "Google"

# Trigger markers
EXCHANGE_VAULT_KEYWORD = "vault"          # lowercase — checked case-insensitively in headers
GMAIL_VAULT_MAILBOX    = "_VAULT_IMPORT"
