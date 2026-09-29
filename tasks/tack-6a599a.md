---
id: tack-6a599a
title: The verified-note shape in the skill and the flow spec
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: feat/functional-core
created: 2026-09-22T10:04:33Z
updated: 2026-09-22T10:36:23Z
started: 2026-09-22T10:33:33Z
completed: 2026-09-22T10:36:23Z
depends: [tack-e2fac3]
parent: tack-634de8
tags: [flow]
agent: claude-code/claude-fable-5-1
plan: docs/plans/2026-09-22-functional-core.md
step: "Task 3: The verified-note shape in the skill and the flow spec"
---

Outcome: the flow skill's implementing → verified gate row and closing-sequence step 2, and the flow spec's section 3.2 row and section 3.5, carry the verified-note shape (checks; review findings with severity and disposition; reviewer label with optional session); the functional core spec's status line says implemented. Approach: plan Task 3, prose edits only. Verification: tasks check prints nothing; grep 'review outcome' over the skill and the flow spec prints nothing.

## Notes

- 2026-09-22T10:04:33Z (feat/functional-core): gate: scoped — step of ai-634de8 plan
- 2026-09-22T10:33:33Z (feat/functional-core): started
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T10:33:33Z (feat/functional-core): gate: implementing .worktrees/functional-core
- 2026-09-22T10:36:23Z (feat/functional-core): gate: verified tree:537ee59e30773933ceb3a80899d93d83bfe6fccd — tasks check silent; grep 'review outcome' prints nothing in the skill and the flow spec; two concrete notes in the documented shape parse as gate with a Verdict and render 'verified (findings: …)'; fresh-context review (sonnet) of the diff at this tree: approve, no findings
- 2026-09-22T10:36:23Z (feat/functional-core): retro: parsing a concrete instance of the documented shape before the review turned the doc row from prose into a checked example; cheap, and worth doing for any doc that describes a grammar.
- 2026-09-22T10:36:23Z (feat/functional-core): done
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T10:36:23Z (feat/functional-core): the flow skill's implementing → verified row, its closing step 2 and the flow spec's 3.2 row carry the checks/review/reviewer shape; 3.5 names the grammar; the functional core spec is marked implemented
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
