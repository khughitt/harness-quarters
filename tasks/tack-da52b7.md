---
id: tack-da52b7
title: "Distilled superpowers: a minimal flow built from reusable blocks"
status: shelved
priority: "2"
created: 2026-09-15T00:43:12Z
updated: 2026-09-22T02:55:34Z
depends: [tack-bc49ed]
tags: [quick-add, skills, obs, flow]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
agent: claude-code/claude-opus-5
---

Build our own sparse version of the key superpowers elements used in projects: (init?) -> brainstorming -> writing-plans -> subagent or inline implementation, plus supporting pieces (git worktrees, verification). Aimed at fable-5.1-level models: capture the core patterns and useful ideas, give the model more free rein, do not over-specify. Include a feedback mechanism where the model can suggest meta-patterns and strategies that worked across problems.

Represent each element as a building block (an atom of useful computation) so blocks can be reused across different processes, workflows, flows, or graphs, including flows other than superpowers.

Depends on the obs work (session-log parsing) because the feedback loop needs observable sessions to evaluate what a flow actually did.

Source: mindful:thought:48e70c654fd84c6ab72d3f06b6261683

## Notes

- 2026-09-15T01:01:58Z (main): Reframe: distilled = the gates, not the prose. Each block is {artifact produced, who reviews, exit criterion}; the how is left to the model. Build around the tasks tracker, whose spec/plan/step links and park reasons already are the state. Blocks are factored out after two concrete flows exist, not designed first; avoid the word atoms (project name).
- 2026-09-15T01:07:15Z (main): The explicit machine (ai-f5da3a) is the first concrete flow; the distilled skill is its walker. Blocks are factored after a second flow exists.
- 2026-09-22T00:31:01Z (main): shelved: A second concrete flow exists to factor blocks against — a per-kind lifecycle (ai-b9ab40) or the self-authored baseline (ai-619958). The distilled flow itself landed as the flow skill (ai-f5da3a); the feedback mechanism is ai-bdff6f and ai-c78706; per-project opt-in (spec §4.3) is each project's own choice, none has taken it yet.
- 2026-09-22T00:31:01Z (main): scope: shelved; of its three parts the walker landed (flow skill, ai-f5da3a), the feedback loop is scoped (ai-bdff6f, ai-c78706), and blocks wait for a second flow as this idea's own note says; brief: docs/notes/2026-09-21-flow-gates-brief.md
- 2026-09-22T02:55:34Z (main): ai-634de8 (functional core framing, spec section 3.5) settles the block shape: a gate is {artifact, check, judge, record}; a flow is an ordered gate list plus back edges; composition is concatenation and nesting. Wake condition unchanged: factor after a second concrete flow.
