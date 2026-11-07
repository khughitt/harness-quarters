---
id: hq-d41fcb
title: Tighten the relay runtime runbook's Codex hook move steps
status: done
priority: 3
size: xs
complexity: low
process: direct
owner: docs/hq-d41fcb-relay-runbook-codex-steps
created: 2026-10-26T15:15:29Z
updated: 2026-11-07T15:38:24Z
started: 2026-11-07T15:36:36Z
completed: 2026-11-07T15:38:24Z
closed: 2026-11-07T15:38:24Z
depends: []
tags: []
source: hq-101302
agent: claude-code
origin: agent
---

Deferred minors from hq-101302's round 3 review of docs/runbooks/relay-runtime.md. 1: the installer command's <version> keeps the v prefix (write v0.2.1 or say the pin's tag), and --evidence FILE should name its source (ops docs/runbooks/relay-guard-evidence-codex.json) or say when it may be omitted. 2: 'reverts the merge' should say git revert -m 1 <merge>, or revert only the pin-and-images commit, since a whole-merge revert also reverts the runbook and task record. 3: say what to do when the only pgrep survivor is codex app-server daemon pid-update-loop (confirm whether daemon stop ends it). 4: a codex-trust line in pgrep is a hook finishing; check again. 5: after the rollback's trust review, commit the personal home's restored hashes too. 6: append (CODEX_HOME unset) to the personal review launch. Docs only; verify each against the rollout hq-101302 actually ran.

## Notes

- 2026-10-26T15:15:29Z (add): created
  provenance: {"harness_session":"claude-code:dd3a0041-6ef0-48cf-a0c1-b98a68b02b56","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-07T15:36:36Z (main): started
- 2026-11-07T15:36:39Z (docs/hq-d41fcb-relay-runbook-codex-steps): resumed
- 2026-11-07T15:37:04Z (docs/hq-d41fcb-relay-runbook-codex-steps): trial: flow-trial-1 — enrolled — flow off
- 2026-11-07T15:37:07Z (docs/hq-d41fcb-relay-runbook-codex-steps): arm: flow-trial-1 — unit tack-d41fcb — flow off
- 2026-11-07T15:38:22Z (docs/hq-d41fcb-relay-runbook-codex-steps): trial-arm: flow-trial-1: flow off (unit tack-d41fcb). Documentation-only change under validated .tt.toml automatic_broad = false creates no test obligation. Verified all six deferred minors from hq-101302 round 3 review against the rollout notes recorded on hq-101302.
- 2026-11-07T15:38:24Z (docs/hq-d41fcb-relay-runbook-codex-steps): done
- 2026-11-07T15:38:24Z (docs/hq-d41fcb-relay-runbook-codex-steps): Updated docs/runbooks/relay-runtime.md for the six deferred minors from hq-101302 round 3 review: (1) stated <version> keeps the v prefix (the pin's tag) and FILE is <ops-records>/docs/runbooks/relay-guard-evidence-codex.json; (2) clarified rollback reverts the pin-and-images commit or runs git revert -m 1 <merge> (noting a whole-merge revert also reverts runbook and task-record changes); (3) documented that codex app-server daemon stop does not end a leftover codex app-server daemon pid-update-loop once the daemon has exited (notRunning), so end it with SIGTERM after user confirmation; (4) noted that a codex-trust line in pgrep -a codex is a hook finishing and to check again once it exits; (5) added committing the personal home's restored [hooks.state] hashes in harnesses/codex/config.toml after rollback trust review; (6) appended (CODEX_HOME unset) to the personal review launch. Verification: focused tests none (documentation-only change); mandatory check just check-hygiene (passed); broad suite just test skipped per .tt.toml automatic_broad = false; remote evidence: none (nothing pushed). Disclosures: host-load --section session reports nothing left running; no task scratch or off-tree evidence created; branch docs/hq-d41fcb-relay-runbook-codex-steps merging fast-forward to local main and worktree .worktrees/hq-d41fcb (no ignored files) being removed after tt-report.
