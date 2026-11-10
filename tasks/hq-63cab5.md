---
id: hq-63cab5
title: color.py reads the tasks resolver for project colour
status: doing
priority: 1
size: xs
complexity: low
process: direct
owner: main
created: 2026-11-09T15:46:04Z
updated: 2026-11-10T02:17:49Z
started: 2026-11-10T02:16:14Z
depends: [tasks-14ae03]
related: [ops-99d2b2, tasks-d09fc4]
tags: []
source: ops-161e17
agent: claude-code/claude-opus-5-5
origin: agent
---

hq's `tools/hq_cli/color.py` reads project colour from `tasks resolve --json` instead of deriving it.

Source: boundary revision 5 (design ops-161e17, spec and program plan approved by the user 2026-11-09), piece 6.5 of stage 6 (ops-99d2b2); spec: ops records `docs/specs/2026-11-09-boundary-revision-5-design.md` §5.1 rule 5.

Bound: hq only.

Acceptance: hq colours are unchanged.

Constraints (r5 plan, Global Constraints): passes the trial gate as the user narrowed it on 2026-11-08 (flows records docs/notes/2026-11-08-flow-trial-1-gate-scope.md); agent-session policy refuses on an unresolvable profile and never judges the user's own commands (spec §5.4); the resolver's identity and profile query stays config-only and write-free (§5.1); no host pointer (global git config, PATH wrappers, harness settings, services) is repointed and no host-wide hook activated without the user's go-ahead at that moment; publishing, renaming a GitHub repository and pushing need the owner's explicit go-ahead each time.

## Notes

- 2026-11-09T15:46:04Z (add): created
  provenance: {"harness_session":"claude-code:8b04cd6d-bc88-4b52-98d6-cf73afc07a6e","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-10T02:16:14Z (main): started
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-10T02:16:41Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-11-10T02:16:44Z (main): arm: flow-trial-1 — unit tack-63cab5 — flow on
- 2026-11-10T02:17:49Z (main): finding: color.py already takes the hex from tasks resolve (projects.place reads row color since b0b56253); the remaining derivation is color.stand_in (xterm-256 nearest in OKLab, pinned to ops project-colors), which r5 spec 5.1 rule 5 assigns to tasks alone. tasks resolve JSON exposes only color #rrggbb (checked 2026-11-09), so removing stand_in now would either change 256-colour output (breaking acceptance: hq colours unchanged) or keep a copy. Blocked on tasks-d09fc4 exposing the stand-in index in resolve/projects JSON; then hq reads it, deletes stand_in, LEGIBLE_256 use for projects, and the two pinned stand-in tests
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
