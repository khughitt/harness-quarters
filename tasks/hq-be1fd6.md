---
id: hq-be1fd6
title: Turn pause coverage for agy
status: idea
priority: 2
reviewed: true
reviewed_at: 2026-11-05T02:15:34Z
created: 2026-11-02T00:05:55Z
updated: 2026-11-05T02:15:34Z
depends: [hq-7bed89]
parent: hq-8f5670
tags: [hooks]
source: "claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79"
agent: claude-code/claude-opus-5-5
origin: agent
---

Follow-up of hq-9aa713 (turn pause, Task 10). The first release covers Claude Code and Codex; agy hooks PreToolUse only for run_command, plus SessionStart and Stop, so a partial pause would mislead (spec Coverage table). Scope: what agy would need to refuse every tool past a limit, or how to state its coverage honestly in lore's rule.

## References

- brief (input, required, kind=brief): docs/notes/2026-11-04-turn-pause-coverage-brief.md — context and questions for this work

## Notes

- 2026-11-02T00:05:55Z (add): created
  provenance: {"harness_session":"claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-05T02:15:34Z (main): scope: briefed; parented under hq-8f5670, added [ref:brief] and dep on hq-7bed89 for agy 1.5.0 PreInvocation/PreToolUse/PostToolUse/subagent payload probe (commit 6273c206 already widened agy/hooks.json PreToolUse matcher to *); origin: stage 1 inferred (claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79 L2502/L2508 toolu_01EkbGT7CaoUsxQbPkLuFpSu: single sourced tasks add candidate per title, id-only stdout with 2>&1 stderr captured and no reuse warning; controller follow-up of hq-9aa713 after human "Accept." at L1210; stage 2 n/a, no origin_session; stored origin=agent confirmed); brief: docs/notes/2026-11-04-turn-pause-coverage-brief.md
