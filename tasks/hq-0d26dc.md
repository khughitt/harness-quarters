---
id: hq-0d26dc
title: "Run the uv test segments under the tools' interpreter: uv's managed Python lacks os.pidfd_open"
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: feat/hq-d33cdc-test-policy
created: 2026-10-25T02:28:24Z
updated: 2026-11-03T15:42:21Z
started: 2026-11-03T15:41:58Z
depends: []
tags: []
source: hq-a7b473
agent: claude-code/claude-opus-5-5
---

Why: just test's uv segments (uv run -q --with pytest ...) pick a uv-managed CPython 3.13.12 whose os module has no pidfd_open (system /usr/bin/python3 3.14 has it). The relay-cutover tools run under /usr/bin/python3 (their shebangs), but tests that execute host operations in-process (transport._execute) run under uv's build, so any in-process stop path (hosts._send in _stop_members) raises AttributeError instead of being exercised. Seen in hq-a7b473: test_service_run_wait_and_result, with a slowed start child, failed with AttributeError: module 'os' has no attribute 'pidfd_open'.

Done: the uv segments in the justfile run on /usr/bin/python3 (uv run --python /usr/bin/python3 ...), or an equivalent explicit pin; just test green; a one-line check (python -c 'import os; os.pidfd_open') under the recipe's interpreter succeeds.

Where: justfile test recipe; tools/relay_cutover_bootstrap/hosts.py _send.

## Notes

- 2026-11-03T15:41:58Z (feat/hq-d33cdc-test-policy): started
  provenance: {"harness_session":"codex:01a1a0e6-b178-7e10-aacc-34aa3af75b7c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-03T15:42:18Z (feat/hq-d33cdc-test-policy): trial: flow-trial-1 — enrolled — flow on
- 2026-11-03T15:42:21Z (feat/hq-d33cdc-test-policy): arm: flow-trial-1 — unit tack-0d26dc — flow on
