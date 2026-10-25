---
id: hq-0d26dc
title: "Run the uv test segments under the tools' interpreter: uv's managed Python lacks os.pidfd_open"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-25T02:28:24Z
updated: 2026-10-25T02:28:24Z
depends: []
tags: []
source: hq-a7b473
agent: claude-code/claude-opus-5-5
---

Why: just test's uv segments (uv run -q --with pytest ...) pick a uv-managed CPython 3.13.12 whose os module has no pidfd_open (system /usr/bin/python3 3.14 has it). The relay-cutover tools run under /usr/bin/python3 (their shebangs), but tests that execute host operations in-process (transport._execute) run under uv's build, so any in-process stop path (hosts._send in _stop_members) raises AttributeError instead of being exercised. Seen in hq-a7b473: test_service_run_wait_and_result, with a slowed start child, failed with AttributeError: module 'os' has no attribute 'pidfd_open'.

Done: the uv segments in the justfile run on /usr/bin/python3 (uv run --python /usr/bin/python3 ...), or an equivalent explicit pin; just test green; a one-line check (python -c 'import os; os.pidfd_open') under the recipe's interpreter succeeds.

Where: justfile test recipe; tools/relay_cutover_bootstrap/hosts.py _send.
