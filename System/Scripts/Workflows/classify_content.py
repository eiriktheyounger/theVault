#!/usr/bin/env python3
"""
classify_content.py — Content classification CLI for theVault

Classifies ingested files into the correct vault location using Haiku API,
with human review via a markdown manifest table.

Modes:
  --scan        Scan source dir, call Haiku for each file, write manifest
  --scan --auto Skip review, move high-confidence files immediately
  --apply       Read reviewed manifest, move files, log decisions to DB

Database: System/Scripts/RAG/rag_data/classification.db
Manifest:  Vault/System/ClassificationReview.md

Usage:
    python3 System/Scripts/Workflows/classify_content.py --scan
    python3 System/Scripts/Workflows/classify_content.py --scan --source Vault/Notes/Scratch
    python3 System/Scripts/Workflows/classify_content.py --apply
    python3 System/Scripts/Workflows/classify_content.py --scan --auto
    python3 System/Scripts/Workflows/classify_content.py --scan --verbose
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

# ── Paths ──────────────────────────────────────────────────────────────────────

VAULT_BASE = Path.home() / 'theVault'
VAULT_ROOT = VAULT_BASE / 'Vault'
NAS_PATH = Path('/Volumes/home/MacMiniStorage')
DB_PATH = VAULT_BASE / 'System' / 'Scripts' / 'RAG' / 'rag_data' / 'classification.db'
MANIFEST_PATH = VAULT_ROOT / 'System' / 'ClassificationReview.md'
DEFAULT_SOURCE = VAULT_ROOT / 'Notes'
LOG_PATH = VAULT_BASE / 'System' / 'Logs' / 'classify.log'

HAIKU_MODEL = 'claude-haiku-4-5-20251001'

# Vault dirs to skip when building directory tree (too large, structural, or unclassified)
SKIP_TREE_DIRS = {
    'Daily', 'Assets', '_archive', '.obsidian', 'TagsRoutes',
    'Vault_RAG', 'Templates', 'Dashboards', 'Temp',
}

# Confidence threshold for ACCEPT vs REVIEW
ACCEPT_THRESHOLD = 0.85

# ── Logging ────────────────────────────────────────────────────────────────────

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger('classify')


# ── NAS validation ─────────────────────────────────────────────────────────────

def check_nas() -> None:
    """Exit if NAS is not mounted."""
    if not NAS_PATH.exists():
        log.error(f'NAS not mounted at {NAS_PATH}. Aborting.')
        sys.exit(1)


# ── Database ───────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Open classification.db, initialize schema, return connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS decisions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash      TEXT    NOT NULL,
            filename       TEXT    NOT NULL,
            model_proposed TEXT,
            final_path     TEXT,
            human_override INTEGER DEFAULT 0,
            confidence     REAL,
            model          TEXT,
            timestamp      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rules (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern          TEXT    NOT NULL UNIQUE,
            destination_path TEXT    NOT NULL,
            priority         INTEGER DEFAULT 50,
            source           TEXT    DEFAULT 'human',
            created          TEXT    NOT NULL,
            hit_count        INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS directory_tree (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            path        TEXT    NOT NULL UNIQUE,
            description TEXT,
            last_used   TEXT
        );
    """)
    conn.commit()


def load_rules(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        'SELECT pattern, destination_path, priority, hit_count FROM rules '
        'ORDER BY priority DESC, hit_count DESC'
    )
    return [dict(r) for r in cur.fetchall()]


def load_recent_overrides(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    cur = conn.execute(
        'SELECT filename, model_proposed, final_path FROM decisions '
        'WHERE human_override = 1 ORDER BY timestamp DESC LIMIT ?',
        (limit,)
    )
    return [dict(r) for r in cur.fetchall()]


def upsert_directory(conn: sqlite3.Connection, path: str) -> None:
    conn.execute(
        'INSERT INTO directory_tree (path, description, last_used) VALUES (?, "", ?) '
        'ON CONFLICT(path) DO UPDATE SET last_used = excluded.last_used',
        (path, datetime.now().isoformat())
    )


def log_decision(
    conn: sqlite3.Connection,
    file_hash: str,
    filename: str,
    model_proposed: Optional[str],
    final_path: str,
    human_override: bool,
    confidence: float,
) -> None:
    conn.execute(
        'INSERT INTO decisions '
        '(file_hash, filename, model_proposed, final_path, human_override, confidence, model, timestamp) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (
            file_hash, filename, model_proposed, final_path,
            int(human_override), confidence, HAIKU_MODEL,
            datetime.now().isoformat(),
        )
    )
    conn.commit()


def add_learned_rule(conn: sqlite3.Connection, pattern: str, destination_path: str) -> None:
    conn.execute(
        'INSERT INTO rules (pattern, destination_path, priority, source, created, hit_count) '
        'VALUES (?, ?, 30, "learned", ?, 0) ON CONFLICT(pattern) DO NOTHING',
        (pattern, destination_path, datetime.now().isoformat())
    )
    conn.commit()


def increment_rule_hit(conn: sqlite3.Connection, pattern: str) -> None:
    conn.execute('UPDATE rules SET hit_count = hit_count + 1 WHERE pattern = ?', (pattern,))
    conn.commit()


# ── Vault directory tree ───────────────────────────────────────────────────────

def scan_vault_tree(conn: sqlite3.Connection) -> list[str]:
    """Walk vault dirs to depth 3, skip noise. Returns sorted relative path list."""
    paths = []
    for item in sorted(VAULT_ROOT.rglob('*')):
        if not item.is_dir():
            continue
        parts = item.relative_to(VAULT_ROOT).parts
        # Skip hidden dirs and known noise
        if any(p.startswith('.') or p in SKIP_TREE_DIRS for p in parts):
            continue
        if len(parts) > 3:
            continue
        rel = str(item.relative_to(VAULT_ROOT))
        paths.append(rel)
        upsert_directory(conn, rel)
    conn.commit()
    return paths


def format_tree_for_prompt(tree_paths: list[str]) -> str:
    """Format vault tree as indented list for the Haiku prompt."""
    lines = []
    for p in tree_paths:
        depth = p.count('/')
        indent = '  ' * depth
        name = Path(p).name
        lines.append(f'{indent}{name}/')
    return '\n'.join(lines)


# ── File utilities ─────────────────────────────────────────────────────────────

def compute_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def read_file_preview(path: Path) -> str:
    """Return frontmatter + first 50 lines of a markdown file."""
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
        lines = content.splitlines()
        return '\n'.join(lines[:50])
    except Exception as e:
        return f'[error reading file: {e}]'


# ── Rule matching ──────────────────────────────────────────────────────────────

def match_rule(rules: list[dict], filename: str, content_preview: str) -> Optional[dict]:
    """Return first matching rule (checked against filename and content), or None."""
    for rule in rules:
        pattern = rule['pattern']
        try:
            if re.search(pattern, filename, re.IGNORECASE):
                return rule
            if re.search(pattern, content_preview, re.IGNORECASE):
                return rule
        except re.error:
            pass
    return None


# ── Haiku classification ───────────────────────────────────────────────────────

def classify_file(
    client: anthropic.Anthropic,
    filename: str,
    content_preview: str,
    tree_str: str,
    rules: list[dict],
    recent_overrides: list[dict],
) -> dict:
    """Call Haiku to classify a single file. Returns dict with destination_path, confidence, etc."""

    rules_section = ''
    if rules:
        rule_lines = [
            f'  - Pattern `{r["pattern"]}` → {r["destination_path"]}  (hits: {r["hit_count"]})'
            for r in rules[:20]
        ]
        rules_section = 'Learned classification rules (highest priority first):\n' + '\n'.join(rule_lines) + '\n'

    overrides_section = ''
    if recent_overrides:
        override_lines = [
            f'  - {o["filename"]}: model said "{o["model_proposed"] or "_unfiled_"}" → human corrected to "{o["final_path"]}"'
            for o in recent_overrides
        ]
        overrides_section = 'Recent human corrections (learn from these):\n' + '\n'.join(override_lines) + '\n'

    prompt = f"""You are classifying a markdown file for a personal knowledge vault.

Vault directory structure (depth 3):
{tree_str}

Organization patterns:
- Work meetings with clients → HarmonicInternal/{{Client}}/{{Project}}/
- Job interviews → Personal/Career/Interviews/{{Company}}/
- Personal finance → Personal/Finance/
- Family matters → Personal/Family/
- Lectures/tutorials/technology → Reference/Technology/{{topic}}/
- Strategy and brainstorming → Knowledge/Strategy/
- Truly unclassifiable scratch notes → Notes/Scratch/

{rules_section}{overrides_section}File to classify:
Filename: {filename}
Content preview (first 50 lines):
---
{content_preview}
---

Respond with JSON only (no markdown fences, no extra text):
{{
  "type": "meeting|interview|personal|lecture|strategy|reference|note",
  "company": "<company name or null>",
  "project": "<project name or null>",
  "topic": "<topic or null>",
  "destination_path": "<path relative to Vault root, no leading or trailing slash>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence>"
}}

Rules:
- destination_path must be a real path that exists in the vault tree above, or a logical extension of it
- If you cannot determine a good destination, set destination_path to "_unfiled_" and confidence to 0.0
- Do not invent new top-level directories"""

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if model wraps the response
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        log.warning(f'Haiku classification failed for {filename}: {e}')
        return {
            'type': 'note',
            'company': None,
            'project': None,
            'topic': None,
            'destination_path': '_unfiled_',
            'confidence': 0.0,
            'reasoning': f'Classification error: {e}',
        }


# ── Manifest write / parse ─────────────────────────────────────────────────────

def write_manifest(source_dir: Path, rows: list[dict]) -> None:
    """Write markdown table manifest to ClassificationReview.md."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    source_rel = str(source_dir.relative_to(VAULT_ROOT))

    accept_count = sum(1 for r in rows if r['status'] == 'ACCEPT')
    review_count = sum(1 for r in rows if r['status'] == 'REVIEW')

    lines = [
        f'# Classification Review — {now}',
        f'',
        f'**Source:** `{source_rel}`  ',
        f'**Files:** {len(rows)} ({accept_count} ACCEPT, {review_count} REVIEW)  ',
        f'**Instructions:** Fill in the `Final` column for REVIEW rows. '
        f'Change Status to `SKIP` to leave a file. Then run `--apply`.',
        f'',
        f'| # | Status | File | Proposed | Final |',
        f'|---|--------|------|----------|-------|',
    ]

    for i, row in enumerate(rows, 1):
        proposed_display = row['proposed'] if row['proposed'] else '_unfiled_'
        final_display = row['final'] if row['final'] else ''
        lines.append(
            f'| {i} | {row["status"]} | {row["rel_path"]} | {proposed_display} | {final_display} |'
        )

    lines.append('')
    MANIFEST_PATH.write_text('\n'.join(lines), encoding='utf-8')
    log.info(f'Manifest written to {MANIFEST_PATH}')


def parse_manifest() -> tuple[Path, list[dict]]:
    """Parse ClassificationReview.md. Returns (source_dir, rows)."""
    if not MANIFEST_PATH.exists():
        log.error(f'No manifest found at {MANIFEST_PATH}. Run --scan first.')
        sys.exit(1)

    content = MANIFEST_PATH.read_text(encoding='utf-8')

    # Extract source dir from header comment
    source_match = re.search(r'\*\*Source:\*\*\s+`([^`]+)`', content)
    source_rel = source_match.group(1) if source_match else 'Notes'
    source_dir = VAULT_ROOT / source_rel

    # Parse table — skip header row and separator row
    rows = []
    in_table = False
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r'\|\s*#\s*\|', stripped) and 'Status' in stripped:
            in_table = True
            continue
        if in_table and re.match(r'\|\s*-+\s*\|', stripped):
            continue
        if in_table and stripped.startswith('|'):
            cols = [c.strip() for c in stripped.split('|')[1:-1]]
            if len(cols) >= 5:
                rows.append({
                    'num': cols[0],
                    'status': cols[1].strip().upper(),
                    'rel_path': cols[2].strip(),
                    'proposed': cols[3].strip(),
                    'final': cols[4].strip(),
                })
        elif in_table and not stripped.startswith('|'):
            break  # end of table

    return source_dir, rows


# ── Scan mode ──────────────────────────────────────────────────────────────────

def run_scan(source_dir: Path, auto: bool = False, verbose: bool = False) -> None:
    check_nas()

    if not source_dir.exists():
        log.error(f'Source directory does not exist: {source_dir}')
        sys.exit(1)

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        log.error('ANTHROPIC_API_KEY not set in environment.')
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    conn = get_db()

    log.info('Scanning vault directory tree...')
    tree_paths = scan_vault_tree(conn)
    tree_str = format_tree_for_prompt(tree_paths)
    log.info(f'Tree: {len(tree_paths)} directories indexed')

    rules = load_rules(conn)
    recent_overrides = load_recent_overrides(conn)
    log.info(f'Loaded {len(rules)} rules, {len(recent_overrides)} recent overrides')

    md_files = sorted(source_dir.rglob('*.md'))
    log.info(f'Found {len(md_files)} markdown files in {source_dir.relative_to(VAULT_ROOT)}')

    manifest_rows = []

    for i, path in enumerate(md_files, 1):
        rel_path = str(path.relative_to(VAULT_ROOT))
        content_preview = read_file_preview(path)
        fhash = compute_hash(path)

        # Check learned rules before calling API
        matched_rule = match_rule(rules, path.name, content_preview)
        if matched_rule:
            destination = matched_rule['destination_path']
            confidence = 0.95
            increment_rule_hit(conn, matched_rule['pattern'])
            if verbose:
                log.info(f'[{i}/{len(md_files)}] Rule match: {path.name} → {destination}')
        else:
            result = classify_file(
                client, path.name, content_preview, tree_str, rules, recent_overrides
            )
            destination = result.get('destination_path', '_unfiled_')
            confidence = float(result.get('confidence', 0.0))
            if verbose:
                log.info(
                    f'[{i}/{len(md_files)}] {path.name}: {destination} '
                    f'(conf={confidence:.2f}) — {result.get("reasoning", "")}'
                )
            else:
                log.info(f'[{i}/{len(md_files)}] {path.name} → {destination} ({confidence:.2f})')

        # Normalize destination
        if destination and destination != '_unfiled_':
            destination = destination.strip('/')

        if not destination or destination == '_unfiled_' or confidence < ACCEPT_THRESHOLD:
            status = 'REVIEW'
            final = ''
            proposed = destination if destination and destination != '_unfiled_' else ''
        else:
            status = 'ACCEPT'
            final = destination
            proposed = destination

        manifest_rows.append({
            'rel_path': rel_path,
            'proposed': proposed,
            'final': final,
            'status': status,
            'confidence': confidence,
            'file_hash': fhash,
        })

    write_manifest(source_dir, manifest_rows)

    accept_count = sum(1 for r in manifest_rows if r['status'] == 'ACCEPT')
    review_count = sum(1 for r in manifest_rows if r['status'] == 'REVIEW')
    print(f'\n✓ Scan complete: {accept_count} ACCEPT, {review_count} REVIEW')
    print(f'  Manifest: {MANIFEST_PATH}')

    if auto:
        log.info('--auto flag: applying ACCEPT rows immediately...')
        _apply_rows(conn, manifest_rows)

    conn.close()


# ── Apply mode ─────────────────────────────────────────────────────────────────

def run_apply() -> None:
    check_nas()
    conn = get_db()
    source_dir, rows = parse_manifest()

    moved = 0
    skipped = 0
    errors = 0
    new_rules: list[tuple[str, str]] = []

    for row in rows:
        status = row['status']
        rel_path = row['rel_path']
        proposed = row['proposed']
        final = row['final'].strip()

        # Skip: explicit SKIP status, or no final path provided
        if status == 'SKIP' or not final or final == '_unfiled_':
            skipped += 1
            continue

        src_path = VAULT_ROOT / rel_path
        if not src_path.exists():
            log.warning(f'Source not found (already moved?): {src_path}')
            skipped += 1
            continue

        dst_dir = VAULT_ROOT / final
        dst_path = dst_dir / src_path.name

        # Rename on conflict rather than silently overwriting
        if dst_path.exists():
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dst_path = dst_dir / f'{src_path.stem}_{stamp}{src_path.suffix}'
            log.warning(f'Conflict resolved: renamed to {dst_path.name}')

        # Detect human override: final differs from what model proposed
        human_override = bool(
            final != proposed
            and proposed not in ('', '_unfiled_')
        )

        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            fhash = compute_hash(dst_path)
            log_decision(
                conn,
                file_hash=fhash,
                filename=src_path.name,
                model_proposed=proposed or None,
                final_path=final,
                human_override=human_override,
                confidence=0.0,  # confidence not round-tripped through manifest
            )
            log.info(f'Moved: {rel_path} → {final}/{dst_path.name}')
            moved += 1

            if human_override:
                # Learn from this correction: use filename stem as pattern seed
                pattern = re.escape(src_path.stem[:30])
                new_rules.append((pattern, final))
                add_learned_rule(conn, pattern, final)
                print(f'  → Rule learned: "{pattern}" → {final}')

        except Exception as e:
            log.error(f'Failed to move {rel_path}: {e}')
            errors += 1

    conn.close()
    print(f'\n✓ Apply complete: {moved} moved, {skipped} skipped, {errors} errors')
    if new_rules:
        print(f'  {len(new_rules)} new rule(s) saved to classification.db')


def _apply_rows(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Internal apply used by --auto mode. Only moves ACCEPT rows."""
    moved = 0
    skipped = 0
    errors = 0

    for row in rows:
        if row['status'] != 'ACCEPT' or not row['final']:
            skipped += 1
            continue

        src_path = VAULT_ROOT / row['rel_path']
        if not src_path.exists():
            skipped += 1
            continue

        dst_dir = VAULT_ROOT / row['final']
        dst_path = dst_dir / src_path.name

        if dst_path.exists():
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dst_path = dst_dir / f'{src_path.stem}_{stamp}{src_path.suffix}'

        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            log_decision(
                conn,
                file_hash=row['file_hash'],
                filename=src_path.name,
                model_proposed=row['proposed'] or None,
                final_path=row['final'],
                human_override=False,
                confidence=row['confidence'],
            )
            log.info(f'Auto-moved: {row["rel_path"]} → {row["final"]}/{dst_path.name}')
            moved += 1
        except Exception as e:
            log.error(f'Failed to auto-move {row["rel_path"]}: {e}')
            errors += 1

    conn.commit()
    print(f'\n✓ Auto-apply complete: {moved} moved, {skipped} skipped, {errors} errors')


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='classify_content.py — Vault content classification CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Scan Notes/ and write manifest for review:
    python3 classify_content.py --scan

  Scan a specific subdirectory:
    python3 classify_content.py --scan --source Vault/Notes/Scratch

  Scan and move high-confidence files without review:
    python3 classify_content.py --scan --auto

  Apply a reviewed manifest:
    python3 classify_content.py --apply
        """,
    )
    parser.add_argument('--scan', action='store_true', help='Scan source dir, call Haiku, write manifest')
    parser.add_argument('--apply', action='store_true', help='Apply reviewed manifest, move files')
    parser.add_argument('--auto', action='store_true', help='With --scan: skip review, move ACCEPT files immediately')
    parser.add_argument(
        '--source',
        type=str,
        default=None,
        help='Source directory relative to Vault root (default: Notes)',
    )
    parser.add_argument('--verbose', '-v', action='store_true', help='Show per-file reasoning from Haiku')
    args = parser.parse_args()

    if not args.scan and not args.apply:
        parser.print_help()
        sys.exit(0)

    if args.scan and args.apply:
        print('Error: --scan and --apply are mutually exclusive.')
        sys.exit(1)

    if args.auto and args.apply:
        print('Error: --auto only applies with --scan.')
        sys.exit(1)

    if args.verbose:
        log.setLevel(logging.DEBUG)

    source_dir = VAULT_ROOT / (args.source if args.source else 'Notes')

    if args.scan:
        run_scan(source_dir, auto=args.auto, verbose=args.verbose)
    elif args.apply:
        run_apply()


if __name__ == '__main__':
    main()
