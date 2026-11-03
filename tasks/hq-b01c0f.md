---
id: hq-b01c0f
title: Run hq's test recipes under host-budget and give agents a budgeted test-one route
status: done
priority: 1
size: s
complexity: low
process: direct
owner: feat/hq-d33cdc-test-policy
created: 2026-11-01T23:42:58Z
updated: 2026-11-03T16:55:11Z
started: 2026-11-03T16:05:39Z
completed: 2026-11-03T16:55:11Z
closed: 2026-11-03T16:55:11Z
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
- 2026-11-03T16:06:54Z (feat/hq-d33cdc-test-policy): Trial assigned flow off; no flow gates will be written for this prerequisite. Claimed for controlled verification preparation only while hq-0d26dc finishes; no budget recipe edit yet. Shared worktree .worktrees/hq-d33cdc and parent-owned external workspace. Existing documented route has no focused entry: the requested just test-one probe is RED with missing recipe (status 1); literal-argv/budget routing self-check is also RED for that same missing feature. Both check scripts/logs live in the open hq-d33cdc-owned workspace; no inherited environment is passed into their subprocess fixtures. The pending post-interpreter full suite will serve as this unchanged-code tree’s baseline before budget edits; no adoption waiver is claimed.
- 2026-11-03T16:23:31Z (feat/hq-d33cdc-test-policy): Proceeding with the scoped budget/focused recipe implementation to enable bounded diagnosis of known hq-36f6c6, which blocked hq-0d26dc full verification. Last unchanged-before-budget full run: 268 agents passed, 2048 hook/tool passed, 1 known archive environment failure; no passing full baseline is claimed. Both prerequisites stay open until shared full verification succeeds. RED checks exist for missing test-one and literal argument forwarding; they run only the recipe boundary, not a guessed test runner.
- 2026-11-03T16:38:30Z (feat/hq-d33cdc-test-policy): review: impl round 1 — verdict: accept; findings: none; reviewer: codex/gpt-6.1-sol
- 2026-11-03T16:54:58Z (feat/hq-d33cdc-test-policy): Verification: fresh combined timeout --signal=INT 1800 just test exited 0 against flow tree 8b962aae04222e06e758c8233cc38f739de068cc: 268 agents (28.36s), 2049 hooks/tools (843.94s), 391 parallel relay (397.71s), 1 serial signal (0.20s), 2709 total passed. Mandatory .githooks/pre-commit exited 0; staged and working fingerprints match, git diff --check passes, tasks check has zero errors and four pre-existing unrelated tag warnings. Focused evidence: archive module 8 passed with explicit-env RED to GREEN, literal argv/budget self-check passed, real budget probe 1 passed. Full runner observed through host-load plus proc/systemd: active background.slice, both worker grants 16, nice 10. Raw logs, frozen patch, diagnosis and independent accept/no-findings report (codex/gpt-6.1-sol) remain under the open hq-d33cdc-owned external workspace. No broad verification was skipped for these independent prerequisites; adoption baseline waiver was not applied here. No remote evidence or hosted claim. Retained accounting: this record owns no independent worktree, scratch or off-tree item; shared .worktrees/hq-d33cdc and all external evidence are owned by open hq-d33cdc. host-load --section session reports nothing left running. No host pointer changes or pushes, no other work modified. Branch feat/hq-d33cdc-test-policy remains unmerged in .worktrees/hq-d33cdc for controller hq-d33cdc to integrate after the approved plan and separate external gates.
- 2026-11-03T16:55:11Z (feat/hq-d33cdc-test-policy): done
  provenance: {"harness_session":"codex:01a1a0e6-b178-7e10-aacc-34aa3af75b7c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-03T16:55:11Z (feat/hq-d33cdc-test-policy): All heavy tests and literal focused route run under observed worker budget, suite passed 2709 tests, independent review accepted
  provenance: {"harness_session":"codex:01a1a0e6-b178-7e10-aacc-34aa3af75b7c","harness_session_source":"CODEX_THREAD_ID"}
