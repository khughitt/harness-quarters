# Codex long waits — brief

Scoped 2026-10-08 from `hq-4ea6fb` and `hq-239c16`. Follows lore's
`docs/notes/2026-09-27-waiting-loops-brief.md`, which set the current wait clause.

## Problem

A Codex agent waiting on a child or a long command should cost a handful of requests
*and* look alive to the user watching it. The current guidance buys the first by giving
up the second, and Codex's own instructions forbid that trade.

## Current behaviour and evidence

- **The global rule** (lore, Processes) tells a Codex controller to wait "at its
  longest": `wait_agent` with `timeout_ms: 3600000`, an empty `write_stdin` with
  `yield_time_ms: 300000`, "never a loop of shorter waits". It came from the
  waiting-loops research (`ai-952dec`): 60 s `wait_agent` calls timed out 60% of the
  time, 300 s calls 14%, and a long wait returns as soon as the child finishes.
- **Codex base instructions** (Codex 0.160.0, session
  `01a0fba6-b334-7252-a61e-7aedd3e230bb`, the session behind `hq-4ea6fb`): "Avoid
  performing blocking sleep or wait calls longer than 60 seconds, as they may prevent
  you from communicating with the user", and the user "should not be left without a
  commentary update for more than 60 seconds during ongoing work".
- **Codex developer message**, same session: "When calling `wait_agent`, prefer longer
  waits (minutes) to avoid busy polling." Codex disagrees with itself.
- **superpowers `using-superpowers/references/codex-tools.md`** "Waiting on children"
  (vendored in lore): wait in 5–10 minute stretches and, after each, "post one status
  line, run `list_agents`, and chase any child that finished without reporting".
- **`hq-239c16`** (Codex 0.160.1, session `01a115f4-1868-7ac3-af84-1294569525a8`, obs):
  a delegated test gate ran an 11-minute silent suite; the controller looked stalled,
  though the worker finished normally and handed off 66 s after the suite ended. The
  session mixed `yield_time_ms` 1000 (30 calls), 60000 (11) and 300000 (6).

## Constraints

- Codex does not wake a controller when a child finishes (`controller-wake`, false on
  0.156.1), so it must wait inside the turn.
- Layering: core, then profile, then repository, then the user. Codex's base
  instructions sit below all of them, but nothing in the rule says it knowingly
  overrides the 60 s line, so a Codex agent sees two binding constraints.
- The global rule's owner is lore. hq owns the capability facts and the Codex settings
  (`codex/config.toml`, `background_terminal_max_timeout`).

## Alternatives

- **A. Long waits, announced.** Keep the longest waits. Before each one, post a
  commentary line naming what is awaited, its expected length and the wait's limit.
  After each one, post one status line. The rule says outright that it outranks Codex's
  60 s guidance. Covers both ideas at no request cost. **Lean.**
- **B. Stretches.** Adopt superpowers' 5–10 minute stretches with a status line after
  each. The user hears something more often, at a small request cost. The rule and the
  vendored reference would then agree.
- **C. 60 s waits in interactive sessions.** Obey Codex. This brings back the measured
  60% timeout rate and the polling cost that the research removed.

## Unanswered questions

1. Does the global rule override Codex's 60 s blocking-wait and commentary lines, and
   with which cadence: A's single long wait or B's stretches? *Answered by the user
   2026-10-08: A, one long wait with a line before and after it.*
2. Does user input during a long `wait_agent` or empty `write_stdin` end the wait, so
   the user can steer mid-wait? If it does, the base instructions' reason ("may prevent
   you from communicating") is moot. *Research `hq-e314e7`, a Codex probe. It no
   longer gates the rule edit; it records whether the user can steer mid-wait.*
3. Would a long silent suite be easier to read if the test front door printed phases and
   elapsed time? *Not asked here: `tt` belongs to ops. Raise it with ops only if A or B
   still leave `hq-239c16`'s case unclear.*

## Proposed decomposition

- Goal `hq-3e69a7` holds both ideas.
- Rule edit `lore-cd01f5` (filed 2026-10-08 after the user's answer): announce each
  long wait before and report after, and say the rule outranks Codex's 60 s guidance
  and the vendored codex-tools stretches. `hq-4ea6fb` and `hq-239c16` close when it
  lands.
- Research `hq-e314e7` answers question 2 and records a capability fact; it no longer
  gates anything.
