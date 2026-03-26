# Resume Engine — Memory Topic File

## Location
~/theVault/ResumeEngine/ (parallel to Vault, not inside it)

## Structure
```
ResumeEngine/
├── config/ (banned-words, voice-guide, framing-rules, templates/)
├── context/
│   ├── roles/ (one per employer)
│   ├── projects/ (one per major project)
│   ├── awards/ (emmy-paris-olympics-interactive-experience.md DONE)
│   ├── patents/granted/ and patents/pending/
│   ├── skills/ (by domain)
│   └── stories/ (from interview transcripts — NOT YET BUILT)
├── jobs/ (incoming/, draft/, active/, archive/)
├── output/
├── scripts/
└── staging/
```

## Status
- Directory structure: CREATED
- Emmy Paris Olympics context file: COMPLETE (verified, individual credit documented)
- Career source docs: exist at Vault/Personal/Career/ (10 patent PDFs, resumes, prep docs)
- Haiku extraction: IN PROGRESS (Eric reviewing generated context files)
- JD analyzer: NOT YET BUILT
- Story bank from transcripts: NOT YET BUILT (depends on clean_md_processor.py)

## Key Design Decisions
- Job config firewall: human reviews before generation (from Proposal 16)
- Semi-automated JD processing: Claude drafts config, Eric reviews in 5 min vs 30 min
- Match analysis output: receipt showing what source material was used
- Stories separate from roles: same story maps to multiple JD themes
- Obsidian backlinks connect ResumeEngine files to Vault/Context_* files

## Eric's Emmy Credit (Important for Resume)
- 4 Engineering Emmys total
- Paris Olympics: Outstanding Interactive Experience (46th Sports Emmys, May 2025)
- Eric individually named as sole Software Developer on the submission
- Built Peacock Live Actions from ground up → generated patent US-20250203152-A1
- Architected Olympic Daily Recap content workflows (7M+ personalized variants)
- Did NOT build the AI platform itself
