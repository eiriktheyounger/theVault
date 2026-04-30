#!/usr/bin/env python3
"""
JD Analyzer — ResumeEngine
Parses a job description and generates a tailored resume from Eric's context files.

Two-stage generation (default):
  Stage A — Sonnet generates ONLY: professional summary + tailored experience bullets
  Stage B — Pure Python assembles the complete resume by merging Stage A output
             with canonical data from context/_canonical.yaml

Legacy single-stage (--legacy flag):
  Sonnet generates the complete resume from scratch (deprecated, kept for comparison).

Usage:
    python3 ResumeEngine/jd_analyzer.py --jd path/to/jd.txt --output output/resume.md
    python3 ResumeEngine/jd_analyzer.py --jd-text "pasted JD text" --output output/resume.md

Flags:
    --jd          Path to a .txt file containing the job description
    --jd-text     Raw JD text (for quick runs)
    --output      Output path for the generated resume (default: output/resume-<timestamp>.md)
    --batch       Process all .txt files in ResumeEngine/jds/
    --verbose     Print scoring details and step logs
    --legacy      Use old single-stage generation (Sonnet writes full resume)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
import yaml
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from dotenv import load_dotenv

# Load .env from ResumeEngine/ first, then project root as fallback.
# override=True: an empty ANTHROPIC_API_KEY='' inherited from the shell must not block us.
load_dotenv(Path(__file__).parent / ".env", override=True)
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

# ---------------------------------------------------------------------------
# Paths (all relative to this file's parent — ResumeEngine/)
# ---------------------------------------------------------------------------

ENGINE_ROOT = Path(__file__).parent
CONFIG_DIR = ENGINE_ROOT / "config"
CONTEXT_DIR = ENGINE_ROOT / "context"
OUTPUT_DIR = ENGINE_ROOT / "output"
JDS_DIR = ENGINE_ROOT / "jds"
JDS_PROCESSED = JDS_DIR / "processed"
JDS_FAILED = JDS_DIR / "failed"

VOICE_GUIDE = CONFIG_DIR / "voice-guide.md"
FRAMING_RULES = CONFIG_DIR / "framing-rules.md"
BANNED_WORDS_FILE = CONFIG_DIR / "banned-words.md"
TEMPLATE_IC = CONFIG_DIR / "templates" / "resume-v1-ic.md"
TEMPLATE_SA = CONFIG_DIR / "templates" / "resume-v2-sa.md"

ROLES_DIR = CONTEXT_DIR / "roles"
PROJECTS_DIR = CONTEXT_DIR / "projects"
SKILLS_DIR = CONTEXT_DIR / "skills"
AWARDS_DIR = CONTEXT_DIR / "awards"
PATENTS_DIR = CONTEXT_DIR / "patents"
CANONICAL_PATH = CONTEXT_DIR / "_canonical.yaml"

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

# Banned words — authoritative list (also parsed from banned-words.md at runtime)
HARD_BANNED = [
    "spearheaded", "leveraged", "revolutionized", "best-in-class",
    "thought leader", "passionate about", "results-driven",
    "dynamic professional", "synergy", "impactful",
]

# JD signals that indicate Solutions Architect / pre-sales roles
SA_SIGNALS = [
    "solutions architect", "pre-sales", "presales", "technical sales",
    "sales engineer", "customer success architect", "technical account",
    "field engineer", "solution engineer", "client architect",
    "partner architect", "channel architect", "enterprise architect",
    "technical evangelist",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("jd_analyzer")


def set_verbose(flag: bool) -> None:
    if flag:
        logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# API call resilience — retry on 429/529/500/transient errors
# ---------------------------------------------------------------------------

# Debug-log directory for raw JSON responses on parse failure
DEBUG_LOG_DIR = ENGINE_ROOT / "output" / "_debug"

# Exceptions where a retry makes sense (transient server errors, rate limits)
_RETRIABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    anthropic.APIStatusError,
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
)


def _call_with_retry(
    client: anthropic.Anthropic,
    *,
    model: str,
    max_tokens: int,
    messages: list[dict],
    label: str = "api_call",
    max_attempts: int = 3,
) -> Any:
    """
    Call client.messages.create with exponential backoff on transient errors.
    Backoff: 5s, 10s, 20s (with jitter). Raises on non-retriable or after max_attempts.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
        except _RETRIABLE_EXCEPTIONS as exc:  # type: ignore[misc]
            last_exc = exc
            status = getattr(exc, "status_code", None)
            # Only retry on 429 / 5xx — other APIStatusErrors (400, 401, 403) fail fast
            if isinstance(exc, anthropic.APIStatusError) and status is not None and status < 500 and status != 429:
                raise
            if attempt == max_attempts:
                logger.error(f"{label}: exhausted {max_attempts} attempts — raising ({exc})")
                raise
            wait = (2 ** (attempt - 1)) * 5 + random.uniform(0, 2)
            logger.warning(f"{label}: attempt {attempt}/{max_attempts} failed ({exc}); retrying in {wait:.1f}s")
            time.sleep(wait)
    # Should be unreachable
    if last_exc:
        raise last_exc
    raise RuntimeError(f"{label}: unreachable retry path")


def _extract_text(response: Any) -> str:
    """Safely extract text from an Anthropic response, guarding empty content."""
    content = getattr(response, "content", None) or []
    if not content:
        return ""
    first = content[0]
    return (getattr(first, "text", "") or "").strip()


def _log_raw_failure(category: str, raw: str, exc: Exception) -> None:
    """Persist a raw response + error to _debug/ for offline inspection."""
    try:
        DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dbg = DEBUG_LOG_DIR / f"{category}_{ts}.txt"
        dbg.write_text(
            f"# {category} — {ts}\n"
            f"# error: {exc}\n"
            f"# raw_len: {len(raw)} chars\n"
            f"# raw_tail (last 400 chars):\n{raw[-400:]!r}\n"
            f"---\n{raw}\n",
            encoding="utf-8",
        )
        logger.error(f"{category}: raw response saved → {dbg}")
    except Exception as dbg_exc:
        logger.error(f"{category}: failed to save raw debug log: {dbg_exc}")


# ---------------------------------------------------------------------------
# File loading helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    """Read a file, return empty string on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not read {path}: {e}")
        return ""


def load_context_dir(directory: Path, skip_index: bool = True) -> dict[str, str]:
    """Load all .md files from a directory. Returns {stem: content}."""
    items: dict[str, str] = {}
    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return items
    for md in sorted(directory.glob("*.md")):
        if skip_index and md.stem.endswith("-index"):
            continue
        content = _read(md)
        if content.strip():
            items[md.stem] = content
    return items


def load_all_context() -> dict[str, dict[str, str]]:
    """Load all context categories."""
    return {
        "roles": load_context_dir(ROLES_DIR),
        "projects": load_context_dir(PROJECTS_DIR),
        "skills": load_context_dir(SKILLS_DIR),
        "awards": load_context_dir(AWARDS_DIR),
        "patents": load_context_dir(PATENTS_DIR),
    }


def load_config() -> dict[str, str]:
    """Load all config files."""
    return {
        "voice_guide": _read(VOICE_GUIDE),
        "framing_rules": _read(FRAMING_RULES),
        "banned_words": _read(BANNED_WORDS_FILE),
        "template_ic": _read(TEMPLATE_IC),
        "template_sa": _read(TEMPLATE_SA),
    }


def load_canonical() -> dict:
    """Load the canonical ground-truth manifest. Dies hard if missing."""
    if not CANONICAL_PATH.exists():
        raise FileNotFoundError(f"Canonical manifest missing: {CANONICAL_PATH}")
    with open(CANONICAL_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Validate essential keys are present
    for key in ("contact", "roles", "patents_granted", "awards", "education"):
        if key not in data:
            raise ValueError(f"Canonical manifest missing required key: {key}")
    return data


def parse_banned_words(banned_words_content: str) -> list[str]:
    """Extract the absolute ban list from banned-words.md."""
    words: list[str] = list(HARD_BANNED)  # always include hard-coded list
    in_absolute = False
    for line in banned_words_content.splitlines():
        if "Absolute Bans" in line:
            in_absolute = True
            continue
        if in_absolute:
            if line.startswith("##"):
                break
            m = re.match(r"^[-*]\s+(.+)$", line.strip())
            if m:
                words.append(m.group(1).strip().lower())
    return list(set(w.lower() for w in words if w))


# ---------------------------------------------------------------------------
# Step 1: Parse JD with Haiku
# ---------------------------------------------------------------------------

JD_PARSE_SCHEMA = {
    "role_title": "str — inferred job title",
    "role_type": "one of: ic, sa, pm, vp, ai_specialist, ad_tech",
    "company_name": "str or null",
    "required_skills": ["list of specific technical skills"],
    "preferred_skills": ["list of nice-to-have skills"],
    "keywords": ["important keywords for ATS and scoring"],
    "sa_signals": "bool — true if pre-sales/solutions architect signals present",
    "ai_emphasis": "bool — true if AI/ML is a primary focus",
    "ad_tech_emphasis": "bool — true if ad tech / monetization is a primary focus",
    "seniority": "one of: senior, principal, staff, vp, director, manager",
    "summary": "2-3 sentence plain-language description of what this role is looking for",
}


def parse_jd(client: anthropic.Anthropic, jd_text: str) -> dict:
    """Use Haiku to extract structured signals from the JD."""
    logger.info("Parsing JD with Haiku...")

    prompt = f"""Analyze this job description and return a JSON object with exactly these keys:

{json.dumps(JD_PARSE_SCHEMA, indent=2)}

Rules:
- role_type: "sa" if pre-sales/solutions architect; "ic" for individual contributor/engineer; "pm" for product; "vp" for director/VP; "ai_specialist" if AI/ML primary; "ad_tech" if advertising technology primary
- Be specific with required_skills — list actual technologies, not categories
- keywords: include both technical terms and business terms from the JD
- Return ONLY valid JSON, no explanation

JOB DESCRIPTION:
{jd_text}"""

    response = _call_with_retry(
        client,
        model=HAIKU_MODEL,
        max_tokens=2048,  # Phase 1: doubled from 1024 — long JDs can have many skills/keywords
        messages=[{"role": "user", "content": prompt}],
        label="parse_jd",
    )

    raw = _extract_text(response)
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
        parsed["_degraded"] = False
    except json.JSONDecodeError as e:
        _log_raw_failure("parse_jd", raw, e)
        logger.error(f"JD parse JSON error: {e} — DEGRADED fallback in use (resume will be generic)")
        # Return minimal fallback with _degraded flag so callers can warn or abort
        parsed = {
            "role_title": "Unknown Role",
            "role_type": "ic",
            "company_name": None,
            "required_skills": [],
            "preferred_skills": [],
            "keywords": [],
            "sa_signals": False,
            "ai_emphasis": False,
            "ad_tech_emphasis": False,
            "seniority": "senior",
            "summary": jd_text[:200],
            "_degraded": True,
        }

    logger.info(f"JD parsed: role_type={parsed.get('role_type')}, sa_signals={parsed.get('sa_signals')}")
    return parsed


# ---------------------------------------------------------------------------
# Step 2: Score context items with Haiku
# ---------------------------------------------------------------------------

def score_category(
    client: anthropic.Anthropic,
    category: str,
    items: dict[str, str],
    jd_analysis: dict,
) -> list[dict]:
    """Score all items in a category for relevance to the JD. Returns sorted list."""
    if not items:
        return []

    logger.info(f"Scoring {len(items)} {category} items...")

    # Build a compact representation of each item (first 400 chars to save tokens)
    item_summaries = {}
    for key, content in items.items():
        lines = [l.strip() for l in content.splitlines() if l.strip()][:12]
        item_summaries[key] = " | ".join(lines)[:400]

    prompt = f"""Score each {category} item for relevance to this job opportunity.

JOB ROLE: {jd_analysis.get('role_title', 'Unknown')} ({jd_analysis.get('role_type', 'ic')})
REQUIRED SKILLS: {', '.join(jd_analysis.get('required_skills', [])[:10])}
KEYWORDS: {', '.join(jd_analysis.get('keywords', [])[:15])}
JD SUMMARY: {jd_analysis.get('summary', '')}

{category.upper()} ITEMS TO SCORE:
{json.dumps(item_summaries, indent=2)}

Return a JSON array. Each element:
{{"key": "item_key", "score": 0-100, "reason": "one-line reason"}}

Score 90-100: directly matches required skills or role type
Score 70-89: strong supporting experience
Score 50-69: relevant background
Score 0-49: low relevance

Return ONLY valid JSON array, no explanation."""

    # Phase 1: dynamic budget — each entry takes ~50-80 output tokens.
    # 80 tokens/item + 150 overhead, capped at 8192.
    budget = max(1024, len(items) * 80 + 150)
    response = _call_with_retry(
        client,
        model=HAIKU_MODEL,
        max_tokens=min(budget, 8192),
        messages=[{"role": "user", "content": prompt}],
        label=f"score_{category}",
    )

    raw = _extract_text(response)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        scores = json.loads(raw)
        # Phase 2c: Haiku sometimes wraps the array in {"scores": [...]}. Unwrap if needed.
        if isinstance(scores, dict):
            for wrap_key in ("scores", "items", "results", "data"):
                if wrap_key in scores and isinstance(scores[wrap_key], list):
                    scores = scores[wrap_key]
                    break
            else:
                raise ValueError(f"Scoring response was a dict but has no known list key: {list(scores.keys())}")
        if not isinstance(scores, list):
            raise ValueError(f"Scoring response was not a list: {type(scores).__name__}")
    except (json.JSONDecodeError, ValueError) as e:
        _log_raw_failure(f"score_{category}", raw, e)
        logger.error(f"Scoring JSON error for {category}: {e} — using neutral fallback")
        scores = [{"key": k, "score": 50, "reason": "scoring unavailable"} for k in items]

    # Attach full content and sort by score desc
    for entry in scores:
        key = entry.get("key", "")
        entry["content"] = items.get(key, "")
        entry["category"] = category

    scores.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scores


def score_all_context(
    client: anthropic.Anthropic,
    context: dict[str, dict[str, str]],
    jd_analysis: dict,
    verbose: bool = False,
) -> dict[str, list[dict]]:
    """Score all context categories."""
    scored: dict[str, list[dict]] = {}
    for category, items in context.items():
        scored[category] = score_category(client, category, items, jd_analysis)
        if verbose:
            for entry in scored[category][:5]:
                print(f"  [{category}] {entry['key']}: {entry.get('score', 0)} — {entry.get('reason', '')}")
    return scored


# ---------------------------------------------------------------------------
# Step 3: Template selection
# ---------------------------------------------------------------------------

def select_template(jd_analysis: dict, config: dict[str, str]) -> tuple[str, str]:
    """
    Return (template_name, template_content).
    IC template for IC/PM/AI roles; SA template for solutions architect/pre-sales.
    Falls back to embedded structure if template file is empty.
    """
    role_type = jd_analysis.get("role_type", "ic")
    sa_signals = jd_analysis.get("sa_signals", False)

    # Check JD text for SA signals
    jd_lower = jd_analysis.get("summary", "").lower()
    role_title_lower = jd_analysis.get("role_title", "").lower()
    explicit_sa = any(sig in jd_lower or sig in role_title_lower for sig in SA_SIGNALS)

    use_sa = (role_type == "sa") or sa_signals or explicit_sa

    if use_sa:
        tmpl_content = config.get("template_sa", "").strip()
        tmpl_name = "resume-v2-sa"
    else:
        tmpl_content = config.get("template_ic", "").strip()
        tmpl_name = "resume-v1-ic"

    logger.info(f"Template selected: {tmpl_name} (role_type={role_type}, sa={use_sa})")
    return tmpl_name, tmpl_content


# ---------------------------------------------------------------------------
# Step 4a: Two-stage generation — Stage A prompt builder + executor
# ---------------------------------------------------------------------------

def build_bullet_prompt(
    jd_text: str,
    jd_analysis: dict,
    scored_context: dict[str, list[dict]],
    template_name: str,
    config: dict[str, str],
    canonical: dict,
) -> str:
    """Build prompt for Stage A: Sonnet tailors ONLY summary + experience bullets."""

    top_roles = scored_context.get("roles", [])[:6]
    top_projects = scored_context.get("projects", [])[:5]
    top_skills = scored_context.get("skills", [])[:4]

    def fmt_items(items: list[dict], max_chars: int = 12000) -> str:
        out, total = [], 0
        for item in items:
            block = f"### {item['key']} (score: {item.get('score', 0)})\n{item.get('content', '')}\n"
            if total + len(block) > max_chars:
                out.append(f"### {item['key']} (score: {item.get('score', 0)}) [truncated]\n")
                break
            out.append(block)
            total += len(block)
        return "\n".join(out)

    # Build the role stubs the LLM must populate with bullets
    role_stubs = []
    for role_key, role_info in canonical["roles"].items():
        role_stubs.append(
            f"- role_key: {role_key}\n"
            f"  company: {role_info['company']}\n"
            f"  title: {role_info['title']}\n"
            f"  dates: {role_info['dates']}"
        )

    is_sa = "sa" in template_name

    prompt = f"""You are tailoring resume content for Eric Manchester for a specific job.

## YOUR TASK
Generate ONLY two things:
1. A professional_summary (3-4 sentences tailored to this JD)
2. Tailored experience bullets for each role listed below

## CRITICAL CONSTRAINTS — READ CAREFULLY
- You are writing ONLY bullets and a summary. The full resume will be assembled by a separate system.
- DO NOT output job titles, dates, company names, patents, awards, education, or contact info.
- DO NOT fabricate skills, certifications, or technologies Eric doesn't have.
- DO NOT include technologies that appear in the JD but NOT in Eric's context (no JD-text leakage).
- If a skill from the JD matches something in Eric's context, include it. If it doesn't match, OMIT IT.
- For NBCU: include EXACTLY this departure note: "During organizational restructuring in early 2025, I transitioned from NBCUniversal."

## JOB DESCRIPTION
{jd_text}

## JD ANALYSIS
- Role: {jd_analysis.get('role_title')} ({jd_analysis.get('role_type')})
- Required: {', '.join(jd_analysis.get('required_skills', []))}
- Keywords: {', '.join(jd_analysis.get('keywords', [])[:15])}

## VOICE GUIDE
{config.get('voice_guide', '')}

## FRAMING RULES
{config.get('framing_rules', '')}

## BANNED WORDS (NEVER use)
{', '.join(HARD_BANNED)}

## ERIC'S ROLES (generate bullets for EACH — {4 if is_sa else 5}-6 bullets per role)
{chr(10).join(role_stubs)}

## ERIC'S CONTEXT (source material for bullets — ONLY use facts from here)
### Roles
{fmt_items(top_roles, 12000)}

### Projects
{fmt_items(top_projects, 6000)}

### Skills
{fmt_items(top_skills, 4000)}

## OUTPUT FORMAT — Return ONLY valid JSON:
{{
  "professional_summary": "3-4 sentence summary tailored to this JD",
  "core_skills": {{
    "Group Name 1": "skill1, skill2, skill3",
    "Group Name 2": "skill1, skill2, skill3"
  }},
  "roles": {{
    "harmonic": {{
      "nbcu_departure_note": null,
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    "nbcu": {{
      "nbcu_departure_note": "During organizational restructuring in early 2025, I transitioned from NBCUniversal.",
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    "leidos": {{
      "nbcu_departure_note": null,
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    "ooyala": {{
      "nbcu_departure_note": null,
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    "re_kreations": {{
      "nbcu_departure_note": null,
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    "twc_2012": {{
      "nbcu_departure_note": null,
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    "twc_2006": {{
      "nbcu_departure_note": null,
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    "aol": {{
      "nbcu_departure_note": null,
      "bullets": ["bullet 1", "bullet 2", ...]
    }}
  }}
}}

{"Lead each bullet with customer/business outcome." if is_sa else "Lead each bullet with technical approach then impact."}
Every bullet: action verb + technical detail + measurable outcome where available.
Generate the JSON now:"""

    return prompt


def tailor_content(client: anthropic.Anthropic, prompt: str) -> dict:
    """Stage A: Sonnet generates tailored summary + bullets. Returns parsed JSON."""
    logger.info("Stage A: Generating tailored bullets with Sonnet...")

    response = _call_with_retry(
        client,
        model=SONNET_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
        label="tailor_content",
    )

    raw = _extract_text(response)
    if not raw:
        _log_raw_failure("tailor_content", repr(response), RuntimeError("empty content"))
        raise RuntimeError("Stage A returned empty content")

    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        _log_raw_failure("tailor_content", raw, e)
        raise RuntimeError(f"Stage A JSON parse error: {e}")


# ---------------------------------------------------------------------------
# Step 4a-post: Sanitize tailored content — strip banned claims the LLM leaked
# ---------------------------------------------------------------------------

def sanitize_tailored_content(tailored: dict, canonical: dict) -> dict:
    """Strip banned claims from LLM-generated bullets and skills before assembly.

    The LLM sometimes injects JD-specific product names (EdgeWorkers, LKE, etc.)
    or wrong framing ("independent architect") into bullets despite prompt constraints.
    This function catches those at the data level before they reach the resume.
    """
    banned = [b.lower() for b in canonical.get("banned_claims", [])]
    if not banned:
        return tailored

    def _clean_text(text: str) -> str:
        """Remove banned terms from a string. For skills: remove the term. For bullets: flag."""
        lower = text.lower()
        for b in banned:
            if b in lower:
                # For short banned terms (single words), remove them from comma-separated lists
                # For phrases, remove the whole phrase
                text = re.sub(re.escape(b), "", text, flags=re.IGNORECASE).strip()
                # Clean up double commas, leading/trailing commas from removal
                text = re.sub(r",\s*,", ",", text)
                text = re.sub(r"^\s*,\s*", "", text)
                text = re.sub(r"\s*,\s*$", "", text)
                text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    # Sanitize core_skills groups
    if "core_skills" in tailored:
        cleaned_skills: dict[str, str] = {}
        for group, skills_str in tailored["core_skills"].items():
            cleaned = _clean_text(skills_str)
            if cleaned:  # only keep non-empty groups
                cleaned_skills[group] = cleaned
        tailored["core_skills"] = cleaned_skills

    # Sanitize role bullets
    if "roles" in tailored:
        for role_key, role_data in tailored["roles"].items():
            if "bullets" in role_data:
                cleaned_bullets = []
                for bullet in role_data["bullets"]:
                    cleaned = _clean_text(bullet)
                    if cleaned and len(cleaned) > 20:  # skip gutted bullets
                        cleaned_bullets.append(cleaned)
                role_data["bullets"] = cleaned_bullets

    # Sanitize summary
    if "professional_summary" in tailored:
        tailored["professional_summary"] = _clean_text(tailored["professional_summary"])

    return tailored


# ---------------------------------------------------------------------------
# Step 4b: Stage B — Pure Python assembly of canonical + tailored into markdown
# ---------------------------------------------------------------------------

def assemble_resume_md(
    canonical: dict,
    tailored: dict,
    jd_analysis: dict,
    template_name: str,
) -> str:
    """Stage B: Pure Python assembly of canonical data + tailored bullets into markdown.

    The LLM never touches: contact info, job titles, dates, patents, awards,
    affiliations, education, certifications.
    """
    c = canonical["contact"]
    lines: list[str] = []

    # Header
    lines.append(f"# {c['name']}\n")
    lines.append(f"{c['email']} | {c['phone']} | {c['linkedin']} | {c['location']}\n")
    lines.append("---\n")

    # Professional Summary
    lines.append("## Professional Summary\n")
    lines.append(tailored.get("professional_summary", "") + "\n")
    lines.append("---\n")

    # Core Skills / Competencies
    is_sa = "sa" in template_name
    header = "Core Competencies" if is_sa else "Core Technical Skills"
    lines.append(f"## {header}\n")
    for group_name, skills_str in tailored.get("core_skills", {}).items():
        lines.append(f"**{group_name}:** {skills_str}\n")
    lines.append("\n---\n")

    # Professional Experience
    lines.append("## Professional Experience\n")
    for role_key, role_info in canonical["roles"].items():
        lines.append(
            f"### {role_info['company']} | {role_info['title']} | "
            f"{role_info['dates']} | {role_info.get('location', '')}\n"
        )

        role_tailored = tailored.get("roles", {}).get(role_key, {})

        # NBCU departure note
        departure = role_tailored.get("nbcu_departure_note")
        if departure and role_key == "nbcu":
            lines.append(f"{departure}\n")

        for bullet in role_tailored.get("bullets", []):
            b = bullet.strip()
            if not b.startswith("- "):
                b = f"- {b}"
            lines.append(f"{b}\n")
        lines.append("\n---\n")

    # Patents (always from canonical — ALL of them)
    granted = canonical.get("patents_granted", [])
    pending = canonical.get("patents_pending", [])
    lines.append(f"## Patents ({len(granted)} Granted | {len(pending)} Pending)\n")
    lines.append("**Granted:**\n")
    for p in granted:
        line = f"- {p['number']} — {p['title']} ({p.get('company', '')})"
        note = p.get("note", "")
        if note:
            line += f" — {note}"
        lines.append(line + "\n")
    if pending:
        lines.append("\n**Pending:**\n")
        for p in pending:
            line = f"- {p.get('number', 'N/A')} — {p.get('title', 'Pending')} ({p.get('company', '')})"
            note = p.get("note", "")
            if note:
                line += f" — {note}"
            lines.append(line + "\n")
    lines.append("\n---\n")

    # Awards (always from canonical — ALL of them)
    lines.append("## Awards & Recognition\n")
    for a in canonical.get("awards", []):
        lines.append(f"- **{a['title']}** ({a['year']}) — {a['subtitle']}\n")
    lines.append("\n---\n")

    # Affiliations
    affiliations = canonical.get("affiliations", [])
    if affiliations:
        lines.append("## Professional Affiliations\n")
        for aff in affiliations:
            lines.append(f"- {aff}\n")
        lines.append("\n---\n")

    # Education
    edu = canonical.get("education", {})
    lines.append("## Education\n")
    if edu.get("degree"):
        lines.append(f"{edu['degree']} | {edu['school']} | {edu['dates']}\n")
    else:
        lines.append(f"{edu.get('school', '')} | {edu.get('dates', '')}\n")

    # Certifications (only if any exist)
    certs = canonical.get("certifications", [])
    if certs:
        lines.append("\n## Certifications\n")
        for cert in certs:
            lines.append(f"- {cert}\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Step 4 (LEGACY): Build generation prompt — DEPRECATED, kept for rollback
# ---------------------------------------------------------------------------

STRUCTURE_IC = """
## Resume Structure — IC/PM/AI Specialist
1. Header: Name, contact, LinkedIn, location
2. Professional Summary: 3-4 lines, role-tailored, no banned words
3. Core Technical Skills: grouped by domain, keyword-rich
4. Professional Experience: reverse chronological
   - Each role: Company, Title, Dates, Location (Remote if applicable)
   - 4-6 bullets per role: action verb + technical detail + measurable outcome
   - NBCUniversal: two-sentence departure framing ("Organizational restructuring"), then bullets
5. Patents: title, number, status, one-line relevance
6. Awards & Recognition: Emmy awards with year and project name
7. Education & Certifications (if space)
"""

STRUCTURE_SA = """
## Resume Structure — Solutions Architect / Technical Sales
1. Header: Name, contact, LinkedIn, location
2. Professional Summary: 3-4 lines emphasizing customer-facing, scalable solution design
3. Core Competencies: business-aligned skill groupings (not just tech)
4. Professional Experience: reverse chronological
   - Each role: Company, Title, Dates, Location
   - 4-6 bullets: customer/business outcome first, technical method second
   - Emphasize: RFP wins, POCs delivered, revenue influenced, enterprise accounts
   - NBCUniversal: two-sentence departure framing, then bullets
5. Technical Expertise: platform/product knowledge relevant to SA role
6. Patents: relevant only; title, number, status
7. Awards & Recognition: Emmy awards, vendor certifications
8. Education & Certifications
"""


def build_generation_prompt(
    jd_text: str,
    jd_analysis: dict,
    scored_context: dict[str, list[dict]],
    template_name: str,
    template_content: str,
    config: dict[str, str],
) -> str:
    """Build the full prompt for Sonnet resume generation.

    DEPRECATED — kept for rollback. Use build_bullet_prompt() + tailor_content()
    + assemble_resume_md() instead. Activate via --legacy flag.
    """

    # Select top items from each category
    top_roles = scored_context.get("roles", [])[:6]
    top_projects = scored_context.get("projects", [])[:5]
    top_skills = scored_context.get("skills", [])[:4]
    top_awards = scored_context.get("awards", [])
    top_patents = scored_context.get("patents", [])[:6]

    def fmt_items(items: list[dict], max_chars: int = 800) -> str:
        out = []
        total = 0
        for item in items:
            block = f"### {item['key']} (score: {item.get('score', 0)})\n{item.get('content', '')}\n"
            if total + len(block) > max_chars:
                out.append(f"### {item['key']} (score: {item.get('score', 0)}) [truncated]\n")
                break
            out.append(block)
            total += len(block)
        return "\n".join(out)

    structure = STRUCTURE_SA if "sa" in template_name else STRUCTURE_IC

    template_section = ""
    if template_content:
        template_section = f"\n## TEMPLATE STRUCTURE (follow this layout):\n{template_content}\n"
    else:
        template_section = f"\n## RESUME STRUCTURE TO FOLLOW:\n{structure}\n"

    prompt = f"""You are writing a tailored resume for Eric Manchester.

## TASK
Generate a complete, tailored resume for the job description below.
Follow Eric's voice guide, framing rules, and NEVER use any banned words.

## JOB DESCRIPTION
{jd_text}

## JD ANALYSIS
- Role Title: {jd_analysis.get('role_title')}
- Role Type: {jd_analysis.get('role_type')}
- Required Skills: {', '.join(jd_analysis.get('required_skills', []))}
- Key Signals: SA={jd_analysis.get('sa_signals')}, AI={jd_analysis.get('ai_emphasis')}, AdTech={jd_analysis.get('ad_tech_emphasis')}
- Summary: {jd_analysis.get('summary')}
{template_section}
## VOICE GUIDE (follow strictly)
{config.get('voice_guide', '')}

## FRAMING RULES (follow strictly)
{config.get('framing_rules', '')}

## BANNED WORDS (NEVER appear in output)
{', '.join(HARD_BANNED)}

NBCUniversal departure rule: "Organizational restructuring" ONLY — two sentences maximum, then redirect immediately to accomplishments.

## TOP-SCORED ROLES (use these, ranked by relevance)
{fmt_items(top_roles, 12000)}

## TOP-SCORED PROJECTS (highlight these)
{fmt_items(top_projects, 6000)}

## TOP-SCORED SKILLS (map to JD requirements)
{fmt_items(top_skills, 4000)}

## AWARDS (include all Emmys)
{fmt_items(top_awards, 2000)}

## TOP-SCORED PATENTS (include if technically relevant)
{fmt_items(top_patents, 3000)}

## GENERATION RULES
1. Use action verbs: Architected, Designed, Built, Delivered, Engineered, Developed — never "Helped" or "Assisted"
2. Every bullet ends with a measurable outcome or scale indicator where available
3. Match keywords from the JD naturally throughout the resume
4. Be specific: real technologies, real numbers, real scale
5. No objective statement
6. No "references available upon request"
7. Accomplishments before responsibilities in every role
8. If role type is SA: lead each bullet with business/customer outcome, then method
9. If role type is IC: lead with technical approach, then scale/impact
10. Output clean Markdown, ready to copy into Obsidian or convert to PDF

Generate the complete resume now:"""

    return prompt


# ---------------------------------------------------------------------------
# Step 5 (LEGACY): Generate resume with Sonnet — DEPRECATED, kept for rollback
# ---------------------------------------------------------------------------

def generate_resume(client: anthropic.Anthropic, prompt: str) -> str:
    """Generate the tailored resume using Sonnet.

    DEPRECATED — kept for rollback. Use tailor_content() + assemble_resume_md() instead.
    Activate via --legacy flag.
    """
    logger.info("Generating resume with Sonnet...")

    response = _call_with_retry(
        client,
        model=SONNET_MODEL,
        max_tokens=8192,  # Phase 1: doubled — full resumes hit ~5-6k tokens
        messages=[{"role": "user", "content": prompt}],
        label="generate_resume",
    )

    text = _extract_text(response)
    if not text:
        _log_raw_failure("generate_resume", repr(response), RuntimeError("empty content"))
    return text


# ---------------------------------------------------------------------------
# Step 6: Banned words validation
# ---------------------------------------------------------------------------

def check_banned_words(text: str, banned: list[str]) -> list[str]:
    """Return list of any banned words found in the generated text."""
    text_lower = text.lower()
    found = []
    for word in banned:
        if word.lower() in text_lower:
            found.append(word)
    return found


def fix_banned_words(
    client: anthropic.Anthropic,
    resume_text: str,
    found: list[str],
) -> str:
    """Ask Haiku to remove banned words from the resume."""
    logger.info(f"Fixing banned words: {found}")

    prompt = f"""This resume contains banned words that must be removed and replaced.

BANNED WORDS FOUND: {', '.join(found)}

REPLACEMENT RULES:
- "spearheaded" → "designed" or "built" or "architected"
- "leveraged" → "used" or "applied" or "deployed"
- "revolutionized" → "transformed" or "rebuilt" or "redesigned"
- "impactful" → describe the actual impact with numbers/outcomes
- "synergy" → describe the actual integration or collaboration
- "thought leader" → cite a specific contribution
- "results-driven" → remove entirely, let the bullets speak
- "passionate about" → remove entirely
- "dynamic professional" → remove entirely
- "best-in-class" → cite specific metric or recognition
- "leveraged" → use the specific technology/tool name

Return the complete resume with all banned words replaced. Maintain all formatting.
Do not add any explanation — output only the corrected resume.

RESUME:
{resume_text}"""

    response = _call_with_retry(
        client,
        model=HAIKU_MODEL,
        max_tokens=8192,  # Phase 1: doubled — mechanical substitution on a full resume
        messages=[{"role": "user", "content": prompt}],
        label="fix_banned_words",
    )

    text = _extract_text(response)
    if not text:
        _log_raw_failure("fix_banned_words", repr(response), RuntimeError("empty content"))
        # If rewrite returned empty, keep the original rather than nuking the resume
        return resume_text
    return text


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_single_jd(
    client: anthropic.Anthropic,
    jd_text: str,
    output_path: Path,
    context: dict[str, dict[str, str]],
    config: dict[str, str],
    banned: list[str],
    verbose: bool = False,
    legacy: bool = False,
) -> None:
    """Process a single JD and write the resume to output_path.

    Default (two-stage):
      Stage A — Sonnet generates tailored summary + bullets (JSON)
      Stage B — Pure Python assembles markdown from canonical + tailored data

    Legacy (--legacy flag):
      Sonnet generates the complete resume in a single pass (old behaviour).
    """
    # 1. Parse JD (unchanged)
    jd_analysis = parse_jd(client, jd_text)

    # Phase 3b: if JD parsing degraded to fallback, abort instead of generating a generic resume
    if jd_analysis.get("_degraded"):
        raise RuntimeError(
            "JD parse degraded — Haiku returned invalid JSON. See output/_debug/parse_jd_*.txt. "
            "Refusing to generate a generic resume."
        )

    # 2. Score context (unchanged)
    scored_context = score_all_context(client, context, jd_analysis, verbose=verbose)

    # 3. Select template (unchanged)
    template_name, template_content = select_template(jd_analysis, config)

    if legacy:
        # --- LEGACY single-stage path ---
        prompt = build_generation_prompt(
            jd_text=jd_text,
            jd_analysis=jd_analysis,
            scored_context=scored_context,
            template_name=template_name,
            template_content=template_content,
            config=config,
        )
        resume_text = generate_resume(client, prompt)
    else:
        # --- TWO-STAGE path ---

        # 4. Load canonical data
        canonical = load_canonical()

        # 5. Stage A: Sonnet tailors summary + bullets
        prompt = build_bullet_prompt(
            jd_text=jd_text,
            jd_analysis=jd_analysis,
            scored_context=scored_context,
            template_name=template_name,
            config=config,
            canonical=canonical,
        )
        tailored = tailor_content(client, prompt)

        # 5b. Sanitize: strip any banned claims the LLM leaked through
        tailored = sanitize_tailored_content(tailored, canonical)

        # 6. Stage B: Pure Python assembly into markdown
        resume_text = assemble_resume_md(canonical, tailored, jd_analysis, template_name)

    # 7. Banned words check (both paths)
    found_banned = check_banned_words(resume_text, banned)
    if found_banned:
        resume_text = fix_banned_words(client, resume_text, found_banned)
        remaining = check_banned_words(resume_text, banned)
        if remaining:
            logger.warning(f"Banned words remaining after fix: {remaining}")

    # 8. Fabrication scan (two-stage path only; skipped gracefully if module not ready)
    if not legacy:
        try:
            from scan_fabrications import scan_resume
            violations = scan_resume(resume_text, canonical)  # type: ignore[possibly-undefined]
            if violations:
                logger.warning(f"Fabrication scan found {len(violations)} issues:")
                for v in violations:
                    logger.warning(f"  - {v}")
                viol_path = output_path.with_suffix(".violations.txt")
                viol_path.write_text("\n".join(violations), encoding="utf-8")
        except (ImportError, ModuleNotFoundError):
            logger.info("scan_fabrications not available — skipping fabrication scan")

    # 9. Write .md
    output_path.write_text(resume_text, encoding="utf-8")

    # 10. Write .docx (two-stage path only)
    if not legacy:
        try:
            from render_docx import render_resume_docx
            docx_path = output_path.with_suffix(".docx")
            render_resume_docx(
                output_path=docx_path,
                canonical=canonical,  # type: ignore[possibly-undefined]
                tailored=tailored,    # type: ignore[possibly-undefined]
                jd_analysis=jd_analysis,
                template_name=template_name,
            )
            logger.info(f"DOCX written: {docx_path}")
        except (ImportError, ModuleNotFoundError):
            logger.info("render_docx not available — .docx output skipped")
        except Exception as e:
            logger.error(f"DOCX render failed: {e}")


def run_batch(verbose: bool = False, legacy: bool = False) -> None:
    """Process all .txt files in jds/ directory, FIFO by modification time."""
    JDS_DIR.mkdir(parents=True, exist_ok=True)
    JDS_PROCESSED.mkdir(parents=True, exist_ok=True)
    JDS_FAILED.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pending = sorted(JDS_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime)

    if not pending:
        print("No .txt files found in ResumeEngine/jds/ — nothing to process.")
        return

    print(f"\n{'='*60}")
    print(f"  ResumeEngine Batch — {len(pending)} JD(s) to process")
    print(f"{'='*60}\n")

    # Load context & config once
    print("Loading context files...")
    context = load_all_context()
    config = load_config()
    banned = parse_banned_words(config.get("banned_words", ""))
    total_items = sum(len(v) for v in context.values())
    print(f"  Loaded {total_items} context items across {len(context)} categories\n")

    # Create client
    client = anthropic.Anthropic()

    results = []

    for jd_file in pending:
        output_name = jd_file.stem + ".md"
        output_path = OUTPUT_DIR / output_name
        print(f"Processing: {jd_file.name} → {output_name}")

        try:
            jd_text = jd_file.read_text(encoding="utf-8").strip()
            if not jd_text:
                raise ValueError("Empty JD file")

            # Process the JD
            process_single_jd(
                client=client,
                jd_text=jd_text,
                output_path=output_path,
                context=context,
                config=config,
                banned=banned,
                verbose=verbose,
                legacy=legacy,
            )

            # Move to processed
            dest = JDS_PROCESSED / jd_file.name
            jd_file.rename(dest)
            results.append((jd_file.name, "OK", str(output_path)))
            print(f"  ✓ Done → moved to processed/\n")

        except Exception as e:
            import traceback
            dest = JDS_FAILED / jd_file.name
            jd_file.rename(dest)
            # Phase 2d: write a companion error log next to the failed JD for post-mortem
            try:
                err_log = JDS_FAILED / f"{jd_file.stem}_error.log"
                err_log.write_text(
                    f"# {jd_file.name} failed at {datetime.now().isoformat()}\n"
                    f"# error: {e}\n\n"
                    f"{traceback.format_exc()}\n",
                    encoding="utf-8",
                )
            except Exception as log_exc:
                logger.error(f"Could not write error log for {jd_file.name}: {log_exc}")
            results.append((jd_file.name, "FAILED", str(e)))
            print(f"  ✗ Failed: {e} → moved to failed/\n")
            logger.error(f"Batch failed for {jd_file.name}: {e}")

    # Summary
    ok_count = sum(1 for r in results if r[1] == "OK")
    print(f"\n{'='*60}")
    print(f"  Batch Complete: {ok_count}/{len(results)} succeeded")
    print(f"{'='*60}")
    for name, status, detail in results:
        icon = "✓" if status == "OK" else "✗"
        print(f"  {icon} {name} — {detail}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="JD Analyzer — generate a tailored resume from a job description"
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--jd", type=Path, help="Path to a .txt file with the job description")
    group.add_argument("--jd-text", type=str, help="Paste JD text directly")
    parser.add_argument("--batch", action="store_true", help="Process all .txt files in ResumeEngine/jds/, move to processed/ on success or failed/ on error")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for the resume (default: output/resume-<timestamp>.md)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print scoring details")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use old single-stage generation (Sonnet writes full resume). Kept for comparison only.",
    )
    args = parser.parse_args()

    # Validation: ensure one of --batch, --jd, or --jd-text is provided
    if not args.batch and not args.jd and not args.jd_text:
        parser.error("Either --batch, --jd, or --jd-text is required")

    set_verbose(args.verbose)

    # --- Handle batch mode ---
    if args.batch:
        run_batch(verbose=args.verbose, legacy=args.legacy)
        return

    # --- Load JD ---
    if args.jd:
        jd_path = args.jd if args.jd.is_absolute() else Path.cwd() / args.jd
        if not jd_path.exists():
            print(f"Error: JD file not found: {jd_path}", file=sys.stderr)
            sys.exit(1)
        jd_text = jd_path.read_text(encoding="utf-8").strip()
    else:
        jd_text = args.jd_text.strip()

    if not jd_text:
        print("Error: JD text is empty.", file=sys.stderr)
        sys.exit(1)

    # --- Output path ---
    if args.output:
        output_path = args.output if args.output.is_absolute() else Path.cwd() / args.output
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"resume-{ts}.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Load context & config ---
    print("Loading context files...")
    context = load_all_context()
    config = load_config()
    banned = parse_banned_words(config.get("banned_words", ""))

    total_items = sum(len(v) for v in context.values())
    print(f"  Loaded {total_items} context items across {len(context)} categories")

    # --- Anthropic client ---
    client = anthropic.Anthropic()

    # --- Parse JD ---
    print("Parsing job description...")
    jd_analysis = parse_jd(client, jd_text)
    print(f"  Role: {jd_analysis.get('role_title')} ({jd_analysis.get('role_type')})")
    print(f"  Company: {jd_analysis.get('company_name') or 'not specified'}")
    print(f"  Required skills: {', '.join(jd_analysis.get('required_skills', [])[:6])}")

    # Phase 3b: warn loudly if JD parsing degraded — resume will be generic
    if jd_analysis.get("_degraded"):
        print(
            "\n  ⚠️  JD PARSE DEGRADED — Haiku returned invalid JSON. "
            "Resume will be generic. See output/_debug/parse_jd_*.txt for the raw response.\n",
            file=sys.stderr,
        )

    # --- Score context ---
    print("Scoring context for relevance...")
    scored_context = score_all_context(client, context, jd_analysis, verbose=args.verbose)

    if args.verbose:
        print("\nTop matches per category:")
        for cat, items in scored_context.items():
            if items:
                top = items[0]
                print(f"  {cat}: {top['key']} ({top.get('score', 0)}) — {top.get('reason', '')}")

    # --- Select template ---
    template_name, template_content = select_template(jd_analysis, config)
    print(f"Template: {template_name}")

    if args.legacy:
        # --- LEGACY single-stage path ---
        print("Generating resume (legacy single-stage)...")
        prompt = build_generation_prompt(
            jd_text=jd_text,
            jd_analysis=jd_analysis,
            scored_context=scored_context,
            template_name=template_name,
            template_content=template_content,
            config=config,
        )
        resume_text = generate_resume(client, prompt)
        tailored = None
        canonical = None
    else:
        # --- TWO-STAGE path ---
        print("Loading canonical manifest...")
        canonical = load_canonical()
        print(f"  {len(canonical.get('roles', {}))} roles, "
              f"{len(canonical.get('patents_granted', []))} patents granted, "
              f"{len(canonical.get('awards', []))} awards")

        print("Stage A: Generating tailored summary + bullets with Sonnet...")
        bullet_prompt = build_bullet_prompt(
            jd_text=jd_text,
            jd_analysis=jd_analysis,
            scored_context=scored_context,
            template_name=template_name,
            config=config,
            canonical=canonical,
        )
        tailored = tailor_content(client, bullet_prompt)
        tailored = sanitize_tailored_content(tailored, canonical)
        print("  Stage A complete.")

        print("Stage B: Assembling resume from canonical data...")
        resume_text = assemble_resume_md(canonical, tailored, jd_analysis, template_name)
        print("  Stage B complete.")

    # --- Validate banned words ---
    found_banned = check_banned_words(resume_text, banned)
    if found_banned:
        print(f"  Banned words found: {found_banned} — fixing...")
        resume_text = fix_banned_words(client, resume_text, found_banned)
        remaining = check_banned_words(resume_text, banned)
        if remaining:
            print(f"  Warning: {remaining} could not be removed automatically", file=sys.stderr)

    # --- Fabrication scan (two-stage path only) ---
    if not args.legacy:
        try:
            from scan_fabrications import scan_resume
            violations = scan_resume(resume_text, canonical)  # type: ignore[arg-type]
            if violations:
                print(f"  Fabrication scan: {len(violations)} issues found — see .violations.txt")
                logger.warning(f"Fabrication scan found {len(violations)} issues")
                for v in violations:
                    logger.warning(f"  - {v}")
                viol_path = output_path.with_suffix(".violations.txt")
                viol_path.write_text("\n".join(violations), encoding="utf-8")
            else:
                print("  Fabrication scan: clean.")
        except ImportError:
            logger.info("scan_fabrications not available — skipping fabrication scan")

    # --- Write .md ---
    output_path.write_text(resume_text, encoding="utf-8")
    print(f"\nResume written to: {output_path}")

    # --- Write .docx (two-stage path only) ---
    if not args.legacy:
        try:
            from render_docx import render_resume_docx
            docx_path = output_path.with_suffix(".docx")
            render_resume_docx(
                output_path=docx_path,
                canonical=canonical,    # type: ignore[arg-type]
                tailored=tailored,      # type: ignore[arg-type]
                jd_analysis=jd_analysis,
                template_name=template_name,
            )
            print(f"DOCX written to:   {docx_path}")
        except (ImportError, ModuleNotFoundError):
            logger.info("render_docx not available — .docx output skipped")
        except Exception as e:
            logger.error(f"DOCX render failed: {e}")
            print(f"  Warning: DOCX render failed: {e}", file=sys.stderr)

    # --- Print analysis summary ---
    print(f"\n--- Analysis Summary ---")
    print(f"Role type:   {jd_analysis.get('role_type')} | Template: {template_name}")
    print(f"AI focus:    {'yes' if jd_analysis.get('ai_emphasis') else 'no'}")
    print(f"Ad tech:     {'yes' if jd_analysis.get('ad_tech_emphasis') else 'no'}")
    print(f"SA signals:  {'yes' if jd_analysis.get('sa_signals') else 'no'}")
    print(f"Keywords:    {', '.join(jd_analysis.get('keywords', [])[:8])}")
    print(f"Output:      {len(resume_text)} chars")


if __name__ == "__main__":
    main()
