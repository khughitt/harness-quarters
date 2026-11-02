# rename-cutover for detached projects — implementation plan

> **For agentic workers:** this task runs under the flow skill (trial arm "flow on"):
> each child is `implementing → verified → closed` in this worktree
> (`.worktrees/hq-5300fd-detached-rename`, branch `feat/hq-5300fd-detached-rename`).
> Steps use checkbox (`- [ ]`) syntax. Every new test is seen to fail before the code
> it covers (RED → GREEN), and each new test is also seen to fail against a targeted
> break of the behaviour it checks.

**Goal:** `tools/rename-cutover` saves, applies, retargets, links, verifies and rolls
back a rename whose checkout or `--repo` repositories are detached tasks projects,
restoring only the rename's own paths in the shared records repository.

**Spec:** `docs/specs/2026-11-02-detached-rename-cutover-design.md`, revision 6 (the
user relayed an accepting review of revision 5; revision 6 folds its three minors).
Section numbers below are the spec's.

**Files:** `tools/rename-cutover` (the tool), `tools/test_rename_cutover.py` (its
tests), `tools/fixtures/records-pre-commit` (new: a copy of the records repository's
pre-commit hook, so the tests meet the refusal the live repository makes).

## Global constraints

- In-tree behaviour does not change. Every existing test passes unmodified, except
  the two that pin today's refusal (`test_save_refuses_a_repository_whose_records_live_in_another`,
  `test_save_refuses_a_detached_checkout`), which Task 2 replaces.
- Every check runs before the first mutation (the tool's existing rule); a new check
  goes into the check phase of its command, never between two writes.
- Fail early: every refusal is a `Stop` naming the path or prefix and the remedy; no
  fallbacks, no silent skips.
- Tests isolate everything as `Sandbox` does: an environment built key by key, a
  temporary `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `GIT_CONFIG_GLOBAL=/dev/null`,
  `GIT_CONFIG_NOSYSTEM=1`, `GIT_CEILING_DIRECTORIES`. No test touches the live
  registry, state or records repository.
- hq declares no `.tt.toml`, so the default policy holds: the focused run while
  working is `uv run -q --with pytest pytest tools/test_rename_cutover.py -q [-k …]`,
  and `just test` before each commit.
- Comments and docs name no machine-specific absolute path.

## Review focus

1. §4.5's rollback over a shared records repository: the classification walk, the
   pre-pass (patches and copies before any mutation), the two path sets (restore:
   index or saved head; commit: index or current HEAD), and convergence on retry.
2. That a detached `--repo`'s code checkout leaves the branch, leftover, porcelain
   and reset sets but keeps `tasks check`.

### Task 1: Detached sandbox and the registry guard's records table

Spec §4.6, §5 (fixture, `registry_view`).

- [ ] Add `tools/fixtures/records-pre-commit`: a byte copy of the records
  repository's `.githooks/pre-commit`, with a header comment naming where it comes
  from (the records repository's hook, by repository-relative path) and that the
  tests use it to meet the live refusal.
- [ ] Extend `Sandbox` with `detached=False` and `detached_repos=()`:
  - a records repository at `sync/records` (`git init -b main`, an initial commit,
    `core.hooksPath` set to a directory holding the fixture hook as `pre-commit`);
  - when `detached`, the checkout is a code checkout holding the tools, `links.toml`
    and `.worktrees` link as today but no `tasks/`, paired with `tasks init --prefix
    ai --records sync/records`, its tasks added and parked as today, the records
    repository committed;
  - each name in `detached_repos` is built the same way (code checkout, records under
    `sync/records/<name>`), the others in-tree as today;
  - `fingerprint()` includes the records repository's tree (excluding `.git`) and
    the list of its directories, so empty `docs/specs` and `docs/plans` count.
  The existing `detached()` helper stays for the two tests Task 2 replaces, then goes.
- [ ] Test (RED first): `test_registry_view_reads_a_moved_records_key_as_the_renames_own`
  and `test_registry_view_sees_any_other_records_change` (unit tests on
  `registry_view`, as the existing ones are).
- [ ] Implement: `REGISTRY_TABLES` gains `records`; `registry_view` drops the `old`
  and `new` keys from it as it does for `projects`; `registry_changes` covers it.
- [ ] Test: `test_detached_sandbox_builds` asserts the fixture's shape (the checkout
  has no `tasks/`, `tasks projects` reports `kind` `detached` with `records` under
  `sync/records`, the records repository is clean and its hook refuses a staged
  `<prefix>/` without a config).
- [ ] `just test`; commit.

### Task 2: save for detached projects

Spec §4, §4.1.

- [ ] Tests (RED first), all on the detached sandbox:
  - `test_save_accepts_a_detached_checkout_and_records_its_records_repository`:
    `meta.json` has `checkout.records` (`repo`, `records_root`, `dirs` with the empty
    doc directories), `records_repos` with `root`, `head`, `branch`, `owned`
    (`ai/`, `tack/`, plus `<p>/` for each detached `--repo`), and `kind` on each repo;
  - `test_save_refuses_a_linked_checkout` and `test_save_refuses_a_linked_repo`
    (a linked project from `tasks init --checkout` in an overlay directory);
  - `test_save_refuses_an_unreachable_repo` (a registered root whose config is gone);
  - refusals on the records repository, each leaving no snapshot: off `main`, a
    stash, a second worktree, a branch with commits `main` lacks, an untracked file
    under `ai/`, an ignored file under `ai/`, a tracked change under `<p>/`, a staged
    file of another project, `sync/records/tack` existing, a records directory not
    directly under the repository's top level, a records directory not named for its
    prefix, a records repository inside the checkout or a `--repo`, the snapshot inside
    the records repository;
  - `test_save_accepts_untracked_files_outside_the_owned_paths` (another project's
    draft, and an untracked file under `<p>/`).
- [ ] Implement in `save` and `preconditions`:
  - `project_row` returns the row; a `project_kind(root, command)` helper refuses an
    unreachable row and a linked one with the spec's messages; `project_prefix`'s
    "outside it" refusal goes;
  - a `records_repo(row)` helper returns the git top level of `row["records"]` and
    checks the parent/name contract;
  - collect and deduplicate records repositories with their owned paths; run the
    §4.1 checks on each (branch, stash, worktree, unmerged branches through the
    existing helpers; `git status --porcelain --untracked-files=all --ignored --
    <old>/`; `--untracked-files=no -- <p>/`; `git diff --cached --quiet`);
  - the porcelain and branch checks of `preconditions` skip a detached `--repo`'s code
    checkout; `tasks check` still runs there;
  - write the new `meta.json` fields; `dirs` lists every directory under `<old>/`,
    relative to the records repository, sorted.
- [ ] Remove the two refusal tests and the `detached()` helper.
- [ ] `just test`; commit.

### Task 3: apply, retarget and verify for detached projects

Spec §4.2, §4.3, §4.4.

- [ ] Tests (RED first):
  - `test_apply_refuses_when_the_new_records_directory_exists` (created after save);
  - `test_apply_repoints_a_detached_checkout_and_prints_the_records_commit`: after
    apply, `tasks projects` maps `tack` to the new root with `records` at
    `sync/records/tack`, the config's `[checkout] path` names the new root, and stdout
    carries the scoped `git -C … add -A -- ai tack && git -C … commit … -- ai tack`;
  - `test_the_whole_detached_cutover_retargets_links_and_verifies`: detached checkout
    and a detached `--repo` sharing the records repository (with a dependency on a
    checkout task), save, apply, the printed commit (run as printed, through the
    fixture hook), retarget, link, verify;
  - `test_verify_fails_while_the_records_repository_holds_the_uncommitted_rename`;
  - `test_verify_fails_while_the_old_records_directory_exists`;
  - `test_retarget_stops_on_a_deferred_record_commit` (a staged file of another
    project, staged after save, makes the `tasks edit` warn `commit_deferred:`; the
    retarget stops naming it).
- [ ] Implement:
  - `apply`: the existing-directory check before `tasks rename`; `tasks init
    --prefix <new> --records <records_root> --force` for a detached checkout; print
    the commit line;
  - `write_rewrites`: parse each `tasks edit`'s JSON output and raise `Stop` on a
    warning starting `commit_deferred:` or `commit_failed:`;
  - `retarget --repo`: accept a detached snapshot repository (no change beyond the
    removed refusal; assert it with the whole-cutover test);
  - `verify`: the row, absence and owned-path cleanliness checks of §4.4; `tasks
    check` in every snapshot project.
- [ ] `just test`; commit.

### Task 4: rollback restores the records repository's owned paths

Spec §4.5 (steps 1–5 for the main cases), §4.6.

- [ ] Tests (RED first), each comparing `fingerprint()` before save and after
  rollback for everything the snapshot owns, and asserting what it must not touch:
  - `test_detached_rollback_before_commit_restores_everything`;
  - `test_detached_rollback_after_commit_restores_everything`;
  - `test_detached_rollback_after_a_retarget_without_the_renames_commit` and
    `…_with_it`;
  - `test_detached_rollback_keeps_another_projects_commit_and_draft` (a third
    detached project outside the snapshot commits a record and leaves an untracked
    draft after save; both survive, and rollback's commit holds only owned paths);
  - `test_detached_rollback_removes_a_task_filed_in_p_since_save_and_patches_it`;
  - `test_detached_rollback_recreates_the_old_empty_doc_directories`;
  - `test_detached_rollback_leaves_a_detached_repos_code_checkout_alone` (a commit
    in that code checkout after save survives; it is not on a branch the check
    compares).
- [ ] Implement:
  - `check_branches`, `validate_leftovers` and the final porcelain loop take their
    sets from `meta` with detached `--repo` code checkouts left out; `resets` holds
    the checkout and in-tree `--repo` repositories only;
  - `validate_records_repos(meta)`: the step-1 walk (filesystem under `<old>/` and
    `<new>/`, ignored files included; skip any path in the index, the current HEAD or
    the saved head; map the rest by the id mapping under `<old>/` and the id-or-identity
    mapping under `<new>/` to originals at the saved head; stop on anything else).
    Returns the leftovers;
  - extend `reset_all`'s pre-pass: records patches (`git diff --binary <head> --
    <owned>`, label `records-<name>`) and the copies of step 2 (leftovers, and every
    file under an owned path not in the index whose bytes differ from the saved
    head's) into `rollback-leftovers-<n>/<label>/<path>`; in-tree leftovers are copied
    the same way;
  - `restore_records(meta)`: `git restore --source=<head> --staged --worktree --
    <owned paths the index or saved head holds>`; delete `<new>/` whole; delete the
    `<old>/` leftovers and the directories they emptied; recreate `dirs`;
  - `commit_records(meta)`, after `restore_dir`: when owned content differs from HEAD,
    `git commit -q -m "revert: roll back rename <old> -> <new>" -- <owned paths the
    index or current HEAD holds>`;
  - final checks: `<new>` absent, owned paths with no tracked change, `git diff
    --quiet <head> -- <owned>`, `tasks check` in every detached snapshot project.
- [ ] `just test`; commit.

### Task 5: rollback edge cases, the second host and the docstring

Spec §4.5 (stopped renames, leftovers, retries), §4.7, §5.

- [ ] Tests (RED first):
  - `test_detached_rollback_after_rename_stopped_after_<stage>` for `files`,
    `config`, `records` and `registry` (`TASKS_RENAME_STOP_AFTER`, as
    `test_rollback_after_rename_stopped_midway` does), and after a partial apply
    (renamed, checkout not moved);
  - `test_detached_rollback_copies_a_note_written_before_the_commit` (a `tasks note`
    on a renamed task after apply; the fixture hook refuses its record commit; after
    rollback the note's file sits under `rollback-leftovers-1/`);
  - `test_detached_rollback_stops_on_a_new_task_written_before_the_commit`, naming it,
    with nothing mutated;
  - `test_detached_rollback_stops_on_a_foreign_file_under_new` and `…_under_old`,
    and `…_on_an_ignored_file_under_new`, each with nothing mutated;
  - `test_detached_rollback_copies_a_file_recreated_under_old_after_the_commit`;
  - `test_detached_rollback_retry_converges_after_a_stop_at_the_commit` and
    `…_inside_the_restore` (after the rename's commit; the stop is induced by a
    failing hook or a planted `index.lock`), including a file written at a `<new>/`
    path between the attempts, which lands in the snapshot;
  - `test_detached_second_host_adopts_the_rename` (§4.7: `tasks rename ai tack
    --adopt` from the new root under a second registry; `[projects]` and
    `[records] tack` follow; the old id resolves; the first host's state is untouched).
- [ ] Implement what the tests show missing (expected: none beyond Task 4, except
  any adjustment the stopped stages expose).
- [ ] Update the module docstring: detached projects are supported; rollback
  restores only the owned paths of a records repository; the second host runs `tasks
  rename <old> <new> --adopt`.
- [ ] `just test`; commit.

## Closing (the parent, after every child closes)

- One fresh-context review of the whole branch diff against the spec; corrective
  rounds per the global rule.
- Notes: hq-7255db (findings 3 and 5 landed here), tasks-ea4cc5 (detached renames
  through `rename-cutover` are supported).
- Merge to main (personal checkout: a reviewed branch may be merged locally).
