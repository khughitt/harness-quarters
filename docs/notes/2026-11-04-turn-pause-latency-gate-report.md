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

## Controlled idle-host baseline/candidate diagnostic (2026-11-04)

Before measurement, advanced `main` (`4971a8c43bec41dbf66fa283615c5773591a57e5`,
including `hq-e51fac` advisory automatic compaction) was merged into `fix/hq-2dd09b`
at `0a8907a4e556eaf9b48e199bdafe7456d19ec148` (`685 passed` across all ten turn-pause
and `hq pause` test modules; `just check-hygiene` clean). `tools/measure_turn_pause.py`
was updated to use native-width identifiers matching the recorded hook fixtures in
both variants: 36-char UUID roots (`7f0c44c1-4c1f-40da-9a15-aa0917fa0728`/`.29` for
Claude Code; `01a19737-5420-7280-9b27-80cdf4ba57c6`/`.c7` for Codex), native worker
IDs (17-char hex for Claude Code, 36-char UUID for Codex), and native-width call IDs
(30-char `toolu_...` for Claude Code, 41-char `exec-...` for Codex).

The host was verified idle before starting (`host-load`: 1s/1m/5m/15m load `0.62 0.77 1.32`
on 32 CPUs, `0.39 0.44 0.61` at the start of the 1000-sample baseline pass; 16-worker
`host-budget` grant). Separate temporary synthetic stores were used for three sequential
1000-sample passes:

1. **`main` baseline** (`main`'s `tools/turn-pause` entry, unversioned `RootState` JSON,
   720–762 B state file): [latency-1000-main.json](../../tasks/files/hq-e60ecb/latency-1000-main.json).
2. **Candidate with 128-event buffer** (`fix/hq-2dd09b`'s `tools/turn-pause` entry,
   version-1 `RootRecord` JSON seeded with 128 events, 91,859–92,156 B state file):
   [latency-1000-candidate-128events.json](../../tasks/files/hq-e60ecb/latency-1000-candidate-128events.json).
3. **Candidate with 1 event (unseeded)** (`fix/hq-2dd09b`'s `tools/turn-pause` entry,
   version-1 `RootRecord` JSON with only the initial `turn_start` event, 1,690–1,732 B
   state file): [latency-1000-candidate-1event.json](../../tasks/files/hq-e60ecb/latency-1000-candidate-1event.json).

### 1000-sample comparison table

| Variant | Harness | Case | Samples | State bytes | p50, ms | p95, ms | p99, ms | Max, ms | Loadavg before -> after | Verdict (<50 ms) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `main` (unversioned) | Claude Code | Serial | 1000 | 732 | 29.47 | 44.64 | 46.60 | 47.91 | 0.39 -> 0.96 | pass |
| `main` (unversioned) | Claude Code | Concurrent | 4000 | 755 | 30.50 | 41.89 | 47.96 | 52.14 | 0.96 -> 3.28 | pass |
| `main` (unversioned) | Codex | Serial | 1000 | 720 | 29.51 | 44.28 | 46.80 | 49.09 | 3.28 -> 1.89 | pass |
| `main` (unversioned) | Codex | Concurrent | 4000 | 762 | 33.20 | 42.65 | 49.58 | 93.18 | 1.89 -> 3.86 | pass |
| Candidate (128 events) | Claude Code | Serial | 1000 | 92,118 | 42.90 | 55.74 | 59.96 | 67.01 | 3.86 -> 1.84 | fail |
| Candidate (128 events) | Claude Code | Concurrent | 4000 | 92,156 | 46.43 | 59.89 | 69.04 | 98.64 | 1.84 -> 4.19 | fail |
| Candidate (128 events) | Codex | Serial | 1000 | 91,859 | 41.75 | 54.83 | 59.59 | 64.87 | 4.19 -> 2.03 | fail |
| Candidate (128 events) | Codex | Concurrent | 4000 | 91,893 | 46.23 | 57.85 | 64.56 | 187.65 | 2.03 -> 5.09 | fail |
| Candidate (1 event) | Claude Code | Serial | 1000 | 1,708 | 36.73 | 49.13 | 53.91 | 58.49 | 5.09 -> 3.04 | fail |
| Candidate (1 event) | Claude Code | Concurrent | 4000 | 1,732 | 40.73 | 52.28 | 59.69 | 79.22 | 3.04 -> 5.20 | fail |
| Candidate (1 event) | Codex | Serial | 1000 | 1,690 | 36.72 | 50.42 | 54.02 | 113.69 | 5.20 -> 2.92 | fail |
| Candidate (1 event) | Codex | Concurrent | 4000 | 1,732 | 40.49 | 54.81 | 64.47 | 290.96 | 2.92 -> 5.19 | fail |

### Answers to the four diagnostic questions

1. **Does `main` also miss 50 ms on an idle host?**
   No, `main` passes all four cases (`p99 = 46.60 ms`, `47.96 ms`, `46.80 ms`, `49.58 ms`),
   but with only **0.42 to 3.40 ms of p99 headroom** below the 50 ms threshold.
   Direct microbenchmarking (200 iterations) shows why `main` starts near 30 ms p50:
   cold `/usr/bin/python3 -S` process spawn alone takes `14.59 ms`, importing
   `turn_pause.hook` takes another `12.42 ms` (`27.01 ms` before `decide()` runs), and
   a single 750-byte temporary-file `fsync` + `os.replace` takes `1.85 ms`.

2. **Was the earlier 98 ms Codex serial median / 128–406 ms p99 caused by a Codex bug or host contention?**
   Transient host contention. On the idle host, Claude Code and Codex have nearly
   identical serial medians (`29.47 ms` vs `29.51 ms` on `main`; `42.90 ms` vs `41.75 ms`
   on candidate with 128 events) and serial p99s (`59.96 ms` vs `59.59 ms`).

3. **Which components in the candidate add the ~12–16 ms p50 and ~13–21 ms p99 over `main`?**
   Microbenchmarking (200 iterations per operation on the same filesystem) isolates two
   distinct additive costs on every `PreToolUse` (and every `PostToolUse`, which doubles
   lock-hold duration under concurrent worker/root contention):
   - **Directory `fsync` in `write_atomic` (`+1.43 to +1.59 ms` per write in isolation,
     `+4–7 ms` under sustained/concurrent write load):** `main` performs one `os.fsync`
     on the temporary file before `os.replace` (`1.85 ms` at 750 B). Candidate's
     `write_atomic` adds a second `os.fsync` on the parent state directory after every
     `os.replace` (`3.28 ms` at 1.7 KB; `3.75 ms` at 92 KB). Even with 1 event (`1.7 KB`),
     the extra directory `fsync` pushes 1000-sample p99 from `46.6–49.6 ms` to
     `53.9–64.5 ms`.
   - **Per-call 128-event (`~92 KB`) JSON read/validate/re-encode/write (`+4.81 ms` CPU
     + `+0.48 ms` file `fsync` per call in isolation, `+5.0–6.2 ms` p50 in 1000-sample
     runs):** On every `PreToolUse` and `PostToolUse`, `parse_record` parses the 92 KB
     record with `object_pairs_hook=_unique` (`1.46 ms`, 1,024 dict callbacks vs `0.97 ms`
     plain `json.loads`), re-serializes all 128 events via `encode(events)` just to
     recheck `MAX_BYTES` (`0.92 ms`), and runs `validate_event` + `validate_snapshot`
     across all 128 historical events (`1.52 ms`, totaling `3.90 ms` for `parse_record`
     at 128 events vs `0.23 ms` at 1 event), before `record_json` serializes the 92 KB
     record again (`0.92 ms`).

4. **What remains uncertain?**
   Whether removing redundant hot-path validation/re-encoding on unchanged historical
   events and omitting directory `fsync` on ordinary counter ticks (keeping directory
   `fsync` only on lifecycle transitions or keeping history in a separate append/transition
   file) is sufficient to hold 1000-sample concurrent p99 below 50 ms given `main`'s slim
   `0.42–3.40 ms` headroom, or whether the `RootRecord` hot path must separate active
   counter state from transition history so ordinary `PreToolUse`/`PostToolUse` calls
   never read or rewrite the 128-event history buffer.

### Recommended design revision for user decision

Because `main` already sits at `46.6–49.6 ms` p99 (`0.42 ms` margin on Codex concurrent),
rewriting a 92 KB 128-event history array and running two `fsync`s on every ordinary
`PreToolUse`/`PostToolUse` call cannot reliably meet `<50 ms` p99. Recommend a bounded
design revision that keeps the 50 ms p99 gate and the 128-event / 131,072-byte history
contract by **touching the 128-event history only on lifecycle transition events** (or
eliminating hot-path full-history re-validation and directory `fsync` on non-transition
counter ticks, or storing the 128-event buffer in `<stem>.history.json` updated only when
a transition event is appended while `<stem>.json` holds the compact ~1.5 KB active/guard
envelope). No code or contract change is made in advance of that decision.
