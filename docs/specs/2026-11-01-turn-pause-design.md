# Turn pause: stop a turn that runs past its range until the user reviews it

Task: hq-9aa713. Companion: lore-911121 (what the paused agent reports and does,
and the rule an agent follows where no hook runs), designed with this one in
`<records root>/lore/docs/specs/2026-11-01-turn-pause-guidance-design.md`.
Status: revision 6 for the user's review. Revision 3 was accepted at `8a130e9`;
the plan's Task 1 probes (hq-fe672f) then showed that Codex 0.166.0 fires no hook
for its outer code-mode `exec`, which that revision's Codex enforcement assumed.
The user chose (2026-11-01) to enforce Codex on the calls its hooks do see.
Revision 4 (`762b0c04`) made that change; round 5 (claude-code/claude-opus-5-5,
a pre-review before the user's) found the shell validator open under zsh, Codex
workers owned by the wrong identifier, scheduled wakes able to reset counters,
deferred Claude Code cancellation tools unreachable while paused, and claims about
unprobed tools; revision 5 (`17162c3a`) fixed those from a third probe round.
Round 6 (same reviewer, scoped) found a paused Codex goal able to keep starting
turns, the validator's any-shell claim too broad for Codex's `shell` argument, and
scheduled-prompt records that never expire; revision 6 fixes those. Since revision
3, what exists today, the Codex counters, the turn unit's wake rule, the
cancellation table, the shell validator, the Codex `exec` rule and its
limitation, and Verification changed; the rest stands as accepted. Earlier rounds: round 3
(codex/gpt-6.1-sol at `e184ba1`: no git while paused, cancellation by function with
probed tool names, budget examples ignored silently); round 2 (same reviewer at
`88b8958`: in-flight active time, the enforced closing allowlist, cancellation
after grace, the budget directive and one reproducible fire rate).

## Intent

The user's words (claude-code:1219a183, 2026-10-31): a hook in hq, or language in
lore, "to ensure that we don't blow past the normal range of token usage / turn
counts; if so, have the agent pause and wait for the user to review the situation",
for all harnesses through hq, not only Codex where it happened. On 2026-11-01 they
added: obs might not be needed for this, "as long as it doesn't slip past us
silently (which hq + lore should handle)". obs-59789b (baselines and alarms) is
shelved until this task closes.

The case: sun-fbaf80's Codex controller ran one turn of about 40 h after the
user's last message (35.1 h of it active by the task's first profile; the
measurement below, which counts running calls in full, reads 41.6 h), with 1,622 tool calls, 80 subagent
spawns and 10 compactions, until the user killed it. Nothing stopped it or told the
user.

## Goals

- A turn that leaves its range stops doing work: every further tool call in its
  session tree is refused, with a reason that tells the agent what to do, until the
  user replies. The only exceptions are an enforced closing allowlist for the
  report, the park and stopping work already started.
- The pause is never silent: the user is notified when it fires, on the desktop and
  through relay's inbox where that is running.
- A user who starts deliberately long work can give that turn a larger budget in
  their own prompt. An approved plan or spec is not a budget.
- The agent sees its standing before the pause (a warning at three quarters of a
  limit) and can read it on demand.
- Claude Code and Codex are covered in the first release; every other harness's
  coverage is stated, not implied.

## Non-goals

- Token, cost or rate-limit limits. No hook payload carries them (survey on
  hq-9aa713). They return with obs-59789b if the static limits prove too coarse.
- Learned baselines. The limits are static, set from one measurement and approved
  here.
- Limits on a whole session or a day. A turn is the unit the user reviews: their
  reply is the review.
- Enforcing lore-56a1c7's review bound or lore-c5856b's handoff point. Those
  designs hand their counts to lore-911121's rule, not to this hook, unless a later
  design adds them as counters.

## Anti-goals

- A pause the agent can lift on its own (by editing state or limits, by an injected
  prompt, by spawning a fresh child) is a failure even if it fires.
- Pausing ordinary interactive work often enough that the user starts granting
  large budgets by reflex, or wants the hook off.
- A fresh approval request for routine work. The pause fires on counters, once per
  turn, and the user's reply ends it (lore-0ed8c8 is the opposite pressure).
- Adding noticeable latency to every tool call.

## What exists today

From the survey recorded on hq-9aa713 (2026-11-01):

- Claude Code and Codex PreToolUse hooks can deny a call
  (`permissionDecision: deny`), and live refusal was proven by ops-c8e4d1. A
  UserPromptSubmit hook can block or add context. A Stop block makes the agent
  *continue*, so it cannot pause; and the case was one 40 h turn, so a check that
  runs only at turn boundaries would never have fired.
- Hook payloads carry `session_id`, `transcript_path`, `tool_name`, `tool_input`,
  `agent_id` (Codex workers), and the prompt on UserPromptSubmit. They carry no
  token, call or compaction counts.
- Relay's guard protocol (relay `docs/api.md`, Guard protocol) can refuse every
  tool, but its `Event` carries no prompt text, so a relay guard cannot read a
  budget line or tell a human prompt from an injected one.
- hq wires SubagentStart for Codex only, and no compaction hook.

Probed by the plan's Task 1 (hq-fe672f, Claude Code 2.1.316 and Codex 0.166.0,
recorded in `facts/capabilities.toml`):

- Both harnesses: a PreToolUse deny holds and its reason reaches the model; the
  prompt text arrives on UserPromptSubmit; a child's calls carry its `agent_id` and
  the root's `session_id`; PostToolUse fires for every allowed call and none for a
  refused one; SubagentStart fires once per started child; SubagentStop names the
  child, Stop does not.
- Claude Code: PreCompact and PostCompact fire. A background completion wakes the
  session with a UserPromptSubmit whose prompt is a `<task-notification>` block.
  The runtime offers no wait tool (waiting is a turn end and a notification wake),
  no `KillShell`, and no `Grep` or `Glob`.
- Codex: **no hook fires for the outer code-mode `exec`**, under the same `*`
  matcher that catches every other call. Each call *inside* an `exec` fires its own
  PreToolUse and PostToolUse (a nested `exec_command` arrives as tool name `Bash`,
  `apply_patch` as `apply_patch`), and a nested deny stops that call's side effect.
  Function tools outside `exec` (`spawn_agent`, `wait_agent`, `interrupt_agent`)
  fire their own hooks. `spawn_agent` cannot be called from inside `exec`; spawns
  are direct function calls, and SubagentStart counts started workers exactly,
  while PreToolUse also counts refused attempts. Whether compaction fires a hook is
  unknown (two probe runs did not compact). `exec` also exposes the signed-in
  account's MCP tools; each call to one fires its own PreToolUse (the hook name
  joins app and tool with a double underscore) and a deny holds. Two controls fire
  **no hook at all**: a nested `write_stdin` (input to a running exec session) and
  the top-level `wait` (including `terminate: true` on a running `exec` cell).
  Every other Codex tool the probes called fires its hook; function tools arrive
  as `collaboration<name>` or `clock<name>`, nested tools under their own names
  (fact `hook-tool-names`). An `exec_command` that yields gets no PostToolUse at
  the yield: one arrived when a later `write_stdin` interrupted the process (the
  one case probed; a `write_stdin` that only collects an already-ended process is
  unprobed), and none
  if the process ends on its own. A deny on a worker's own nested call holds.
  `spawn_agent` takes a bare `task_name` and returns it as `/root/<name>`;
  `interrupt_agent`, `send_message` and `followup_task` target that name, and no
  hook payload links a name to the worker's `agent_id`. A goal continuation turn
  fires no UserPromptSubmit.
- Claude Code (round 3): a `ScheduleWakeup` wake arrives as a UserPromptSubmit
  whose prompt is the scheduled text verbatim, with no marker; whether a
  `CronCreate` job's fire does the same is unknown (two runs never saw one fire).
  A deny on a subagent's own call holds.
- agy hooks PreToolUse only for `run_command`, plus SessionStart and Stop.
  opencode and pi have no hook path hq wires.

## Measured range

One read-only pass over the session trees on this host whose turns began in the
fixed window [2026-10-02T00:00Z, 2026-11-01T00:00Z), counted with the hook's own
rules below: tree events (the root plus Claude Code `subagents/` transcripts and
Codex child rollouts linked through obs's index), the in-flight active-time rule,
root tool calls, tree spawns and root compactions. Attachments on lore-911121:
script `turn-spans-v2.py`, output `turn-spans-v2-2026-10-02_2026-11-01.txt`, rows
`turn-rows-v2-2026-10-02_2026-11-01.json.gz` (uncompressed sha256 `e377c032…8d8ed4`,
printed in full in the output). Rerunning the attached script reproduced the output
byte for byte. It reproduces only while the stores keep these files; session
retention (hq-401088) may later prune some.

5,483 turns (Claude Code 3,033, Codex 2,450):

| Per turn | p50 | p90 | p99 | p99.9 | max |
| --- | --- | --- | --- | --- | --- |
| Active minutes, Claude Code | 2.8 | 25.4 | 163 | 510 | 1,266 |
| Active minutes, Codex | 6.0 | 32.0 | 252 | 616 | 2,499 |
| Root tool calls, Claude Code | 9 | 49 | 143 | 300 | 529 |
| Root tool calls, Codex | 12 | 55 | 246 | 700 | 1,622 |
| Tree spawns, Claude Code | 0 | 1 | 16 | 38 | 103 |
| Tree spawns, Codex | 0 | 1 | 19 | 50 | 80 |
| Root compactions, Claude Code | 0 | 0 | 1 | 1 | 1 |
| Root compactions, Codex | 0 | 0 | 1 | 4 | 10 |

Turns over each limit alone, and over any limit of a set, in those 30 days:

| Limit | Turns |
| --- | --- |
| Active over 3 h / 4 h / 6 h | 63 / 42 / 19 |
| Root calls over 300 / 500 / 800 | 19 / 6 / 1 |
| Tree spawns over 20 / 30 / 50 | 39 / 14 / 4 |
| Compactions over 1 / 2 | 20 / 11 |
| 3 h, 500 calls, 20 spawns, 1 compaction | 81 (2.70 a day) |
| 4 h, 500 calls, 30 spawns, 1 compaction | 56 (1.87 a day) |
| **4 h, 500 calls, 30 spawns, 2 compactions** | **50 (1.67 a day)** |
| 6 h, 800 calls, 50 spawns, 2 compactions | 24 (0.80 a day) |

The sun-fbaf80 controller's long turn reads 41.6 h active, 1,622 calls, 80 spawns
and 10 compactions; every set above pauses it within its first 3 to 6 active hours.
Its earlier turn (4.4 h active, 219 calls, 22 spawns) also pauses under a 3 h or
4 h limit.

Superseded: the first draft quoted 5,468 turns and 1.1 a day from an earlier
script. That script used a window relative to its run time (its attachment, from a
second run, holds 5,470), counted harness bookkeeping records written around the
user's next prompt as activity, dropped every gap over 10 minutes even while a
call was running, and left compactions out of the combined rate. Its attachments
stay on lore-911121 as the record of that draft.

Wall time since the prompt is not a usable measure: turns that sit idle and are
woken days later by a background notification read as 40 to 200 h with a handful
of calls.

## Approaches considered

1. **Hook pause, lore report (chosen).** A direct hook in each harness counts the
   turn and refuses tool calls past the limit; lore says what the paused agent
   reports and how it parks. The pause holds even when the agent would argue
   past it, which matters here: the same run overrode a P0 halt nine times on its
   own authority.
2. **Hook notifies, agent self-pauses.** The hook only notifies; lore tells the
   agent to stop. Cheaper and never blocks a legitimate run, but it rests the
   outcome on the agent obeying guidance, which the case shows it did not.
3. **Lore only.** No enforcement and no notification when the user is away; it
   cannot meet "doesn't slip past us silently".

Option 1 is the agent's call under the user's standing rule for bounded
decisions; option 2's notification is folded into it.

## Design

### The unit: a turn of a session tree

A turn starts at a **genuine human prompt** in a **root session** and lasts until
the next one. A prompt is genuine when its text does not begin with `<` (system
reminders, `<task-notification>`, hook context), except a turn beginning
`<pasted_content`, and, for Codex, does not begin `# AGENTS.md`. That is the
human-or-injected rule obs's adapters and hq's session-logs skill already use; the
three stay in step. A Codex worker's events (`agent_id` present) belong to the root
`session_id`; a Claude Code subagent's tool calls arrive under its parent's
`session_id`. So one counter set covers the controller and every child.

A background wake (a task notification, a scheduled loop tick) does not start a
turn. That is deliberate: an unattended loop is exactly what must not reset its own
counters, and a job an agent scheduled before a pause must not lift it. A wake that
arrives as a `<…>` block is caught by the rule above. A scheduled prompt an agent
wrote itself may arrive as plain text, so the hook keeps the session's **pending
scheduled prompts** and treats a UserPromptSubmit whose text equals a pending one
as a wake:

- a `ScheduleWakeup` (seen at PreToolUse, its fire time from the PostToolUse
  `scheduledFor`) is pending from 1 minute before its fire time to 10 minutes
  after it, and is consumed by its first match;
- a `CronCreate` job is pending while it exists: recorded at its PostToolUse
  (its `id`), dropped at its `CronDelete`, and the whole set refreshed from the
  `session_crons` list every Claude Code Stop payload carries, so a durable job
  or one created before the hook was installed is covered from the first Stop.

The probes showed a `ScheduleWakeup` wake arrives exactly so (its scheduled text,
verbatim); a `CronCreate` fire was not observed, and the same match covers it.
The cost is stated, not hidden: a prompt the user types that is identical to a
pending scheduled prompt (a self-pacing loop that schedules `continue`, say) is
read as a wake, and ends neither the turn nor a pause; the hook then adds one line
of context saying so, so the agent can tell the user to rephrase. A Codex goal
continuation fires no UserPromptSubmit, so it never starts a turn; how a paused
Codex root stops its goal is under Cancellation.

### Counters

Kept per root session by the hook itself, from events it already receives:

- **active seconds**, from two separate records the hook keeps:
  - *operations in flight*: a tool call is in flight from its PreToolUse (when
    allowed) to its PostToolUse or PostToolUseFailure, matched by tool-use id.
    Codex has no PostToolUseFailure event: a failed Codex call closes at its
    PostToolUse if Codex sends one for a failure, which is not probed, and
    otherwise at its agent's Stop. An agent's open calls close
    at its Stop or SubagentStop, and every open call closes at the next genuine
    prompt. A call that waits on the user (Claude Code `AskUserQuestion` and `ExitPlanMode`, Codex
    `request_user_input` and `request_user_input_async`) is never in flight:
    waiting on the user is not work. An agent's open calls also close when that
    agent starts a call that waits on the user, except a Codex nested
    `exec_command` (hook name `Bash`), the one call that can stay open without a
    PostToolUse after a yield. An open call at that point is in practice one
    another hook refused (refused calls get no PostToolUse in either harness),
    and without this rule the wait after it would count as active.
  - *the idle gap*: the time from one tree event to the next.

  The gap counts in full while any operation in the tree is in flight, however
  long it is; otherwise it counts only when under 10 minutes (model inference
  between calls). So eight back-to-back half-hour calls count four hours, a
  half-hour `wait_agent` on a quiet child counts half an hour, and a session left
  at a question overnight counts nothing, unless another call is still in flight
  meanwhile (a background worker, a yielded Codex `exec_command`), in which case
  the wait counts as the time that call runs. Nothing after the turn's last event
  counts. The measurement script applies the same rule to transcripts, except
  the user-wait exception (it counts those calls, so its rate is an upper bound
  in that respect). For Codex, the in-flight operations are the hooked calls: a
  nested call inside an `exec` and a function tool such as `wait_agent`. The outer
  `exec` itself is never seen, so time an `exec` spends in tool-free code counts
  only through the idle-gap rule. A nested `exec_command` that yields stays in
  flight until its PostToolUse or its agent's Stop, since Codex sends no
  PostToolUse at the yield: time spent driving or waiting on a yielded process
  counts in full, and a process that ended on its own still counts until the
  agent's turn ends, an overcount accepted over missing work;
- **tool calls**: the root's own calls the hook sees, counted at PreToolUse.
  Children's calls are not added: the measurement below counted the root
  transcript only, and counting the tree would make the approved numbers mean
  something else. For Codex that is each nested call and each function tool, not
  each `exec`: an `exec` running three commands counts three, and an `exec` that
  calls no tool counts none. The measurement counted one per `exec`, so the
  verification replay recounts Codex calls the hook's way before anything is
  wired, and the fire-rate gate under Limits decides whether 500 still fits;
- **subagent spawns**: every child started in the tree, counted once per child:
  Claude Code from each allowed `Agent`/`Task` call, keyed by its tool-use id;
  Codex from SubagentStart, keyed by the worker's `agent_id` (PreToolUse on
  `spawn_agent` also sees refused attempts, so it is not the count). Under
  SubagentStart the 31st worker exists before it is counted, and the tree pauses
  at its next call;
- **compactions**: PreCompact or PostCompact, counted once per compaction, for
  Claude Code. Codex has no compaction counter until a probe shows a compaction
  hook fires; lore's rule has its agents count their own.

Tokens and rate limits are not visible to a hook and are not counted.

### Limits

Defaults, for the user to approve at this review: **4 h active, 500 root tool
calls, 30 tree spawns, 2 compactions per turn** (the third compaction pauses).
Whichever is crossed first pauses the turn. Over the measured window these pause
50 of 5,483 turns, 1.67 a day, about one turn in 110. Allowing only one compaction
raises that to 56 (1.87 a day); the case pauses at 4 h active under either. The
other rows of the table above are the alternatives. The limits live in one hq file, read by
the hook and by `hq pause limits`; lore's rule refers to that command rather than
repeating the numbers.

The verification replay recomputes the fire rate from the hook's own code over
the same window, with Codex counted the way the hook sees it (above): calls are
nested and function calls, spawns are started workers, active time comes only from
hooked calls in flight and the idle-gap rule, and compactions are not counted. It
prints the pauses per limit and per harness, so a changed Codex count is visible
even when the overall rate stays inside its band. If it differs from 1.67 a day by more than half, the plan stops and
brings the numbers back to the user before wiring anything.

### Warning, pause, notification

- **Warning.** At three quarters of any limit, the hook adds context to the
  allowed call once per limit: what has been used, what remains, and that the
  agent should finish a coherent step and prepare its report.
- **Pause.** The first call past a limit is refused with a reason naming the
  counters, the limit crossed and the instruction. The root is told: write the
  pause report lore describes, park the task waiting on the user, end the turn. A
  child (a Codex worker by `agent_id`, a Claude Code subagent by its `agent_id`)
  is told: stop, release any claim to your controller (`--waiting-on agent`), and
  return; only the root reports, so the user gets one decision, not one per child.
- **Paused calls.** Once paused, the hook allows only calls on the closing
  allowlist below and refuses everything else, including every shell command that
  does not pass the shell validator. Each session in the tree gets 25 allowlisted
  calls of **grace** to read what its report needs and park. After grace, only
  the *bookkeeping* and *cancellation* classes stay allowed. Cancellation is never
  exhausted: a session that finds a running process on its last call can still
  stop it. Git and other repository-configured readers are not on the list (see
  below), so a paused park records the accounting the session already holds and
  says it was not refreshed; lore's rule makes that the paused park's form, and
  the resuming session refreshes it first.
- **Notification.** When the pause fires, once per turn: a desktop notification,
  and a relay inbox notice when relay serve is reachable. Both are dispatched
  within the hook's time budget, with standard streams redirected so nothing holds
  the hook open. A failed notification is recorded in the pause state and shown by
  `hq pause status`; it does not lift the pause.

#### Closing allowlist

| Class | During grace | After grace |
| --- | --- | --- |
| Bookkeeping: `tasks park`, `tasks note`, `hq pause status` | yes | yes |
| Cancellation (below) | yes | yes |
| Records reads and attachments: `tasks show --no-fetch`, `tasks claims`, `tasks list`, `tasks attach` | yes | no |
| Reading: Claude Code `Read` (and `Grep`, `Glob` in a release that offers them; 2.1.316 does not); shell `cat`, `head`, `tail`, `wc`, `ls`; `host-load --section session` | yes | no |
| Everything else: file writes (`Edit`, `Write`, `NotebookEdit`, `apply_patch`), spawns and worker messages (`send_message`, `followup_task`), web and MCP tools, `git` in any form, any other command | no | no |

Each reader on the list runs no program the repository or user configuration
chooses. Git does: plain `git diff` runs a configured external diff helper, and
other subcommands can run fsmonitor, textconv, pager or signature programs, so no
git invocation is allowed while paused, rather than an option list that would
have to anticipate every configured program (finding reproduced by the round 3
reviewer in an isolated fixture). `tasks show` must carry `--no-fetch`, since it
otherwise runs a configured document provider for external links.

One boundary is accepted, not closed: `tasks park`, `tasks note` and
`tasks attach` commit records in projects that set `[git] commit`, and that
commit runs the repository's own pre-commit hook. Parking must work, the hook is
the repository's configuration rather than a command the agent chose, and lore's
rule already forbids changing it to get work done.

**Cancellation** stops work the session already started, and nothing else. It is
defined by what a control does, each with an ownership check; the tool names the
hook accepts come from capability facts recorded per harness version, because
names differ by runtime and an unlisted name is refused:

| Control | Claude Code 2.1.316 | Codex 0.166.0 | Ownership check |
| --- | --- | --- | --- |
| Stop an own background task | `TaskStop {task_id}` (2.1.316 offers no `KillShell`) | `wait` with `terminate: true` on a running `exec` cell: fires no hook, so it is never refused and stays available | the harness scopes `TaskStop` to the session; Codex `wait` cannot be checked |
| Interrupt an own worker | `TaskStop` on a background subagent's task id or name (its description says it accepts them; not exercised live) | `interrupt_agent {target}` (hook name `collaborationinterrupt_agent`; 0.166.0 offers no `close_agent`) | Claude Code: harness-scoped. Codex: the target is a task name an allowed `spawn_agent` in this tree gave (its `task_name`, bare or as `/root/<name>`); no hook payload links a task name to the worker's `agent_id`, so names and ids are recorded separately |
| Interrupt an own exec session | (none) | nested `write_stdin`: fires no hook, so it is never refused or checked, whatever input it sends | none possible (see the limitation below) |
| Cancel own scheduled work | `CronDelete {id}`; `ScheduleWakeup {stop: true}` | `update_goal` setting `status` to `paused` (a goal continues, starting a new turn after each Stop, until its status is `complete`, `paused` or `blocked`) | a `CronDelete` id must be a pending job of this session; `ScheduleWakeup` and the Codex goal are scoped to the session |
| Signal an own process | shell `kill <pid>…`, optionally with one of `-TERM`, `-INT`, `-KILL`, `-HUP` | the same through a nested `exec_command` (hook tool name `Bash`), only where commands share the harness's PID namespace (no sandbox); under the workspace sandbox each `exec_command` runs in its own PID namespace, its pids cannot be traced and the hook refuses them, so a yielded process is stopped with `write_stdin` and an interrupt (unhooked, always available; Task 9 lifecycle run) | every target pid descends from the harness process the hook runs under (ancestry read from `/proc`), and none is that process |

Claude Code defers `TaskStop` and `CronDelete` (2.1.316's deferred list; whether
`ScheduleWakeup` is deferred is not recorded): a session loads their schemas through `ToolSearch` before it can call them. A `ToolSearch` whose
query is `select:` naming only cancellation tools is therefore itself in the
cancellation class; any other `ToolSearch` is refused while paused.

The tool-surface probe (Verification) lists the tools each runtime offers its
model; a cancellation control named here that the probe does not find, or a
cancellation tool it finds that is not named, fails the plan's gate until this
table is corrected.

**The shell validator** decides whether a shell call (Claude Code `Bash`, Codex
nested `exec_command`, hook name `Bash`) is on the allowlist. It must hold under
the shells a harness runs by default, POSIX `sh`, `bash`, `dash` and `zsh`, because
the hook does not see which one runs: Codex `exec_command` defaults to the user's
login shell (zsh on this host). It cannot hold for an arbitrary binary: Codex
`exec_command` also takes a `shell` argument (and `login`, `tty`, `workdir`), and
the hook payload carries only `command` (inferred from the payloads observed, which
dropped every other argument the model passed; not separately probed). That gap is
part of the unhooked-controls limitation below. zsh expands
words POSIX `shlex` treats as plain text (`cat =(touch x)` and the glob qualifier
`cat a(e:'touch x':)` both run a command; reproduced by the round 5 reviewer), so
the validator reads the raw command, not only its `shlex` split:

- outside quotes, every character is an ASCII letter, an ASCII digit, a space
  (U+0020) or one of `_ . / : @ % + , = -`, and no `shlex` word (after quote
  removal, so `''=ls` counts) starts with `=` or `~`; this alone excludes
  `;`, `&`, `|`, redirection, `` ` ``, `$`, globs, braces, parentheses, `#`, `^`
  and newline;
- inside single quotes, anything but a newline; inside double quotes, anything but
  `$`, `` ` ``, `\`, `!` and a newline;
- the command then parses (POSIX `shlex`) as one simple command with no leading
  environment assignment; anything that fails either step is refused;
- `argv[0]` is a bare program name (no path) on the table above;
- every option is on that program's own option list, which excludes options that
  run programs, follow, or write files (for `tail`: no `-f`);
- `tasks` and `hq` run only the subcommands named, with any options except that
  `tasks show` requires `--no-fetch`.

**Codex code-mode `exec`** reaches no hook, so its source is never read or
judged. Each call it makes is judged on its own, by the same rules as any other
call: a nested `exec_command` (tool name `Bash`) passes only through the shell
validator, and a nested `apply_patch` is a file write and is refused. Code inside an `exec` that calls no
tool (arithmetic, string handling, the `text` and `store` helpers) still runs
while paused; it can change nothing outside the session without a tool, so it is
accepted as unseen rather than blocked. A nested MCP call is refused like any MCP
tool.

**Limitation: unhooked Codex controls.** Nested `write_stdin` (input to a yielded
`exec_command` session) and top-level `wait` (polling or terminating a yielded
`exec` cell) reach no hook in Codex 0.166.0, alongside the outer `exec`; every other tool the
probes called is hooked, and two were never called (`request_plugin_install`,
which the model declined, and `image_gen__imagegen`, skipped for its quota cost):
they are refused while paused if hooked and unprobed otherwise. The arguments of
a hooked `exec_command` other than `command` (`shell`, `login`, `tty`, `workdir`)
are not in its hook payload either, so an allowed command line can run under a
binary the validator never considered (`shell: "script"` turns `-c "cat a"` into
a file write). Three consequences:

- *While paused*, an agent can still send any input to a session it opened before
  the pause (an interactive shell, an `ssh` session), and the hook neither sees nor
  refuses it. That includes editing the pause state or limits file through such a
  shell: the protected-path check matches only inputs the hook sees.
- *Before the pause*, work driven through such a session makes no hooked calls,
  so it is invisible to the call counter. Its time does count: the
  `exec_command` that opened the session stays in flight until its PostToolUse
  or the agent's Stop (above). A turn that works only through one long-lived
  session would never reach its call limit, but would reach its active-time
  limit.
- The mitigation is narrow: opening a *new* session needs a hooked
  `exec_command`, which the pause refuses unless its command passes the shell
  validator, and an agent choosing an unusual `shell` binary to slip a validated
  command past it is outside what the hook can see.

Two more things outside the hook's view, found by the allowlist's adversarial
review: a harness that evaluated commands after loading the user's shell snapshot
would let zsh global aliases (`G` for `| grep -i`) extend a validated command,
which no harness was seen doing (Codex runs commands in a fresh shell, inferred,
not observed); and a reader shadowed earlier on `PATH` (a `cat` in `~/bin`) would
run in place of the system one. Non-default zsh options (`rcquotes`,
`magicequalsubst`) change arguments but run nothing.

This is accepted for the first release as stated, not closed. The refusal text and
lore's rule allow only an interrupt, and agents do not use long-lived interactive
sessions as their normal way of working. A follow-up re-probes each Codex version
and prepares an upstream request for hooks on `write_stdin` and `wait` and for
the full `exec_command` arguments in the hook payload, for the user to approve
publishing.

Bookkeeping and cancellation stay allowed in every state, so claim-guard's Stop
block and the refusal never loop, and no session is left unable to stop its own
work.

### Resuming and granting more

- The next genuine human prompt in the root session ends the pause and starts a new
  turn with fresh counters. The user's reply is the review.
- A prompt sets a budget only with a **budget directive**: the first non-empty
  line of the text the user typed, alone on its line, matching
  `budget: <duration>[, <n> calls][, <n> agents][, <n> compactions]` (for example
  `budget: 10h, 2000 calls, 80 agents`). The text the user typed excludes
  `<pasted_content …>` blocks, so a pasted prompt never grants a budget; a line
  inside a code fence or a quote (`> budget: …`) is not a first line that starts
  with `budget:`, so neither does a fenced or quoted example. Budget text
  anywhere else is an example, not a directive: it sets nothing, and the hook says
  nothing about it, so reviewing a spec full of budget examples raises no
  question. A first typed line that starts with `budget:` but does not parse is an
  attempted directive: it sets nothing, the turn keeps its limits, and the hook
  adds one line of context naming the parse error, for the agent to mention in
  its next report without stopping its work.
- The duration sets the active limit and scales every unnamed limit by the same
  factor over the 4 h default: `budget: 12h` allows 1,500 calls, 90 spawns and 6
  compactions. A named count overrides its scaled value. The hook confirms the
  limits it read as added context, so a typo shows at once. A budget lasts one
  turn.
- Only the UserPromptSubmit payload is read for a budget. Nothing an agent writes
  (a task note, a plan, a file) can set or raise one.
- **Limitation.** A session an agent launches from the shell (`claude -p`,
  `codex exec`, a crew dispatch, a cross-harness reviewer) is a new root with its
  own counters, and its agent-written prompt passes the genuine-prompt test, so a
  budget line in it would be honoured. The first release does not tie such
  sessions to their parent; lore's rule forbids putting a budget line in a prompt
  an agent writes, and a follow-up task covers linking them by process ancestry
  or an inherited environment variable.

### State and integrity

State is one small file per root session under `$XDG_STATE_HOME/hq/pause/`,
updated under a lock (parallel tool calls write concurrently), pruned at
SessionEnd and after seven days without events. An agent that edits the state or
limits defeats the design. Lore's rule forbids it, and the hook refuses any tool
call whose input names the state directory or the limits file (a string match on
paths and commands: it raises the bar, it is not a sandbox). The hook also records
the limits file's hash at each new turn; a change mid-turn pauses the turn and
notifies the user.

When the hook cannot read or write its state, it refuses the call with a reason
naming the file and the error. That follows the user's fail-early rule; the cost is
that a broken hook blocks work until it is fixed, which is the visible failure the
user prefers to a silent one. The harnesses' own timeout behaviour (the call
proceeds) is the one fail-open path, and the latency budget keeps it remote.

### Wiring and latency

A direct hook, not a relay guard, because it needs the prompt text. It is wired in
`claude/settings.json` and `codex/hooks.json` (and their work variants) on
PreToolUse, PostToolUse (all tools), PostToolUseFailure (Claude Code only; Codex
has no such event) and UserPromptSubmit;
on Stop and SubagentStop as an observer that never blocks (it closes in-flight
calls); on SessionEnd for pruning; on PreCompact/PostCompact for Claude Code; and
on SubagentStart for both (Claude Code records workers from it, Codex counts its
spawns from it). Target: under 50 ms at p99 on this host
per call, measured over a replay of a large rollout; hq's test-latency practice
applies.

### Coverage

| Harness | First release | Notes |
| --- | --- | --- |
| Claude Code | pause, warning, budget | |
| Codex | pause, warning, budget | worker events grouped by root; enforced on the calls its hooks see (nested calls and function tools), not on the outer `exec`, nested `write_stdin` or `wait` (limitation under Closing allowlist); no compaction counter until a compaction hook is shown to fire |
| agy | not covered | PreToolUse sees only `run_command`; a partial pause would mislead. Follow-up task. |
| opencode, pi | not covered | no hook path; lore's rule is the only bound |

### Agent-visible surface

`hq pause status` prints the current root session's counters, limits, budget,
pause state and notification result as one line (`--json` for tools), found from
the harness's session environment (`CODEX_THREAD_ID`; Claude Code's session id as
the hook records it per cwd). A count the harness's hook does not keep (Codex
compactions today) prints as not counted, and lore-911121's rule has the agent
keep that count itself. `hq pause limits` prints the defaults. lore-911121's
rule tells agents when to run them.

## Verification

- **Replay.** Feeding the sun-fbaf80 controller rollout through the counter logic
  pauses its long turn no later than 4 h active, by whichever limit is crossed
  first, and does not pause its earlier 4.4 h turn twice.
- **Fire rate.** Replaying the 30-day store through the hook's counting (root
  calls, tree spawns and active time, compactions) gives the pause rate the user
  approves numbers against; the gate under Limits applies.
- **Live probes, per harness**, recorded as capability facts and rerun on a
  version change (the plan's Task 1 re-probe gate). Done for Claude Code 2.1.316
  and Codex 0.166.0 in hq-fe672f: a deny holds, with its side effect prevented,
  for a spawn, a shell call, a file write and a child's own call in both
  harnesses, and for a worker wait and an MCP call in Codex (Claude Code offers no
  wait tool, and its runs loaded no MCP server); the hook names of every tool called, and
  the unhooked set (Codex: outer `exec`, nested `write_stdin`, `wait`);
  PreCompact and PostCompact fire for Claude Code; SubagentStart fires per
  started child; UserPromptSubmit carries the prompt; a Claude Code task
  notification wake arrives as a `<task-notification>` block and a
  `ScheduleWakeup` wake as its scheduled text; a Codex goal continuation fires no
  UserPromptSubmit; child calls carry `agent_id`; PostToolUse fires for allowed
  calls but not at a Codex yield; each runtime's tool surface and cancellation
  argument schemas. Still unknown: whether a Codex compaction fires a hook,
  whether a Claude Code `CronCreate` fire arrives as plain text, and the hooking
  of the two Codex tools never called. The isolated lifecycle run (cross the
  limit, spend grace, cancel own work, park, resume) shows that a refused turn
  can still park and end.
- **Tests** cover, at least:
  - active time: eight back-to-back half-hour calls count 4 h and pause; a
    half-hour `wait_agent` with a silent child counts in full; a call with no
    PostToolUse closes at the agent's next event or Stop; an `AskUserQuestion`
    left open overnight counts nothing; idle gaps over 10 minutes with nothing in
    flight count nothing;
  - counter grouping across root, Claude Code subagents and Codex workers, and
    the genuine-prompt rule (shared fixtures with obs's adapters);
  - the budget directive: honoured on the first typed line; ignored silently, as
    an example, on a later line, inside a code fence, after `>`, inside a
    `<pasted_content>` block, and as a second `budget:` line after a valid
    directive; ignored with one line of context when the first typed line starts
    with `budget:` but does not parse; scaling and named overrides;
  - the shell validator: each allowlisted command passes; each operator,
    expansion, redirection, path-qualified program, write-capable option and
    unlisted subcommand is refused, and so are the zsh forms `cat =(touch x)`,
    `cat =ls`, `cat ''=ls`, `cat a(e:'touch x':)` and `cat a~b`; a Codex nested `Bash` call is
    judged by the same validator, and a nested `apply_patch` is refused;
  - `kill` refuses process groups and broadcast targets (`kill 0`, `kill -1`,
    `kill -TERM -1`, `kill -- -1`);
  - Codex worker ownership: `interrupt_agent` passes for a task name an allowed
    `spawn_agent` in the tree gave, as the full path its response returns and as
    the bare name, including a worker's own nested spawn, and is refused for any
    other name;
  - scheduled wakes: a fired `ScheduleWakeup` prompt within its window is a wake
    and is consumed; the same text typed after the window is genuine; a pending
    `CronCreate` prompt is a wake until its `CronDelete` or its absence from a
    Stop's `session_crons`; a genuine prompt identical to a pending one is read as
    a wake and adds the one context line;
  - a paused Codex root can set its goal to `paused`, and any other `update_goal`
    is refused; a yielded call closed by Stop whose PostToolUse arrives in a later
    turn neither reopens it nor adds time;
  - Codex counting: an `exec` with three nested calls counts three root calls, one
    with no tool call counts none; spawns count from SubagentStart once per worker,
    and a refused `spawn_agent` attempt counts nothing;
  - cancellation after grace, per harness, with each control in the
    cancellation table: an exhausted Claude Code session can `TaskStop` its
    background task, `CronDelete` its own job, stop its loop and `kill` its own
    process; an exhausted Codex controller can `interrupt_agent` its own worker
    and `kill` its own process through a nested `exec_command`; each control is
    refused against a worker, job or pid this tree does not own (Codex
    `write_stdin` and `wait` never reach the hook, so no test can cover them);
  - the paused allowlist refuses every `git` invocation, including plain
    `git diff`, `git status` and `git worktree list`, and `tasks show` without
    `--no-fetch`;
  - the budget directive's silent cases: a reviewed spec whose body holds
    `budget:` examples sets nothing and adds no context; a malformed first-line
    directive adds exactly one line of context;
  - root versus child refusal text, refused edits to the state and limits,
    concurrent writes, unreadable state, and the warning firing once.

## Left to the builder

The hook's language and file layout inside hq, the state file format, the exact
notification command, and how Claude Code's session id reaches `hq pause status`.

## Activation

Wiring the hook into live harness settings changes a live global surface. It needs
the user's separate approval after implementation, as `just link --apply` from main.
