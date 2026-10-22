---
id: hq-d9aefd
title: Clean up europa's relay cutover state
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: main
created: 2026-10-22T15:45:24Z
updated: 2026-10-22T15:56:21Z
started: 2026-10-22T15:55:36Z
depends: []
tags: []
agent: claude-code
---

The user approved deleting the cutover state on 2026-10-22; titan's was archived and deleted then (see hq-539508), but europa was offline. When europa is up: archive ~/.local/state/hq/relay-cutover and ~/.local/state/hq/relay-smoke without node_modules copies (tar --exclude='*/node_modules' --exclude='relay-cutover/familiar-node_modules.pre') to $WORK_ROOT/hq/hq-539508/cutover-state-europa.tgz on europa (ask the user where if europa has no WORK_ROOT), note its sha256 on hq-539508, then delete both directories. While there, ask whether to run git-index-health --repair ~/d (14 stale indexes on 2026-10-22, ops-e344cf).

## Notes

- 2026-10-22T15:55:36Z (main): started
  provenance: {"harness_session":"claude-code:0835d699-ead2-4a3a-a9f3-1bf52da12939","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-22T15:55:46Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-22T15:55:46Z (main): arm: flow-trial-1 — unit tack-d9aefd — flow on
- 2026-10-22T15:56:20Z (main): scope: outcome — europa holds no relay-cutover or relay-smoke state, and an archive without node_modules copies exists with its sha256 noted on hq-539508. Approach — europa has no WORK_ROOT, so stream the tar from europa into titan's $WORK_ROOT/hq/hq-539508/ beside titan's archive (no europa location to invent), verify its listing, then delete on europa. Verification — the archive lists the window's europa observations and operations, its sha256 is recorded, and the directories are gone on europa. No repository change.
