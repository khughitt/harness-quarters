---
id: hq-b9ab40
title: "Per-kind lifecycles: does one flow fit every task type?"
status: shelved
priority: 3
defer: 2026-11-30
wake_on: [tasks-5b73bf]
created: 2026-09-18T18:56:12Z
updated: 2026-10-31T11:07:18Z
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
- 2026-10-31T11:07:06Z (main): shelved: tasks-5b73bf writes the kinds section, and a retro listing or an obs-00809f report shows one kind's flow tasks skipping or faking a gate or repeating the same friction
- 2026-10-31T11:07:18Z (main): scope: shelved; renewed the missing checkpoint to 2026-11-30, retaining the full two-part condition. tasks-5b73bf is still todo; the current curate-kinds deliverable remains outstanding. The 127 retros since 2026-09-24 (no scan warnings) do not establish kind-specific gate friction. obs-00809f is done but E1 remains unvalidated, tracked by obs-c1b5ac; closure alone does not supply the required kind evidence. Related direction: flows-912ac5 types existing gates rather than establishing per-kind lifecycles. Evidence: tasks 7589a04, flows 55b28e4, obs 2e31cd0. origin: filing unavailable (no stamped creation occurrence); canonical mindful thought:7b1b0c108103464388357acb293ad0ed confirms the human's lifecycle question, separately from the task's evidence conditions; origin field unchanged.
  provenance: {"harness_session":"codex:01a1919f-7e52-7202-94dd-12751aee4777","harness_session_source":"CODEX_THREAD_ID"}
