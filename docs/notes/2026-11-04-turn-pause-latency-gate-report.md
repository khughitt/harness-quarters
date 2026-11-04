# Turn-pause latency gate: failed, design review required

Type: verification report. Owner: hq-e60ecb under hq-e10b76 and hq-2dd09b;
execution workspace/branch controller: hq-c58737. Status: Task 4 stopped at its
latency gate; Task 5 unstarted. This is the author's verification report, not an
independent whole-branch review or approval to activate the changes.

## Frozen inputs and result

Measured code: hq `45d430de23fb3c9fff38600a055c966b50b897ee`, especially
`tools/measure_turn_pause.py`, `tools/turn_pause/state.py`, `history.py` and
`hook.py`. Main was checked as an ancestor immediately before measurement.
The implementation plan is `34357c02e62c0d7d64197312834f41bf8e04caf6`,
`docs/plans/2026-11-04-turn-pause-reliability.md`; original design `95773e6e`
and approved guard addendum `90740430` remain unchanged.

Full raw result: [latency-full-45d430de.json](../../tasks/files/hq-e60ecb/latency-full-45d430de.json).
Every named case fails the unchanged p99 <50ms requirement.

| Harness | Case | Timed PreToolUse samples | p50, ms | p99, ms |
| --- | --- | ---: | ---: | ---: |
| Claude Code | Serial |1000|42.54|128.65|
| Claude Code | Concurrent |4000|50.14|406.51|
| Codex | Serial |1000|98.39|166.57|
| Codex | Concurrent |4000|66.45|206.44|

Each concurrent case has two roots, each with one root and one worker client.
Each client makes1000 calls. Both root records retain128 events, each root counts
exactly1000 root attempts despite worker activity, and all in-flight calls close.
The script asserts counter correctness and the131072-byte event bound; these
assertions passed in every case. The initial host-budget grant was16 workers;
the benchmark used four concurrent clients. The complete run took approximately
9.7 minutes, measured from its immediately preceding code-freeze commit to its
result-file write, rather than from an internal monotonic total timer.

The run executes the real entry, including its `python3 -S` shebang, over
temporary synthetic stores. PreToolUse wall time is measured; PostToolUse closes
each call outside the timed interval. Quantiles use nearest rank. Environments
are constructed key by key with temporary homes/state/runtime directories and a
notification stub. No live store, transcript, launcher or settings pointer was
used or changed.

## Correctness and measurement checks

The final focused command was:

```text
just test-one tools/test_turn_pause_hook.py tools/test_turn_pause_history.py tools/test_turn_pause_state.py tools/test_turn_pause_prompt.py tools/test_turn_pause_migrate.py tools/test_turn_pause_replay.py -q
```

It passed324 tests in26.49s at the measured source revision. Mandatory
`just check-hygiene` and `git diff --check` passed before that commit. This covers
the previously failing late-wake regression, both harnesses, guard privacy and
validation, turn identities, notification/reset/end races, ordered end/resume,
cleanup rechecks, capacity/expiry/debt and atomic-write failure boundaries.
Broad suites were deliberately omitted under validated policy; there is no
remote evidence. A passing correctness run is not a passing latency gate.

The first pilot had a measurer bug: invoking Python explicitly bypassed the
entry's `-S` flag. Its result is diagnostic only. A real `sitecustomize` regression
test failed before the invocation fix and passed afterward. The corrected pilot
completed all cases, with serial44.48/44.53ms and concurrent maxima52.76/59.28ms.
The authorized full run followed only after reading those verdicts; four pilot
samples cannot establish a reliable99th percentile. Its target/buffer remained
unchanged, and the full result above is the failed acceptance evidence.

One isolated cProfile diagnosis of a full-buffer call showed about26ms inside
the profiled entry, including about7ms loading/parsing/validating state and5ms
in fsync. It is instrumentation, not an uninstrumented latency baseline or an
explanation of the full-run tail. Raw profiles, scripts, pilots, focused logs
and the full execution ledger remain in the controller's retained workspace.

## What is known and unknown

The implementation did not meet its gate on this run. The cause has not been
isolated between persistence costs, process/scheduler delays and changing host
contention. There was no contemporaneous idle-host baseline or continuous
contention record. An initial worker grant does not prove an uncontended run.
The large difference between serial medians merits a controlled comparison; it
does not establish a Codex-specific defect or prove host contention.

Fixture payloads were used with synthetic identifiers and temporary storage.
The short benchmark root/worker identifiers do not reproduce native identifier
widths. A follow-up should match those widths in both compared variants. No
claim of a performance regression against main, production latency, or a
passing real-host rollout follows from these results.

## Recommended review disposition

Keep the50ms target and128-event/128KiB contract while diagnosing the failure.
Do not approve this implementation for activation or mark Task 4 complete.
The approved plan's Task 4 Step6 explicitly returns a latency failure to design
review; no threshold, history bound or persistence architecture has been changed.

Recommend approving one controlled baseline/candidate diagnostic in an idle-host
window of approximately25 minutes, before deciding whether storage must change:

1. Use main's and the candidate's explicit entry paths, with separate synthetic
   stores seeded by their respective code/formats. Never point an old hook at a
   version-1 store or repoint a shared launcher. Preserve the real startup flags,
   identical native payload/identifier widths, filesystem, limits and load shape.
2. Establish the quiet window, record its resource/budget evidence and capture
   load observations. Run the smallest baseline/candidate pilot through every
   case and its verdict, checking counter/bounds integrity before a longer run.
3. Compare one1000-sample serial/concurrent pass for each harness and variant;
   retain case-level results and budget/contention evidence. Estimate5 minutes
   for preparation/pilots, about15–18 for measurements and2–5 for analysis.
   Adjust the estimate from the pilots before committing to the long passes.
4. Report whether main also misses50ms, which component adds time, and what
   remains uncertain. Bring any proposed schema, bounds, architecture or latency
   requirement change back as a separately reviewed design revision. No automatic
   retry, budget increase or activation is included.

Approval of this disposition authorizes that bounded diagnostic work under the
existing Task 4; it does not accept the failed latency result, alter the binding
design or waive the remaining branch/activation gates. Alternatives are to defer
history or request a revised persistence/retention/latency design now; neither
alternative has enough controlled evidence here to be the recommendation.

Task 3's continuation is complete at `7c617a53`. Task 4's correctness-passing
implementation is frozen at `45d430de` but remains incomplete on latency. Task 5,
the fresh whole-branch review, obs handoff and separate live activation remain
outstanding. Both the hq branch and independently owned lore branch remain
unmerged; no live change or push occurred.
