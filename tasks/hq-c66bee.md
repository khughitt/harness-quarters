---
id: hq-c66bee
title: Declare ~/.agents/bin links for flows' flow-gate and flow-graph
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-10-16T04:09:12Z
updated: 2026-10-24T12:55:19Z
started: 2026-10-24T12:55:07Z
depends: []
tags: []
source: flows-912ac5
agent: claude-code/claude-opus-5-5
---

flows adds bin/flow-gate and bin/flow-graph beside bin/flow-state (flows docs/specs/2026-10-15-typed-gates-design.md). The flow skill calls them as ~/.agents/bin/flow-gate and ~/.agents/bin/flow-graph. Add the two rows to links.toml the way flow-state is declared, and install them on every host.

## Notes

- 2026-10-16T09:38:07Z (main): flows-912ac5 final review: relay itself is not on PATH on this host (which relay finds nothing, no ~/.agents/bin/relay), and flow-gate calls relay. Declare relay's CLI link here too, or name the task that installs it; FLOW_GATE_RELAY is the override meanwhile.
- 2026-10-24T12:55:07Z (main): started
  provenance: {"harness_session":"codex:01a16df9-ed57-76a1-967a-ef9db5371dbe","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-24T12:55:19Z (main): trial: flow-trial-1 — enrolled — flow on
