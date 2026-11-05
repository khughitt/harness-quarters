# Turn-pause follow-ups: approval waits, migration and latency

## Problem

Keep turn-pause safeguards from interrupting ordinary work because of user approval
waits or an incompatible state change, without adding a service without evidence
that it is needed. This scope pass covers hq-a639e4, hq-14bab1 and hq-33ad66.
These are agent-authored follow-ups of hq-9aa713; their filing session records the
user asking to execute the existing plan and later approving activation, rather
than requesting these three additions individually.

## Current behaviour and evidence

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
migration implementation. Its branch remains separately owned and unmerged;
activation requires the existing operator window. Existing coverage research
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

## Unanswered questions

Which existing Claude Code and Codex events identify the start and end of a
permission wait, including approval, denial and cancellation? Can those events
exclude only the waiting agent's interval while concurrent work still counts?
The bounded local evidence review below answers this or names the missing
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
