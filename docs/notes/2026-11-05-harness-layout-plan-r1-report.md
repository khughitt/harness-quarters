# Harness layout plan: author self-review

Task: hq-b77d0c. Verdict: accept for user review; no remaining findings.
Reviewer: `codex/gpt-6-astra`, verified in this turn by
`timeout 2 relay model --harness codex --pretty` (exit 0).
This is the writing-plans author self-review, not independent implementation
review or user approval.

Reviewed repository: hq.
Reviewed commit: `432432185328918540402a4f7ebc00820b7642de`.
Reviewed plan: `docs/plans/2026-11-05-harness-layout.md`.
Binding spec: `docs/specs/2026-11-05-harness-layout-design.md` at
`d1399577ffe0fd65feaaa4393332e4f8b3f26498`, approved by the user in this session.

## Checklist and coverage

1. **Spec coverage:** Task 1 covers all five moves, active manifests and code
   consumers, fact probes, private-state boundaries, byte-identical Codex hooks,
   named current runbooks and affected tests. Its activation rehearsal covers
   record-key ordering before post-merge hooks, unfiltered settings, detached agy
   adoption, ignored files and both rollback points. Task 2 covers the separate
   live authorization, host verification, adoption ownership and cleanup.
2. **Step clarity:** The inventory assigns exact current paths and destinations;
   the finite key command has a CLI, pure-function interface, known record maps,
   refusal/no-op behavior and locking limits. The runbook's initiating/post-sync/
   recovery ordering is specified. Task 1 must produce runnable commands and
   exercise them against real fixture hooks before an activation request exists.
3. **Interface consistency:** Task 2 consumes the exact accepted Task 1 build and
   runbook; it adds no runner code or implicit authorization. Saved-record paths,
   config maps, kept private paths and the two unchanged Codex hook files agree
   with the approved design.
4. **Review focus:** All five named conditions map to concrete Task 1 tests.
   Self-review tightened post-sync handling: both possible mtime-selected bases
   must retain the verified merged unfiltered content, so existing adoption
   cannot silently discard it. It also added the two direct probe-import tests.
   These refinements were made before freezing the reviewed revision.
5. **Proportion:** Two dependent tasks, one implementation/rehearsal deliverable
   and one approved operational step. The only new runtime helper performs four
   finite key renames; existing state/link tools handle the rest. No general
   migration system, compatibility layer, new dependencies or model calls.
   Inline execution avoids duplicated context for coupled edits; the final
   independent whole-branch review remains required before activation.

## Evidence and limits

The controller inspected current post-merge hooks, record validation/locking,
detached adoption's mtime logic, path consumers and existing fixture patterns.
`git diff --check`, `just check-hygiene` and the plan commit hook passed.
`tasks check` found no errors and the pre-existing hq-c58737 record-growth warning.
Both child tasks are blocked pending their stated approval gates.

This is a documentation review. Runtime tests, the migration rehearsal and
independent build review have not run; the plan requires them during execution.
No main runtime files, private settings, host links or services were changed.
Plan approval still belongs to the user; live activation is a later distinct gate.
