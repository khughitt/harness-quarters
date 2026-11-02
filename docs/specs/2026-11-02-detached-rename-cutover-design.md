# rename-cutover for detached projects — design

Task: hq-5300fd. Status: draft, revision 1 (2026-11-02).

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
absent, and re-points the registry. A sandbox run of this task's probe
(`files:probe-rename.sh`, installed `tasks` of 2026-11-02) shows the rest of what the
cutover meets:

- `tasks rename ai tack`, run in the detached code checkout, moves `<records>/ai/` to
  `<records>/tack/` and leaves the move uncommitted in the records repository:
  `ai/tasks/…` deleted, `tack/` untracked. The code checkout is untouched.
- After the checkout moves, `tasks init --prefix tack --records <records> --force`
  re-points both the config and the registry and warns that the config is not
  committed.
- `tasks resolve` answers the old id through the alias and the old root through the
  location history.

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
- In-tree behaviour is unchanged; every existing test passes unmodified except the two
  that pin today's refusal.

Non-goals:

- Linked projects. A linked checkout or `--repo` (an overlay directory) is refused by
  `kind`, which also settles hq-7255db finding 3.
- The second host's adoption. It stays a runbook step (`tasks rename <old> <new>
  --adopt`, then `tasks init --prefix <new> --records <records-root> --force` if the
  registry still names the old root); a sandbox test pins the sequence that works
  (§4.7).
- Committing. As today, the runbook commits between the cutover's steps; for a
  detached project that includes the records repository.

## 3. Approaches

1. **Path-scoped restore of the records repository (chosen).** Save the records
   repository's head and branch. On rollback, restore only the paths the cutover owns
   there to the saved head, remove the rename's leftovers, and commit the restoration
   with a pathspec. Other projects' commits since save survive.
2. **Reset the records repository whole, as `--repo` repositories are reset.**
   Simplest, and consistent with the in-tree model, but the records repository is
   shared by every detached project and each `tasks` write there commits
   automatically. A reset would discard (into a patch) every other project's record
   commit since save, across a window that lasts until the other host adopts. A guard
   that refuses when other projects committed would make rollback fail in the common
   case. Rejected.
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

### 4.1 save

- Each snapshot project's row must have `kind` `in-tree` or `detached`. A `linked` row
  is refused: `save: <root> is a linked project; this cutover renames and retargets
  only in-tree and detached projects`. The current "keeps its records … outside it"
  refusal goes.
- For each detached snapshot project, the records directory must be inside a git
  repository whose top level is neither the checkout, any `--repo`, nor inside one of
  them, and the snapshot must not lie inside it.
- When the checkout is detached: `<records-root>/<new>` must not exist, and the
  records directory's name must equal `--old` (records-home's contract; a mismatch is
  a config the cutover cannot reason about).
- Records repositories are collected and deduplicated (several detached projects
  share one). For each, the preconditions the checkout already meets, for the same
  reason (a stash, a second worktree or an unmerged branch could bring old-prefix
  records back after the rename): clean (`git status --porcelain
  --untracked-files=all` empty), on `main`, no stashes, one worktree, no branch with
  commits `main` lacks.
- `meta.json` gains:
  - `checkout.records`: `null` for in-tree; for detached `{"repo": <top level>,
    "records_root": <records root>}`.
  - `records_repos`: one entry per records repository: `record()`'s `root`, `head` and
    `branch`, plus `owned`, its sorted owned paths.

### 4.2 apply

- Before `tasks rename`, besides the existing checks: when the checkout is detached,
  refuse if `<records-root>/<new>` exists.
- After the move, re-point with `tasks init --prefix <new> --records <records-root>
  --force` for a detached checkout, and `tasks init --prefix <new> --force` for an
  in-tree one, as today.
- Print, for a detached checkout, that the records repository holds the uncommitted
  move and config rewrite, naming it, so the runbook commits it beside the checkout.

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
- Each records repository's owned paths are clean (`git status --porcelain -- <owned>`
  empty): the rename was committed, so the other host's sync carries a committed
  state.

`sample_task` already reads under the row's `records`.

### 4.5 rollback

The order below keeps every check before the first mutation, as today.

1. Checks (no writes): `check_environment`, the forward record, `guard`,
   `check_branches` (now including each records repository's branch),
   `validate_leftovers`, `validate_kept_destinations`, and the new
   `validate_records_repos`:
   - Untracked files under an owned path must be rename leftovers: each untracked
     `<new>/<rest>` maps to `<old>/<rest'>`, where `rest'` replaces the `<new>-` id
     prefix by `<old>-` in `tasks/<new>-<hex>.md` and `tasks/files/<new>-<hex>/…`, and
     leaves every other path (`tasks/.config.toml`, `docs/…`) as it is; the mapped
     original must exist at the saved head. Any other untracked file under an owned
     path stops rollback, naming it. Untracked files outside the owned paths belong to
     other projects and are left alone.
2. Mutations, in today's order, with the records repositories inserted after the
   reset of the checkout and `--repo` repositories:
   - For each records repository: write a patch of `git diff --binary <head> --
     <owned>` (the same never-overwrite naming as `save_reset_patch`, label
     `records-<name>`); then `git checkout <head> -- <owned that exist at head>`,
     `git rm -r -q --cached --ignore-unmatch` and removal from disk of every tracked
     path under an owned path that the saved head lacks, and deletion of the validated
     leftovers with their emptied directories (up to and including `<new>/`).
   - A detached `--repo`'s code checkout is recorded at save but not reset: the
     cutover never writes in it. An in-tree `--repo` is reset as today.
   - After `restore_dir` puts the registry and state back, commit each records
     repository whose owned paths differ from its head:
     `git commit -q -m "revert: roll back rename <old> -> <new>" -- <owned>`. The
     pathspec keeps any other project's staged change out. The commit comes after the
     registry restore so the records repository's pre-commit hook (`tasks check` for
     each staged prefix) sees the old prefix registered.
3. Final checks, as today, plus for each records repository: owned paths clean, and
   `git diff --quiet <head> -- <owned>` (the owned content equals the saved head).

The patch written in step 2 keeps notes or tasks added to the renamed project after
`apply` (they are discarded, as an in-tree rollback discards them today).

### 4.6 What is unchanged

`guard` (registry and state), `move_back`, kept files, the link tool, the claims
preconditions (keyed by prefix, so they cover detached projects already), and the
`retarget --forward` boundary. A rollback's in-tree reset of the renamed checkout
still runs for a detached checkout: the runbook may commit in it.

### 4.7 The second host

`tasks rename <old> <new> --adopt` "pairs the directory already renamed by sync"
(records-home §5.4); the config the sync delivers already names the new checkout, so
`tasks init --prefix <new> --records <records-root> --force` is a registry-only
re-point (relocation design §4.2) if `--adopt` leaves the registry's root at the old
path. A sandbox test runs the first host's cutover, then the second host's sequence,
and asserts the second registry maps `<new>` to the new root and `[records] <new>`,
that the old id resolves, and that the first host's state is untouched. The test
decides whether the `init` step is needed; the tool's docstring states the sequence.

## 5. Tests

Sandbox tests in `tools/test_rename_cutover.py`, extending the existing `detached()`
fixture (a records repository beside the code checkouts). Every test isolates git
config and the tasks registry as the existing `Sandbox` does.

- save: a detached checkout is accepted and `meta.json` records its records
  repository and owned paths; a linked checkout and a linked `--repo` are refused; a
  records repository that is dirty, off `main`, has a stash, a second worktree or an
  unmerged branch is refused; `<records-root>/<new>` existing is refused.
- The whole cutover for a detached checkout with a detached `--repo` sharing its
  records repository: save, apply, commit both, retarget, link, verify.
- verify fails while the records repository holds the uncommitted rename.
- rollback before commit, after commit, and after a retarget restores the records
  repository's owned paths to the saved head, removes `<new>/`, and keeps another
  project's record commit made after save (the case approach 2 would lose).
- rollback stops on an untracked non-leftover under `<new>/` and on an untracked file
  under `<old>/`, before any mutation; an untracked file outside the owned paths is
  left alone and does not stop it.
- rollback after a partial apply (rename done, checkout not moved).
- The second host's adoption (§4.7).
- The two tests that pin today's refusal are replaced by these.

Policy: `.tt.toml` is absent here, so `just test` is the suite route.

## 6. Follow-ups at landing

- hq-7255db: note that finding 3 (linked overlays) landed here.
- tasks-ea4cc5 (records-home amendment): note that detached renames through
  `rename-cutover` are supported, as hq-5300fd's own note asks.
