# Flow: an explicit state machine for task work

Status: merged to main 2026-09-15 at ba4f873 (plan executed, six steps and the trial closed)
Tasks: ai-f5da3a (state machine), ai-da52b7 (distilled flow)
Related: ai-bdff6f (retro loop), ai-21ea5d (gates as hooks), ai-9dfba9 (measure), ai-619958 (baselines)

## 1. Problem

Superpowers carries its value in a few checkpoints — design reviewed before plan,
plan reviewed before code, tests before implementation, evidence before "done",
fresh-context review — wrapped in a large volume of prose whose job is to stop a
model from skipping those checkpoints. The prose is what a capable model pays for
on every turn; the checkpoints are what the work depends on.

The tasks tracker already holds two implicit machines: `status` (idea, todo,
doing, blocked, shelved, done, dropped, with `Status::can_transition`) and a
derived `phase` (brainstorming, planning, implementing, inferred from spec, plan,
and step links). Neither says what must be true to advance or who decides. The
`process` field (direct, planned) chooses a path but not the gates along it.

`flow` makes that missing layer explicit: the states a task passes through, the
gate on each transition, who may open it, and how the transition is recorded. The
model has free rein inside a state; only the transitions are specified.

## 2. Decisions taken during brainstorming

- **Coexist, opt-in per project.** Superpowers stays installed. A project opts in
  with one line in its `AGENTS.md`; skill-triggering instructions yield to user
  instructions, so that line is the whole switch. This keeps an A/B possible.
- **First pass = model + one skill + one real task.** The machine, a skill that
  walks it, and one small task from `ai` or `tasks` run end to end under it.
  Hooks (ai-21ea5d) come later and consume the same machine.
- **Harness-neutral prose, verified in Claude Code.** Nothing in the skill names
  a Claude-only tool. Codex verification is a later task.
- **No tracker changes.** State is a function of existing fields plus a note
  convention. If the convention proves itself, promoting it into the tracker is
  a separate decision.

## 3. The machine

### 3.1 States

| State | Meaning | Tracker status allowed | Other evidence |
| --- | --- | --- | --- |
| `captured` | An unscoped thought | `idea` | no gate notes |
| `scoped` | Priority, size, complexity, and process chosen; the work is understood | `todo`, `doing` | `process` set; last gate `scoped` |
| `designed` | A design spec exists and the human has reviewed it | `todo`, `doing` | `spec` link; last gate `designed` |
| `planned` | An implementation plan exists, is reviewed, and its steps are filed as children | `todo`, `doing` | `plan` link, step children none of which has left `scoped`; last gate `planned` |
| `implementing` | Code is changing in a task worktree | leaf: `doing`; parent: `todo`, `doing` | leaf: last gate `implementing`; parent: last gate `planned` and any child has left `scoped` (§3.3), or last gate `implementing — reopened` (§3.6) |
| `verified` | Verification ran against a named covered tree; a fresh-context review happened; findings addressed | leaf: `doing`; parent: `todo`, `doing` | last gate `verified tree:<f>`, and `<f>` is still the covered tree (§3.6) |
| `closed` | Retro written; the task is done in the landing commit, which may follow the code commits (§3.6) | `done` | `retro:` note; last gate `verified` |
| `outside` | A record the flow has never touched | any | no gate notes and status is not `idea` |

A *leaf* is a record without children; a *parent* is a record with step
children. For a leaf, `doing` in `scoped` or `designed` means *claimed*: `tasks
start` is how a session takes ownership of producing the next artifact (a scope
brief, a spec, a plan), and only the `implementing` gate note says code is
changing. For a parent, status is only ever a claim: the session that designed
and planned it may hold `doing` through to `done`, or release it and leave
`todo` while children run; neither says anything about phase. The tasks skill's
rule that a goal is never *picked* as work stands; picking and claiming are
different things.

`blocked` is a `todo` with open dependencies and counts as `todo` wherever
`todo` is allowed.

`parked` is an overlay on any state, provided by `tasks park` with its reasons.
`flow` adds one obligation to it: a turn never ends with the task open and
work still owed unless a park names the next owner — only `closed` needs no
park, and a gate record is not one, since `gate: implementing` is written on
entry — and a step the agent owns (the fresh-context review, an unrun check,
an undispatched child) is parked as the agent's next step, never reported as
pending for the human. The closing message reports observed status: what
stopped, what still runs and how its result is collected, who acts next. `park` leaves status alone and `start` sets `doing`,
so a parked task resumes in the same flow state with a `doing` status — allowed
everywhere except `captured` and `closed`. `dropped` and `shelved` leave the
machine.

`outside` is a result, not a state. The eleven completed records in this
checkout and every todo without a gate note are `outside`; they never acquire a
flow state retroactively. A record enters the flow with its first gate note
(§3.5).

### 3.2 Transitions and gates

A gate has four parts: the **artifact** that must exist, the **check** that can
be run mechanically, the **judge** who decides the artifact is good enough, and
the **record** that marks the transition in the task.

| From → To | Artifact | Check | Judge | Record |
| --- | --- | --- | --- | --- |
| captured → scoped | Scope brief in the body: outcome, approach, verification | `tasks check` clean; p/size/complexity/process all set | model (human sees it in `prime`) | `tasks edit … --process`, `gate: scoped` |
| scoped → designed *(planned only)* | Design spec at the spec path | file exists; no placeholders | **human** | `tasks edit --spec`, `gate: designed <path>` |
| designed → planned *(planned only)* | Plan with `### Task N:` headings; one child per heading, each filed already scoped (§3.3) | `tasks check` clean (heading drift) | **human** | `tasks edit --plan`, children with `--step`, `gate: planned <path>` |
| scoped → implementing *(direct)* | Task worktree exists | `git worktree list` shows it | model | `tasks start`, `gate: implementing <worktree>` |
| implementing → verified | Verification output; review findings and their disposition; the covered tree they apply to | the verification commands ran in this session against covered tree `<f>` (§3.6), output in the note; each new test was seen to fail against a targeted break of the behaviour it checks; code that reads a live store (task records, session stores, an index) ran over every record of the real store it reads, and `checks:` names that run | fresh-context reviewer (subagent, or another model) who read the diff at `<f>` against the raw evidence it rests on (sources, transcripts, records, not the model's summary), hand-traced its hardest assertions, and tried its failure paths and, where it touches files or hooks, the delete and rename cases; then model | `gate: verified tree:<f> — checks: <commands and result>; review: none \| <severity> <disposition> <text>, …; reviewer: <harness/model \| human \| none> [session:<harness:id>]` |
| verified → closed | Retro (2–3 lines on what helped or hurt); the landing commit | `tasks check` clean; the covered tree is still `<f>` | model | `retro:` note, then `tasks done`, then one commit (§3.6) |

`closed` is the one transition without a `gate:` note: its record is `tasks done`
itself, which the tracker stamps with `completed`. `flow-state` reports `closed`
when status is `done`, the last gate is `verified`, and a `retro:` note exists;
`done` without those is `closed (inconsistent: …)`.

**Back edges.** A back edge is a gate note for an earlier state, and every gate
after it is void. There are two targets: `scoped`, for a design that no longer
holds, and `implementing`, written only when reopening a closed task (§3.6,
step 7); the ordinary loss of verification is automatic and unrecorded.

- `implementing → scoped` when the implementation exposes a decision the spec did
  not settle, or when direct work grows beyond the scoped task. Record it as
  `gate: scoped — invalidated: <why>`; on the direct path also set
  `--process planned`. The spec and plan links stay as drafts to revise;
  their approvals are gone, and `designed` and `planned` must be re-entered
  through their gates, human review included. Status may stay `doing` (the
  session still holds the claim).
- `verified → implementing` is automatic, not recorded: when the covered tree no
  longer matches the `gate: verified` note — an edit, a staged change, a
  rebase, a conflict resolution — `flow-state` reports
  `implementing (verified at tree:<f>, covered content changed)`. Re-verify and
  write a new `gate: verified` before closing. Bookkeeping writes never change
  the covered tree, so the closing commit does not trigger this (§3.6).

Skipping a gate is the one thing the skill forbids. Inside a state the model
chooses its own method: how to test, how to debug, how to split work between
subagents and inline edits.

### 3.3 The planned path: parent and children

A planned task becomes a goal at the `planned` gate: its steps are children, and
the tracker never lets a record with open children close. The two records carry
different gates.

**Parent** (the planned task): `captured → scoped → designed → planned`, then
`implementing` *derived*, then `verified` and `closed` with their own gates.
The derivation: while the parent's last gate is `planned`, it is `planned` until
any child leaves `scoped`, and `implementing` from then on — including after
every child has closed — until the parent's own `gate: verified`. No note marks
the parent's entry into implementation; the children's notes do. Parent
verification is integration-level: the whole branch, the full suite, one
fresh-context review of the combined diff. Its *check* is that every child is
validly closed; its record is `gate: verified tree:<f>`, then `retro:`, then
`tasks done`, which the tracker permits only when every child is closed. A
`dropped` child is neither open nor blocking — the tracker itself counts it
closed and lets the parent close over it — and `flow-state` skips it. A
`shelved` child stays blocking, because the tracker holds it open. Parent status
is a claim throughout (§3.1) and never part of the derivation.

**Child** (one per `### Task N:`): filed at the `planned` gate with
`--parent`, `--step`, `--complexity`, and `--process`, and a body that is its
scope brief, so it is born `scoped` — its first gate note is written by whoever
files it: `gate: scoped — step of <parent> plan`. Like any brief that hands
work to an implementer, it carries the contract the step must satisfy (or its
path) and a one-line why for each detail that looks removable. A
`--process direct` child
runs the direct path in the parent's worktree: `implementing → verified →
closed`, each with its own gate note, `tasks done` in the commit that lands the
step. A child that `--process planned` is a planned task in its own right and
runs the whole machine; its own children are its steps. Child verification is
step-level (the step's tests and a review of the step's diff); the parent's
verification is not a substitute for it and vice versa.

A back edge on a child (`gate: scoped — invalidated`) that changes the plan is a
back edge on the parent too: the parent's `planned` approval is void, and the
plan is re-reviewed before the remaining children continue. A back edge that
only reshapes the child's own work stays on the child.

### 3.4 Two paths through the machine

```
direct:   captured → scoped → implementing → verified → closed
                        ↑          │    (covered tree changed: back to implementing, unrecorded)
                        └──────────┘    gate: scoped — invalidated

planned:  captured → scoped → designed → planned → implementing* → verified → closed
  parent                ↑                              (derived from children)
                        └────── invalidated (from a child, or from the parent's own review)

  child:  scoped (at filing) → implementing → verified → closed
```

Human judgment sits on exactly two gates, `designed` and `planned` — the same two
artifacts the global instructions already gate. Every other gate is mechanical
(a check) or the model's own evidence.

### 3.5 Recording transitions

Each transition except `closed` is one `tasks note <id> "gate: <state> —
<evidence>"`. Notes are timestamped, ordered, and already shown by `tasks show`,
so the sequence of `gate:` notes is the task's transition log. No new tracker
field is needed, and `obs` can read the log from the record. While a task has
a worktree, its record is read and written there, since it lands with the
code: the main checkout's copy is as of the last merge, and a note written to
it forks the log. Briefs dispatched for the task give absolute worktree paths
and stop on a failed `cd`.
The grammar of those notes is `agents/flow/gate-notes.md`, with the corpus
every parser is tested against beside it; a malformed note voids the state it
attempted (functional core spec, 2026-09-21, section 4.2).

State is derived, never stored: the last `gate:` note names it, the tracker
fields must agree with §3.1, and `gate: verified` additionally agrees with the
covered tree (§3.6) when `flow-state` runs inside a git worktree. Disagreement is reported as
`<state> (inconsistent: <why>)`, never resolved by guessing. The tracker's own
status transitions remain authoritative for what `status` may become; `flow`
narrows when the model may ask for them.

**Adoption.** A record without gate notes is `outside` (or `captured` when it is
an idea, which claims nothing beyond what `idea` already means). An existing
scoped todo enters the flow when a session picks it up under the skill: it
writes `gate: scoped — adopted` after confirming the record meets the `scoped`
gate (process set, scope brief present), scoping it first if not. Nothing is
backfilled onto closed records.

### 3.6 The covered tree, and the closing sequence

Verification is bound to *content*, not to a commit. The **covered tree** is a
git tree hash of what is on disk — tracked files as they currently are,
untracked files git would add, staged or not — with the bookkeeping paths left
out: `tasks/`, and the spec and plan documents. `flow-state fingerprint`
computes it with a temporary index seeded from the real one, so git keeps its
knowledge of which files are tracked (a tracked file that also matches an
ignore rule is still covered):

    cp .git/index <tmp>                       # or the worktree's index file
    GIT_INDEX_FILE=<tmp> git add -A
    GIT_INDEX_FILE=<tmp> git rm -r -q -f --cached --ignore-unmatch -- tasks docs/specs docs/plans
    GIT_INDEX_FILE=<tmp> git write-tree

`-f` is required: without it `git rm --cached` refuses a path whose staged
content differs from both HEAD and disk, and a half-staged task file must not
stop the projection. The flag acts only on the temporary index. The excluded
set is fixed by the skill, not chosen per task, so two sessions compute the
same value. An untracked file that matches an ignore rule stays
invisible, which is right: git would never land it. A spec kept under
`.git/info/exclude` is invisible for the same reason.

The same projection has two more forms, and the closing sequence uses all
three:

- `fingerprint` (default): the working tree, as above.
- `fingerprint --index`: the real index copied, bookkeeping removed, written —
  what `git commit` would record right now.
- `fingerprint --head`: `git read-tree HEAD` into the temporary index,
  bookkeeping removed, written — what a commit did record.

**Submodules.** A submodule contributes its recorded commit to the tree, never
its working-tree contents; an edit inside `agents/skills/superpowers` would
leave every projection unchanged. The first pass does not fingerprint
recursively. Instead `fingerprint` refuses — non-zero exit, no hash — while any
covered submodule has modified content or untracked files
(`git status --porcelain=2 --ignore-submodules=none`, entries whose submodule
field shows `M` or `U`). A submodule whose only change is a moved commit
pointer is fine: that is in the tree. Verification cannot start, and closure
cannot proceed, until the submodule is clean or its change is committed there
and the pointer updated here.

Consequences:

- An uncommitted edit to a covered file changes the fingerprint. `verified` is
  not a claim about HEAD; it is a claim about what is on disk.
- Writing `gate:` and `retro:` notes, `tasks done`, and editing a spec or plan
  do not change it. Bookkeeping never invalidates verification.
- A rebase or conflict resolution that changes covered content changes it; one
  that reproduces the same content byte for byte does not, which is correct.

**Closing sequence** for a leaf, with `<f>` the fingerprint at the moment
verification ran:

1. Verify: run the checks, get the review, address findings. Any fix moves
   `<f>`; re-run until the checks pass against the tree you will land.
2. `tasks note <id> "gate: verified tree:<f> — …"`.
3. `tasks note <id> "retro: …"`.
4. Stage everything that will land, then require
   `fingerprint --index` = `fingerprint` = `<f>`. A partially staged file
   fails this: tests saw the working-tree version, the commit would record the
   staged one. Stage the rest (or revert it) and re-check; if that changes the
   working tree, the state is `implementing` (automatically, §3.2) and the
   sequence restarts at step 1. Nothing has been closed yet.
5. `tasks done <id> "…"`, and stage the `tasks/` change it made.
6. One commit containing the code and every `tasks/` change from steps 2–5.
7. Confirm `fingerprint --head` = `<f>`. After step 4 this can fail only if a
   hook rewrote content during the commit. If it does, the task is `done` in
   the tracker but the commit did not land what was verified, so reopen it
   explicitly before anything else:

       tasks edit <id> --status todo        # done reopens to todo only
       tasks start <id>
       tasks note <id> "gate: implementing — reopened: commit <sha> landed tree:<g>, verified tree:<f>"

   then restart at step 1. The `gate: implementing` note is a recorded back
   edge from `verified`; it voids the `verified` gate the way `gate: scoped`
   voids later ones, and the reopened record needs a fresh `gate: verified`
   and `retro:` before it closes again. The commit stays; the next closing
   commit carries the reopening and the new closure. A parent reopens the
   same way: `gate: implementing — reopened` is the one case where a parent
   carries that gate itself rather than deriving it from children (§3.1).

   **A commit that fails** (a rejecting hook, a signing error, a missing
   tool) leaves the task `done` with no landing commit. Run `fingerprint`
   first. If it still reads `<f>` and the cause needs no covered change —
   a signing key, a hook's own dependency — fix the cause and retry step 6;
   the tracker record is still true, and nothing was verified in vain. If the
   cause needs a covered change (the hook rejected the content), reopen as
   above with the failure recorded in place of a SHA:

       tasks note <id> "gate: implementing — reopened: commit failed: <reason>, verified tree:<f>"

   and restart at step 1. Either way the failure is visible in the record or
   in a retried commit, never in a `done` task that has no commit behind it.

Steps 2, 3, and 5 change nothing covered, so a commit that passes step 4
records `<f>`. Code may already be committed before step 1 (a series of
commits during `implementing` is normal); what matters is that nothing covered
changes between step 1 and step 6.

`flow-state <id>` re-derives `verified` against the working tree whenever it
runs. It does not re-derive `closed` against git afterwards: the landing commit
is not recorded in the task, and HEAD moves on with other work. Step 7 is the
closer's check at close time, and the hook work (ai-21ea5d) is where it becomes
enforced rather than followed.

A parent's closing sequence is the same, with the check in step 1 being that
every child is closed and the verification being integration-level.

## 4. Components

### 4.1 `agents/skills/flow/SKILL.md`

The skill is short. It says:

1. Find the task's state: `flow-state <id>`, or read the last `gate:` note.
   `outside` means adopt it (§3.5) before doing anything else.
2. Inside a state, work however fits. The state names the artifact you are
   producing, nothing more.
3. To advance, satisfy the gate (artifact, check, judge) and write the record.
   Never advance without the record; never write the record without the gate.
4. When work in a state invalidates an earlier gate, write `gate: scoped —
   invalidated: <why>` and say so. Every later approval is gone.
5. Before `tasks done`, write the `retro:` note: two or three lines on which
   pattern helped or hurt on this task. This is the feedback channel; ai-bdff6f
   curates it later.

The skill carries the tables from §3 as its reference section. It does not
restate testing, debugging, or review method; it names the gate criterion
("tests exist before the code they cover", "a reviewer without your context read
the diff at tree `<f>`") and leaves the how to the model. Criteria promoted
from retros (the ai-c78706 curation pass, 2026-09-24) name acts the
verification and review must have done (a targeted break of each new test, a
run over the real store, a hand trace, the failure and lifecycle cases) and
leave how to do them to the model.

### 4.2 `agents/bin/flow-state`

A small script: `tasks show <id>` as JSON in, one line out —
`<state>`, `<state> (inconsistent: <why>)`, or `outside` — with `--json` for
hooks and obs. `flow-state fingerprint [--index|--head]` prints the three projections of
§3.6 and refuses on a dirty covered submodule; inside a git worktree
`flow-state <id>` compares a `gate: verified tree:<f>` against the working-tree
projection. For a record with children it derives `implementing` from their
states. It is the executable form of §3.1–3.5 and the only code in the first
pass.

Tests are transition-sequence fixtures, not single states: one record's note
log at each step of the direct path; a planned parent with two children through
filing, step closure, parent verification, and parent closure; invalidation from
`implementing` and re-entry through `designed`; park and resume in `scoped` and
in `implementing`; closure with and without the retro; a closed leaf and a closed parent each
reopened through `todo`, `start`, and `gate: implementing — reopened`, which
must read `implementing`, not `closed` or `verified`, the parent without
re-deriving from its closed children; a verified record whose
covered tree changed, once by a commit and once by an uncommitted edit, and one
whose only change since verification is bookkeeping (still `verified`);
fingerprint cases in a temporary repository: a tracked file matching an ignore
rule edited (fingerprint changes), an untracked ignored file added (unchanged),
a partially staged file (`--index` differs from the default), a dirty
submodule (refused) and one with only a moved pointer (allowed); and adoption of a pre-existing todo and of a completed record
(`outside`, unchanged).

### 4.3 Opt-in

A project opts in with one line in its `AGENTS.md`:

> This project uses the `flow` skill for task work. Superpowers process skills
> (brainstorming, writing-plans, executing-plans) do not trigger here; their
> implementation skills may be used inside a state when they fit.

The `tasks` skill's **Process and workspace** section already defers to the
project's agent instructions for whether brainstorming runs, so this line is
sufficient and consistent with it.

In `ai` itself `AGENTS.md` is the global instruction file (the harnesses' user
instruction files link to it), so the line cannot go there without opting in
every project. The first-pass trial in `ai` invokes the skill explicitly; the
first per-project opt-in is a later choice, made in that project.

## 5. What the first pass does not do

- No hooks. ai-21ea5d will make the `check` column enforceable from the harness
  using `flow-state`; the first pass only makes the checks statable.
- No blocks or reusable atoms. Two concrete flows come before factoring
  (ai-da52b7 note). This machine is the first flow.
- No tracker changes, no new fields, no `tasks gate` command.
- No pairwise agent protocol. The `verified` gate's "fresh-context reviewer" is
  the seam where ai-fc26cf (Codex reviews a Claude plan) plugs in.
- No measurement. ai-9dfba9 defines that; the `gate:` log is designed to be
  what it measures.

## 6. Verification of the first pass

1. `flow-state` transition-sequence fixtures (§4.2) pass.
2. One real task from `ai` or `tasks`, small and direct-process, is run under the
   skill in Claude Code with superpowers still installed: its record ends with a
   complete `gate:` sequence, a `retro:` note, and `tasks done` in the landing
   commit (which may follow the code commits, §3.6), and `flow-state` reports
   `closed` with no inconsistency. The session
   log is kept for ai-9dfba9.
3. `flow-state` reports every task in `ai` without error: completed records and
   unassessed todos as `outside`, ideas as `captured`, nothing else claimed.

## 7. Open questions

- Whether `scoped` needs a human judge for high-complexity tasks. Not in the
  first pass: `prime` already surfaces scoping, and adding a third human gate is
  the kind of ceremony this is trying to remove. Revisit with data.
- Where the retro goes beyond the note: mindful capture, a journal file, or the
  note alone. The first pass uses the note alone; ai-bdff6f decides the store
  when it designs curation.
- A `--process planned` child (a step that is itself a planned task with its own
  steps): the machine allows it (§3.3) and `flow-state` reads such a child
  through `derive_leaf` without fetching grandchildren; the skill does not
  describe it. First real case decides whether it needs more.
