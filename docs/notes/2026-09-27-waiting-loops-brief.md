# Waiting loops — brief

Scoped 2026-09-27 from `ai-bd5b6e`. Evidence: obs `docs/reports/2026-09-26-tool-failure-modes.md` §4
(in the obs checkout; Claude Code 2026-08-05..09-26, Codex 2026-08-27..09-26).

## Problem

Agents spend about 9.2% of their context tokens waiting: each poll re-reads the whole
context to learn that nothing has changed. The goal is that an agent waiting on background
work, a child agent or a long command costs a handful of requests, not hundreds, in both
harnesses.

## Current behaviour and evidence

Three loop shapes, each with its own mechanics:

1. **Claude main sessions: backgrounded sleep, then `ListAgents` + `sleep`.** A long
   `sleep` came back at once as a background task (1,432 such sleeps in 31 sessions,
   median 590 s requested, next call about 13 s later). The agent then looped; 46% of
   `ListAgents` calls returned the previous result. Worst case: 166 calls over 60 min, 143M
   tokens. The current harness blocks a foreground `sleep` and names Monitor or
   `run_in_background` instead (observed 2026-09-27, Claude Code 2.1.283); when that block
   arrived is not known.
2. **Claude subagents: no-op keepalives.** `true`, `echo .` or `:` while a Monitor waits:
   162 episodes, 938 calls, 23 sessions, 174M tokens. A subagent's turn end is its final
   report, so it cannot end a turn to be woken the way a main session can.
3. **Codex polling.** 67% of `wait_agent` calls time out (mostly 60 s requests); 98% of
   `write_stdin` calls send nothing and only poll a running command. 12.7k requests, 2.55B
   tokens (8.6% on their own). Codex does not start a new turn when a child finishes
   (`CHILD_WAKES`, probed 2026-09-24), so it must wait inside the turn; the question is how
   long each wait lasts. Codex 0.157.1 carries a `sleep_tool` feature and a
   `default_exec_yield_time_ms` setting, both untested here.

The global rule "Never end a turn waiting on work the harness does not track" (AGENTS.md
Processes, `ab4f636`) landed on 2026-09-24, two days before the window closed, so the
measurement is almost entirely pre-rule.

## Constraints

- AGENTS.md Processes already tells agents to wait through the harness's own mechanism, and
  a controller to end its turn only where the harness wakes it (Claude Code yes, Codex no).
  A new rule should not restate it.
- obs-f074aa (todo, obs) will detect these episodes at index time; until it lands, counts
  need a direct scan of the session stores (the `session-logs` skill).
- Codex settings live in `codex/config.toml` and `codex/config.work.toml`; Claude in
  `claude/settings*.json`. Both are live through symlinks.

## Alternatives

- **A. Harness settings first.** Claude: rely on the sleep block and ending the turn. Codex:
  enable `sleep_tool` or raise the default exec yield and the `wait_agent` timeout, if they
  do what their names say. Lean: yes for Codex, where polling is the harness's design and an
  instruction cannot lengthen a timeout the model does not choose.
- **B. Instruction per shape.** For example: a subagent runs a long check in the foreground
  with a timeout and never through a Monitor; a Codex agent passes the longest `wait_agent`
  timeout. Lean: only for the shape that settings cannot reach (Claude subagents).
- **C. Wait for the rule to show in obs.** The 09-24 rule may already have ended shape 1.
  Lean: measure before changing anything, which is the first research step anyway.

## Unanswered questions — answered by `ai-952dec` (2026-09-27)

Method: one scan of both stores with the report's detectors, comparing sessions that
started 09-10 to the rule (pre) with sessions that started after the rule (post), and
the same scan over 08-05 to 09-10 to check the detectors. That early scan found 1,409
backgrounded sleeps and 149 no-op episodes, against the report's 1,432 and 162, so the
detectors match. Two `codex exec` probes on Codex 0.157.1 settled the limits.

1. **Do the shapes still occur?**
   - *Claude backgrounded sleeps:* an August pattern. Almost all of them predate 08-28,
     and there were 13 between 09-10 and the rule. Post-rule: 2 in 248 main sessions,
     5 `ListAgents` calls, and no poll episodes.
   - *Claude no-op keepalives:* bursts on 09-01 and 09-05/06 (about 970 calls), then
     single-digit tails. Post-rule: no episodes in 251 subagent transcripts.
   - *Codex `wait_agent`:* pre-rule, 3,681 calls with 2,208 timeouts. The timeout rate
     follows the requested wait: 60 s times out 60% of the time, 45–50 s 73–80%, 10 s
     82%, while 300 s times out 14% and 600 s 11%. Post-rule: 8 calls; Codex use fell to
     20 main sessions.
   - *Codex empty `write_stdin` polls:* pre-rule, 3,511 in 254 sessions, mostly with
     1 s and 30 s yields. Post-rule: 263 polls, 258 of them in three sessions, each
     polling one long command about every 30 s.
2. **Codex limits.**
   - `wait_agent` accepts `timeout_ms` up to 3,600,000; 7,200,000 fails with
     `timeout_ms must be at most 3600000`. It returns when the child finishes: a 600 s
     wait on a 45 s child took about 46 s.
   - An empty `write_stdin` is capped by `background_terminal_max_timeout` (default
     300000). A 600,000 ms request waited 300 s without any warning, and returns early
     when the command ends.
   - `sleep_tool` is already on by default (stable) and was used 270 times pre-rule.
     `default_exec_yield_time_ms` sets the code-mode exec default; the loops come from
     waits the model chose, so it is not the lever.
3. **Claude subagent idle wait.** Not probed: the no-op loop shape has not recurred
   since 09-07, so there is nothing to fix. obs-f074aa will flag it if it returns.

Why the Claude shapes faded is not established. The drop lines up with Claude Code
releases (2.1.25x → 2.1.26x) and with the harness now blocking a foreground `sleep`,
not with the rule, which came later.

## Proposed decomposition

- Claude: no change. obs-f074aa's detectors keep watch.
- Codex: one rule clause — `ai-6d496d`, which names both waits with their limits.
- `ai-bd5b6e` is covered by `ai-6d496d`.
