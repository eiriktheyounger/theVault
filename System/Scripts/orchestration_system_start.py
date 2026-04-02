#!/usr/bin/env python3
"""orchestration_system_start.py — Ingest orchestration entry point.

Called by:
  - routes/ingest.py POST /ingest/start (background task)
  - morning_workflow.py Step 4

Runs clean_md_processor (Plaud inbox) and email_thread_ingester if available.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # ~/theVault


def run_orchestration(dry_run: bool = False) -> dict:
    """Run all ingest pipelines. Returns combined stats dict."""
    stats = {
        "plaud": {"groups": 0, "succeeded": 0, "skipped": 0, "failed": 0},
        "email": {"threads_processed": 0, "errors": []},
        "ok": True,
        "errors": [],
    }

    # 1. Plaud inbox (clean_md_processor)
    try:
        from System.Scripts.clean_md_processor import run_orchestration as plaud_run

        log.info("Running Plaud inbox processor...")
        result = plaud_run(dry_run=dry_run)
        stats["plaud"] = result
        log.info(f"Plaud: {result.get('succeeded', 0)} succeeded, {result.get('failed', 0)} failed")
    except ImportError:
        msg = "clean_md_processor not found — skipping Plaud ingest"
        log.warning(msg)
        stats["errors"].append(msg)
    except Exception as e:
        msg = f"Plaud ingest failed: {e}"
        log.error(msg)
        stats["errors"].append(msg)
        stats["ok"] = False

    # 2. Email thread ingester (optional)
    try:
        from System.Scripts.email_thread_ingester import run_orchestration as email_run

        log.info("Running email thread ingester...")
        result = email_run(dry_run=dry_run)
        stats["email"] = result
        log.info(f"Email: {result.get('threads_processed', 0)} threads processed")
    except ImportError:
        log.info("Email thread ingester not available — skipping")
    except Exception as e:
        msg = f"Email ingest failed: {e}"
        log.error(msg)
        stats["errors"].append(msg)

    return stats


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run all ingest pipelines")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    result = run_orchestration(dry_run=args.dry_run)

    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}")

    plaud = result["plaud"]
    print(f"\nPlaud: {plaud.get('succeeded', 0)} succeeded, {plaud.get('skipped', 0)} skipped, {plaud.get('failed', 0)} failed")

    email = result["email"]
    if email.get("threads_processed", 0) > 0:
        print(f"Email: {email['threads_processed']} threads processed")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
