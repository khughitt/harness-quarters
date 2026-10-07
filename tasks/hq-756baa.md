---
id: hq-756baa
title: "Flow after the first pass: harness gates and retro curation"
status: todo
priority: "2"
created: 2026-09-22T00:29:43Z
updated: 2026-09-22T00:38:30Z
depends: []
tags: [flow]
source: docs/notes/2026-09-21-flow-gates-brief.md
agent: "claude-code/claude-opus-5[1m]"
---

The explicit machine (ai-f5da3a) and the flow skill landed 2026-09-15 with hooks, measurement, blocks, and the retro store deferred (spec §5, §7). Six days on: 16 tasks closed under the flow across ai and obs (17 retro notes; obs-03e018 closed twice), every record with a verified gate and a retro — which supports deferring more state-gate enforcement but does not by itself establish that every review occurred or covered the right tree; the measure lives in obs (charter §7, obs-e1dd2b's pre-flow stall baseline at 1.4%, obs-a6c7d4's cost per stage); the recorded failure class is the turn boundary (ai-c62995: an abandoned claim, and repeated parking of an unblocked task), not a skipped state gate. This goal holds the two follow-ons that feed on that data: a harness gate on abandoned claims (ai-21ea5d, briefed; probe ai-80b836) and a retro listing with a recurring curation pass (ai-bdff6f, ai-c78706). Brief: docs/notes/2026-09-21-flow-gates-brief.md.
