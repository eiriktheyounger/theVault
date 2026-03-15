#!/usr/bin/env python3
"""
Minimal RAG index builder for NeroSpicy.

This script walks the Vault/ tree, finds Markdown files, and (optionally)
precomputes a lightweight on-disk index that other scripts can use.
If your pipeline supports "live" mode, this script can be a no-op that just
validates the Vault and reports counts — but it exists so the server's
/rag/start endpoint has something to call.

Usage (from Makefile):
  python System/Scripts/RAG/rag_build.py --mode live --vault Vault

Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from ..index.config import EXCLUDE_GLOBS  # type: ignore
except Exception:
    EXCLUDE_GLOBS: list[str] = []

VAULT_DEFAULT = os.environ.get("VAULT_DIR", "Vault")


def iter_markdown_under_vault(vault_root: str | os.PathLike) -> Iterable[Path]:
    """Yield all .md files under the given Vault directory, skipping hidden dirs."""
    root = Path(vault_root)
    if not root.exists():
        return
    for p in root.rglob("*.md"):
        # Skip anything in dot-directories like .git, .obsidian, etc.
        if any(part.startswith(".") for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, g) for g in EXCLUDE_GLOBS):
            continue
        yield p


def summarize_vault(vault: str | os.PathLike) -> Dict[str, Any]:
    files: List[Path] = list(iter_markdown_under_vault(vault))
    total_bytes = 0
    for f in files:
        try:
            total_bytes += f.stat().st_size
        except OSError:
            pass
    digest = hashlib.sha256(("|".join(str(p) for p in files)).encode()).hexdigest()[:12]
    return {
        "mode": "live",
        "vault": str(vault),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "digest": digest,
    }


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build (or validate) RAG index")
    ap.add_argument("--mode", choices=["live", "precompute"], default="live")
    ap.add_argument("--vault", default=VAULT_DEFAULT)
    ap.add_argument("--out", default="System/Scripts/RAG/.index")
    args = ap.parse_args(argv)

    Path(args.out).mkdir(parents=True, exist_ok=True)

    info = summarize_vault(args.vault)

    # In live mode we just write a tiny manifest the server can read.
    manifest_path = Path(args.out) / "manifest.json"
    manifest_path.write_text(json.dumps(info, indent=2))
    print(json.dumps({"ok": True, "manifest": str(manifest_path), **info}, indent=2))


if __name__ == "__main__":
    main()
