---
id: hq-b01c0f
title: Run hq's test recipes under host-budget and give agents a budgeted test-one route
status: doing
priority: 1
size: s
complexity: low
process: direct
owner: feat/hq-d33cdc-test-policy
created: 2026-11-01T23:42:58Z
updated: 2026-11-03T16:06:03Z
started: 2026-11-03T16:05:39Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
origin: user
---

Hub goal: ops-4adbbe.

Problem: hq's `just test` runs the relay-cutover files with `uv run -q --with pytest --with pytest-xdist pytest ... -n auto`, outside host-budget, so xdist starts one worker per CPU (32 on titan) at nice 0 in the caller's app.slice scope. Agents copy that line, or other bare `uv run --with pytest pytest <files>` lines, because hq has no focused test route (no `test-one`, no tt front door, no `.tt.toml`). On 2026-11-01 one such run held ~24.5 of 32 cores for minutes while a budgeted job elsewhere was squeezed; nearly all of the 26 unbudgeted runner commands in that two-hour window came from two hq sessions.

Do:
- Run every heavy step of `just test` under `host-budget run --`, and have xdist read its worker count from the grant (`-n auto` honours PYTEST_XDIST_AUTO_NUM_WORKERS, which host-budget sets; or pass `-n "$OPS_WORKERS"`). Keep the serial signal-test step as it is.
- Add a `test-one` recipe that forwards runner args through host-budget, and name it in hq's AGENTS.md as the route for focused runs, so agents stop composing `uv run --with pytest` by hand.
- Coordinate with hq-d33cdc (shared test execution policy adoption), which will also bring the tt front door; this task need not wait for it, but must not conflict with its recipe split.

Done when `just test` and `just test-one` each run inside a background.slice scope with a granted worker count (check with `host-load` during a run), and AGENTS.md names `just test-one`.

## Notes

- 2026-11-01T23:42:58Z (add): created
  provenance: {"harness_session":"claude-code:029eacc3-b922-4a57-bd6b-7fcb7ca9ead1","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"user"}
- 2026-11-03T16:05:39Z (feat/hq-d33cdc-test-policy): started
  provenance: {"harness_session":"codex:01a1a0e6-b178-7e10-aacc-34aa3af75b7c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-03T16:06:01Z (feat/hq-d33cdc-test-policy): trial: flow-trial-1 — enrolled — flow off
- 2026-11-03T16:06:03Z (feat/hq-d33cdc-test-policy): arm: flow-trial-1 — unit tack-b01c0f — flow off
