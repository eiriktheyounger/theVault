#!/usr/bin/env python3
"""start_all.py — Start all theVault services.

Called by morning_workflow.py Step 1.
Starts: Ollama (11434), RAG server (5055).
Vite dev server (5173) is optional / manual.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # ~/theVault


def _is_port_open(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_port(port: int, timeout: int = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_port_open(port):
            return True
        time.sleep(1)
    return False


def start_ollama() -> bool:
    """Ensure Ollama is running on port 11434."""
    if _is_port_open(11434):
        print("✓ Ollama already running on :11434")
        return True

    print("  Starting Ollama...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if _wait_for_port(11434, timeout=15):
            print("✓ Ollama started on :11434")
            return True
        else:
            print("✗ Ollama failed to start within 15s")
            return False
    except FileNotFoundError:
        print("✗ Ollama not installed")
        return False


def start_rag_server() -> bool:
    """Ensure RAG server is running on port 5055."""
    if _is_port_open(5055):
        print("✓ RAG server already running on :5055")
        return True

    print("  Starting RAG server...")
    try:
        subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "System.Scripts.RAG.llm.server:app",
                "--host", "0.0.0.0", "--port", "5055",
            ],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if _wait_for_port(5055, timeout=20):
            print("✓ RAG server started on :5055")
            return True
        else:
            print("✗ RAG server failed to start within 20s")
            return False
    except Exception as e:
        print(f"✗ RAG server start failed: {e}")
        return False


def main() -> int:
    print("Starting theVault services...")
    results = []
    results.append(start_ollama())
    results.append(start_rag_server())

    if all(results):
        print("\n✓ All services running")
        return 0
    else:
        print("\n✗ Some services failed to start")
        return 1


if __name__ == "__main__":
    sys.exit(main())
