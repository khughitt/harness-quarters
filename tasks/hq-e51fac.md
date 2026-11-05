---
id: hq-e51fac
title: Make automatic compaction advisory in turn-pause hook and CLI
status: doing
priority: 1
size: s
complexity: mid
process: direct
owner: fix/hq-e51fac
created: 2026-11-05T00:36:12Z
updated: 2026-11-05T00:53:27Z
started: 2026-11-05T00:36:32Z
depends: []
parent: hq-2dd09b
tags: []
source: hq-1942a1
origin: user
---

The user accepted assessment hq-1942a1 (tasks/files/hq-1942a1/compaction-assessment-report.md) and requested: "file and prepare the advisory-compaction changes from compaction-assessment-report.md first, but make sure we don't let issue persist blocked for too long."

Done: compactions are no longer an independent hard pause/refusal trigger in tools/turn_pause, while active (16h), calls (500), and spawns (30) remain hard limits. Keep compactions in Limits and limits.toml (so limits_sha and stored RootState JSON remain compatible and live sessions do not trip limits-changed on activation) and keep TurnState.compactions and due_warnings for hooked advisory warnings. Update counters.crossed to check only ('active', 'calls', 'spawns'), and update tools/hq_cli/pause.py, tools/turn_pause/hook.py, README.md, and focused tests so human-readable status/limits/refusal text labels compactions as advisory (and unhooked rather than "count your own") while preserving JSON structure. Prepare in a dedicated worktree branched from main so this fix is not blocked behind .worktrees/hq-2dd09b (hq-e60ecb's 25-minute idle-host latency comparison). Coordinate with the paired lore guidance task. Live hook activation remains separately approved after preparation and review.

Where: tools/turn_pause/counters.py, tools/turn_pause/hook.py, tools/hq_cli/pause.py, README.md, and focused tests (tools/test_turn_pause_counters.py, tools/test_turn_pause_hook.py, tools/test_turn_pause_replay.py, tools/test_hq_pause.py). Run focused tests and mandatory just check-hygiene.

## References

- assessment (input, required, kind=report): tasks/files/hq-1942a1/compaction-assessment-report.md — accepted assessment recommending advisory-only compaction

## Notes

- 2026-11-05T00:36:12Z (add): created
  provenance: {"origin":"user"}
- 2026-11-05T00:36:32Z (main): started
- 2026-11-05T00:36:54Z (main): arm: flow-trial-1 — unit tack-2dd09b — flow off
- 2026-11-05T00:36:56Z (fix/hq-e51fac): resumed
- 2026-11-05T00:38:38Z (fix/hq-e51fac): arm: flow-trial-1 — unit tack-2dd09b — flow off
- 2026-11-05T00:38:40Z (fix/hq-e51fac): Hydrated .worktrees/hq-e51fac with just setup; focused baseline just test-one tools/test_turn_pause_counters.py tools/test_turn_pause_hook.py tools/test_turn_pause_limits.py tools/test_turn_pause_replay.py tools/test_hq_pause.py passed (161 passed in 15.61s); broad test suite deliberately omitted under validated .tt.toml policy. Paired lore guidance task filed as lore-d27b9c.
- 2026-11-05T00:53:27Z (fix/hq-e51fac): review: impl round 1 — verdict: revise; findings: 1 minor (label compactions as advisory in ROOT_TEXT, LIMITS_CHANGED_HEAD and _notice in tools/turn_pause/hook.py); reviewer: agy/gemini
