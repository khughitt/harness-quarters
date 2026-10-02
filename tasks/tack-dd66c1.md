---
id: tack-dd66c1
title: "Friends: a bridge for triggering sub-agents that run in another harness or model family"
status: idea
priority: 2
created: 2026-09-16T15:57:15Z
updated: 2026-10-02T08:14:09Z
depends: []
parent: tack-67d253
tags: [quick-add, skills, flow]
source: "mindful:thought:34328bb6f74e4517bb0c5a2569ade36b"
agent: "claude-code/claude-opus-5[1m]"
---

Claude Code, Codex and other harnesses each have their own sub-agent mechanism, and skills like superpowers subagent-driven development use them. An abstraction over those mechanisms would let a human or an agent call out for a review or a task in a different harness or model family without knowing the mechanics. The insight: review by a different model family catches different things than a weaker copy of oneself, because each family and harness has different biases. Related: ai-91e028 (super friends: the pairwise flow that would run on this layer), ai-fc26cf (one-hop Codex-reviews-Claude through a file in the worktree: the simplest possible bridge, a candidate first step).

Source: mindful:thought:34328bb6f74e4517bb0c5a2569ade36b

## Notes

- 2026-09-29T20:39:20Z (main): scope: briefed; framed as a choice between a documented recipe (lean), a thin friend CLI, and a relay-owned bridge, decided by the tack-fc26cf result; parented under tack-67d253; brief: docs/notes/2026-09-29-cross-harness-review-brief.md
- 2026-09-29T20:47:27Z (main): User 2026-09-29: the Codex → Claude direction is in scope; any recipe or bridge serves both directions. Requiring cross-family review at the gate, and tack vs relay for a bridge, are undecided; brief §5 records both.
- 2026-10-02T08:14:09Z (exp/cross-family-review): tack-fc26cf finding: cross-family review adds real findings both ways (union 23 real, overlap 4; Codex 100% precise but sparse, Claude broader at 75%), and both headless invocations work in one command with session ids readable, so a bridge is not earned for one-hop review: brief §4 now recommends alternative 1 (a documented recipe).
