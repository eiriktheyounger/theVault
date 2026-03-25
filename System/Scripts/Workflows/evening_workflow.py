#!/usr/bin/env python3
"""
Evening Workflow Orchestrator

Handles evening review and overnight job preparation.

Steps:
1. Generate Day Review (tasks from ingest, quick adds, dashboard)
2. Highlight Tomorrow's Focus (priorities, key tasks)
3. Queue Overnight Jobs (documentation, reports, batch processing)

Usage:
    from evening_workflow import EveningWorkflow
    workflow = EveningWorkflow(date="2025-11-19", callback=progress_callback)
    result = workflow.run()
"""

import logging
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any, List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class WorkflowStep:
    """Represents a single workflow step with progress tracking."""

    def __init__(self, step_num: int, name: str, total_steps: int):
        self.step_num = step_num
        self.name = name
        self.total_steps = total_steps
        self.status = "pending"
        self.progress = 0
        self.started_at = None
        self.completed_at = None
        self.summary_lines = []
        self.errors = []

    def start(self):
        self.status = "running"
        self.started_at = time.time()
        logger.info(f"Step {self.step_num}/{self.total_steps}: {self.name} - Started")

    def update_progress(self, progress: int, summary_lines: list):
        self.progress = min(100, max(0, progress))
        self.summary_lines = summary_lines[-5:]

    def complete(self, summary_lines: list = None):
        self.status = "complete"
        self.progress = 100
        self.completed_at = time.time()
        if summary_lines:
            self.summary_lines = summary_lines[-5:]
        logger.info(f"Step {self.step_num}/{self.total_steps}: {self.name} - Complete")

    def error(self, error_msg: str):
        self.status = "error"
        self.completed_at = time.time()
        self.errors.append(error_msg)
        logger.error(f"Step {self.step_num}/{self.total_steps}: {self.name} - Error: {error_msg}")

    def to_dict(self) -> Dict:
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


class EveningWorkflow:
    """Orchestrates the evening workflow with progress tracking."""

    def __init__(self, date: Optional[str] = None, callback: Optional[Callable] = None):
        """
        Initialize evening workflow.

        Args:
            date: Target date (YYYY-MM-DD), defaults to today
            callback: Optional callback function(step: WorkflowStep) for progress updates
        """
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.callback = callback
        self.vault_path = Path.home() / "theVault" / "Vault"

        # Define workflow steps
        self.steps = [
            WorkflowStep(1, "Generate Day Review", 4),
            WorkflowStep(2, "Email Summary → Daily Note", 4),
            WorkflowStep(3, "Highlight Tomorrow's Focus", 4),
            WorkflowStep(4, "Queue Overnight Jobs", 4),
        ]

        self.errors = []
        self.started_at = None
        self.completed_at = None

    def _notify_callback(self, step: WorkflowStep):
        if self.callback:
            try:
                self.callback(step)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def _find_daily_dashboard(self) -> Optional[Path]:
        """Find today's daily dashboard file."""
        date_obj = datetime.strptime(self.date, "%Y-%m-%d")
        year = date_obj.strftime("%Y")
        month = date_obj.strftime("%m")

        dashboard_path = self.vault_path / "TimeTracking" / year / month / f"Daily_{self.date}.md"

        if dashboard_path.exists():
            return dashboard_path

        return None

    def _extract_tasks_from_file(self, file_path: Path) -> List[Dict]:
        """Extract tasks from a markdown file."""
        tasks = []

        try:
            content = file_path.read_text(encoding="utf-8")

            # Find task items (- [ ] or - [x])
            import re
            task_pattern = r"^[\s]*[-*]\s+\[([ x])\]\s+(.+)$"

            for line in content.split("\n"):
                match = re.match(task_pattern, line, re.MULTILINE)
                if match:
                    completed = match.group(1) == "x"
                    task_text = match.group(2).strip()
                    tasks.append({
                        "text": task_text,
                        "completed": completed,
                        "source": file_path.name
                    })

        except Exception as e:
            logger.error(f"Failed to extract tasks from {file_path}: {e}")

        return tasks

    def _find_recent_notes(self) -> List[Path]:
        """Find notes created/modified today."""
        today = datetime.strptime(self.date, "%Y-%m-%d")
        today_start = today.timestamp()
        today_end = (today + timedelta(days=1)).timestamp()

        recent_notes = []

        # Check common locations
        search_dirs = [
            self.vault_path / "Notes",
            self.vault_path / "Notes" / "Meetings",
            self.vault_path / "Notes" / "Plaud",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for note_path in search_dir.glob("**/*.md"):
                if note_path.name.startswith(".") or "TOC" in note_path.name:
                    continue

                mtime = note_path.stat().st_mtime
                if today_start <= mtime < today_end:
                    recent_notes.append(note_path)

        return recent_notes

    def _step_generate_day_review(self) -> bool:
        """Step 1: Generate review of today's activities."""
        step = self.steps[0]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(20, ["Finding today's daily dashboard..."])
            self._notify_callback(step)

            # Find daily dashboard
            dashboard = self._find_daily_dashboard()

            if not dashboard:
                step.error(f"Daily dashboard not found for {self.date}")
                self._notify_callback(step)
                return False

            step.update_progress(40, ["Extracting tasks from dashboard..."])
            self._notify_callback(step)

            # Extract tasks
            tasks = self._extract_tasks_from_file(dashboard)

            step.update_progress(60, ["Finding notes from today..."])
            self._notify_callback(step)

            # Find recent notes
            recent_notes = self._find_recent_notes()

            step.update_progress(80, ["Generating review summary..."])
            self._notify_callback(step)

            # Generate review
            date_obj = datetime.strptime(self.date, "%Y-%m-%d")
            year = date_obj.strftime("%Y")
            month = date_obj.strftime("%m")
            review_path = self.vault_path / "TimeTracking" / year / month / f"Evening_Review_{self.date}.md"
            review_path.parent.mkdir(parents=True, exist_ok=True)

            completed_tasks = [t for t in tasks if t["completed"]]
            pending_tasks = [t for t in tasks if not t["completed"]]

            review_content = [
                f"# Evening Review - {self.date}",
                "",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}",
                "",
                "## Today's Accomplishments",
                "",
            ]

            if completed_tasks:
                review_content.append(f"✅ **{len(completed_tasks)} tasks completed:**")
                for task in completed_tasks[:10]:  # Top 10
                    review_content.append(f"- {task['text']}")
                review_content.append("")
            else:
                review_content.append("*No tasks marked as completed*")
                review_content.append("")

            review_content.extend([
                "## Notes & Content Created Today",
                "",
            ])

            if recent_notes:
                review_content.append(f"📝 **{len(recent_notes)} notes created/updated:**")
                for note in recent_notes[:10]:  # Top 10
                    review_content.append(f"- [[{note.name}]]")
                review_content.append("")
            else:
                review_content.append("*No new notes today*")
                review_content.append("")

            review_content.extend([
                "## Pending Tasks",
                "",
            ])

            if pending_tasks:
                review_content.append(f"⏳ **{len(pending_tasks)} tasks still pending:**")
                for task in pending_tasks[:15]:  # Top 15
                    review_content.append(f"- [ ] {task['text']}")
                review_content.append("")
            else:
                review_content.append("*All tasks completed!*")
                review_content.append("")

            review_content.extend([
                "## Action Items",
                "",
                "- [ ] Review pending tasks - carry over to tomorrow?",
                "- [ ] Set priorities for tomorrow (see Tomorrow's Focus below)",
                "- [ ] Queue any overnight documentation jobs",
                "",
            ])

            review_path.write_text("\n".join(review_content), encoding="utf-8")

            summary = [
                f"Review generated: {review_path.name}",
                f"  {len(completed_tasks)} tasks completed",
                f"  {len(pending_tasks)} tasks pending",
                f"  {len(recent_notes)} notes created"
            ]

            step.complete(summary)
            self._notify_callback(step)
            return True

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def _step_email_summary(self) -> bool:
        """Step 2: Run daily email summary and inject into daily note."""
        step = self.steps[1]
        step.start()
        self._notify_callback(step)

        try:
            import subprocess
            summary_script = (Path(__file__).parent.parent /
                              "Claude Code Desktop Specific" / "gmail" / "daily_email_summary.py")

            if not summary_script.exists():
                step.complete(["Email summary script not found — skipping"])
                self._notify_callback(step)
                return True  # Non-fatal

            result = subprocess.run(
                [sys.executable, str(summary_script), "--date", self.date],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, text=True, timeout=120, close_fds=True
            )

            lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
            step.complete(lines or ["Email summary complete"])
            self._notify_callback(step)
            return True

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return True  # Non-fatal

    def _step_highlight_tomorrow(self) -> bool:
        """Step 2: Highlight tomorrow's focus areas."""
        step = self.steps[1]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(30, ["Analyzing pending tasks..."])
            self._notify_callback(step)

            # Find review file
            date_obj = datetime.strptime(self.date, "%Y-%m-%d")
            year = date_obj.strftime("%Y")
            month = date_obj.strftime("%m")
            review_path = self.vault_path / "TimeTracking" / year / month / f"Evening_Review_{self.date}.md"

            if not review_path.exists():
                step.error("Review file not found")
                self._notify_callback(step)
                return False

            step.update_progress(60, ["Generating tomorrow's focus..."])
            self._notify_callback(step)

            # Read review
            review_content = review_path.read_text(encoding="utf-8")

            # Append tomorrow section
            tomorrow_date = (datetime.strptime(self.date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

            tomorrow_section = [
                "",
                "---",
                "",
                f"## Tomorrow's Focus - {tomorrow_date}",
                "",
                "### High Priority",
                "*(Drag most important tasks here)*",
                "",
                "- [ ] ",
                "- [ ] ",
                "- [ ] ",
                "",
                "### Medium Priority",
                "*(Tasks to tackle if time permits)*",
                "",
                "- [ ] ",
                "- [ ] ",
                "",
                "### Low Priority / Nice to Have",
                "*(Future tasks to consider)*",
                "",
                "- [ ] ",
                "",
                "### Key Meetings Tomorrow",
                "*(Check calendar and add meeting prep here)*",
                "",
                "- ",
                "",
                "### Energy Considerations",
                "- **High Energy Windows**: Morning (9-11am), After Lunch (2-4pm)",
                "- **Low Energy Windows**: Mid-morning (11am-12pm), Late Afternoon (4-6pm)",
                "- **Plan Accordingly**: Schedule demanding tasks during high energy, admin during low energy",
                "",
            ]

            # Write updated review
            review_path.write_text(review_content + "\n".join(tomorrow_section), encoding="utf-8")

            summary = [
                "Tomorrow's focus added to review",
                f"  Priority sections created",
                f"  Ready for planning"
            ]

            step.complete(summary)
            self._notify_callback(step)
            return True

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def _step_queue_overnight_jobs(self) -> bool:
        """Step 3: Queue overnight documentation/batch jobs."""
        step = self.steps[2]
        step.start()
        self._notify_callback(step)

        try:
            step.update_progress(30, ["Creating overnight job queue..."])
            self._notify_callback(step)

            # Create overnight jobs file
            jobs_path = self.vault_path / "System" / "Logs" / f"overnight_jobs_{self.date}.json"
            jobs_path.parent.mkdir(parents=True, exist_ok=True)

            # Default job queue (user can customize)
            jobs = {
                "created_at": datetime.now().isoformat(),
                "date": self.date,
                "jobs": [
                    {
                        "id": "weekly_summary",
                        "name": "Generate Weekly Summary",
                        "type": "documentation",
                        "status": "queued",
                        "description": "Summarize this week's activities, tasks, and notes",
                        "enabled": False  # User must enable manually
                    },
                    {
                        "id": "backlog_review",
                        "name": "Review Task Backlog",
                        "type": "analysis",
                        "status": "queued",
                        "description": "Analyze overdue and stale tasks, suggest archival",
                        "enabled": False
                    },
                    {
                        "id": "email_digest",
                        "name": "Generate Email Digest",
                        "type": "documentation",
                        "status": "queued",
                        "description": "Create summary of important emails from today",
                        "enabled": False
                    }
                ]
            }

            jobs_path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

            # Add note to evening review
            date_obj = datetime.strptime(self.date, "%Y-%m-%d")
            year = date_obj.strftime("%Y")
            month = date_obj.strftime("%m")
            review_path = self.vault_path / "TimeTracking" / year / month / f"Evening_Review_{self.date}.md"

            if review_path.exists():
                review_content = review_path.read_text(encoding="utf-8")

                jobs_section = [
                    "",
                    "---",
                    "",
                    "## Overnight Job Queue",
                    "",
                    f"Job configuration: [[{jobs_path.relative_to(self.vault_path)}]]",
                    "",
                    "Available jobs (edit config to enable):",
                    "- Weekly Summary Generation",
                    "- Task Backlog Review",
                    "- Email Digest",
                    "",
                    "*Note: Jobs are disabled by default. Edit the config file to enable specific jobs.*",
                    "",
                ]

                review_path.write_text(review_content + "\n".join(jobs_section), encoding="utf-8")

            summary = [
                f"Job queue created: {jobs_path.name}",
                f"  {len(jobs['jobs'])} jobs available",
                f"  Jobs disabled by default - enable as needed"
            ]

            step.complete(summary)
            self._notify_callback(step)
            return True

        except Exception as e:
            step.error(str(e))
            self._notify_callback(step)
            return False

    def run(self) -> Dict:
        """
        Execute the complete evening workflow.

        Returns:
            Dictionary with workflow results
        """
        logger.info("=" * 60)
        logger.info(f"Starting Evening Workflow - {self.date}")
        logger.info("=" * 60)

        self.started_at = time.time()

        # Execute each step
        step_methods = [
            self._step_generate_day_review,
            self._step_email_summary,
            self._step_highlight_tomorrow,
            self._step_queue_overnight_jobs,
        ]

        for step_method in step_methods:
            success = step_method()
            if not success:
                logger.warning(f"Step failed but continuing workflow...")

        self.completed_at = time.time()
        duration = self.completed_at - self.started_at

        # Count errors
        total_errors = sum(len(step.errors) for step in self.steps)

        logger.info("=" * 60)
        if total_errors == 0:
            logger.info(f"✅ Evening Workflow Complete ({duration:.1f}s)")
        else:
            logger.info(f"⚠️  Evening Workflow Complete with {total_errors} errors ({duration:.1f}s)")
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

    parser = argparse.ArgumentParser(description="Run evening workflow")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    workflow = EveningWorkflow(date=args.date)
    result = workflow.run()

    print("\n" + "=" * 60)
    print("EVENING WORKFLOW RESULTS")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
