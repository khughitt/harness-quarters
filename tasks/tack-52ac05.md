---
id: tack-52ac05
title: "Codex sessions cannot name their own model id: TASKS_AGENT is a static 'codex', so review notes and task stamps lose the model half"
status: idea
priority: 2
created: 2026-09-30T14:49:23Z
updated: 2026-10-02T15:33:38Z
depends: []
parent: tack-fce47e
tags: [obs]
source: tack-1327b8
agent: claude-code/claude-opus-5-5
---

A Codex session asked to attribute its review (tack-1327b8, 2026-09-30) could name its harness but not a verified model id. codex/config.toml exports TASKS_AGENT = "codex" as a constant, and the config's default model can be overridden per session (-m, profiles), so config is not evidence. The rollout records it: each turn_context line carries model and effort, and the session has CODEX_THREAD_ID to find its own rollout. Investigate: a small resolver (thread id -> rollout -> latest turn_context.model) that TASKS_AGENT/TASKS_MODEL stamping and review notes can use, whether relay's identity already knows the model, and whether Claude Code has the same gap (claude/settings.json exports neither TASKS_AGENT nor TASKS_MODEL). Affects obs's review-round and model attribution.

## Notes

- 2026-10-02T15:33:37Z (main): scope: briefed; parented under tack-fce47e; Claude Code half settled (claude-provenance hook, tack-d5a56c); Codex resolver depends on relay's id conflict (relay-c85a0f); research tack-1bd166; brief: docs/notes/2026-10-02-codex-model-identity-brief.md
