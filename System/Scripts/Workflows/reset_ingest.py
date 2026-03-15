#!/usr/bin/env python3
"""
Reset Ingest - Recovery Tool for NeroSpicy

Moves processed files back to inbox and deletes outputs for a given time period.
Used for testing and recovering from failed processing.

Usage:
    python reset_ingest.py --hours 1     # Reset last 1 hour
    python reset_ingest.py --hours 24    # Reset last 24 hours
    python reset_ingest.py --hours 336   # Reset last 14 days
    python reset_ingest.py --dry-run     # Show what would be done
"""

import argparse
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Paths - HARDCODED FOR SAFETY
# Only these specific directories will be affected
PROCESSED_PATH = Path.home() / "theVault" / "Processed" / "Plaud"
INBOX_PATH = Path.home() / "theVault" / "Inbox" / "Plaud" / "MarkdownOnly"

# VAULT SAFETY: Only these specific subdirectories - NOT the whole Vault
VAULT_PROCESSED = Path.home() / "theVault" / "Vault" / "Processed"
# For Notes, we ONLY delete files matching specific patterns (-Full.md, -Clean.md)
VAULT_NOTES = Path.home() / "theVault" / "Vault" / "Notes"

# Safety patterns - file types that will be moved back from Vault/Notes
# Includes processed outputs AND Plaud component files that need consolidation
SAFE_DELETE_PATTERNS = [
    "-Full.md",
    "-Clean.md",
    # Plaud component suffixes (for files that were processed individually)
    "-Summary.md",
    "-Voice Note.md",
    "-To-do List.md",
    "-Meeting Minutes.md",
    "-Quantitative Data.md",
    "-Teaching Note.md",
    "-Client Needs.md",
    "-Intent Analysis.md",
    "-Highlights.md",
]


def get_files_in_timeframe(directory: Path, hours: float, pattern: str = "*.md") -> list:
    """Get files added/moved/modified within the given timeframe."""
    if not directory.exists():
        return []

    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_timestamp = cutoff.timestamp()

    files = []
    for file_path in directory.rglob(pattern):
        if file_path.is_file():
            stat = file_path.stat()
            # Use max of ctime and mtime to capture both:
            # - ctime: when file was moved/renamed (added to this directory)
            # - mtime: when file content was modified (created/updated)
            latest_time = max(stat.st_ctime, stat.st_mtime)
            if latest_time >= cutoff_timestamp:
                files.append(file_path)

    return sorted(files, key=lambda f: max(f.stat().st_ctime, f.stat().st_mtime), reverse=True)


def reset_ingest(hours: float, dry_run: bool = False) -> dict:
    """
    Reset ingest for the given time period.

    Returns dict with counts and actions taken.
    """
    results = {
        "hours": hours,
        "dry_run": dry_run,
        "moved_to_inbox": 0,
        "deleted_full": 0,
        "deleted_vault": 0,
        "errors": [],
        "actions": []
    }

    cutoff = datetime.now() - timedelta(hours=hours)
    print(f"🔄 Reset Ingest - Last {hours} hours")
    print(f"   Cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
    if dry_run:
        print("   🧪 DRY RUN - No files will be modified")
    print()

    # Step 1: Find and move source files from Processed back to Inbox
    print("📂 Step 1: Move source files from Processed → Inbox")
    processed_files = get_files_in_timeframe(PROCESSED_PATH, hours)

    # Filter out -Full.md files (these are consolidated, not source)
    source_files = [f for f in processed_files if not f.name.endswith("-Full.md")]
    full_files = [f for f in processed_files if f.name.endswith("-Full.md")]

    if source_files:
        for file_path in source_files:
            dest = INBOX_PATH / file_path.name
            action = f"   ← {file_path.name}"
            print(action)
            results["actions"].append(f"Move: {file_path.name} → Inbox")

            if not dry_run:
                try:
                    # Handle duplicate names
                    if dest.exists():
                        stem = dest.stem
                        suffix = dest.suffix
                        counter = 1
                        while dest.exists():
                            dest = INBOX_PATH / f"{stem}-{counter}{suffix}"
                            counter += 1

                    shutil.move(str(file_path), str(dest))
                    results["moved_to_inbox"] += 1
                except Exception as e:
                    error = f"Failed to move {file_path.name}: {e}"
                    results["errors"].append(error)
                    print(f"   ❌ {error}")
            else:
                results["moved_to_inbox"] += 1
    else:
        print("   (no source files found)")

    print(f"   Total: {results['moved_to_inbox']} files")
    print()

    # Step 2: Delete -Full.md files from Processed
    print("🗑️  Step 2: Delete -Full.md files from Processed")
    if full_files:
        for file_path in full_files:
            action = f"   ✕ {file_path.name}"
            print(action)
            results["actions"].append(f"Delete: {file_path.name}")

            if not dry_run:
                try:
                    file_path.unlink()
                    results["deleted_full"] += 1
                except Exception as e:
                    error = f"Failed to delete {file_path.name}: {e}"
                    results["errors"].append(error)
                    print(f"   ❌ {error}")
            else:
                results["deleted_full"] += 1
    else:
        print("   (no -Full.md files found)")

    print(f"   Total: {results['deleted_full']} files")
    print()

    # Step 3: Delete output files from Vault/Processed
    print("🗑️  Step 3: Delete output files from Vault/Processed")
    vault_processed_files = get_files_in_timeframe(VAULT_PROCESSED, hours)

    if vault_processed_files:
        for file_path in vault_processed_files:
            action = f"   ✕ {file_path.relative_to(VAULT_PROCESSED)}"
            print(action)
            results["actions"].append(f"Delete Vault: {file_path.name}")

            if not dry_run:
                try:
                    file_path.unlink()
                    results["deleted_vault"] += 1
                except Exception as e:
                    error = f"Failed to delete {file_path.name}: {e}"
                    results["errors"].append(error)
                    print(f"   ❌ {error}")
            else:
                results["deleted_vault"] += 1
    else:
        print("   (no files found)")

    print(f"   Total: {results['deleted_vault']} files")
    print()

    # Step 4: Also check Vault/Notes for files matching SAFE_DELETE_PATTERNS
    # - Processed outputs (-Full.md, -Clean.md): DELETE
    # - Component files (Summary, Voice Note, etc.): MOVE to inbox for re-consolidation
    print("🔄 Step 4: Handle files from Vault/Notes")
    print(f"   (Files matching: {', '.join(SAFE_DELETE_PATTERNS[:3])}...)")
    vault_notes_files = get_files_in_timeframe(VAULT_NOTES, hours)
    # Filter to ONLY files matching safe patterns
    output_notes = [f for f in vault_notes_files if any(f.name.endswith(p) for p in SAFE_DELETE_PATTERNS)]

    # Patterns that should be deleted (processed outputs)
    DELETE_PATTERNS = ["-Full.md", "-Clean.md"]
    # Everything else should be moved back to inbox

    deleted_notes = 0
    moved_notes = 0
    if output_notes:
        for file_path in output_notes:
            # Determine if this should be deleted or moved
            should_delete = any(file_path.name.endswith(p) for p in DELETE_PATTERNS)

            if should_delete:
                action = f"   ✕ Delete: {file_path.name}"
                print(action)
                results["actions"].append(f"Delete Note: {file_path.name}")

                if not dry_run:
                    try:
                        file_path.unlink()
                        deleted_notes += 1
                    except Exception as e:
                        error = f"Failed to delete {file_path.name}: {e}"
                        results["errors"].append(error)
                        print(f"   ❌ {error}")
                else:
                    deleted_notes += 1
            else:
                # Move component file back to inbox
                dest_path = PLAUD_INBOX / file_path.name
                action = f"   ↩ Move to inbox: {file_path.name}"
                print(action)
                results["actions"].append(f"Move to inbox: {file_path.name}")

                if not dry_run:
                    try:
                        shutil.move(str(file_path), str(dest_path))
                        moved_notes += 1
                        results["restored_plaud"] += 1
                    except Exception as e:
                        error = f"Failed to move {file_path.name}: {e}"
                        results["errors"].append(error)
                        print(f"   ❌ {error}")
                else:
                    moved_notes += 1
                    results["restored_plaud"] += 1
    else:
        print("   (no processed notes found)")

    results["deleted_vault"] += deleted_notes
    print(f"   Deleted: {deleted_notes}, Moved to inbox: {moved_notes}")
    print()

    # Summary
    print("=" * 50)
    print("📊 Summary")
    print(f"   • Moved to inbox: {results['moved_to_inbox']} (from Processed/Plaud)")
    print(f"   • Moved from Notes: {moved_notes} (component files)")
    print(f"   • Deleted -Full.md: {results['deleted_full']}")
    print(f"   • Deleted from Vault: {results['deleted_vault']}")

    if results["errors"]:
        print(f"   • Errors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"     - {error}")

    if dry_run:
        print("\n🧪 DRY RUN - No files were modified")
    else:
        print("\n✅ Reset complete")

    return results


def main():
    parser = argparse.ArgumentParser(description="Reset ingest for testing/recovery")
    parser.add_argument("--hours", type=float, default=1, help="Time period in hours (max 336 = 14 days)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")

    args = parser.parse_args()

    # Validate hours
    if args.hours <= 0 or args.hours > 336:
        print("❌ Hours must be between 0 and 336 (14 days)")
        return 1

    results = reset_ingest(args.hours, args.dry_run)

    return 0 if not results["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
