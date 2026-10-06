# The residue: name, capability facts, surface audit, archive review — design

Task: `tack-dcb11a`, under ops `ops-cb9749`. Status: draft 2026-10-06, awaiting review.
Parent design: ops `docs/specs/2026-10-03-agent-layer-split-design.md` §4.1 (harness
support keeps), §5.3 (capability facts), §6 phase 3, §7.1 (naming gate), §9 (acceptance).

## 1. Decision and scope

Phase 3 finishes the split in the repository that stayed. Flows and lore have left; what
remains is harness support: homes, declared links, settings, state hygiene, the session
archive, mods. This design settles five things:

1. **The name.** Open. The draft recommended keeping `tack`; the user rejected that on
   2026-10-06 and is choosing a new name (§3). Every other section stands whichever name
   is chosen, and the rename gets its own spec.
2. **Capability facts.** A tracked fact file with typed values and separate evidence, one
   tool that validates and prints it, and the first three facts carried out of ops
   `hooks/claim-guard` (§4).
3. **The agent surface.** An audit of what is installed against what is declared, on both
   hosts, and the three gaps it found closed (§5).
4. **Old material.** A recorded disposition for every item under `archive/`, `doc/ref/`
   and `claude/archive/` (§6).
5. **The front door.** tack's feedback scope, guide and identity say what the residue is
   (§7).

Not in this design: moving the claim rule or switching `claim-guard` to read the facts
(tasks `tasks-56b450`, by the parent's §6); OpenCode's skills link (`tack-915ef2`); any
change to `tack-link`'s behaviour; a staleness signal for facts (§4.6, filed as an idea).

## 2. Evidence from the tree (2026-10-06)

- **The name was changed nine days ago.** `ai` became `tack` on 2026-09-27
  (`docs/specs/2026-09-27-rename-to-tack-design.md`): an irreversible `tasks rename`, a
  reserved alias, an adoption step on the second host, and a one-off tool,
  `tools/rename-cutover`, with its test still in the suite. `identity.toml` already
  describes the residue: "Harness homes, declared links, settings, and session-state
  hygiene".
- **The facts are three constants in a policy.** ops `hooks/claim-guard` holds
  `CHILD_WAKES = {"claude-code": True, "codex": False}` (probed 2026-09-24 on Claude Code
  2.1.282 and Codex 0.156.1, `tack-00ccb6`), `WAKING = ("shell", "subagent")` (the child
  kinds that probe covered) and `IN_FLIGHT = ("running", "pending")` (Claude Code's Stop
  input statuses, probed 2026-09-29 on 2.1.284, `ops-ed76fe`; the probe showed `running`,
  and `pending` comes from the input's schema). Their evidence lives in code comments.
  `agents/bin/wake-judge` here is the tool that judged the wake probe.
- **Relay keeps no store of its evidence records.** Its installer takes one as
  `--evidence FILE` and records only the harness and version in the installation artifact.
  Nothing on either host holds the live record at a stable path.
- **The surface is converged, with three gaps.** `just link-check` passes. Every entry
  under `~/.agents`, `~/.agents/bin` and `~/.agents/skills` is declared. Outside that:
  `~/.claude/skills/tasks` is a link into the tasks checkout that no line declares;
  `~/.codex/skills/vercel-react-best-practices` and `~/.codex/skills/web-design-guidelines`
  are relative links to `~/.agents/skills/` entries that no longer exist; and the comment
  above the aggregate entries in `links.toml` still says the surface "stays in tack until
  the owner of each entry moves", which has happened. Harness-owned real directories
  (`.system`, `synced`, `.trash`) sit beside the links and are not ours.
- **Old material, three places.** `archive/` is untracked (the user's global ignore
  excludes `/archive`): 24 files, the newest from 2026-08. `doc/ref/` is tracked: two
  notes. `claude/archive/` is tracked: six retired agent definitions and ten retired
  commands.
- **The feedback scope is stale.** tack's scope still opens with "Global agent instruction
  delivery", written when the instruction file lived here.

## 3. The name

**Superseded 2026-10-06.** The user rejected keeping `tack` and is choosing a new name.
This section is rewritten when the name is chosen; the text below is the draft's
recommendation, kept until then so the review history reads straight. The rename then
runs first in this phase, under its own spec, so that the new consumers in §4 are
written against the final registry key.

**Draft recommendation, rejected: the residue keeps the name `tack` and the prefix `tack`.**

- The name already fits. Tack is the word for harness gear, and the identity line was
  rewritten for the residue during phase 2.
- A second rename buys nothing functional and costs a full all-host barrier: another
  irreversible `tasks rename`, a second reserved alias (`ai` is already one), the registry
  and mirror on each host, and an edit wherever another project names the registry key.
- Every reference written during phases 1 and 2 (`tack-link`, the `tack` registry key,
  the task ids in three projects' records) stays true.

Rejected: a functional name such as `harness`. It reads more plainly to a newcomer, but
relay's purpose line already says "harness adapters", so the word would name two
projects' subject at once.

Consequences, all in the plan:

- ops `ops-593133` ("the residue rename on every host") is dropped with this decision as
  its reason; nothing is renamed on any host.
- The parent spec's §7.1 and status line gain one dated sentence: the residue keeps
  `tack`. Its §9 item 3 ("the residue's rename") is met by the recorded decision.
- `tools/rename-cutover` and `tools/test_rename_cutover.py` are removed. The tool is a
  one-off for a finished cutover; its design document stays, and history keeps the code.
  The plan first confirms the three task records that cite it are closed.

If the user names a new name instead: §4 to §7 are unchanged, `ops-593133` stays, the
one-off tool stays as the starting point, and the rename gets its own spec modelled on
the 2026-09-27 design, after this one lands.

## 4. Capability facts

### 4.1 What a fact is here

The parent's §5.3 defines it: an operational fact about an environment, with a typed
value and, separately, an evidence status. This design adds only what an implementation
needs.

A fact has a name, a type, and one entry per harness it has been established for. An
entry is either `probed`, with a value and the harness version, date and evidence pointer
of the probe, or `unknown`, with no value. A harness with no entry is `unknown`. "The
harness does not do this" is a probed value (`controller-wake` is `false` on Codex);
"nobody has looked" is `unknown`. The two are never merged, and no reader substitutes a
default for `unknown`.

### 4.2 The file

`facts/capabilities.toml`, tracked, hand-edited, schema-versioned:

```toml
schema = 1
harnesses = ["claude-code", "codex", "opencode"]

[facts.controller-wake]
type = "boolean"
description = "The harness starts a new controller turn, without human input, when a child it runs finishes."
probe = "agents/bin/wake-judge"

[facts.controller-wake.harness.claude-code]
status = "probed"
value = true
version = "2.1.282"
date = 2026-09-24
evidence = "tack-00ccb6"

[facts.controller-wake.harness.codex]
status = "probed"
value = false
version = "0.156.1"
date = 2026-09-24
evidence = "tack-00ccb6"
```

Rules the validator enforces, each a refusal with the table's name:

- `schema` is 1. `harnesses` is a non-empty list of unique names; every `harness.<name>`
  table names one of them.
- `type` is `boolean`, `number` or `set`. A `set` value is a list of unique strings; a
  `number` is an integer or float; a `boolean` is a TOML boolean.
- A `probed` entry has `value` of the fact's type, a non-empty `version`, a TOML `date`,
  and a non-empty `evidence`. An `unknown` entry has `status` and nothing else except an
  optional `note`.
- `description` is required. `probe` (the tool that judges the fact, as a path in this
  checkout) and `note` (a qualifier on an entry) are optional. No other key is accepted
  anywhere, so a misspelt key is an error and not a silent omission.

`evidence` is an opaque pointer: a task id or a record path. The validator checks that it
is present, not that it resolves, because resolving would make a commit here depend on
another project's checkout.

### 4.3 The tool

`tools/harness-facts`, Python, standard library only, linked as
`~/.agents/bin/harness-facts`. The name is functional, like `harness-state-refresh`, so
it would survive a rename.

- `harness-facts check` validates the file. Exit 0, or exit 2 with one line per refusal.
  `just test` runs it, and the pre-commit hook runs it when the file is staged.
- `harness-facts list` prints the whole view as JSON: `schema`, `harnesses`, and for each
  fact its type, description, probe and one entry per declared harness, with `unknown`
  filled in for harnesses that have no table. `--pretty` prints a table for a person.
- `harness-facts get <fact> <harness>` prints one entry as JSON. Exit 0 for `probed` and
  for `unknown`, since unknown is an answer. Exit 2 for an undeclared fact or harness, or
  an invalid file: a typo must not read as "unknown".

It never writes. `--file PATH` points it at another file, for tests.

### 4.4 The consumer contract

Every reader goes through the tool's own validation. There are two ways in, and parsing
the TOML by hand is not one of them:

- **The tool as a command**, by its installed path: `get` or `list`.
- **The tool as a module**, for a Python hook that cannot afford a subprocess: locate this
  checkout through the tasks registry, load `tools/harness-facts` with a source loader
  (the pattern lore's profile hook uses for ops's resolver), and call
  `lookup(fact, harness)`. It validates the whole file first, by the rules of §4.2, and
  returns the same entry `get` prints.

Both refuse the same things: an invalid file, an undeclared fact, an undeclared harness.
So a misspelt harness can never read as `unknown`, and a value of the wrong type (the
string `"false"` where a boolean is declared) can never reach a consumer as a truthy
value. A hand-written reader would have neither guarantee, which is why none is
supported.

Either way the consumer owns three decisions the view does not make: what `unknown`
permits (the current `claim-guard` rule, "an unprobed kind allows nothing", is the
conservative default the parent names), what to do when the read fails (a guard fails
closed), and whether a fact probed on an older harness version is still good enough.
Facts are not judgments (parent §5.3).

Data flows one way (parent §5.1): consumers read harness support. Nothing here reads a
consumer.

### 4.5 The first three facts

Carried from `claim-guard` with their evidence, value for value:

| Fact | Type | Entries |
|---|---|---|
| `controller-wake` | boolean | claude-code `true` (2.1.282, 2026-09-24, `tack-00ccb6`); codex `false` (0.156.1, 2026-09-24, `tack-00ccb6`), with the note that it rests on a bounded 170-second observation for both child kinds and not on a judge verdict (§4.6) |
| `controller-wake-kinds` | set | claude-code `["shell", "subagent"]` (same probe): the child kinds for which the wake was shown |
| `stop-input-in-flight-statuses` | set | claude-code `["running", "pending"]` (2.1.284, 2026-09-29, `ops-ed76fe`), with the note that the probe showed `running` and `pending` is from the input's schema |

OpenCode has no entry for any of them and reads as `unknown`. The plan checks each value,
version and date against the cited task records before committing the file, and records
any difference from the code comments.

### 4.6 The probe tool, and re-probing

`agents/bin/wake-judge` stays here as the probe tool for `controller-wake` and
`controller-wake-kinds`; the fact names it in `probe`. It can establish a wake. It cannot
establish the absence of one: it prints `FAIL` for a transcript it cannot classify as
well as for a run with no wake, and it knows no Codex completion form at all. The Codex
entry above rests on a separate observation, recorded on `tack-00ccb6`: the controller's
turn ended, the child finished, and no new turn began within 170 seconds.

So a probe run for one child kind (a subagent, a background command) has three outcomes,
and the README's "Re-probing a fact" section defines them:

- **Woke.** `wake-judge` prints `PASS` for the run's transcript.
- **Did not wake.** A bounded negative observation, recorded on the evidence task with
  the transcript's path: the controller's turn ended, the child's own output shows it
  finished, and no controller turn began in the 170 seconds after that. A judge `FAIL`
  is not this observation and never stands in for it.
- **Inconclusive.** Anything else, including a judge `FAIL` with no bounded observation
  behind it.

Both child kinds are probed before the aggregate fact is touched:

| The two runs | `controller-wake` | `controller-wake-kinds` |
|---|---|---|
| both woke | `true` | both kinds |
| either inconclusive | unchanged, with its old version and evidence | unchanged |
| neither inconclusive, at least one did not wake | `false` | the kinds that woke, possibly none |

A refresh edits `version`, `date`, `evidence` and the values in one commit. An
inconclusive run is recorded on its task and changes nothing in the file, so the entry
keeps saying which version it was last established on.

A fact goes stale silently when a harness upgrades. This design does not solve that. It
is filed as an idea in tack (compare the installed version with `version` and report the
gap), because the remedy needs a decision about who looks and when, and no consumer asks
for it yet.

### 4.7 Until `claim-guard` reads the view

The parent leaves the consumer switch to tasks (`tasks-56b450`), in whichever order it
chooses, and that task is under active design. So for a period the three values exist
twice: here, authoritative from the commit that adds them, and as constants in
`claim-guard`.

One test guards the gap, on the consumer's side so the data still flows one way: ops
`tests/test_claim_guard.py` gains a test that locates tack through the registry, reads
`facts/capabilities.toml`, and asserts that `CHILD_WAKES`, `WAKING` and `IN_FLIGHT` equal
the three facts (sets compared as sets; `CHILD_WAKES` against the probed boolean entries).
It reads through the tool's module (§4.4), and reads the file named by
`HARNESS_FACTS_FILE` when that is set, so it can be pointed at a candidate. It skips,
with the reason printed, only when the registry has no `tack` entry and no candidate is
named; an invalid file or a difference fails.

That test alone would only catch a change made in ops. A change made here would pass
tack's gates, merge, and leave the live guard on its old constants until someone next ran
ops's suite. So the check also runs from this side, against the candidate, before a fact
change can be committed: tack's pre-commit hook, when `facts/capabilities.toml` is
staged, runs ops's mirror test with `HARNESS_FACTS_FILE` set to the staged file, in the
registered ops checkout, and refuses the commit if it fails. `just facts-mirror` runs the
same check by hand. A refresh that changes only `version`, `date` or `evidence` passes
untouched. A refresh that changes a value lands as a pair: the constant is changed in an
ops worktree, the hook is pointed there with `FACTS_MIRROR_OPS=<that worktree>`, tack's
commit passes, and the two merge together, tack first.

Both halves, the ops test and the hook step, are deleted with the constants. A note on
`tasks-56b450` names the file's path, the contract in §4.4, and the two things to remove.

Rejected: switching `claim-guard` to read the view in this phase. It would close the gap
at once, but it changes a Stop hook that tasks is redesigning this week, and the parent
assigns that change to tasks. Rejected too: no guard at all, which leaves two unguarded
copies of a fact a gate depends on.

### 4.8 Relay's facts

The parent says harness support exposes one consolidated view and never becomes a second
catalog of relay's facts (events, replies, budgets). Relay has no stored evidence record
to read (§2), so schema 1 of the view holds harness support's own facts only. Including
relay's by reference waits for two things: relay keeping its live evidence record at a
stable path, and a consumer that needs it through this view. An idea is filed in relay
for the first. This is a deliberate shortfall against the parent's wording, accepted at
review round 1 (2026-10-06). The parent spec records it, so its requirement and this
phase's acceptance agree: §5.3 gains one dated sentence saying the consolidated view
starts with harness support's own facts and takes relay's by reference once relay stores
its evidence record and a consumer asks.

## 5. The agent surface

Phases 1 and 2 built the aggregated surface: `~/.agents` is a real directory, and each
entry is a declared link to its owner. Phase 3 audits it and closes what the audit found.

- **Declare** `~/.claude/skills/tasks` in `[harness.claude.links]` as
  `"skills/tasks" = "tasks:skills/tasks"`. It is installed and in use; this is the line
  it never had.
- **Remove** the two dangling links under `~/.codex/skills`. They were never declared, so
  `[retired]` cannot prove ownership of them; the plan shows each link's target and
  removes it by hand at a gated host step, on each host where it exists.
- **Rewrite** the stale comment above the aggregate entries in `links.toml`: each entry
  targets its owner, and adding or removing a skill is a line here.
- **Leave** harness-owned real directories alone. Nothing prunes undeclared paths (parent
  §4.1).
- **Repeat the audit on the second host**, read-only over SSH, before the host step, and
  record both hosts' results on the task.

One observation, filed as an idea and not acted on: the work Claude home declares no
skills at all, so a work Claude session has none of `flow`, `tasks` or `session-logs`.
Whether that is intended is the user's call.

## 6. Old material: dispositions

Being old does not make an item irrelevant (parent §6), and instruction text is lore's
subject now. So old instruction text goes to lore's archive for the review lore already
owns (`lore-d6acd5`, whose scope the plan extends by a note), project leftovers are
deleted, and retired harness definitions stay where they are.

| Item | What it is | Disposition |
|---|---|---|
| `archive/agents-md/AGENTS-longer.md`, `AGENTS-ohai.md`, `python.md` | Earlier versions and a language section of the global instructions, 2026-02 to 2026-08, never committed | Move to lore `docs/archive/agents-md/`, committed for the first time; reviewed under `lore-d6acd5` |
| `archive/cursor/cursor-rules/**` (18 files) | Cursor rule files per stack (Python, TypeScript, Docker), 2026-01 | Move to lore `docs/archive/cursor-rules/`; same review |
| `archive/cursor/check-health.cjs`, `fix-imports.ts`, `workspaces/v3.code-workspace` | Scripts and a workspace file for the retired mindful v3 checkout, 2025-07 | Delete |
| `doc/ref/marimo-best-practices.md`, `doc/ref/xstate_timer_testing.md` | Two debugging notes on tools other projects use; nothing here or in lore cites them | Move to lore `docs/archive/ref/`; the review decides whether either becomes a skill reference |
| `claude/archive/**` (16 files) | Retired Claude Code agent and command definitions | Keep in place: tracked, harness-specific, and inert because nothing links them |

Rules for the moves:

- A moved file is committed in lore with a message naming its source (the tack commit for
  tracked files; "untracked, from tack's `archive/`" for the rest), then removed here in
  the commit that follows lore's.
- lore's pre-commit hygiene check applies to the moved text and is never bypassed. If it
  refuses a literal (a machine path, a host name), that literal is replaced and the commit
  message says so.
- The deletion is of untracked files and cannot be undone from git. It runs at a gated
  step, after the plan lists the three files, and Dropbox's own history is the only
  recovery.
- After the moves `archive/` and `doc/` no longer exist here.

## 7. The front door

- **Feedback scope**, in `tasks/.config.toml`: "Harness homes and the declared links that
  install the agent surface, harness settings and hook wiring, capability facts, state
  hygiene, the session archive, and the session-logs skill with its tools." It reaches
  the global instructions in the order phase 2 established: tack main, then ops main with
  `just projects` (mirror and fragment), then lore's `assemble-instructions write`.
- **`identity.toml`**: `authority` gains this spec; the abstract gains the capability
  facts.
- **`AGENTS.md` and `README.md`**: the layout names `facts/` and `tools/harness-facts`;
  the README gains the consumer contract in brief and the re-probing section; the lines
  about `doc/` and the rename tool go.

## 8. Order and gates

Structural changes land before behavioural ones (parent §5.6). Nothing in this phase
changes what a running session does except the scope sentence in the global instructions
and one new link.

1. **In the tack worktree**, test-first: the facts tool and its tests, the fact file, the
   `links.toml` lines, the front door, the removal of the rename tool. Reviewed, then
   merged to tack main. Nothing on a host has changed yet: links apply only on
   `just link --apply`.
2. **In an ops worktree**: the mirror test (§4.7) and the parent spec's dated sentences
   (the name, §3; the relay deferral, §4.8). Merged to ops main after tack main holds the
   file. tack's hook step is enabled in a follow-up commit here once ops main holds the
   test, since it runs that test.
3. **Gated on the user, per host**: `just link` previewed, then `just link --apply` from
   tack main (two new links); the two dangling Codex links removed; the three leftover
   files deleted. The second host repeats the link step after sync.
4. **Gated, once**: the scope chain (tack, ops with `just projects`, lore assembly), which
   changes the global instruction file every session reads.
5. **In a lore worktree**: the archive moves, then their removal here.

Rollback is by revert at each step: the links through a `[retired]` entry for the two new
paths, the scope by reverting the three commits and regenerating in the same order, the
archive moves by reverting lore's commit and restoring from tack's history or Dropbox.
The deletion in step 3 is the one step with no revert.

## 9. Testing

- `tools/test_harness_facts.py`, test-first: each validator refusal in §4.2 by name; the
  shipped file passes `check`; `list` fills `unknown` for an undeclared harness table;
  `get` exits 2 for an undeclared fact or harness and 0 for `unknown`; `lookup`, loaded
  as a module, refuses exactly what `get` refuses, including a string where a boolean is
  declared; the tool opens the file read-only.
- The pre-commit step: a staged fact file that disagrees with a scratch copy of the guard
  is refused, one that agrees passes, and a commit that does not stage the file never
  runs the check.
- `tools/test_tack_link.py` gains nothing: no link behaviour changes. `just link-check`
  on main after the apply is the check for the two new lines.
- ops: the mirror test, shown failing against a deliberately wrong scratch fact file
  before it is trusted.
- `just test` here and `just check` in ops and lore before each merge.

## 10. Acceptance and decomposition

`tack-dcb11a` is done when:

1. The name decision is recorded in the parent spec, and `ops-593133` is closed to match.
2. `facts/capabilities.toml` holds the three facts with their evidence; `harness-facts`
   is installed on both hosts; ops's mirror test passes and tack's hook runs it on a
   staged fact change; the parent spec records the relay deferral; `tasks-56b450` carries
   the hand-off note.
3. The surface audit is recorded for both hosts, `link-check` passes on both, and the two
   dangling links are gone.
4. Every item in §6 has its disposition carried out, and `lore-d6acd5` covers the moved
   text.
5. The feedback scope reads as in §7 in tack, the mirror and the assembled instructions.

Filed by the plan: the staleness idea (tack), the stored-evidence idea (relay), the work
home's skills idea (tack). With this task done, `ops-cb9749` waits only on
`tasks-56b450`.
