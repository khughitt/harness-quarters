---
id: hq-d9aefd
title: Clean up europa's relay cutover state
status: todo
priority: 3
created: 2026-10-22T15:45:24Z
updated: 2026-10-22T15:45:24Z
depends: []
tags: []
agent: claude-code
---

The user approved deleting the cutover state on 2026-10-22; titan's was archived and deleted then (see hq-539508), but europa was offline. When europa is up: archive ~/.local/state/hq/relay-cutover and ~/.local/state/hq/relay-smoke without node_modules copies (tar --exclude='*/node_modules' --exclude='relay-cutover/familiar-node_modules.pre') to $WORK_ROOT/hq/hq-539508/cutover-state-europa.tgz on europa (ask the user where if europa has no WORK_ROOT), note its sha256 on hq-539508, then delete both directories. While there, ask whether to run git-index-health --repair ~/d (14 stale indexes on 2026-10-22, ops-e344cf).
