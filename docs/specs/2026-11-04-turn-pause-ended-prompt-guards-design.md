# Scheduled-prompt recognition after a root ends

Type: design addendum. Status: proposed, awaiting human review.
Owner: hq-e60ecb under hq-e10b76 and hq-2dd09b.

## Authority and the conflict

This narrowly amends the approved reliability design at
95773e6eb742a3a4884126de9b93538be3676d84,
`docs/specs/2026-11-04-turn-pause-reliability-design.md`.
The approved implementation plan is
3c29183b042929a43619ab2b780527fad82dd307,
`docs/plans/2026-11-04-turn-pause-reliability.md`.
Their remaining requirements and separate live activation gate stand.

Task 4 requires both clearing active state at SessionEnd and preventing late
scheduled prompts from starting a human turn. The pending cron prompts and wake
windows currently live only in that active state. The captured
`tools/fixtures/turn-pause/hooks/claude-code-ScheduleWakeup.json` shows a wake
arriving as plain UserPromptSubmit text without a scheduled-wake marker.
`engine.prompt_kind` recognizes it by comparing the text against pending state.
Clearing that state removes the information required for the comparison.

The regression test
`test_history_late_scheduled_wake_cannot_resume_after_session_end` reproduces
this using the recorded wake payload: the same text is recognized as a wake
before SessionEnd and starts a human turn afterward. The approved envelope has
no field for retaining the necessary identity once `state` becomes null; event
history intentionally excludes prompts and tool arguments. A bounded event
buffer cannot serve as an authoritative schedule registry either.

The original design explicitly reserves schema identity changes for a reviewed
revision. This addendum proposes that revision; no guard implementation is
authorized until its design and subsequent plan update are approved.

## Approaches and recommendation

The author's recommendation is a small piece of private resume metadata outside
the transition buffer. It preserves the approved behavior without retaining full
prompt text in ended records.

Keeping full active state after end would retain counters, ownership, tool
bookkeeping and private text, contradicting the agreed clearing behavior.
Clearing everything would allow the demonstrated false human resume.
Refusing every prompt after end would prevent ordinary session resumption.
Relying on a new harness provenance field is unsupported by the recorded payload.

## Envelope change

Add one required `prompt_guards` field to the unreleased version-1 root record:

```json
{"prompt_guards":{"cron":[],"wakeups":[]}}
```

`cron` contains unique, sorted lowercase SHA-256 hexadecimal digests of stripped
pending cron prompt text. `wakeups` contains unique rows
`[digest, not_before, not_after]`, with finite nonnegative UTC epoch seconds and
`not_before <= not_after`. Rows have a stable lexicographic ordering. Validate
exact keys, digest length/alphabet, numeric types excluding booleans, uniqueness
and ordering when reading a record. The empty object above is the initial value.

Before clearing active state at SessionEnd or idle pruning, derive guards from
its pending cron jobs and wakeups in the same locked atomic update as the closing
snapshot, session_end event, `state = null` and `ended_at`. Do not reconstruct
guards from transition history, transcripts or providers. They share the record's
generation, private file permissions, 30-day expiry and ended-root capacity
retention. The metadata has one digest per pending cron and one row per pending
wake; it cannot grow through late hook events. This does not introduce an
additional registry or process, nor change the transition-buffer bounds.

These are matching fingerprints, not anonymization: someone with the private
record can test guesses for short prompts. They never appear in history/list
output or portable handoff fixtures. Ended records retain no raw prompt text.

## Recognition and resumption

For an ended root, worker or injected prompts remain ineligible to start a turn.
For a root prompt that passes the existing genuine-text check, compare its
stripped-text digest against the retained guards before initializing active state.
A cron match, or a wake match within its retained window, leaves the root ended
and returns the existing scheduled-prompt/rephrase guidance. Consume a matched
one-shot wake as the current engine does; retain cron matches. A nonmatching
genuine root prompt atomically clears guards and starts the next turn in the
same generation. Late PreToolUse remains refused until that resumption.

This preserves the existing limits of scheduled-prompt recognition: only known
pending cron text and wake windows can identify an otherwise unmarked wake.
After the entire root record expires or is evicted, its identity and guards are
unavailable; any later record starts a new generation with unknown prior coverage.
The implementation must not claim permanent wake provenance or human receipt.
If the user types text matching a pending scheduled prompt, they must rephrase
it, as under the current active-state rule.

## Migration and verification

The prepared version-1 format has not been activated and all conversion runs so
far used temporary synthetic stores. Revise that unreleased format explicitly;
do not add a runtime reader for its earlier shape. Legacy-to-version-1 conversion
preserves complete active state and initializes empty guards. Rollback export
continues exporting current active states only and retains the source envelope.
Previously generated synthetic records are recreated rather than silently read
through a compatibility layer. Any discovery of a real prior version-1 cutover
blocks this assumption and requires a migration decision before activation.

Extend Task 3 validation/conversion tests and Task 4 lifecycle tests in the plan
update. Exercise recorded unmarked cron/wake payloads before and after end/idle
clearing, expired wake windows, worker/injected prompts, genuine nonmatching
resume, human text matching a guard, restart, duplicate/invalid guard rows,
concurrent end/resume, and unchanged ended_at expiry despite late events.
History/CLI tests must prove that guard digests and raw prompts are absent from
the public handoff. Hash only at end or ended-prompt recognition; preserve normal
PreToolUse's hot import invariant. The full-buffer serial/concurrent p99 target
remains below 50 ms for both harness paths.

After design approval, write and separately freeze the implementation-plan
update before implementing this schema change or resuming dependent Tasks 4–5.
The builder may settle private helper names and hash batching, within these
contracts. This addendum authorizes no live operation, main merge or push.
