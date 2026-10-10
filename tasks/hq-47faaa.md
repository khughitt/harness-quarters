---
id: hq-47faaa
title: "Claude's effortLevel is tracked while Codex's effort is filtered: decide whether /effort is session state"
status: idea
priority: 2
created: 2026-10-10T14:07:56Z
updated: 2026-10-10T18:52:16Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Found while designing hq-14d183 (docs/specs/2026-10-10-live-model-preservation-design.md §1.1, §2). The clean filter drops Codex's model_reasoning_effort but leaves Claude's effortLevel in claude/settings.json tracked (committed as "high"), so /effort shows as a real diff and a checkout restores the committed value instead of dropping it. Decide whether effortLevel should be filtered and, if so, owned by live-picks.

## Notes

- 2026-10-10T18:52:16Z (main): follow-up confirmed after hq-a77096 rollout: Claude model/modelSettings and Codex model/effort are preserved; Claude effortLevel remains deliberately tracked and out of scope. Keep this as the separate decision about whether /effort should be session state; no implementation implied.
