# Turn accounting and pause diagnostics

Type: guide, data model; document types 1. The public history envelope and durable
root records use version 1; the reader/converter also handles the original version-0
active-state form. This describes current code, not every host's activation state.
See [capabilities](harness-capabilities.md) for hook coverage and
[test execution](test-execution.md) for the verification route.

## Limits and turn boundaries

```text
hq pause limits [--json]
hq pause status [--session ID] [--json]
hq pause history [--session ROOT] [--harness claude-code|codex]
hq pause list [--session ROOT] [--harness claude-code|codex]
```

Current defaults are 57,600 active seconds (16 hours), 2,000 root call attempts,
60 tree spawns and two root compactions. Active/calls/spawns are enforced only
when strictly above their limit; exact equality is allowed. Compactions are
advisory. Warnings start at 75% and authorize continued work within limits;
a warning alone is not a pause or request for a new budget.

Calls count the root controller's attempts, including refusals, not workers' tool
calls. Spawns count started children across the tree, deduplicated by native keys.
A session launched from the shell (`codex exec`, `claude -p`) is its own root with its
own limits: it adds nothing to the launcher's calls or spawns, and the launcher counts
it by hand, while the launcher's wait for it counts as the launcher's active time.
Active time advances for in-flight work and short idle gaps; user-input waits are
excluded. Countability depends on observed native hooks; an uncounted value is
unknown/null, never a guessed zero. Record manual unhooked counts separately.

A genuine root human prompt begins/resumes a turn. Worker/injected messages and
known scheduled wake prompts do not reset it. First-line budget text can scale
unnamed counts; explicit counts override that scaling. Preserve exact prompt
syntax and unknown counters; do not edit state/limits or start another controller
to avoid a crossed limit. Actual policy decisions belong to the governing global
instructions, not to inference from a warning message.

To set a turn budget, put this on its own first line of your human prompt:

```text
budget: 12h, 2000 calls, 80 agents, 4 compactions
```

This is a prompt line, not a shell command. Budget text later in the prompt or
inside quoted, fenced or pasted material sets no budget, and `budget:` lines
neither scale nor lift spend pauses.

Status first resolves an explicit/native session ID (workers map to their root),
then newest cwd state, then main-checkout state for a linked worktree, and
includes a `spend` diagnostic read directly from the signal file, root record
and host outage latch rather than the hook's active-state cache. Missing state
fails with what was searched. History/list instead query all local roots without
that cwd/session fallback. History is transition evidence, not proof of human
receipt or full coverage of agent-initiated stops.

## Spend signals

On `PreToolUse` and `UserPromptSubmit`, the hook stats `spend-signals.json`
under `XDG_STATE_HOME/obs` (or the home `.local/state/obs` fallback) and parses
schema 1 only when `(st_mtime_ns, st_size, st_ino)` changes; when a fresh
resolved entry for `<harness>:<root>` (including in a `partial` run) is due or
pending and no counter limit pauses first, `PreToolUse` pauses the turn with
reason `spend`, formatting root refusals (`turn paused: spend...`) from the
turn's snapshot to stop started work, record value/threshold/episode with
single-line `tasks note` calls, park `--waiting-on user --reason decision`,
report the signal and end the turn, while children get the child pause text
naming `spend` (a child-only pause leaves `delivered_value` null). Only a
genuine root human prompt lifts and acknowledges a delivered pause at
`max(seen_value, delivered_value)`; an episode that opened or went undelivered
while idle is instead injected on the next genuine root prompt as
`additionalContext` (`turn-pause: spend signal...`, setting
`delivered_value = acked_value = value` and recording `warning`/`spend` on the
new turn) so the controller reports and investigates in that turn before
resuming original work, and an acknowledged episode pauses again only at
`value >= 2 * acked_value` while a new episode id replaces the record. Missing,
stale or malformed signals fail open for tool calls and appear in
`hq pause status` as `absent` (never seen fresh on the host), `vanished`
(missing after a fresh sighting), `unreadable`, `stale` or `fresh`; `vanished`,
`unreadable` and `stale` send one desktop alert per outage via the host latch
(retrying failed alerts at most hourly until a fresh signal clears it). Stopping
the producer (`systemctl --user stop obs-spend.timer`) is the immediate off
switch — the file turns stale within `stale_after_ms`, alerting once and pausing
nothing — whereas reverting code is unsupported once `spend` fields or history
reasons have been written, so defects are fixed forward.

## Public history query envelope

History/list accept --since/--until RFC 3339 timestamps with explicit UTC offsets,
forming [since, until), -n from 1–1000 (default 50), and --json. Invalid ranges,
naive timestamps, malformed state or unknown versions fail rather than yielding an
apparently empty history. Queries read no transcripts and create no state store.

| Field | Meaning |
| --- | --- |
| version | Integer 1 |
| observed_at | Observation time as UTC epoch seconds |
| host | Executing host |
| coverage | Status available/partial/unavailable, local_store scope, per_root_atomic observation, root/event bounds, dropped events, unobserved roots and disappeared files |
| window | Applied filters and requested range |
| events or summaries | Bounded matching transition records or derived per-turn rows |
| truncated | Whether retained data/limits truncate the answer |
| retention | Store bounds: 30 days, 512 ended roots, 128 events, 131072 bytes and 32 maintenance mutations |
| cleanup_debt | Remaining bounded-maintenance work |
| diagnostics | Explicit limits/errors in the observation |

A missing store reports unavailable coverage, not zero interruptions. Events order
newest first by time/harness/root/generation/turn/sequence. Summaries order by last
retained event and identify incomplete or unobserved roots explicitly.

## Transition records and snapshots

Each event has exactly version, harness, root, generation, turn, sequence, host,
at, kind, reason, snapshot, notification and source. Version is 1; source is hook;
turn and sequence are positive integers; time is finite nonnegative epoch seconds.
Identity strings are nonempty and bounded. Accepted transitions are turn_start,
warning, enforced_pause, notification, turn_reset, turn_resume and session_end;
each permits only its declared reasons, not arbitrary event text. `enforced_pause`
(and snapshot `paused` when non-null) permits `active`, `calls`, `spawns`,
`compactions`, `limits-changed` and `spend`; `warning` permits `active`, `calls`,
`spawns`, `compactions` and `spend`, where `spend` is used only for prompt
injections of an idle episode on the receiving turn.

A snapshot is null or has active/calls/spawns/compactions `{used,limit}` pairs,
limits_sha, paused, counted and scopes. Counted metrics have finite nonnegative
usage; uncounted usage must be null. Counts/limits use integer values except active
time usage. Scope labels distinguish tree_active_seconds, root_attempts,
tree_started and root compactions. Compaction countability is a recorded boolean.

Notification is null or has outcome, error_code, desktop, relay, receipt and
pause_sequence. Outcomes are pending/attempted/error/unknown; error_code is null or
notify_failed. Desktop/relay/receipt are unknown: a committed notification attempt
is never a delivery acknowledgement. pause_sequence binds the attempt to its event.

Summaries identify harness/root/generation/turn and report nullable start/end,
origin, ending kind/reason, event counts/kinds, warnings, enforced pause,
notification, snapshot, root-active/ended metadata and truncation. A summary is
built only from observed transitions; it fabricates no turn for an unobserved root.

## Private durable state

State lives below XDG_STATE_HOME/hq/pause, or the home .local/state fallback,
with private directory/file permissions and locked atomic writes. Version 1 roots
hold version, harness, root, generation, created_at, turn_serial, event_serial,
state, ended_at, events, dropped_count, dropped_through, prompt_guards and
optional `spend` (`{episode, seen_value, delivered_value, acked_value}`). `spend`
is serialized immediately before `prompt_guards` and omitted when null, keeping
version 1 compatible with pre-spend records and preserving the
`prompt_guards`-immediately-before-`events` splice marker that `_LazyEvents` uses
to avoid parsing historical events on hot calls. Generation distinguishes
root-store lifetimes; serials order turns/events; dropped metadata records
truncation instead of pretending full retention. Beside the root records, the
dot-prefixed `.spend-host.json` (locked via `.spend-host.lock`) holds host-level
`seen_fresh` and the active `outage` latch (`{state, alerted_at, outcome, error}`
or null); root listing, pruning and `history`/`list` skip dot-prefixed entries.

Active state contains harness/root, current turn, paused reason, grace usage,
worker IDs/names, scheduled cron/wakeup state, harness pid/cwd, notification
status, budget note, and optional `spend_cache` (cached signal plus
`(st_mtime_ns, st_size, st_ino)` identity) and `spend_snapshot` (the paused
turn's spend entry snapshot, cleared when the next turn starts), both omitted
when null. A turn records started/last time, limits/digest, active/call/spawn/
compaction usage, in-flight calls/tools, spawn keys and warned metrics. Alongside
the pause state directory, turn limits, capabilities snapshot and hook wiring,
the four `obs` spend files under `XDG_STATE_HOME/obs` (or the home
`.local/state/obs` fallback) — `spend-signals.json`, `spend-baseline.json`,
`spend-state.json` and `spend.lock` — are protected paths. These private
implementation records are validated by tools/turn_pause/state.py; public
history omits cwd, private schedule material, `spend`, `spend_cache`,
`spend_snapshot` and `.spend-host.json`.

prompt_guards has cron digests and wake rows `[digest,not_before,not_after]`.
Digests are SHA-256 fingerprints of stripped prompt text, not anonymization.
Ending/idle clearing retains known guards; a genuine resume clears them until
fresh schedule evidence arrives. Late tool calls on an ended root are refused.
Expired windows/evicted records cannot establish historical provenance.

Ended roots expire lazily after 30 days or beyond 512 roots, with at most 32
maintenance mutations per pass. An individual root retains at most 128 events
and 131072 encoded bytes. Seven-day idle clearing ends abandoned active state;
maintenance does not make an old end look recent. Repeated/malformed JSON keys,
invalid types, private metadata leaks and unsupported versions are errors.

## Diagnosis and protected reads

A recorded pause proves a prepared refusal, not that an unhooked tool obeyed it.
Use status/limits for bookkeeping; history/list are reads and spend the paused
read grace (25), as do permitted literal filesystem inspections. Read-only access
never authorizes writes or clears a pause. Allowed readers use concrete paths and
restricted options; wrappers, redirection, glob expansion and compound actions
are not equivalent to a validated single read.

Single-line tasks note, tasks park and tasks feedback commands remain bookkeeping
after read grace is exhausted. Their command text is limited to 16,384 characters;
split longer pause reports across note calls. Workspace file writes and structured
question tools remain refused while paused. Put the durable handoff in task notes
and the continuation decision, including any exact budget first line, in the
closing assistant message. Other task mutations remain refused.

Before worktree disposal inspect declared launchers, user units and config includes
for targets into the worktree, including embedded paths. Resolve literal entries;
unreadable or uninspected pointers are unresolved, not clean. Never repoint a
shared launcher for a test. State conversion/live activation requires its own
approved quiescent window and exact backups; inspect current main and owner
records instead of running a historical activation document as a live recipe.
