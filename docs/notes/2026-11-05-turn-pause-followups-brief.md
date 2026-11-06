# Turn-pause follow-ups: approval waits, migration and latency

## Problem

Keep turn-pause safeguards from interrupting ordinary work because of user approval
waits or an incompatible state change, without adding a service without evidence
that it is needed. This scope pass covers hq-a639e4, hq-14bab1 and hq-33ad66.
These are agent-authored follow-ups of hq-9aa713; their filing session records the
user asking to execute the existing plan and later approving activation, rather
than requesting these three additions individually.

## Evidence at scoping

- At main `7abc23c3`, `tools/turn_pause/events.py` recognizes question tools and
  `ExitPlanMode` as user waits. `adapters.py` has no `PermissionRequest` event.
  The original final-review ruling deliberately deferred permission-prompt
  handling pending evidence. Approval/cancellation boundaries remain unknown.
- Main still reads unversioned state with strict turn-field matching
  (`tools/turn_pause/state.py`); `hq pause` exposes only status and limits.
  The unmerged `fix/hq-2dd09b` branch at `a352cda4` already contains versioned
  records, explicit offline conversion in `tools/turn_pause/migrate.py`, and
  `docs/runbooks/turn-pause-activation.md`. hq-c58737 owns its activation gate;
  this is implemented branch capability, not active main behaviour.
- hq-33ad66's original 500-sample sets reported p99 47–48 ms, with one 65 ms
  result under load. The newer hq-e60ecb branch evidence records a passing
  1000-sample check after optimization at `97b2c670`: p99 31.93–47.43 ms across
  Claude/Codex serial/concurrent cases with 128 seeded events. This synthetic
  result does not establish production latency or the benefit of a service.

## Constraints

Preserve fail-closed state handling and existing pause limits. Reuse hq-2dd09b's
remediation goal and hq-c58737's converter/activation work; do not create another
migration implementation. At scoping, its branch was separately owned and unmerged;
activation required the existing operator window. The evidence review below records
the subsequent merge and activation; these branch descriptions are historical.
Existing coverage research
hq-a5a449, hq-2bc2d6 and hq-7bed89 asks different questions and is not duplicated.
No live hooks, state, host services or new model sessions change in this pass.

Scope-pass verification: `tasks check` and `just check-hygiene` passed; the three
members each have one stamped audit and remain unclaimed. Nine rows remain in the
review queue. This pass changed only records and this brief, so no test suite was
run. No new worktree, unmerged branch, surviving process or push was created;
`host-load --section session` reported nothing left running. The pre-existing
`agy/settings.json` edit remains untouched. The existing remediation branches
remain with their current owners and activation gates.

## Alternatives

1. **Lean:** review installed hook definitions, existing code and retained
   request/result sequences first. Implement wait accounting only after its
   boundaries are established; explicitly report missing evidence.
2. Run a new interactive permission probe if the local review cannot settle the
   boundary. Recommend its smallest scope separately; this brief authorizes no
   probe, metered experiment or live activation.
3. Replace the hook with a resident process. Defer: the newer candidate meets the
   existing latency target locally, and no service benefit has been measured.

## Boundary questions

Which existing Claude Code and Codex events identify the start and end of a
permission wait, including approval, denial and cancellation? Can those events
exclude only the waiting agent's interval while concurrent work still counts?
The bounded local evidence review below names the missing
observation; a missing observation is not permission to invent a fallback.

## Proposed decomposition

- Reuse hq-2dd09b as the goal; hq-f96f58 is the P2, small, mid-complexity, direct
  local evidence review. It wakes hq-a639e4, which stays an idea dependent on it.
- hq-14bab1: dropped with user approval on 2026-11-05 because hq-c58737 and its completed
  branch step hq-cc91d4 cover explicit migration and activation/rollback guidance.
  The drop does not imply that migration has been activated.
- hq-33ad66: shelve until 2026-12-05, revisiting earlier for a measured normal-call
  latency breach or a user report of noticeable hook delay. Prefer local
  optimization before reconsidering a separately approved service.

## Permission-wait evidence result — 2026-11-05

**Verdict:** existing local evidence does not establish a complete permission-wait
interval for either harness. Do not implement wait subtraction from a
`PermissionRequest` alone. hq-f96f58 closes on this evidence report; hq-a639e4 stays
an idea and receives the findings for a separately scoped interactive probe.
Approval, human denial and pending-permission cancellation all need observations
that are absent here. Ordinary execution and child-call attribution are observed.

The review used repository source, installed definitions, retained probes and
session records only. No model session, interactive probe, live hook/state change
or service was started. Installed versions were **Claude Code 2.1.318** and
**codex-cli 0.166.0**. The portable
[evidence attachment](../../tasks/files/hq-f96f58/permission-wait-local-evidence.json)
preserves selected source excerpts and projected records, source hashes, line or
byte locations, capability-fact results and the exact limits of each source. It is
selected evidence, not a full raw transcript or a new capability probe.

### Authority and current code

The human goal inherited through hq-2dd09b is fewer premature interruptions while
preserving safeguards. The permission-specific addition came from the agent's
final-review ruling on hq-9aa713, not a separate human request. Its attached
`plan-ledger-2026-11-01.md`, lines 228–230, fixes `ExitPlanMode` and deliberately
defers permission prompts pending a probe. The task-filing session
`codex:01a1ac00-5258-7c73-9788-26641df81fef` contains the human's scope request and
later drop approval; its assistant filed this bounded evidence review. This
session's human request selects hq-f96f58; it grants no live-probe authority.

Main at pickup was `5a7be0168a9098aa7216de50ff512c83e5a293bc`.
The formerly unmerged reliability revision `a352cda4db55656c2efa9390d6b5738affea829d`
is now its ancestor, and the old `fix/hq-2dd09b` branch/worktree is absent. The
parent's November 5 closeout notes record activation. Main now has versioned
storage, offline conversion and durable history; these are no longer merely
branch intentions. The observed permission-accounting gap remains:

- `events.py` defines only question tools and `ExitPlanMode` as user waits.
- `adapters.py` accepts neither `PermissionRequest` nor a permission-resolution
  event. A successful `PostToolUse` closes a call after execution.
- `counters.py` charges an entire gap while any call is in flight. Without an open
  call, gaps shorter than 600 seconds still count. Merely removing a pending call
  would therefore continue charging short waits.
- The installed personal Codex hooks route `PermissionRequest` to relay, but not
  turn-pause. Claude routes `Notification:permission_prompt` to relay; its
  turn-pause wiring has no permission lifecycle. Configuration proves routing,
  not that the harness emitted the event in a particular case.

These statements come from the tree and installed settings. They do not redefine
the broader goal or establish a permission-wait implementation contract.

### Claude Code

**Declared start candidate:** the installed 2.1.318 bundle defines
`PermissionRequest`. Its embedded hook table calls it a pre-permission-prompt
event. Its actual payload schema and constructor include session/agent context,
tool name, input and suggestions, but omit `tool_use_id`; the embedded help claims
that field is included. The dispatcher receives a tool-use id separately. This
internal disagreement makes the actual command-hook payload and call correlation
an explicit missing observation. Matching by tool name/input is not a reliable
substitute when concurrent calls can be identical.

**Observed request/result:** the retained personal smoke on 2.1.304 has
`toolu_01VqaGnuDZ7epgeaPKzQ7Qci`, Bash `touch approval.marker && sleep 7`, requested
at `2026-10-22T11:17:35.379Z` and successfully returned at
`2026-10-22T11:18:19.533Z`. The source is the session
`f169ae86-8c59-45c9-bc98-15c77deab001`, lines 93 and 95. The
`manual-mode-asks-for-sleep` fact records that this command prompted, whereas plain
`sleep 7` did not. The 44.154-second bracket includes execution and other overhead;
it provides no timestamp at which the user approved. Subtracting seven seconds
does not establish an exact wait.

**Observed controls:** hq-fe672f's 2.1.316 `claude-main-1/hooks.jsonl`, lines 4–5,
contains an ordinary allowed Bash `PreToolUse`/`PostToolUse` pair with the same id.
Lines 13–16 show separate root and child calls overlapping, with `agent_id` only
on the child's events. These establish call/agent attribution for those events,
not attribution or timing of a permission prompt. All six retained Claude hook
logs in that probe set contain zero `PermissionRequest` events; absence in these
runs does not show the hook is unavailable.

| Case | What the local evidence establishes | Missing observation |
| --- | --- | --- |
| Approval | A historical prompted tool ultimately succeeded. `PostToolUse` is observed after ordinary execution. | The current-version request payload and a resolution/execution-entry boundary before tool completion. |
| Human denial | A hook-denied call has no successful `PostToolUse` in the retained probes. | Human denial's actual event sequence and pending-call cleanup. Hook denial is not human denial. |
| Cancellation | 2.1.318 defines `PostToolUseFailure` with optional `is_interrupt`. Older question-tool probes record Esc interruption. | Whether Esc, turn interruption and session close while permission is pending emit a correlated end event. Question-tool cancellation does not establish permission cancellation. |

`PermissionDenied` is not an all-purpose answer event: 2.1.318's embedded help
specifically describes auto-mode denial. No captured manual denial in this review
proves otherwise. `PostToolUse.duration_ms` is declared to exclude prompt and hook
time, but the post-event timestamp minus that duration is not an observed approval
timestamp and does not recover ordering across concurrent events. A notification
that a prompt exists likewise supplies no resolution boundary.

### Codex

**Declared start candidate:** installed 0.166.0 defines `PermissionRequest` among
its hook events. Its event-name table includes `Interrupt`, but no dedicated
permission-resolution event. This is an installed declaration, not a finding that
no other observable route exists. The retained 0.165.0 `core/src/hook_runtime.rs`
at lines 266–306 dispatches a permission hook and returns its optional decision;
its hook-start/completed lifecycle describes the hook's execution, not the user's
later answer. Its pinned source hash was checked. It remains historical evidence,
not proof of 0.166.0 payloads or cancellation behaviour.

**Observed request/result control:** hq-fe672f's 0.166.0
`codex-main-1/hooks.jsonl`, lines 4–5, records Bash `echo probe-shell` with id
`exec-686eaa3f-45fd-4ead-8bd1-39bbc719fa36`: `PreToolUse` at
`1793535090.8648672`, `PostToolUse` at `1793535091.0254843`. Lines 15–16 provide
a child pair with its own `agent_id`. The session used `bypassPermissions`; this
is deliberately an ordinary-execution control, not an approval sequence. All
thirteen retained Codex hook logs in that probe set contain zero
`PermissionRequest` events. No actual escalation request/reply sequence was found
in the bounded retained hook/protocol captures inspected here.

**Protocol possibility:** retained generated 0.166.0 app-server types declare
`item/commandExecution/requestApproval` parameters with `threadId`, `turnId`,
`itemId`, `startedAtMs` and optional `approvalId`. Replies distinguish `accept`,
`acceptForSession`, amendment decisions, `decline` and `cancel`.
`serverRequest/resolved` carries `threadId` and `requestId`, without the decision.
Multiple callbacks may share an item id, so any eventual observer would need the
request/callback identity as well. These are declarations, not captured permission
events. hq-d85ede's recorded resolved-notification observation concerns
`requestUserInput`, not command approval. It does not verify this permission route
or authorize adding an observer/service.

| Case | What the local evidence establishes | Missing observation |
| --- | --- | --- |
| Approval | An installed start-hook declaration and generated approval request/reply types exist. Ordinary start/end hooks are captured. | A genuine escalation, actual hook payload/call mapping, answer timing and execution-entry event on 0.166.0. |
| Human denial | Generated replies include `decline`; hook-denied calls lack a successful post event in retained probes. | A captured human decline and the exact hooks/result cleanup it emits. |
| Cancellation | Generated replies include `cancel`; the installed hook table includes `Interrupt`. | Pending-permission Esc/turn/session cancellation, its correlation, and any resolution/interrupt ordering. |

The captured running-command cancellation in `codex-cancel-1/hooks.jsonl`, lines
5–6, closes a Bash call after interrupting its process. It is not cancellation of
a pending approval. The existing `hook-posttooluse` fact also records yielded
commands with missing/delayed post events, and `hook-unhooked-tools` records
unhooked `exec`, nested `write_stdin` and `wait`. None is a permission end signal.
Capability facts were obtained only through `tools/harness-facts`; older-version
facts stay labelled by their recorded versions.

### Concurrent accounting and recommendation

The future rule must exclude only intervals during which permission is pending
and no other counted work is executing. If agent A waits while B runs, B's
interval still counts once. If A is approved and starts a long command, counting
must resume at approval/execution entry, before its post event. Two overlapping
waits cannot be subtracted twice. Scope state to a call and its agent; a global
pause flag or closing every open call would lose concurrent work. An outstanding
parent `Agent`/`wait_agent` wrapper also needs consideration: leaving that wrapper
in flight can keep charging time when its child is only waiting on permission.
The existing under-ten-minute idle heuristic is not explicit wait state.

**Recommended next scope for hq-a639e4:** a separately authorized, isolated manual
probe on each installed harness, using one harmless approval-gated marker command.
Capture timestamps, actual hook payloads and call/agent identities at request,
answer, execution entry and result. Exercise acceptance, human denial and pending
permission cancellation; distinguish Esc, turn abort and session close if their
events differ. Include one case with another agent/call running during the wait
and account for its parent wrapper. Record no-hook/missing-id outcomes explicitly.
Use the existing hook capture approach; do not begin with a new daemon or service.
If hooks lack an answer boundary, evaluate the already-declared protocol route
separately rather than inferring completion from a tool result or generic event.

This is a recommendation for later scoping, not an approved design, paid-run
budget or permission to invoke another model. It does not expand hq-a5a449's
compaction, failed-command and argument-loss probe. No interface change is
recommended as implementable from the evidence gathered here.
