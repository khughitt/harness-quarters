---
id: tack-e2fac3
title: "The derivation reduces the history in order, and reports the verdict"
status: done
priority: "2"
size: s
complexity: mid
process: direct
owner: feat/functional-core
created: 2026-09-22T10:04:33Z
updated: 2026-09-22T10:33:27Z
started: 2026-09-22T10:16:33Z
completed: 2026-09-22T10:33:27Z
depends: [tack-f6a3a1]
parent: tack-634de8
tags: [flow]
agent: claude-code/claude-fable-5-1
plan: docs/plans/2026-09-22-functional-core.md
step: "Task 2: The derivation reduces the history in order, and reports the verdict"
---

Outcome: flow-state derives from reduce_history: well-formed gates append and supersede earlier malformed notes; a malformed note cancels the tail gates naming its state, stopping at a back edge recognised by is_back_edge (state plus leading marker); live malformed notes are the inconsistency, superseded ones a JSON diagnostic; no effective gate means captured, or closed when done; verified derivations carry a verdict summary rendered in the CLI. Approach: plan Task 2, TDD: the sequence tests (fallback, recovery, reopen, prose words, done-only-malformed, parent with a malformed child, CLI verdict) first. Verification: full suite passes with exactly the five named assertion updates; the host sweep comparing main's flow-state with the worktree's over every gated record shows only verified (no verdict) differences and any malformed note found on record, pasted into the task note.

## Notes

- 2026-09-22T10:04:33Z (feat/functional-core): gate: scoped — step of ai-634de8 plan
- 2026-09-22T10:16:33Z (feat/functional-core): started
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T10:16:33Z (feat/functional-core): gate: implementing .worktrees/functional-core
- 2026-09-22T10:28:02Z (feat/functional-core): host sweep: 0 of 2175 records differ between main's flow-state and the worktree's (--no-git); no open verified record exists, so no '(no verdict)' rendering appears; obs-03e018's short-hash verified note is superseded — closed, inconsistent null, malformed:[{note:2, why:'tree hash not 40 hex', superseded:true}] in JSON only; is_back_edge changed no parent's state
- 2026-09-22T10:33:11Z (feat/functional-core): gate: verified tree:966e394b597a9da6d15078fa8b0925397280f73b — uv run --with pytest pytest agents/bin/test_flow_state.py -q: 117 passed, exactly the five named assertions updated plus one regression test; host sweep 0/2175 differ; fresh-context review (sonnet) of the diff at tree db9e0a35: approve with fixes, 1 important addressed at this tree (_child_left_scoped read the child's raw gates, not its reduced history, so a cancelled child gate flipped the parent to implementing; now reduce_history, regression test), 1 minor addressed (docstring ties it to spec 4.2); reviewer probed nine further sequences, all per spec
- 2026-09-22T10:33:11Z (feat/functional-core): retro: the reviewer's important finding was a call site the plan did not list — the plan named which functions consume the reduction but not every function that still read raw gates(); a grep for gates( callers before the gate would have caught it in a minute. Helped: the plan's exact five-assertion contract made the suite diff a one-line check.
- 2026-09-22T10:33:27Z (feat/functional-core): done
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T10:33:27Z (feat/functional-core): reduce_history folds the notes in order: a malformed gate cancels the tail gates naming its state, stops at a back edge (is_back_edge: state plus leading marker), is superseded by a later well-formed gate; live malformed notes are the inconsistency, superseded ones JSON diagnostics; verified derivations carry a findings summary; host sweep 0/2175 differ
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
