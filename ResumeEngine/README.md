# Resume Engine

**ResumeEngine** is an AI-powered resume generation system that analyzes job descriptions and tailors resumes using a curated library of career context files, strategic voice guidance, and intelligent scoring.

**Current Status:** Ready for production. JD Analyzer built 2026-03-28. Ideal for competitive job applications like DraftKings.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Context Structure](#context-structure)
4. [Configuration Files](#configuration-files)
5. [Running the JD Analyzer](#running-the-jd-analyzer)
6. [Output & Templates](#output--templates)
7. [Workflow Example](#workflow-example)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Python 3.10+
- `ANTHROPIC_API_KEY` environment variable set
- Claude API access (Haiku + Sonnet models)

### Basic Usage

```bash
# From anywhere, with venv activated:
cd ~/theVault
export ANTHROPIC_API_KEY="sk-ant-..."

# Run with a job description file
python3 ResumeEngine/jd_analyzer.py --jd /path/to/jobdesc.txt --output ResumeEngine/output/my-resume.md

# Or paste the JD directly
python3 ResumeEngine/jd_analyzer.py --jd-text "Job Title: Senior Engineer..." --output ResumeEngine/output/drafted.md

# Verbose mode (see scoring details)
python3 ResumeEngine/jd_analyzer.py --jd jobdesc.txt --verbose
```

**Output:** Generated resume written to `ResumeEngine/output/resume-<timestamp>.md` by default.

---

## Architecture

The JD Analyzer uses a **three-stage pipeline**:

### Stage 1: JD Parsing (Haiku)
- **Input:** Job description (file or text)
- **Process:** Extract role signals, required skills, keywords, domain (ad-tech, AI, SA, etc.)
- **Output:** Structured JSON (role type, key skills, signals)

### Stage 2: Context Scoring (Haiku)
- **Input:** Parsed JD + all context files (roles, projects, skills, awards, patents)
- **Process:** Score each context item (0–100) against JD signals and keywords in batch calls per category
- **Output:** Ranked list of relevant context for this job

### Stage 3: Resume Generation (Sonnet)
- **Input:** Scored context + voice guide + framing rules + selected template
- **Process:** Generate tailored resume; enforce banned-words policy
- **Output:** Polished markdown resume with YAML frontmatter

**Template Selection:**
- **IC roles** (Senior Engineer, Staff Engineer, PM): `resume-v1-ic.md`
- **SA roles** (Solutions Architect, Sales Engineer): `resume-v2-sa.md`

**Banned Words Check:**
- If any banned words detected, Haiku performs auto-fix pass
- Banned word list: `config/banned-words.md`

---

## Context Structure

The system loads **48 context items** across five categories:

### 1. **Roles** (10 files, `context/roles/`)

Career positions spanning 2001–2025. Index: `context/role-index.md`

Examples:
- `aol-2001-2006.md` — Broadcast Operations, live streaming pioneer
- `twc-2006-2012.md` — Sr. Solutions Architect, VOD automation (350%+ ad revenue)
- `twc-2012-2017.md` — Principal Engineer, OTT platform (TWCTV, Emmy 2014)
- `ooyala-2017-2018.md` — Sr. Solutions Architect, SaaS OTT
- `leidos-2019-2020.md` — Sr. Software Engineer, defense contracting
- `nbcu-2020-2024.md` — Principal Engineer, SVG (organizational restructuring framing only)
- And 4 others (government, consulting, AI)

### 2. **Projects** (18 files, `context/projects/`)

Detailed case studies of major work. Index: `context/project-index.md`

Examples:
- `twctv-application-2012-2017.md` — OTT platform serving millions
- `dynamic-ad-insertion.md` — DRM + DAI architecture
- `vms-transition.md` — VOD system migration
- `live-streaming-infrastructure.md` — 100+ concurrent channels
- And 14 others (infrastructure, payments, ML, automation)

### 3. **Skills** (5 domain files, `context/skills/`)

Technical and soft skill clusters. Index: `context/skills-index.md`

Domains:
- `backend-engineering.md` — Python, C++, distributed systems
- `frontend-engineering.md` — React, TypeScript, UX
- `solutions-architecture.md` — Enterprise sales, system design
- `data-engineering.md` — ML pipelines, Spark, embeddings
- `leadership.md` — Team management, mentoring, strategy

### 4. **Awards** (4 files, `context/awards/`)

Recognition and achievements. Index: `context/award-index.md`

Examples:
- `emmy-2005-live-8.md` — Live 8 Concert Streaming
- `emmy-2014-twctv.md` — TWCTV Application
- 2 others (innovation awards, recognition)

### 5. **Patents** (11 files, `context/patents/`)

Issued US patents across ad insertion, streaming, DRM. Index: `context/patent-index.md`

Examples:
- `patent-8028092.md` — Inserting Advertising Content (2011)
- `patent-8762575.md` — Dynamically Inserting Targeted Ads (2014)
- 9 others (video streaming, encryption, payment systems)

### Stories (1 file, `context/stories/`)

Personal narrative pieces. Index: `context/story-index.md`. Currently minimal; can be expanded with life/career stories if needed.

---

## Configuration Files

### `config/voice-guide.md`

**Purpose:** Strategic voice and tone for resume writing.

**Content:** Guidelines on:
- Tone (direct, results-driven, technical depth)
- Audience focus (hiring managers, CTOs, VPs)
- Emphasis areas (impact, technical leadership, product vision)

**When used:** Sonnet reads this during resume generation to maintain consistent voice.

**Example:** *"Emphasize measurable business impact. Be specific about scale (customers, revenue, infrastructure). Technical depth first, process details second."*

### `config/framing-rules.md`

**Purpose:** Special handling rules for sensitive career transitions.

**Content:**
- **NBCUniversal (2020–2024):** "Organizational restructuring" only, two sentences max, then redirect to current work
- Any other transition-specific guidance

**When used:** Sonnet enforces these rules during generation.

**Critical Rule:** NBCUniversal departure is never discussed as personal circumstance — always organizational restructuring.

### `config/banned-words.md`

**Purpose:** Authoritative list of clichéd/banned resume words.

**Content (hardcoded in script, also in file):**
- spearheaded, leveraged, revolutionized, best-in-class
- thought leader, passionate about, results-driven
- dynamic professional, synergy, impactful

**When used:** Haiku scans generated resume for these words. If found, auto-fix pass happens.

### `config/templates/`

**Resume Templates:**

- `resume-v1-ic.md` — Individual Contributor / Product roles (currently empty; embedded structure `STRUCTURE_IC` is fallback)
- `resume-v2-sa.md` — Solutions Architect / pre-sales roles (currently empty; embedded structure `STRUCTURE_SA` is fallback)

**Note:** Templates are empty but can be populated to override embedded fallback structures. If you want custom formatting, edit these files and they will be used instead of hardcoded structures.

---

## Running the JD Analyzer

### Command Line

```bash
python3 ResumeEngine/jd_analyzer.py [OPTIONS]
```

### Options

| Flag | Required | Description | Example |
|------|----------|-------------|---------|
| `--jd` | One of jd/jd-text | Path to job description file | `--jd ~/downloads/draftkings-jd.txt` |
| `--jd-text` | One of jd/jd-text | Inline JD text | `--jd-text "Job Title: Senior Engineer..."` |
| `--output` | No | Output resume path (default: `output/resume-<timestamp>.md`) | `--output output/draftkings-v1.md` |
| `--verbose` | No | Print scoring details and logs | `--verbose` |

### Examples

#### Example 1: File-based JD

```bash
python3 ResumeEngine/jd_analyzer.py \
  --jd ~/downloads/DraftKings-SDE-job.txt \
  --output ResumeEngine/output/draftkings-resume.md \
  --verbose
```

**Process:**
1. Reads job description from file
2. Parses role signals (e.g., "Senior Software Engineer", "backend systems")
3. Scores all 48 context items against the JD
4. Selects IC template (not SA)
5. Generates resume with top-scored projects/roles
6. Checks for banned words
7. Writes to `ResumeEngine/output/draftkings-resume.md`

#### Example 2: Inline JD (quick test)

```bash
python3 ResumeEngine/jd_analyzer.py \
  --jd-text "Solutions Architect — enterprise SaaS, Kubernetes, ML pipeline design" \
  --output output/sarch-test.md
```

**Result:** Selects SA template; scores context for enterprise, SaaS, and systems expertise.

#### Example 3: Dry run (verbose scoring)

```bash
python3 ResumeEngine/jd_analyzer.py \
  --jd jobdesc.txt \
  --verbose
```

**Output:** Logs showing:
- Parsed JD signals and skills
- Score for each context item (0–100)
- Template selection logic
- Generation steps
- Banned word scan

---

## Output & Templates

### Resume Structure

Generated resumes include:

**YAML Frontmatter:**
```yaml
---
role: Senior Software Engineer
company: DraftKings
generated: 2026-03-31T14:22:00Z
jd_signals: [backend, systems, scale, payment]
---
```

**Content:**
1. **Executive Summary** — 2–3 sentences highlighting fit
2. **Experience** — Selected roles and projects, contextualized for the JD
3. **Skills** — Matched against job requirements
4. **Awards & Patents** — Relevant recognitions
5. **Impact Metrics** — Scale, revenue, customers (from projects)

### Template Customization

Templates are in `config/templates/`:

- If `resume-v1-ic.md` or `resume-v2-sa.md` are **empty**, embedded `STRUCTURE_IC` or `STRUCTURE_SA` constants are used.
- If you **populate** these files with custom markdown, they override the embedded structures.

**To customize:**

1. Edit `config/templates/resume-v1-ic.md` with your preferred IC format
2. Edit `config/templates/resume-v2-sa.md` with your preferred SA format
3. Re-run jd_analyzer.py — it will use your templates

**Template Variables (if needed):**
- `{{ROLE}}` — Position title from JD
- `{{COMPANY}}` — Company name
- `{{EXPERIENCE}}` — Selected experience blocks
- `{{SKILLS}}` — Scored skills

---

## Workflow Example

### DraftKings Application (March 2026)

**Step 1: Prepare JD**

Save job description to `~/downloads/DraftKings-SDE.txt`:
```
Senior Software Engineer — Payments Platform
About DraftKings: ...
Responsibilities:
- Design and build payment processing systems
- Optimize backend for 100M+ daily transactions
- ...
Required Skills: Python, C++, payment systems, scale, SQL
```

**Step 2: Generate Resume**

```bash
cd ~/theVault
export ANTHROPIC_API_KEY="sk-ant-..."
python3 ResumeEngine/jd_analyzer.py \
  --jd ~/downloads/DraftKings-SDE.txt \
  --output ResumeEngine/output/draftkings-final.md \
  --verbose
```

**Step 3: Review & Edit**

- Open `ResumeEngine/output/draftkings-final.md`
- Review selected experience blocks — do they fit?
- Check for any missed opportunities or weak positioning
- Manually refine if needed

**Step 4: Export**

Convert markdown to PDF/Word as needed for application.

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set"

**Problem:** Environment variable missing or empty.

**Solution:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
python3 ResumeEngine/jd_analyzer.py --jd jobdesc.txt
```

### "No context files found"

**Problem:** Context directories are missing.

**Solution:** Verify directory structure:
```bash
ls -la ~/theVault/ResumeEngine/context/roles/
ls -la ~/theVault/ResumeEngine/context/projects/
```

If missing, check that NAS mount is active and Vault is synced.

### "Banned words detected"

**Problem:** Generated resume contains words from `config/banned-words.md`.

**Solution:** Haiku automatically fixes these. If you see this message, it means the auto-fix was applied. Review the output to ensure edits make sense.

### Script fails with "ModuleNotFoundError: anthropic"

**Problem:** Anthropic SDK not installed.

**Solution:**
```bash
source .venv/bin/activate
pip install anthropic
```

### Generated resume is generic/weak

**Problem:** Context scoring may have missed relevant items.

**Solution:**
1. Run with `--verbose` to see scores for each context item
2. Check if relevant projects/roles scored low (< 50)
3. If missing context, add new files to `context/projects/` or `context/roles/`
4. Re-run jd_analyzer.py

### Output written to wrong directory

**Problem:** `--output` path specified incorrectly.

**Solution:** Ensure path is relative to current working directory or use absolute path:
```bash
# Relative (from ~/theVault)
python3 ResumeEngine/jd_analyzer.py --jd jobdesc.txt --output ResumeEngine/output/resume.md

# Absolute
python3 ResumeEngine/jd_analyzer.py --jd jobdesc.txt --output /Users/ericmanchester/theVault/ResumeEngine/output/resume.md
```

---

## Files Reference

### Directory Structure

```
ResumeEngine/
├── README.md                    (this file)
├── config/
│   ├── banned-words.md          (clichéd word list)
│   ├── framing-rules.md         (special handling rules)
│   ├── voice-guide.md           (tone/voice guidelines)
│   └── templates/
│       ├── resume-v1-ic.md      (IC role template — currently empty)
│       └── resume-v2-sa.md      (SA role template — currently empty)
├── context/
│   ├── award-index.md           (awards overview)
│   ├── patent-index.md          (patents overview)
│   ├── project-index.md         (projects overview)
│   ├── role-index.md            (roles overview)
│   ├── skills-index.md          (skills overview)
│   ├── story-index.md           (stories overview)
│   ├── awards/                  (4 award files)
│   ├── patents/                 (11 patent files)
│   ├── projects/                (18 project files)
│   ├── roles/                   (10 role files)
│   ├── skills/                  (5 skill domain files)
│   └── stories/                 (personal narratives)
├── output/                      (generated resumes — auto-created)
└── .claude/                     (worktree metadata)
    └── worktrees/condescending-mccarthy/
        └── ResumeEngine/jd_analyzer.py  (main script)
```

### Key Scripts

- **`jd_analyzer.py`** — Main script (worktree: `ResumeEngine/.claude/worktrees/condescending-mccarthy/`)
  - Entry point for resume generation
  - Models: Haiku (parsing/scoring), Sonnet (generation)
  - Loads all context and config files
  - Enforces banned words and framing rules

---

## Maintenance & Future

### Adding New Context

To add experience, projects, or skills:

1. Create file in appropriate `context/` subdirectory
2. Update the corresponding index file (e.g., `context/role-index.md`)
3. Re-run jd_analyzer.py — new context automatically scored

### Updating Guides

- **Voice:** Edit `config/voice-guide.md` to change tone
- **Framing:** Edit `config/framing-rules.md` to add rules
- **Banned words:** Edit `config/banned-words.md` (also update hardcoded list in script)

### Template Customization

Populate `config/templates/resume-v1-ic.md` and `resume-v2-sa.md` to customize resume formatting.

---

## Support

For issues or questions:
- Check the **Troubleshooting** section above
- Review `project_jd_analyzer.md` in memory (`~/.claude/projects/.../memory/`)
- Examine script logs with `--verbose` flag
- Verify context files are readable and NAS mount is active
