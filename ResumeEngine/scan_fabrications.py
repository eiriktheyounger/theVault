#!/usr/bin/env python3
"""
scan_fabrications.py — Post-generation resume validator.

Checks a generated resume against the canonical ground-truth manifest
(_canonical.yaml) and flags fabrications, omissions, and errors.

Usage:
    # As module (called by jd_analyzer.py after generation):
    from ResumeEngine.scan_fabrications import scan_resume
    violations = scan_resume(resume_text, canonical_data)

    # As CLI (for manual verification):
    python3 ResumeEngine/scan_fabrications.py ResumeEngine/output/SomeResume.md
    python3 ResumeEngine/scan_fabrications.py --all  # scan all .md in output/
"""

import re
import sys
import yaml
from pathlib import Path
from typing import Any

CANONICAL_PATH = Path(__file__).parent / "context" / "_canonical.yaml"


def load_canonical() -> dict:
    """Load canonical manifest."""
    with open(CANONICAL_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def scan_resume(resume_text: str, canonical: dict | None = None) -> list[str]:
    """
    Scan resume text for fabrications, omissions, and errors.
    Returns list of violation strings. Empty list = clean.
    """
    if canonical is None:
        canonical = load_canonical()

    violations = []
    text_lower = resume_text.lower()

    # CHECK 1: Banned claims
    # Any token from banned_claims appearing in the resume is a fabrication
    for claim in canonical.get("banned_claims", []):
        if claim.lower() in text_lower:
            violations.append(f"BANNED_CLAIM: Found '{claim}' in resume")

    # CHECK 2: Contact info verification
    # The canonical contact info should appear in the resume
    contact = canonical.get("contact", {})
    if contact.get("email") and contact["email"].lower() not in text_lower:
        violations.append(f"MISSING_CONTACT: Email '{contact['email']}' not found")
    if contact.get("phone") and contact["phone"] not in resume_text:
        violations.append(f"MISSING_CONTACT: Phone '{contact['phone']}' not found")
    if contact.get("linkedin") and contact["linkedin"].lower() not in text_lower:
        violations.append(f"MISSING_CONTACT: LinkedIn '{contact['linkedin']}' not found")

    # CHECK 3: Job titles must match canonical exactly
    for role_key, role_info in canonical.get("roles", {}).items():
        title = role_info.get("title", "")
        company = role_info.get("company", "")
        # At minimum, the company name should appear
        if company.lower() not in text_lower:
            violations.append(
                f"MISSING_ROLE: Company '{company}' not found for role {role_key}"
            )
        # Title should appear (case-insensitive partial match is OK for compound titles)
        elif title.lower() not in text_lower:
            violations.append(
                f"WRONG_TITLE: Canonical title '{title}' for {company} not found"
                f" — possible title rewrite"
            )

    # CHECK 4: Patent count
    # Count how many patent numbers from canonical appear in the resume
    granted = canonical.get("patents_granted", [])
    found_patents = 0
    for p in granted:
        num = p.get("number", "")
        # Normalize: strip spaces around commas for matching
        num_normalized = num.replace(" ", "")
        text_no_spaces = resume_text.replace(" ", "")
        if num_normalized.lower() in text_no_spaces.lower():
            found_patents += 1
    if found_patents < len(granted):
        violations.append(
            f"MISSING_PATENTS: Only {found_patents}/{len(granted)} granted patents"
            f" found in resume"
        )

    # CHECK 5: Award count (Emmys)
    awards = canonical.get("awards", [])
    emmy_count_expected = sum(
        1 for a in awards if "emmy" in a.get("title", "").lower()
    )
    # Count Emmy mentions in the resume (look for year + emmy pattern)
    emmy_years_found = set()
    for a in awards:
        if "emmy" in a.get("title", "").lower():
            year_str = str(a["year"])
            # Check if both the year and "emmy" appear near each other or the subtitle appears
            subtitle = a.get("subtitle", "")
            if year_str in resume_text and "emmy" in text_lower:
                emmy_years_found.add(year_str)
    if len(emmy_years_found) < emmy_count_expected:
        violations.append(
            f"MISSING_AWARDS: Only {len(emmy_years_found)}/{emmy_count_expected}"
            f" Emmy awards verifiable"
        )

    # CHECK 6: Affiliations
    for aff in canonical.get("affiliations", []):
        # Check for key phrase
        if "television academy" in aff.lower() and "television academy" not in text_lower:
            violations.append(f"MISSING_AFFILIATION: '{aff}' not found")

    # CHECK 7: Education — no fabricated degree
    edu = canonical.get("education", {})
    if edu.get("degree") is None:
        # Eric has no degree — check for fabricated ones
        degree_patterns = [
            r"\bBS[,\s]", r"\bB\.S\.", r"\bBachelor", r"\bMaster", r"\bMS[,\s]",
            r"\bM\.S\.", r"\bPh\.?D", r"\bMBA\b",
        ]
        for pattern in degree_patterns:
            if re.search(pattern, resume_text, re.IGNORECASE):
                violations.append(
                    f"FABRICATED_DEGREE: Pattern '{pattern}' found — Eric has no degree"
                )
                break

    # CHECK 8: School name should appear if education section exists
    school = edu.get("school", "")
    if school and "education" in text_lower:
        if school.lower() not in text_lower and "maryland" not in text_lower:
            violations.append(
                f"WRONG_SCHOOL: '{school}' not found in education section"
            )

    # CHECK 9: Certifications — should be empty (all expired)
    certs = canonical.get("certifications", [])
    if not certs:
        # No active certs — check for fabricated ones
        cert_patterns = [
            r"AWS Certified", r"Google Cloud Certified", r"Azure Certified",
            r"PMP\b", r"CISSP\b", r"CKA\b", r"CKAD\b",
        ]
        for pattern in cert_patterns:
            match = re.search(pattern, resume_text, re.IGNORECASE)
            if match:
                violations.append(
                    f"FABRICATED_CERT: '{match.group()}' found — no active certifications"
                )

    # CHECK 10: Placeholder detection
    placeholders = ["[University]", "[Year]", "[City]", "[State]", "TBD", "TODO", "[placeholder"]
    for ph in placeholders:
        if ph.lower() in text_lower:
            violations.append(f"PLACEHOLDER: Found '{ph}' in resume")

    return violations


def scan_file(path: Path, canonical: dict) -> tuple[str, list[str]]:
    """Scan a single resume file. Returns (filename, violations)."""
    text = path.read_text(encoding="utf-8")
    violations = scan_resume(text, canonical)
    return path.name, violations


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scan resumes for fabrications")
    parser.add_argument("files", nargs="*", help="Resume .md files to scan")
    parser.add_argument("--all", action="store_true", help="Scan all .md files in output/")
    parser.add_argument(
        "--strict", action="store_true", help="Exit with code 1 if ANY violations found"
    )
    args = parser.parse_args()

    canonical = load_canonical()

    if args.all:
        output_dir = Path(__file__).parent / "output"
        files = sorted(output_dir.glob("*.md"))
    elif args.files:
        files = [Path(f) for f in args.files]
    else:
        parser.error("Provide file paths or --all")
        return

    total_violations = 0

    for fpath in files:
        if not fpath.exists():
            print(f"  x {fpath} — FILE NOT FOUND")
            continue
        name, violations = scan_file(fpath, canonical)
        if violations:
            print(f"\n  x {name} — {len(violations)} violations:")
            for v in violations:
                print(f"    - {v}")
            total_violations += len(violations)
        else:
            print(f"  OK {name} — CLEAN")

    print(f"\n{'='*50}")
    print(f"  Total: {len(files)} files, {total_violations} violations")
    print(f"{'='*50}")

    if args.strict and total_violations > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
