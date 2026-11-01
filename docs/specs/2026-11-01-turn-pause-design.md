# Turn pause: stop a turn that runs past its range until the user reviews it

Task: hq-9aa713. Companion: lore-911121 (what the paused agent reports and does,
and the rule an agent follows where no hook runs), designed with this one in
`<records root>/lore/docs/specs/2026-11-01-turn-pause-guidance-design.md`.
Status: revision 2 for the user's review, after review round 2 (codex/gpt-6.1-sol
at `88b8958`: in-flight active time, enforced closing allowlist, cancellation after
grace, budget directive, one reproducible fire rate).

## Intent

The user's words (claude-code:1219a183, 2026-10-31): a hook in hq, or language in
lore, "to ensure that we don't blow past the normal range of token usage / turn
counts; if so, have the agent pause and wait for the user to review the situation",
for all harnesses through hq, not only Codex where it happened. On 2026-11-01 they
added: obs might not be needed for this, "as long as it doesn't slip past us
silently (which hq + lore should handle)". obs-59789b (baselines and alarms) is
shelved until this task closes.

The case: sun-fbaf80's Codex controller ran one turn of about 40 h after the
user's last message (35.1 h of it active), with 1,622 tool calls, 80 subagent
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
- hq wires SubagentStart for Codex only, and no compaction hook. Both installed
  binaries (Claude Code 2.1.316, Codex 0.166.0) name `PreCompact`, `PostCompact`
  and `SubagentStart` events; that they fire for hooks is not yet probed.
- Codex code-mode `exec` calls are what a Codex transcript records as tool calls;
  whether PreToolUse fires once per `exec` or per nested call is unproven
  (ops-daf2cd).
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
counters.

### Counters

Kept per root session by the hook itself, from events it already receives:

- **active seconds**, from two separate records the hook keeps:
  - *operations in flight*: a tool call is in flight from its PreToolUse (when
    allowed) to its PostToolUse or PostToolUseFailure, matched by tool-use id.
    Where a harness has no PostToolUse (the probe below says), the call stays in
    flight until the next hook event of the same agent. An agent's open calls close
    at its Stop or SubagentStop, and every open call closes at the next genuine
    prompt. A call that waits on the user (Claude Code `AskUserQuestion`, Codex
    `request_user_input`) is never in flight: waiting on the user is not work.
  - *the idle gap*: the time from one tree event to the next.

  The gap counts in full while any operation in the tree is in flight, however
  long it is; otherwise it counts only when under 10 minutes (model inference
  between calls). So eight back-to-back half-hour calls count four hours, a
  half-hour `wait_agent` on a quiet child counts half an hour, and a session left
  at a question overnight counts nothing. Nothing after the turn's last event
  counts. The measurement script applies the same rule to transcripts, except
  the user-wait exception (it counts those calls, so its rate is an upper bound
  in that respect);
- **tool calls**: the root's own PreToolUse calls. Children's calls are not added:
  the measurement below counted the root transcript only, and counting the tree
  would make the approved numbers mean something else. (Codex: one per `exec`
  until ops-daf2cd settles nesting, which is what the measurement counted.)
- **subagent spawns**: every spawn in the tree: Claude Code `Agent`/`Task` tool
  calls, Codex `spawn_agent` (SubagentStart where it fires);
- **compactions**: PreCompact or PostCompact, once the probe below shows it fires
  for that harness. Where it does not, the harness has no compaction counter and
  lore's rule has the agent count its own.

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
the same window. If it differs from 1.67 a day by more than half, the plan stops
and brings the numbers back to the user before wiring anything.

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
  calls of **grace** to report, account for what it holds and park (the global
  rules ask for worktree and process accounting at park). After grace, only the
  *bookkeeping* and *cancellation* classes stay allowed. Cancellation is never
  exhausted: a session that finds a running process on its last call can still
  stop it.

#### Closing allowlist

| Class | During grace | After grace |
| --- | --- | --- |
| Bookkeeping: `tasks park`, `tasks note`, `hq pause status` | yes | yes |
| Cancellation (below) | yes | yes |
| Records reads and attachments: `tasks show`, `tasks claims`, `tasks list`, `tasks attach` | yes | no |
| Reading: Claude Code `Read`, `Grep`, `Glob`; shell `cat`, `head`, `tail`, `wc`, `ls`; `git status`, `git log`, `git diff`, `git show`, `git worktree list`; `host-load --section session` | yes | no |
| Everything else: file writes (`Edit`, `Write`, `NotebookEdit`, `apply_patch`), spawns, web and MCP tools, any other command | no | no |

**Cancellation** stops work the session already started, and nothing else:

- Claude Code's own task controls (`TaskStop`, `KillShell`), which only reach the
  session's own background tasks;
- Codex `close_agent` for its own workers, and `write_stdin` to one of its own
  exec sessions when the input is only an interrupt (`\u0003`) or end of input;
- shell `kill [-TERM|-INT|-KILL|-HUP] <pid>…` when every target pid is a
  descendant of the harness process the hook runs under (its ancestry read from
  `/proc`) and none is that process itself.

**The shell validator** decides whether a shell call (Claude Code `Bash`, Codex
`exec_command` or `shell`) is on the allowlist:

- the command parses (POSIX `shlex`) as one simple command: no `;`, `&`, `&&`,
  `||`, `|`, redirection, `` ` ``, `$(`, `${`, `$` variable, glob character,
  newline, or leading environment assignment; anything that fails to parse is
  refused;
- `argv[0]` is a bare program name (no path) on the table above;
- every option is on that program's own option list, which excludes options that
  run programs or write files (for git: `-C <dir>` is allowed; `-c`, `--output`,
  `--ext-diff` and `--textconv` are not; for `tail`: no `-f`);
  `git` runs only the subcommands named;
- `tasks` and `hq` run only the subcommands named, with any options.

**Codex code-mode `exec`** calls pass only when their whole source is one
`tools.exec_command({cmd: "<string literal>", …})` call, optionally wrapped in
`text(await …)`, with only literal option values from a short list (`workdir`,
`max_output_tokens`, `yield_time_ms`), and the literal passes the shell
validator; or one `tools.close_agent(…)` or interrupt-only `tools.write_stdin(…)`
call with literal arguments. Anything else, including any second statement,
template literal or variable, is refused. If the ops-daf2cd probe shows Codex
fires PreToolUse for each nested call, the hook validates those nested calls
directly and refuses an `exec` body that does anything else.

Bookkeeping and cancellation stay allowed in every state, so claim-guard's Stop
block and the refusal never loop, and no session is left unable to stop its own
work.
- **Notification.** When the pause fires, once per turn: a desktop notification,
  and a relay inbox notice when relay serve is reachable. Both are dispatched
  within the hook's time budget, with standard streams redirected so nothing holds
  the hook open. A failed notification is recorded in the pause state and shown by
  `hq pause status`; it does not lift the pause.

### Resuming and granting more

- The next genuine human prompt in the root session ends the pause and starts a new
  turn with fresh counters. The user's reply is the review.
- A prompt sets a budget only with a **budget directive**: the first non-empty
  line of the text the user typed, alone on its line, matching
  `budget: <duration>[, <n> calls][, <n> agents][, <n> compactions]` (for example
  `budget: 10h, 2000 calls, 80 agents`). The text the user typed excludes
  `<pasted_content …>` blocks, so a pasted prompt never grants a budget; a line
  inside a code fence or a quote (`> budget: …`) is not a first line that starts
  with `budget:`, so neither does a fenced or quoted example. A `budget:` line
  anywhere else, or a malformed directive, sets nothing; the hook adds context
  saying it was ignored and why, so the agent can tell the user.
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
PreToolUse, PostToolUse and PostToolUseFailure (all tools) and UserPromptSubmit;
on Stop and SubagentStop as an observer that never blocks (it closes in-flight
calls); on SessionEnd for pruning; and on PreCompact/PostCompact and
SubagentStart where their probes pass. Target: under 50 ms at p99 on this host
per call, measured over a replay of a large rollout; hq's test-latency practice
applies.

### Coverage

| Harness | First release | Notes |
| --- | --- | --- |
| Claude Code | pause, warning, budget | |
| Codex | pause, warning, budget | worker events grouped by root |
| agy | not covered | PreToolUse sees only `run_command`; a partial pause would mislead. Follow-up task. |
| opencode, pi | not covered | no hook path; lore's rule is the only bound |

### Agent-visible surface

`hq pause status` prints the current root session's counters, limits, budget,
pause state and notification result as one line (`--json` for tools), found from
the harness's session environment (`CODEX_THREAD_ID`; Claude Code's session id as
the hook records it per cwd). `hq pause limits` prints the defaults. lore-911121's
rule tells agents when to run them.

## Verification

- **Replay.** Feeding the sun-fbaf80 controller rollout through the counter logic
  pauses its long turn at 4 h active, not later, and does not pause its earlier
  4.0 h turn twice.
- **Fire rate.** Replaying the 30-day store through the hook's counting (root
  calls, tree spawns and active time, compactions) gives the pause rate the user
  approves numbers against; the gate under Limits applies.
- **Live probes, per harness**, recorded as capability facts: a deny holds for
  every tool, including `Agent`/`Task`, `spawn_agent` and `wait_agent`; whether
  Codex PreToolUse fires per `exec` or per nested call (ops-daf2cd); PreCompact or
  PostCompact and SubagentStart fire for hooks; a refused turn can still park and
  end; UserPromptSubmit fires on a typed prompt and does not, or is filtered, on a
  task-notification wake; Codex worker and Claude Code subagent calls carry
  `agent_id`; whether Codex has PostToolUse, which decides its in-flight rule;
  the names and reach of Claude Code's task controls (`TaskStop`, `KillShell`)
  and Codex's `close_agent` and `write_stdin`.
- **Tests** cover, at least:
  - active time: eight back-to-back half-hour calls count 4 h and pause; a
    half-hour `wait_agent` with a silent child counts in full; a call with no
    PostToolUse closes at the agent's next event or Stop; an `AskUserQuestion`
    left open overnight counts nothing; idle gaps over 10 minutes with nothing in
    flight count nothing;
  - counter grouping across root, Claude Code subagents and Codex workers, and
    the genuine-prompt rule (shared fixtures with obs's adapters);
  - the budget directive: honoured on the first typed line; ignored, with the
    hook's notice, on a later line, inside a code fence, after `>`, inside a
    `<pasted_content>` block, when malformed, and when two directives appear;
    scaling and named overrides;
  - the shell validator: each allowlisted command passes; each operator,
    expansion, redirection, path-qualified program, write-capable option and
    unlisted subcommand is refused; Codex `exec` bodies with one literal
    `exec_command` pass and bodies with a second statement, a variable or a
    template literal are refused;
  - cancellation after grace: an exhausted session can `kill` its own background
    process and `close_agent` its worker, and cannot `kill` a process outside its
    harness's tree;
  - root versus child refusal text, refused edits to the state and limits,
    concurrent writes, unreadable state, and the warning firing once.

## Left to the builder

The hook's language and file layout inside hq, the state file format, the exact
notification command, the parsing of Codex code-mode `exec` inputs for spawns, and
how Claude Code's session id reaches `hq pause status`.

## Activation

Wiring the hook into live harness settings changes a live global surface. It needs
the user's separate approval after implementation, as `just link --apply` from main.
