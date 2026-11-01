---
id: hq-8af61d
title: Route agy/hooks.json through pinned relay and native ops hooks once relay-7b8340 and ops-33cef9 land
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-11-01T08:44:46Z
updated: 2026-11-01T08:44:47Z
depends: []
tags: [hooks, cross-project]
source: hq-e72097
agent: agy
origin: mixed
---

Why: hq-e72097 introduced agy/hook as a local adapter because relay (relay-7b8340) and ops (ops-33cef9) do not yet speak Antigravity CLI camelCase hook payloads or its ~/.gemini/config hook working directory. Once those upstream adapters ship, hq should update its pinned relay runtime and route agy/hooks.json through relay and native ops hooks so agy participates in the live-agent registry and avoids duplicating claim-guard translation.

Done:
- After relay-7b8340 and ops-33cef9 land, just relay-install updates relay/ and agy/hooks.json dispatches through relay and native ops hooks (retiring or slimming agy/hook to only hq-owned state).
- Isolated live agy smoke checks and just test pass, with explicit rollout approval before merging live hook changes.

Where: relay/, agy/hooks.json, agy/hook, tools/test_agy_hooks.py, tools/test_claim_guard_wiring.py, README.md.

## Notes

- 2026-11-01T08:44:46Z (add): created
  provenance: {"origin":"mixed"}
- 2026-11-01T08:44:47Z (main): concerns: hq-e72097 extension — migrate agy/hooks.json from the local agy/hook shim to pinned relay and native ops hooks after relay-7b8340 and ops-33cef9 land
