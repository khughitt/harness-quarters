---
id: hq-2cb1ee
title: Run superpowers 7.0.1 from obra's marketplace with auto-update off
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-10-25T12:18:32Z
updated: 2026-10-25T12:19:14Z
started: 2026-10-25T12:18:43Z
depends: []
tags: [skills]
agent: claude-code
---

claude-plugins-official still pins superpowers 7.0.0 (bb92a77) four days after the 7.0.1 release; obra's superpowers-marketplace offers 7.0.1. User chose 2026-10-25: enable superpowers@superpowers-marketplace, disable the official entry, and set that marketplace's autoUpdate false so the plugin cannot drift ahead of lore's pinned vendor/superpowers. Then install the plugin and bump lore's pin to match.

## Notes

- 2026-10-25T12:18:43Z (main): started
  provenance: {"harness_session":"claude-code:5f570bb5-1b44-4a25-831f-f043464ca1e2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T12:19:12Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-25T12:19:14Z (main): arm: flow-trial-1 — unit tack-2cb1ee — flow on
