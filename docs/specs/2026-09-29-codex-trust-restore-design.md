# Codex trust restore: keep project trust across checkouts that drop it

Status: draft for review. Task: `tack-de8d97`. Follows the local layer
(`docs/specs/2026-09-28-local-layer-design.md` §3.2).

## 1. Problem

The `harness-state` clean filter keeps Codex's `[projects."<path>"]` trust tables out of
the index. The live `codex/config.toml` in the main checkout (`~/.codex/config.toml`
links to it) still carries them, but any git command that writes a new blob of the file
over it drops the whole list. The checkout is shared through Dropbox, so every host
loses the list at the same moment, and Codex asks for trust again in every checkout.

The README documents a manual save and restore around a merge. It is easy to forget,
and it covers only merges. A probe (git 2.55.0, 2026-09-29) found which commands
overwrite the file and which of them run a hook:

| Command | Hook that runs |
|---|---|
| `git switch` / `git checkout <branch>` | `post-checkout`, read from the tree just checked out |
| the same, to a branch whose tree lacks the hook | none |
| `git checkout -- <path>`, `git restore <path>` | `post-checkout` (flag 0) |
| `git merge` (fast-forward included), `git pull` | `post-merge` |
| a merge that stops on a conflict in any file | none, and the `git commit` that concludes it runs none either |
| `git rebase`, `git pull --rebase` | `post-checkout`, `post-rewrite` |
| `git stash`, `git stash pop`, `git reset --hard` | none |
| a fresh clone | none (hooks are not configured until `just setup`) |

Git looks a hook up after the command has written the tree, in `core.hooksPath`
(`.githooks`, tracked). A switch to a branch that predates a hook removes the hook
before git looks for it. A switch back to a branch that has it runs it. A merge that
stops on a conflict has already written every cleanly merged file, `codex/config.toml`
included, and leaves no `index.lock` behind.

## 2. Goals and non-goals

Goals:

- The trust list survives every row of the table without a manual step, on this
  schedule:
  - Where a hook runs, the list is back before the command returns.
  - Where none runs (stash, reset, a conflicted merge, a fresh clone), it is back at
    the end of the next turn in either harness. A Codex session started in the gap
    asks for trust again.
  - While the main checkout is on a branch that predates this change, nothing restores
    the list. Both hooks resolve into the checked-out tree, the Stop hook through its
    `~/.local/bin` link included. The `post-checkout` of the switch back restores it.
    The main checkout normally stays on `main`, since work happens in worktrees.
- A trust table is protected once a turn end has captured it. Until then, a drop loses
  it. Codex adds a table when a session starts, so the window closes at that session's
  first turn end.
- The saved copy lives in `local/`, untracked, and Dropbox carries it between hosts
  along with the rest of `local/`.
- The README's manual save and restore goes away.

Non-goals:

- Trust in `local/codex/config.work.toml`. That file is untracked, and no git command
  overwrites it.
- Pruning entries automatically (§3.4).
- Writes from two hosts at once. Two hosts writing the shared file in the same instant
  give a Dropbox conflict copy. That is true today of any write to the file, and this
  design makes it no more likely.

## 3. Design

### 3.1 The sidecar

`local/codex/trust.toml` holds `[projects."<path>"]` tables only, each as the exact
text Codex wrote (header, keys, and the blank lines up to the next header). It is valid
TOML on its own. The README already names this path for the manual save, so a
hand-made copy from before this change is picked up as it is.

### 3.2 One tool, two operations

A new script, `.githooks/codex-trust`, owns the sidecar. Its operations work on the
checkout it lives in (like `harness-state-refresh`, which it serves) and on
`codex/config.toml` only:

- `capture` merges the live file's trust tables into the sidecar. It adds the tables
  the sidecar lacks, and replaces the text of those it already holds. A table the live
  file lacks stays in the sidecar. That is the point: a dropped list must never shrink
  the saved one. When the live value wins, a directory Codex marks untrusted is saved
  as untrusted.
- `restore` appends to the live file each sidecar table whose project path the live
  file lacks. It leaves the tables the live file has alone. It is idempotent: a second
  run appends nothing.
- `sync` is `capture` then `restore`, under one lock.

Tables are matched by project path, parsed with `tomllib`, not by header text.
Otherwise `[projects."/a"]` and `[ projects."/a" ]` would count as two tables.

Both operations run under an exclusive `flock` on `local/codex/trust.toml.lock`, which
serializes the Stop hooks of concurrent sessions and the git hooks on one host.
Without it, two restores racing would each append the same table, and a duplicate
table makes the file invalid TOML, so Codex would refuse to load it. Every write is
atomic (a temporary file, then a rename). A write to the live file goes through the
link's target, so the link survives.

Before writing, `restore` parses the result with `tomllib` and exits non-zero without
writing if it does not parse. It does the same when the sidecar itself does not parse.
A missing sidecar is the state before any capture, and both operations treat it as
empty. A missing `local/codex/` directory is an error that names `just setup`.

### 3.3 Where it runs

**Capture and restore at every turn end.** `harness-state-refresh` already runs from
Stop in both harnesses, on the main checkout, through the `~/.local/bin` link. It
calls `codex-trust sync` before its existing staging step, so a restored file is
restaged in the same run. The `index.lock` check guards both steps: while another git
command holds the index, the hook skips both, and the next Stop retries. This is the
only capture point. Codex adds a trust table at the start of a session, and that
session's first turn end saves it. A table added since the last turn end is not yet
saved, and a drop in that window loses it (§2). This is also the restore that covers
the rows with no hook: stash, reset, a fresh clone that has a sidecar, and a merge
stopped on a conflict. That merge holds no `index.lock`, so the hook runs while it is
still open. It restores the working file and restages it: git has already staged the
cleanly merged config at stage 0, so the resolution is unaffected.

**Restore after a git command.** New `post-checkout`, `post-merge` and `post-rewrite`
hooks in `.githooks/` run `codex-trust restore`. Each is a two-line shell wrapper that
ignores its arguments and stdin. They act only in the main checkout, where the
worktree's git dir equals the common git dir. A linked worktree's `codex/config.toml`
is not live, and restoring into it would only make the worktree dirty. The hooks
restore but never capture. When they run, the file has already been overwritten, and
the Stop hook has already saved what it held.

A hook location that survives branch switches was considered and rejected. It would
be a `core.hooksPath` outside the tracked tree, filled by `just setup` with copies,
or links into the tree, which a switch empties just the same. Copies drift from the
tracked scripts, and the Stop hook's link resolves into the tree either way. The
exposure is a main checkout parked on an old branch, and §2 names it.

Why the clean filter is not the capture point, as the task suggested: git runs the
filter for its own reasons (status, diff, add, and the index refresh after a merge),
in every worktree, and sometimes on content that is not the working file. A side
effect there fires on stale worktree copies and on the dropped file itself. It stays a
pure function.

### 3.4 Stale entries

Nothing prunes the sidecar automatically. A stale table (a deleted checkout, a `/tmp`
directory) costs one inert entry in Codex's list. A wrongly pruned one costs a trust
prompt on every host. And no host can judge staleness: the file is shared by hosts
whose directory trees differ, so "this path does not exist here" is not evidence.

To forget a directory, delete its table from both `local/codex/trust.toml` and
`codex/config.toml` before the next turn end. The README says so. A table deleted
from only one of the two comes back from the other at the next `sync`, by design.

### 3.5 Docs

- README: replace the manual save and restore paragraph with the automatic behaviour,
  the forget procedure, and one line on the no-hook rows (the list returns at the next
  turn end).
- The `harness-state-clean` docstring and the local-layer spec §3.2 say that trust
  dropped from the working file is restored from `local/codex/trust.toml`.

## 4. Testing

`.githooks/test_codex_trust.py`, in the style of `test_harness_state_refresh.py`
(temporary repositories built from copies of the real hook files):

- `capture` into a missing sidecar writes the live tables. Capture from a live file
  with fewer tables keeps the sidecar's extra tables. A live table's text replaces the
  saved one (untrusted wins).
- `restore` appends only the missing tables, twice in a row appends nothing, and the
  result parses. A malformed sidecar exits non-zero, and the live file is byte-for-byte
  unchanged.
- The live path is a symlink into the checkout: after `restore`, it is still a symlink.
- End to end in a temporary repository with `just setup`'s configuration: a merge, a
  branch switch, `git checkout -- codex/config.toml` and a rebase that each replace the
  file leave the trust tables in place. The same commands in a linked worktree leave
  its file untouched.
- A switch to a branch whose tree lacks the hooks leaves the tables dropped. The
  switch back restores them.
- A merge that stops on a conflict in another file leaves the tables dropped.
  `harness-state-refresh` run during the open merge restores them, and concluding the
  merge commits a config blob without trust tables.
- `harness-state-refresh` after a `git stash` / `stash pop` round trip restores the
  tables and leaves `git status` clean.
- Two `sync` processes started together leave exactly one copy of each table.

## 5. Rollout

Merging the branch changes no `codex/config.toml` blob, so the merge itself drops
nothing. The hooks take effect when the merge lands, because `core.hooksPath` and the
`~/.local/bin` link point into the main checkout. The sidecar does not exist yet, so
until the first capture a drop would lose the list with nothing to restore. Right
after the merge, before any other git command in the main checkout:

1. Run `.githooks/codex-trust capture` by hand.
2. Check that the `[projects.*]` headers in `local/codex/trust.toml` match those in
   `codex/config.toml`, and that the sidecar parses.

Only then run the destructive live check: `git checkout -- codex/config.toml` in the
main checkout, which must bring the list back. That checkout also drops
the model pick and Codex's bookkeeping, as any checkout of the file does (README), so
run it between sessions.
