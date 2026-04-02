#!/usr/bin/env python3
"""emergency_kill.py — Force-kill all theVault services."""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    print("EMERGENCY KILL — force-stopping all services...")

    for pattern in ["uvicorn.*5055", "uvicorn.*5111", "ollama serve", "vite.*5173"]:
        result = subprocess.run(["pkill", "-9", "-f", pattern], capture_output=True)
        label = pattern.split(".*")[-1] if ".*" in pattern else pattern
        if result.returncode == 0:
            print(f"  Killed: {label}")
        else:
            print(f"  Not running: {label}")

    print("\n✓ All processes killed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
