---
id: hq-c66bee
title: Declare ~/.agents/bin links for flows' flow-gate and flow-graph
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-16T04:09:12Z
updated: 2026-10-16T04:09:12Z
depends: []
tags: []
source: flows-912ac5
agent: claude-code/claude-opus-5-5
---

flows adds bin/flow-gate and bin/flow-graph beside bin/flow-state (flows docs/specs/2026-10-15-typed-gates-design.md). The flow skill calls them as ~/.agents/bin/flow-gate and ~/.agents/bin/flow-graph. Add the two rows to links.toml the way flow-state is declared, and install them on every host.
