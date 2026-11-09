# Consume the rename receipt before moving the checkout

Task: hq-74f102. Status: proposed, revision 1; awaiting human review.

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
  commands. For a detached checkout, print a scoped command from the new checkout:
  `tasks commit --project <new> tasks/.config.toml -m "chore(tasks): relocate <new> checkout"`.
  Include an explicit `-C <new-root>` in the emitted command, with shell quoting.
  This second commit records only the changed checkout path before retargeting.
  In-tree callers still commit their subsequent code/config edits as their runbook
  requires. Neither path prints the old raw rename commit command.
- A receipt commit failure stops before the move, preserves the receipt and
  reports the command's failure. Git may already have committed before a later
  receipt-removal error; do not assume a failed command means no commit exists.
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

Execution Setup runs the focused baseline through
`just test-one tools/test_rename_cutover.py`; implementation preserves focused
RED→GREEN and runs `just check-hygiene`. Record counts and deliberately omit the
broad suite under the validated checkout policy. Documentation-only preparation
adds no test obligation. An approved implementation plan follows human approval
of this design; neither approval authorizes a live cutover.
