# Whole-branch review: rename receipt consumption

What this change does: `apply` now commits the rename through tasks before moving the checkout, then commits the detached config relocation when applicable. It refuses surviving receipts, preserves successful commit warnings, and allows rollback to restore unchanged or removed original inventories without treating them as foreign writes.

Verdict: **Accept with one Minor finding.** No Critical or Important finding. The minor does not block integration.

## Reviewed revision and identity

- Repository: hq.
- Frozen HEAD: `96aeb2a7032e87fa9ede6708d7fe0dcfbf52d311`.
- Base: `4cda27164be61caf1b006397256ac20d01786aa8`.
- Reviewer identity: `codex/gpt-6-astra`, freshly verified during this review by `timeout 2 relay model --harness codex --pretty`, exit 0.
- Binding spec: `f975b51ceb554f9df229d10d22b6f10314c436ab:docs/specs/2026-11-09-rename-receipt-design.md`.
- Binding plan: `be04346961dfae9cd1950d2800c8cd6794e4bbe1:docs/plans/2026-11-09-rename-receipt.md`.
- Execution rulings read in the supplied workspace's `progress.md`: use hqprobe; run the unrenamed normal-hook baseline; merge main before rehearsal; reproduce the exact named retained refs inside the disposable clone. These preserve the approved behavior and do not introduce an alternate commit order or bypass.

## Actionable finding

1. **Minor — recovery text still sends the operator to a command that apply no longer prints.** Locations: `tools/rename-cutover:1264-1266`; related fixture description at `tools/fixtures/records-hook/README.md:8-11`.

   `verify_records` handles any uncommitted change under owned records paths. For example, the existing `test_verify_fails_while_the_records_repository_holds_uncommitted_config` edits the relocated config after successful apply and enters this branch. The diagnostic still says to commit the rename with “the line apply printed,” although this change removes that printed line and commits the rename itself. The fixture README repeats the same obsolete contract.

   Smallest fix: remove that parenthetical from the diagnostic and describe committing the remaining edits; update the fixture sentence to say that apply invokes tasks commit. Historical specs and plans should remain historical. If deferred, an operator gets misleading recovery guidance, but verify still refuses the dirty state and rollback remains available. This is not a data-loss or success-reporting defect.

## Code and failure-path review

Reviewed the complete runtime tool, the code/test diff, the connected sandbox helpers and relevant existing rollback tests, the real pre-commit hook, and the saved rehearsal driver. Expected load is one operator performing a bounded rename against the saved repositories; no concurrent cutover guarantee is claimed or required here.

- **Commit boundaries:** `apply` checks receipt absence before rename, calls `commit_tasks` from the original checkout, checks receipt absence again, and only then moves checkout/storage. A detached relocation calls `init --force` followed by the scoped config commit from the explicit new checkout. Success is printed only after that call returns. The first commit has no positional targets; the second selects only `tasks/.config.toml` with the specified conventional subject.
- **Pretty-format environment and warnings:** the shared helper always invokes `tasks --json commit`. Both argument vectors are checked by the unit test; the actual in-tree and detached apply tests run with `TASKS_FORMAT=pretty`. Successful reports must be objects with a list of string warnings. Each warning is printed intact with command context, with no execution of suggested recovery commands. Invalid JSON/report shape raises before the next apply action. Tests cover the helper's malformed-report path; propagation through apply is directly visible in the sequential calls.
- **Refusing hooks:** the new detached test fails the receipt hook while the original checkout still exists and the receipt remains, or fails relocation only once the new checkout exists and the receipt has gone. It then restores the fixture hook and runs rollback to exact saved fingerprints and clean task/Git checks. I hand-traced both states through guard, move_back, patch/copy preservation, scoped records restore, restored registry/state, and the records revert commit. The new early commit does not bypass those recovery stages.
- **Interrupted and uncommitted renames:** direct `tasks rename` now constructs the cases needing an unconsumed receipt or uncommitted leftovers. Existing stopped-stage tests still exercise files/config/records/registry boundaries; tests for preserved note bytes and repeated leftover copies no longer depend on successful apply remaining uncommitted. Separate tests cover committed apply, scoped rollback after relocation, unrelated records drafts/commits, attachments, live trust preservation, and second-host adoption.
- **Inventory ownership:** changed/new inventory bytes are checked against source, target and root; all must be strings before root path conversion. Identical saved bytes are accepted without reinterpreting original foreign ownership, and removal of a saved inventory remains restorable. The guard adds these owned paths to its exclusions, while rollback later replaces state with the saved directory. The foreign changed-inventory tests still refuse before mutation. Receipt refusal uses lstat, so unreadable contents, directories and dangling links cannot be mistaken for absence.
- **Scope:** only the intended runtime tool and its tests change among runtime files. The tool docstring describes the new operator contract and cites the amendment. No new dependency, collected real-hook test, hosted omission, live cutover, or general runner framework was introduced. The stale diagnostic above is the one remaining operator-text mismatch found.

## Evidence examined

Evidence paths below are relative to the controller-provided execution workspace; the portable rehearsal report is committed at `tasks/files/hq-5e90dd/real-hook-rehearsal.md`.

- `task-1-tests-6fap40.log` records `just test-one tools/test_rename_cutover.py`: 218 collected, 218 passed in 181.37 seconds. This is saved implementer evidence at `091984c51971fa2685138f00f1ba00b04e208349`, not a fresh reviewer test run. A direct Git comparison confirms the reviewed tool and test bytes have not changed since that revision.
- Inspected the saved RED/GREEN summaries and relevant failures in `red.log`, `green-new.log`, `green-migration.log` and `mutation-red.log`. The targeted mutation log records two failing tests when the removed-original-inventory tolerance and the post-commit receipt check are absent.
- Read `rehearsal-3/driver.py`, `evidence.json`, the command records, and hook invocation lines in both traces. Independently checked the recorded driver/command/trace digests, byte equality of current and frozen driver copies, and successful command statuses. This was evidence inspection, not another hook run.
- The unrenamed baseline commit `544e5263abc64eb8ce7f35bf89b0c6f1312ea7a9` has an empty tree diff. Both baseline and renamed traces record the actual `.githooks/pre-commit` invocation without `--ci`; setup records `core.hooksPath=.githooks`. The frozen hook's ordinary path runs hygiene, docs validation and both staged checks, and its bytes match the candidate.
- The receipt commit `7218f9acd27a5ece2dfe3d91c84b98acb31b7576` reports 1703 paths, no warnings, exit 0. The resulting commit differs from the pinned candidate only under `tasks/`; guide/identity bytes match both the saved before copies and the candidate Git blobs. Checked the saved hook, checker, manifest, attributes and family input files against the candidate. The target receipt is absent.
- The rehearsal candidate is `b5f88e231ab0a64c2ede833543b7be1a48dc117f`; relevant hook/guide/checker inputs are unchanged between it and the reviewed HEAD. The source inventory also pins ops and lore. Preparation failure records establish missing lore reference context in attempt 1 and a missing named local retained branch in attempt 2; they do not show a hook-order incompatibility. Attempt 3 faithfully supplies those inputs and passes.

## Limits and declined judgments

No broad suite or additional focused test was run: `.tt.toml` has `automatic_broad = false`, and reading the code and saved evidence raised no specific correctness doubt requiring another run. Mandatory hygiene success is reported in the controller's saved completion record; I did not repeat it. This review does not establish hosted coverage, live cutover success, second-host live behavior, or future compatibility with a different tasks version. It does not authorize host changes or publication, audit all task bookkeeping, or reopen historical runbook scope.

Verdict: Ship with the Minor recovery-text finding recorded for disposition.
