# Rename tack to harness quarters (hq) — design

Status: draft 2026-10-06, revised after review rounds 1 and 2, awaiting review. Task
`tack-8b7a28`, under `tack-dcb11a` and ops `ops-593133`.
Parent: ops `docs/specs/2026-10-03-agent-layer-split-design.md` §6 phase 3, §7.1.
Model: `docs/specs/2026-09-27-rename-to-tack-design.md`, whose procedure this reuses.
Sibling: `docs/specs/2026-10-06-residue-design.md`, which no longer waits for this (§7).

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
adopt the prefix, apply the links. No hook command names the checkout, so no Codex hook is
re-trusted.

Not in scope: rewriting history. Three kinds of text keep the old name:

- Dated specs, plans, notes and closed task records. They record what was true, and
  `tack-` and `ai-` ids keep resolving through the tasks aliases.
- Provenance statements ("extracted from tack") in lore's and flows' identity and README.
  They say where something came from, under the name it had.
- Fixtures that hold `tack` as data: ops's profile and session-start tests, flows'
  verdict tests and evaluation cases, the mods' pane test, lore's profile-hook test, and
  lore's instruction-assembly baselines, which are pinned by hash.

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
  %h/d/tack/tools/session-archive …` and a `Documentation=file://%h/d/tack/…` line.
- One link the manifest does not hold: `timers.target.wants/session-archive-capture.timer`
  under the user's systemd directory, made by `systemctl enable`, pointing at the unit
  file's absolute path in the checkout. On this host the capture timer is enabled and the
  prune timer is only linked.
- State keyed by the working directory: Claude Code's per-project store (session history
  and this project's memory files) and its folder-trust record, in each Claude home;
  Codex's *project* trust entry in `codex/config.toml` and the untracked
  `local/codex/trust.toml`; Crush's project list.

**Hook commands do not name it.** They call `~/.local/bin/harness-state-refresh`,
`~/d/lore/hooks/claude-profile` and ops's hooks. So the Codex hook trust, which hashes the
command, is untouched.

**In the repository.** `identity.toml`; the prefix in `tasks/.config.toml` and over 200
task files; `AGENTS.md`, `README.md` and one `links.toml` comment; `tools/tack-link`,
which carries its name in its usage line, its error prefixes and its staging suffix, with
its test and the `justfile`; `tools/rename-cutover` and its test; the two unit files and
the test that pins their `ExecStart`; and `agents/bin/session-episodes`, which maps a
session's working directory to a project through current roots only.

**In other projects.**

- **ops.** `identity-mirror.toml [tack]` (name, path, feedback), regenerated lists, and
  four lines of README prose. No ops tool looks the project up by name.
- **lore.** The assembled instructions (generated from ops), and prose in `README.md`,
  `AGENTS.md` and `skills/README.md` that says "tack's `links.toml`".
- **flows.** Prose in `README.md`, `AGENTS.md` and two tools' headers. And the flow trial,
  which depends on the prefix in three ways (§3.4).
- **obs.** More than comments (§3.5): its join refuses an id that resolves through an
  alias, its indexer maps a session to a project through current roots only, and its
  outcome measures skip a record whose task is no longer listed.
- **Task records in five projects** depend on or cite `tack-` ids in fields `tasks check`
  reads: ops (10), flows (2), lore (1), relay (1), tasks (1).
- **GitHub.** `origin` is `git@github.com:khughitt/tack.git`.

**Verified in a sandbox today**, with the config and state directories both isolated: a
second rename keeps the first alias (`aa` to `bb` to `cc` leaves `aa = "cc"` and
`bb = "cc"`, and all three forms of a task id resolve); `tasks rename` rewrites group
members; `tasks init --prefix … --force` after a move repoints the root and keeps the
aliases; `--adopt` works from a moved root; and `tasks rename` leaves a task id that
appears inside a note's text unchanged. Nothing on this host or on GitHub is named `hq`
or `harness-quarters`.

## 3. Approach

### 3.1 Phase 1: under the name `tack`, no rename

Each step is behaviour-preserving, lands on its own, and reverts on its own.

1. **The units stop naming the checkout.** The manifest gains
   `"~/.local/bin/session-archive" = "tools/session-archive"`; the tool already finds its
   package from its own real path. Both units call `%h/.local/bin/session-archive`, and
   the `Documentation=` line becomes a comment naming the spec by its path in the
   repository. This is the September design's move for the hook commands, applied to the
   two paths it missed. Host step, gated, per host: `just link --apply`, then
   `systemctl --user daemon-reload`, then one manual run of the capture unit to see it
   exit cleanly.
2. **The cutover tool is made general.** `tools/rename-cutover` already takes the old and
   new prefix and the new root. What it hardcodes, and what changes:
   - exactly two repositories, by the options `--ai` and `--ops` and the snapshot keys
     named for them. They become a list of repositories with the renamed one marked;
   - retargeting of retired ids in ops only. It becomes every repository in the list;
   - the claims precondition, written for ops. A `tasks dep` write prunes dead claims
     from the project it writes in, and rollback's guard compares every other project's
     claims file byte for byte, so the precondition becomes "no claim at all, live or
     dead" in every repository the tool retargets in;
   - one `apply` that retargets and applies the links together, ahead of the hand edits.
     It is split, so the links are applied at step 7, after the commits they depend on;
   - the name of the link tool, in six places. It becomes an argument.

   Its test, some 600 lines, runs the September case and this one, and gains a planted
   dead claim in a retargeted repository.
3. **The link tool gets a functional name.** `tools/tack-link` becomes
   `tools/harness-links`, with its test, the `justfile` recipes (`just link` and
   `just link-check` keep their names), the cutover tool's default, and the live prose.
   The only behaviour that changes is the name the tool prints in its usage and error
   lines and the suffix of its staging files; the suite is the proof.
4. **`session-episodes` resolves former roots and alias prefixes**, by the mechanism obs
   chooses (§3.5), so a session recorded under the old directory, and a task id written
   under the old prefix, still map to this project.
5. **Consumers prepare, without activating** (§3.3 to §3.5): each owning project holds a
   reviewed branch that the cutover merges.

### 3.2 Phase 2: the cutover

One sitting, run from a session started in ops: the checkout is moved from under any
session standing in it.

1. **Preconditions.** The tool checks and refuses on these:
   - `tasks claims` shows no live claim in any project, and no claim at all, live or
     dead, in ops, lore and flows, the repositories it retargets in. The cutover session
     holds none, so `tack-dcb11a` and `tack-8b7a28` are parked first;
   - the checkout has no local branch with commits that main lacks. A branch merged
     after the rename would bring `tasks/tack-<hex>.md` files back; `feat/residue` is
     such a branch today and merges first;
   - the checkout has one git worktree. Today it has three: the main one,
     `session-retention-job` (another session's, its tasks done) and this design's.
     Each feature worktree is merged, harvested with `tt-report`, unlocked and removed
     first, because each holds the checkout's absolute path;
   - clean trees in tack, ops, lore and flows; `just link-check` clean.

   The runbook checks these from task records, before it calls the tool: the flows and
   obs tasks (§3.4, §3.5) are done; phase 1's steps are done; the rehearsal (§4) is
   recorded as passed on `tack-8b7a28`.

   The user attests these, since no tool on this host can see them:
   - no harness session runs on this host except the cutover session;
   - the other host is idle in all four checkouts, because rollback resets them and the
     file sync would carry that under a running session;
   - the file sync is up to date on both hosts.

   Then every user timer that runs `tasks` or git across checkouts is stopped for the
   window, and started again after verification or rollback. Today that is four:
   `obs-index.timer`, `tt-latency.timer`, `work-link.timer` and
   `dropbox-ignore-flux.timer`. Any of them could act on a half-moved tree or write into
   a store the rollback guard compares. The runbook lists the timers afresh that day.
   Then the saved originals of §4 are taken.
2. `tasks rename tack hq` at the current root.
3. Move the checkout to `hq` and the worktree storage with it; rewrite the `.worktrees`
   link; from the moved checkout, `tasks init --prefix hq --force` points the registered
   root at the new path.
4. In hq: `identity.toml` (`name = "harness-quarters"`) and `just docs` to regenerate the
   identity regions the pre-commit hook checks; the guide and README; the `links.toml`
   comment; and the README's rename note rewritten for this rename. Codex's project
   trust gains an entry for the new path beside the old one, in both config files, by
   the README's trust procedure and not by rewriting a key; the old entry is forgotten
   after the other host adopts.
5. In ops: the mirror's table becomes `[hq]` with the new name and path; `just projects`
   regenerates the lists; the parent spec's status line and §7.1 record the name; the
   registry key in the residue's mirror test changes, if that test has landed; and every
   dependency on a retired `tack-` id that `tasks check` reports as `retired_prefix` is
   retargeted by the tool. One commit.
6. In lore and flows: the prepared branches merge, their own `retired_prefix` findings
   are retargeted, and lore's `assemble-instructions write` folds ops's regenerated
   fragment in.
7. `just link --apply` in hq repoints every link on this host; `systemctl --user
   daemon-reload`; `systemctl --user reenable session-archive-capture.timer`, which
   rewrites the one link the manifest does not hold; then `just link-check` again. On
   some systemd versions a re-enable of a linked unit also removes the unit's own link,
   which the manifest holds; the plan probes that offline, and the fallback is a second
   `just link --apply`. These systemd steps are the runbook's, not the tool's.
8. Verify (§5), then commit in hq.
9. **Forward-only, after verification:** every other registered project that reports
   `retired_prefix` for `tack` is retargeted, one commit each. Today that is relay and
   tasks. They are outside the snapshot, so they wait until there is nothing left to
   roll back on this host.
10. **Gated, outward-facing:** the GitHub repository is renamed and `origin` updated. The
    user does it or approves it at that moment; GitHub redirects the old URL, so this
    step can also wait.

**The other host**, after the sync carries the move, is where the September design said
it would be: the files say `hq` while its registry still maps `tack` to the old root.
Under its own quiescence, with its registry and state directories saved first and the
same three timers stopped, it runs: `tasks rename tack hq --adopt`, the storage move,
`work-link --ensure .worktrees`, `just link --apply`, `systemctl --user daemon-reload`,
and the timer re-enable for whichever archive timers its saved unit listing shows
enabled. Until then its sessions start without global instructions, skills or hooks; the
README's rename note says so.

### 3.3 Consumer migrations

| Consumer | What changes | When |
|---|---|---|
| ops mirror, generated lists, parent spec | `[tack]` to `[hq]`; `just projects`; the name recorded | cutover step 5 |
| ops README prose | four lines | same commit |
| lore prose and assembled instructions | "tack's `links.toml`" and the like; assembly | cutover step 6 |
| flows prose | `README.md`, `AGENTS.md`, two tool headers | cutover step 6 |
| **flows' trial** | §3.4 | decided and built in flows before the cutover |
| **obs** | §3.5 | decided and built in obs before the cutover |
| Task records that depend on `tack-` ids | retargeted where `tasks check` reports them | steps 5, 6 and 9 |
| The residue's fact consumers, if they have landed | any lookup of the registry key `tack` becomes `hq` (today: ops's mirror test) | cutover step 5 |
| Codex project trust | an entry for the new path added beside the old, so no prompt; the old one forgotten after the other host adopts | cutover step 4 |
| Claude Code folder trust | one prompt per Claude home on the first session at the new path; accepted, not edited by hand | after each host's step |
| Claude Code project memory | the memory directory copied to the store's new key, per home, per host. Session history stays under the old key, so resuming an old session by picker will not find it | after each host's step |

### 3.4 The flow trial

`flow-trial-1` enrols tasks from `tack` and `obs` until 2026-11-29 and reads out in 2027.
Nine task records here carry its notes. It depends on the prefix in three ways, and a
bare rename breaks each:

- **Enrolment is by prefix.** The trial lists `projects: [tack, obs]`. A task with the
  prefix `hq` is not in the list, so new work here would fall out of the trial without a
  word.
- **The arm is a hash of the full task id.** `arm_of` hashes the trial id with the unit's
  id, prefix included. Under a new prefix about half of the enrolled units would compute
  the other arm, and the tool's own check then stops with "contradicts the arm function".
  The two decisions recorded so far happen not to flip; the ones made between now and the
  cutover may.
- **Arm notes name their unit by id, and the rename does not touch note text.** A member
  note keeps saying `unit tack-…` inside a file now named `hq-…`. The lookup of that
  unit, and the census, then fail on a missing task. The global instructions tell every
  session to stop task work when the tool exits non-zero.

And the definition cannot simply be edited: the trial's design freezes the file once
enrolment opens, a change is a new trial under a new id, a new id reseeds every arm, and
two trials may not overlap on `obs`. A test in flows pins the project list.

This is flows' decision. A flows task, `flows-44890e`, filed with this draft and blocking the
cutover, chooses one of three and builds it:

1. **Make the trial's identity survive a rename.** The tools map a task id to the prefix
   the trial file lists, through the registry's aliases, everywhere the prefix is read.
   That is more places than the hash: choosing the trial for a task, where an `hq-` id
   today finds none and prints "not enrolled" with success; the comparison that decides
   whether to read the worktree's records or the main checkout's; every record lookup
   and parent walk, since the tracker returns `hq-` ids while notes name `tack-` units,
   including a child created after the rename under a root enrolled before it; the
   census filter, which on `hq-` ids returns an empty census with success; the stratum;
   and the text and target of the notes it writes. On a host whose registry lacks the
   alias the tool must fail, never hash the `hq-` id. The file, every unit and every arm
   stay exactly as they are. This design's recommendation to flows, since it changes
   nothing the trial measures.
2. **Halt the trial**, by its own halt rule, and accept what it has.
3. **Ask for the rename to wait** until enrolment closes or the trial reads out.

If flows chooses the third, this rename waits and nothing else does (§7). The rehearsal
exercises whatever flows builds, on copies, before the live run.

**One row per task, agreed with obs.** The trial's verdict joins its census to obs's
report by task id and silently skips a member with no row. If the census kept `tack-`
ids while obs reported `hq-` ids, a task open across the rename would be dropped, or the
two would be reported as disagreeing. So the flows task and the obs task settle together,
and each records, which id form and which project value a task carries in the census and
in the report: one of each, the same in both, for a task's whole life.

### 3.5 What obs must be able to do

Stated as requirements; the mechanism is obs's. An obs task, `obs-ff4e76`, filed with this
draft and blocking the cutover, delivers them or records a decision to drop history:

- An id that resolves through an alias is followed to its canonical id, not refused.
  That includes old ids inside recorded sessions: a mention of `tack-<hex>` and a write
  to `tasks/tack-<hex>.md` attribute to the same task as their `hq-` forms.
- A session recorded under a former root, or under a former root's worktree storage,
  maps to the project. Today the indexer reads only current roots, so every session
  recorded under the old directory would map to nothing when re-indexed.
- A task record that predates the rename stays in the outcome measures, which the
  trial's verdict consumes.
- The project is one project in every stored value. The task and session tables, the
  report's project stratum and the dashboard each derive a project from an id or a root;
  none may split this project into `tack` and `hq`.
- A task is one row across the rename, with the id form and project value agreed with
  flows (§3.4).
- The lookup of instruction projects by the prefix `ai`, left behind by the September
  rename, is corrected. That one is a defect today, whatever happens here.

`agents/bin/session-episodes` in this project has the same resolver, and it also drops
any task id whose prefix is not a current registry key, counting it unregistered. It
takes obs's mechanism for both, former roots and alias prefixes, in phase 1; the
session-logs skill already says the two change together.

## 4. Rollback and rehearsal

`tasks rename` cannot be reversed. Rollback restores saved originals and never replays
commands backwards, exactly as in September; this section states only what differs.

- **Four repositories, not two.** The saved commits, the reset in rollback, and the
  clean-tree checks cover tack, ops, lore and flows. relay and tasks are changed only
  after verification (step 9) and so never need restoring.
- **Quiescence is wider than it was.** More projects run sessions at once than in
  September, and three timers write or read across checkouts. The window, from the save
  until verification passes or rollback completes, has no other tasks writer on this
  host. The user picks it.
- **Saved** at the end of step 1: the four commits; copies of the tasks config and state
  directories; the `link-check` report, which by then includes the session-archive link;
  the `.worktrees` link's target; the target of the timer's enable link; the listing of
  which archive units are enabled; the untracked Codex trust file; and the set of links
  under the home directory that are already broken, for §5's comparison.
- **Rollback on this host** follows September's seven steps with these changes: step 3
  resets four repositories; step 4's leftover rule reads `tasks/hq-<hex>.md` beside
  `tasks/tack-<hex>.md`; and after the link apply come a `daemon-reload`, the timer
  re-enable, and a comparison of the enable link with its saved target.
- **Rollback is defined until the other host adopts.** After that the rename goes
  forward. Steps 9 and 10 are outside rollback and are therefore last.

**Rehearsal before the live run**, in a sandbox: copies of the four checkouts and of obs,
a scratch home for the links, and scratch `XDG_CONFIG_HOME` and `XDG_STATE_HOME` both. It
runs the cutover and the rollback from two points (before and after the commits), the
second-host adoption against a second pair of scratch directories, and the guard against
a planted foreign registry entry and a planted dead claim in a retargeted repository. It
never touches the live user manager: the timer's enable link is a fixture in the scratch
home, and the rehearsal checks link targets only.

It also proves the two consumers, together and not one at a time. The trial's whole
judging pipeline (census, obs's report, the verdict) runs on the copy before the rename
and after it, and the two runs must agree on the number of members with rows and on the
row of one task that is open across the rename. A planted unit whose two id forms hash
to different arms shows that the arm is computed from the listed prefix and not from the
new one; the live units cannot show that, since theirs happen to agree. And obs's
indexer, run over the copy, maps a session recorded under the old root to the project
with one project value.

It passes when each restored sandbox matches its saved originals byte for byte and
`tasks check` is clean in all four.

## 5. Verification

On each host, after its step:

- `just link-check` is clean. Over `find ~ -maxdepth 6 -type l`, a depth that reaches
  the timer's enable link: no link is broken that was not already broken in the set
  saved at step 1 (the host has some two thousand, in caches, before any of this), and
  no link's text or resolved path passes through the old directory.
- `tasks check` is clean in hq, ops, lore and flows, and after step 9 in relay and
  tasks. `tasks show tack-dcb11a` and `tasks show ai-4b1878` resolve through the aliases.
- A fresh session in each of the four homes shows its profile line, naming `[hq]` as the
  mirror table for a session started in this checkout. Codex sessions get one prompt
  each first, since Codex records hook text at the first model turn.
- Codex does not ask to re-trust a hook, and does not ask to trust the directory. Claude
  Code asks once per home to trust the folder; that prompt is expected.
- The archive units match the saved listing: the same timers enabled, and the capture
  unit exits cleanly when run by hand.
- If flows chose to keep the trial running: `trial-arm hq-dcb11a` prints
  `flow-trial-1: flow off (unit …)`, the arm recorded for that unit today, and the
  trial's check exits 0. "Not enrolled" is a failure. If flows halted the trial, the
  check is that the halt is recorded and the tool says so.
- obs's next index run completes; a named session recorded before the rename joins to
  its task, and that task appears in the outcome rows.
- The suites: hq's, ops's, lore's `test-fast`, flows' `test-fast`. If the residue's
  mirror test has landed, ops's run shows it ran and was not skipped.

## 6. Alternatives rejected

- **Rename the prefix and name, keep the directory.** Half the cost, but the disliked
  name stays in every path a person types and every link target, and the directory and
  registry key would disagree.
- **Rename the identity name and directory, keep the prefix.** It would spare the trial
  and obs entirely, since both key on the prefix and on roots that obs could alias. But
  every task id, the registry key and every `--project` flag would still say `tack`,
  which is most of where the name is read.
- **Wait for the trial before doing anything.** The cutover may have to wait, if flows
  says so (§3.4). Phase 1, the rehearsal and the consumers' work need not: none of them
  changes a name, and they are what makes the cutover a single sitting when its turn
  comes.
- **Keep `tack-link` and the units as they are and edit them at cutover.** It works once.
  Phase 1's steps mean the next rename, if there is one, touches no tool name and no
  unit.
- **A transitional link from the old directory.** A compatibility layer, and the file
  sync does not carry symlinks reliably.
- **Fold the rename into the residue's plan.** The rename has an irreversible step, a
  quiescence window, a rehearsal and two other projects' work in front of it; the rest
  of the residue has none of those.

## 7. Order, tasks and acceptance

The draft of this design had the rename run first in phase 3. It no longer does: the
cutover waits on work in flows and obs and on a quiet window, and the residue's other
work has no reason to wait with it. So the two proceed side by side. The residue lands
under the name `tack`; this design's phase 1 lands in the same period; the cutover runs
when its preconditions hold, and one line of the consumer table covers whatever of the
residue's has landed by then.

Tasks: `tack-8b7a28` for this design and its plan. The host steps are ops `ops-593133`,
which the plan unblocks. The flows task `flows-44890e` (§3.4) and the obs task `obs-ff4e76` (§3.5) are filed
with this draft, and `tack-8b7a28` depends on both.

Done when: both hosts have adopted and verified (§5); the four repositories are
committed and `tasks check` is clean in each, and in relay and tasks; the parent spec
records the name; the GitHub repository is renamed or its rename is recorded as deferred
by the user; and `ops-593133` is closed.
