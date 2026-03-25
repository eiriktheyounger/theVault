#!/Users/ericmanchester/theVault/.venv/bin/python3
"""
Shared Gmail API authentication.
References existing token from gmail-cleanup project.
Auto-refreshes token on expiry.
"""

from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = Path.home() / "ClaudeCodeProjects/gmail-cleanup/token.json"
SCOPES = ["https://mail.google.com/"]


def get_service():
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)
