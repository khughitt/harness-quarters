# Turn-boundary gate: a Stop guard on held claims, and the rules it enforces

Tasks: ai-21ea5d (the guard), ai-c62995 (what a park must say; no parking
between increments), ai-804671 (no waits on untracked background work).
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
`tasks claims --all-projects`, or the error that reading it raised. The order
is fixed:

1. `stop_hook_active` is `true` → **Allow**. Checked first, so no later
   failure can turn the harness's retry into a loop.
2. Input is not a JSON object, or `session_id` is not a non-empty string →
   **Block**, reason names the defect. (If the input is so malformed that step
   1 cannot read the flag, the block repeats on the retry; this is the one
   unbounded case, it has never been observed, and fail-closed plus a visible
   reason is §3.4's rule. The user interrupts.)
3. The claim read failed — `tasks` missing, nonzero exit, timeout at 10 s,
   output that is not `{"claims": [...]}` with every field of §3.1 → **Block**,
   reason: the claims could not be read, with the error; the reason carries the
   full option set of §3.3, since a claim may still be held; if you hold none,
   say so and end.
4. Held claims: every claim whose `live` is true and whose `session` is the
   input `session_id`, or that id tagged with a known harness
   (`claude-code:<id>`, `codex:<id>`). None → **Allow**. Some → **Block**
   with the reason in §3.3.

The shell reads stdin, runs the claims read with the timeout, calls `decide`,
prints `{"decision":"block","reason":…}` or nothing, and exits 0. Every
exception becomes a Block through steps 2–3, never an exit code the harness
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
It names what is held (id and recorded worktree) and the legitimate ways to
end:

> You are ending a turn while this session holds a live task claim:
> `ai-21ea5d` in `/…/ai`. Before the turn ends, do one: An instruction the
> user gave this turn (stop, wait, only answer) stands over Continue: park
> with `--waiting-on user` naming what they must decide, then end.
> (1) **Continue** — the work is unblocked and yours; keep going.
> (2) **Park** — `tasks park <id> "<next step>"`: the next step is an action
> and who takes it ("rerun `just gate` in .worktrees/x, then dispatch the
> Task 6 review"), never a state ("waiting for next steps"). Add
> `--waiting-on user --reason review|decision|approval` only when a person
> must act.
> (3) **Done** — `tasks done <id> "<what landed>"` if it is finished.
> (4) **A child is running** — *per harness, below.* A job detached with `&`
> or `nohup` is never a running child: nothing will re-invoke you.
> If you are a subagent, the claim is your controller's but the assignment is
> yours, and your turn's end is your final report: nothing wakes you again.
> Report and stop only when the assignment is complete or blocked on something
> only your controller or a person can resolve, and say which. If work remains
> or a check you started is still running, continue it, or wait on the check in
> the foreground or with the harness's bounded wait, then report.

The subagent sentence is conditional on purpose. The same `session_id` means
the guard cannot tell a worker from its controller (§2), so the reason must be
right for both; an unconditional "report and stop" would hand the 2026-09-19
and 2026-09-24 workers exactly the exit they took.

Branch 4 depends on whether the harness restarts an idle controller when a
child finishes. The guard keeps one table, `CHILD_WAKES`, and the text
follows it:

- **Wakes** (the harness restarts the controller): "End the turn with a report
  naming the child, what it will produce, and who acts next; its completion
  starts your next turn."
- **Does not wake**: "Do not end the turn. Wait on the child with the harness's
  bounded wait (`wait_agent` with a long timeout on Codex), act on its result,
  and if the wait times out, check the child before waiting again."

`CHILD_WAKES` starts as `{claude-code: False, codex: False}`. An entry becomes
`True` only when the controller-wake probe (§5) has shown it for that harness
for **both** kinds of child the rules name — a subagent and a background
command — since their completion paths may differ; one boolean is kept because
the rule an agent reads does not distinguish them. The safe text is the
default, not the hoped-for one. Claude Code's contract
claims the wake, so its probe runs first; Codex's guidance denies it, so its
probe confirms the default.

The 2026-09-22 controller is the case branch 4 covers. Until Claude Code's
wake is proven, it is blocked once and told to wait on its child; after, it
is blocked once and told to write the report the incident lacked. Branch 2's
wording is ai-c62995's rule; branch 4's `&` sentence is ai-804671's.

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
  missing a field → Block, and the reason names every held id with its
  worktree, carries the branch-4 text `CHILD_WAKES` selects for each
  harness, and carries the conditional subagent sentence (complete or blocked
  → report; work or a check outstanding → continue or wait), never a bare
  "report and stop".
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
