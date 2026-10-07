---
id: hq-9dfba9
title: "Define the measure: what a flow working means, and an A/B harness over session logs"
status: shelved
priority: "2"
created: 2026-09-15T01:01:58Z
updated: 2026-09-22T03:05:35Z
depends: []
tags: [flow, obs]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
agent: claude-code/claude-opus-5
---

Decide the metrics before comparing flows: rework commits per task, park reasons hit, review findings per task, rounds to converge, time. Then run the same task under superpowers and under the distilled flow and compare from session logs. Without this the distilled flow cannot be shown better or worse.

## Notes

- 2026-09-22T00:31:01Z (main): shelved: A second flow exists to compare against the explicit machine (a self-authored baseline from ai-619958, or a per-kind lifecycle from ai-b9ab40), or obs asks for controlled repeated runs. The measure itself already lives in obs: charter §7 names this task and sets the outcome measure (a verified gate before closure with an independent reviewer and matching covered tree; costs secondary), obs-e1dd2b reports the pre-flow stall proxy (1.4%), obs-a6c7d4 gives cost per stage and stage revisits from the gate notes.
- 2026-09-22T00:31:01Z (main): scope: shelved; the measure is defined and running in obs (charter §7 cites this id, obs-e1dd2b, obs-a6c7d4), what remains is the A/B runner, which needs a second flow to compare; brief: docs/notes/2026-09-21-flow-gates-brief.md
- 2026-09-22T03:05:35Z (main): obs-abfcf9 (obs) defines the case and verdict records a runner would consume; the runner condition here is unchanged.
