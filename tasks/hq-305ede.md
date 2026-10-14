---
id: hq-305ede
title: Isolated Claude first-run onboarding can leave an initial command-line prompt unsubmitted. Experiment guidance should finish onboarding and verify a real conversation/tool call before assuming the seed prompt ran.
status: idea
priority: 2
created: 2026-10-14T10:43:34Z
updated: 2026-10-14T12:59:05Z
depends: []
tags: [feedback, gap, "from:trans"]
agent: codex
---

Observed with Claude Code 2.1.296 and a fresh private configuration directory: theme, terms, directory trust and permission-mode notice preceded an idle session with no transcript/tool call; manually entering the same prompt produced the intended tool call and receipt. Prepared preference copy also used a sibling configuration path while this version wrote its config inside the private directory; capture that version-specific path and cleanup contract in capability guidance.

## Notes

- 2026-10-14T12:59:05Z (feedback): feedback from trans: Confirmed isolated Claude preference seeding and cleanup must use the override directory’s actual config file and preference backups; a sibling seed is not read, and cleanup of that sibling leaves generated account preferences behind.
- 2026-10-14T12:59:05Z (feedback): detail from trans: The bounded slice restored the endpoint/process state and removed copied credentials, but generated private preferences and backups remained. Those files were removed manually after verifying all owned processes had stopped. Experiment supervisor now seeds only allowed onboarding/account fields at the actual config path and removes that file plus its preference backups; focused checks cover normal expiry, hangup and restoration failure.
