# Rename ai to tack — design

Status: approved at d0c0ece (ai-4b1878, goal ai-5b608f); plan docs/plans/2026-09-27-rename-to-tack.md

## 1. Goal

The project is renamed from `ai` to `tack` everywhere it is a live name: the checkout
directory, the task prefix, every harness home's links, the hook commands, and ops's view
of it. After the rename every host that uses the checkout converges with one command, and a
future rename or a new host needs no hand-made links.

Not in scope: the GitHub repository (ai-688cda), the sensitivity audit (ai-8062ad), and
rewriting history. Dated specs, plans and notes that say `ai` or `~/d/ai` stay as written:
they record what was true, and `ai-` ids keep resolving through the tasks alias.

## 2. What names the project today

Per host (this machine, 2026-09-27; other hosts sync the checkout through Dropbox and have
their own hand-made links):

- 20 symlinks into the checkout, made by hand, recorded nowhere: `~/.agents`;
  `~/.claude/{CLAUDE.md,settings.json,agents,commands,plans}`,
  `~/.claude/skills/{flow,session-logs}`; `~/.claude-work/{CLAUDE.md,settings.json,
  statusline-command.sh}`; `~/.codex/{AGENTS.md,config.toml,hooks.json,rules}`;
  `~/.codex-work/{AGENTS.md,config.toml,hooks.json}`; `~/.config/AGENTS.md`;
  `~/.config/opencode.local/AGENTS.md`. All but one go through `~/d/ai`;
  `~/.codex-work/config.toml` uses the absolute Dropbox path.
- The tasks registry (`~/.config/tasks/projects.toml`: `ai = "<Dropbox>/ai"`), per host.
- The worktree storage `.worktrees -> ../../.dropbox-work/ai/.worktrees`, per host
  (`work-link`).
- Codex hook trust: `[hooks.state."<home>/hooks.json:<event>:<i>:<j>"] trusted_hash` in
  `codex/config*.toml`, keyed by the hooks file and position; the hash covers the command,
  so changing a command string means re-trusting it.

In the repository: `identity.toml` (`name = "ai"`), the task prefix in
`tasks/.config.toml` and every `tasks/ai-*.md`, the generated project lists in
`AGENTS.md`, the hook commands `~/d/ai/.githooks/harness-state-refresh` in
`claude/settings*.json` and `codex/hooks*.json`, and prose in the flow and session-logs
skills ("the `ai` checkout").

In ops: `identity-mirror.toml [ai]`; `bin/ops-projects` finds the file its project list is
written into by `TARGET_PREFIX = "ai"`; `bin/ops-profile` finds profile fragments at
`reg["ai"]`. Both read the registry's `[projects]` table directly, so the tasks alias does
not reach them. Their tests use `ai` only as a fixture name.

## 3. Approach: make the links declarative, then rename

**Phase 1 — under the name `ai`, no rename.**

1. `links.toml` at the checkout root lists every home link as
   `"<link path>" = "<path inside the checkout>"` in two kinds of table:
   - **`[required]`** — links installed on every host whose parent is always present:
     `~/.agents`, `~/.config/AGENTS.md`, `~/.local/bin/harness-state-refresh`. A missing
     parent directory (`~/.local/bin`) is created.
   - **`[harness.<name>]`** with `home = "<dir>"` — the links inside one harness's home
     (`~/.claude`, `~/.claude-work`, `~/.codex`, `~/.codex-work`,
     `~/.config/opencode.local`). The group applies only when `home` is a real directory
     on the host; otherwise it is reported `skipped (<home> absent)` once. A harness home is
     never itself a managed link, so the check cannot be defeated by a dangling link.

   The manifest is validated before anything is read from disk: no entry's path may lie
   under another entry's path (so no entry is reached through a managed link such as
   `~/.agents`), and every target must exist in the checkout.
2. `tools/tack-link` (run as `just link`) reports one line per applicable entry:
   `ok`, `create`, `repoint (was <target>)` — including a dangling link, such as
   `~/.agents` after the checkout has moved — or `refuse (<why>)`. It writes only with
   `--apply`, and only when no entry is `refuse`. It refuses outright when run from a
   worktree (links must never resolve into one), and refuses an entry whose path holds a
   real file or directory rather than a link (never overwrite data). Targets are absolute
   paths under the checkout root as `git rev-parse --show-toplevel` reports it from the
   script's own location. `just link-check` exits non-zero on any drift, for a host's
   routine check. On a new host, `just link --apply` installs the required links and the
   groups of whichever harnesses are installed.
3. Hook commands stop naming the checkout: the manifest links
   `~/.local/bin/harness-state-refresh` to `.githooks/harness-state-refresh`, and the four
   hook files call `~/.local/bin/harness-state-refresh`. The script already resolves its
   checkout from its own real path. The command string then survives any rename, so Codex
   trust is re-granted once, now, and never again for this reason.
4. `just link --apply` runs on this host (expected: every entry `ok` except the
   `~/.codex-work/config.toml` repoint to the `~/d` form and the new `~/.local/bin` link),
   then on each other host after Dropbox syncs it. Any `refuse` is resolved by hand before
   phase 2.

Phase 1 is safe to land and to revert on its own: it changes no name.

**Phase 2 — the cutover**, one sitting, run from a session in ops (the ai checkout is
moved from under any session standing in it):

1. Preconditions, checked by the runbook before any change: the tasks capability of
   section 3a (tasks-7f1596) has landed and passed the rehearsal of section 4; no harness session running
   in the checkout; `tasks` has no live claim in `ai`; one git worktree; clean trees in ai
   and ops; `just link-check` clean. Then the saved originals of section 4 are taken.
2. `tasks rename ai tack` at the current root, while the registry still points at it.
3. Move the checkout `<Dropbox>/ai` → `<Dropbox>/tack`, and the worktree storage
   `.dropbox-work/ai` → `.dropbox-work/tack` with the `.worktrees` link rewritten; then,
   from the moved checkout, `tasks init --prefix tack --force` points the registered root
   at the new path under the registry lock, keeping the `ai → tack` alias (verified in a
   sandbox 2026-09-27: old ids resolve afterwards).
4. In tack: `identity.toml` name, skill prose that names the checkout, README.
5. In ops: `identity-mirror.toml [tack]`, `TARGET_PREFIX = "tack"`, `reg["tack"]` in
   ops-profile; `just projects` regenerates the project lists (including `AGENTS.md` in
   tack). An ops task that depends on a retired `ai-` id through `tasks dep` is also
   retargeted here: `tasks check` in ops reports each as `retired_prefix`, and the
   cutover tool runs `tasks dep --rm <old> --on <new>` for each finding so `tasks check`
   comes back clean; those rewrites ride in the one ops commit alongside the rest of
   this step.
6. `just link --apply` in tack repoints every link on this host.
7. Verify (section 5), then commit in tack.

**Other hosts**, after Dropbox syncs the move, are in a state the primary never passes
through: the synced files already say `tack` while the host's registry still maps `ai` to
the old root, and replaying `tasks rename ai tack` refuses it. Each host runs the tasks
capability's second-host migration (section 3a), saving its registry and state directory
first, then `just link --apply` and `work-link --ensure .worktrees`. Until a host does
this, its harness sessions start without global instructions, skills or hooks; the
README's rename note says so, and the user runs it on each host at their next login.

### 3a. The tasks capability the cutover depends on

Owned by the tasks project (tasks-7f1596); this spec states the requirement, not the
CLI. Relocating a root on the primary is already supported (`tasks init --prefix <p>
--force`, step 3). What is missing is one registry migration, under the registry lock and
keeping the registry's invariants:

- **Adopt a rename made elsewhere:** the checkout at a (possibly moved) root already
  carries a new prefix `new`, and this host's registry maps `old` to it; the migration
  makes `new` the live key at the new root, records `old` as its alias, and carries this
  host's state-directory records keyed by `old` (claims, parks) — without touching the
  synced task files.

It is verified by the tasks project in sandboxes, and by this project's rehearsal
(section 4).

## 4. Rollback and rehearsal

`tasks rename` cannot be reversed: after `ai → tack`, `tasks rename tack ai` refuses
because `ai` is taken as an alias. Rollback therefore restores saved originals, never
replays commands backwards.

**Quiescence.** The tasks registry and state directory are shared by every project on
the host, so the whole window — from the save below until verification passes or
rollback completes — has no other tasks writer: no harness session runs on the host other
than the cutover session, `tasks claims` shows no live claim in any project, and the
cutover session holds none. Restoring a partial registry entry under the lock is rejected:
no tasks command does it, and a hand-written one would bypass the lock. Save also refuses
any claim on ops, live or dead: a `tasks` write (such as apply's own retarget below)
prunes dead claims from a project's own claims store as a side effect, so a dead ops claim
present at save would be silently dropped by apply and the guard would then stop on a
change the cutover itself made.

**Saved at the end of phase 2 step 1:**

- the pre-cutover commits of ai and ops (clean trees are a precondition, so these are the
  whole tracked state);
- a copy of `$XDG_CONFIG_HOME/tasks/` (registry and aliases) and of
  `$XDG_STATE_HOME/tasks/` (claims, parks, rename inventories);
- the link report of `just link-check`, and the `.worktrees` link's target as
  `readlink` prints it (the link is ignored by git, so no reset restores it).

**Rollback on this host**, in order; each step stops the rollback when its check fails,
leaving the state for a person:

1. Guard the snapshot: diff the live tasks config and state directories against the
   copies. Every difference must belong to `ai` or `tack` (the registry key, its alias,
   records keyed by either). Any other difference means a writer ran despite quiescence:
   stop. A claims file is exempted from this only when it is empty live and its saved
   copy is absent or also empty — an empty claims file records no claim, so restoring
   over it loses nothing; a non-empty foreign claims file still stops the guard.
2. Move the checkout and the worktree storage back; rewrite the `.worktrees` link to the
   saved target.
3. `git reset --hard` ai and ops to the saved commits.
4. Remove the rename's untracked leftovers: `git status --porcelain` in ai may list only
   untracked `tasks/tack-<hex>.md`, and each is removed only after `tasks/ai-<hex>.md` with
   the same hex exists in the restored tree. Any other untracked or modified path: stop.
5. Restore both tasks directories from the copies.
6. `just link --apply` from the restored checkout; its report must equal the saved one.
7. `tasks check` in ai and ops is clean and `git status` in both is empty.

A second host that has migrated restores its own saved registry and state the same way,
under its own quiescence. Rollback is defined until the first host other than this one
migrates; after that the rename goes forward.

**Rehearsal before the live run.** The plan's first cutover step runs phase 2 and the
rollback in a sandbox: a copy of the ai and ops checkouts, a scratch `HOME` for the
links, and temporary **`XDG_CONFIG_HOME` and `XDG_STATE_HOME` both** — a probe with only
a scratch config still writes claims, parks and rename inventories into the live state
directory, and has been seen to move another checkout's parked task. Rollback is
rehearsed twice, from two points: after step 6 **before the tack commit**, when the
`tack-*.md` files are still untracked, and after the tack and ops commits. The rehearsal
also runs the second-host adoption against a second pair of scratch directories over the
same copy, and step 1's guard against a planted foreign registry entry. It passes when
each restored sandbox matches the saved originals byte for byte (registry, state
directory, tree hashes, link targets, the `.worktrees` link) and `tasks check` is clean.
Every probe in the plan uses the same isolation.

## 5. Verification

- `just link-check` clean on this host; `find ~ -maxdepth 6 -type l` finds no link that
  resolves into a missing path or names `ai`.
- `tasks check` clean in tack and ops; `tasks show ai-4b1878` resolves through the alias.
- ops tests pass; `ops-profile session` in tack prints the personal profile.
- A fresh Claude Code session and a fresh Codex session in tack load `AGENTS.md`, list the
  flow and session-logs skills, and run the Stop hooks (the refresh clears a size-only mark,
  as in ai-fb0e2a).
- Tests for `tools/tack-link` over a scratch home: each state (`ok`, `create`, `repoint`,
  `refuse` on a real file, `skipped` for an absent harness home, refusal from a worktree);
  a dangling `~/.agents` repointed and not skipped; a new host with no links getting the
  required links and only its installed harnesses' groups; manifest validation refusing a
  nested entry; and `--apply` converging a drifted home.
- The rehearsal of section 4 passes, including the second-host migration.

## 6. Alternatives rejected

- **A transitional `ai -> tack` link** in Dropbox to bridge hosts that have not re-linked.
  It is a compatibility layer, and Dropbox does not sync symlinks reliably across hosts.
- **Rename first, relink by hand** on each host: twenty links per host with no record of
  what they should be, repeated for every host and every future rename.
- **ops finds the project by a role** (`identity.toml [agents] scope = "global"`) instead
  of a prefix. Better long-term, but a larger ops change than a rename needs; a follow-up
  idea if the name changes again.
