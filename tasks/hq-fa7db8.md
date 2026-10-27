---
id: hq-fa7db8
title: Mark the relay cutover runbook and its README entry as a completed record
status: done
priority: 3
size: xs
complexity: low
process: direct
owner: docs/hq-fa7db8-cutover-record
created: 2026-10-27T14:17:54Z
updated: 2026-10-27T18:49:25Z
started: 2026-10-27T18:24:44Z
completed: 2026-10-27T18:49:03Z
closed: 2026-10-27T18:49:03Z
depends: []
parent: hq-7e81ed
tags: []
agent: claude-code/claude-opus-5-5
origin: agent
---

Why: the cutover window completed on 2026-10-22 and the tool is being retired (hq-7e81ed), but README Layout still describes docs/runbooks/relay-cutover.md as the bootstrap the operator runs, and the runbook's 'Evidence: what is proven and what is not' section says the pilot is pending and nothing ran live, against its own 'Completed 2026-10-22' header (curate-docs hq-30fd95 at 8686be3, noted on hq-7e81ed 2026-10-24). An agent reading either today would take the tool as something to run.

Done:
- README.md's 'Relay operator cutover' bullet says the runbook is the record of the completed 2026-10-22 window, that the tool is retired pending deletion (hq-7e81ed), and that relay upgrades go through the pinned relay runtime runbook.
- The runbook's Evidence section states what the window proved (six receipts, four targets on both hosts, per the header and hq-f27918's finish note) instead of a pending pilot. No other section is rewritten: the whole file goes with the tool's deletion.
- docs/runbooks/relay-runtime.md's 'historical operator cutover' link stays valid.

Check: just test passes and the pre-commit hook's ops-docs and ops-check runs pass. Read the two changed passages against the runbook header and hq-f27918's finish note. Under the flow-trial-1 gate, this is a correction to a document's description of a finished event, not a change to treatment or measurement.

## Notes

- 2026-10-27T14:17:54Z (add): created
  provenance: {"harness_session":"claude-code:250666f1-b992-451b-81cc-31d0ea638ce6","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-10-27T18:24:44Z (main): started
  provenance: {"harness_session":"codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T18:25:01Z (main): arm: flow-trial-1 — unit tack-7e81ed — flow on
- 2026-10-27T18:25:16Z (main): gate: scoped — adopted
  provenance: {"harness_session":"codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T18:25:27Z (docs/hq-fa7db8-cutover-record): resumed
  provenance: {"harness_session":"codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T18:27:45Z (docs/hq-fa7db8-cutover-record): retained: {"host":"titan","kind":"worktree","path":".worktrees/hq-fa7db8","state":"kept","verification":"verified","purpose":"Documentation correction and verification","next_owner":"task:hq-fa7db8","cleanup_trigger":"After reviewed documentation merges locally, inspect ignored files and host pointers before removal"}
- 2026-10-27T18:27:47Z (docs/hq-fa7db8-cutover-record): gate: implementing .worktrees/hq-fa7db8
  provenance: {"harness_session":"codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T18:38:06Z (docs/hq-fa7db8-cutover-record): Baseline: hydrated with just setup; just test passed 1674 tests (231 agent-tool, 1051 hook/tool, 391 cutover, 1 signal). Source cross-check: hq-f27918 finish note and runbook header agree on six receipts and completed window; hq-c6c847 completion confirms real-host pilot passed.
- 2026-10-27T18:39:45Z (docs/hq-fa7db8-cutover-record): review: impl round 1 — verdict: accept; findings: none; reviewer: codex/gpt-6.1-sol
- 2026-10-27T18:39:56Z (docs/hq-fa7db8-cutover-record): attached: impl-review.md (1662 bytes): Independent implementation review by codex/gpt-6.1-sol; accepted without findings
- 2026-10-27T18:48:40Z (docs/hq-fa7db8-cutover-record): gate: verified tree:ca032e870e9e7e98e46810d9397b044741441898 — checks: just test 1674 passed and git diff --check passed and Evidence-only scope and historical link checked; review: none; reviewer: codex/gpt-6.1-sol
  provenance: {"harness_session":"codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T18:48:41Z (docs/hq-fa7db8-cutover-record): retro: The task scope and completed-window finish note settled both passages without a new design. Independent review found no issues; the explicit recovery limit avoids turning successful cutover evidence into an unsupported recovery claim.
- 2026-10-27T18:49:01Z (docs/hq-fa7db8-cutover-record): retained: {"host":"titan","kind":"worktree","path":".worktrees/hq-fa7db8","state":"kept","verification":"verified","purpose":"Immediate local integration and checked removal; ignored entries are regenerable Python and pytest caches to discard","next_owner":"session:codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","cleanup_trigger":"After local merge, inspect host pointers and remove the clean task worktree in this turn"}
- 2026-10-27T18:49:03Z (docs/hq-fa7db8-cutover-record): done
  provenance: {"harness_session":"codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T18:49:03Z (docs/hq-fa7db8-cutover-record): Recorded the completed relay cutover, retired-tool status and runtime upgrade route; just test passed 1674 tests and independent review accepted without findings.
  provenance: {"harness_session":"codex:01a17e9a-c533-7680-a754-59ef9d89b3f6","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T18:49:25Z (main): retained: {"host":"titan","kind":"worktree","path":".worktrees/hq-fa7db8","state":"released","verification":"verified","purpose":"Merged locally into main; checked host launchers and user units for references, harvested tt-report, discarded only regenerable Python and pytest caches, removed clean worktree and merged branch","next_owner":"none","cleanup_trigger":"none"}
