# Turn-boundary gate: a Stop guard on held claims, and the rules it enforces

Tasks: ai-21ea5d (the guard), ai-c62995 (what a park must say; no parking
between increments), ai-804671 (no waits on untracked background work),
ops-ed76fe and tack-89a1d1 (the guard reads the Stop input's running children;
the reason is a few lines).
Goal: ai-756baa. Brief: `docs/notes/2026-09-21-flow-gates-brief.md` (§4
alternative 1, §5 probe findings). Framing:
`docs/specs/2026-09-21-functional-core-design.md` §3.4 (guard vs observer).

## 1. Problem

The recorded failure class of the flow is the turn boundary: a turn ends
while work is still owed and nobody is told. Four incidents, in three shapes,
are on record:

| Date | Record | Shape |
| --- | --- | --- |
| 2026-09-19 | ai-c62995 | An agent parked a claimed, unblocked task between ordinary red-green increments. |
| 2026-09-19 | ai-c62995, ai-80b836 | A subagent with everything in hand ended its turn waiting on a background monitor and never resumed: an **abandoned claim**. |
| 2026-09-22 | ai-6c8245 note | A controller ended a turn with its Task 5 implementer still running and a report that named neither the child nor the next review. |
| 2026-09-24 | ai-804671 | A subagent detached `just gate` with `&`, armed a Monitor, and waited two hours for a notification the harness never tracked; the controller relayed "may resume on its own" unchecked. |

The rules already say what should have happened (AGENTS.md "Decisions", last
bullet; flow skill rule 5; tasks skill rule 5). Prose alone did not hold. The
harness can check one part of it mechanically: *this session holds a live
claim and is ending its turn*.

## 2. What the harnesses and tasks allow

From the ai-80b836 probe (2026-09-21):

- A Stop hook refuses the turn end in Claude Code and Codex with
  `{"decision":"block","reason":…}` on stdout; the reason is fed back to the
  model as the next instruction.
- The harness then retries the stop with `stop_hook_active: true`, and a hook
  must let that retry through or it loops. **So a block is a one-shot
  interruption, not a lock:** the model gets one mandatory turn to act on the
  reason, then may end regardless. The design leans on the reason text for
  that reason; it cannot force a park.
- Claude Code: `session_id` in the hook input equals `CLAUDE_CODE_SESSION_ID`,
  under which `tasks start` claims. A subagent's `tasks start` claims under the
  **controller's** session. A Stop fires in the subagent's context too, with the
  same `session_id` and nothing distinguishing it (only `SubagentStop` carries
  an `agent_id`, and it cannot block), so a subagent is blocked once.
- Codex: since tasks-3190fb, a claim's session is the thread id tagged
  `codex:<id>`, liveness by TTL; the hook input's `session_id` is the thread id.
  The native path (no `TASKS_SESSION` override) is unverified end to end.
- A blocked model with nothing to do parked with next step "Waiting for next
  steps": a vacuous park, which obs's stall proxy counts as handled.

From the spec review (2026-09-24), reproduced with a throwaway registry:

- **`tasks prime --all-projects` is not a claim read.** It builds `.doing` from
  the task files in each project's *registered* checkout and joins claims onto
  them. A task that exists only in a worktree branch (a plan step added there)
  is invisible: with a live claim on `zz-6fec1d` in a worktree, local `prime`
  listed it and `prime --all-projects` returned `"doing": []` with no warning.
- **`prime --all-projects` degrades silently.** An unreachable registered
  project is skipped with a warning and exit 0, so a successful parse does not
  mean every project was read.
- **The claim store does not live in any checkout.** Claims are kept per
  prefix under `$XDG_STATE_HOME/tasks/claims/<prefix>.toml`, outside git and
  shared by every worktree, and liveness is computed from the claim alone. A
  claim read needs the registry and the store, never a task file.
- **Codex does not wake an idle controller.** The installed Codex guidance
  (superpowers `codex-tools`) says completion mail cannot wake an idle
  controller; `wait_agent` with a long timeout covers the wait. Claude Code's
  tool contract says the opposite: a background subagent or a
  `run_in_background` command re-invokes the session when it finishes. Neither
  has been probed against a controller that ended its turn.

From the live checks and wake probes (2026-09-24, ai-2f1271, ai-00ccb6):

- Claude Code 2.1.282 no longer fires Stop in a subagent's context — only the
  controller is blocked;
- Codex 0.156.1 native identity verified end to end (controller);
- a Codex subagent's `tasks start` falls back to `sid:<pid>` and is dead at
  once, so its claim is invisible to the guard (tasks-0c2c39);
- the wake probe found Claude Code starts a new controller turn for both a
  subagent and a `run_in_background` command, Codex for neither, so
  `CHILD_WAKES` is `{claude-code: True, codex: False}`.

From the Stop-input probe (2026-09-29, ops-ed76fe):

- Claude Code's Stop input carries `background_tasks`, a list of the work the
  harness tracks for the session: `{id, type, status, description}` plus
  `command` for a `shell` item and `agent_type` for a `subagent` item. A
  headless 2.1.284 session that ended its turn with one `run_in_background`
  command and one background subagent listed both with `status: "running"`.
  The same input carries `last_assistant_message` and `session_crons`.
- The fields are in the input schema inside the 2.1.282, 2.1.283 and 2.1.284
  binaries and not in the public hook documentation, so a release can change
  them without notice.
- A background command started by a subagent appears in the controller's
  list once the subagent has stopped.
- Only `running` was observed. `pending` is taken from the schema's own
  description of the field, and the 2.1.284 binary filters the list to those
  two statuses, so finished work is not listed.
- The binary names more kinds than the two probed, among them `monitor`,
  `workflow` and `remote_agent`. Whether the end of one starts a controller
  turn has not been probed.

## 3. Design

Four changes: a claims read in tasks, the guard in ops, its wiring in this
repository, and the rules the guard's reason text points at.

### 3.1 The claims read (tasks)

A new read command, `tasks claims --all-projects`, answers exactly the
guard's question and nothing else:

```
tasks claims --all-projects
→ {"claims": [{"id", "prefix", "session", "live", "host", "worktree"}, …]}
```

- Its scope is always every registered prefix; `--all-projects` is accepted as
  the default, as `tasks quiet` accepts it, and there is no single-project form
  until a caller needs one.
- It reads the registry and, for each registered prefix, that prefix's claim
  store. It opens no checkout and no task file, so a worktree-only task's
  claim is listed and an unreachable checkout is irrelevant.
- A prefix with no store file has no claims; that is the normal state, not an
  error.
- **Coverage is all or nothing.** A registry it cannot read, or a store that
  exists and cannot be read or parsed, exits nonzero naming the prefix. There
  is no warnings array: no partial answer is ever printed with exit 0, so the
  guard never has to tell a coverage warning from an ordinary one.
- Liveness is the same computation `prime` uses (`ClaimInfo::of`), so the two
  never disagree about a claim both can see.

This is a tasks-project change, filed there (§7); the guard depends on it.

### 3.2 The guard (ai-21ea5d; code in ops)

`ops/hooks/claim-guard --harness claude-code|codex`, Python, in the idiom of
`claude-pretooluse` and `relay-guard`: a pure function and a thin shell.

```
decide(harness, event, claims) -> Reply     # pure; the tested core
Reply = Allow | Block(reason)
```

`event` is the parsed hook input; `claims` is the parsed output of
`tasks claims --all-projects`, or the error that reading it raised. The read
is passed in as a function, so a stop that step 3 allows never runs it. The
order is fixed:

1. `stop_hook_active` is `true` → **Allow**. Checked first, so no later
   failure can turn the harness's retry into a loop.
2. Input is not a JSON object (or nests too deep to parse), or `session_id`
   is not a non-empty string →
   **Block**, reason names the defect. (If the input is so malformed that step
   1 cannot read the flag, the block repeats on the retry; this is the one
   unbounded case, it has never been observed, and fail-closed plus a visible
   reason is §3.4's rule. The user interrupts.)
3. On a harness whose `CHILD_WAKES` entry is true: `background_tasks` lists
   an item of type `shell` or `subagent` whose `status` is `running` or
   `pending` → **Allow**, without the claims read. Those are the two kinds
   the wake probe covered; such a child is running and its completion starts
   the next turn, so the turn end is the one §3.5 asks for. Anything else the
   guard cannot vouch for allows nothing: the guard goes on to step 4 and, if
   it blocks, the reason says it could not see children and why (§3.3). That
   covers a list that is absent, or is not a list of objects each with a
   string `type` and `status`; a status other than those two; a list holding
   only other kinds; and an empty list beside a non-empty `session_crons`. On
   a harness whose entry is false this step is skipped whatever the input
   holds.
4. The claim read failed — `tasks` missing, nonzero exit, timeout at 10 s,
   output that is not `{"claims": [...]}` with every field of §3.1 → **Block**,
   reason: the claims could not be read, with the error; the reason carries the
   full option set of §3.3, since a claim may still be held; if you hold none,
   say so and end.
5. Held claims: every claim whose `live` is true and whose `session` is the
   input `session_id`, or that id tagged with a known harness
   (`claude-code:<id>`, `codex:<id>`). None → **Allow**. Some → **Block**
   with the reason in §3.3.

The shell reads stdin, runs the claims read with the timeout, calls `decide`,
prints `{"decision":"block","reason":…}` or nothing, and exits 0. Every
exception becomes a Block through steps 2 and 4, never an exit code the harness
might read as a pass. The guard never writes, never logs, and never indexes
(obs: "indexing never runs from a harness hook"). The evidence of a block is
the reason in the session transcript, which `session-logs` already reads;
recording, if ever wanted, is a separate observer (§3.4).

`--harness` is required and names the entry's own harness. It selects the
running-child branch of the reason (§3.3); session matching still accepts
both tags, because the tag records which identity level resolved the claim,
not which harness is asking.

### 3.3 The reason text

The reason is the guard's real output; the model acts on it with one turn.
It is also printed in full in the terminal on every block, under the
harness's own "Stop hook error" label, which no setting hides or renames. So
it is a few lines: what is held (id and recorded worktree), what the guard
saw of children, the ways to end, and a pointer to the rules of §3.5, which
the agent already has in its instructions. On Claude Code:

> You are ending a turn while this session holds a live task claim:
> `ai-21ea5d` in `/…/ai`. No child the harness tracks is running, so nothing
> will start your next turn; a job detached with `&` or `nohup` never does.
> If the user told you this turn to stop, wait or only answer, use (2) with
> `--waiting-on user`, not (1). Otherwise do one of these before the turn
> ends:
> (1) Continue: the work is unblocked and yours.
> (2) Park: `tasks park <id> "<next step>"`, an action and who takes it,
> never a state; add `--waiting-on user --reason review|decision|approval`
> only when a person must act.
> (3) Done: `tasks done <id> "<what landed>"`.
> Decisions and Processes in your instructions give the rules.

That is about 700 characters for one claim; the first text was 1,633.

What the reason says about children depends on whether the harness restarts
an idle controller when a child finishes. The guard keeps one table,
`CHILD_WAKES`, and the text follows it:

- **Wakes, and the input listed the background work** (none of it in flight,
  or step 3 would have allowed): "No child the harness tracks is running, so
  nothing will start your next turn; a job detached with `&` or `nohup` never
  does."
- **Wakes, and the guard cannot vouch for what the input says** (any case
  step 3 of §3.2 lists): "The guard cannot see whether a child is running
  (*why*). If one the harness tracks is running and your last message named
  it, reply with one line naming it again and end; the stop that follows is
  allowed, and the child's completion starts your next turn; a job detached
  with `&` or `nohup` never does." This is the behaviour of 2026-09-28
  (ops-0633a8), kept as the fallback for a harness release that drops or
  reshapes the field and for kinds of work not yet probed.
- **Does not wake**: no sentence before the options, and a fourth option
  after them: "(4) A child is running: Do not end the turn. Wait on it with
  the harness's bounded wait (`wait_agent` with a long timeout), act on its
  result, and if the wait times out, check the child before waiting again. A
  job detached with `&` or `nohup` is never a running child." It is followed
  by the subagent sentence: "If you are a subagent, your turn's end is your
  final report: report and stop only when the assignment is complete or
  blocked on your controller or a person, and say which; if work remains or a
  check you started is still running, continue it or wait on it, then
  report."

The subagent sentence is conditional on purpose: an unconditional "report and
stop" would hand the 2026-09-19 and 2026-09-24 workers exactly the exit they
took. It is printed only where a Stop can fire in a subagent's context.
Claude Code 2.1.282 fires it in the controller only (§2), so the Claude Code
reason leaves it out.

`CHILD_WAKES` started as `{claude-code: False, codex: False}`. An entry
becomes `True` only when the controller-wake probe (§5) has shown it for that
harness for **both** kinds of child the rules name — a subagent and a
background command — since their completion paths may differ; one boolean is
kept because the rule an agent reads does not distinguish them. The safe text
is the default, not the hoped-for one. Since the 2026-09-24 probes it is
`{claude-code: True, codex: False}`.

The 2026-09-22 controller is the case the child sentence covers. On Claude
Code it is blocked only when no tracked child is running, and told so; a
controller that ends its turn with a report naming a running child is not
blocked at all. Option 2's wording is ai-c62995's rule; the `&` sentence is
ai-804671's.

### 3.4 Wiring (ai-21ea5d; this repository)

- `claude/settings.json`: a second `Stop` entry,
  `~/d/ops/hooks/claim-guard --harness claude-code`, beside familiar's. No
  `SubagentStop` entry: it cannot block.
- `codex/hooks.json`: `~/d/ops/hooks/claim-guard --harness codex` under
  `Stop`. Changing the file changes its hash, so Codex asks the user to trust
  it on next start (`codex/config.toml` `[hooks.state]`); that approval is the
  user's, and `codex/config.toml` already carries unrelated uncommitted edits
  in the main checkout, so the plan does not touch it.
- Not `.work` variants in this change: the work profile's repositories have
  not adopted tasks claims. Named here so its absence is deliberate.
- Relay: relay's `turn-end` kind already refuses on Stop and carries
  `stopHookActive`. A relay entry for the guard is a thin adapter over the same
  `decide`, like `relay-guard` over `claude-pretooluse`; it is filed as a task
  depending on ai-539508 (the cutover), not built now. Until then the native
  entries are the only authority, so there is no third one.

### 3.5 The rules (ai-c62995, ai-804671; this repository)

The guard points at rules; they must exist in the text agents read.

- **AGENTS.md "Decisions", last bullet** gains two sentences: a park's next
  step is an action with its actor, not a state; an unblocked task you hold is
  not parked between increments — continue until a blocker, a gate that needs
  a person, or the session ending.
- **AGENTS.md "Processes"** gains one bullet: never end a turn waiting on work
  the harness does not track. Run a long check in the foreground with a timeout
  that covers it, or with the harness's own background mechanism; never detach
  with `&` and wait on a monitor. A controller with a running child ends its
  turn only where the harness is known to restart it on the child's
  completion, and otherwise waits with the harness's bounded wait. A
  controller treats a child's "waiting on background work" as unverified:
  check the process or its output exists before relaying it. A worker's turn
  end is its final report: it reports and stops only when its assignment is
  complete or blocked on its controller or a person, never with its own check
  still running. After a wake-up, report what was observed; do not invent a
  late notification.
- **flow skill rule 5** gains the next-step sentence and a pointer to the
  Processes bullet; it already carries the observed-status report.
- The tasks skill (`agents/skills/tasks`) is vendored from the tasks project
  and is not edited here; if its rule 5 should carry the next-step sentence,
  that goes with the tasks piece (§7).

## 4. Alternatives considered

- **Build it as a relay guard only** and wait for the cutover. Rejected: the
  cutover (ai-539508) waits on four open pieces in three projects, and the
  failure is recurring now. The pure `decide` keeps the relay entry a small
  adapter later.
- **Keep `prime --all-projects` and fix its gaps.** Rejected: `prime` answers
  "what is the state of the work", joined to task files; a claim with no file
  in the registered checkout has no row to join to, and inventing one would
  change `prime` for every reader. The guard's question is narrower, and the
  store answers it without any checkout.
- **Read the claim store files from the guard.** Rejected: the TOML layout
  and the liveness rules (pid, boot id, TTL, relay handles) are tasks'
  internals; duplicating them in Python would drift.
- **Treat every `prime` warning as incomplete coverage.** Rejected: it blocks
  on ordinary warnings (uncommitted task files) and still misses worktree-only
  claims, which produce no warning.
- **Allow "report and end" for a running child everywhere.** Rejected by the
  review: Codex does not restart an idle controller, and Claude Code's
  restart is claimed, not probed. Wake is opt-in per harness on evidence.
- **Detect a running child from the transcript.** Rejected (ops-0633a8): the
  transcript format is undocumented and a child's state is spread over Agent
  launches, SendMessage resumes, Monitor tasks and repeated notifications.
  The Stop input's own list (§2) answers the same question in one field, and
  when it is missing the guard falls back to the blocking text.
- **Block a stop whose only running child is a background command.** A
  command that never exits (a server) is listed as running for as long as it
  lives, so a session that holds one is never blocked. Accepted: the input
  cannot tell a server from a test run, five days of blocks held no such
  case, and blocking every background command would bring back the block on
  a gate or build that is running, which is the common one.
- **Allow for every kind of background work the input lists.** Rejected by
  the review of ops-ed76fe: a monitor or a workflow may never finish, or may
  not start a turn when it does. A kind allows only after the wake probe has
  covered it, as `CHILD_WAKES` does per harness.
- **Count `session_crons` as a reason to allow.** Not done: no recorded turn
  end waited on one, and a scheduled wake-up was not probed. A turn end that
  has one blocks once with the fallback sentence, not with the claim that
  nothing will wake the session.
- **`tasks check` on Stop, or pre-commit gates** (brief §4 alternatives 2–3).
  Rejected for the reasons recorded there: no drift or skipped gate is on
  record.
- **Allow when the input is unreadable** instead of blocking. Rejected: §3.4
  makes a guard total and fail-closed; the loop risk is confined to a harness
  contract violation that has never been seen.

## 5. Verification

- **tasks (the claims read):** a claim on a task that exists only in a
  worktree is listed; an unreachable registered checkout does not change the
  answer; a prefix without a store file yields no claims and exit 0; a
  corrupt store exits nonzero naming its prefix; a live and a stale claim
  agree with `prime`'s `live` for the same task.
- **Unit (ops):** `decide` over a table — each probe case (own live claim →
  Block; another session's claim → Allow; parked, so no claim → Allow;
  `stop_hook_active` → Allow even with a held claim and even with a failed
  read), the Codex tag `codex:<id>` → Block, a stale claim (`live: false`) →
  Allow, malformed input → Block, failed read → Block, a claims document
  missing a field → Block; a running or a pending `shell` or `subagent` with
  a held claim → Allow, and the read is never called, also when a monitor is
  listed beside it; an empty list → Block saying no tracked child is running;
  an absent or malformed list, an unknown status, a list of other kinds only,
  a malformed item beside a running child, or a scheduled wake-up with an
  empty list → Block saying the guard could not look and why, and Allow when
  no claim is held; a running child on a harness that does not wake → Block;
  a running child with no `session_id` → Block; input nested too deep to
  parse → Block. The reason names every held id with
  its worktree, carries the child text `CHILD_WAKES` selects for each
  harness, stays under 800 characters on Claude Code, and on a harness that
  does not wake carries the conditional subagent sentence (complete or
  blocked → report; work or a check outstanding → continue or wait), never a
  bare "report and stop".
- **Stop input, live (ops-ed76fe):** a headless Claude Code session with a
  Stop hook that writes its input to a file starts one background command and
  one background subagent and ends its turn; the captured input is then fed
  to the real entry with a stub `tasks` that reports a held claim → no
  output. Rerun it when a Claude Code release changes the Stop input.
- **Shell (ops):** the entry run with a stub `tasks` on `PATH` (held claim,
  none, nonzero exit) and with no `tasks` on `PATH`, asserting stdout and exit
  0. The timeout is exercised in the unit tests with an injected runner that
  raises `TimeoutExpired`, so the suite never waits 10 s.
- **Worktree regression, live:** in a throwaway registry
  (`XDG_CONFIG_HOME`, `XDG_STATE_HOME` under a temp dir), a task added and
  started inside a worktree, then the real guard fed a Stop input for that
  session → Block naming the task. This is the review's reproduction, run
  against the guard.
- **Stop cases, both harnesses:** rerun ai-80b836's five cases against the
  real entry in a throwaway `CLAUDE_CONFIG_DIR` and `CODEX_HOME`, Codex
  **without** a `TASKS_SESSION` override — closing the brief's open
  native-identity item. Also the Codex subagent case, unprobed so far.
- **Controller wake, both harnesses, both kinds:** a controller starts a child
  that sleeps briefly and exits, then ends its turn; pass if a new controller
  turn starts on the child's completion without user input, within a bound.
  Run once with a subagent as the child and once with a background command
  (Claude Code: `run_in_background`; Codex: its own background mechanism, or
  recorded as absent). A harness's `CHILD_WAKES` entry becomes `True` only
  when both runs pass; any failure leaves it `False`, and each result is
  recorded on ai-21ea5d.
- **Gates:** the tasks project's and ops's test suites; `tasks check` here.

## 6. Rollout and judgment

The guard ships live on this host with the wiring change. obs's stall proxy
alone cannot judge it (a park counts as handled). A follow-up task, deferred
14 days, reads Stop blocks from session logs with `session-logs` and sorts
each by what the blocked turn did: resumed work, a park with an action, a
park with a state (vacuous), a bounded wait on a child, a report-and-end for
a running child, or a bare end on retry. That count decides whether the
reason text needs work, and whether ai-c62995's over-parking shape moved.

A first count ran early, on 2026-09-29 (ops-552425), over the Claude Code
turn ends of 2026-09-25 to 2026-09-29. Of 1,144 turn ends that ran the guard,
388 were blocked. 359 of those drew a reply with no tool call and then the
allowed repeat stop, and 355 of the 359 were followed by a child's completion
notice: the first message had already been the report §3.5 asks for. 11
blocks led to a recorded park or done. The reason-text fix of 2026-09-28
(ops-0633a8) shortened the repeat reply and left the block rate as it was,
which is why the guard now reads the Stop input (§3.2 step 3). Codex showed
no blocks in 143 rollouts. The deferred count still runs, against the guard
as it now stands.

## 7. Decomposition

One implementation plan drives all of it
(`docs/plans/2026-09-24-turn-boundary-gate.md`), so every piece is a plan step
under ai-21ea5d, tagged with the repository it changes, rather than a task in
tasks or ops that would mirror the step.

| Task | Where | What | Depends on |
| --- | --- | --- | --- |
| new, tasks | tasks | `tasks claims --all-projects` (§3.1) and its tests | — |
| new, ops | ops | `hooks/claim-guard` and its tests (§3.2, §3.3, §5 unit and shell) | the tasks piece |
| ai-21ea5d | ai | wiring (§3.4); live checks: worktree regression, Stop cases, controller wake (§5) | the ops piece |
| ai-c62995 | ai | AGENTS.md and flow rule text (§3.5, first bullet) | — |
| ai-804671 | ai | AGENTS.md Processes bullet (§3.5, second bullet) | — |
| new, ai, blocked | ai | relay entry for the guard | ai-539508 |
| new, ai, deferred 14d | ai | rollout judgment (§6) | ai-21ea5d |

## 8. Out of scope

- Enforcing that a park's next step is non-vacuous (the tool could reject
  "waiting…"): a tasks-side change, only if §6 shows vacuous parks persist.
- The agent side of the host broadcast (ai-21aaa3), another turn-boundary
  hook, waits on relay.
- The `.work` harness configurations.
- `prime --all-projects` omitting worktree-only tasks for its other readers:
  a tasks idea, filed alongside the tasks piece, not fixed here.
