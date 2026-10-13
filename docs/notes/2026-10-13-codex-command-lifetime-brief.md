# Codex command lifetime — brief

Scoped 2026-10-13 from `hq-3be737`. Siblings in the same pass: `hq-da1015` (scoped,
a Claude Code `/hooks` omission) and `hq-872750` (drop proposed, covered by relay's
`relay-eaca0e`).

## Problem

An agent that starts a server for the user to use (a preview, a lab page) needs it to
keep running until the agent or the user stops it, and needs to know in advance whether
the harness will keep it alive. In Codex, a command left running in an `exec_command`
session was ended by a signal nobody asked for. Neither the cause nor any lifetime
promise is known, so agents work around it by guessing.

## Current behaviour and evidence

- **The report** (mind6 controller session `01a12f9f-8550-7973-832b-e6fd98ffb80c`,
  Codex 0.162.1, 2026-10-13): a preview wrapper was started in an exec session (id
  66391, with a TERM trap that reaps its server group and deletes a temporary store).
  The session became ready around 00:51Z and was serving at 00:55Z. The controller then
  spawned a worker (`task15_gate3`, session `01a132c2-52f5-70a1-a89a-9328eecbe9dc`)
  and waited in `wait_agent`. At 01:04Z the worker reported the preview gone. An empty
  `write_stdin` on session 66391 returned exit code 143 (SIGTERM), and the wrapper's
  cleanup had run. The application log showed no error.
- **What did not do it**: the worker's 32 commands contain no `kill`, `pkill`, `tmux`
  or port-5191 operation, and it reported never stopping the preview. The controller
  had at most 3 yielded exec sessions after 20:00 local time and the worker had 5, so a
  pruning of the oldest of many sessions is not evident. The sender is unverified.
- **The workaround**: the agent added a HUP trap to the wrapper and restarted the
  preview in a separately named tmux server (`tmux -L <name>`) with an explicit stop.
  Killing that server reaped the wrapper and server and removed the store.
- **hq's Codex settings** (`codex/config.toml`) set no exec or background-terminal
  keys. The only related knowledge is `background_terminal_max_timeout`, which caps an
  empty `write_stdin` wait (the 2026-09-27 waiting-loops research).

## Constraints

- The global Processes rule says a detached launch owns its cleanup, and a process that
  must outlive the turn is named in the report with its pid and stop command. It says
  nothing about how long a harness keeps a foreground command alive. lore owns that rule.
- `host-load --section session` lists only reparented processes, so it cannot see a
  preview the harness still parents. ops scoped `ops-ac0c70` to make its empty line say
  so. That is separate from this question.
- A capability fact is read through `tools/harness-facts`, and `unknown` is never a
  default. hq owns the Codex settings and the facts. A Codex change is upstream, and
  posting one needs the user's approval.

## Alternatives

- **A. Record the lifetime, own persistence outside the harness.** Find what Codex
  promises for a yielded exec session (a count cap, an idle timeout, a turn or interrupt
  boundary). Record it as a capability fact, and have a server that must persist use a
  named tmux server or a user systemd unit with an explicit stop, as the reporter did.
  If the instructions need to say so, file feedback to lore. **Lean.**
- **B. Configure it away.** If a Codex config key bounds or prunes sessions, set it in
  `codex/config.toml` so that previews survive. This applies only if such a key exists
  and the cause is that bound.
- **C. Ask upstream for a persistent command mode** in exec, prepared as an issue that
  the user approves. This is worthwhile only if research shows that Codex ends sessions
  by design with no setting.

## Unanswered questions

1. What sent the SIGTERM: Codex's exec-session management (and under which rule), or
   something outside Codex? *Research `hq-5e067c`: Codex 0.162.1 source and issues,
   plus one isolated reproduction.*
2. Does Codex offer a supported way to keep a command running for the session's life?
   *Same research.*
3. Should the global instructions name a persistence mechanism for servers that must
   outlive their command? *lore, once 1 and 2 are answered. File feedback there rather
   than here.*

## Proposed decomposition

- Goal `hq-69134b` holds `hq-3be737`.
- Research `hq-5e067c` answers questions 1 and 2. It records a capability fact or a
  bounded negative, and recommends A, B or C. On completion it wakes `hq-3be737`.
- No design task: the choice among A, B and C follows from what the research finds.
