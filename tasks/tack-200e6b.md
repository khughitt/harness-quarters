---
id: tack-200e6b
title: The flow skill
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: flow
created: 2026-09-15T10:03:36Z
updated: 2026-09-15T11:04:09Z
started: 2026-09-15T10:57:37Z
completed: 2026-09-15T11:04:09Z
depends: [tack-23da85]
parent: tack-f5da3a
tags: [flow]
model: "claude-opus-5[1m]"
agent: claude-code/claude-opus-5
plan: docs/plans/2026-09-15-flow-state-machine.md
step: "Task 5: The `flow` skill"
---

Outcome: agents/skills/flow/SKILL.md carrying the rules, states, gates, parent/child, closing sequence, and opt-in from spec §4.1/§4.3; README bullet; ~/.claude/skills/flow link. Verification: the link resolves and /flow loads in a fresh session.

## Notes

- 2026-09-15T10:03:53Z (flow): gate: scoped — step of ai-f5da3a plan
- 2026-09-15T10:57:37Z (flow): gate: implementing .worktrees/flow
- 2026-09-15T11:04:09Z (flow): gate: verified tree:e5c5672623215671d568e46a8da911591aaa92e9 — link ~/.claude/skills/flow resolves and the harness listed /flow in-session; fresh-context review (sonnet) against spec §3/§4: 1 important (adoption must exclude closed records) fixed in 6293b38 with two minors, scoped re-review all addressed; 3 minors deferred (nested planned children unmentioned; gate row 1 artifact compressed; 'findings addressed' dropped from the verified meaning cell)
- 2026-09-15T11:04:09Z (flow): retro: reviewing prose against the spec section by section caught a rule the plan's own text had dropped (no backfill onto closed records); a compression pass needs the same review as code.
- 2026-09-15T11:04:09Z (flow): flow skill: rules, states, gates, parent/child, closing sequence, opt-in; README bullet; harness link
