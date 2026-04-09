---
name: Model delegation for builds
description: Eric wants Opus to plan and orchestrate, not build — delegate build work to Sonnet/Haiku agents by cost tier
type: feedback
---

Break build work into sequential prompts targeted at the cheapest model that can handle the task accurately. Opus plans and orchestrates; Sonnet builds complex new scripts; Haiku handles mechanical edits, wiring, and verification.

**Why:** Token cost optimization. Opus is expensive — don't waste it on writing code that Sonnet can handle, or on mechanical edits that Haiku can do.

**How to apply:** When a plan is approved, create a prompt chain: Haiku for simple edits (~6 lines), Sonnet for complex new code (350+ lines), Haiku for integration wiring (~8 lines), Haiku for verification/testing. Launch them sequentially via Agent tool with `model` parameter. Opus stays in the orchestrator role.
