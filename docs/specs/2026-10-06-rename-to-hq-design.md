# Rename tack to harness quarters (hq) — design

Status: draft 2026-10-06, awaiting review. Under `tack-dcb11a` and ops `ops-593133`.
Parent: ops `docs/specs/2026-10-03-agent-layer-split-design.md` §6 phase 3, §7.1.
Model: `docs/specs/2026-09-27-rename-to-tack-design.md`, whose procedure this reuses.
Sibling: `docs/specs/2026-10-06-residue-design.md`, which this precedes.

## 1. Goal

The project is renamed everywhere it is a live name. The user chose the name on
2026-10-06: "harness quarters".

| Where | Today | After |
|---|---|---|
| Identity name (`identity.toml`, the mirror, the projects list) | `tack` | `harness-quarters` |
| Task prefix and tasks registry key | `tack` (alias `ai`) | `hq` (aliases `ai`, `tack`) |
| Checkout directory, and its worktree storage | `tack` | `hq` |
| Link tool | `tools/tack-link` | `tools/harness-links` |
| GitHub repository | `khughitt/tack` | `khughitt/harness-quarters` |

After the rename every host converges with the commands the September rename established:
adopt the prefix, apply the links. Nothing a harness runs names the checkout, so no Codex
hook is re-trusted.

Not in scope: rewriting history. Dated specs, plans, notes and closed task records that
say `tack`, `~/d/tack` or `tack-link` stay as written: they record what was true, and
`tack-` and `ai-` ids keep resolving through the tasks aliases. Test fixtures that use
`tack` as sample data (ops's profile and session-start tests, flows' verdict tests, the
mods' pane test) are data, not references, and stay.

## 2. What names the project today (2026-10-06)

**Per host.**

- The tasks registry: `tack = "<sync root>/tack"`, `[aliases] ai = "tack"`, and the
  `agent-layer` group's member list.
- Every home link: `links.toml` targets resolve to absolute paths under the checkout, so
  each installed link holds the old directory. `just link --apply` repoints them.
- The worktree storage: `.worktrees -> ../../.dropbox-work/tack/.worktrees`, and the
  storage directory itself (`work-link`). Each worktree's admin file holds the checkout's
  absolute path.
- Two systemd user units, installed as links: `ExecStart=/usr/bin/python3
  %h/d/tack/tools/session-archive …` and a `Documentation=file://%h/d/tack/…` line. These
  are the only things a host runs that name the checkout.
- Claude Code's per-project store, keyed by the working directory: session history and
  this project's memory files, in each Claude home.

**Hook commands do not name it.** They call `~/.local/bin/harness-state-refresh`,
`~/d/lore/hooks/claude-profile` and ops's hooks. So the Codex hook trust, which hashes the
command, is untouched.

**In the repository.** `identity.toml`; the prefix in `tasks/.config.toml` and over 200 task
files; `AGENTS.md`, `README.md` and one `links.toml` comment; `tools/tack-link`, its test
and the `justfile`; `tools/rename-cutover` and its test, written for `ai` to `tack`; the
two unit files and the test that pins their `ExecStart`; and a Codex *project* trust
entry keyed by the checkout's absolute path, in `codex/config.toml` and in the untracked
`local/codex/trust.toml`.

**In other projects.**

- **ops.** `identity-mirror.toml [tack]` (name, path, feedback), regenerated lists, and
  four lines of README prose. No ops tool looks the project up by name any more.
- **lore.** The assembled instructions (the projects list and feedback owners, both
  generated from ops), and prose in `README.md`, `AGENTS.md`, `identity.toml` and
  `skills/README.md` that says "tack's `links.toml`".
- **flows.** Prose in `AGENTS.md`, and the live trial definition
  `evals/trials/flow-trial-1.md`, whose `projects: [tack, obs]` decides enrolment by
  prefix. Arm notes on task records name their unit by task id.
- **obs.** Comments only. Its join already resolves an alias prefix to the canonical one.
- **GitHub.** `origin` is `git@github.com:khughitt/tack.git`.

**Verified in a sandbox today:** a second rename keeps the first alias. After `aa` to
`bb` to `cc` the registry holds `aa = "cc"` and `bb = "cc"`, and all three forms of a
task id resolve.

## 3. Approach

### 3.1 Phase 1: under the name `tack`, no rename

Each step is behaviour-preserving, lands on its own, and reverts on its own.

1. **The units stop naming the checkout.** The manifest gains
   `"~/.local/bin/session-archive" = "tools/session-archive"`; the tool already finds its
   package from its own real path. Both units call `%h/.local/bin/session-archive`, and
   the `Documentation=` line becomes a comment naming the spec by its path in the
   repository. This is the September design's move for the hook commands, applied to the
   last two paths it missed. Host step, gated, per host: `just link --apply`, then
   `systemctl --user daemon-reload`, then one manual run of the capture unit to see it
   exit cleanly.
2. **The link tool gets a functional name.** `tools/tack-link` becomes
   `tools/harness-links`, with its test, the `justfile` recipes (`just link` and
   `just link-check` keep their names) and the live prose. No behaviour changes; the
   suite is the proof.
3. **The cutover tool is made general.** `tools/rename-cutover` takes the old and new
   prefix, name and root as arguments wherever it holds `ai` or `tack`, and learns the
   two repositories this rename adds to its snapshot and rollback (lore and flows, §4).
   Its tests run both the September case and this one. This design's plan removes it once
   the second host has adopted.
4. **Consumers prepare, without activating** (§3.3): each owning project holds a reviewed
   branch that the cutover merges.

### 3.2 Phase 2: the cutover

One sitting, run from a session started in ops: the checkout is moved from under any
session standing in it, this one included.

1. **Preconditions**, checked by the tool before any change, each a refusal:
   - no harness session runs on this host except the cutover session, and none runs in
     the checkout on the other host;
   - `tasks claims` shows no live claim in any project, and no claim at all on ops;
   - the checkout has one git worktree. Feature worktrees, this design's included, are
     merged and removed first, because each holds the checkout's absolute path;
   - clean trees in tack, ops, lore and flows; `just link-check` clean;
   - the file sync is up to date on both hosts;
   - phase 1 has landed on both hosts, and the rehearsal (§4) has passed.
   Then the saved originals of §4 are taken.
2. `tasks rename tack hq` at the current root.
3. Move the checkout to `hq` and the worktree storage with it; rewrite the `.worktrees`
   link; from the moved checkout, `tasks init --prefix hq --force` points the registered
   root at the new path.
4. In hq: `identity.toml` (`name = "harness-quarters"`), the guide and README, the
   `links.toml` comment, the Codex project-trust key in both config files, and the
   README's rename note rewritten for this rename.
5. In ops: the mirror's table becomes `[hq]` with the new name and path; `just projects`
   regenerates the lists; any dependency on a retired `tack-` id that `tasks check`
   reports as `retired_prefix` is retargeted by the tool, as in September. One commit.
6. In lore and flows: the prepared branches merge (§3.3), and lore's
   `assemble-instructions write` folds ops's regenerated fragment in.
7. `just link --apply` in hq repoints every link on this host; `systemctl --user
   daemon-reload`.
8. Verify (§5), then commit in hq.
9. **Gated, outward-facing:** the GitHub repository is renamed and `origin` updated. The
   user does it or approves it at that moment; GitHub redirects the old URL, so this step
   can also wait.

**The other host**, after the sync carries the move, is where the September design said
it would be: the files say `hq` while its registry still maps `tack` to the old root. It
runs, under its own quiescence: `tasks rename tack hq --adopt`, the storage move,
`work-link --ensure .worktrees`, `just link --apply`, `systemctl --user daemon-reload`.
Until then its sessions start without global instructions, skills or hooks; the README's
rename note says so.

### 3.3 Consumer migrations

| Consumer | What changes | When |
|---|---|---|
| ops mirror and generated lists | `[tack]` to `[hq]`; `just projects` | cutover step 5 |
| ops README prose | four lines | same commit |
| lore prose and assembled instructions | "tack's `links.toml`" and the like; assembly | cutover step 6 |
| flows prose | `AGENTS.md` | cutover step 6 |
| **flows' trial** | see below | decided in flows before the cutover; activated at step 6 |
| obs | nothing to change; verified after (§5) | after the cutover |
| Claude Code project memory | the memory directory copied to the store's new key, per home, per host | after each host's step |
| Codex project trust | the key rewritten in both files, so no prompt | cutover step 4 |

**The flow trial is the one consumer that needs a decision.** `flow-trial-1` enrols by
prefix, runs until 2027-01-11, and has units assigned under `tack-` ids. After the rename
a task here has the prefix `hq`, which the trial's list does not hold, so new tasks would
silently fall out of the trial, and the verdict tools would be asked to recount units
whose ids changed under them. Changing a preregistered trial's definition is flows'
call, not this project's. So flows gets a task, filed by the plan and blocking the
cutover, to decide and prepare: the amended project list with the amendment recorded,
how an arm note's unit id is matched after `tasks rename` (the rehearsal shows what the
rename does to ids inside note text), and a check that `trial-arm` returns the recorded
arm for an enrolled task under its new id. The cutover does not run until that branch
exists and the rehearsal has exercised it.

## 4. Rollback and rehearsal

`tasks rename` cannot be reversed. Rollback restores saved originals and never replays
commands backwards, exactly as in September; this section states only what differs.

- **Four repositories, not two.** The saved commits, the reset in rollback, and the
  clean-tree checks cover tack, ops, lore and flows.
- **Quiescence is wider than it was.** More projects run sessions at once than in
  September. The window, from the save until verification passes or rollback completes,
  has no other tasks writer on this host. The user picks it.
- **Saved** at the end of step 1: the four commits; copies of the tasks config and state
  directories; the `link-check` report; the `.worktrees` link's target; the two unit
  files' installed targets.
- **Rollback on this host** follows September's seven steps with these changes: step 3
  resets four repositories; step 4's leftover rule reads `tasks/hq-<hex>.md` beside
  `tasks/tack-<hex>.md`; and a `daemon-reload` follows the link apply.
- **Rollback is defined until the other host adopts.** After that the rename goes
  forward. The GitHub rename is outside rollback and is therefore last.

**Rehearsal before the live run**, in a sandbox: copies of the four checkouts, a scratch
home for the links, and scratch `XDG_CONFIG_HOME` and `XDG_STATE_HOME` both. It runs the
cutover and the rollback from two points (before and after the commits), the second-host
adoption against a second pair of scratch directories, and the guard against a planted
foreign registry entry. It also answers the two questions this rename adds: what `tasks
rename` does to a task id inside an arm note's text, and whether `trial-arm` returns the
recorded arm afterwards. It passes when each restored sandbox matches its saved originals
byte for byte and `tasks check` is clean in all four.

## 5. Verification

On each host, after its step:

- `just link-check` is clean, and no link under the homes resolves into a missing path or
  through the old directory.
- `tasks check` is clean in hq, ops, lore and flows. `tasks show tack-dcb11a` and
  `tasks show ai-4b1878` resolve through the aliases.
- A fresh session in each of the four homes shows its profile line, naming `[hq]` as the
  mirror table for a session started in this checkout. Codex sessions get one prompt
  each first, since Codex records hook text at the first model turn.
- Codex does not ask to re-trust a hook, and does not ask to trust the directory.
- Both session-archive units start and exit cleanly when run by hand, and the timers are
  listed.
- `trial-arm` on an enrolled task under its new id prints its recorded arm.
- obs's next index run completes, and a session recorded before the rename still joins
  to its task.
- The suites: hq's, ops's, lore's `test-fast`, flows' `test-fast`.

## 6. Alternatives rejected

- **Rename the prefix and name, keep the directory.** Half the cost, but the disliked
  name stays in every path a person types and every link target, and the directory and
  registry key would disagree.
- **Keep `tack-link` and the units as they are and edit them at cutover.** It works once.
  Phase 1's two steps mean the next rename, if there is one, touches no tool name and no
  unit.
- **A transitional link from the old directory.** A compatibility layer, and the file
  sync does not carry symlinks reliably.
- **Fold the rename into the residue's plan.** The rename has an irreversible step, a
  quiescence window and a rehearsal; the rest of the residue has none of those. Separate
  plans keep each one's gate honest.

## 7. Order, tasks and acceptance

The rename runs first in phase 3. The residue design's other work then starts in a fresh
worktree under the new name, so its new consumers look up `hq`.

Tasks: this design and its plan run under a child of `tack-dcb11a`, filed with this
draft. The host steps are ops `ops-593133`, which the plan unblocks. The plan files the
flows task (§3.3) and makes the cutover depend on it.

Done when: both hosts have adopted and verified (§5); the four repositories are
committed and `tasks check` is clean in each; the parent spec's status line and §7.1
record the name; the GitHub repository is renamed or its rename is recorded as deferred
by the user; and `ops-593133` is closed.
