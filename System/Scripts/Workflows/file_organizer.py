#!/usr/bin/env python3
"""
File Organizer - Auto Note Mover Logic for Workflow Integration

Moves files to appropriate vault locations based on:
- Tags in content
- Frontmatter properties
- Filename patterns
- Content analysis

Usage:
    from file_organizer import FileOrganizer
    organizer = FileOrganizer("/path/to/vault")
    results = organizer.organize_files()
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)


@dataclass
class MoveRule:
    """Represents a file movement rule."""
    name: str
    condition: callable  # Function that takes FileInfo, returns bool
    destination: str  # Relative path from vault root
    priority: int = 50  # Lower = higher priority


@dataclass
class FileInfo:
    """Information extracted from a markdown file."""
    path: Path
    filename: str
    content: str
    frontmatter: Dict[str, Any]
    tags: List[str]
    title: Optional[str]
    created_date: Optional[datetime]


class FileOrganizer:
    """
    Organizes vault files based on rules similar to Obsidian Auto Note Mover.
    """

    def __init__(self, vault_path: str):
        """
        Initialize file organizer.

        Args:
            vault_path: Path to Obsidian vault root
        """
        self.vault_path = Path(vault_path)
        self.rules: List[MoveRule] = []
        self._init_default_rules()

        # Stats tracking
        self.stats = {
            "files_scanned": 0,
            "files_moved": 0,
            "files_skipped": 0,
            "errors": []
        }

    def _init_default_rules(self):
        """Initialize default file organization rules."""

        # Rule 1: Meeting notes by filename pattern
        self.add_rule(
            name="Meeting notes by filename",
            condition=lambda f: (
                f.filename.startswith("Meeting_") or
                f.filename.startswith("Weekly Meeting_") or
                f.filename.startswith("10-") or  # Plaud meeting summaries
                "meeting" in f.filename.lower()
            ),
            destination="Notes/Meetings",
            priority=10
        )

        # Rule 2: Plaud recordings
        self.add_rule(
            name="Plaud recordings",
            condition=lambda f: (
                f.filename.endswith("-Full.md") or
                "plaud" in f.filename.lower() or
                "recording" in f.title.lower() if f.title else False
            ),
            destination="Notes/Plaud",
            priority=15
        )

        # Rule 3: Email content
        self.add_rule(
            name="Email notes",
            condition=lambda f: (
                "#email" in f.tags or
                f.frontmatter.get("type") == "email" or
                f.frontmatter.get("source") == "email"
            ),
            destination="Notes/Email",
            priority=20
        )

        # Rule 4: Work-related content
        self.add_rule(
            name="Work content",
            condition=lambda f: (
                "#work" in f.tags or
                "#harmonic" in f.tags or
                f.frontmatter.get("category") == "work"
            ),
            destination="HarmonicInternal",
            priority=25
        )

        # Rule 5: Personal content
        self.add_rule(
            name="Personal content",
            condition=lambda f: (
                "#personal" in f.tags or
                f.frontmatter.get("category") == "personal"
            ),
            destination="Personal",
            priority=30
        )

        # Rule 6: Standards and reference
        self.add_rule(
            name="Standards",
            condition=lambda f: (
                f.frontmatter.get("type") == "standard" or
                "#standard" in f.tags
            ),
            destination="🗂️ References/Standards",
            priority=35
        )

        # Rule 7: Health & wellness
        self.add_rule(
            name="Health content",
            condition=lambda f: (
                "#health" in f.tags or
                "#fitness" in f.tags or
                "#medical" in f.tags or
                "#wellness" in f.tags
            ),
            destination="Personal/Health & Wellness",
            priority=40
        )

        # Rule 8: Archive tag
        self.add_rule(
            name="Archive",
            condition=lambda f: "#archive" in f.tags,
            destination="Archive",
            priority=5  # High priority
        )

        # Rule 9: Technology/programming
        self.add_rule(
            name="Technology",
            condition=lambda f: (
                "#code" in f.tags or
                "#programming" in f.tags or
                "#tech" in f.tags or
                f.frontmatter.get("category") == "technology"
            ),
            destination="Personal/Technology & Learning",
            priority=45
        )

        # Rule 10: Tasks and todos
        self.add_rule(
            name="Tasks",
            condition=lambda f: (
                "#task" in f.tags or
                "#todo" in f.tags or
                f.frontmatter.get("type") == "task"
            ),
            destination="Tasks",
            priority=50
        )

    def add_rule(self, name: str, condition: callable, destination: str, priority: int = 50):
        """
        Add a file organization rule.

        Args:
            name: Human-readable rule name
            condition: Function that takes FileInfo and returns bool
            destination: Relative path from vault root
            priority: Rule priority (lower = higher priority)
        """
        rule = MoveRule(name=name, condition=condition, destination=destination, priority=priority)
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)

    def _extract_file_info(self, file_path: Path) -> Optional[FileInfo]:
        """
        Extract metadata from a markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            FileInfo object or None if extraction fails
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Extract frontmatter
            frontmatter = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1]
                    for line in fm_text.strip().split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            frontmatter[key.strip()] = value.strip()

            # Extract tags (both #tag and frontmatter tags)
            tags = []
            # Hashtags in content
            tags.extend(re.findall(r"#([\w\-/]+)", content))
            # Frontmatter tags
            if "tags" in frontmatter:
                fm_tags = frontmatter["tags"]
                if isinstance(fm_tags, str):
                    tags.extend([t.strip() for t in fm_tags.split(",")])

            # Normalize tags (remove duplicates, add # prefix)
            tags = ["#" + t.lstrip("#") for t in tags]
            tags = list(set(tags))

            # Extract title
            title = frontmatter.get("title")
            if not title:
                # Try to find first heading
                match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                if match:
                    title = match.group(1).strip()

            # Get created date
            created_date = None
            if "created" in frontmatter:
                try:
                    created_date = datetime.fromisoformat(frontmatter["created"])
                except:
                    pass

            return FileInfo(
                path=file_path,
                filename=file_path.stem,
                content=content,
                frontmatter=frontmatter,
                tags=tags,
                title=title,
                created_date=created_date
            )

        except Exception as e:
            logger.error(f"Failed to extract info from {file_path}: {e}")
            return None

    def _find_matching_rule(self, file_info: FileInfo) -> Optional[MoveRule]:
        """
        Find the first matching rule for a file.

        Args:
            file_info: File metadata

        Returns:
            Matching MoveRule or None
        """
        for rule in self.rules:
            try:
                if rule.condition(file_info):
                    return rule
            except Exception as e:
                logger.warning(f"Rule '{rule.name}' failed for {file_info.filename}: {e}")
                continue

        return None

    def _should_move_file(self, file_path: Path) -> bool:
        """
        Check if file should be considered for moving.

        Args:
            file_path: Path to file

        Returns:
            True if file should be processed
        """
        # Skip hidden files and directories
        if any(part.startswith(".") for part in file_path.parts):
            return False

        # Skip system directories
        skip_dirs = {
            ".obsidian", ".trash", ".git", "node_modules",
            "__pycache__", "System", "Templates"
        }
        if any(part in skip_dirs for part in file_path.parts):
            return False

        # Only process markdown files
        if file_path.suffix != ".md":
            return False

        # Skip TOC files
        if "TOC" in file_path.name or file_path.name.startswith("!"):
            return False

        return True

    def _move_file(self, file_info: FileInfo, destination: str) -> Tuple[bool, str]:
        """
        Move file to destination directory.

        Args:
            file_info: File metadata
            destination: Relative destination path from vault root

        Returns:
            Tuple of (success, message)
        """
        try:
            dest_dir = self.vault_path / destination
            dest_path = dest_dir / file_info.path.name

            # Check if already in correct location
            if file_info.path.parent == dest_dir:
                return False, "Already in correct location"

            # Create destination directory if needed
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Handle filename conflicts
            if dest_path.exists():
                # Add timestamp to avoid overwriting
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = dest_path.stem
                dest_path = dest_dir / f"{stem}_{timestamp}.md"
                logger.warning(f"Filename conflict, using: {dest_path.name}")

            # Move the file
            shutil.move(str(file_info.path), str(dest_path))

            return True, f"Moved to {destination}"

        except Exception as e:
            error_msg = f"Failed to move {file_info.filename}: {e}"
            logger.error(error_msg)
            return False, error_msg

    def organize_files(self, source_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Organize files in the vault based on rules.

        Args:
            source_dirs: List of directories to scan (relative to vault root).
                        If None, scans common ingest locations.

        Returns:
            Dictionary with organization results
        """
        logger.info("Starting file organization...")

        # Default source directories (scan where processed files land)
        if source_dirs is None:
            source_dirs = [
                "Processed",  # Main output from ingest
                "Notes",
                "Inbox",  # Manual additions
            ]

        moved_files = []
        skipped_files = []

        # Scan each source directory
        for source_dir in source_dirs:
            source_path = self.vault_path / source_dir
            if not source_path.exists():
                logger.warning(f"Source directory not found: {source_path}")
                continue

            logger.info(f"Scanning {source_dir}...")

            # Find all markdown files
            for file_path in source_path.rglob("*.md"):
                self.stats["files_scanned"] += 1

                if not self._should_move_file(file_path):
                    self.stats["files_skipped"] += 1
                    continue

                # Extract file info
                file_info = self._extract_file_info(file_path)
                if not file_info:
                    self.stats["errors"].append(f"Failed to read {file_path}")
                    continue

                # Find matching rule
                rule = self._find_matching_rule(file_info)
                if not rule:
                    skipped_files.append({
                        "file": str(file_path.relative_to(self.vault_path)),
                        "reason": "No matching rule"
                    })
                    self.stats["files_skipped"] += 1
                    continue

                # Move file
                success, message = self._move_file(file_info, rule.destination)
                if success:
                    moved_files.append({
                        "file": file_info.filename,
                        "from": str(file_path.parent.relative_to(self.vault_path)),
                        "to": rule.destination,
                        "rule": rule.name
                    })
                    self.stats["files_moved"] += 1
                    logger.info(f"✓ {file_info.filename} → {rule.destination} ({rule.name})")
                else:
                    if "Already in correct location" not in message:
                        self.stats["errors"].append(message)

        logger.info(f"Organization complete: {self.stats['files_moved']} moved, "
                   f"{self.stats['files_skipped']} skipped, "
                   f"{len(self.stats['errors'])} errors")

        return {
            "success": len(self.stats["errors"]) == 0,
            "stats": self.stats,
            "moved_files": moved_files,
            "skipped_files": skipped_files,
            "errors": self.stats["errors"]
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
        print("Usage: python file_organizer.py /path/to/vault [source_dirs...]")
        sys.exit(1)

    vault_path = sys.argv[1]
    source_dirs = sys.argv[2:] if len(sys.argv) > 2 else None

    organizer = FileOrganizer(vault_path)
    results = organizer.organize_files(source_dirs=source_dirs)

    print("\n" + "=" * 60)
    print("FILE ORGANIZATION RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
