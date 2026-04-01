#!/usr/bin/env python3
"""
daily_vault_activity.py — Unified vault post-processor + daily activity tracker

Three-phase workflow:
1. SCAN: Walk ~/theVault/Vault/ for .md files modified since last run
2. POST-PROCESS: Extract glossary terms, enrich tags via LLM, extract action items
3. INJECT: Group files by date, write ## Vault Activity section into daily notes

Dual-LLM pattern:
  Primary: Anthropic Haiku API (claude-haiku-4-5-20251001)
  Fallback: Ollama qwen2.5:7b (http://localhost:11434/api/chat)
  Last resort: Skip (log warning, continue)

Usage:
    python System/Scripts/daily_vault_activity.py             # scan last 7 days
    python System/Scripts/daily_vault_activity.py --dry-run   # preview only
    python System/Scripts/daily_vault_activity.py --days 14   # scan last 14 days
    python System/Scripts/daily_vault_activity.py --verbose   # debug logging
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("daily_vault_activity")

# ── Path Constants ────────────────────────────────────────────────────────────

VAULT_HOME = Path.home() / "theVault"
VAULT_ROOT = VAULT_HOME / "Vault"
DAILY_DIR = VAULT_ROOT / "Daily"
GLOSSARY_PATH = VAULT_ROOT / "System" / "glossary.md"
TAGS_YAML = VAULT_HOME / "System" / "Config" / "tags.yaml"
STATE_FILE = VAULT_HOME / ".vault_activity_state.json"

# ── LLM Configuration ─────────────────────────────────────────────────────────

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_OLLAMA_MODEL = "qwen2.5:7b"
_OLLAMA_URL = "http://localhost:11434/api/chat"

# ── Regexes ───────────────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
PLAUD_FILENAME_RE = re.compile(r"\d{2}-\d{2}.*-Full\.md$")


# ── State Management ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load last run timestamp from state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            log.warning(f"Failed to load state: {e}")
            return {}
    return {}


def _save_state(state: dict) -> None:
    """Save state to file."""
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        log.warning(f"Failed to save state: {e}")


# ── Frontmatter Parsing ───────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter as dict. Simple regex-based parsing."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}

    fm = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # Handle simple list syntax: tags: [tag1, tag2]
            if val.startswith("[") and val.endswith("]"):
                val = [t.strip().strip('"').strip("'") for t in val[1:-1].split(",")]
            fm[key] = val
    return fm


def _update_frontmatter(content: str, updates: dict) -> str:
    """Update YAML frontmatter with new values, preserving order and format."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        # No frontmatter — prepend one
        fm_lines = ["---"]
        for k, v in updates.items():
            if isinstance(v, list):
                fm_lines.append(f"{k}: {json.dumps(v)}")
            else:
                fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        return "\n".join(fm_lines) + "\n" + content

    fm_text = match.group(1)
    body = content[match.end():].lstrip("\n")

    # Parse existing frontmatter
    fm = {}
    fm_lines = []
    for line in fm_text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            fm_lines.append(line)
            continue
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key in updates:
                # Replace this line
                v = updates[key]
                if isinstance(v, list):
                    fm_lines.append(f"{key}: {json.dumps(v)}")
                else:
                    fm_lines.append(f"{key}: {v}")
                del updates[key]
            else:
                fm_lines.append(line)
        else:
            fm_lines.append(line)

    # Append new keys
    for k, v in updates.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}: {json.dumps(v)}")
        else:
            fm_lines.append(f"{k}: {v}")

    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


# ── LLM Backends ──────────────────────────────────────────────────────────────

def _call_anthropic(prompt: str) -> Optional[dict]:
    """Call Anthropic Haiku API. Returns parsed JSON dict or None."""
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            log.debug("ANTHROPIC_API_KEY not set, skipping Haiku")
            return None
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return json.loads(text)
    except ImportError:
        log.debug("anthropic SDK not installed")
        return None
    except Exception as e:
        log.debug(f"Anthropic error: {e}")
        return None


def _call_ollama(prompt: str) -> Optional[dict]:
    """Call local Ollama. Returns parsed JSON dict or None."""
    try:
        payload = json.dumps({
            "model": _OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        }).encode()
        req = urllib.request.Request(
            _OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        text = result.get("message", {}).get("content", "").strip()
        return json.loads(text)
    except Exception as e:
        log.debug(f"Ollama error: {e}")
        return None


def _call_llm(prompt: str) -> Optional[dict]:
    """Call LLM with fallback chain. Returns parsed JSON or None."""
    result = _call_anthropic(prompt)
    if result is None:
        log.debug("Falling back to Ollama")
        result = _call_ollama(prompt)
    return result


# ── File Detection ────────────────────────────────────────────────────────────

def _get_file_date(file_path: Path, fm: dict) -> str:
    """
    Assign a date to the file:
    - Plaud files (source: plaud or filename match): use frontmatter 'date:' field
    - Email files (type: email-thread): use frontmatter 'updated:' or 'last_message:' field
    - Other files: use st_mtime
    Returns YYYY-MM-DD string.
    """
    is_plaud = fm.get("source") == "plaud" or PLAUD_FILENAME_RE.search(file_path.name)
    is_email = fm.get("type") == "email-thread"

    if is_plaud and "date" in fm:
        return str(fm["date"])

    if is_email:
        # Use updated or last_message field
        for key in ("updated", "last_message"):
            if key in fm:
                date_str = str(fm[key])
                # Extract YYYY-MM-DD if it's a timestamp
                if len(date_str) >= 10:
                    return date_str[:10]

    # Default: use file mtime
    mtime = file_path.stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def _scan_vault(start_ts: float, end_ts: float) -> dict[str, list[dict]]:
    """
    Walk Vault/ for modified .md files.
    Returns {date_str: [file_info, ...]}.

    Excludes: Daily/**, System/**, Templates/**, dotfiles, files < 100 bytes.
    """
    files_by_date: dict[str, list[dict]] = {}

    if not VAULT_ROOT.exists():
        log.warning(f"Vault root not found: {VAULT_ROOT}")
        return files_by_date

    exclude_dirs = {"Daily", "System", "Templates"}

    for md_path in VAULT_ROOT.rglob("*.md"):
        # Skip if in excluded directory
        if any(part in exclude_dirs for part in md_path.parts):
            continue

        # Skip dotfiles/directories
        if any(part.startswith(".") for part in md_path.parts):
            continue

        # Skip small files
        try:
            stat = md_path.stat()
            if stat.st_size < 100:
                continue
            mtime = stat.st_mtime
        except OSError:
            continue

        # Check time bounds
        if mtime < start_ts or mtime > end_ts:
            continue

        # Parse frontmatter
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            log.warning(f"Failed to read {md_path}: {e}")
            continue

        fm = _parse_frontmatter(content)

        # Determine file date
        try:
            file_date = _get_file_date(md_path, fm)
        except Exception as e:
            log.warning(f"Failed to get date for {md_path}: {e}")
            file_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

        # Build file info
        source_type = fm.get("source", "note")
        file_info = {
            "path": md_path,
            "relative_path": md_path.relative_to(VAULT_ROOT).as_posix(),
            "title": fm.get("title") or md_path.stem.replace("_", " "),
            "source_type": source_type,
            "frontmatter": fm,
            "content": content,
            "mtime": mtime,
        }

        files_by_date.setdefault(file_date, []).append(file_info)

    return files_by_date


# ── Glossary Extraction ───────────────────────────────────────────────────────

def _extract_glossary_from_file(content: str) -> dict:
    """
    Extract glossary terms from existing ## Glossary section.
    Format: - **Term**: definition or - Term: definition
    Returns {term: definition}.
    """
    glossary = {}
    section_re = re.compile(r"(?:##|###)\s+Glossary\s*\n(.*?)(?=\n##|\Z)", re.DOTALL)
    match = section_re.search(content)
    if not match:
        return glossary

    section_text = match.group(1)
    for line in section_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Pattern: - **Term**: definition or - Term: definition
        m = re.match(r"^[-*]\s+\*\*(.+?)\*\*:\s*(.+)$", line)
        if not m:
            m = re.match(r"^[-*]\s+(.+?):\s*(.+)$", line)
        if m:
            term = m.group(1).strip()
            defn = m.group(2).strip()
            if term and defn:
                glossary[term] = defn

    return glossary


def _extract_glossary_via_llm(summary_text: str) -> Optional[dict]:
    """
    Send summary to LLM to extract glossary terms.
    Returns {term: definition} or None.
    """
    prompt = f"""Extract technical terms, acronyms, and domain-specific vocabulary from this summary.
Return JSON: {{"glossary": {{"term": "definition", ...}}}}
Only include terms that would be non-obvious to a general reader. Max 10 terms.

SUMMARY:
{summary_text[:2000]}"""

    result = _call_llm(prompt)
    if result and "glossary" in result:
        return result["glossary"]
    return None


def _merge_glossary_into_file(glossary_terms: dict, dry_run: bool = False) -> int:
    """
    Merge glossary terms into central glossary.md file.
    Returns number of new terms added.
    """
    if not glossary_terms:
        return 0

    # Load current glossary
    current_text = GLOSSARY_PATH.read_text(encoding="utf-8") if GLOSSARY_PATH.exists() else ""
    current_glossary = {}
    for line in current_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^[-*]\s+(.+?):\s*(.+)$", line)
        if m:
            term = m.group(1).strip()
            defn = m.group(2).strip()
            current_glossary[term.lower()] = (term, defn)

    # Merge (case-insensitive)
    added = 0
    for term, defn in glossary_terms.items():
        key = term.lower()
        if key not in current_glossary:
            current_glossary[key] = (term, defn)
            added += 1

    if added == 0:
        return 0

    if dry_run:
        log.info(f"  [dry-run] Would add {added} glossary terms")
        return added

    # Rebuild glossary file
    GLOSSARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Glossary", ""]
    for key in sorted(current_glossary.keys()):
        term, defn = current_glossary[key]
        lines.append(f"- {term}: {defn}")
    lines.append("")
    GLOSSARY_PATH.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"  Added {added} glossary terms")
    return added


# ── Tag Enrichment ────────────────────────────────────────────────────────────

def _load_approved_tags() -> list[str]:
    """Load approved tags from tags.yaml."""
    if not TAGS_YAML.exists():
        return []
    try:
        text = TAGS_YAML.read_text(encoding="utf-8")
        tags = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("-"):
                tag = line.lstrip("- ").strip()
                if tag:
                    tags.append(tag)
        return tags
    except Exception as e:
        log.warning(f"Failed to load tags.yaml: {e}")
        return []


def _enrich_tags_via_llm(
    summary_text: str,
    existing_tags: list[str],
    approved_tags: list[str],
) -> Optional[list[str]]:
    """
    Send content + existing tags to LLM for tag suggestions.
    Returns enriched tag list or None.
    """
    approved_str = "\n  - ".join(approved_tags) if approved_tags else "(empty)"
    existing_str = ", ".join(existing_tags) if existing_tags else "(none)"

    prompt = f"""Given this content summary and existing tags, suggest up to 10 tags for this document.
Rules:
- Use existing tags from the approved list when they match (prefer exact matches)
- Tags should be lowercase, hyphenated (e.g., "job-search", "home-projects")
- Priority order: most specific/useful tag first
- Include the existing tags if still relevant
- Max 10 tags total

Approved tag list:
  - {approved_str}

Existing tags on file: {existing_str}

Content summary:
{summary_text[:1500]}

Return JSON: {{"tags": ["tag1", "tag2", ...]}}"""

    result = _call_llm(prompt)
    if result and "tags" in result:
        tags = result["tags"]
        if isinstance(tags, list):
            return [str(t).lower() for t in tags[:10]]
    return None


def _update_tags_in_file(file_info: dict, new_tags: list[str], dry_run: bool = False) -> int:
    """
    Update file's frontmatter with new tags.
    Returns 1 if updated, 0 otherwise.
    """
    if not new_tags:
        return 0

    content = file_info["content"]
    updated = _update_frontmatter(content, {"tags": new_tags})

    if dry_run:
        log.debug(f"  [dry-run] Would update tags in {file_info['path'].name}")
        return 1

    try:
        file_info["path"].write_text(updated, encoding="utf-8")
        log.debug(f"  Updated tags in {file_info['path'].name}")
        return 1
    except Exception as e:
        log.warning(f"Failed to update tags in {file_info['path'].name}: {e}")
        return 0


def _add_new_tags_to_registry(new_tags: list[str], dry_run: bool = False) -> None:
    """Add new tags to tags.yaml registry."""
    if not new_tags:
        return

    # Load current tags
    current_tags = set(_load_approved_tags())

    # Find new ones
    new_only = [t for t in new_tags if t not in current_tags]
    if not new_only:
        return

    if dry_run:
        log.info(f"  [dry-run] Would add {len(new_only)} tags to registry")
        return

    # Append to tags.yaml
    TAGS_YAML.parent.mkdir(parents=True, exist_ok=True)
    lines = ["tags:"]
    all_tags = sorted(current_tags | set(new_only))
    for tag in all_tags:
        lines.append(f"  - {tag}")
    lines.append("")
    TAGS_YAML.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"  Added {len(new_only)} new tags to registry")


# ── Action Item Extraction ────────────────────────────────────────────────────

def _extract_action_items_via_llm(summary_text: str, activity_date: str) -> Optional[list[str]]:
    """
    Extract action items from summary.
    Returns list of task strings with 📅 stamps or None.
    """
    due_date = (datetime.strptime(activity_date, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")

    prompt = f"""Extract actionable tasks from this content.
For each task, return a markdown checkbox item: - [ ] task description
Always stamp each task with a due date: 📅 {due_date}

Return ONLY the task list in markdown format. If no actionable tasks, return "No tasks found."

CONTENT:
{summary_text[:2000]}"""

    try:
        result = _call_llm(prompt)
        if isinstance(result, dict) and "tasks" in result:
            tasks = result["tasks"]
            if isinstance(tasks, list):
                return [str(t) for t in tasks if t]
    except Exception as e:
        log.debug(f"Task extraction via LLM failed: {e}")

    # Fallback: parse plain text response
    try:
        import ollama
        resp = ollama.chat(
            model=_OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        text = resp.get("message", {}).get("content", "").strip()
        tasks = []
        for line in text.splitlines():
            if line.strip().startswith("- [ ]"):
                if "📅" not in line:
                    line = line.rstrip() + f" 📅 {due_date}"
                tasks.append(line)
        return tasks if tasks else None
    except Exception as e:
        log.debug(f"Task extraction fallback failed: {e}")
        return None


# ── Daily Note Injection ──────────────────────────────────────────────────────

def _daily_note_path(date_str: str) -> Path:
    """Return path to daily note for given YYYY-MM-DD."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    year = dt.strftime("%Y")
    month = dt.strftime("%m")
    fname = dt.strftime("%Y-%m-%d") + "-DLY.md"
    return DAILY_DIR / year / month / fname


def _build_vault_activity_section(
    date_str: str,
    files_by_source: dict[str, list[dict]],
    dry_run: bool = False,
) -> str:
    """Build ## Vault Activity section content."""
    lines = ["## Vault Activity", "<!-- vault-activity-start -->", ""]

    # Meetings & Transcripts (Plaud)
    plaud_files = files_by_source.get("plaud", [])
    if plaud_files:
        lines.append("### Meetings & Transcripts")
        lines.append("")
        for f in plaud_files:
            title = f.get("title", f["relative_path"])
            wikilink = f"[[{f['relative_path']}|{title}]]"
            lines.append(f"- {wikilink}")
        lines.append("")

    # Notes & Documents (all others, excluding email)
    other_files = [
        f for f in files_by_source.get("note", [])
        if f.get("source_type") not in ("email", "plaud")
    ]
    if other_files:
        lines.append("### Notes & Documents")
        lines.append("")
        for f in other_files:
            title = f.get("title", f["relative_path"])
            wikilink = f"[[{f['relative_path']}|{title}]]"
            lines.append(f"- {wikilink}")
        lines.append("")

    # Action Items (from task extraction)
    all_tasks = []
    for source_list in files_by_source.values():
        for f in source_list:
            if "action_items" in f:
                all_tasks.extend(f["action_items"])

    if all_tasks:
        lines.append("### Action Items")
        lines.append("")
        for task in all_tasks:
            lines.append(str(task))
        lines.append("")

    lines.append("<!-- vault-activity-end -->")
    return "\n".join(lines)


def _inject_vault_activity(
    date_str: str,
    files_by_source: dict[str, list[dict]],
    dry_run: bool = False,
) -> None:
    """Inject or replace ## Vault Activity section in daily note."""
    note_path = _daily_note_path(date_str)
    section_content = _build_vault_activity_section(date_str, files_by_source, dry_run)

    if dry_run:
        log.info(f"  [dry-run] Would inject section into {note_path.name}")
        return

    if not note_path.exists():
        log.debug(f"Daily note not found: {note_path} — skipping injection")
        return

    existing = note_path.read_text(encoding="utf-8")

    # Idempotent replace using markers
    section_re = re.compile(
        r"## Vault Activity\n<!-- vault-activity-start -->.*?<!-- vault-activity-end -->",
        re.DOTALL,
    )

    if section_re.search(existing):
        updated = section_re.sub(section_content, existing)
    else:
        # Append before ## Navigation or at end
        nav_match = re.search(r"\n## Navigation", existing)
        if nav_match:
            updated = existing[:nav_match.start()] + "\n\n" + section_content + existing[nav_match.start():]
        else:
            updated = existing.rstrip() + "\n\n" + section_content + "\n"

    note_path.write_text(updated, encoding="utf-8")
    log.info(f"  Injected Vault Activity into {note_path.name}")


# ── Public API ────────────────────────────────────────────────────────────────

def run_vault_activity(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = 7,
    extract_tasks: bool = True,
    enrich_tags: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run the full vault activity pipeline.

    Args:
        start_date: YYYY-MM-DD override (else use last run or days ago)
        end_date: YYYY-MM-DD override (else use today)
        days: Days to scan if start_date not provided
        extract_tasks: Whether to extract action items
        enrich_tags: Whether to enrich tags via LLM
        dry_run: Preview only, no writes
        verbose: Debug logging

    Returns:
        dict with {dates_updated, files_tracked, glossary_terms_added, tags_enriched, tasks_extracted, errors}
    """
    if verbose:
        log.setLevel(logging.DEBUG)

    # Validate NAS
    if not VAULT_ROOT.exists():
        log.error(f"Vault root not found: {VAULT_ROOT}")
        return {"error": "Vault not accessible"}

    # Determine time bounds
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()
    end_ts = end_dt.replace(hour=23, minute=59, second=59).timestamp()

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        # Use last run or days ago
        state = _load_state()
        last_run = state.get("last_run")
        if last_run:
            start_dt = datetime.fromisoformat(last_run)
        else:
            start_dt = end_dt - timedelta(days=days)
    start_ts = start_dt.replace(hour=0, minute=0, second=0).timestamp()

    log.info(f"Scanning {start_dt.date()} to {end_dt.date()}")

    # Phase 1: Scan vault
    files_by_date = _scan_vault(start_ts, end_ts)
    log.info(f"Found {sum(len(v) for v in files_by_date.values())} files across {len(files_by_date)} dates")

    if not files_by_date:
        log.info("No files to process")
        return {"dates_updated": 0, "files_tracked": 0, "glossary_terms_added": 0, "tags_enriched": 0, "tasks_extracted": 0, "errors": 0}

    # Load approved tags once
    approved_tags = _load_approved_tags() if enrich_tags else []

    # Counters
    dates_updated = 0
    glossary_added = 0
    tags_enriched = 0
    tasks_extracted = 0
    errors = 0

    # Phase 2 & 3: Post-process and inject
    for date_str in sorted(files_by_date.keys()):
        log.info(f"Processing {date_str}")
        files = files_by_date[date_str]

        # Group by source type for injection
        files_by_source: dict[str, list[dict]] = {}

        for file_info in files:
            source = file_info.get("source_type", "note")
            files_by_source.setdefault(source, []).append(file_info)

            content = file_info["content"]

            # Phase 2a: Extract glossary
            glossary = _extract_glossary_from_file(content)
            if not glossary:
                # Try LLM extraction
                summary_text = file_info.get("title", "")[:200]
                llm_glossary = _extract_glossary_via_llm(summary_text)
                if llm_glossary:
                    glossary = llm_glossary

            if glossary:
                glossary_added += _merge_glossary_into_file(glossary, dry_run=dry_run)

            # Phase 2b: Enrich tags
            if enrich_tags and approved_tags:
                existing_tags = file_info["frontmatter"].get("tags", [])
                if isinstance(existing_tags, str):
                    existing_tags = [t.strip() for t in existing_tags.split(",")]

                summary = file_info.get("title", "")[:200]
                new_tags = _enrich_tags_via_llm(summary, existing_tags, approved_tags)
                if new_tags:
                    _update_tags_in_file(file_info, new_tags, dry_run=dry_run)
                    tags_enriched += 1
                    _add_new_tags_to_registry(new_tags, dry_run=dry_run)

            # Phase 2c: Extract action items
            if extract_tasks:
                summary = file_info.get("title", "")[:500]
                tasks = _extract_action_items_via_llm(summary, date_str)
                if tasks:
                    file_info["action_items"] = tasks
                    tasks_extracted += len(tasks)

        # Phase 3: Inject into daily note
        _inject_vault_activity(date_str, files_by_source, dry_run=dry_run)
        dates_updated += 1

    # Update state
    state = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "dates_processed": len(files_by_date),
        "files_processed": sum(len(v) for v in files_by_date.values()),
    }
    if not dry_run:
        _save_state(state)

    return {
        "dates_updated": dates_updated,
        "files_tracked": sum(len(v) for v in files_by_date.values()),
        "glossary_terms_added": glossary_added,
        "tags_enriched": tags_enriched,
        "tasks_extracted": tasks_extracted,
        "errors": errors,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Unified vault post-processor + daily activity tracker"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--start-date", type=str, help="Scan start (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="Scan end (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=7, help="Days to scan if start-date not set (default: 7)")
    parser.add_argument("--no-tasks", action="store_true", help="Skip action item extraction")
    parser.add_argument("--no-tags", action="store_true", help="Skip tag enrichment")

    args = parser.parse_args()

    result = run_vault_activity(
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        extract_tasks=not args.no_tasks,
        enrich_tags=not args.no_tags,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    # Summary output
    print()
    print("=" * 60)
    print("Vault Activity Summary")
    print("=" * 60)
    for key, value in result.items():
        if key != "error":
            print(f"  {key.replace('_', ' ').title()}: {value}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
    print("=" * 60)
