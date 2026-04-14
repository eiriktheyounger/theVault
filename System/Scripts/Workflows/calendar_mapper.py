#!/usr/bin/env python3
"""
Calendar-to-File Mapper

Matches ingested files (especially Plaud notes) to calendar events based on timestamps.
Adds meeting metadata (title, attendees, description) to the files.

Usage:
    from calendar_mapper import CalendarMapper
    mapper = CalendarMapper("/path/to/vault")
    results = mapper.map_files_to_calendar()
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

# Import EventKit framework
try:
    from EventKit import EKEventStore, EKEntityTypeEvent
    from Foundation import NSDate, NSCalendar
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False
    logging.warning("EventKit not available - calendar mapping will be limited")

logger = logging.getLogger(__name__)


def clean_zoom_description(description: str) -> str:
    """Clean up Zoom meeting descriptions by removing dial-in numbers.

    Keeps:
    - Any text before the Zoom invite
    - Meeting URL

    Removes:
    - Zoom logo/image links
    - One tap mobile numbers
    - Join by Telephone section
    - All dial-in numbers
    - Meeting ID/Passcode (already in URL)
    """
    if not description:
        return ""

    # Check if this is a Zoom meeting (contains zoom.us)
    if "zoom.us" not in description.lower():
        return description

    lines = description.split('\n')
    cleaned_lines = []
    skip_until_blank = False

    for line in lines:
        # Skip image/logo links
        if '[https://st' in line and 'zoom' in line.lower():
            continue

        # Skip "One tap mobile:" and everything after
        if 'One tap mobile:' in line:
            skip_until_blank = True
            continue

        # Skip "Join by Telephone" and everything after
        if 'Join by Telephone' in line:
            skip_until_blank = True
            continue

        # Skip "Dial:" section
        if line.strip() == 'Dial:':
            skip_until_blank = True
            continue

        # Skip "International numbers" link
        if 'International numbers' in line:
            continue

        # Skip phone numbers (lines starting with + or toll-free patterns)
        if re.match(r'^\s*[\+\d][\d\s\-\(\)]+', line.strip()) or 'Toll-free' in line:
            continue

        # Skip Meeting ID/Passcode lines (info is in URL)
        if line.strip().startswith('Meeting ID:') or line.strip().startswith('Passcode:'):
            continue

        # Skip if we're in skip mode
        if skip_until_blank:
            if line.strip() == '':
                skip_until_blank = False
            continue

        cleaned_lines.append(line)

    # Clean up multiple blank lines
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


@dataclass
class CalendarEvent:
    """Calendar event information."""
    title: str
    start: datetime
    end: datetime
    location: str = ""
    description: str = ""
    attendees: List[str] = None
    uid: str = ""

    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []


@dataclass
class FileTimestamp:
    """Extracted timestamp from a file."""
    file_path: Path
    timestamp: datetime
    confidence: str  # "high", "medium", "low"
    source: str  # "filename", "frontmatter", "content"


class CalendarMapper:
    """
    Maps files to calendar events based on timestamps.
    """

    def __init__(self, vault_path: str, calendar_name: str = None, calendar_names: "list[str] | str" = "ExchangeCalendar"):
        """
        Initialize calendar mapper.

        Args:
            vault_path: Path to Obsidian vault root
            calendar_name: Deprecated — use calendar_names instead (kept for backwards compat)
            calendar_names: Calendar name(s) to read from. Accepts str or list[str].
        """
        self.vault_path = Path(vault_path)
        # Backwards compatibility: if old calendar_name kwarg was passed, honour it
        if calendar_name is not None:
            calendar_names = calendar_name
        if isinstance(calendar_names, str):
            calendar_names = [calendar_names]
        self.calendar_names: list[str] = calendar_names
        # Keep legacy attribute for any code that reads it directly
        self.calendar_name = self.calendar_names[0] if self.calendar_names else "ExchangeCalendar"

        # Initialize EventKit if available
        self.eventkit_store = None
        if EVENTKIT_AVAILABLE:
            self.eventkit_store = EKEventStore.alloc().init()
            if not self._request_calendar_access():
                logger.warning("Calendar access not granted - using fallback mode")
                self.eventkit_store = None

        # Stats tracking
        self.stats = {
            "files_scanned": 0,
            "files_mapped": 0,
            "files_no_timestamp": 0,
            "files_no_match": 0,
            "errors": []
        }

    def _request_calendar_access(self) -> bool:
        """Request access to calendar data."""
        if not EVENTKIT_AVAILABLE:
            return False

        from EventKit import EKAuthorizationStatusAuthorized, EKAuthorizationStatusNotDetermined
        import time

        status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)

        if status == EKAuthorizationStatusAuthorized:
            return True

        if status == EKAuthorizationStatusNotDetermined:
            granted = [False]
            completed = [False]

            def completion_handler(g, e):
                granted[0] = g
                completed[0] = True

            self.eventkit_store.requestAccessToEntityType_completion_(
                EKEntityTypeEvent,
                completion_handler
            )

            # Wait for completion
            timeout = 10
            elapsed = 0
            while not completed[0] and elapsed < timeout:
                time.sleep(0.1)
                elapsed += 0.1

            return granted[0] if completed[0] else False

        return False

    def _get_calendar_events(self, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """
        Get calendar events for a date range.

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            List of CalendarEvent objects
        """
        if not self.eventkit_store:
            logger.warning("EventKit not available, cannot fetch calendar events")
            return []

        try:
            # Get calendar by name
            calendars = self.eventkit_store.calendarsForEntityType_(EKEntityTypeEvent)
            target_calendar = None

            for calendar in calendars:
                if calendar.title() == self.calendar_name:
                    target_calendar = calendar
                    break

            if not target_calendar:
                logger.error(f"Calendar '{self.calendar_name}' not found")
                return []

            # Convert to NSDate
            ns_start = NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp())
            ns_end = NSDate.dateWithTimeIntervalSince1970_(end_date.timestamp())

            # Create predicate
            predicate = self.eventkit_store.predicateForEventsWithStartDate_endDate_calendars_(
                ns_start, ns_end, [target_calendar]
            )

            # Fetch events
            events = self.eventkit_store.eventsMatchingPredicate_(predicate)

            # Convert to CalendarEvent objects
            calendar_events = []
            for event in events:
                # Extract attendees
                attendees = []
                if event.attendees():
                    for attendee in event.attendees():
                        name = attendee.name()
                        if name:
                            attendees.append(name)

                calendar_events.append(CalendarEvent(
                    title=event.title() or "",
                    start=datetime.fromtimestamp(event.startDate().timeIntervalSince1970()),
                    end=datetime.fromtimestamp(event.endDate().timeIntervalSince1970()),
                    location=event.location() or "",
                    description=event.notes() or "",
                    attendees=attendees,
                    uid=event.eventIdentifier() or ""
                ))

            logger.info(f"Found {len(calendar_events)} events in '{self.calendar_name}' calendar")
            return calendar_events

        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return []

    def _extract_timestamp_from_plaud(self, content: str, filename: str) -> Optional[FileTimestamp]:
        """
        Extract timestamp from Plaud note.

        Plaud format typically has:
        - Filename: "10-15 Meeting Summary..." (MM-DD)
        - Summary section with date/time information

        Args:
            content: File content
            filename: Filename

        Returns:
            FileTimestamp or None
        """
        # Try to extract from filename pattern: "10-15 Meeting Summary"
        filename_match = re.search(r"^(\d{1,2})-(\d{1,2})\s+", filename)
        if filename_match:
            month = int(filename_match.group(1))
            day = int(filename_match.group(2))

            # Assume current year
            year = datetime.now().year

            # Look for time in content
            time_match = re.search(r"(?:Time|Started|Begin):\s*(\d{1,2}):(\d{2})\s*(AM|PM)?", content, re.IGNORECASE)

            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                am_pm = time_match.group(3)

                # Convert to 24-hour
                if am_pm:
                    if am_pm.upper() == "PM" and hour != 12:
                        hour += 12
                    elif am_pm.upper() == "AM" and hour == 12:
                        hour = 0

                try:
                    timestamp = datetime(year, month, day, hour, minute)
                    return FileTimestamp(
                        file_path=None,
                        timestamp=timestamp,
                        confidence="high",
                        source="filename+content"
                    )
                except ValueError:
                    pass

            # Fallback: just date, assume 9 AM
            try:
                timestamp = datetime(year, month, day, 9, 0)
                return FileTimestamp(
                    file_path=None,
                    timestamp=timestamp,
                    confidence="medium",
                    source="filename"
                )
            except ValueError:
                pass

        # Try to extract from content with various patterns
        patterns = [
            # ISO format
            r"(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})",
            # US format
            r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)?",
            # Written format
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\s+(?:at\s+)?(\d{1,2}):(\d{2})\s*(AM|PM)?",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    if "January" in pattern:  # Month name pattern
                        months = {"january": 1, "february": 2, "march": 3, "april": 4,
                                "may": 5, "june": 6, "july": 7, "august": 8,
                                "september": 9, "october": 10, "november": 11, "december": 12}
                        month = months[match.group(1).lower()]
                        day = int(match.group(2))
                        year = int(match.group(3))
                        hour = int(match.group(4))
                        minute = int(match.group(5))
                        am_pm = match.group(6) if len(match.groups()) >= 6 else None
                    else:
                        # Parse based on pattern
                        if match.group(1).startswith("2"):  # ISO format (year first)
                            year = int(match.group(1))
                            month = int(match.group(2))
                            day = int(match.group(3))
                        else:  # US format (month first)
                            month = int(match.group(1))
                            day = int(match.group(2))
                            year = int(match.group(3))

                        hour = int(match.group(4))
                        minute = int(match.group(5))
                        am_pm = match.group(6) if len(match.groups()) >= 6 else None

                    # Handle AM/PM
                    if am_pm:
                        if am_pm.upper() == "PM" and hour != 12:
                            hour += 12
                        elif am_pm.upper() == "AM" and hour == 12:
                            hour = 0

                    timestamp = datetime(year, month, day, hour, minute)
                    return FileTimestamp(
                        file_path=None,
                        timestamp=timestamp,
                        confidence="high",
                        source="content"
                    )
                except (ValueError, KeyError):
                    continue

        return None

    def _extract_timestamp_from_file(self, file_path: Path) -> Optional[FileTimestamp]:
        """
        Extract timestamp from any markdown file.

        Args:
            file_path: Path to file

        Returns:
            FileTimestamp or None
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Try Plaud-specific extraction first
            if "plaud" in file_path.name.lower() or file_path.name.endswith("-Full.md"):
                result = self._extract_timestamp_from_plaud(content, file_path.stem)
                if result:
                    result.file_path = file_path
                    return result

            # Try frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    for line in frontmatter.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip().lower()
                            if key in ["date", "created", "timestamp"]:
                                try:
                                    timestamp = datetime.fromisoformat(value.strip())
                                    return FileTimestamp(
                                        file_path=file_path,
                                        timestamp=timestamp,
                                        confidence="high",
                                        source="frontmatter"
                                    )
                                except ValueError:
                                    pass

            # Fallback: file modification time
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            return FileTimestamp(
                file_path=file_path,
                timestamp=mtime,
                confidence="low",
                source="file_mtime"
            )

        except Exception as e:
            logger.error(f"Failed to extract timestamp from {file_path}: {e}")
            return None

    def _find_matching_event(self, file_timestamp: FileTimestamp,
                            events: List[CalendarEvent]) -> Optional[CalendarEvent]:
        """
        Find calendar event that matches file timestamp.

        Args:
            file_timestamp: File timestamp
            events: List of calendar events

        Returns:
            Matching CalendarEvent or None
        """
        # Define matching windows based on confidence
        if file_timestamp.confidence == "high":
            window = timedelta(minutes=15)  # ±15 minutes
        elif file_timestamp.confidence == "medium":
            window = timedelta(hours=2)  # ±2 hours
        else:
            window = timedelta(hours=4)  # ±4 hours

        best_match = None
        best_diff = None

        for event in events:
            # Check if timestamp is within event duration or nearby
            if event.start <= file_timestamp.timestamp <= event.end:
                # Direct hit!
                return event

            # Check within window
            start_diff = abs((file_timestamp.timestamp - event.start).total_seconds())
            end_diff = abs((file_timestamp.timestamp - event.end).total_seconds())
            min_diff = min(start_diff, end_diff)

            if min_diff <= window.total_seconds():
                if best_diff is None or min_diff < best_diff:
                    best_match = event
                    best_diff = min_diff

        return best_match

    def _add_meeting_metadata_to_file(self, file_path: Path, event: CalendarEvent) -> bool:
        """
        Add meeting metadata to file frontmatter and content.

        Args:
            file_path: Path to file
            event: Calendar event

        Returns:
            True if file was updated
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Build meeting metadata section
            metadata_lines = [
                "",
                "## Meeting Details",
                f"**Meeting**: {event.title}",
                f"**Time**: {event.start.strftime('%Y-%m-%d %I:%M %p')} - {event.end.strftime('%I:%M %p')}",
            ]

            if event.location:
                metadata_lines.append(f"**Location**: {event.location}")

            if event.attendees:
                metadata_lines.append(f"**Attendees**: {', '.join(event.attendees)}")

            if event.description:
                cleaned_desc = clean_zoom_description(event.description)
                if cleaned_desc:
                    metadata_lines.append(f"**Description**: {cleaned_desc}")

            metadata_lines.append("")
            metadata_section = "\n".join(metadata_lines)

            # Check if metadata already exists
            if "## Meeting Details" in content:
                logger.info(f"Meeting metadata already exists in {file_path.name}")
                return False

            # Add metadata after frontmatter (if exists) or at beginning
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    # Insert after frontmatter
                    new_content = f"---{parts[1]}---\n{metadata_section}\n{parts[2]}"
                else:
                    new_content = metadata_section + "\n" + content
            else:
                new_content = metadata_section + "\n" + content

            # Write updated content
            file_path.write_text(new_content, encoding="utf-8")
            logger.info(f"✓ Added meeting metadata to {file_path.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add metadata to {file_path}: {e}")
            return False

    def map_files_to_calendar(self, source_dirs: Optional[List[str]] = None,
                              date_range_days: int = 30) -> Dict[str, Any]:
        """
        Map files to calendar events and add meeting metadata.

        Args:
            source_dirs: List of directories to scan (relative to vault root)
            date_range_days: Number of days to look back for calendar events

        Returns:
            Dictionary with mapping results
        """
        logger.info("Starting calendar-to-file mapping...")

        # Default source directories - scan where processed files land
        if source_dirs is None:
            source_dirs = [
                "Processed",  # Main output from ingest
                "Notes",
                "Notes/Plaud",
                "Notes/Meetings",
            ]

        # Fetch calendar events for date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=date_range_days)
        calendar_events = self._get_calendar_events(start_date, end_date)

        if not calendar_events:
            logger.warning("No calendar events found")
            return {
                "success": False,
                "error": "No calendar events available",
                "stats": self.stats
            }

        mapped_files = []
        no_timestamp_files = []
        no_match_files = []

        # Scan each source directory
        for source_dir in source_dirs:
            source_path = self.vault_path / source_dir
            if not source_path.exists():
                continue

            logger.info(f"Scanning {source_dir}...")

            for file_path in source_path.rglob("*.md"):
                self.stats["files_scanned"] += 1

                # Skip TOC and system files
                if "TOC" in file_path.name or file_path.name.startswith("."):
                    continue

                # Extract timestamp
                file_timestamp = self._extract_timestamp_from_file(file_path)
                if not file_timestamp:
                    no_timestamp_files.append(str(file_path.relative_to(self.vault_path)))
                    self.stats["files_no_timestamp"] += 1
                    continue

                # Find matching event
                matching_event = self._find_matching_event(file_timestamp, calendar_events)
                if not matching_event:
                    no_match_files.append({
                        "file": str(file_path.relative_to(self.vault_path)),
                        "timestamp": file_timestamp.timestamp.isoformat(),
                        "confidence": file_timestamp.confidence
                    })
                    self.stats["files_no_match"] += 1
                    continue

                # Add metadata to file
                if self._add_meeting_metadata_to_file(file_path, matching_event):
                    mapped_files.append({
                        "file": file_path.name,
                        "path": str(file_path.relative_to(self.vault_path)),
                        "meeting": matching_event.title,
                        "meeting_time": matching_event.start.isoformat(),
                        "confidence": file_timestamp.confidence
                    })
                    self.stats["files_mapped"] += 1

        logger.info(f"Mapping complete: {self.stats['files_mapped']} mapped, "
                   f"{self.stats['files_no_match']} no match, "
                   f"{self.stats['files_no_timestamp']} no timestamp")

        return {
            "success": True,
            "stats": self.stats,
            "mapped_files": mapped_files,
            "no_match_files": no_match_files,
            "no_timestamp_files": no_timestamp_files
        }


def main():
    """CLI entry point for testing."""
    import sys
    import json

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python calendar_mapper.py /path/to/vault [calendar_name]")
        sys.exit(1)

    vault_path = sys.argv[1]
    calendar_name = sys.argv[2] if len(sys.argv) > 2 else "Work"

    mapper = CalendarMapper(vault_path, calendar_name=calendar_name)
    results = mapper.map_files_to_calendar()

    print("\n" + "=" * 60)
    print("CALENDAR MAPPING RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
