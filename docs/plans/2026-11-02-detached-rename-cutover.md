# rename-cutover for detached projects — implementation plan

> **For agentic workers:** this task runs under the flow skill (trial arm "flow on"):
> each child is `implementing → verified → closed` in this worktree
> (`.worktrees/hq-5300fd-detached-rename`, branch `feat/hq-5300fd-detached-rename`).
> Steps use checkbox (`- [ ]`) syntax. Within a task, write every test the task lists
> first and see each fail (RED), then implement (GREEN). A test labelled **guard**
> covers behaviour that already holds; it is instead seen to fail against a targeted
> break of that behaviour, named in the task.

Revision 2 (after plan review round 1, revise: Important 7, Minor 11): the
deferred-commit stop is in the `--repo` path only and its fake-run test is the third
modified test (I1); records repositories join `check_branches` (I2); every walk and
copy behaviour is tested in the task that implements it (I3); the in-tree checkout
with a detached `--repo` is tested (I4); refusal fixtures reach their own check and
assert their own message (I5); the in-tree leftover copy is tested (I6); the detached
fixture commits its config first and its helpers fit automatic record commits (I7);
minors 1–11 folded in.

Revision 3 (after plan review round 2, revise: Important 4, Minor 4): Task 5's guard
tests name breaks that fail in their states (N1); each box gets its own copy of the
hook, so a test can make it fail without editing the tracked fixture (N2); the
misnamed-directory fixture moves the directory and edits the sandbox registry, with no
fallback (N3); `commit()` stays loud and a `commit_rename()` helper plus a HEAD
assertion keep after-commit tests honest (N4); the verify row test breaks `records`,
the nested fixture creates its directory, the deferred-commit check runs after each
edit, and the location refusals cover a `--repo` and a top level equal to the
checkout (M1–M4).

**Goal:** `tools/rename-cutover` saves, applies, retargets, links, verifies and rolls
back a rename whose checkout or `--repo` repositories are detached tasks projects,
restoring only the rename's own paths in the shared records repository.

**Spec:** `docs/specs/2026-11-02-detached-rename-cutover-design.md`, revision 6 (the
user relayed an accepting review of revision 5; revision 6 folds its three minors).
Section numbers below are the spec's.

**Files:** `tools/rename-cutover` (the tool), `tools/test_rename_cutover.py` (its
tests), `tools/fixtures/records-hook/pre-commit` (new, executable: a byte copy of the
records repository's `.githooks/pre-commit`) and `tools/fixtures/records-hook/README.md`
(new: where the copy comes from, why the tests use it, and that whoever changes the
records repository's hook re-copies it here; tests cannot read the live file).

## Global constraints

- In-tree behaviour does not change, except that in-tree leftovers are copied into
  the snapshot before deletion (spec §2). Every existing test passes unmodified,
  except: the two that pin today's refusal
  (`test_save_refuses_a_repository_whose_records_live_in_another`,
  `test_save_refuses_a_detached_checkout`), which Task 2 replaces; and
  `test_retarget_writes_each_task_once`, whose fake `run` returns `""` for `tasks edit`
  and now returns `'{"id":"ops-1","warnings":[]}'` (Task 3), since the `--repo` path
  parses that output strictly.
- Every check runs before the first mutation (the tool's existing rule); a new check
  goes into the check phase of its command, never between two writes.
- Fail early: every refusal is a `Stop` naming the path or prefix and the remedy; no
  fallbacks, no silent skips. Unparseable `tasks` output is a `Stop`, never "no
  warnings".
- Tests isolate everything as `Sandbox` does: an environment built key by key, a
  temporary `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `GIT_CONFIG_GLOBAL=/dev/null`,
  `GIT_CONFIG_NOSYSTEM=1`, `GIT_CEILING_DIRECTORIES`. No test touches the live
  registry, state or records repository. The fixture hook is never bypassed to make a
  build pass; only the one fixture that needs a layout the hook forbids (Task 2's
  nested records directory) commits with `--no-verify`, and says why.
- Every refusal test asserts its own message, not only the exit status and the
  absence of a snapshot or mutation.
- hq declares no `.tt.toml`, so the default policy holds: the focused run while
  working is `uv run -q --with pytest pytest tools/test_rename_cutover.py -q [-k …]`,
  and `just test` before each commit.
- Comments and docs name no machine-specific absolute path.

## Review focus

1. §4.5's rollback over a shared records repository: the classification walk, the
   pre-pass (patches and copies before the first reset or restore), the two path sets
   (restore: index or saved head; commit: index or current HEAD), and convergence on
   retry.
2. That a detached `--repo`'s code checkout leaves the branch, leftover, porcelain
   and reset sets but keeps `tasks check`, and that an in-tree checkout with a
   detached `--repo` owns `<p>/` alone.

### Task 1: Detached sandbox and the registry guard's records table

Spec §4.6, §5 (fixture, `registry_view`).

- [ ] Add `tools/fixtures/records-hook/pre-commit` (byte copy, committed with mode
  755) and its `README.md`.
- [ ] Extend `Sandbox` with `detached=False` and `detached_repos=()`. Only a box with
  either set creates `sync/records`, so in-tree boxes and their fingerprints are
  unchanged:
  - the records repository: `git init -b main`, an initial commit, and
    `core.hooksPath` pointing at the box's own copy of the hook (`tmp/hooks/pre-commit`,
    copied from `tools/fixtures/records-hook/pre-commit` with its mode). A test that
    needs the hook to fail edits only that copy; the tracked fixture is never edited;
  - when `detached`, the checkout is a code checkout holding the tools, `links.toml`
    and `.worktrees` link as today but no `tasks/`; it is paired with `tasks init
    --prefix ai --records sync/records`, and `ai/tasks/.config.toml` (with the empty
    `ai/docs/specs` and `ai/docs/plans`, which git does not track) is committed in the
    records repository at once, before any task write: until the config is in the
    index, the hook refuses every record commit under `ai/`. Then the tasks are added,
    started and parked as today; each write commits itself (`[git] commit = true`);
  - each name in `detached_repos` is built the same way (code checkout, config
    committed, records under `sync/records/<name>`); other repos stay in-tree;
  - `commit(root, message)` is unchanged and still fails when there is nothing to
    commit, so a test that expected a commit learns it did not happen.
    `depend_on_checkout` skips `commit` for a detached root (its records committed
    themselves) and calls it for an in-tree root as today;
  - `commit_rename()` runs, for a detached box, the records commit `apply` prints
    (the scoped `add` and `commit` over `ai` and `tack`), then asserts that the records
    repository's HEAD holds `tack/` and no `ai/`. Every after-commit test of a detached
    box uses it, so none can silently run as a before-commit test;
  - `fingerprint()` adds, for a detached box, the records repository's files
    (excluding `.git`) and its sorted directory list, so empty `docs/specs` and
    `docs/plans` count.
- [ ] Tests:
  - `test_registry_view_reads_a_moved_records_key_as_the_renames_own` (RED: today the
    moved key differs);
  - `test_registry_view_sees_any_other_records_change` (**guard**: holds today through
    `rest`; seen to fail when the new code drops every `records` key instead of only
    `old` and `new`);
  - `test_detached_sandbox_builds` (**guard** on the fixture: the checkout has no
    `tasks/`; `tasks projects` reports `kind` `detached` with `records` under
    `sync/records`; the records repository is clean after the build, so the fixture's
    own writes committed; the hook refuses a staged `zz/` without a config; seen to
    fail with `core.hooksPath` unset).
- [ ] Implement: `REGISTRY_TABLES` gains `records`; `registry_view` drops the `old`
  and `new` keys from it as it does for `projects`; `registry_changes` covers it.
- [ ] `just test`; commit.

### Task 2: save for detached projects

Spec §4, §4.1.

- [ ] Tests (RED first):
  - `test_save_accepts_a_detached_checkout_and_records_its_records_repository`:
    `meta.json` has `checkout.records` (`repo`, `records_root`, `dirs` including the
    empty doc directories), `records_repos` with `root`, `head`, `branch` and `owned`
    (`ai/`, `tack/`, plus `<p>/` for each detached `--repo`), and `kind` on each repo;
  - `test_save_with_an_in_tree_checkout_and_a_detached_repo_owns_only_p`:
    `checkout.records` is `null` and `owned` is `["<p>/"]`;
  - `test_save_accepts_a_dirty_detached_repo_code_checkout` (the cutover never writes
    there) and `test_save_accepts_untracked_files_outside_the_owned_paths` (another
    project's draft, and an untracked file under `<p>/`);
  - `test_save_refuses_a_linked_checkout` and `test_save_refuses_a_linked_repo`: a
    linked project from `tasks init --prefix lnk --checkout <code>` run in an overlay
    directory; its registered root is the overlay, so the overlay passed as
    `--checkout` holds a copy of `tools/harness-links` (save checks the link tool
    before the kind);
  - `test_save_refuses_an_unreachable_repo`: an in-tree `--repo` with its
    `tasks/.config.toml` moved aside, which `tasks projects` reports as `reachable:
    false` with no `kind`. (A detached project with its records config gone makes
    `tasks projects` itself fail from its code root; `project_row` reports that
    through `run`'s `Stop`, which is not this test's message.)
  - refusals on the records repository, each asserting its message and that no
    snapshot was written: off `main`; a stash; a second worktree; a branch with commits
    `main` lacks; an untracked file under `ai/`; an ignored file under `ai/` (ignore
    rule in the records repository's `.git/info/exclude`); a tracked change under
    `<p>/`; a staged file of another project; `sync/records/tack` existing; a records
    directory not directly under the repository's top level (`mkdir
    sync/records/sub`, then `init --records sync/records/sub`, whose setup commit needs
    `--no-verify` because the hook refuses `sub/` without a config at its top); a
    records directory not named for its prefix (move `sync/records/<p>` to
    `sync/records/other` and edit `[records] <p>` in the sandbox registry's text to
    match, as `test_save_refuses_a_checkout_the_registry_does_not_map` edits the
    registry; the round-2 reviewer's probe showed the row, the hook and `tasks check`
    accept that layout); a records repository inside the checkout and one inside a
    `--repo` (each nested repository git-ignored in its outer one, so the clean check
    does not refuse first); a records directory whose repository's top level is the
    checkout itself (records kept in a git-ignored subdirectory of the checkout, not
    a repository of its own, so `git rev-parse --show-toplevel` from it answers the
    checkout and the clean check does not refuse first); the snapshot inside the
    records repository; a records directory outside any git repository (`git
    rev-parse` fails and `run` raises the `Stop`, asserted by its message).
- [ ] Implement in `save` and `preconditions`:
  - `project_row` keeps returning the row; a `project_kind(root, command)` helper
    refuses an unreachable row and a linked one with the spec's messages; the
    `project_prefix` "outside it" refusal goes;
  - a `records_repo(row)` helper returns the git top level of `row["records"]` and
    checks the parent and name contract;
  - collect and deduplicate records repositories with their owned paths (`<old>/` and
    `<new>/` only when the checkout is detached and its records live there); run the
    §4.1 checks on each: branch, stash, worktree and unmerged branches through the
    existing helpers (today they apply to the checkout only); `git status --porcelain
    --untracked-files=all --ignored -- <old>/`; `--untracked-files=no -- <p>/`; `git
    diff --cached --quiet`;
  - `preconditions`' porcelain loop (the only check it runs on `--repo` repositories)
    skips a detached `--repo`'s code checkout; `tasks check` still runs there;
  - write the new `meta.json` fields; `dirs` lists every directory under `<old>/`,
    relative to the records repository, sorted.
- [ ] Remove the two refusal tests and the old `detached()` helper.
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
    and a detached `--repo` sharing the records repository, with a dependency on a
    checkout task; save, apply, the printed commit (run as printed, through the
    fixture hook), retarget, link, verify; plus the same with an in-tree checkout and
    a detached `--repo`;
  - `test_verify_fails_while_the_records_repository_holds_the_uncommitted_rename`;
  - `test_verify_fails_while_the_old_records_directory_exists`;
  - `test_verify_fails_when_the_row_names_other_records` (after the full cutover,
    copy `sync/records/tack` elsewhere and edit `[records] tack` in the sandbox
    registry's text to name the copy, so the row still sits at the new root and
    `project_row` finds it; verify names the `records` mismatch);
  - `test_verify_fails_on_a_tracked_change_under_p`;
  - `test_retarget_repo_stops_on_a_deferred_record_commit` (a staged file of another
    project, staged after save; `tasks edit` exits 0 with a `commit_deferred:` warning
    in its stdout JSON; the retarget stops naming it).
- [ ] Modify `test_retarget_writes_each_task_once`'s fake as the global constraints
  say.
- [ ] Implement:
  - `apply`: the existing-directory check before `tasks rename`; `tasks init
    --prefix <new> --records <records_root> --force` for a detached checkout; print
    the commit line;
  - `retarget_dependencies` (the `--repo` path): after each `tasks edit`, parse its
    stdout as JSON (a parse failure is a `Stop`) and raise `Stop` on a warning
    starting `commit_deferred:` or `commit_failed:`, before the next edit runs.
    `write_rewrites` takes an optional per-edit `check(output)` that the `--repo` path
    passes and `retarget_forward` does not, so `--forward` keeps today's behaviour, as
    spec §4.3 says; the test asserts the second edit did not run;
  - `retarget --repo`: accept a detached snapshot repository (the refusal is gone with
    Task 2; the whole-cutover test asserts it);
  - `verify`: the row, absence and owned-path cleanliness checks of §4.4; `tasks
    check` in every snapshot project.
- [ ] `just test`; commit.

### Task 4: rollback restores the records repository's owned paths

Spec §4.5 steps 1–5, §4.6. Every behaviour of the walk, the leftover copies, the
restore and the commit is tested here, RED first: rollback of a detached box does not
work before this task.

- [ ] Tests (RED first), each comparing `fingerprint()` before save and after
  rollback, and asserting what must not be touched:
  - main cases: `test_detached_rollback_before_commit_restores_everything`;
    `…_after_commit_…`; `…_after_a_retarget_without_the_renames_commit`; `…_with_it`;
    `test_rollback_with_an_in_tree_checkout_and_a_detached_repo_restores_p` (after
    the commit and a retarget);
  - other projects: `test_detached_rollback_keeps_another_projects_commit_and_draft`
    (a third detached project outside the snapshot commits a record and leaves an
    untracked draft after save; both survive; rollback's commit holds only owned
    paths), and an untracked draft under `<p>/` survives in place;
  - `test_detached_rollback_removes_a_task_filed_in_p_since_save_and_patches_it`;
  - `test_detached_rollback_recreates_the_old_empty_doc_directories`;
  - `test_detached_rollback_leaves_a_detached_repos_code_checkout_alone` (a commit
    there after save survives);
  - `test_detached_rollback_stops_when_the_records_repository_changed_branch`, with
    nothing mutated;
  - the walk: `test_detached_rollback_after_rename_stopped_after_<stage>` for `files`,
    `config`, `records` and `registry` (`TASKS_RENAME_STOP_AFTER`, as
    `test_rollback_after_rename_stopped_midway` does) and after a partial apply
    (renamed, checkout not moved); `…_stops_on_a_foreign_file_under_new`,
    `…_under_old`, `…_on_an_ignored_file_under_new` (rule in `.git/info/exclude`) and
    `…_on_a_new_task_written_before_the_commit`, each naming the file with nothing
    mutated;
  - the copies: `test_detached_rollback_copies_a_note_written_before_the_commit`
    (`tasks note` on a renamed task after apply; the fixture hook refuses its record
    commit; the copy under `rollback-leftovers-1/` contains the note's text);
    `test_rollback_copies_in_tree_leftovers_into_the_snapshot` (in-tree box,
    `forward()`, rollback; `rollback-leftovers-1/checkout/tasks/tack-<hex>.md` holds
    the renamed bytes).
- [ ] Implement, in `rollback()`'s order:
  - checks: `check_branches` adds each `meta["records_repos"]` branch and drops
    detached `--repo` code checkouts; `validate_leftovers` and the final porcelain loop
    take their repositories from `meta` without detached `--repo` code checkouts;
    `validate_records_repos(meta)` walks the filesystem under `<old>/` and `<new>/`
    (ignored files included), skips any path in the index, the current HEAD or the
    saved head, maps the rest (id mapping under `<old>/`, id-or-identity under `<new>/`)
    to originals at the saved head, stops on anything else, and returns the leftovers;
  - after `move_back` and before the first reset or restore (this is what "before any
    mutation" means in spec step 2: `move_back` only renames the checkout back, so the
    in-tree leftovers are read at the moved-back path), `reset_all`'s pre-pass writes
    every patch: the existing ones and the records patches (`git diff --binary <head>
    -- <owned>`, label `records-<name>`), then copies every leftover (records and
    in-tree) into `rollback-leftovers-<n>/<label>/<path>`;
  - `resets` holds the checkout and in-tree `--repo` repositories only;
  - `restore_records(meta)` right after `reset_all`: `git restore --source=<head>
    --staged --worktree -- <owned paths the index or saved head holds>`; delete
    `<new>/` whole; delete the `<old>/` leftovers and the directories they emptied;
    recreate `dirs`;
  - `remove_leftovers`, `restore_kept`, `refresh_kept`, `restore_dir` as today;
  - `commit_records(meta)` right after `restore_dir`: when owned content differs from
    HEAD, `git commit -q -m "revert: roll back rename <old> -> <new>" -- <owned paths
    the index or current HEAD holds>`;
  - final checks: `<new>` absent, owned paths with no tracked change, `git diff
    --quiet <head> -- <owned>`, `tasks check` in every detached snapshot project.
- [ ] `just test`; commit.

### Task 5: the differing-file copy, retries, the second host and the docstring

Spec §4.5 (step 2's differing-file copy, concurrent writers), §4.7, §5.

- [ ] Tests:
  - `test_detached_rollback_copies_a_file_recreated_under_old_after_the_commit`
    (RED: other bytes at an `<old>/` path the saved head holds, written after the
    rename's commit; the copy lands under `rollback-leftovers-<n>/` and the saved blob
    is restored);
  - `test_detached_rollback_retry_converges_after_a_stop_at_the_commit` (**guard** on
    Task 4's two path sets and walk: after `commit_rename()`, the box's hook copy is
    made to fail, so the first attempt stops at `commit_records` with `<old>/` restored
    and staged and `<new>/` dropped from the index; the test asserts that exit status,
    message and state; the hook copy is restored; then a file is written at
    `tack/tasks/tack-<hex>.md`, a path only the current HEAD holds, and the retry exits
    0, the file's bytes land under `rollback-leftovers-<n>/` (RED for that part), and
    the fingerprint matches. Seen to fail against each of two breaks: the restore set
    including HEAD-only paths (the retry's `git restore -- tack/` matches nothing in its
    source or the index and fails), and the walk excluding only the current HEAD (the
    restored `ai/tasks/ai-<hex>.md` is walked, cannot be mapped under `<old>/`, and
    stops the retry));
  - `test_detached_rollback_retry_converges_after_an_index_lock` (**guard**: a
    planted `index.lock` stops `git restore` before it changes anything, leaving the
    checkout reset and the records repository untouched; the test asserts git's lock
    message and that state; the lock is removed and the retry converges. Seen to fail
    when `restore_records` does not raise on git's failure: the first attempt then
    goes on and its output lacks the lock message);
  - `test_detached_second_host_adopts_the_rename` (§4.7: `tasks rename ai tack
    --adopt` from the new root under a second registry; `[projects] tack` and
    `[records] tack` follow; the old id resolves; the first host's state is untouched;
    **guard** on tasks' behaviour, seen to fail if the adopt is skipped).
- [ ] Implement the differing-file copy in the pre-pass: every file under an owned
  path, walked on disk (including `<p>/`), that is not in the index and whose bytes
  differ from the saved head's blob at its path (absent counts as different), unless
  it is already a leftover.
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
