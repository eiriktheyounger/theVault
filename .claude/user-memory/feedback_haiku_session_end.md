---
name: Haiku session end behavior
description: Avoid asking clarification questions at session end; either wait for explicit direction or execute autonomously on known work
type: feedback
---

Don't end sessions asking "what should I work on?" or "what's the next focus?"

**Why:** Creates session friction and relies on user follow-up when the session could have waited for explicit direction or executed autonomously on P0/P1 work. Hook feedback indicates this pattern triggers early session termination before meaningful work is completed.

**How to apply:** When a session starts:
1. Read briefing/context files as instructed
2. If no explicit task follows, either:
   - Wait for next user message with clear direction
   - Execute autonomously on top-priority open work (P0/P1) without asking permission
3. Don't ask "what next?" — let the user tell you, or act on known priorities
4. Report at natural milestones, not at session end
