#!/usr/bin/env python3
"""stop_all.py — Stop all theVault services."""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    print("Stopping theVault services...")

    # Stop RAG server
    result = subprocess.run(["pkill", "-f", "uvicorn.*5055"], capture_output=True)
    if result.returncode == 0:
        print("✓ RAG server stopped")
    else:
        print("  RAG server was not running")

    # Stop Ollama
    result = subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True)
    if result.returncode == 0:
        print("✓ Ollama stopped")
    else:
        print("  Ollama was not running")

    print("\n✓ All services stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
