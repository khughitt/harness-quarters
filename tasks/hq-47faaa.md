---
id: hq-47faaa
title: "Claude's effortLevel is tracked while Codex's effort is filtered: decide whether /effort is session state"
status: idea
priority: 2
created: 2026-10-10T14:07:56Z
updated: 2026-10-10T19:22:05Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Found while designing hq-14d183 (docs/specs/2026-10-10-live-model-preservation-design.md §1.1, §2). The clean filter drops Codex's model_reasoning_effort but leaves Claude's effortLevel in claude/settings.json tracked (committed as "high"), so /effort shows as a real diff and a checkout restores the committed value instead of dropping it. Decide whether effortLevel should be filtered and, if so, owned by live-picks.

Where it stands (2026-10-10): the clean filter's JSON_KEYS are ("model", "modelSettings") in .githooks/harness-state-clean:20; live-picks owns those plus Codex's model and model_reasoning_effort (.githooks/live-picks). effortLevel has been "high" at claude/settings.json:268 since the first commit (c28e2da, 2026-09-29) and has never changed in history, so no /effort pick has been committed or lost yet.

If filtered: add effortLevel to JSON_KEYS and to live-picks' owned Claude fields, extend test_harness_state_clean.py and test_live_picks.py, update the spec's §1.1 row and the README. The committed file would then carry no effort, so a fresh home runs Claude Code's default effort until /effort is used once. The change touches the live hooks, so it gets the same gated rollout as hq-a77096.

## Open questions

- Is Claude's /effort a session pick (filter it and let live-picks preserve it, as Codex's effort already is) or a committed default (keep "high" tracked, so /effort shows as a diff to commit or revert)? Recommendation: filter it, for parity with Codex and because a picker-written value is live state under AGENTS.md's rules; the alternative keeps one reproducible default across hosts.

## Notes

- 2026-10-10T18:52:16Z (main): follow-up confirmed after hq-a77096 rollout: Claude model/modelSettings and Codex model/effort are preserved; Claude effortLevel remains deliberately tracked and out of scope. Keep this as the separate decision about whether /effort should be session state; no implementation implied.
- 2026-10-10T19:22:04Z (main): scope: question; body records the filter and live-picks touch points (.githooks/harness-state-clean:20, .githooks/live-picks), that effortLevel has stayed "high" since c28e2da, and the cost of filtering (fresh homes start at the default effort); one open question: is /effort a session pick or a committed default, recommendation filter it
