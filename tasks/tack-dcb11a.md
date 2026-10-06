---
id: tack-dcb11a
title: "Residue: rename in place, capability facts, aggregated agent surface, archive review"
status: doing
priority: 1
size: l
complexity: high
process: planned
owner: feat/residue
created: 2026-10-04T10:54:36Z
updated: 2026-10-06T15:45:39Z
started: 2026-10-06T11:20:33Z
depends: [ops-f2405d]
tags: []
source: ops-cb9749
agent: claude-code
spec: docs/specs/2026-10-06-residue-design.md
plan: docs/plans/2026-10-06-residue.md
---

Why: phase 3 of the agent layer split (ops docs/specs/2026-10-03-agent-layer-split-design.md §4.1, §5.3, §6). What remains of tack after flows and lore leave is harness support: homes, links, state hygiene, session archive, mods, capability facts.

Done: tack renamed in place by the rename design's procedure (tasks rename, identity.toml, the mirror, the registry on each host, links.toml targets, just projects in ops) once the user names it; an ordinary project guide and [agents] scope dropped from identity.toml (landed with phase 2's removal commit); capability facts with a typed value and a separate evidence status, starting with CHILD_WAKES, WAKING and IN_FLIGHT moved out of ops hooks/claim-guard; wake-judge kept here as the probe tool; archive/ and doc/ref/ reviewed in place with a recorded disposition; tack's identity-mirror feedback scope corrected.

## Notes

- 2026-10-06T11:20:33Z (main): started
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T11:20:37Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-10-06T11:20:37Z (main): arm: flow-trial-1 — unit tack-dcb11a — flow off
- 2026-10-06T11:32:56Z (feat/residue): review: spec round 1 — verdict: revise; findings: P2 3; reviewer: codex/gpt-6-astra
- 2026-10-06T11:32:57Z (feat/residue): name: the user rejects keeping 'tack' (2026-10-06, leaning strongly to a rename; dislikes the name and its connotation); spec §3 is rewritten once a name is chosen
- 2026-10-06T11:34:19Z (feat/residue): review: spec round 2 — verdict: revise; findings: Important 5, Minor 6; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T11:34:37Z (feat/residue): parked (waiting on user, decision): User chooses the residue's new name (candidates given in the session); then this session rewrites spec §3, drafts the rename spec modelled on docs/specs/2026-09-27-rename-to-tack-design.md, and sends the residue spec back for review round 3
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T12:56:04Z (feat/residue): resumed
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T12:56:04Z (feat/residue): review: spec round 3 — verdict: revise; findings: P2 1, P3 1; reviewer: codex/gpt-6-astra
- 2026-10-06T12:56:04Z (feat/residue): name chosen by the user 2026-10-06: 'harness quarters', prefix hq
- 2026-10-06T13:19:00Z (feat/residue): parked (waiting on user, review): User reviews both specs (GPT round): docs/specs/2026-10-06-residue-design.md (after round 3) and docs/specs/2026-10-06-rename-to-hq-design.md (after two fresh-context rounds), and confirms or overrides: the rename no longer runs first; the cutover waits on flows-44890e and obs-ff4e76. Then this session records the round, fixes findings, and on acceptance writes the residue plan first.
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T13:21:53Z (feat/residue): resumed
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T13:21:53Z (feat/residue): review: spec round 4 — verdict: accept; findings: none; reviewer: codex/gpt-6-astra
- 2026-10-06T13:48:21Z (feat/residue): review: plan round 1 — verdict: revise; findings: Critical 2, Important 10, Minor 6; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T14:03:25Z (feat/residue): review: plan round 2 — verdict: revise; findings: Important 1, Minor 9; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T14:03:32Z (feat/residue): parked (waiting on user, review): User reviews (GPT round): docs/plans/2026-10-06-residue.md with docs/plans/2026-10-06-residue.env.sh (after two fresh-context rounds, code rebuilt and run in scratch both times), and docs/specs/2026-10-06-rename-to-hq-design.md (after the round 3 fixes). On acceptance of the plan this session executes it inline from Task 1; the rename spec's acceptance leads to its plan.
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T14:32:54Z (feat/residue): resumed
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T14:32:54Z (feat/residue): review: plan round 3 — verdict: revise; findings: P1 1, P2 2; reviewer: codex/gpt-6-astra
- 2026-10-06T14:33:38Z (feat/residue): parked (waiting on user, review): User reviews (GPT round): docs/plans/2026-10-06-residue.md after its round 3 fixes (Tasks 8 and 10), and docs/specs/2026-10-06-rename-to-hq-design.md after its round 4 fix (§3.2 step 9, §4). On acceptance of the plan this session executes it inline from Task 1.
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T14:52:43Z (feat/residue): resumed
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T14:52:43Z (feat/residue): review: plan round 4 — verdict: accept; findings: none; reviewer: codex/gpt-6-astra
- 2026-10-06T14:52:43Z (feat/residue): parked (waiting on user, decision): Paused at the user's request after acceptance. On the user's go: this session executes docs/plans/2026-10-06-residue.md inline from Task 1 (it stops for approval at Tasks 8, 9 and 10). Separately, the rename's plan is still to be written under tack-8b7a28.
  provenance: {"harness_session":"claude-code:f110e5bf-234d-4815-8f46-8780451c03cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T14:59:19Z (feat/residue): resumed
  provenance: {"harness_session":"claude-code:856ae840-5763-49d7-a62e-93994791cdcb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T15:15:21Z (feat/residue): review: impl round 1 — verdict: accept; findings: Minor 8; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T15:18:47Z (feat/residue): merged to tack main a803d37: facts and tool on main; nothing applied to any host yet
- 2026-10-06T15:25:39Z (feat/residue): surface audit, this host: report non-ok: create ~/.agents/bin/harness-facts (status 0); skills/tasks ok; DANGLING ~/.codex/skills/vercel-react-best-practices -> ../../.agents/skills/vercel-react-best-practices; DANGLING ~/.codex/skills/web-design-guidelines -> ../../.agents/skills/web-design-guidelines; harness-owned real dirs: ~/.claude/skills/{synced,.trash}, ~/.claude-work/skills/synced, ~/.codex/skills/.system, ~/.codex-work/skills/.system
- 2026-10-06T15:30:53Z (feat/residue): approvals (user, in session 2026-10-06): this host's link step; scope chain; deletion of tack archive/ (24-file checksummed inventory); the second host's link step when online, applied only if its preview matches its audit
- 2026-10-06T15:31:33Z (feat/residue): host step done on this host: harness-facts installed and answering; link-check clean; dangling Codex links: vercel-react-best-practices removed, web-design-guidelines removed. Preview/apply scripts ran without just --quiet (just 1.58 suppresses recipe output under --quiet).
- 2026-10-06T15:31:33Z (feat/residue): review: impl round 2 — verdict: revise; findings: Important 2, Minor 4; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T15:37:20Z (feat/residue): archive/ deleted from tack (24 untracked files; 21 committed in lore docs/archive/, 3 mindful v3 leftovers removed)
- 2026-10-06T15:45:39Z (feat/residue): review: impl round 3 — verdict: accept; findings: Important 1, Minor 4; reviewer: claude-code/claude-fable-5-1
