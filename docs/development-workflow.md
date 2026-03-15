# Development Workflow

## Making Changes

1. Always work from ~/theVault on Mac Mini
2. Activate venv: source .venv/bin/activate
3. Verify NAS: bash System/Scripts/check_nas.sh
4. Make changes
5. Test
6. Commit: git add -A && git commit -m "description"
7. Push: git push origin main

## Claude Code Sessions

- Use cc-haiku for quick tasks
- Use cc-sonnet for daily coding
- Use cc-opus for architecture decisions
- One session at a time — no parallel edits

## Daily Note Workflow

- Morning: Open Daily Note widget on iPhone or Obsidian on Mac
- Throughout day: Cmd+Shift+C to capture, or dictate on iPhone
- Evening: Open daily note, fill in Evening section
- 10 PM: Overnight processor runs automatically

## Overnight Processing

Cron job at 10 PM:
```
0 22 * * * cd ~/theVault && source .venv/bin/activate && python3 System/Scripts/overnight_processor.py
```
