#!/usr/bin/env python3
# EOL 2026-03-25 — This script is no longer called. Archived copy in Vault/_archive/eol-scripts/
# Kept in place to prevent import errors if anything references it. Safe to delete after 2026-04-25.
"""
TOC Generator and Backlink Manager

Automatically generates and updates Table of Contents files throughout the vault.
Creates bidirectional links between parent and child TOCs.

Usage:
    from toc_generator import TOCGenerator
    generator = TOCGenerator("/path/to/vault")
    results = generator.update_all_tocs()
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class DirectoryInfo:
    """Information about a directory."""
    path: Path
    name: str
    files: List[Path]
    subdirs: List[Path]
    toc_file: Optional[Path]
    parent_toc: Optional[Path]


class TOCGenerator:
    """
    Generates and updates TOC (Table of Contents) files throughout the vault.
    """

    def __init__(self, vault_path: str):
        """
        Initialize TOC generator.

        Args:
            vault_path: Path to Obsidian vault root
        """
        self.vault_path = Path(vault_path)

        # Directories to skip
        self.skip_dirs = {
            ".obsidian", ".trash", ".git", "node_modules",
            "__pycache__", "System", "Processed", "Vault_RAG"
        }

        # Stats tracking
        self.stats = {
            "tocs_created": 0,
            "tocs_updated": 0,
            "tocs_unchanged": 0,
            "backlinks_added": 0,
            "errors": []
        }

    def _should_process_directory(self, dir_path: Path) -> bool:
        """
        Check if directory should have a TOC.

        Args:
            dir_path: Directory path

        Returns:
            True if directory should be processed
        """
        # Skip system directories
        if any(skip in dir_path.parts for skip in self.skip_dirs):
            return False

        # Skip hidden directories
        if any(part.startswith(".") for part in dir_path.parts):
            return False

        # Only process if directory has files or subdirectories with content
        has_md_files = any(dir_path.glob("*.md"))
        has_subdirs = any(p.is_dir() for p in dir_path.iterdir()
                         if not p.name.startswith("."))

        return has_md_files or has_subdirs

    def _get_directory_info(self, dir_path: Path) -> DirectoryInfo:
        """
        Gather information about a directory.

        Args:
            dir_path: Directory path

        Returns:
            DirectoryInfo object
        """
        # Get all markdown files (exclude TOCs and system files)
        files = sorted([
            f for f in dir_path.glob("*.md")
            if not f.name.startswith("!")
            and "TOC" not in f.name
            and not f.name.startswith(".")
        ])

        # Get subdirectories
        subdirs = sorted([
            d for d in dir_path.iterdir()
            if d.is_dir()
            and self._should_process_directory(d)
        ])

        # Find existing TOC file
        toc_file = None
        toc_patterns = [
            f"!{dir_path.name} TOC.md",
            f"{dir_path.name} TOC.md",
            f"{dir_path.name} Vault TOC.md",
        ]

        for pattern in toc_patterns:
            potential_toc = dir_path / pattern
            if potential_toc.exists():
                toc_file = potential_toc
                break

        # Find parent TOC
        parent_toc = None
        if dir_path != self.vault_path:
            parent_dir = dir_path.parent
            for pattern in [f"!{parent_dir.name} TOC.md", f"{parent_dir.name} TOC.md"]:
                potential_parent = parent_dir / pattern
                if potential_parent.exists():
                    parent_toc = potential_parent
                    break

        return DirectoryInfo(
            path=dir_path,
            name=dir_path.name,
            files=files,
            subdirs=subdirs,
            toc_file=toc_file,
            parent_toc=parent_toc
        )

    def _generate_display_name(self, file_path: Path) -> str:
        """
        Generate a human-readable display name from filename.

        Args:
            file_path: Path to file

        Returns:
            Display name
        """
        name = file_path.stem

        # Remove date prefixes (MM-DD, YYYY-MM-DD, etc.)
        name = re.sub(r"^\d{1,2}-\d{1,2}\s+", "", name)
        name = re.sub(r"^\d{4}-\d{2}-\d{2}\s+", "", name)

        # Remove common suffixes
        name = re.sub(r"\s*-?\s*Full$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*_\d+_$", "", name)

        # Clean up underscores
        name = name.replace("_", " ")

        return name.strip()

    def _extract_file_summary(self, file_path: Path, max_length: int = 150) -> str:
        """
        Extract a brief summary from file content.

        Args:
            file_path: Path to file
            max_length: Maximum summary length

        Returns:
            Summary text
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Skip frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2]

            # Find first paragraph or heading
            lines = content.strip().split("\n")
            for line in lines:
                line = line.strip()
                # Skip empty lines, hashtags, horizontal rules
                if not line or line.startswith("#") or line.startswith("---"):
                    continue
                # Remove markdown formatting
                line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)  # Links
                line = re.sub(r"[*_`]", "", line)  # Bold, italic, code
                if len(line) > 20:  # Minimum meaningful length
                    if len(line) > max_length:
                        return line[:max_length] + "..."
                    return line

            return ""

        except Exception:
            return ""

    def _generate_toc_content(self, dir_info: DirectoryInfo) -> str:
        """
        Generate TOC markdown content for a directory.

        Args:
            dir_info: Directory information

        Returns:
            TOC markdown content
        """
        lines = []

        # Title (with emoji if it's a top-level directory)
        is_root = dir_info.path == self.vault_path
        is_major_section = dir_info.path.parent == self.vault_path

        if is_root:
            lines.append("# 🗂️ Vault Table of Contents")
        else:
            # Use emoji if directory name starts with one
            title = f"# {dir_info.name}"
            if not is_major_section:
                title += f" - {dir_info.path.parent.name}"
            lines.append(title)

        lines.append("")
        lines.append("## Overview")
        lines.append(f"*Generated TOC for {dir_info.name}*")
        lines.append("")

        # Files in this directory
        if dir_info.files:
            lines.append("## Files in This Directory")
            for file_path in dir_info.files:
                display_name = self._generate_display_name(file_path)
                summary = self._extract_file_summary(file_path)

                # Create Obsidian link
                if summary:
                    lines.append(f"- [[{file_path.name}|{display_name}]] - {summary}")
                else:
                    lines.append(f"- [[{file_path.name}|{display_name}]]")

            lines.append("")

        # Subdirectories
        if dir_info.subdirs:
            lines.append("## Subdirectories")
            for subdir in dir_info.subdirs:
                # Find subdir's TOC
                subdir_toc = None
                for pattern in [f"!{subdir.name} TOC.md", f"{subdir.name} TOC.md"]:
                    potential_toc = subdir / pattern
                    if potential_toc.exists():
                        subdir_toc = potential_toc
                        break

                if subdir_toc:
                    lines.append(f"- [[{subdir_toc.name}|{subdir.name}]]")
                else:
                    lines.append(f"- {subdir.name}")

            lines.append("")

        # Navigation (parent link)
        if dir_info.parent_toc:
            lines.append("## Navigation")
            parent_name = dir_info.parent_toc.parent.name
            lines.append(f"↑ [[{dir_info.parent_toc.name}|{parent_name}]]")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}")

        return "\n".join(lines)

    def _content_hash(self, content: str) -> str:
        """
        Generate hash of content (ignoring timestamps).

        Args:
            content: Content to hash

        Returns:
            MD5 hash
        """
        # Remove timestamp line before hashing
        content_no_ts = re.sub(r"\*\*Last Updated\*\*:.*", "", content)
        return hashlib.md5(content_no_ts.encode()).hexdigest()

    def _update_toc_file(self, dir_info: DirectoryInfo, toc_content: str) -> Tuple[bool, str]:
        """
        Create or update TOC file.

        Args:
            dir_info: Directory information
            toc_content: Generated TOC content

        Returns:
            Tuple of (changed, action_taken)
        """
        try:
            # Determine TOC filename
            if dir_info.path == self.vault_path:
                toc_filename = "!Vault TOC.md"
            elif dir_info.path.parent == self.vault_path:
                toc_filename = f"!{dir_info.name} TOC.md"
            else:
                toc_filename = f"{dir_info.name} {dir_info.path.parent.name} TOC.md"

            toc_path = dir_info.path / toc_filename

            # Check if content changed
            if toc_path.exists():
                existing_content = toc_path.read_text(encoding="utf-8")
                if self._content_hash(existing_content) == self._content_hash(toc_content):
                    return False, "unchanged"

                toc_path.write_text(toc_content, encoding="utf-8")
                return True, "updated"
            else:
                toc_path.write_text(toc_content, encoding="utf-8")
                return True, "created"

        except Exception as e:
            raise Exception(f"Failed to write TOC: {e}")

    def update_all_tocs(self) -> Dict:
        """
        Update all TOC files in the vault.

        Returns:
            Dictionary with update results
        """
        logger.info("Starting TOC generation...")

        processed_dirs = []

        # Walk the vault directory tree
        for dir_path in sorted(self.vault_path.rglob("*")):
            if not dir_path.is_dir():
                continue

            if not self._should_process_directory(dir_path):
                continue

            try:
                # Get directory info
                dir_info = self._get_directory_info(dir_path)

                # Generate TOC content
                toc_content = self._generate_toc_content(dir_info)

                # Update TOC file
                changed, action = self._update_toc_file(dir_info, toc_content)

                if action == "created":
                    self.stats["tocs_created"] += 1
                    logger.info(f"✓ Created TOC for {dir_info.name}")
                elif action == "updated":
                    self.stats["tocs_updated"] += 1
                    logger.info(f"✓ Updated TOC for {dir_info.name}")
                else:
                    self.stats["tocs_unchanged"] += 1

                processed_dirs.append({
                    "directory": str(dir_path.relative_to(self.vault_path)),
                    "action": action,
                    "files_count": len(dir_info.files),
                    "subdirs_count": len(dir_info.subdirs)
                })

            except Exception as e:
                error_msg = f"Error processing {dir_path}: {e}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)

        logger.info(f"TOC generation complete: {self.stats['tocs_created']} created, "
                   f"{self.stats['tocs_updated']} updated, "
                   f"{self.stats['tocs_unchanged']} unchanged")

        return {
            "success": len(self.stats["errors"]) == 0,
            "stats": self.stats,
            "processed_dirs": processed_dirs,
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
        print("Usage: python toc_generator.py /path/to/vault")
        sys.exit(1)

    vault_path = sys.argv[1]

    generator = TOCGenerator(vault_path)
    results = generator.update_all_tocs()

    print("\n" + "=" * 60)
    print("TOC GENERATION RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
