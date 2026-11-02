---
id: hq-c899fb
title: Write a reference runbook for rename-cutover covering in-tree and detached projects
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-11-02T20:00:54Z
updated: 2026-11-02T20:16:54Z
depends: []
tags: [rename-cutover]
source: hq-5300fd
agent: claude-code
origin: agent
---

The rename procedure lives only in dated plans (docs/plans/2026-10-06-rename-to-hq-cutover.md and earlier) and the tool's docstring. hq-5300fd made the tool general: a detached checkout adds the records commit apply prints (run before retarget --repo), verify's records checks, rollback's owned-path restore and leftovers copies, and the second host's tasks rename <old> <new> --adopt. A docs/runbooks/rename-cutover.md reference document should give the step order (save, apply, the printed records commit, retarget --repo per repository, retarget --forward, link, verify, the other host's adopt), what each step commits, the rollback window and its retry behaviour. Moot if hq-ca01cf deletes the tool; settle that first. Verification: a sandbox rehearsal following the runbook verbatim (the Sandbox in tools/test_rename_cutover.py) reaches verify.

## Notes

- 2026-11-02T20:00:54Z (add): created
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
