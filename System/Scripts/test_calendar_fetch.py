#!/usr/bin/env python3
"""
Test Google Calendar API access.
Lists all calendars and fetches next events from target calendars.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar.readonly",
]

CREDENTIALS_FILE = Path("/Users/ericmanchester/ClaudeCodeProjects/gmail-cleanup/credentials.json")
TOKEN_FILE = Path("/Users/ericmanchester/theVault/System/Scripts/calendar_token.json")

TARGET_CALENDARS = [
    "ExchangeCalendar",
    "eric.manchester@gmail.com",
    "Bella",
    "Alyssa Manchester",
    "Lulu",
    "Rachel",
    "Class Schedule",
    "Holidays in United States",
]


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def main():
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    # List all calendars
    print("=== ALL CALENDARS ===")
    calendars_result = service.calendarList().list().execute()
    calendars = calendars_result.get("items", [])
    cal_by_name = {}
    for cal in calendars:
        summary = cal.get("summary", "")
        cal_id = cal["id"]
        print(f"  {summary!r:40s} id={cal_id}")
        cal_by_name[summary] = cal_id

    # Fetch next events from target calendars
    now = datetime.now(timezone.utc).isoformat()
    print("\n=== NEXT EVENTS (target calendars) ===")
    for name in TARGET_CALENDARS:
        cal_id = cal_by_name.get(name)
        if not cal_id:
            print(f"\n[{name}] NOT FOUND in calendar list")
            continue
        print(f"\n[{name}]")
        events_result = service.events().list(
            calendarId=cal_id,
            timeMin=now,
            maxResults=3,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
        if not events:
            print("  (no upcoming events)")
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            print(f"  {start}  {e.get('summary', '(no title)')}")


if __name__ == "__main__":
    main()
