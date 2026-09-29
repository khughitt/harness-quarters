# Local layer: host and work state out of the tracked tree

Status: draft for review. Task: `tack-4cd688` (goal `tack-5b608f`: publish tack).

## 1. Problem

tack is about to become a public repository. The audit (`tack-8062ad`) found that
four kinds of content in the tracked tree are not configuration anyone else could use,
and some of it must not be public:

1. **Work harness configs.** `claude/settings.work.json` and `codex/config.work.toml`
   name the employer's tools (work plugins, work SaaS MCP servers) and list work
   checkouts as trusted projects.
2. **Codex project trust.** Codex appends a `[projects."<path>"]` table to
   `codex/config.toml` each time a directory is trusted. The list names every
   checkout on this host, including work checkouts and personal research directories.
3. **Codex command approvals.** Codex appends `prefix_rule(...)` lines to
   `codex/rules/default.rules` as commands are approved. They carry absolute paths to
   other checkouts and to caches.
4. **The generated projects block in `AGENTS.md`.** `ops-projects` renders every
   registered project, including the ones whose profile is `work`, with purposes that
   describe client work.

Items 2 and 3 are harness-written state, like the model picks the `harness-state`
filter already keeps out of the index. Item 1 is configuration, but only for the work
home on hosts that have it. Item 4 belongs to ops: tack only receives the block.

## 2. Goals and non-goals

Goals:

- After this change, none of the four kinds of content are tracked in tack, and a
  tree-wide grep for the work terms matches nothing.
- Every harness home on this host loads exactly what it loads today. The one exception
  is that sessions under a non-work profile no longer see work project prefixes. They
  have no use for them.
- A host that syncs the checkout through Dropbox needs no manual step beyond
  `just link --apply`.

Non-goals:

- Rewriting history. That is `tack-90bf74`, which runs after this change lands.
- Removing host paths that are ordinary configuration. The Codex
  `permissions.workspace-local` roots and the `ohai` MCP path, for example, are
  functional and not sensitive.
- Keeping version history of the work configs. Dropbox's file history covers them.

## 3. Design

### 3.1 The `local/` directory

Add a directory `local/` at the checkout root. `.gitignore` excludes it. Because the
checkout lives in Dropbox, the directory syncs to every host the way the rest of the
working tree does. It holds the files a harness home links to but the repository must
not publish:

    local/
      README.md                  what lives here and why (untracked, like the rest)
      claude/settings.work.json  moved from claude/
      codex/config.work.toml     moved from codex/
      codex/rules/               moved from codex/rules/ (the Codex-written approvals)

`codex/hooks.work.json` stays tracked: it names only the profile hook and the
refresh hook.

`links.toml` points the affected links into `local/`:

    [harness.claude-work.links]
    "settings.json" = "local/claude/settings.work.json"

    [harness.codex.links]
    "rules" = "local/codex/rules"

    [harness.codex-work.links]
    "config.toml" = "local/codex/config.work.toml"

**tack-link validates only the entries that apply.** Today `load()` checks that every
target exists before `plan()` skips the groups whose home is absent. With targets under
`local/`, that order would make a public clone, which has no `local/`, fail
`just link` outright, even for its required links and even with no work home. It also
breaks `test_real_manifest_validates_in_a_fresh_clone`. The change: `load()` keeps
the structural checks (links under links, homes as links), and target existence moves
to the entries `plan()` keeps. Those are required links, plus harness groups whose home
is a real directory. A missing target in an active group is still an error, and it
names the path. For a target under `local/`, it adds: "copy it from another host's
`local/`, or run `just setup` for the directories it creates". An inactive group is
reported as `skipped`, as it is today, and its targets are never checked.

**Bootstrap.** A new `just setup` recipe creates what the public tree needs on a
fresh clone:

- `local/codex/rules/` as an empty directory. Codex creates `default.rules` in it
  on the first approval, as it does in an empty rules directory today.
- The git configuration the README's Setup section lists now (`core.hooksPath`, the
  `harness-state` filter). This recipe replaces those manual steps.

It never creates the work configs. A host with a work home and no synced `local/`
fails at `just link` with the message above, and does not get a dangling link.
`just setup` is idempotent. On this host it is a no-op, apart from confirming the
git configuration.

**The branch never installs `local/`.** `local/` is ignored, so nothing under it
travels through git. The branch does `git rm --cached` on the moved files, and when it
merges into the main checkout, that becomes a deletion of the live files there. The
live copies in the main checkout are also newer than any copy in a worktree, because
the harnesses write them. So the rollout (§4) copies the main checkout's own live files
into the main checkout's `local/` before the merge, verifies them, and repoints the
links right after it. It runs with no harness session open that writes those files:
no work-home session and no Codex session in any home.

### 3.2 Codex project trust: filtered, not moved

Moving `codex/config.toml` into `local/` would take the personal Codex configuration,
which is worth publishing, along with the trust list. Instead, the `harness-state`
clean filter drops every `[projects."…"]` table from `codex/config*.toml`, header
through the line before the next header. This works the same way the filter already
drops `[tui.model_availability_nux]`. The working tree, and so the live file, keeps
the tables. The index never sees them.

The consequences match those of the existing filtered keys, and the README states
them the same way:

- A checkout of the file (a fresh clone, `git checkout -- codex/config.toml`) drops
  the trust list, and Codex asks again per directory.
- Git's size-only "modified" mark after Codex adds a trust entry is cleared by the
  existing Stop hook (`harness-state-refresh`). Its patterns already cover
  `codex/config*.toml`.

The branch changes the filter but never restages `codex/config.toml`. A branch commit
that dropped the tables would change the file's blob, and merging it would check the
trust-less blob out over the live file in the main checkout. The removal is committed
in the main checkout after the merge (§4), where the working tree stays as it is and
only the index changes. `git add -u` cannot do this: git decides "modified" from the
file's stat, so an unchanged file is never re-cleaned under the new filter.
`git add --renormalize -- codex/config.toml` re-runs the filter regardless.

### 3.3 The projects block: work projects leave the global block

This is a change in ops, filed as its own ops task. tack depends on it. The contract:

- `profiles.toml` gains a per-profile key `private = true`, set on `work`.
- `ops-projects` omits from the rendered block every project that lists a private
  profile. It also omits them from "Feedback owners", though no work project accepts
  feedback today.
- `ops-profile session` appends the projects under the session's private profile, in
  the block's own line format, to its output after the profile fragment:

      ### Projects under this profile

      - `<prefix>` — <name> — <purpose>

  A work-profile session therefore still resolves `rad` and `nrp`, and a personal
  session no longer sees them.
- `ops-projects check` keeps the pre-commit guard's meaning: the committed block
  equals what the generator renders.

tack's side is to regenerate the block (`just projects` in ops) once ops lands, and to
state in the README that private-profile projects are listed by the session hook, not
by `AGENTS.md`.

### 3.4 Guard against regressions

`.githooks/pre-commit` gains one check. It refuses a commit when a staged path is
under `local/`, which can only happen through `git add -f`. The only way back into the
tracked tree for a work config is then a deliberate edit to the hook.

A content grep for work terms in the hook would have to name those terms in the public
tree, so the hook does not do one. The one-time grep before the squash (`tack-90bf74`)
covers content.

## 4. Rollout on this host

Run from the main checkout, with no Codex session open in any home and no work-home
session open, on every host that shares the checkout. The checkout, its `.git`
included, is one Dropbox directory, so the merge changes every host's files at once.

1. **Copy the live files into `local/` before the merge.** In the main checkout:

       mkdir -p local/claude local/codex
       cp -a claude/settings.work.json local/claude/
       cp -a codex/config.work.toml local/codex/
       cp -a codex/rules local/codex/

   Then verify: `cmp` each copied file against its source, and
   `diff -r codex/rules local/codex/rules` is empty. `local/` is untracked in main
   until the merge brings the `.gitignore` line, and `git status` shows it as `??`
   in the meantime. That is expected.
2. **Merge** the branch (`--ff-only`). It deletes the three tracked originals from the
   working tree. Their copies in `local/` are now the only live copies.
3. **`just link --apply`**, then `just link-check` exits 0. `readlink -f` on
   `~/.claude-work/settings.json`, `~/.codex-work/config.toml` and `~/.codex/rules`
   resolves into `local/`.
4. **Drop the trust tables from the index**:

       git add --renormalize -- codex/config.toml
       git show :codex/config.toml | grep -c '^\[projects'    # prints 0
       grep -c '^\[projects' codex/config.toml                # unchanged, live file keeps them
       git commit -m "chore(codex): keep project trust out of the index" -- codex/config.toml

5. Start one Codex session and one work-home Claude session. Each must load its
   settings: the work plugins are listed, and Codex does not re-prompt for trust in a
   trusted checkout.
6. After the ops task lands: `just projects` in ops, then commit the regenerated block
   in tack.

Each other host whose harness homes link here runs `just link --apply` once, after
Dropbox has synced `local/` to it. Until then, its work homes and `~/.codex/rules`
links dangle, so those harnesses stay closed there. The README's "Renamed from ai"
section gets a sibling line saying so.

## 5. Testing

- `.githooks/test_harness_state_clean.py`: `[projects."…"]` tables are dropped from
  `codex/config.toml` and `codex/config.work.toml`. A table that follows keeps its
  header and keys. A file with no trust tables passes through unchanged.
- `.githooks/test_pre_commit.py`: a staged `local/…` path is refused, and a commit
  without one passes.
- `tools/test_tack_link.py`:
  - A links.toml entry whose target is under `local/` resolves like any other.
  - A missing target in an active group is an error naming the path and the remedy,
    and nothing is created.
  - A missing target in a skipped group (absent home) is not checked.
  - `test_real_manifest_validates_in_a_fresh_clone` still passes with Claude alone
    installed and no `local/`.
  - With a Codex home present, it passes after `just setup` and fails before it.
- `just setup` run twice in a fresh clone succeeds both times, and leaves
  `local/codex/rules/` plus the git configuration in place.
- ops tests for `private` profiles live with the ops task.
- Acceptance: `git ls-files local codex/rules` prints nothing, and
  `git show :codex/config.toml | grep -c '^\[projects'` prints 0. The work-term grep over
  the tree matches only the generated block until the ops task lands, and nothing after
  it.

## 6. Open questions

None blocking. If a second private layer appears (another employer, a client), it
belongs in `local/` next to the work files. The ops `private` key already covers its
projects.
