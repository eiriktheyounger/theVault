---
name: ResumeEngine Phase 4 — Anti-Fabrication Overhaul (2026-04-16)
description: Two-stage generator, canonical manifest, hallucination scanner, docx output, sanitizer. End-to-end validated.
type: project
originSessionId: continued-from-d779d3e3
---

# ResumeEngine Phase 4 — Anti-Fabrication Overhaul (2026-04-16)

## Problem
Phase 1-3 made the pipeline resilient (retries, backoff, logging). But the LLM still:
- Fabricated AWS certs Eric never had
- Changed job titles ("Sr. Live Events Producer" → "Senior Broadcast Engineer")
- Omitted 9 of 11 patents, 1-3 of 4 Emmys
- Injected JD product names as Eric's skills (EdgeWorkers, LKE, mPulse, Kubernetes)
- Listed a BS degree Eric never earned
- Used placeholder contact info

69 violations across 3 generated resumes.

## Solution: Canonical-Data Enforcement

### New files created
| File | Purpose |
|------|---------|
| `ResumeEngine/context/_canonical.yaml` | Ground-truth manifest: 8 roles (correct titles), 7 granted + 4 pending patents, 4 Emmys, affiliations, education (UMD 1990-1994, no degree), 21 banned claims |
| `ResumeEngine/scan_fabrications.py` | Post-generation validator: 10 check categories (banned claims, contact, titles, patents, awards, affiliations, degree, school, certs, placeholders) |
| `ResumeEngine/render_docx.py` | .docx renderer using python-docx: reads canonical + tailored data, generates Word doc alongside .md |

### Modified files
| File | Changes |
|------|---------|
| `ResumeEngine/jd_analyzer.py` | Two-stage generator (Stage A: Sonnet → JSON bullets; Stage B: Python assembly from canonical), `sanitize_tailored_content()`, `load_canonical()`, `--legacy` flag, scan + docx wiring |
| `ResumeEngine/context/roles/time-warner-cable-2012-2017.md` | "independent architect" → "lead architect and individual contributor" (2 occurrences) |

### Architecture: Two-Stage Generation
**Stage A** — `build_bullet_prompt()` + `tailor_content()`:
- Sonnet receives role stubs (keys only, no titles/dates), context, JD
- Returns JSON: `{professional_summary, core_skills, roles: {key: {bullets: [...]}}}` 
- LLM NEVER writes titles, dates, patents, awards, education, contact

**Stage B** — `assemble_resume_md()`:
- Pure Python merges canonical.yaml data + Stage A bullets
- Contact, titles, dates, all 11 patents, all 4 Emmys, affiliations, education are hardcoded from YAML

**Sanitizer** — `sanitize_tailored_content()`:
- Runs between Stage A and Stage B
- Strips any banned claims (Kubernetes, EdgeWorkers, "independent architect", etc.) from bullets/skills/summary
- Cleans up orphaned punctuation from removals

### Validation results
- **End-to-end test (Akamai JD)**: Pipeline ran successfully. Output had correct contact info, all 8 role titles, all 11 patents, all 4 Emmys, Television Academy membership, University of Maryland (no degree), no fabricated certs
- **Scanner caught 1 issue**: "Kubernetes" leaked into core_skills from JD text — sanitizer now strips it pre-assembly
- **Scanner on old output**: 69 violations across 3 files (every known issue caught)
- **API credits exhausted** during final sanitizer validation test — batch re-run pending credit reload

### CLI changes
- `--legacy` flag uses old single-stage path (deprecated `build_generation_prompt` + `generate_resume`)
- Default path: two-stage with sanitizer + scan + .docx output
- Both .md and .docx written on each run

### Corrected .docx files (manual, pre-pipeline)
Three corrected resumes were manually generated via `_render_docx.py` for tonight's submissions:
- `ResumeEngine/output/corrected/Advisor360_TechLead.docx`
- `ResumeEngine/output/corrected/AirBNB_BackEnd_MediaIngest.docx`
- `ResumeEngine/output/corrected/Akamai_PrinTechSolArch.docx`

### Pending
- **Re-run full batch** through new pipeline once API credits reload
- **Priority #16**: Migrate `score_category` to Gemma 4 E4B (highest-volume Haiku call)
- **Consider**: Tightening Emmy award count check in scanner (currently lenient — checks year+emmy co-occurrence)
