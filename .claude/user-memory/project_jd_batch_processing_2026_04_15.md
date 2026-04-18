---
name: JD Batch Processing Issue — 2026-04-15 (SUPERSEDED)
description: RESOLVED 2026-04-15 by Phase 1-3 hardening. See project_jd_analyzer_fixes_2026_04_15.md. Kept for historical record only.
type: project
originSessionId: 4bc5104f-958f-4f24-aee1-414fc3ed9bec
---
## Status: RESOLVED — See project_jd_analyzer_fixes_2026_04_15.md

Root cause (token truncation in scoring phase) fixed by Phase 1-3 hardening (2026-04-15). All 3 JDs validated successfully. Phase 4 anti-fabrication overhaul followed 2026-04-16. This file is kept for historical record only.

---
## Original Debugging Record (for history)

**Date**: 2026-04-15  
**Work**: Batch processing 3 JDs through ResumeEngine

## Completed
1. ✅ Converted 3 RTF job descriptions → clean plain text
   - Advisor360_TechLead.txt (44 lines, 1,104 words)
   - AirBNB_BackEnd_MediaIngest.txt (35 lines, 821 words)
   - Akamai_PrinTechSolArch.txt (48 lines, 962 words)
   - 40-43% byte reduction (removed RTF control codes)
   - Files verified clean and readable

2. ✅ Files copied to `ResumeEngine/jds/`

3. ✅ Batch run initiated: `python3 ResumeEngine/jd_analyzer.py --batch`

## Current Issue

**Error during scoring phase:**
```
Processing: Advisor360_TechLead.txt → Advisor360_TechLead.md
2026-04-15 08:24:18,158  ERROR  Scoring JSON error for projects: 
Unterminated string starting at: line 85 column 15 (char 3702)
```

**What's happening:**
- JD parses OK (Haiku extraction works)
- Scoring phase fails when scoring `projects` category
- Haiku returns malformed JSON (unterminated string)
- Current code has fallback: scores projects at neutral 50/100 (lines 286-290)
- Resume still generates but projects ranking is broken

## Root Cause Unknown

Possible causes:
1. Special characters in project context files breaking JSON serialization
2. JD content with quotes/newlines confusing Haiku's JSON output
3. Token limits hit during scoring (response truncation mid-JSON)
4. Scoring prompt construction issue (item_summaries malformed)

## Next Steps (Opus)

1. **Debug**: Add verbose logging to capture raw Haiku response
2. **Analyze**: Trace why JSON is malformed (check project context files, JD content)
3. **Design**: Improve error handling or input validation
4. **Fix**: Implement solution (Sonnet can build)

## Files & Paths

- **JD Analyzer**: `~/theVault/ResumeEngine/jd_analyzer.py`
- **Scoring function**: Lines 238-299 (score_category)
- **JDs to process**: `~/theVault/ResumeEngine/jds/` (3 files)
- **Context**: `~/theVault/ResumeEngine/context/` (projects, roles, skills, awards, patents)
- **Output**: `~/theVault/ResumeEngine/output/` (resumes generated here)

## Notes

- Run was killed mid-process (Advisor360 file partially generated)
- User has ANTHROPIC_API_KEY set (API calls working, JSON parsing is the issue)
- This is not a Haiku-level task (complex debugging → Opus)
