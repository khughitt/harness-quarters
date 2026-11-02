# rename-cutover for detached projects — design

Task: hq-5300fd. Status: draft, revision 4 (2026-11-02).

Revision 4 (after spec review round 3, revise: Important 1, Minor 1): the restore
and the commit take separate path sets, since `git restore` matches only its source
and the index (§4.5 steps 3 and 4); an untracked file at a saved-head path that
differs from the saved blob is copied into the snapshot before the restore
overwrites it (§4.5 step 2).

Revision 3 (after spec review round 2, revise: Important 2, Minor 4): the restore
uses `git restore --source=<head> --staged --worktree`, which removes tracked files
the saved head lacks and overwrites uncommitted changes (§4.5 step 3); the walk
classifies only files absent from the index, the current HEAD and the saved head, so
a retry after a stopped restore converges (§4.5 step 1); what the leftover copy keeps,
the concurrent-writers paragraph, §4.2's commit-order reason and step 3's deletion
wording are corrected.

Revision 2 (after spec review round 1, revise: Critical 1, Important 5, Minor 7):
the guard reads `[records]` as the rename's own (§4.6); rollback's records commit
names only paths git knows (§4.5); leftovers are mapped in both the old and the new
directory, so a rename stopped midway rolls back (§4.5); `<new>/` is validated by a
walk that includes ignored files and removed whole, and `<old>/`'s directories are
recreated (§4.5); cleanliness is scoped to the owned paths and a detached `--repo`'s
code checkout leaves the branch, leftover, porcelain and reset sets (§4.1, §4.4,
§4.5); deleted leftovers are copied into the snapshot first, and the fixture runs
the records repository's real pre-commit hook (§4.5, §5); minors 1–7 folded in.

Amends the cutover tool described by `docs/specs/2026-10-06-rename-to-hq-design.md` §3.1
and implements the `rename-cutover` row of the tasks records-home design
(`tasks:docs/specs/2026-10-22-records-home-design.md` §4, with §5.4 for `tasks rename`).

## 1. Intent

`tools/rename-cutover` renames a project's prefix and moves its checkout, with a
snapshot that rollback restores until the other host adopts. hq-d05d5c made it refuse
any checkout or `--repo` whose records live outside it (a detached project), for two
reasons recorded in its ruling:

- rollback resets only the repositories it saves, and a detached project's records
  live in the records repository, which it does not save;
- after the checkout moved, `tasks init --force --records` could not re-point the
  detached config's `[checkout] path` (tasks-e9ce63).

tasks-e9ce63 has landed: from the moved checkout, `tasks init --prefix <new> --records
<records-root> --force` rewrites `[checkout] path` when the recorded checkout is
absent, and re-points the registry. Sandbox runs (this task's `files:probe-rename.sh`
and the round-1 reviewer's probes, installed `tasks` of 2026-11-02) show the rest of
what the cutover meets:

- `tasks rename ai tack`, run in the detached code checkout, renames the records
  inside `<records>/ai/` first (`ai/tasks/tack-<hex>.md`, `ai/tasks/files/tack-<hex>/`),
  then rewrites the config, then moves `<records>/ai/` to `<records>/tack/`, and moves
  the registry's `[records]` key. Everything stays uncommitted in the records
  repository. The code checkout is untouched.
- The moved directory carries the empty `docs/specs` and `docs/plans` that `init
  --records` created.
- After the checkout moves, `tasks init --prefix tack --records <records> --force`
  re-points both the config and the registry.
- `tasks resolve` answers the old id through the alias and the old root through the
  location history.
- The records repository's pre-commit hook refuses a staged `<prefix>/` whose index has
  no `<prefix>/tasks/.config.toml`, so any `tasks` write to the renamed project before
  the rename is committed fails its record commit and stays untracked.

With 23 of 37 registered projects detached, every repository the cutover would
retarget in is likely detached too, so support covers a detached checkout and detached
`--repo` repositories alike.

## 2. Goals and non-goals

Goals:

- `save`, `apply`, `retarget --repo`, `link`, `verify` and `rollback` work when the
  renamed checkout, any `--repo`, or both are detached.
- Rollback restores the records repository's part of the rename (the renamed
  project's records directory and every detached `--repo`'s records directory) and
  leaves every other project's records in that repository as they are.
- Nothing rollback deletes is lost: tracked changes go to a patch, untracked
  leftovers are copied into the snapshot.
- In-tree behaviour is unchanged, except that the in-tree leftovers are copied into
  the snapshot before deletion too; every existing test passes unmodified except the
  two that pin today's refusal.

Non-goals:

- Linked projects. A linked checkout or `--repo` (an overlay directory) is refused by
  `kind`, which also settles hq-7255db finding 3.
- The second host's adoption, which stays a runbook step (§4.7).
- Committing. As today, the runbook commits between the cutover's steps; for a
  detached project that includes the records repository, with the command `apply`
  prints.
- Rolling back while other sessions are active. The existing guard already stops
  rollback when another project's claims file changed since save; that holds for
  every approach below.

## 3. Approaches

1. **Path-scoped restore of the records repository (chosen).** Save the records
   repository's head and branch. On rollback, restore only the paths the cutover owns
   there to the saved head, remove the rename's leftovers, and commit the restoration
   with a pathspec. Other projects' commits since save survive.
2. **Reset the records repository whole, as `--repo` repositories are reset.**
   Simplest, and consistent with the in-tree model, but the records repository is
   shared by every detached project and each `tasks` write there commits
   automatically. A reset would discard (into a patch) every other project's record
   commit since save, across a window that lasts until the other host adopts; a guard
   that refuses when other projects committed would refuse on writes that do not touch
   a claim (notes, adds), which the claims guard does not catch. Rejected.
3. **Keep refusing detached projects.** Rejected: the records-home design expects the
   support, and most repositories are now detached, so the cutover could rename almost
   nothing.

## 4. Behaviour

Terms: for a snapshot project (the checkout or a `--repo`), its `tasks projects` row
gives `kind` and `records`. A detached project's **records repository** is the git
top level of its `records` directory; its **records root** is the parent of `records`
(the directory name equals the prefix, records-home §3.4). The **owned paths** of a
records repository are, relative to its top level, `<old>/` and `<new>/` when the
renamed checkout's records live there, and `<p>/` for each detached `--repo` with
prefix `p` whose records live there.

A detached `--repo` contributes its prefix and its records directory only: the
cutover never writes in its code checkout, so that checkout is not in the branch,
leftover, porcelain or reset sets. `tasks check` still runs in it at save, verify and
rollback.

### 4.1 save

- Each snapshot project's row must be reachable and have `kind` `in-tree` or
  `detached`. An unreachable row (no `kind`, records-home §5.2) is refused naming it;
  a `linked` row is refused: `save: <root> is a linked project; this cutover renames
  and retargets only in-tree and detached projects`. The current "keeps its records …
  outside it" refusal goes.
- For each detached snapshot project, the records directory must be inside a git
  repository whose top level is neither the checkout, any `--repo`, nor inside one of
  them, and the snapshot must not lie inside it.
- When the checkout is detached: `<records-root>/<new>` must not exist, and the
  records directory's name must equal `--old` (records-home's contract).
- Records repositories are collected and deduplicated (several detached projects
  share one). For each:
  - on `main`, no stashes, one worktree, no branch with commits `main` lacks: the
    checkout's preconditions, for the same reason (a stash, a second worktree or an
    unmerged branch could bring old-prefix records back after the rename);
  - `<old>/` clean, untracked and ignored files included (`git status --porcelain
    --untracked-files=all --ignored -- <old>/` empty), so that every file under it
    after the rename is the rename's;
  - each `<p>/` with no tracked change (`git status --porcelain
    --untracked-files=no -- <p>/` empty). Untracked files under `<p>/` and anywhere
    outside the owned paths (another session's draft) are allowed and left alone.
- `meta.json` gains:
  - `checkout.records`: `null` for in-tree; for detached `{"repo": <top level>,
    "records_root": <records root>, "dirs": [...]}`, where `dirs` lists every
    directory under `<old>/` relative to the records repository, empty ones included.
  - `records_repos`: one entry per records repository: `record()`'s `root`, `head` and
    `branch`, plus `owned`, its sorted owned paths.
  - each `repos` entry gains `kind`.

### 4.2 apply

- Before `tasks rename`, besides the existing checks: when the checkout is detached,
  refuse if `<records-root>/<new>` exists.
- After the move, re-point with `tasks init --prefix <new> --records <records-root>
  --force` for a detached checkout, and `tasks init --prefix <new> --force` for an
  in-tree one, as today.
- For a detached checkout, print the commit the runbook makes next, scoped to the
  rename's paths so another project's untracked draft is not swept in:
  `git -C <repo> add -A -- <old> <new> && git -C <repo> commit -m "…" -- <old> <new>`.
  The runbook commits it before `retarget --repo` so the records repository's history
  reads rename, then retarget; either order commits, since the printed command stages
  and commits in one line.

### 4.3 retarget

`retarget --repo <root>` accepts a detached snapshot repository: its writes are
`tasks edit` calls that commit under `<p>/` in a saved records repository, which
rollback restores. `--forward` is unchanged: it ends rollback before its first write,
whatever the kind of the project it writes in.

### 4.4 verify

Besides today's checks, for a detached checkout:

- The new prefix's `tasks projects` row has `kind` `detached`, `checkout` equal to
  the new root and `records` equal to `<records-root>/<new>`.
- `<records-root>/<old>` does not exist.
- In each records repository, `<new>/` has no tracked change and no untracked file,
  and each `<p>/` has no tracked change: the rename was committed, so the other host's
  sync carries a committed state.

`tasks check` runs in every snapshot project (detached `--repo` code checkouts
included). `sample_task` already reads under the row's `records`.

### 4.5 rollback

The order keeps every check before the first mutation, as today.

1. Checks (no writes): `check_environment`, the forward record, `guard`,
   `check_branches` (each records repository's branch added; detached `--repo` code
   checkouts removed), `validate_leftovers` (in-tree repositories only),
   `validate_kept_destinations`, and the new `validate_records_repos`. For each records
   repository, it walks the filesystem under `<old>/` and `<new>/`, ignored files
   included, and classifies every file that is in none of the index, the current
   HEAD and the saved head's tree. A file at one of those paths is an original the
   restore puts back, a tracked change the patch holds, or (step 2) an untracked file
   the snapshot keeps; leaving it out of the walk is what lets a retry pass after an
   earlier rollback restored and staged `<old>/` but stopped before its commit:
   - under `<new>/`: `<new>/<rest>` must map to an original `<old>/<rest'>` that
     exists at the saved head, where `rest'` is `rest` with the id mapping applied
     (`tasks/<new>-<hex>.md` to `tasks/<old>-<hex>.md`, `tasks/files/<new>-<hex>/…`
     to `tasks/files/<old>-<hex>/…`), or `rest` itself for every other path
     (`tasks/.config.toml`, `docs/…`);
   - under `<old>/`: only the id mapping applies, for a rename that stopped before it
     moved the directory (`<old>/tasks/<new>-<hex>.md` to `<old>/tasks/<old>-<hex>.md`,
     and attachments likewise);
   - any other file stops rollback, naming it. Untracked files under `<p>/` and
     outside the owned paths are not examined and are left alone.
2. Patches, before any mutation: `reset_all`'s pre-pass writes, besides each reset
   repository's patch, each records repository's `git diff --binary <head> --
   <owned>` (label `records-<name>`, same never-overwrite naming). The validated
   leftovers (records and in-tree) are copied into the snapshot under
   `rollback-leftovers-<n>/<repository label>/<path>`, also before any mutation. A
   note written to an existing task of the renamed project after `apply` and before
   the commit (refused by the hook, so untracked) is such a leftover, so it is kept
   here rather than lost. A new task filed there in that window has no original at
   the saved head, so step 1 stops rollback naming it, for the person to move aside.
   The same copy takes every file under an owned path that is in neither the index
   nor the current HEAD, sits at a path the saved head holds, and differs from the
   saved blob (something recreated under `<old>/` after the rename's commit): the
   restore overwrites it and the patch, a diff of tracked content, does not hold it.
3. Mutations, in today's order, with the records repositories inserted after the
   reset of the checkout and the in-tree `--repo` repositories:
   - `git restore --source=<head> --staged --worktree -- <restorable owned paths>`,
     where the restorable owned paths are those the index or the saved head holds:
     `restore` matches a pathspec only against its source and the index, and one it
     cannot match fails the command (a retry after the committed `<new>/` left the
     index is the case: only the current HEAD still holds it). `restore` works
     without overlay: it removes tracked files the saved head lacks (a task filed in
     `p` since save, the committed `<new>/`) and overwrites uncommitted changes; the
     patch holds both;
   - delete `<new>/` from disk whole: what remains in it is untracked, and step 1
     validated every such file;
   - delete the validated leftovers under `<old>/` and the directories they emptied;
   - recreate every directory in `checkout.records.dirs` that is missing, which
     restores `<old>/`'s empty `docs/specs` and `docs/plans`.
   Restoring `<p>/` returns it to the saved head, which discards all of project `p`'s
   record activity since save, not only the retarget; the patch holds it.
4. After `restore_dir` puts the registry and state back, commit each records
   repository whose owned content differs from HEAD, naming only the owned paths
   that the current HEAD or the index knows (`git ls-files` and `git ls-tree HEAD`; a
   set apart from step 3's, since the commit matches against HEAD and the index), as
   a pathspec git does not know fails the commit: `git commit -q -m "revert: roll back
   rename <old> -> <new>" -- <known owned paths>`. The pathspec keeps any other
   project's staged change out, and the commit comes after the registry restore so the
   records repository's pre-commit hook (`tasks check` for each staged prefix) sees
   the old prefix registered.
5. Final checks, as today, plus for each records repository: `<new>` absent; owned
   paths with no tracked change; `git diff --quiet <head> -- <owned>`; and `tasks
   check` in every detached snapshot project.

Concurrent writers: between the restore in step 3 (which stages) and the commit in
step 4, a `tasks` write in another project defers its record commit; that write stays
uncommitted until its project's next write or `tasks commit`, and does not affect
rollback. A git call of rollback's can meet another process's `index.lock`, which
stops rollback with git's message. A retry is the remedy and converges from any stop:
the checks pass again (the guard, the branches, and the walk, which skips files the
earlier restore put in the index), the patches take the next unused number, and the
restore and commit converge on the saved head.

### 4.6 What changes and what does not

Changed: `registry_view` adds `records` to `REGISTRY_TABLES`, dropping the `old` and
`new` keys as `projects` does, since `tasks rename` moves the `[records]` key with the
prefix. Unchanged: the rest of `guard` (registry and state), `move_back`, kept files,
the link tool, the claims preconditions (keyed by prefix, so they cover detached
projects already) and the `retarget --forward` boundary. A rollback's reset of the
renamed checkout still runs for a detached checkout: the runbook may commit in it.

### 4.7 The second host

`tasks rename <old> <new> --adopt`, run in the new root after the sync delivers the
moved checkout and the committed records repository, writes `[projects] <new>` = the
new root, `[records] <new>` and the former location (round-1 reviewer's probe); no
`init` step follows. Wide reads on that host succeed before the adopt. A sandbox test
runs the first host's cutover, then the second host's adopt, and asserts the second
registry maps `<new>` to the new root and `[records] <new>`, that the old id resolves,
and that the first host's state is untouched. The tool's docstring names the step.

## 5. Tests

Sandbox tests in `tools/test_rename_cutover.py`, extending the existing `detached()`
fixture (a records repository beside the code checkouts). The fixture installs a copy
of the records repository's pre-commit hook (`core.hooksPath`), so record commits in
the tests meet the refusal the live repository makes. Every test isolates git config
and the tasks registry as the existing `Sandbox` does.

- `registry_view` reads a moved `[records]` key as the rename's own and any other
  `[records]` change as foreign.
- save: a detached checkout is accepted and `meta.json` records its records
  repository, owned paths and directories; an unreachable row, a linked checkout and
  a linked `--repo` are refused; a records repository that is off `main`, has a stash,
  a second worktree or an unmerged branch is refused; an untracked or ignored file
  under `<old>/`, a tracked change under `<p>/`, and an existing `<records-root>/<new>`
  are refused; an untracked file under `<p>/` or outside the owned paths is accepted.
- The whole cutover for a detached checkout with a detached `--repo` sharing its
  records repository: save, apply, the commit `apply` prints, retarget, link, verify.
- verify fails while the records repository holds the uncommitted rename.
- rollback before commit, after commit, after a retarget without the rename's commit,
  and after a retarget with it: restores the owned paths to the saved head, removes
  `<new>/` whole, recreates `<old>/docs/{specs,plans}`, and keeps another project's
  record commit and untracked draft made after save.
- rollback after a rename stopped after each of its stages
  (`TASKS_RENAME_STOP_AFTER`: `files`, `config`, `records`, `registry`) and after a
  partial apply (rename done, checkout not moved).
- rollback copies a note written to the renamed project between `apply` and the
  commit (refused by the hook, so untracked) into the snapshot.
- rollback stops before any mutation on an untracked file under `<new>/` or `<old>/`
  that is not a leftover, and on an ignored file under `<new>/`.
- rollback after the rename's commit removes a task committed in `p` since save and
  keeps it in the patch.
- rollback retried after the rename's commit converges, from a stop at the commit
  (step 4) and from a stop inside step 3.
- The second host's adoption (§4.7).
- The two tests that pin today's refusal are replaced by these.

Policy: `.tt.toml` is absent here, so `just test` is the suite route.

## 6. Follow-ups at landing

- hq-7255db: note that findings 3 (linked overlays) and 5 (rows without the new
  fields; here, unreachable rows) landed here.
- tasks-ea4cc5 (records-home amendment): note that detached renames through
  `rename-cutover` are supported, as hq-5300fd's own note asks.
