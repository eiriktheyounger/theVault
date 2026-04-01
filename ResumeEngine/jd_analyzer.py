#!/usr/bin/env python3
"""
JD Analyzer — ResumeEngine
Parses a job description and generates a tailored resume from Eric's context files.

Usage:
    python3 ResumeEngine/jd_analyzer.py --jd path/to/jd.txt --output output/resume.md
    python3 ResumeEngine/jd_analyzer.py --jd-text "pasted JD text" --output output/resume.md

Flags:
    --jd          Path to a .txt file containing the job description
    --jd-text     Raw JD text (for quick runs)
    --output      Output path for the generated resume (default: output/resume-<timestamp>.md)
    --verbose     Print scoring details and step logs
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic

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

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JD parse JSON error: {e}\nRaw: {raw[:200]}")
        # Return minimal fallback
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

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        scores = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Scoring JSON error for {category}: {e}")
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
# Step 4: Build generation prompt
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
    """Build the full prompt for Sonnet resume generation."""

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
{fmt_items(top_roles, 2000)}

## TOP-SCORED PROJECTS (highlight these)
{fmt_items(top_projects, 1500)}

## TOP-SCORED SKILLS (map to JD requirements)
{fmt_items(top_skills, 1200)}

## AWARDS (include all Emmys)
{fmt_items(top_awards, 800)}

## TOP-SCORED PATENTS (include if technically relevant)
{fmt_items(top_patents, 800)}

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
# Step 5: Generate resume with Sonnet
# ---------------------------------------------------------------------------

def generate_resume(client: anthropic.Anthropic, prompt: str) -> str:
    """Generate the tailored resume using Sonnet."""
    logger.info("Generating resume with Sonnet...")

    response = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


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

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


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
    args = parser.parse_args()

    # Validation: ensure one of --batch, --jd, or --jd-text is provided
    if not args.batch and not args.jd and not args.jd_text:
        parser.error("Either --batch, --jd, or --jd-text is required")

    set_verbose(args.verbose)

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

    # --- Build prompt ---
    prompt = build_generation_prompt(
        jd_text=jd_text,
        jd_analysis=jd_analysis,
        scored_context=scored_context,
        template_name=template_name,
        template_content=template_content,
        config=config,
    )

    # --- Generate ---
    print("Generating resume...")
    resume_text = generate_resume(client, prompt)

    # --- Validate banned words ---
    found_banned = check_banned_words(resume_text, banned)
    if found_banned:
        print(f"  Banned words found: {found_banned} — fixing...")
        resume_text = fix_banned_words(client, resume_text, found_banned)
        remaining = check_banned_words(resume_text, banned)
        if remaining:
            print(f"  Warning: {remaining} could not be removed automatically", file=sys.stderr)

    # --- Write output ---
    output_path.write_text(resume_text, encoding="utf-8")
    print(f"\nResume written to: {output_path}")

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
