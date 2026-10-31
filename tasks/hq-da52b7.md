---
id: hq-da52b7
title: "Distilled superpowers: a minimal flow built from reusable blocks"
status: dropped
priority: 2
created: 2026-09-15T00:43:12Z
updated: 2026-10-31T10:54:33Z
closed: 2026-10-31T10:54:33Z
depends: [hq-bc49ed]
tags: [quick-add, skills, obs, flow]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
agent: claude-code/claude-opus-5
origin: user
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
- 2026-10-31T10:47:58Z (main): unshelved
- 2026-10-31T10:48:01Z (main): scope: drop; reviewed the second-flow condition against current intended direction rather than treating today's deterministic implementation as the whole goal. Walker already landed in hq-f5da3a; feedback listing/curation landed in hq-bdff6f/hq-c78706. Remaining native replacement and reusable blocks are held by flows-91a6b4/flows-abf80d and flows-0a19b9, with design flows-8d2f2d explicitly inventorying meaningful current obligations before implementation. Read their bodies and flows docs/notes/2026-10-28-flow-atoms-brief.md at 9f6d9de; flows main 080d86d remains the existing deterministic machine, so this is coverage of intended work, not a claim the replacement is built. Unshelved to a reviewed idea; original sparse/model-discretion goal, body and source preserved. origin: filing event unavailable (no creation occurrence/stamp in show); older request not applicable (no origin_session). Corrected field to user from resolved human-authored thought:48e70c654fd84c6ab72d3f06b6261683, which explicitly asks for sparse superpowers and reusable blocks. proposal: drop as covered by flows-91a6b4 and flows-0a19b9; when accepting, retain the original sparse prose/model-discretion and feedback requirements as input to flows-8d2f2d rather than assume a larger native flow already satisfies them.
  provenance: {"harness_session":"codex:01a1918d-e320-7110-90dd-2422cb01520e","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-31T10:54:23Z (main): drop approved by user 2026-10-31, conditional on preserving otherwise missing intent. Completed the coverage check against flows-91a6b4, flows-8d2f2d and flows-0a19b9 and the resolved typed source. Added sparse guidance/core patterns, model discretion, the original approximate fable-5.1 capability target, and session-grounded model-suggested meta-patterns/strategies to both the native-flow idea and its design task; existing retro listing/curation hq-bdff6f/hq-c78706 are reuse inputs, with gaps to be assessed rather than presumed complete. Existing core phases, inline/delegated execution, worktrees and verification are covered by flows-8d2f2d; reusable blocks/nesting and extraction after a second flow are covered by flows-0a19b9. Original body, source and history retained here; no new task, workflow implementation, trial change or host change. This answers the pending drop proposal; successor task fields and existing approvals remain intact.
  provenance: {"harness_session":"codex:01a1918d-e320-7110-90dd-2422cb01520e","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-31T10:54:33Z (main): dropped
  provenance: {"harness_session":"codex:01a1918d-e320-7110-90dd-2422cb01520e","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-31T10:54:33Z (main): User approved consolidation on 2026-10-31. Missing sparse/model-discretion, capability-target and session-grounded feedback intent is preserved in flows-91a6b4 and design flows-8d2f2d; reusable-block work is covered by flows-0a19b9. Original body/source/history retained in this dropped record.
  provenance: {"harness_session":"codex:01a1918d-e320-7110-90dd-2422cb01520e","harness_session_source":"CODEX_THREAD_ID"}
