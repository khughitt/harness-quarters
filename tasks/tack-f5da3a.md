---
id: tack-f5da3a
title: "Explicit state machine for the task workflow: states, transitions, gates, who advances"
status: done
priority: "2"
size: m
complexity: mid
process: planned
created: 2026-09-15T01:01:58Z
updated: 2026-09-15T11:26:40Z
completed: 2026-09-15T11:26:40Z
depends: []
tags: [flow, skills]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
model: "claude-opus-5[1m]"
agent: claude-code/claude-opus-5
spec: docs/specs/2026-09-15-flow-state-machine-design.md
plan: docs/plans/2026-09-15-flow-state-machine.md
---

Make the workflow model explicit instead of implied by superpowers prose and tracker fields: the states a task passes through (idea, scoped, designed, planned, implementing, verified, done, parked), the transitions, which gate guards each transition (artifact + reviewer + exit criterion), and who may advance it (model, hook, human). The tracker's process, spec, plan, step, and park fields are the current implicit encoding. Output: one diagram and a table the distilled flow and hooks both reference.

## Notes

- 2026-09-15T01:07:15Z (main): Brainstorm 2026-09-15: coexist opt-in per project; first pass = machine + flow skill + flow-state script, proven on one real direct task in Claude Code; harness-neutral prose; no tracker changes, transitions recorded as gate: notes. Spec drafted in worktree .worktrees/flow (excluded, not committed).
- 2026-09-15T02:12:11Z (main): Spec revised after review: back edges land on scoped and void later gates; planned parent/child gates split (parent implementing derived, never started); closed recorded by tasks done, not a gate note; doing allowed pre-implementation as a claim; outside result and adoption rule for pre-existing records; gate: verified carries a revision and goes stale when HEAD moves; fixtures are transition sequences.
- 2026-09-15T02:48:03Z (main): Spec revised again: verification bound to a covered-tree fingerprint (working tree incl. uncommitted, tasks/ and spec/plan docs excluded) instead of HEAD; explicit closing sequence (verify, gate note, retro, done, one commit); parent status is a claim only, allowed todo/doing from planned through verified; parent is implementing from the first child leaving scoped until its own verified gate, including after all children close.
- 2026-09-15T03:05:01Z (main): Spec §3.6 revised: fingerprint index seeded from the real index (tracked-but-ignored files covered), three projections (worktree, --index, --head), closure requires index = worktree = f before the commit and head = f after; dirty covered submodule makes fingerprint refuse (no recursive hashing in the first pass); closed is checked by the closer at close time, not re-derived from git later.
- 2026-09-15T03:18:33Z (main): Spec §3.6: index preflight moved before tasks done; explicit reopen after a failed head check (edit --status todo, start, gate: implementing — reopened) as a second recorded back-edge target; git rm --cached -f in the temporary index so a half-staged task file cannot block the projection.
- 2026-09-15T09:56:28Z (main): Spec: reopened parents carry gate: implementing themselves; a failed closing commit either retries (fingerprint unchanged, cause outside covered content) or reopens with the failure recorded. Four review rounds addressed; spec reviewed, moving to plan.
- 2026-09-15T09:56:47Z (main): gate: scoped — outcome: flow skill + flow-state script + fixtures, proven on one real direct task; approach: spec 2026-09-15-flow-state-machine-design; verification: spec §6. Scoped by the brainstorm, planned process.
- 2026-09-15T09:56:47Z (main): gate: designed docs/specs/2026-09-15-flow-state-machine-design.md — human review, four rounds, all findings addressed.
- 2026-09-15T10:13:59Z (flow): Plan revised after review (9 findings): loader registers the module; porcelain v2 submodule field is parts[2]; trial closing sequence stops on each failed check with the recovery command; closure requires a tree hash and a retro after the current verified gate; parent verification requires validly closed children and names the child's inconsistency; child-left-scoped reads history; planned requires the plan link; skill calls ~/.agents/bin/flow-state; sweep uses checkout-local tasks list.
- 2026-09-15T10:25:00Z (main): Plan: Gate carries its note index and retro_after inspects only later notes (identical same-second gates covered by a fixture); trial closing sequence is one set -eu script with a fingerprint helper that fails on non-zero exit or empty output, exiting at the first failed check with that point's recovery command.
- 2026-09-15T10:37:33Z (flow): gate: planned docs/plans/2026-09-15-flow-state-machine.md — human review, five rounds, all findings addressed; six step children filed scoped.
- 2026-09-15T11:11:46Z (flow): Trial: ai-c6086b closed under flow. flow-state read outside → implementing → verified → closed with no inconsistency; one review fix round moved the fingerprint and verification re-ran at the new tree; the closing script's preflight and head check both passed first time (commit 35f51f2). Session log kept for ai-9dfba9.
- 2026-09-15T11:20:38Z (flow): Incident during final review: a reviewer subagent's chained command ran in the main checkout after a failed cd and overwrote/staged AGENTS.md (the global instruction file); restored from HEAD, nothing else touched. Reviewer prompts now need an explicit scratch path and a no-cd-chaining rule.
- 2026-09-15T11:26:32Z (flow): gate: verified tree:04fedb5e1ad5ced3021f1646426857a38098c311 — full suite 70 passed, pristine; corpus sweep clean; whole-branch review (opus, 25 commits): with fixes — 2 important + 7 minor, all addressed in a17032c and confirmed by scoped re-review; every recorded verified tree re-derived from its landing commit by the reviewer. Deferred minors triaged: all leave except the fingerprint flag fallback, fixed.
- 2026-09-15T11:26:32Z (flow): retro: gates-as-notes worked from the first record (this task's own) with zero tracker changes; the covered-tree fingerprint held across every bookkeeping commit; the plan carrying complete code let cheap models transcribe and the reviews carry the judgment. What hurt: writing notes from two checkouts diverged the record once (rebase conflict), and a reviewer's failed cd wrote into the main checkout — the flow needs a 'where am I' rule as much as a 'what state' rule.
- 2026-09-15T11:26:40Z (flow): Explicit task state machine: flow-state (derivation, covered-tree fingerprint, CLI; 56 tests), the flow skill, and a real direct task closed under it; spec §6 met
