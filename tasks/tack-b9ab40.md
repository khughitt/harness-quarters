---
id: tack-b9ab40
title: "Per-kind lifecycles: does one flow fit every task type?"
status: shelved
priority: 3
created: 2026-09-18T18:56:12Z
updated: 2026-09-29T20:54:33Z
depends: [tasks-5b73bf]
tags: [quick-add, flow, question]
source: "mindful:thought:7b1b0c108103464388357acb293ad0ed"
agent: claude-code/claude-opus-5
---

ai-f5da3a formalized the single task lifecycle as the flow skill (captured, scoped, designed, planned, implementing, verified, closed). Open question: whether the common observed task types (defect, decision-needed idea, goal, plan step, feedback, research question) want distinct state and gate sequences, or whether one flow with optional gates covers them.

What would settle it: evidence that the single flow is hurting one kind, e.g. a kind whose tasks routinely skip or fake a gate, or whose retros name the same friction. Depends on task kinds being derived from curation passes (tasks-5b73bf) and on a measure of a flow working (ai-9dfba9).

Rejected: filing under tasks. The tracker has no lifecycle concept; flow lives here.

Source: mindful:thought:7b1b0c108103464388357acb293ad0ed

## Notes

- 2026-09-22T02:55:34Z (main): ai-634de8 (spec section 3.5): a per-kind lifecycle is another gate list over the same states and note grammar; when one exists flow-state reads its machine from a table. That is the shape an answer here would take.
- 2026-09-29T20:54:33Z (main): scope: shelved; flow has closed ~27 tasks in tack and obs, nearly all one kind (tooling plan steps), and the retros (agents/bin/retros, 2026-09-29) show no friction concentrated in a kind; the measure is in obs (obs-00809f), not tack-9dfba9. Added a dependency on tasks-5b73bf, the kinds this question needs.
- 2026-09-29T20:54:33Z (main): shelved: tasks-5b73bf writes the kinds section, and a retro listing or an obs-00809f report shows one kind's flow tasks skipping or faking a gate or repeating the same friction
