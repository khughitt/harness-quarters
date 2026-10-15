---
id: hq-dd66c1
title: "Friends: a bridge for triggering sub-agents that run in another harness or model family"
status: dropped
priority: 2
created: 2026-09-16T15:57:15Z
updated: 2026-10-15T13:06:36Z
depends: [crew-ba0a02]
parent: hq-67d253
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
- 2026-10-10T12:24:53Z (main): scope: briefed; retained idea and existing parent hq-67d253; hq-fc26cf supports the recipe, not new transport or mandatory cross-family gates; research hq-ba1758 will test unmet handoff needs; historical brief was transferred to lore in 067b5dc; brief: docs/notes/2026-10-10-mediated-cross-harness-brief.md
- 2026-10-15T11:46:22Z (main): 2026-10-15: crew-9b4b47 proposes delegation as crew runtimes (Claude Code, Codex) behind crew's Runtime seam with identity, cancellation and evidence in the attempt record; revisit the recipe-versus-adapter choice against that lifecycle requirement
- 2026-10-15T11:46:30Z (main): readmitted for scope: re-decide against crew-9b4b47
- 2026-10-15T13:05:37Z (main): scope: drop; no edits; crew-9b4b47 now holds the same outcome (hand bounded work to another harness or model family through one request, without knowing the mechanics) and crew's brief docs/notes/2026-10-15-cross-harness-delegation-brief.md §4 settles this idea's recipe-versus-bridge choice as the existing headless recipe first, then a narrow crew adapter; both ideas already wait on crew-ba0a02; proposal: drop as covered by crew-9b4b47, and on drop remove hq-dd66c1 from the wake lists of crew-ba0a02 and hq-ba1758 (crew-9b4b47 already receives crew-ba0a02's finding)
- 2026-10-15T13:06:36Z (main): dropped
  provenance: {"harness_session":"claude-code:fd2a6a44-57e9-4aa4-a3bc-925843766a56","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T13:06:36Z (main): covered by crew-9b4b47: same outcome (hand bounded work to another harness or model family through one request); crew's 2026-10-15 cross-harness delegation brief §4 settles the recipe-versus-bridge choice; user approved the scope pass's drop proposal 2026-10-15
  provenance: {"harness_session":"claude-code:fd2a6a44-57e9-4aa4-a3bc-925843766a56","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
