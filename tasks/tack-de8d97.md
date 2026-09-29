---
id: tack-de8d97
title: Restore Codex project trust automatically after a checkout drops it
status: doing
priority: 3
size: s
complexity: mid
process: planned
owner: codex-trust-restore
created: 2026-09-28T10:51:24Z
updated: 2026-09-29T10:42:56Z
started: 2026-09-29T09:14:43Z
depends: []
tags: [rules]
agent: claude-code/claude-opus-5-5
spec: docs/specs/2026-09-29-codex-trust-restore-design.md
plan: docs/plans/2026-09-29-codex-trust-restore.md
---

From the local-layer review: with trust out of the index, a merge, rebase, checkout or clone that writes a new codex/config.toml blob into the main checkout drops the live [projects.*] tables on every host at once (the checkout is shared through Dropbox). README documents a manual save/restore. Wanted: keep the tables in local/ and restore them without a manual step, e.g. the clean filter writes a sidecar and a post-merge/post-checkout hook re-appends it. Needs a design: where the sidecar is refreshed and how stale entries are handled.

## Notes

- 2026-09-29T09:04:41Z (main): Moved off tack-5b608f when it closed: a follow-up to the local layer, not needed for publication.
- 2026-09-29T09:14:43Z (main): started
  provenance: {"harness_session":"claude-code:669361e4-a89f-455b-a473-2b02963d95ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T09:17:36Z (codex-trust-restore): parked (waiting on user, review): User reviews docs/specs/2026-09-29-codex-trust-restore-design.md in .worktrees/codex-trust-restore; on approval, agent writes the plan with writing-plans
  provenance: {"harness_session":"claude-code:669361e4-a89f-455b-a473-2b02963d95ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T09:49:10Z (codex-trust-restore): Spec review round 1: hook-less branch switch, conflicted merge (no post-merge) and pre-first-capture window added to the spec; switch and merge cases reproduced on git 2.55.0
- 2026-09-29T09:54:36Z (codex-trust-restore): resumed
  provenance: {"harness_session":"claude-code:669361e4-a89f-455b-a473-2b02963d95ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T10:08:00Z (codex-trust-restore): parked (waiting on user, review): User reviews docs/plans/2026-09-29-codex-trust-restore.md (and the planning amendments to the spec) in .worktrees/codex-trust-restore and picks subagent-driven or native; then the agent executes Task 1 (tack-197b79)
  provenance: {"harness_session":"claude-code:669361e4-a89f-455b-a473-2b02963d95ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T10:17:14Z (codex-trust-restore): Plan review round 1: rollout live check gated on git diff --quiet; restore refuses a headerless file without a final newline and checks the filter output is unchanged; README qualifies fresh clone
- 2026-09-29T10:23:20Z (codex-trust-restore): resumed
  provenance: {"harness_session":"claude-code:669361e4-a89f-455b-a473-2b02963d95ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T10:42:56Z (codex-trust-restore): Tasks 1-4 landed (982283a..5764f5d); final review fix 70e6c85 (multi-line string placement); deferred minors filed as tack-46ba6c
