---
id: tack-dd66c1
title: "Friends: a bridge for triggering sub-agents that run in another harness or model family"
status: idea
priority: "2"
created: 2026-09-16T15:57:15Z
updated: 2026-09-16T15:57:15Z
depends: []
tags: [quick-add, skills, flow]
source: "mindful:thought:34328bb6f74e4517bb0c5a2569ade36b"
agent: "claude-code/claude-opus-5[1m]"
---

Claude Code, Codex and other harnesses each have their own sub-agent mechanism, and skills like superpowers subagent-driven development use them. An abstraction over those mechanisms would let a human or an agent call out for a review or a task in a different harness or model family without knowing the mechanics. The insight: review by a different model family catches different things than a weaker copy of oneself, because each family and harness has different biases. Related: ai-91e028 (super friends: the pairwise flow that would run on this layer), ai-fc26cf (one-hop Codex-reviews-Claude through a file in the worktree: the simplest possible bridge, a candidate first step).

Source: mindful:thought:34328bb6f74e4517bb0c5a2569ade36b
