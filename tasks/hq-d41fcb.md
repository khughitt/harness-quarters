---
id: hq-d41fcb
title: Tighten the relay runtime runbook's Codex hook move steps
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-26T15:15:29Z
updated: 2026-10-26T15:15:29Z
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
