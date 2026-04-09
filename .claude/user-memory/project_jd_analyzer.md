---
name: ResumeEngine JD Analyzer
description: jd_analyzer.py at ResumeEngine/ root — single + batch JD processing, scan-process-move pattern, 48 context files, Haiku+Sonnet pipeline
type: project
---

**Built:** 2026-03-28. Script moved from worktree to `ResumeEngine/jd_analyzer.py` on 2026-04-01.

**What it does:** Takes a job description (file, pasted text, or batch) and generates a tailored resume by:
1. Parsing the JD (Haiku) → role type, required skills, keywords, SA/AI/ad-tech signals
2. Scoring all context files (Haiku, one batch call per category) → ranked 0–100 per item
3. Selecting template: `resume-v1-ic` for IC/PM/AI, `resume-v2-sa` for SA/pre-sales/technical sales
4. Generating the resume (Sonnet) with top-scored context + voice guide + framing rules
5. Banned-words validation → auto-fix pass via Haiku if any found

**CLI:**
```bash
cd ~/theVault && source .venv/bin/activate

# Single JD (file or inline)
python3 ResumeEngine/jd_analyzer.py --jd ResumeEngine/jds/company-role.txt --output ResumeEngine/output/company-role.md --verbose
python3 ResumeEngine/jd_analyzer.py --jd-text "paste JD..." --output ResumeEngine/output/test.md

# Batch mode — process all .txt in jds/, FIFO by mtime
python3 ResumeEngine/jd_analyzer.py --batch --verbose
```

**Batch mode (added 2026-04-01):**
- Drop `.txt` JD files into `ResumeEngine/jds/`
- `--batch` processes all pending `.txt` files, FIFO by modification time
- Success → JD moved to `jds/processed/`, resume written to `output/{stem}.md`
- Failure → JD moved to `jds/failed/`, error logged
- Summary printed at end with pass/fail per file

**Directory structure:**
```
ResumeEngine/
├── jd_analyzer.py          ← main script
├── jds/                    ← drop JDs here
│   ├── processed/          ← successful JDs moved here
│   └── failed/             ← errored JDs moved here
├── output/                 ← generated resumes
├── config/                 ← voice, framing, banned words, templates
└── context/                ← 48 career context files
```

**Models:** Haiku (`claude-haiku-4-5-20251001`) for parsing + scoring; Sonnet (`claude-sonnet-4-6`) for generation

**Context loaded (48 items):**
- `context/roles/` — 10 role files
- `context/projects/` — 18 project files
- `context/skills/` — 5 skill domain files
- `context/awards/` — 4 Emmy award files
- `context/patents/` — 11 patent files

**Config loaded:** `voice-guide.md`, `framing-rules.md`, `banned-words.md`, both templates

**Templates:** Both `resume-v1-ic.md` and `resume-v2-sa.md` are empty — the script embeds structural fallback (`STRUCTURE_IC` / `STRUCTURE_SA` constants) when template files are blank.

**Output:** `ResumeEngine/output/resume-<timestamp>.md` by default, `--output` override for single mode, auto-derived `output/{stem}.md` in batch mode.

**NBCUniversal framing:** "Organizational restructuring" only, two sentences max, enforced via system prompt to Sonnet and framing-rules.md content.

**Why:** Directly tied to job applications and income. Batch mode enables processing multiple opportunities efficiently.

**How to apply:** Run from `~/theVault` with venv active. ANTHROPIC_API_KEY must be set (available in .env, .bash_profile, crontab). Workflow: copy JD from webpage → `pbpaste > ResumeEngine/jds/company-role.txt` → `--batch`.
