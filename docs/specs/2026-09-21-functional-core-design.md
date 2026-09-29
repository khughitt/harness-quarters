# Functional core, imperative shell: a framing for agent work

Status: implemented (ai-634de8); steps 4.1 and 4.2 landed on 2026-09-22.
Related: `docs/specs/2026-09-15-flow-state-machine-design.md` (the machine),
`obs/docs/specs/2026-09-17-obs-evals-charter-design.md` (evidence classes),
`obs/docs/specs/2026-09-21-cost-per-outcome-design.md` (the join),
`ops/docs/specs/2026-09-16-relay-design.md` (guards and observers),
`docs/notes/2026-09-21-flow-gates-brief.md` (the flow cluster after the first pass).

## 1. Problem

The recent work in `ai`, `obs`, `relay` and `tasks` has converged on one shape
without naming it. Flow state is derived from the record and the tree, never
stored. obs keeps an append-only log and rebuilds its views from their inputs
rather than trusting a stored answer. relay
splits hooks into guards that may deny and observers that may only record. The
tasks tracker's `check` turns drift into findings instead of guesses. Each
project arrived at this on its own, and the theme in the plans is the same:
detect silent failure, make things explicit, compose from reusable pieces.

Unnamed, the shape has two failure modes. New work drifts: a tool that caches a
derived state, a hook that swallows an error to stay out of the way, a note
convention nobody checks. Or the shape gets over-named into a framework: a work
algebra, a typed step library, a flow DSL that has to be learned before a task
can be filed. The prompt that produced this spec asked for the second thing
("steps as typed functions", "failures as implicit effects", "generalize work").
This spec gives the framing and rejects the framework.

The document is a lens, not a component. Its test is whether a reader in any of
the four projects can look at a proposed change and say which side of the line
it lands on and what it owes.

## 2. Decisions taken during brainstorming

- **Framing, not framework.** Vocabulary and rules that the existing tools
  already satisfy, plus the two small changes the vocabulary exposes (section
  4). No library, no DSL, no rewrite.
- **Explicit effects, not implicit.** Implicit effects are the silent-failure
  mechanism. The rule is the opposite: every failure is a value someone must
  handle (section 3.3).
- **Typed means checked.** A convention is typed only when a program rejects
  the ill-formed case. Prose alone is untyped whatever it says (section 3.5).
- **Land in `ai`.** The framing is about agent workflow, sits beside the flow
  spec, and its concrete steps land in `agents/`. Pieces owned by another
  project are filed there and depend on this goal; the hub project is not used
  because the steps are not spread across projects.
- **Reuse the charter's evidence classes.** obs already types evidence as
  expected, claimed, observed, inferred. The framing adopts those words instead
  of inventing a second set.

## 3. The framing

### 3.1 Core and shell

The **core** is a function from explicit inputs to a result, with no IO of its
own. The **shell** is everything that gathers those inputs and acts on the
result: the model, the harness loop, git, the filesystem, the hooks, and the
commands that orchestrate a core function. A command is shell even when its
whole purpose is to run one core function; the line is drawn at the function,
not at the executable. Core code is tested against fixtures; shell code is
tested by live checks. New logic goes in the core with its inputs named; the
shell reads, calls, writes.

What is already core, with the shell that wraps it:

| Project | Pure derivation | Explicit inputs | Output | Shell around it |
| --- | --- | --- | --- | --- |
| ai | leaf and parent derivation in `flow-state` | one record's notes and fields, its children's, an optional covered tree hash | state, or `<state> (inconsistent: why)` | `flow-state <id>`: runs `tasks show`, lists worktrees, calls `fingerprint` |
| ai | the covered-tree projection | the tracked and untracked content minus the bookkeeping paths | a tree hash | `flow-state fingerprint`: copies the index, stages into a temporary index, writes git objects, reads the hash back |
| tasks | record validation in `check` | every record, the spec and plan headings | findings, or nothing | the `check` command reads the files and prints |
| tasks | selection in `ready`, `next`, `prime` | records, claim rows | a selection, hidden items counted | the commands read the claim store |
| obs | one reconcile step | previous state (cursor and derived state), the clock, new log records, the claim stores' current rows | next state, the findings view, diagnostics | `obs reconcile`: reads `state.json`, the log and the live stores; writes `state.json` and `findings.json` atomically |
| obs | cost attribution | index rows, stamped lifecycle notes, gate notes | cost per task and stage, an unattributed remainder | `obs index` and the report queries |
| obs | the stall proxy | episodes from the index | incidents, with the shape it cannot see stated | the report command |

Two qualifications the table forces. `fingerprint`'s result is a function of
content, but computing it writes objects into git's store; the write is
idempotent and never touches the real index, which is why the spec treats the
projection as core and the command as shell. obs reconcile is a fold with an
explicit accumulator and a clock, and one of its inputs (the claim stores) is
read live and never logged. So obs findings are replayable from the log only
for the part the log determines; the claim-derived part is reproducible only
while the stores still hold those rows. The charter's coverage-gap reporting
is where that limit is stated, and any new obs view says which of its inputs
are logged.

The consequence that matters most: **a derived answer is never stored as
truth.** A flow state, a finding, a cost figure, a stall incident are all
recomputed from their inputs. A stored accumulator is fine when it is the
fold's own state, and the two obs stores give the two different guarantees
such state can have. The transcript index is rebuilt from its sources: `obs
index --full` re-reads every present harness file, and a missing file keeps
its rows with a `missing_since` stamp because the source is gone. Reconcile's
`state.json` is not rebuilt: when it is absent the command cold-starts, reports
`cold_start` in its coverage, and reads the current claim stores, so a restart
reproduces the log-determined findings and not the history of live rows it
had seen. Each store says which guarantee it gives; a new store must too. What
is not fine is a cached verdict that a later reader trusts without the inputs
that produced it.

### 3.2 Evidence has a type

The charter's four classes are the types of the core's inputs and outputs:

| Class | Meaning | In the flow |
| --- | --- | --- |
| expected | an obligation a flow names | the gate table; "a reviewer without your context read the diff" |
| claimed | a model said it happened | every `gate:` and `retro:` note |
| observed | a source measured it | stamped lifecycle notes, claim liveness, a recomputed fingerprint, a hook event |
| inferred | correlated facts imply it | a turn attributed to a stage; a stall incident |

The classes are categories, not a ranking, so there is no rule that an output
"takes the weakest input". The rules are per operation:

- **Carrying** keeps the class. A listing of gate notes reports claims; a
  count of verified gates is a count of claims. Curating retros or reading
  review outcomes from notes never promotes them.
- **Recomputing** from a source yields observed evidence for exactly what the
  source measures. A fingerprint that matches a `verified` note's hash makes
  the tree identity observed; the review named in the same note stays
  claimed. The charter says this in one sentence: matching a tree establishes
  its identity, while tests and reviewer independence require their own
  evidence.
- **Joining or correlating** two sources yields inferred evidence, and the
  result keeps each source's limitation. Cost per stage joins observed stamps
  to a claimed gate, so every attributed figure is inferred and the
  cost-per-outcome design says so; the stall proxy correlates a turn end with
  a missing park and says which shape it cannot see.
- **Promotion** needs a new observed source, not a derivation: a hook event
  for a reviewer's session, a transcript row for the commands run.
- A figure that blends classes without saying which has a bug, not a
  presentation choice. A view reports its class per figure or per column, as
  the cost-per-outcome view does.

### 3.3 Failures are values

A failure is a record the caller must handle: a finding, a diagnostic, a
refusal, a coverage gap. It is never an exception swallowed to keep going, a
default substituted for a missing input, or a partial result presented as
whole. This is the core rule "fail early, avoid silent fallbacks" with a shape:
the failure has a type, a place it is written, and a reader.

Where it already holds, so a new tool has a model to copy:

- obs `ingest` exits 1 with a JSON diagnostic and never echoes input; the
  reconciler skips a malformed line with its byte offset and reports a trailing
  partial line as a coverage gap. Unsafe permissions are rejected, not repaired.
- relay: a configured guard's error, timeout or invalid reply is a refusal, not
  an allow; an observer's failure is reported and healed by reconciliation; an
  oversized context reply is an error, not truncation.
- `flow-state` reports `<state> (inconsistent: <why>)` and never resolves the
  disagreement by guessing; `fingerprint` refuses on a dirty submodule rather
  than hashing around it.
- `tasks ready` hides claimed, deferred and over-complexity work and says in
  warnings how many it hid; `check` prints findings as JSON and exits 1.
- The flow itself: a back edge is written out loud (`gate: scoped —
  invalidated: <why>`); a turn that ends with work owed writes a park naming
  the next owner. Both are failures of the happy path turned into records.

**Why implicit effects are rejected.** An effect system where failure
propagates unseen until a handler catches it is the unchecked-exception model.
It is what produces the two recorded stall shapes on ai-c62995: a subagent's
turn ending with a claim live and nothing written, and a park with a vacuous
next step. The framing wants the opposite discipline: at the point a failure
occurs, a value is written that names it, and the shell's job is to make sure
that value has a reader (a finding in obs, a refusal in the harness, a park in
the tracker).

### 3.4 Two effect kinds

relay's roles are the two effect types every hook must choose between:

- **Guard**: `Event -> Reply`. Total: every outcome, including the guard's own
  failure, maps to a reply, and an unknown outcome maps to deny. Runs first,
  before enrichment, without depending on the observer path. Its reason text
  is part of the value (denial requires a reason).
- **Observer**: `Event -> ()`. May not return a decision. Its failure is a
  diagnostic and a reconciliation item; it never reaches the reply.

The rule for new hook work: name the kind before writing the hook. The Stop
hook on an abandoned claim (ai-21ea5d) is a guard: its reply is block or allow,
its reason names the claim and the release (`tasks park` with a real next step),
and its own failure (`tasks prime` unreachable, malformed input) is a block with
that reason, not a pass. familiar and obs collection are observers: an obs
outage never changes what the harness lets through. A hook that wants both,
recording and deciding, is two subscribers.

### 3.5 A gate is a typed record; a flow is data

The flow spec already defines a gate as four things: the artifact that must
exist, the check that can be run mechanically, the judge who decides the
artifact is good enough, and the record that marks the transition. That is the
building block ai-da52b7 was looking for. Written as a type:

    Gate     = { from: State, to: State, artifact: Kind, check: Evidence -> Findings,
                 judge: Human | Model | Reviewer, record: NoteGrammar }
    Flow     = { gates: [Gate], back_edges: [(State, State, Reason)] }
    state    : (Record, Children, Worktrees, Tree) -> State | Inconsistent

Composition is two operations the spec already uses and nothing else:
concatenation (the direct path is the planned path with two gates removed) and
nesting (a parent's state is a fold over its children's states, spec section
3.3). A second concrete flow (a per-kind lifecycle, ai-b9ab40) is another
`gates` list over the same `State` and the same `NoteGrammar`, and the day it
exists `flow-state` reads its machine from a table instead of its source. Until
then the table stays in the source: one consumer does not justify the
indirection, and ai-da52b7's wake condition is unchanged.

**Typed means checked.** The gate record is typed to the extent a program
rejects an ill-formed one. Today two programs read `gate:` notes and no
document says which is the grammar. Their entry points already disagree in
three ways: `flow-state` finds the tree anywhere in a `verified` detail
(`search`) while obs's `_gate` requires it at the start of the detail
(`match`), so a note that puts `tree:` after the checks is verified to one and
tree-less to the other; a note beginning `gate:` with a state the machine does
not have is silently not a gate to `flow-state` and an `unrecognized_gate`
diagnostic to obs; and the regexes differ in anchoring (`match` on `^gate:`
against `fullmatch` without the anchor), which happens to agree on stripped
text. The `verified` note carries `tree:<hash>` because `flow-state` demands
it; everything after the dash is free text. Section 4.1 makes the grammar one
artifact with the parse result spelled out per case, so the entry points, not
the regexes, are what gets tested.

### 3.6 The judge is a bounded question

Two gates have a human judge; the rest have the model or a fresh-context
reviewer. Jev's discipline for a model-answered decision is the right
discipline for that reviewer: a question specific enough that two reviewers
would agree what a good answer looks like; a typed answer from a bounded set,
with the evidence kept beside it; policy (the threshold, what to do with the
answer) in application code, not in the model. And its caveat: type safety is
about structure, not correctness. A well-formed verdict says a review happened
in the expected shape, not that the work is good.

Applied to `implementing -> verified`: the reviewer's output is a verdict
record, not prose to be summarised. Each finding with a severity and a
disposition, the tree they were read at, and a reviewer field. The flow keeps
the policy: a finding rated important is addressed or the gate is not written,
and a record that says otherwise is an inconsistency, not a gate. The record
is what lets obs count findings per task, which it cannot today. What the
record does not do is substantiate that the reviewer was independent: a label
in a note is a claim, and section 4.2 says exactly what it leaves open.

The bounded-question shape also suggests an experiment, filed as an idea and
not built here: ask a Jev-style question of each past verified gate ("does
this note evidence an independent review of the named tree?") and compare the
distribution with the retros. If the answers separate the gates the retros
complain about, the reviewer question can become part of the gate's check.

### 3.7 Conversation and work as folds

A session is a fold over turns; a task is a fold over sessions and gate notes;
a goal is a fold over its children. This is true and useful in exactly the
places the projects own: obs's transcript index and cost attribution are those
folds, and the parent derivation in the flow spec is the third. The harness's
message loop is also a fold, and not ours: nothing here proposes building or
wrapping the agentic loop. The framing's claim is only that every figure the
projects report about a session, a task or a goal should be expressible as a
fold over records, log and tree, with no hidden state in the middle. Where a
figure cannot be, that is the place to look for a stored verdict.

## 4. What falls out

Two changes, both in `ai`, both small, filed as plan steps at the `planned`
gate. Two ideas beside the goal.

### 4.1 One gate-note grammar and a golden corpus

- `agents/flow/gate-notes.md` states the grammar: `gate: <state>` followed by
  optional detail; `verified` detail must contain `tree:<40 hex>`; the states
  are the five the parsers accept; a `retro:` note is `retro:` followed by text;
  a back edge is `gate: scoped — invalidated: <why>` or
  `gate: implementing — reopened: <why>`.
- `agents/flow/gate-notes.jsonl` is the corpus: one case per line, the note
  text and the full parse result, not a regex match. A result is one of three
  kinds. `gate` carries the state, the detail, the tree (present or absent)
  and, for a `verified` note, the verdict fields of section 4.2 or their
  absence. `not-a-gate` is any note the grammar does not claim, such as prose
  that mentions "gate:" mid-sentence or a `retro:` note. `malformed` is a note
  that begins `gate:` and is not a gate: an unknown state, a hash of the wrong
  length, a verdict that fails its own consistency rule. A `verified` gate
  without a tree is a `gate` with the tree absent, never `malformed`: the
  derivation turns it into `verified (no verdict; inconsistent: verified gate without tree:<hash>)` and that report
  must survive, so the grammar recognises the note and the machine judges it.
- The corpus covers every note shape on record on the day it is written (grep
  over each registered project's `tasks/`), a `verified` note with the tree
  after the checks text, leading whitespace, and the section 4.2 shape in its
  well-formed and malformed variants.
- `flow-state` gains one parsing entry point, `parse_note(text)`, returning
  the three kinds; `gates()` and `verified_tree_of` are expressed through it,
  and the tests run the corpus through that entry point and through the
  derivation for the `verified`-without-tree case. This is the whole of the
  step; it is complete and verifiable inside `ai`.
- obs consumes the corpus separately (obs-8ad564, filed): it vendors the file
  the way `cli.toml` is vendored from ops and runs it through its own entry
  points (`_gate` and the events path in `join.py`), then either converges or
  records in its test which case it legitimately parses differently. That
  work is outside this goal's acceptance criteria; it depends on the corpus
  existing, not on this goal closing.

### 4.2 The verified record carries a typed verdict

The `verified` gate's detail gains a fixed shape after the tree:

    gate: verified tree:<f> — checks: <commands and result>; review: <findings>; reviewer: <label>[ session:<qualified id>]

where `<findings>` is `none` or a list of finding records separated by
commas:

    <severity> <disposition> <short text>
    severity    := important | minor
    disposition := addressed | deferred
    short text  := one or more characters, none of them a comma or a semicolon

Whitespace separates the three parts, so `addressedness` is not a
disposition and the finding is malformed.

The two delimiters are reserved: a comma ends a finding, a semicolon ends a
field, and a finding with empty text is malformed. The corpus carries the
cases: text containing a comma, text containing a semicolon, empty text, and a
well-formed two-finding list.

- Field parsing applies only when the detail contains `review:`; a detail
  without it is free text, as every note on record today is, so the
  semicolons in those notes are not a problem.
- `checks` is free text (the commands and what they printed); in the new
  shape it may not contain a semicolon, which is the field separator.
- Each finding is one record, so the policy in section 3.6 is checkable:
  an `important deferred` finding in a `verified` note is `malformed` under
  section 4.1. A `minor deferred` finding is well-formed and stays visible to
  the reader and to obs. Counts are derived from the list, never written
  beside it, so there is no count to keep consistent.
- **A malformed gate note in the history.** Today `gates()` skips what it
  cannot parse and the derivation reads the last note it kept, so a
  well-formed `verified` followed by a malformed one would report the earlier
  verification as current. The rule is the opposite: a malformed note that
  names a state is a failed attempt at that state, and the history is reduced
  in order. A well-formed gate is appended. A malformed note naming a known
  state cancels the gates at the tail of the effective history that name that
  state, stopping at a back edge, which nothing cancels (a `scoped` gate
  whose detail begins `— invalidated:` or an `implementing` gate whose detail
  begins `— reopened:`; the words elsewhere in a note are prose); a malformed note naming an unknown state cancels nothing. A
  malformed note is *live* until a later well-formed gate supersedes it. A
  live one is reported as `<state> (inconsistent: malformed gate at note <i>:
  <why>)`; a superseded one is kept as a diagnostic in the JSON output
  (`malformed: [{note, state, why, superseded}]`) and not in the rendered
  inconsistency, so a corrected note closes cleanly. When no effective gate
  remains, an `idea`, `todo` or `doing` record is `captured` and a `done`
  record is `closed`, each with the inconsistency; `outside` stays reserved
  for a record with no gate note at all. So `verified` then malformed
  `verified` reports `implementing (inconsistent: …)`; `implementing` then a
  malformed `verified` reports the same; `verified`, `implementing —
  reopened`, then a malformed `implementing` reports `implementing
  (inconsistent: …)` with the reopen standing; `verified`, malformed
  `verified`, `verified` reports a clean `verified` with the failed attempt
  superseded; a `done` record whose only gate note is malformed reports
  `closed (inconsistent: …)`. The plan's derivation step covers these
  sequences through the derivation, not only the parse of the single note.
- `reviewer` is two parts. The label is the form the tracker uses for `agent`
  (`<harness>/<model>`), or `human`, or `none`. It is metadata: it says what
  kind of reviewer was used and cannot distinguish the implementer from a
  fresh reviewer on the same model. The optional `session:` is the reviewer's
  qualified session id in the charter's form (`<harness>:<native id>`: a
  lowercase harness name, a colon, a non-empty id; anything else makes the
  note malformed) when the flow can obtain one: a Codex reviewer's thread id, a cross-harness
  review (ai-fc26cf), a human's absence of one. A Claude Code subagent shares
  the controller's session id (ai-80b836), so a subagent review carries no
  usable session and writes only the label.
- What this substantiates and what it does not. The shape closes the grammar
  gap the charter names: there is a structured reviewer field. It does not
  substantiate independence or which review covered the tree; both stay
  claimed until obs can join a `session:` to an observed session that read
  the diff at `<f>`. The charter's rule stands: unsubstantiated review remains
  unknown, not failed. The step's text says so in the skill.
- `none` is written when no independent review happened. The skill forbids
  closing on it; writing it honestly is better than an unparseable claim, and
  obs reports it as a finding.
- Existing notes keep parsing: a `verified` note without `review:` is a gate
  with the verdict absent and reports `verified (no verdict)`; one with a
  `review:` that fails the grammar is `malformed`. `flow-state` reports a
  well-formed verdict as `verified (findings: <important addressed>/<minor
  addressed>/<minor deferred>, <label>)`.
- The flow skill's gate table and the flow spec section 3.2 are updated to the
  shape in the same step.

### 4.3 Ideas filed beside the goal

- obs: review findings per task and per reviewer from the verdict shape, as a
  consumer of the cost-per-outcome join. Depends on this goal.
- ai: the Jev-style probe from section 3.6, over the verified gates on record.
  Depends on this goal.

## 5. What this does not do

- No library of typed steps, no work algebra, no flow DSL. A second concrete
  flow is still the precondition for factoring blocks (ai-da52b7) and for
  `flow-state` reading its machine from data.
- No change to the harness loop, no wrapper around the model's turn.
- No implicit effects; no retrofit of per-figure class labels onto
  `flow-state` output. The classes are a rule for authors and reviewers, and
  the one place they are surfaced mechanically stays obs.
- No new prose in `AGENTS.md`. The instruction file is being pruned
  (ai-9ec1eb); this spec is the reference, and the flow skill and the relay
  design are where the rules already bind.
- No change to relay or tasks code. Both already satisfy the rules; the spec
  cites them as the model to copy.

## 6. Verification

For the spec: the self-review in the brainstorming skill (no placeholders, no
contradiction with the flow spec's section 3 or the charter's classes), and a
check that every "already holds" claim in sections 3.1, 3.3 and 3.5 names the
file or command it describes. The human review at the `designed` gate judges
whether the lens is worth having.

For the steps: 4.1 is verified when `flow-state`'s parsing entry point passes
the corpus, the derivation still reports `verified (no verdict; inconsistent: verified gate without tree:<hash>)` for
the tree-less case, and the corpus contains every shape on record; obs's run
over the same corpus is obs-8ad564's own check and not a condition here, which
removes the cycle between this goal and an idea that depends on it. 4.2 is
verified when `flow-state` reports the findings for a note in the new shape,
reports `malformed` for an `important deferred` one, and still reports
`verified` for every existing verified note, and the skill and spec tables show
the shape. The flow runs this task, so the goal's own `verified` gate is the
first note written in the new shape.

## 7. Decomposition

| Task | What | State |
| --- | --- | --- |
| ai-634de8 | this spec; goal for the steps | scoped, spec drafted, review round 1 applied |
| step 1 (at `planned`) | gate-note grammar, corpus, `parse_note` entry point (4.1) | not filed |
| step 2 (at `planned`) | finding records and reviewer field in the verified note, skill and spec tables (4.2) | not filed |
| obs-8ad564 | obs entry points run the vendored corpus | idea in obs; depends on the corpus, verified there |
| obs-f161b5 | review findings per task and reviewer | idea in obs, depends on ai-634de8 |
| ai-a15e38 | Jev-style bounded question over past verified gates | idea, depends on ai-634de8 |
| ai-99ea5d, obs-abfcf9 | eval case probe; eval records goal | filed 2026-09-22, both depend on ai-634de8 |
| ai-da52b7, ai-b9ab40, ai-21ea5d | noted: block shape, second-flow shape, guard kind | notes only |
