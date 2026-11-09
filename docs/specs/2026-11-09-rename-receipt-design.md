# Consume the rename receipt before moving the checkout

Task: hq-74f102. Status: proposed, revision 2; awaiting human review.

Revision 2 addresses spec review round 1: require a real in-tree hook acceptance
case before guide edits, surface successful commit warnings, and have `apply`
commit the detached config relocation itself. The full review is saved in
`docs/notes/2026-11-09-rename-receipt-spec-round-1-report.md`. These are the
author's proposed dispositions; revision 1 remains frozen in its original commit.

## Intent and evidence

A successful forward cutover must leave no `rename-commit/<new>.toml` receipt,
and `verify` must reject a remaining receipt. Today the runbook's raw Git commit
leaves it behind; later bare `tasks commit` calls revalidate stale digests and fail.

This is an agent-filed follow-up to hq-0f7499, not an additional human request.
The source chain reaches the user's request to fix CI failures or file larger
issues separately. The outcome and three deferred guard findings come from the
task records. The approach below is the author's recommendation.

Tree evidence: `tools/rename-cutover` calls `tasks rename`, moves the checkout,
then calls `tasks init --force`. `tools/test_rename_cutover.py` models the manual
commit afterward. In tasks, `src/commands/commit.rs::validate_rename_receipt`
requires the original records path and frozen config/task digests. Moving an
in-tree checkout changes that path; repointing a detached checkout changes the
config digest. The source task records the detached refusal from an attempted
post-move receipt commit. This design has not yet been exercised in a sandbox.

This amends the commit boundary in
`docs/specs/2026-11-02-detached-rename-cutover-design.md` §2 and §4.2: `apply`
will commit the rename itself. The rest of its rollback and adoption contract stays
binding. The older document's statement that test policy is absent is historical;
the invoking checkout now disables automatic broad tests.

## Approaches

1. **Commit through the receipt before moving (recommended).** Reuse the existing
   `tasks commit --project <new>` route immediately after rename. No tasks change
   is needed. Trade-off: `apply` now runs a Git commit and its hooks, and may stop
   before moving the checkout.
2. **Split apply around a manual receipt commit.** Print the commit at the original
   checkout, then resume a separate move phase. This preserves manual committing
   but adds a command boundary and continuation handling for the same result.
3. **Change tasks to refresh receipts after relocation.** This preserves the
   current post-move runbook boundary but changes receipt identity/digest rules in
   another project. The related gap is tracked in tasks-73e604; this fix need not
   wait for or implement it.

## Behaviour

- `save` refuses an existing target receipt, before creating the snapshot, naming
  the path and directing the operator to resolve its owning rename first. `apply`
  repeats this check before `tasks rename` so it cannot overwrite a receipt that
  appeared since save. Do not delete or rewrite that receipt.
- In both layouts, `apply` runs `tasks rename <old> <new>`, then runs
  `tasks commit --project <new>` with no targets, from the original checkout.
  It must succeed and the target receipt must be absent before the checkout or
  storage moves. Use the existing command runner and conventional default subject.
  The tasks command owns receipt validation, path selection, repository locking
  and consumption; hq does not duplicate them or unlink a receipt itself.
- Only then move the checkout/storage and repoint with the current `init --force`
  commands. For a detached checkout, run this scoped commit from the new checkout:
  `tasks commit --project <new> tasks/.config.toml -m "chore(tasks): relocate <new> checkout"`.
  Pass the new root as the runner's explicit working directory. This second
  commit records only the changed checkout path before retargeting. `apply`
  commits its own rename and relocation writes; the runbook commits its own edits.
  In-tree callers still commit their subsequent code/config edits as their runbook
  requires. Neither path prints a manual rename or relocation commit command.
- For both commit calls, parse the successful command's JSON report and print
  every warning verbatim to stderr with the command identified, preserving any
  recovery command it contains. Nonempty warnings do not themselves turn success
  into failure or cause hq to execute their instructions. Require a JSON object
  with a `warnings` list of strings; malformed output stops at that boundary.
  This follows the explicit validation pattern in `committed_check`, without
  introducing warning classes or changing retarget's policy.
- A receipt commit failure stops before the move and reports the command's
  failure, retaining any receipt still present. Git may already have committed
  before a later receipt-removal or report-validation error; do not assume a
  failed apply means no commit exists. A detached relocation commit failure
  stops after the move/repoint, before apply reports success; the rename is
  already committed and its receipt consumed, and the config may be uncommitted.
  Recovery uses the saved snapshot's existing rollback, then a fresh apply;
  no automatic retry or new apply-resume mechanism is added. Failures after the
  commit or move remain within the existing rollback window.
- `verify` refuses any remaining target receipt, including an unreadable entry or
  dangling symlink, before reporting success. Explain that it belongs to an
  uncompleted receipt commit and must be resolved; do not recommend blindly
  retrying a post-move commit whose identity/digests may already be invalid.
- Close the assigned guard findings: validate a live inventory only when it
  differs from its saved counterpart; an unchanged saved inventory is original
  state, not evidence of a new foreign write. Changed/new inventories still must
  match this rename's source, target and root. Require those values to be strings
  before path conversion/comparison, yielding `Stop` rather than `TypeError` for
  malformed values. An inventory removed since save remains restorable original
  state. Existing foreign-state guards retain their scope.

## Scope and acceptance

Change the existing tool, its sandbox tests and its operator-facing description.
Keep the frozen November 2 spec as history and cite this amendment from the tool;
the separate general-runbook task hq-c899fb remains separate. No new dependency,
tasks implementation, host configuration, live cutover or second-host operation
is required. Preserve unrelated records, live picks and rollback evidence.

Sandbox acceptance must cover both layouts end to end: receipt gone after the
pre-move commit and after runbook commits; a later task write followed by bare
`tasks commit` works; detached relocation commits only its config and leaves
another project's draft untouched. Prove a refusing commit hook prevents the
move, preserves the receipt, and rolls back; prove rollback after the new commit,
after relocation and after the scoped config commit. Exercise interrupted rename
rollback directly rather than assuming successful apply still leaves a receipt.
Verify must reject an injected receipt. Test pre-existing receipts at save/apply,
unchanged saved inventories, malformed field types and changed foreign inventories.

The in-tree success case must also use a sandbox copy of hq's real committed
hook inputs, with `just setup` and `core.hooksPath=.githooks`, and an isolated
registry, HOME and Git configuration. Run the normal pre-commit hook, including
`ops-check`, `ops-docs check` and both staged checks; neither `--ci` nor a no-op
substitute proves this case. After `tasks rename`, before runbook edits to
`identity.toml`, README or AGENTS, the receipt commit must succeed with those
files unchanged. Expected reason: guide identity is checked against the still
unchanged identity manifest, and retired ids resolve through the rename alias.
Record actual hook output and the unchanged guide/identity content at that point.
If this fails, return the demonstrated conflict for a design amendment before
implementing an alternate commit order or bypass; there is no demonstrated pass
yet. The fixture must supply its own required registry context rather than read
the user's stores.

For each commit boundary, test a successful JSON response with warnings and
assert that every warning and its recovery instruction reaches stderr while
apply succeeds. Include separate-repository predecessor and staged-recovery
warning examples; these test output transport, not permission to run the
suggested commands. Test malformed reports fail at their boundary, and a refusing
detached relocation hook stops after the move and can roll back. Whole detached
cutovers now finish apply with both commits complete and no manual commit step.

Execution Setup runs the focused baseline through
`just test-one tools/test_rename_cutover.py`; implementation preserves focused
RED→GREEN and runs `just check-hygiene`. Record counts and deliberately omit the
broad suite under the validated checkout policy. Documentation-only preparation
adds no test obligation. An approved implementation plan follows human approval
of this design; neither approval authorizes a live cutover.
