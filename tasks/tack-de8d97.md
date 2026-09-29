---
id: tack-de8d97
title: Restore Codex project trust automatically after a checkout drops it
status: doing
priority: 3
size: s
complexity: mid
process: planned
owner: main
created: 2026-09-28T10:51:24Z
updated: 2026-09-29T09:17:36Z
started: 2026-09-29T09:14:43Z
depends: []
tags: [rules]
agent: claude-code/claude-opus-5-5
spec: docs/specs/2026-09-29-codex-trust-restore-design.md
---

From the local-layer review: with trust out of the index, a merge, rebase, checkout or clone that writes a new codex/config.toml blob into the main checkout drops the live [projects.*] tables on every host at once (the checkout is shared through Dropbox). README documents a manual save/restore. Wanted: keep the tables in local/ and restore them without a manual step, e.g. the clean filter writes a sidecar and a post-merge/post-checkout hook re-appends it. Needs a design: where the sidecar is refreshed and how stale entries are handled.

## Notes

- 2026-09-29T09:04:41Z (main): Moved off tack-5b608f when it closed: a follow-up to the local layer, not needed for publication.
- 2026-09-29T09:14:43Z (main): started
  provenance: {"harness_session":"claude-code:669361e4-a89f-455b-a473-2b02963d95ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T09:17:36Z (codex-trust-restore): parked (waiting on user, review): User reviews docs/specs/2026-09-29-codex-trust-restore-design.md in .worktrees/codex-trust-restore; on approval, agent writes the plan with writing-plans
  provenance: {"harness_session":"claude-code:669361e4-a89f-455b-a473-2b02963d95ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
