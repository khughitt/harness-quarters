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
updated: 2026-11-02T20:27:14Z
started: 2026-11-02T20:22:25Z
depends: []
tags: [feedback, friction, "from:mm"]
agent: claude-code
origin: user
---

The user asked for this (their request): the 4 h active-time limit is too aggressive. It paused a valid subagent-driven plan execution partway through a task, while the session's other counters were far below their limits (about 59 of 500 calls, 7 of 30 spawns, 0 of 2 compactions). The user suggests something closer to 12 or 16 h. They want the implementer to choose the cutoff from historic session data, so that it catches the true outlier sessions without ending valid long-running ones. My reading: a session that only dispatches subagents and waits on them accrues active time while doing little itself, so wall-clock active time may be a weak signal compared with the call, spawn and compaction counters.

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
