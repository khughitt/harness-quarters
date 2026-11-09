---
id: hq-63cab5
title: color.py reads the tasks resolver for project colour
status: todo
priority: 1
size: xs
complexity: low
process: direct
created: 2026-11-09T15:46:04Z
updated: 2026-11-09T15:46:04Z
depends: []
related: [ops-99d2b2]
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
