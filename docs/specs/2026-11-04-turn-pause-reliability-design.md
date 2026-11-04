# Turn-pause reliability and reviewable interruptions

Type: design. Status: proposed, awaiting human review before implementation plan.
Owners: hq-c58737, hq-704fe5, hq-e10b76 under hq-2dd09b.

## Intent and authority

The user accepted hq-7fb9d5's seven-case audit and requested actionable fixes that
let authorized implementation continue while retaining safeguards against runaway
execution. The goal and three task bodies preserve that request; the audit is
`tasks/files/hq-7fb9d5/interruption-audit-report.md`. Four audited stops exhausted
no configured limit, and three reflected policy during progressing plans. This
is a selected sample, not a population false-positive estimate.

The choices below are the author's recommendations, not previously approved user
decisions. Approving this document approves preparation of an implementation
plan. It does not activate hooks, change global instructions, merge into live
main, authorize a service, or authorize a push or PR. The plan is a separate
human review gate. Existing 16-hour/root-call protections remain in force.

## Current behavior, verified in the tree

`Judge` checks crossed limits and protected-path strings before its paused
allowlist. `protect.touches_protected` cannot distinguish reading a wiring file
from editing it. The allowlist already has a strict shell scanner, literal argv
parsing and constrained reader options; `tasks attach` is classified as a read
despite its record mutations, so a generic read verdict is not a safe exemption.

`Store.locked` applies each root's state update under flock and atomically
replaces a JSON file. A genuine prompt replaces the turn; SessionEnd deletes the
state; seven-day pruning deletes idle state. No durable history remains.
`hq pause status` and `limits` are the existing read-only CLI surfaces. The hook
notifier records launch/socket success or error, never proof of human receipt.

The direct fixes already prepared on this branch make warnings nonblocking and
condition goal pausing on an explicit user request. Their reviewed implementation
is f7259d9098f66ed2e60fa14f9aeb22824f2ba53d. They are not yet active.

## Approaches and decisions

Use the existing strict reader grammar for protected-path reads. A dedicated
inspection command would add selectors and duplicate filesystem access; a broad
shell exemption would allow mutation. Neither is needed for the observed reads.

Raise the default hard spawn cap to 60, with the existing 75% warning at 45.
Compare 90 and warning-only below. Keep the other limits and the strict
above-limit boundary. This retains an independent fanout backstop.

Keep a bounded transition buffer in the same atomic record as current state.
Separate state and journal files introduce a two-write recovery problem; moving
all current counters to SQLite would replace the persistence system for this
feature. Co-location gives one commit point with the existing root lock and
atomic replacement. The cost is bounded extra parsing/serialization on each call,
which must pass the existing hook latency checks before activation.

## Safe read-only diagnostics — hq-c58737

When an input names protected paths, allow only a positively identified safe
reader: Claude's native Read/Grep/Glob tools, or a single Bash command accepted
by the existing scanner whose program is an explicitly enumerated filesystem
reader. Reuse the present cat/head/tail/wc/ls rules. Add only `readlink -f` with
one or more literal path operands for pointer resolution; reject all other
readlink options and option-like operands. Do not permit arbitrary executables,
interpreters, wrappers, redirects, pipes, substitutions, shell expansion or
compound commands. A merge followed by a read remains refused as one compound
request; the caller must separate the operations.

Limit the exemption to these tool/program identities and their validated
arguments. `tasks attach`, other task operations, cancellation, hq bookkeeping,
unknown tool names and arbitrary extra shell execution fields cannot qualify
merely because a classifier labels them read-like. Inputs outside this boundary
retain protected-path rejection. State, limits, trust and wiring mutations remain
protected; no read clears a pause, changes counters or resets grace.

Before a pause, safe inspection proceeds under normal counters. While paused,
these reads use the existing per-agent 25-read grace; bookkeeping and owned
cancellation retain their existing treatment. Update refusal/recovery text to
name the supported route. A host-pointer audit can list launcher/unit/include
locations, then resolve literal entries with readlink; the guidance must show
the complete known inventory, including user systemd units and declared config
includes, and report unreadable or uninspected scope rather than claim a clean
audit. No shared host pointer is repointed for a test.

Trust boundaries are tool arguments and shell text. Assets are the live guard,
trust/wiring and host pointers. Abuse tests cover writes disguised as readers,
extra execution fields, task attachment side effects, command composition and
reader options that execute or follow indefinitely. This remains a cooperative
guard, not an operating-system sandbox or a claim that arbitrary executable
replacement on PATH is prevented.

## Measured spawn policy — hq-704fe5

The declared pass selected the audit's six roots in
[2026-11-01T00:00:00Z, 2026-11-04T04:00:00Z), taking seven case snapshots at their
audited stop times. It added the October runaway as a labelled out-of-window
positive control. Audit A and F are the two labelled multi-step executions;
B is valid long implementation; C/D/E/G are warning/interpretation cases.
Labels are inherited from the accepted audit, not newly inferred from counters.

The existing converter and replay read each selected tree once per run and
compare all policies. The pilot exercised A/F/control: 3 roots, 174 files,
18.23 seconds. The one full pass read 7 roots and 217 files in 5.63 seconds,
producing eight snapshots and no scheduled-record problems. Sources did not
change size or mtime during their individual reads; this is not a transactionally
frozen collection. Script, pilot and full JSON are attachments on hq-704fe5:
`spawn-policy-measure.py`, `spawn-policy-pilot.json`,
`spawn-policy-measurement.json`.

| Candidate | A at 31 spawns | F at 30 spawns | Original runaway first pause |
| --- | --- | --- | --- |
| Current 30 | Spawn pause, 2.5526 active hours | No hook pause; no remaining spawn allowance | Root call 501, 9.8567 active hours |
| Proposed 60 | No spawn pause; 29 remaining | 30 remaining | Same |
| 90 | No spawn pause; 59 remaining | 60 remaining | Same |
| Warning only | No standalone spawn pause | No standalone spawn stop | Same |

Warning-only was replayed with a very large finite surrogate; it is not a
proposed configuration value. No sampled turn has an explicit budget. The other
five audited snapshots remain below the unchanged hard backstops in all four
candidates. The control's eventual totals differ from the frozen original
measurement; its stable first refusal is the relevant comparison here.

Choose 60 because the observed eleven-step implementation/review workflow used
30 agents before whole-branch review; another 30 dispatches gives room for that
review and corrections without removing the independent fanout guard. Frozen
historical p99.9 spawn counts of 38/50 support checking above 30, but do not by
themselves choose a number. Reject 90 for this revision because this labelled
sample establishes no extra requirement for it. Reject warning-only because a
small number of root calls can launch children that themselves fan out before
the time/root-call limits act.

This is a conservative policy judgment, not a proven optimum. Larger legitimate
plans can still stop at 61; a low-call runaway can spawn 30 more agents than
today. Replay cannot observe work prevented by the actual interruption or
guarantee successful completion of the interrupted plans. Keep the independently
eligible November 11 reassessment hq-b9d356.

Implementation changes the default cap and its dependent tests/docs, not the
counter algorithm or review requirements. Budget scaling remains proportional:
12h gives 45 spawns and 48h gives 180; explicit named agent allowances still win.
The call/time/compaction budgets keep their existing scaling and units. Changing
the live limits file still triggers `limits-changed` for old turns; activation
must account for it rather than silently resetting a turn.

## Durable transition history — hq-e10b76

Extend the root record to an explicitly versioned envelope containing current
state (nullable), durable root identity, and a bounded ordered transition buffer.
Retain the existing per-root flock and atomic replacement. All counter/state
updates and their transition records commit together; no separate append can
claim a warning or pause whose state write failed. Existing active JSON records
need an explicit, reversible migration during the separately approved activation
window, preserving exact counters, budgets, paused state and ownership. There is
no silently accepted second format or steady-state compatibility layer. Prevent
old hook code from writing migrated records during cutover.

Give each new root record a random generation id and each genuine turn a
monotonic sequence within that generation. Event identity is
`(harness, root, generation, turn, sequence)`. Repeated refusals add no transition.
Record turn start, each metric's first warning, first enforced pause, notification
attempt outcome, genuine-user reset/resume and root SessionEnd. Worker or
scheduled prompts never reset identity or create a false user resume. Preserve
the previous turn's closing snapshot when a genuine prompt resets it.

Each transition includes schema version, event identity, host, UTC timestamp,
kind/reason, counts and limits, metric scope/countability, limits digest and source
`hook`. Active time is seconds; unknown Codex compactions remain null. Notification
outcome is pending/attempted/error/unknown, with channel attempts distinguished
when known and receipt always unknown. Current notifier success cannot prove a
relay notice was delivered or a desktop notification seen; do not manufacture
channel certainty from its aggregate result. Store bounded error categories,
not unrestricted exception text that may contain host/private values.

An enforced-pause event means the hook committed a refusal decision. It does not
prove the harness obeyed it; outside evidence can corroborate actual denial.
A crash after commit and before returning output leaves that delivery unknown.
After restart, generation and sequences persist. Normal state-write errors
retain existing fail-closed enforcement and surface the actual error; do not
claim a successfully recorded event when the write failed.

Keep at most 128 transitions and 128 KiB of transition payload per root; evict
oldest complete events and record the dropped count and earliest retained time.
Clear current state at SessionEnd or idle-state pruning while preserving history.
Keep ended-root history for 30 days and at most 512 ended roots. Reuse SessionEnd
maintenance with a separate catalog lock, releasing the current root lock first;
inspect file metadata and recheck under each target's root lock before deleting.
Never evict active state. Cap deletions at 32 per maintenance call and expose any
remaining cleanup debt; normal transition payload writes stay bounded. No new
daemon or timer is introduced. Expiry and collection are lazy when hooks are idle;
report that fact rather than promise deletion at an exact wall-clock deadline.
Do not store prompts, tool arguments/results, command text, credentials, cwd,
notification bodies or private configuration in history. Native root/host ids
exist solely for local correlation and remain in mode-0700/0600 storage.

## Read-only handoff and self-stops

Add `hq pause history [--session ID] [--harness NAME] [--since RFC3339]
[--until RFC3339] [-n N] [--json]` for bounded event rows, newest first, and
`hq pause list` with the same filters for root/turn summaries. No session filter
means the local store, not an implicit current-directory session. Default limit
50; maximum 1000. Invalid ranges, malformed records or unsupported versions fail
visibly. Neither command runs document providers, reads transcripts or writes
state. While paused, both spend read grace; status/limits retain bookkeeping.

Version-1 JSON contains `observed_at`, host/store coverage, the requested window,
returned events/summaries, truncation and retention bounds, cleanup debt and
diagnostics. Records carry the identity and metrics above. A missing store is
reported as unavailable coverage, not proof of zero interruptions. Selection
limits and retention gaps are explicit. Document this schema with portable
fixtures for obs-1450e7; do not make obs parse private JSON state files.

Self-stops are derived outside hooks. Reuse stamped task parks/lifecycle evidence
and supported session records: associate an explicit range-related stop with the
qualified session and enclosing genuine human turn; retain task id, timestamp,
source locator and the supporting evidence type. An ordinary decision/review park
alone is insufficient. Multiple matches, absent stamps, missing transcripts or
ambiguous range language stay unknown. Do not count every warning as a stop or
every decision as a range interruption. Separate observed continued work,
enforced pauses, pre-enforcement stops, ordinary human gates, resumes and unknowns.
Absence of a self-stop record does not establish continuation.

hq owns the transition producer and stable portable handoff. obs-1450e7 owns the
report/correlation consumer and its separate design/plan gate, reusing its
existing session/task associations. Include portable A–G equivalents and an
ordinary gate in the handoff fixtures so both projects use the same semantics.
Broader session/tree token, quota and learned alarm scope stays with obs-59789b.

## Verification, sequencing and builder discretion

The reviewed plan will sequence reader protection, the spawn default and the
history producer; lore-296a0f supplies matching global warning/counter guidance.
No planned feature code is authorized until both document gates pass. Direct
fixes can be activated separately only with the user's explicit approval.

Under validated `automatic_broad=false`, preserve focused RED to GREEN through
`just test-one`, plus mandatory `just check-hygiene`. Exercise safe inspection
before/after pause, grace exhaustion, writes and composed bypasses; cap60 and
crossed61 in both harnesses, budget overrides and the positive control; history
survival after reset/SessionEnd/prune, restart, concurrent workers, repeated
denials, notification failures, truncation, missing/partial evidence and ordinary
gates. Exercise crash boundaries around atomic replacement and cutover, preserving
unknown delivery rather than asserting success. Test subprocesses use isolated,
key-by-key environments and temporary stores, never live logs or real git state.

Measure the existing hook latency route with a full history buffer and concurrent
root/worker activity; the original normal-call p99 target is 50 ms. A regression
requires a design revision before activation, not a silent budget increase or a
second unreviewed persistence architecture. Review all implementation changes
before integration and obtain live activation approval afterward.

The builder may settle module names, compact serialization and fixture layout
within these contracts. Schema identity, retention bounds, failure semantics,
security boundary and threshold changes require an explicit reviewed revision.
