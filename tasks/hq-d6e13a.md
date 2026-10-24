---
id: hq-d6e13a
title: Prepare native agent-toast suppression for coordinated desktop attention
status: todo
priority: 2
size: m
complexity: mid
process: direct
created: 2026-10-24T14:13:27Z
updated: 2026-10-24T21:32:40Z
depends: [hq-4c954d]
tags: []
agent: codex
---

For fam-9c8dd1 rollout, prepare and validate owner-specific suppression/filtering of native Claude/Codex/OpenCode agent toasts so the Noctalia attention coordinator is their sole event-toast producer, preserving relay Notification/permission/session hooks and unrelated application notices. Verify current native versions rather than relying on historical settings; provide isolated captured-output checks showing required lifecycle hooks still fire when native notifications are suppressed, include workers and fresh sessions, and document exact setting preimages/restore commands. Do not apply live changes or merge through live config pointers without user approval. Activation is gated on familiar implementation, widget health detection and the hq-4c954d concurrency evidence; report unsupported filtering rather than silently disabling useful requests.

## Notes

- 2026-10-24T21:32:40Z (main): fam-9c8dd1 code is reviewed (unmerged). Its runbook (docs/runbooks/desktop-attention-rollout.md on familiar's feat/desktop-attention) starts the familiar coordinator's toasts at step 4 and applies this task's suppression at step 7: between them native and familiar toasts duplicate, so have the suppression ready to apply right after the coordinator's readiness check.
