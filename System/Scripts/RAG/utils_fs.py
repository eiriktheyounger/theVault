# System/Scripts/RAG/utils_fs.py
import fnmatch
from pathlib import Path
from typing import Iterator

try:
    from ..index.config import EXCLUDE_GLOBS  # type: ignore
except Exception:
    EXCLUDE_GLOBS: list[str] = []


def iter_markdown_under_vault(vault_dir: str) -> Iterator[Path]:
    """Yield all .md files under the given vault directory (recursively)."""
    root = Path(vault_dir).expanduser().resolve()
    if not root.exists():
        return
    for p in root.rglob("*.md"):
        # Skip hidden/system files if needed
        if any(part.startswith(".") for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, g) for g in EXCLUDE_GLOBS):
            continue
        yield p
