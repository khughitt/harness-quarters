---
id: hq-d2c11e
title: Probe two unverified resume paths behind hq sessions
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-10-15T11:34:31Z
updated: 2026-10-15T11:34:31Z
depends: []
parent: hq-65f661
tags: []
agent: claude-code/claude-opus-5-5
---

Why: hq sessions launches by the native resume command in the recorded cwd, and two cases from docs/notes/2026-10-15-session-discovery-contract.md were never verified with a real launch.

1. Codex: 491 interactive personal rollouts from before 2026-07-08 have no `threads` row in state_5.sqlite. Does `codex resume <id>` still open such a rollout? If it does, hq sessions could list them from the rollout files (the README says this is untested).
2. Claude: 4 live transcripts sit under a `projects/<dir>` other than the slug of their last history `project` (the cwd changed during the session). Does `claude --resume <id>` run from the recorded cwd find them, or does it look only in that cwd's project directory?

Approach: synthetic homes (a scratch CODEX_HOME and CLAUDE_CONFIG_DIR holding copied or minimal fixtures), never the live homes. Run the real CLIs with a bounded timeout, non-interactively where possible. Record each answer as a capability fact through tools/harness-facts, with its probe under claude/probes or a codex probe, per README 'Re-probing a fact'.

Done when: both answers are recorded as facts with harness versions; if either is 'no', hq sessions refuses or warns on that case (with a test), and the README's 'Not listed' bullet states the answer.
