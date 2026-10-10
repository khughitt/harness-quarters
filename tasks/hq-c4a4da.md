---
id: hq-c4a4da
title: The case's first live run against obs
status: done
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-10-02T11:40:02Z
updated: 2026-10-10T13:20:02Z
started: 2026-10-10T13:19:12Z
completed: 2026-10-10T13:20:02Z
depends: [hq-4f8712, obs-0491f1]
parent: hq-7d9375
tags: [flow]
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-10-02-flow-trial.md
step: "Task 6: the case's first live run against obs"
---

## Notes

- 2026-10-10T13:19:12Z (main): started
  provenance: {"harness_session":"claude-code:f4800c2e-b868-4a2a-b838-1c282275e0ab","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T13:19:17Z (main): arm: flow-trial-1 — unit tack-7d9375 — not enrolled
- 2026-10-10T13:20:02Z (main): done
  provenance: {"harness_session":"claude-code:f4800c2e-b868-4a2a-b838-1c282275e0ab","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T13:20:02Z (main): First live run recorded in flows evals/cases/flow-trial-1-delivery.md (flows ab91901): judge exit 0 'insufficient: before read date'; --validate 'inputs valid: 13 census units, 0 obs rows for their members' — 0 by design, since --units lists only units whose 30-day follow-up is complete (none before 2026-11-04; hq-e4e58a rechecks then). obs runs as python3 obs.py; no obs command on PATH.
  provenance: {"harness_session":"claude-code:f4800c2e-b868-4a2a-b838-1c282275e0ab","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
