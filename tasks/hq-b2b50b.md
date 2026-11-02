---
id: hq-b2b50b
title: turn-pause's 4 h active-time limit stops valid long sessions; set the cutoff from historic session data
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: fix/hq-b2b50b-active-limit
created: 2026-11-02T19:14:07Z
updated: 2026-11-02T20:45:52Z
started: 2026-11-02T20:22:25Z
depends: []
tags: [feedback, friction, "from:mm"]
agent: claude-code
origin: user
---

The user asked for this (their request): the 4 h active-time limit is too aggressive. It paused a valid subagent-driven plan execution partway through a task, while the session's other counters were far below their limits (about 59 of 500 calls, 7 of 30 spawns, 0 of 2 compactions). The user suggests something closer to 12 or 16 h. They want the implementer to choose the cutoff from historic session data, so that it catches the true outlier sessions without ending valid long-running ones. My reading: a session that only dispatches subagents and waits on them accrues active time while doing little itself, so wall-clock active time may be a weak signal compared with the call, spawn and compaction counters.

Scope: choose and prepare a measured default active-time cutoff with the existing replay, preserving all counting rules and other defaults. Done when default, CLI output, long-turn pause boundary, budget scaling, and current user documentation agree, with full verification and review. Live activation requires approval. Evidence and recommendation: [ref:calibration]. Implementation starts in .worktrees/hq-b2b50b. The inference about weak wall-clock signals above is the filing agent's interpretation; the measured counter includes in-flight tool time and short gaps, not all elapsed wall time.

## References

- calibration (output, kind=report): docs/notes/2026-11-02-active-cutoff-report.md — historical comparison, decision and activation consequences

## Notes

- 2026-11-02T19:14:07Z (feedback): created
  provenance: {"harness_session":"claude-code:c67f4b5f-818d-4533-83b0-172009b992c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T20:22:23Z (main): scope: scoped; origin: filing matched, Claude session c67f4b5f-818d-4533-83b0-172009b992c2 lines 519, 533-534 (duplicate records 535-536 lack timestamps and repeat the same tool id); user explicitly requested a historic-data cutoff, suggesting 12 or 16 h. Direct: existing replay and limits file settle approach; compare historical turn tails at 4/12/16 h, record coverage and outlier evidence, update only active default plus dependent tests and current docs. Keep calls/spawns/compactions and counting semantics unchanged. Verification: hydrated full baseline and just test before commit, default/CLI and budget scaling checks. Activation changes a live hook surface and requires user approval before merge.
  provenance: {"harness_session":"codex:01a19deb-d3a4-7b80-a260-fdc7e14f54ea","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-02T20:22:25Z (main): started
  provenance: {"harness_session":"codex:01a19deb-d3a4-7b80-a260-fdc7e14f54ea","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-02T20:22:49Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-11-02T20:22:52Z (main): arm: flow-trial-1 — unit tack-b2b50b — flow off
- 2026-11-02T20:23:13Z (fix/hq-b2b50b-active-limit): resumed
  provenance: {"harness_session":"codex:01a19deb-d3a4-7b80-a260-fdc7e14f54ea","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-02T20:23:42Z (fix/hq-b2b50b-active-limit): Created scratch on titan: $WORK_ROOT/hq/hq-b2b50b for replay measurement script/results; owner task:hq-b2b50b; contents mutable, not yet checkpointed.
- 2026-11-02T20:24:41Z (fix/hq-b2b50b-active-limit): Pilot: existing replay recovered the reported 4.099 h / 59 calls / 7 spawns / 0 compactions turn and pauses it only at the 4 h candidate. The 41.643 h controller remains caught at 9.857 active hours by the 501st root call under 12/16/24 h candidates. Pilot: 2 roots, 122 transcript files, 5.37 s, no scheduled-record problems. Beginning 2026-10-02 through 2026-11-02T20:00Z store comparison at 4/8/12/16/24 h; explicit-budget turns separated.
- 2026-11-02T20:27:12Z (fix/hq-b2b50b-active-limit): attached: active-cutoff-measure.py (3411 bytes): Read-only candidate comparison using turn_pause.replay; run from hq checkout
- 2026-11-02T20:27:14Z (fix/hq-b2b50b-active-limit): attached: active-cutoff-measurement.json (12410 bytes): 2026-10-02 through 2026-11-02T20Z: 6005 turns, 6596 files, 4/8/12/16/24 h replay candidates
- 2026-11-02T20:27:33Z (fix/hq-b2b50b-active-limit): Decision: use 16 h active, retaining 500 calls / 30 spawns / 2 compactions and existing proportional budget semantics. Why: 6005 replayed turns (3490 Claude, 2515 Codex), p99.9 active 9.549/10.195 h; 4 h pauses 52 turns, 8 h 26, 12 h 26, 16 h 26, 24 h 25. At 16 h only 2 turns exceed the time threshold; the 41.643 h Codex case pauses first on calls at 9.857 h, leaving one independent time-only stop at 21.101 h. 12 h adds no pause coverage and preempts the 15.655 h controller before its spawn limit at 14.021 h; 24 h loses the independent time-only guard. Cost: compared with 4 h a low-call low-spawn runaway can run up to 12 active hours longer; tails are not validity-labelled and the 21.101 h controller was doing review corrections, not proven runaway. One host/live-store window, partial edge turns and converter limitations apply; no claim of zero false positives. Budget: 12h now scales unnamed counts to 375 calls / 23 spawns / 2 compactions; 48h scales to 1500/90/6. Activation may pause already open turns via limits-changed; require fresh user prompt afterwards.
- 2026-11-02T20:28:31Z (fix/hq-b2b50b-active-limit): Correction to candidate arithmetic: 8 h pauses 27 turns (14 Claude plus 13 Codex), not 26. The selected 12 h / 16 h totals remain 26. Full comparison and limitations are in docs/notes/2026-11-02-active-cutoff-report.md; the two measurement attachments are committed and portable.
- 2026-11-02T20:45:52Z (fix/hq-b2b50b-active-limit): Baseline: hydrated worktree via just setup; no .tt.toml, so policy enabled. just test passed 2672 tests (268 agent-tool + 2012 hook/tool + 391 parallel cutover + 1 serial signal); the hook/tool segment took 695.41 s and parallel segment 600.89 s. No test-fast or test-one declared; focused verification uses the uv/pytest invocation declared by just test, narrowed to affected files, with just test again before commit. No code was changed before baseline.
