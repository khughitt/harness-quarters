---
id: hq-7e1e9c
title: "Delete the relay cutover tool, its tests, runbook and allowances"
status: doing
priority: 3
size: m
complexity: low
process: planned
owner: main
created: 2026-10-27T14:17:56Z
updated: 2026-11-10T02:29:40Z
started: 2026-11-10T02:28:09Z
depends: []
related: [ops-630a87]
parent: hq-7e81ed
tags: []
agent: claude-code/claude-opus-5-5
origin: agent
---

Why: the tool served one completed window, and hq-7e81ed decided to retire it rather than fix its six defects. The goal's body keeps the defects as the record, so deleting the code loses nothing a future procedure needs.

Delete: tools/relay-cutover, tools/relay-cutover-bootstrap, tools/relay-cutover-rehearse, tools/relay-cutover-host, tools/relay_cutover_bootstrap/, tools/test_relay_cutover.py, tools/test_relay_cutover_bootstrap.py, tools/test_relay_cutover_transport.py, docs/runbooks/relay-cutover.md, and the window plan docs/plans/2026-10-19-relay-cutover.md if it is still tracked. Also, in the same change:
- remove justfile's two cutover test segments and the --ignore flags in the main segment;
- remove the eight relay-cutover paths in .ops-check.toml's allowances (hq-c6a149) and the fleet-layout prefix entries for tools/relay-cutover and tools/test_relay_cutover.py (hq-d5ba0a). Keep the three wiring-test allowances that protect the live hook strings;
- remove the README.md 'Relay operator cutover' bullet;
- repoint docs/runbooks/relay-runtime.md's 'historical operator cutover' link at the runbook's last commit, or reword it to name hq-7e81ed.
Leave docs/specs and docs/plans that cite the tool as decision records.

Before starting, check for consumers with grep -rn over relay-cutover and relay_cutover outside tasks/ and .git/. Check whether any host still holds ~/.local/state/hq/relay-cutover/ records or saved node_modules copies the tool owned (the user mentioned cleaning these up on 2026-10-22). Give each a disposition under the retained-item rule, and never delete a host's state without saying what it is.

Gate: deferred to 2026-11-30 with hq-ca01cf, under the same flow-trial-1 reassessment (revision 3, change 5). Judge whether removing the tool and two test segments changes what enrolled hq sessions see, or what obs and the verdict tools measure (just test's segments and timing). If it does, it waits for the 2027-02-16 readout. hq-ca01cf depends on this task because tools/relay_cutover_bootstrap/quiesce.py runs tools/quiesce-timers.

Done: the paths are gone, just test passes, and the pre-commit checks pass. grep finds no reference outside tasks/, docs/specs/, docs/plans/ and git history. hq-583ac7 (the tool's deferred review minors) is then moot: propose its drop citing this commit, and keep its raw retained attachment record (hq-c5fd83) in step.

## Notes

- 2026-10-27T14:17:56Z (add): created
  provenance: {"harness_session":"claude-code:250666f1-b992-451b-81cc-31d0ea638ce6","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-08T16:16:07Z (main): Trial gate re-scoped 2026-11-08 at the user's request (flows records docs/notes/2026-11-08-flow-trial-1-gate-scope.md, superseding ops-630a87 change 5's wait-for-readout for flow-trial-1): this step neither reaches the two arms differently nor touches the verdict's inputs (trial-arm census, obs outcomes report), so it no longer waits for readout. Land it on its own merits.
- 2026-11-10T02:28:09Z (main): started
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-10T02:28:36Z (main): arm: flow-trial-1 — unit tack-7e81ed — flow on
- 2026-11-10T02:29:37Z (main): scope grew (evidence 2026-11-09 at main 09dbead8): since filing, the cutover test modules became partitions 3 and 4 of tools/test-suite (relay-parallel under xdist, relay-signal serial), named in tools/test_test_execution.py fixtures, docs/test-execution.md partitions list, AGENTS.md Gates (relay signal test stays serial, xdist reads the grant), .github/workflows/ci.yml PYTEST_XDIST_AUTO_NUM_WORKERS 2 with its partition comment, and docs/specs/2026-11-03-test-execution-policy-design.md (four partitions, hosted zsh requirement for the cutover modules). Deleting the tool now means redesigning the partitions (two partitions or keep xdist for hooks-tools, whether ci-test still needs the explicit worker count, hosted coverage contract), not removing two justfile segments. Other findings: no ~/.local/state/hq/relay-cutover on titan or europa; .githooks/harness-state-clean:37 comment and tools/test_turn_pause_wiring.py:18 comment also cite it. Process changed direct to planned, size s to m
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
