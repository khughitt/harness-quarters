# Mediated cross-harness exchanges

Scoping handoff, 2026-10-10. Goal: hq-67d253. Ideas: hq-dd66c1 and hq-a0ac1c.

## Problem

Reduce the human work of relaying requests, reviews, and corrections between
Claude Code and Codex. Establish which repeated failures deserve a shared message
format or workflow before building a bridge or a general roles system.

## Current behaviour and evidence

- hq-fc26cf measured seven trees with independent Claude and Codex reviews:
  23 distinct real findings, four shared. Both headless invocations worked and
  exposed session IDs. No same-family repeat was run, so the result does not
  distinguish model diversity from the benefit of a second independent review.
  Evidence: task completion notes and commit 0a7db40.
- The earlier cross-harness review brief was removed from this checkout in
  067b5dc when corpus ownership moved to lore. Its historical content is readable
  at `067b5dc^:docs/notes/2026-09-29-cross-harness-review-brief.md`.
  This handoff covers the new session-evidence work; it does not restore or
  supersede lore's maintained recipe or policy. Stale task links: hq-89bd30.
- Both typed Mindful sources resolve: `thought:34328bb6f74e4517bb0c5a2569ade36b`
  and `thought:47f2f857a23d382e61fa6f4bb210b109`. The newer source proposes
  annotating mediated exchanges before defining graphs, cycles, schemas, roles,
  and a shared vocabulary; possible scientific specialist roles are later scope.
- `agents/bin/session-episodes` reads both stores and distinguishes human,
  assistant, and tool events. `agents/skills/session-logs/SKILL.md` explains
  provenance and injected context. Neither establishes cross-session handoff
  identity merely from adjacent timestamps. No exchange sample was read in this pass.

## Constraints

Preserve the human spec and plan gates and both review directions. Use existing
session readers; keep private transcript contents out of committed artifacts.
hq owns session evidence tooling, flows owns workflow gates, lore owns general
skills, and relay owns cross-harness dispatch. Shared roles across scientific
disciplines and automatic flow inference remain unvalidated extensions.
The shelved hq-91e028 remains unchanged. Existing hq-a15e38 concerns evidence of
review independence and hq-9dfba9 concerns comparative flow evaluation; neither
answers the mediated-handoff question.

## Alternatives

1. **Existing headless recipe plus a bounded annotation pass — recommended.**
   Recover three exchanges and name concrete failures and candidate message fields.
   The earlier measurement supports one-hop review without new transport.
2. **A small structured handoff artifact.** Consider only if repeated ambiguity
   in that sample can be prevented by explicit fields or round boundaries.
3. **A live bridge and multi-round workflow.** Defer until evidence requires live
   state, repeated exchanges, or coordination beyond a recipe. A graph with cycles
   alone does not establish that requirement.

## Unanswered questions

- Can three distinct mediated chains be recovered with trustworthy links between
  their sessions, including both directions? hq-ba1758 answers or reports gaps.
- Which friction is missing intent, context, role, or termination information, and
  which comes from the harness itself? hq-ba1758 maps each claim to source evidence.
- Is a schema, typed vocabulary, or bridge earned? Re-scope after that finding;
  no implementation or design task is justified yet.
- Should some tasks require cross-family review despite its cost? This remains
  the user's policy decision from the original brief; it does not block annotation.

## Proposed decomposition

| Task | Next action | Ideas it wakes |
| --- | --- | --- |
| hq-ba1758 | Inspect at most 12 candidate sessions, with a 60-minute discovery bound, and annotate up to three supported exchange chains; return a recommendation or precise evidence gaps | hq-a0ac1c, hq-dd66c1 |
| hq-a0ac1c | Keep as an idea until the sample establishes useful roles, fields, and transitions | — |
| hq-dd66c1 | Keep as an idea; prefer the recipe and revisit a bridge only for demonstrated unmet needs | — |

Reuse hq-67d253; no new goal, lane, bridge, or design task. Research completion
records findings on both waiting ideas in the same commit as its result.
