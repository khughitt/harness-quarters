---
id: hq-a0cc24
title: "No guide names just relay-subscribers, which renders the config every relay hook reads"
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: docs/curate-docs-hq-30fd95
created: 2026-10-24T22:15:24Z
updated: 2026-10-24T23:53:39Z
started: 2026-10-24T23:34:21Z
depends: []
tags: [docs]
source: hq-30fd95
agent: claude-code
---

Found by the curate-docs pass hq-30fd95 at 8686be3 (criterion 8). The justfile recipe relay-subscribers renders relay/subscribers.template.json into ~/.config/relay/subscribers.json (FORCE=1 replaces different content). Every relay hook in codex/hooks.json and the Claude settings passes that file with --subscribers. Only a dated plan (docs/plans/2026-10-19-relay-cutover.md) mentions the recipe. docs/runbooks/relay-runtime.md, which README links for installing and upgrading relay, does not name it, so a reader setting up relay on a new host cannot find the step. Add one sentence to relay-runtime.md.

## Notes

- 2026-10-24T23:34:21Z (main): started
  provenance: {"harness_session":"claude-code:c2f3e76e-ba29-4176-9424-f3373a5a3562","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-24T23:34:32Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-10-24T23:34:32Z (main): arm: flow-trial-1 — unit tack-a0cc24 — flow off
- 2026-10-24T23:35:17Z (docs/curate-docs-hq-30fd95): resumed
  provenance: {"harness_session":"claude-code:c2f3e76e-ba29-4176-9424-f3373a5a3562","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-24T23:53:39Z (docs/curate-docs-hq-30fd95): review: impl round 1 — verdict: accept; findings: none; reviewer: claude-code
