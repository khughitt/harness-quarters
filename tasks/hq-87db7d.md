---
id: hq-87db7d
title: "Add the mid-merge recovery caveat to AGENTS.md, the harness manifest spec and justfile"
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: docs/hq-87db7d-recovery-caveat
created: 2026-11-01T19:26:17Z
updated: 2026-11-07T11:31:56Z
started: 2026-11-07T11:26:30Z
depends: []
tags: [docs]
origin: agent
---

Deferred from hq-2eba07's reviews. README and the adding-a-harness runbook say that during a merge or rebase 'git checkout -- harnesses.toml' fails on an unmerged path (resolve the conflict or abort instead, never unset filter.harness-state.required); AGENTS.md Rules and the spec's 5.5.1 recovery line still give only the checkout command. justfile line 1 still says 'after pulling a change to it' (AGENTS.md now says 'to the recipe'). README's broken-manifest paragraph could also note the racy-clean case: while harnesses.toml is broken, an unrelated git add within about a second of an index write can fail because git re-filters racily clean configs.

## Notes

- 2026-11-01T19:26:17Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-07T11:26:30Z (main): started
- 2026-11-07T11:26:32Z (docs/hq-87db7d-recovery-caveat): resumed
- 2026-11-07T11:26:56Z (docs/hq-87db7d-recovery-caveat): trial: flow-trial-1 — enrolled — flow on
- 2026-11-07T11:26:58Z (docs/hq-87db7d-recovery-caveat): arm: flow-trial-1 — unit tack-87db7d — flow on
- 2026-11-07T11:27:23Z (docs/hq-87db7d-recovery-caveat): gate: scoped — adopted
- 2026-11-07T11:27:25Z (docs/hq-87db7d-recovery-caveat): gate: implementing .worktrees/hq-87db7d
- 2026-11-07T11:27:27Z (docs/hq-87db7d-recovery-caveat): baseline: documentation-only scope (AGENTS.md, docs/specs/2026-11-01-harness-manifest-design.md, README.md, and justfile comment) under validated policy-off (.tt.toml automatic_broad = false); no focused or broad test obligation.
- 2026-11-07T11:31:49Z (docs/hq-87db7d-recovery-caveat): review: impl round 1 — verdict: accept; findings: none; reviewer: agy
- 2026-11-07T11:31:51Z (docs/hq-87db7d-recovery-caveat): review detail: round 1 on tree 5133ff5760cc90fdccd7e4088593ca7d2e3be757 by session:agy:6aba736f-10bf-493f-8ca6-562704a50395 accepted with 0 findings. Reviewer label recorded as bare agy because timeout 2 relay model --harness agy --pretty exited 2 on hq's pinned relay v0.3.0.
- 2026-11-07T11:31:53Z (docs/hq-87db7d-recovery-caveat): gate: verified tree:5133ff5760cc90fdccd7e4088593ca7d2e3be757 — checks: just check-hygiene exit 0 and tasks check exit 0; review: none; reviewer: agy
- 2026-11-07T11:31:56Z (docs/hq-87db7d-recovery-caveat): retro: Updating AGENTS.md, docs/specs/2026-11-01-harness-manifest-design.md, justfile, and README.md together aligned every broken-manifest recovery and setup-recipe passage with the adding-a-harness runbook.
