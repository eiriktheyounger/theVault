#!/usr/bin/env python3
"""
Morning Workflow Orchestrator

Handles all morning startup and ingest tasks with progress tracking.

Steps (Mac Mini):
0. Verify NAS Mount (Mac Mini only)
1. Start Services (Ollama, LLM, RAG, UI)
2. Sync Calendar (Harmonic → Work)
3. Create Daily Dashboard
4. Run Ingest (all inbox types)
5. Organize Files (Auto Note Mover logic)
6. Map to Calendar (match files to meetings)
7. Update TOCs (generate/update all TOCs)

Steps (Other Machines):
1. Start Services (Ollama, LLM, RAG, UI)
2. Sync Calendar (Harmonic → Work)
3. Create Daily Dashboard
4. Run Ingest (all inbox types)
5. Organize Files (Auto Note Mover logic)
6. Map to Calendar (match files to meetings)
7. Update TOCs (generate/update all TOCs)

Usage:
    from morning_workflow import MorningWorkflow
    workflow = MorningWorkflow(date="2025-11-19", callback=progress_callback)
    result = workflow.run()
"""

import logging
import sys
import subprocess
import time
import socket
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Callable, Any

# Add parent to path for imports
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import our new workflow components
from file_organizer import FileOrganizer
from calendar_mapper import CalendarMapper
# EOL 2026-03-25 — TOC generation permanently disabled per Eric
# from toc_generator import TOCGenerator

logger = logging.getLogger(__name__)


class WorkflowStep:
    """Represents a single workflow step with progress tracking."""

    def __init__(self, step_num: int, name: str, total_steps: int):
        self.step_num = step_num
        self.name = name
        self.total_steps = total_steps
        self.status = "pending"  # pending, running, complete, error
        self.progress = 0  # 0-100
        self.started_at = None
        self.completed_at = None
        self.summary_lines = []
        self.errors = []

    def start(self):
        """Mark step as started."""
        self.status = "running"
        self.started_at = time.time()
        logger.info(f"Step {self.step_num}/{self.total_steps}: {self.name} - Started")

    def update_progress(self, progress: int, summary_lines: list):
        """Update step progress."""
        self.progress = min(100, max(0, progress))
        self.summary_lines = summary_lines[-5:]  # Keep last 5 lines

    def complete(self, summary_lines: list = None):
        """Mark step as completed."""
        self.status = "complete"
        self.progress = 100
        self.completed_at = time.time()
        if summary_lines:
            self.summary_lines = summary_lines[-5:]
        logger.info(f"Step {self.step_num}/{self.total_steps}: {self.name} - Complete "
                   f"({self.completed_at - self.started_at:.1f}s)")

    def error(self, error_msg: str):
        """Mark step as failed."""
        self.status = "error"
        self.completed_at = time.time()
        self.errors.append(error_msg)
        logger.error(f"Step {self.step_num}/{self.total_steps}: {self.name} - Error: {error_msg}")

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "step_num": self.step_num,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": (self.completed_at - self.started_at) if self.completed_at else None,
            "summary_lines": self.summary_lines,
            "errors": self.errors
        }


class MorningWorkflow:
    """Orchestrates the morning workflow with progress tracking."""

    def __init__(self, date: Optional[str] = None, callback: Optional[Callable] = None):
        """
        Initialize morning workflow.

        Args:
            date: Target date (YYYY-MM-DD), defaults to today
            callback: Optional callback function(step: WorkflowStep) for progress updates
        """
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.callback = callback
        self.vault_path = str(Path.home() / "theVault" / "Vault")

        # Detect machine profile
        self.hostname = socket.gethostname()
        self.is_mac_mini = "mini" in self.hostname.lower()

        # Define workflow steps
        # Mac Mini gets Step 0 for NAS verification
        total_steps = 9 if self.is_mac_mini else 8

        if self.is_mac_mini:
            self.steps = [
                WorkflowStep(0, "Verify NAS Mount", total_steps),
                WorkflowStep(1, "Start Services", total_steps),
                WorkflowStep(2, "Sync Calendar (Harmonic → Work)", total_steps),
                WorkflowStep(3, "Create Daily Dashboard", total_steps),
                WorkflowStep(4, "Run Ingest", total_steps),
                WorkflowStep(5, "Import Flagged Emails", total_steps),
                WorkflowStep(6, "Organize Files", total_steps),
                WorkflowStep(7, "Map to Calendar", total_steps),
                WorkflowStep(8, "Update TOCs", total_steps),
            ]
        else:
            self.steps = [
                WorkflowStep(1, "Start Services", total_steps),
                WorkflowStep(2, "Sync Calendar (Harmonic → Work)", total_steps),
                WorkflowStep(3, "Create Daily Dashboard", total_steps),
                WorkflowStep(4, "Run Ingest", total_steps),
                WorkflowStep(5, "Import Flagged Emails", total_steps),
                WorkflowStep(6, "Organize Files", total_steps),
                WorkflowStep(7, "Map to Calendar", total_steps),
                WorkflowStep(8, "Update TOCs", total_steps),
            ]

        self.errors = []
        self.started_at = None
        self.completed_at = None
        self.nas_check_failed = False  # Track NAS check status for retry

    def _notify_callback(self, step: WorkflowStep):
        """Notify callback of step update."""
        if self.callback:
            try:
                self.callback(step)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def _get_step_index(self, step_num: int) -> int:
        """
        Get the array index for a given step number.

        On Mac Mini: Step 0 is at index 0, Step 1 at index 1, etc.
        On other machines: Step 1 is at index 0, Step 2 at index 1, etc.
        """
        if self.is_mac_mini:
            return step_num
        else:
            return step_num - 1

    def _step_verify_nas(self) -> bool:
        """Step 0: Verify NAS is mounted (Mac Mini only)."""
        if not self.is_mac_mini:
            return True  # Skip on non-Mac Mini machines

        step = self.steps[0]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(25, ["Checking NAS mount..."])
            self._notify_callback(step)

            nas_path = Path("/Volumes/home/MacMiniStorage")
            vault_symlink = Path.home() / "theVault" / "Vault"

            errors = []

            # Check NAS mount
            if not nas_path.exists():
                errors.append("❌ NAS not mounted at /Volumes/home/MacMiniStorage")
                errors.append("   Please mount NAS and click Retry")
            elif not nas_path.is_dir():
                errors.append("❌ NAS path exists but is not a directory")
            else:
                step.update_progress(50, ["✓ NAS mounted", "Checking Vault symlink..."])
                self._notify_callback(step)

            # Check Vault symlink
            if not vault_symlink.exists():
                errors.append("❌ Vault symlink not found at ~/theVault/Vault")
            elif not vault_symlink.is_symlink():
                errors.append("❌ ~/theVault/Vault exists but is not a symlink")
            else:
                # Verify symlink points to NAS
                try:
                    resolved = vault_symlink.resolve()
                    if not str(resolved).startswith(str(nas_path)):
                        errors.append(f"❌ Vault symlink points to {resolved} instead of NAS")
                except Exception as e:
                    errors.append(f"❌ Could not resolve Vault symlink: {e}")

            if errors:
                self.nas_check_failed = True
                error_msg = "\n".join(errors)
                step.error(error_msg)
                self._notify_callback(step)
                return False

            # Success!
            step.complete([
                "✓ NAS mounted",
                f"✓ Path: {nas_path}",
                "✓ Vault symlink accessible",
                f"✓ Target: {vault_symlink.resolve()}"
            ])
            self._notify_callback(step)
            self.nas_check_failed = False
            return True

        except Exception as e:
            self.nas_check_failed = True
            step.error(f"NAS verification error: {str(e)}")
            self._notify_callback(step)
            return False

    def _step_start_services(self) -> bool:
        """Step 1: Start all services."""
        step = self.steps[self._get_step_index(1)]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(20, ["Starting services..."])
            self._notify_callback(step)

            # Call the service starter as subprocess
            start_script = scripts_dir / "Services" / "start_all.py"
            result = subprocess.run(
                [sys.executable, str(start_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=60,
                close_fds=True
            )

            # Parse output for summary
            lines = []
            for line in (result.stdout + result.stderr).split("\n"):
                if "✓" in line or "started" in line.lower() or "running" in line.lower():
                    lines.append(line.strip())

            if result.returncode == 0:
                step.complete(lines or ["All services started"])
                self._notify_callback(step)
                return True
            else:
                step.error(f"Service startup failed: {result.stderr}")
                self._notify_callback(step)
                return False

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def _step_sync_calendar(self) -> bool:
        """Step 2: Sync calendar (Harmonic → Work)."""
        step = self.steps[self._get_step_index(2)]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(30, ["Syncing Harmonic calendar to Work calendar..."])
            self._notify_callback(step)

            # Call calendar sync script with deletion enabled
            calendar_script = scripts_dir / "Calendar" / "sync_calendar.py"
            result = subprocess.run(
                [sys.executable, str(calendar_script), "--date", self.date, "--allow-delete"],
                capture_output=True,
                text=True,
                timeout=60,
                close_fds=True
            )

            if result.returncode == 0:
                # Parse output for event count
                lines = result.stdout.split("\n")
                event_count = "calendar synced"
                for line in lines:
                    if "event" in line.lower() or "sync" in line.lower():
                        event_count = line.strip()
                        break

                step.complete([
                    f"Calendar synced for {self.date}",
                    event_count,
                    "Harmonic → Work calendar sync complete"
                ])
                self._notify_callback(step)
                return True
            else:
                step.error(f"Calendar sync failed: {result.stderr}")
                self._notify_callback(step)
                return False

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def _step_create_dashboard(self) -> bool:
        """Step 3: Create daily dashboard."""
        step = self.steps[self._get_step_index(3)]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(25, ["Syncing calendar..."])
            self._notify_callback(step)

            # Call dashboard generator as subprocess
            dashboard_script = scripts_dir / "generate_daily_dashboard.py"
            result = subprocess.run(
                [sys.executable, str(dashboard_script), self.date],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=120,
                close_fds=True
            )

            if result.returncode == 0:
                step.complete([
                    f"Dashboard created for {self.date}",
                    f"Saved to TimeTracking/{self.date[:4]}/{self.date[5:7]}/Daily_{self.date}.md"
                ])
                self._notify_callback(step)
                return True
            else:
                step.error(f"Dashboard generation failed: {result.stderr}")
                self._notify_callback(step)
                return False

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def _step_run_ingest(self) -> bool:
        """Step 4: Run ingest orchestration."""
        step = self.steps[self._get_step_index(4)]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(10, ["Checking inboxes..."])
            self._notify_callback(step)

            step.update_progress(25, [
                "Processing Plaud notes...",
                "Consolidating multi-file transcriptions...",
                "Extracting tags and glossary terms..."
            ])
            self._notify_callback(step)

            # Run clean ingest processor as subprocess
            clean_processor = scripts_dir / "clean_md_processor.py"
            result = subprocess.run(
                [sys.executable, str(clean_processor)],
                cwd=str(Path.home() / "theVault"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=600,  # 10 minutes for ingest
                close_fds=True
            )

            # Parse output for summary - just totals, not individual files
            summary_lines = []
            if result.stdout:
                for line in result.stdout.split("\n"):
                    # Extract only summary/total lines
                    if any(marker in line for marker in [
                        "📊 Summary:", "📭 No files",
                        "• Input:", "• Groups:", "• Output:"
                    ]):
                        summary_lines.append(line.strip())

            # Show results
            if result.returncode == 0:
                if "📭 No files found in inbox" in result.stdout:
                    step.complete([
                        "Ingest complete",
                        "No files found in inbox"
                    ])
                else:
                    step.complete([
                        "Ingest complete",
                        *summary_lines  # Show all summary lines
                    ])
                self._notify_callback(step)
                return True
            else:
                # Ingest may partially succeed, so don't fail completely
                warning_details = summary_lines[:3] if summary_lines else [result.stderr[:100] if result.stderr else "Check logs for details"]
                step.complete([
                    "Ingest completed with warnings",
                    *warning_details
                ])
                self._notify_callback(step)
                return True  # Continue workflow even if ingest has issues

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def _step_organize_files(self) -> bool:
        """Step 5: Organize files using Auto Note Mover logic."""
        step = self.steps[self._get_step_index(5)]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(20, ["Scanning files for organization..."])
            self._notify_callback(step)

            organizer = FileOrganizer(self.vault_path)

            step.update_progress(50, ["Applying organization rules..."])
            self._notify_callback(step)

            results = organizer.organize_files()

            summary = [
                f"Files scanned: {results['stats']['files_scanned']}",
                f"Files moved: {results['stats']['files_moved']}",
                f"Files skipped: {results['stats']['files_skipped']}"
            ]

            # Add ALL moved files (not just first 2)
            if results['stats']['files_moved'] > 0:
                summary.append("--- Moved Files ---")
                for moved in results['moved_files']:
                    file_name = Path(moved['file']).name
                    dest_name = Path(moved['to']).name
                    summary.append(f"  ✓ {file_name} → {dest_name}")

            # Add skipped files for visibility
            if results['stats']['files_skipped'] > 0 and 'skipped_files' in results:
                summary.append("--- Skipped Files ---")
                for skipped in results.get('skipped_files', []):
                    file_name = Path(skipped['file']).name
                    summary.append(f"  ⊘ {file_name} ({skipped.get('reason', 'no rule matched')})")

            step.complete(summary)
            self._notify_callback(step)
            return results['success']

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def _step_map_to_calendar(self) -> bool:
        """Step 6: Map files to calendar events."""
        step = self.steps[self._get_step_index(6)]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(20, ["Reading Work calendar..."])
            self._notify_callback(step)

            mapper = CalendarMapper(self.vault_path, calendar_name="Work")

            step.update_progress(50, ["Matching files to meetings..."])
            self._notify_callback(step)

            results = mapper.map_files_to_calendar()

            summary = [
                f"Files scanned: {results['stats']['files_scanned']}",
                f"Files mapped: {results['stats']['files_mapped']}",
                f"No match: {results['stats']['files_no_match']}"
            ]

            # Add ALL mapped files
            if results['stats']['files_mapped'] > 0:
                summary.append("--- Mapped to Calendar ---")
                for mapped in results['mapped_files']:
                    file_name = Path(mapped['file']).name
                    meeting_title = mapped['meeting']
                    summary.append(f"  ✓ {file_name}")
                    summary.append(f"     ← {meeting_title}")

            # Add files with no match
            if results['stats']['files_no_match'] > 0 and 'no_match_files' in results:
                summary.append("--- No Calendar Match ---")
                for no_match in results.get('no_match_files', []):
                    file_name = Path(no_match['file']).name
                    reason = no_match.get('reason', '')
                    summary.append(f"  ⊘ {file_name}" + (f" ({reason})" if reason else ""))

            step.complete(summary)
            self._notify_callback(step)
            return results['success']

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    # EOL 2026-03-25 — TOC generation permanently disabled per Eric
    # def _step_update_tocs(self) -> bool:
    #     """Step 7: Update all TOC files."""
    #     step = self.steps[self._get_step_index(7)]
    #     step.start()
    #     self._notify_callback(step)
    #
    #     try:
    #         step.update_progress(20, ["Scanning vault directories..."])
    #         self._notify_callback(step)
    #
    #         generator = TOCGenerator(self.vault_path)
    #
    #         step.update_progress(50, ["Updating TOC files..."])
    #         self._notify_callback(step)
    #
    #         results = generator.update_all_tocs()
    #
    #         summary = [
    #             f"TOCs created: {results['stats']['tocs_created']}",
    #             f"TOCs updated: {results['stats']['tocs_updated']}",
    #             f"TOCs unchanged: {results['stats']['tocs_unchanged']}"
    #         ]
    #
    #         # Add created TOCs
    #         if results['stats']['tocs_created'] > 0 and 'created_tocs' in results:
    #             summary.append("--- Created TOCs ---")
    #             for toc in results.get('created_tocs', [])[:10]:
    #                 toc_name = Path(toc).name
    #                 summary.append(f"  + {toc_name}")
    #
    #         # Add updated TOCs
    #         if results['stats']['tocs_updated'] > 0 and 'updated_tocs' in results:
    #             summary.append("--- Updated TOCs ---")
    #             for toc in results.get('updated_tocs', [])[:10]:
    #                 toc_name = Path(toc).name
    #                 summary.append(f"  ↻ {toc_name}")
    #
    #         step.complete(summary)
    #         self._notify_callback(step)
    #         return results['success']
    #
    #     except Exception as e:
    #         step.error(str(e))
    #         self._notify_callback(step)
    #         return False

    def run(self) -> Dict:
        """
        Execute the complete morning workflow.

        Returns:
            Dictionary with workflow results
        """
        logger.info("=" * 60)
        logger.info(f"Starting Morning Workflow - {self.date}")
        logger.info("=" * 60)

        self.started_at = time.time()

        # Execute each step
        step_methods = []

        # Mac Mini gets NAS verification first
        if self.is_mac_mini:
            step_methods.append(self._step_verify_nas)

        # Common steps for all machines
        step_methods.extend([
            self._step_start_services,
            self._step_sync_calendar,
            self._step_create_dashboard,
            self._step_run_ingest,
            # self._step_organize_files,  # Disabled - manual organization for now
            self._step_map_to_calendar,
            # self._step_update_tocs,  # EOL 2026-03-25 — TOC generation permanently disabled per Eric
        ])

        for step_method in step_methods:
            success = step_method()
            if not success:
                # If NAS check fails on Mac Mini, STOP workflow (don't continue)
                if self.is_mac_mini and step_method == self._step_verify_nas:
                    logger.error("NAS verification failed - workflow stopped")
                    logger.error("Please fix NAS mount and retry workflow")
                    break
                else:
                    logger.warning(f"Step failed but continuing workflow...")

        self.completed_at = time.time()
        duration = self.completed_at - self.started_at

        # Count errors
        total_errors = sum(len(step.errors) for step in self.steps)

        logger.info("=" * 60)
        if total_errors == 0:
            logger.info(f"✅ Morning Workflow Complete ({duration:.1f}s)")
        else:
            logger.info(f"⚠️  Morning Workflow Complete with {total_errors} errors ({duration:.1f}s)")
        logger.info("=" * 60)

        return {
            "success": total_errors == 0,
            "date": self.date,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": duration,
            "steps": [step.to_dict() for step in self.steps],
            "total_errors": total_errors
        }


def main():
    """CLI entry point."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run morning workflow")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    workflow = MorningWorkflow(date=args.date)
    result = workflow.run()

    print("\n" + "=" * 60)
    print("MORNING WORKFLOW RESULTS")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
