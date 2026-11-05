# SDD ledger — plan: $WORK_ROOT/hq/.worktrees/hq-2dd09b/docs/plans/2026-11-04-turn-pause-reliability.md
Task 1: BASE 9d23f3e35eafa83bcc7fcf8e3f7bf75c24ab8bf5

Approved inputs: plan hq3c29183b042929a43619ab2b780527fad82dd307 sha2561c42c62673e79518887bc5a9608a4d8a52bf98456082734c5b753a4bc2fd48e2; spec hq95773e6eb742a3a4884126de9b93538be3676d84; native execution, separate activation gate.
Pre-flight: Task1 -> Task5: protected_read and exact reader identities stay distinct from history/list read grace; no conflict.
Pre-flight: Task2 -> Tasks3–5: Limits fields unchanged, default spawns60, explicit isolated30 fixtures retained; no conflict.
Pre-flight: Task3 -> Task4: RootRecord, locked(create), snapshot/append_event signatures match lifecycle calls; no conflict.
Pre-flight: Tasks3/4 -> Task5: read_record and retention are read-only; active read returns RootState or None, history coverage remains explicit; no conflict.
Ruling: one coordinated five-task plan. Why: shared hook/state/allowlist interfaces. Cost: serial execution and a longer combined review. Revision: approved plan Setup.
Ruling: native inline execution with fresh final reviewer and corrective re-reviews. Why: explicitly approved method for shared interfaces. Cost: no independent per-task review. Revision: approved plan Setup and user approval.
Ruling: migration receipts outside state stores and single-format runtime parsing. Why: prevent receipts being read as state and hidden incomplete cutover. Cost: separately approved quiesced operator window. Revision: approved plan Task3.
Task 1: baseline361 passed; RED45 failed/20 passed/346 deselected for new protected_read API and inspection refusals (task1-red.log); GREEN pending captured in task1-green.log. No threshold/counter changes.
Task 1: GREEN411 passed in11.48s; mandatory hygiene and diff whitespace check passed; import invariant included. Optional host-budget flasgger warning is unrelated.
Task 1: attempt (status 0, command: just test-one tools/test_turn_pause_allowlist.py tools/test_turn_pause_hook.py -q, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-1-tests-hZv7oC.log)
Task 1: complete (commits 9d23f3e35eafa83bcc7fcf8e3f7bf75c24ab8bf5..d35f34c7ad1dc642e68b76ae299696305ab4a543, command: just test-one tools/test_turn_pause_allowlist.py tools/test_turn_pause_hook.py -q, status: 0, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-1-tests-hZv7oC.log)
Task 2: BASE 7943d2e1a14564dcfcd363764c5e9b1df8c59c75
Task 2: RED11 failed/43 passed/108 deselected on old defaults; frozen candidate60 attachment reverified sha256af401d1d70595a07f12bbf14745138be05a2ffd17283b393420eeddb05cd27a6; A/F headroom29/30, positive control call501 at9.8567h; no rescan/replay pass.
Task 2: GREEN162 passed in13.76s; mandatory hygiene/diff check passed. Default60, warning45; two harnesses/root+worker boundaries, explicit budgets and old safeguards verified.
Task 2: attempt (status 0, command: just test-one tools/test_turn_pause_limits.py tools/test_turn_pause_hook.py tools/test_hq_pause.py tools/test_turn_pause_replay.py -q, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-2-tests-VG4Wzw.log)
Task 2: complete (commits 7943d2e1a14564dcfcd363764c5e9b1df8c59c75..29c7142ed6cca092145115fe955dc6c01d814d04, command: just test-one tools/test_turn_pause_limits.py tools/test_turn_pause_hook.py tools/test_hq_pause.py tools/test_turn_pause_replay.py -q, status: 0, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-2-tests-VG4Wzw.log)
Task 3: BASE de0e23f0f720abb89be31573cbc465fd9096d1fe

Task 3: RED 27 failed/68 passed; bounded record/converter APIs absent. Additional range-validation RED 5 failed/18 deselected. First green 234 passed; added validation exposed four existing zero-limit fixtures. Ruling: retain zero-valued stored limits and reject negatives. Why: existing engine explicitly handles zero without division errors; changing that contract is outside migration. Cost: a corrupted zero limit remains a supported immediate-boundary state. Config loader validation unchanged.
Task 3: GREEN 239 passed in focused state/history/migration/hook/replay/CLI modules; mandatory check-hygiene and diff-check pass. Runtime migration is explicit-only; old lifecycle removal deliberately replaced in Task 4 before activation. Broad suite omitted per validated policy; no live conversion run.
Task 3: attempt (status 0, command: just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py tools/test_turn_pause_hook.py tools/test_turn_pause_replay.py tools/test_hq_pause.py -q, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-3-tests-II2vyk.log)
Task 3: complete (commits de0e23f0f720abb89be31573cbc465fd9096d1fe..f2f704f2299165443adc3a6bb3a3e1f180682074, command: just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py tools/test_turn_pause_hook.py tools/test_turn_pause_replay.py tools/test_hq_pause.py -q, status: 0, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-3-tests-II2vyk.log)
Task 4: BASE 2efc20c5950a0999e2ec086d943eb21ffd77af40

Task 4: started at BASE2efc20c5950a0999e2ec086d943eb21ffd77af40, flow off. RED1 failed/106 deselected in0.38s (task4-ended-wake-red.log): captured unmarked scheduled wake changes from wake to human turn after SessionEnd. No lifecycle/retention implementation has been written.
Task 4: Ruling: stop schema implementation and propose an ended-prompt-guard design addendum. Why: approved state=null discards the only pending-prompt provenance; captured Claude wake has no source marker, and the frozen design explicitly requires review for schema identity changes. Cost: an extra design/plan review before Tasks4–5; knowingly retaining the original shape would permit false user resumes. Revisions: original spec95773e6e / plan3c29183b; proposed docs/specs/2026-11-04-turn-pause-ended-prompt-guards-design.md.
Task 4: proposed recommendation adds private hashed scheduled-prompt guards outside event history, retains state clearing and existing recognition limits. Alternatives rejected: retain complete active state (private data/contract), clear all guards (false resume), reject all ended-root prompts (no normal resume), assume unsupported native provenance. No feature implementation or live state conversion after this finding.
Task 4: proposed addendum frozen in hq907404308e3172de57f81a9175ef7da46f0c988d:docs/specs/2026-11-04-turn-pause-ended-prompt-guards-design.md SHA256009789ceebccd691d2022335192ce38b8745d0bac285ed4d22fb964c45449130; regression is committed in the same revision and remains intentionally RED. Mandatory hygiene, whitespace and tasks check exit0. No independent review of this small addendum; human review is requested. After approval, write/freeze a plan update for its separate gate, then complete Task4/Task5, latency gate and fresh whole-branch review. Do not claim branch readiness or live effect.
Closing observation: Tasks1–3 complete with focused evidence411/162/239 tests; Task4 stopped on design review; Task5 not started. Broad tests deliberately skipped under invoking checkout policy; no remote coverage, push, PR, merge to main, live conversion, pointer change or new service. Existing branch fix/hq-2dd09b remains locked and unmerged in .worktrees/hq-2dd09b, owned by hq-c58737; separate activation approval authorizes eventual integration/migration under the runbook. Foreign fix/lore-296a0f remains independently owned by lore-296a0f, unmerged/unactivated; same separate live-global approval remains required. No subagents dispatched this turn. First manual compaction used; no turn limit reached. host-load --section session reports nothing left running. Ignored pytest/Python caches are regenerable and retained with the worktree; no removal proposed. The external workspace remains the canonical evidence container, owned by the open controller through review/activation gates.

## Plan revision 2 review gate

Frozen plan: hq34357c02e62c0d7d64197312834f41bf8e04caf6:docs/plans/2026-11-04-turn-pause-reliability.md; SHA256c9302a3c6b0024c3c3199ba3560f3eed7750f353d8d88590c84525760449b829. Approved design addendum: hq90740430; human review round1 recorded on hq-e60ecb. Plan self-review round4: codex/gpt-6.1-sol, accept for human review, not execution approval; full report at docs/notes/2026-11-04-reliability-plan-r2-self-review-report.md in the frozen plan commit. No deferred minors.


Ruling: reopen hq-cc91d4 after plan approval instead of adding an overlapping
sixth child or silently treating its original completion as the new contract.
Why: the schema/converter contract changes before branch integration, and the
repository explicitly reopens closed records for pre-integration corrections.
Cost: another focused Task 3 completion, preserving its prior BASE and history.
Revision: revision-2 Setup and Task 3 continuation.

Ruling: preserve the recorded zero-valued stored-limit behavior while retaining
positive configuration validation.
Why: the tree's existing zero-limit hook tests and Task 3 execution ruling
already establish that behavior; the earlier plan's blanket positive wording
was inaccurate for persisted records.
Cost: a zero-valued stored limit remains an immediate boundary rather than a
parse error. Revision: Shared Contracts and Task 3 Step11.

Ruling: clear an imported/uninitialized active record with no known turn without
fabricating a positive turn/event identity.
Why: legacy RootState permits turn=None and migration preserves it, while event
turns are positive. Ending that state must not manufacture an observed human turn.
Cost: no synthetic session_end event for that unobserved turn; CLI must disclose
the missing turn evidence. Revision: Task 4 no-turn test and Step4; Task 5 tests.

Ruling: follow the addendum's explicit guard clearing on a genuine nonmatching
resume and disclose the resulting recognition limit.
Why: retaining guards into active matching would change the approved design and
current engine/replay contract. Known pending schedules are protected while the
ended root retains their guards; after clearing, prior schedules are unknown
until native active-state evidence records them again.
Cost: a surviving unmarked scheduled prompt can look genuine after that loss of
evidence, as it can after root eviction. The plan makes no permanent-provenance
guarantee. Revision: Shared Contracts recognition limit and Task 4 Step3, following
the approved addendum's Recognition and resumption section.

Ruling: Task 3's continuation proves its schema/helper contract separately from
the already-recorded Task 4 integration regression.
Why: hook end/resume integration is Task 4's dependent deliverable, and the task
record already owns that failing test. The focused scope is named explicitly.
Cost: the controller must not misreport a contract GREEN as a passing branch;
Task 4 and final verification require the regression to pass. Revision: Task 3
Step11 and Task 4 Step5.


Actual status: Tasks1/2 complete; Task3 original contract complete, its revision2 continuation proposed and not started; Task4 stopped before lifecycle implementation with recorded late-wake RED; Task5 unstarted. No runtime changes, new test run, latency measurement or independent branch review during this plan-writing turn. After human plan approval, reopen Task3 and run only its new continuation, then Task4/5 inline. Preserve all existing BASE values/completion ranges; new Task3 completion follows the new contract at its later HEAD. Live activation remains separate.

Plan revision2 human approved; review round5 on hq-c58737. Task3 continuation: pending, reopened hq-cc91d4; old completion only proves f2f704f2. Native execution resumes here; no old implementation sequence replayed.
Task3 revision2 baseline:167 passed in8.08s; broad baseline omitted by validated policy. RED33 failed/134 deselected in0.51s: missing prompt_guards/helper APIs, not collection/environment errors (task3-r2-red.log). Implementing required field and sorted matching helpers only; Task4 integration remains separate.
Task3 revision2 GREEN200 passed in16.49s, plus focused hot-path/zero-limit checks passed (task3-r2-hook.log); hygiene and whitespace pass. Required guard schema/helpers/converter guarantees implemented. Known Task4 late-wake regression remains pending/outside this contract-focused gate, not claimed green. No live conversion or activation.
Task 3: attempt (status 0, command: just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py tools/test_turn_pause_prompt.py tools/test_turn_pause_replay.py tools/test_hq_pause.py -q, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-3-tests-8afZR3.log)
Task 3: complete (commits de0e23f0f720abb89be31573cbc465fd9096d1fe..7c617a539a238bd08183716a9a1ec206ae2e6170, command: just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py tools/test_turn_pause_prompt.py tools/test_turn_pause_replay.py tools/test_hq_pause.py -q, status: 0, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-3-tests-8afZR3.log)
Task4 RED28 failed/47 passed/171 deselected in3.54s for absent transitions/end/retention and notification race behavior (task4-red.log). Integrating history at current decision boundaries; no counter/replay algorithm change.
Task4 first full run315 passed/4 failed: missing RootState import on ended resume, fixed with focused4 GREEN. Added two ordered end/resume and cleanup/end-crash checks:323 passed in26.47s. Initial latency pilot had serial47.24/47.20ms and concurrent58.44/66.49ms (16-worker grant), but used an invalid invocation bypassing the real entry shebang -S. Frozen faulty measurer is measure-before-shebang-fix.py; initial pilot files remain diagnostic, not accepted gate evidence. Regression measurement_call RED1 failed due to sitecustomize startup; correcting to direct ENTRY execution. No persistence/threshold/environment change or latency-regression conclusion from this invalid pilot.
Task4 corrected measurement-startup test GREEN1. Corrected pilot-r2 remains above50ms for four concurrent samples (52.76/59.28ms); serial44.48/44.53ms. Profile is diagnostic only: entry26ms with load/parse7ms and fsync5ms. Ruling: run the already-authorized1000-sample measurement after reading every pilot verdict. Why: the pilot exercised all gates/correctness assertions but its4-sample maximum is not a reliable p99 estimate; instructions require running/reading pilot, not a statistical pass from4 points. Cost: several minutes may confirm a real failed gate. No bound/target/environment/persistence change;128 events remain required. Ruling: commit correctness-passing Task4 implementation before latency readiness solely to freeze measured inputs. Why: bind performance evidence to reproducible code. Cost: branch remains incomplete/unmerged if latency fails; Task4 must not close until gate passes.

## Task4 latency gate: stopped for design review

Measured implementation45d430de23fb3c9fff38600a055c966b50b897ee; correctness324 passed in26.49s (task4-final-correctness.log), hygiene/diff pass. Main was ancestor before full run. Current handoff merge base ec03a308fba347efdbe5b7a746b673c08d00d21a; current main ec03a308fba347efdbe5b7a746b673c08d00d21a. Task3 continuation complete7c617a53; Task4 remains incomplete on latency, Task5 unstarted. No plan-task-done4/completion recorded.
Full result latency-full.json (also hq-e60ecb files:latency-full-45d430de.json):1000 serial/4000 concurrent samples per harness,128-event buffers, initial grant16, all counters/bounds/inflight assertions pass. Claude serial/concurrent p99=128.653920/406.507965ms; Codex=166.574452/206.435925ms; every case fails50ms. Approximately9.7min from code freeze to result. No uninstrumented idle-host baseline or contention history; cannot attribute the failed gate to storage alone. Short synthetic IDs do not match native widths; next controlled comparison must fix that method limit.
Ruling: stop Task4 and do not start Task5 after the failed full gate. Why: approved plan34357c02 Task4 Step6 returns latency failures to design review. Cost: remaining CLI/handoff and final branch review wait for a valid performance disposition. Revision: measured code45d430de; verification report46c0c32133e1efb2ae1fb02c58629acf8b546df5:docs/notes/2026-11-04-turn-pause-latency-gate-report.md.
Ruling: keep50ms/128 events/131072 bytes and retain current architecture while requesting controlled diagnostics. Why: data proves this run failed but lacks a baseline/control for changing host load; do not guess a new budget or storage design. Cost: about25min of idle-host baseline/candidate measurement may still require a later design revision. Alternatives: defer history or explicitly revise architecture/retention/latency; none chosen without review. Revision: verification report46c0c321. No deferred minors or independent final review yet.
Next owner/action: user reviews frozen latency report46c0c321 and recommended25min idle-host diagnostic; agent then performs only the approved disposition, keeping full design/activation gates. No push, PR, main merge, live conversion, host pointer change, service or subagent this turn. Both branches remain unmerged: fix/hq-2dd09b in .worktrees/hq-2dd09b (open controller hq-c58737), and independent fix/lore-296a0f (lore-296a0f). Integration requires separate live-global approval and merges from their main checkouts; no worktree removal. Broad suites deliberately skipped, no remote evidence. Required raw profiles/logs/invalid initial pilot and corrected/full evidence remain in this container; no disposal.
Closing resource observation: host-load --section session reports nothing left running. Worktree has only regenerable pytest/Python caches ignored; no removal planned. Foreign lore worktree is clean and fix/lore-296a0f remains unmerged, owned by lore-296a0f; no custody transfer. Local worktree remains locked on fix/hq-2dd09b. All execution inputs/evidence/previous ledger versions remain under the controller container; no independent child scratch/off-tree evidence. No Task4 completion, Task5 implementation, final review, live activation or push. Next: required user review of frozen latency report46c0c321 and its recommended controlled diagnostic; current50ms/128-event contract stands.

## Approved diagnostic: queued for later idle host

User approved frozen report46c0c32133e1efb2ae1fb02c58629acf8b546df5 disposition and explicitly directed adding the idle-host comparison to the quiet queue for later execution. hq-e60ecb is the single queued execution owner:25min, needs idle; prep/pilots5, measurements15–18, analysis2–5min. No run is started in this turn. Controller hq-c58737 and goal hq-e10b76 wait on the queued dependency, with no new diagnostic approval outstanding.
Next queued runner: verify specific canonical inputs/claim/Git state and base freshness, use explicit main/candidate entries and separate format-correct synthetic stores with native-width identifiers, inspect both pilots, perform the approved paired serial/concurrent measurement in the established idle window and report causal limits. Keep50ms/128 events and existing frozen inputs; any architecture/bounds/latency change or live activation remains separately gated. Previous324 correctness tests and failed p99 values remain historical evidence. Task4 remains incomplete on latency; Task5 remains unstarted. No diagnostics, tests, source edits, push, merge, host pointer or service change in this queue-maintenance turn.
Queue resource Ruling: declare an exclusive quiet need in the task vocabulary and on hq-e60ecb. Why: the checkout had no shared-resource declaration, and controlled idle measurements should not overlap another host-heavy step. Cost: the queued runner must acquire the host-local quiet hold when it starts; no hold or benchmark is started while parked. This is task-tracker metadata only, not a latency/schema/architecture change.
Quiet queue verification: tasks quiet --project hq lists hq-e60ecb, park.reason=quiet, needs=idle, minutes25, task.needs=[quiet], no active execution claim. Required latency-report input points to the approved frozen protocol. Resource vocabulary committed773b0e71; tasks check and mandatory hygiene pass. No comparison or runtime test run. host-load --section session reports nothing left running. Controller/goal wait on the queued dependency, not another review. Original hq/lore branches remain unmerged and activation-gated under their open owners; no push, pointer/service change or removal.

## Controlled idle-host baseline/candidate diagnostic (2026-11-04)

Merged advanced `main` (`4971a8c43bec41dbf66fa283615c5773591a57e5`, including `hq-e51fac` advisory automatic compaction) into `fix/hq-2dd09b` at `0a8907a4e556eaf9b48e199bdafe7456d19ec148` before measurement; `685 passed in 29.69s` across all ten turn-pause and `hq pause` test modules, and `just check-hygiene` passed.

Ruling: remove `('claude-code', 'compactions', 3)` from `test_history_pause_transition_is_atomic_and_not_repeated` and assert advisory warning history in `test_claude_third_compaction_warns_once_as_advisory_and_never_pauses`.
Why: `hq-e51fac` (`6e25be8a` on `main`) changed `counters.crossed` to check `PAUSE_COUNTS = ('active', 'calls', 'spawns')` so automatic compactions warn once as an advisory signal and never trigger an enforced pause.
Cost: compaction is no longer an `enforced_pause` transition case; history coverage for compaction remains verified on `warning` (`reason == 'compactions'`) and absence of `enforced_pause`. Revision: `0a8907a4e556eaf9b48e199bdafe7456d19ec148` (`tools/test_turn_pause_hook.py`).

Updated `tools/measure_turn_pause.py` and `tools/test_turn_pause_hook.py` (`fb3337d3d583db592481b5c09466476cced7c6af`; `324 passed in 26.84s`, `just check-hygiene` clean) to use native-width identifiers matching recorded hook fixtures (`36`-char UUID roots, `17`/`36`-char worker IDs, `30`/`41`-char call IDs) and support `--entry` and `--no-seed-events` over isolated temporary stores.

Idle-host verification (`host-load`: `0.62 0.77 1.32` on 32 CPUs at start; `0.39 0.44 0.61` at 1000-sample start; 16-worker `host-budget` grant). Pilots ran first (`latency-pilot-main.json`, `latency-pilot-candidate.json`, `latency-pilot-candidate-unseeded.json`), followed by three sequential 1000-sample runs (`latency-1000-main.json`, `latency-1000-candidate-128events.json`, `latency-1000-candidate-1event.json`; portable derivatives attached to `hq-e60ecb`):
- `main` (`<HQ_CHECKOUT>/tools/turn-pause`, unversioned `RootState`, 720–762 B): passes all four cases (`p50 = 29.47 / 30.50 / 29.51 / 33.20 ms`, `p99 = 46.60 / 47.96 / 46.80 / 49.58 ms`), leaving only `0.42–3.40 ms` p99 headroom below `50 ms`.
- Candidate with 128 events (`fix/hq-2dd09b`, version-1 `RootRecord`, 91,859–92,156 B): fails all four cases (`p50 = 42.90 / 46.43 / 41.75 / 46.23 ms`, `p99 = 59.96 / 69.04 / 59.59 / 64.56 ms`).
- Candidate with 1 event (`fix/hq-2dd09b`, version-1 `RootRecord`, 1,690–1,732 B): fails all four cases (`p50 = 36.73 / 40.73 / 36.72 / 40.49 ms`, `p99 = 53.91 / 59.69 / 54.02 / 64.47 ms`).
- Microbenchmark breakdown (200 iterations): `/usr/bin/python3 -S` noop `14.59 ms`, `import turn_pause.hook` `26.29–27.01 ms`, `main` 750 B file-only `fsync` + `replace` `1.85 ms`, candidate `write_atomic` file+directory `fsync` `3.28 ms` (1.7 KB) / `3.75 ms` (92 KB), `parse_record` `0.23 ms` (1 event) vs `3.90 ms` (128 events: `1.46 ms` `_unique` JSON parse + `0.92 ms` `encode(events)` bound recheck + `1.52 ms` 128-event validation), `record_json` `0.92 ms` (128 events).

Ruling: keep Task 4 incomplete on latency, do not start Task 5, and return the controlled diagnostic and design-revision recommendation (`fb3337d3d583db592481b5c09466476cced7c6af:docs/notes/2026-11-04-turn-pause-latency-gate-report.md`, SHA256 `0866da1c9e413ca1f9da5a08d7b763001d0e618ff7e37016836555877909e2f2`) to the user for a design revision decision.
Why: `docs/notes/2026-11-04-turn-pause-latency-gate-report.md` explicitly requires bringing any schema, bounds, persistence architecture, or latency requirement change back as a separately reviewed design revision with no automatic retry, budget increase, or activation.
Cost: `hq-e60ecb`, `hq-c58737`, and `hq-e10b76` park on `user` (`decision`) until the hot-path persistence design revision is approved.

## Task 4 hot-path optimization and passing latency gate (2026-11-05)

User instructed: "Great! Next, decide on how best to continue hq-e60ecb / hq-c58737".
Prior ledger preserved at `$WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/progress-before-hotpath-opt-b0703b1b819d.md` (`0400`, SHA256 `b0703b1b819d0999b93d69a1f5ca23cb16427cb1eacb1c2aae6a7de50e2065d4`).

Ruling: optimize the non-transition hot path within the existing single-file `RootRecord` v1 contract (`95773e6e` lines 250–252 builder latitude for compact serialization) using C-backed `_json` helpers (`record.py`), `_LazyEvents` raw-event splicing on non-transition calls (`state.py`), deferred `prompt`/`history` imports (`hook.py`/`engine.py`), and transition-scoped directory `fsync` (`write_atomic(..., sync_dir=...)` in `state.py`), rather than changing the `RootRecord` v1 schema, splitting history into a second file, or relaxing the 50 ms / 128-event / 131,072-byte bounds.
Why: preserves the frozen specs (`95773e6e` and `90740430`), `tools/turn-pause-migrate` v1 compatibility, and single-file atomic replacement while cutting subprocess startup imports from `17.14 ms` (72 modules) to `9.70 ms` (46 modules) and avoiding 128-event dict decoding/validation/re-encoding and redundant directory `fsync` on ordinary `PreToolUse`/`PostToolUse` counter ticks.
Cost: `state.py` carries `_LazyEvents` splicing for `lazy_events=True` callers (`Store.locked`, `Store.read`, `Store.latest_for_cwd`, `Store.root_for_agent`) while `parse_record(text)` and `Store.read_record` always materialize and validate all events eagerly; tested by `test_history_lazy_events_roundtrip_and_corrupt_tail_refusal`. Revision: `97b2c670c4effdf54a1d3c4d8c4bd2aec438da4b`.

Verification for Task 4 (`97b2c670c4effdf54a1d3c4d8c4bd2aec438da4b`):
- Pilot (`latency-pilot-hotpath-opt.json`, SHA256 `7f81695f6fa51babfb570cda157f2b5675f6ec5bd48e02b9a104331c188c88cb`): `status: passed` across all 4 cases (`claude-code` serial `27.73 ms`, concurrent `p99 = 35.02 ms`; `codex` serial `21.28 ms`, concurrent `p99 = 36.18 ms`).
- 1000-sample isolated latency gate (`latency-1000-hotpath-opt-128events.json`, SHA256 `5836b76cde9b8e60867bfa5b7039b885b426b38c47a504f061909e21864aeda2`, attached to `hq-e60ecb` at `tasks/files/hq-e60ecb/latency-1000-hotpath-opt-128events.json`, `workers = 16`, `seed_events = true`, 128 events per root, 91,857–92,163 B state files): `status: passed` across all 4 cases:
  - `claude-code` serial (1000 samples): `p50 = 23.99 ms`, `p95 = 29.25 ms`, `p99 = 31.93 ms`, `max = 35.21 ms` (`passed: true`)
  - `claude-code` concurrent (4000 samples): `p50 = 22.63 ms`, `p95 = 35.49 ms`, `p99 = 39.56 ms`, `max = 53.68 ms` (`passed: true`)
  - `codex` serial (1000 samples): `p50 = 23.64 ms`, `p95 = 31.28 ms`, `p99 = 33.82 ms`, `max = 38.50 ms` (`passed: true`)
  - `codex` concurrent (4000 samples): `p50 = 26.51 ms`, `p95 = 39.53 ms`, `p99 = 47.43 ms`, `max = 70.04 ms` (`passed: true`)
- Focused suite: `just test-one tools/test_turn_pause_hook.py tools/test_turn_pause_history.py tools/test_turn_pause_state.py tools/test_turn_pause_prompt.py tools/test_turn_pause_migrate.py tools/test_turn_pause_replay.py tools/test_turn_pause_allowlist.py tools/test_hq_pause.py -q` -> `646 passed in 36.04s`; `just check-hygiene` and `git diff --check` exited 0.
- Task 4 (`hq-e60ecb`) complete at `97b2c670c4effdf54a1d3c4d8c4bd2aec438da4b` (`plan-task-done 4` log: `task-4-tests-b7N41V.log`, `325 passed in 33.25s`).

## Task 5: Expose read-only history/list and the obs handoff (2026-11-05)

Armed Task 5 (`hq-f50d9f`) at base `b85b0af33c18a1b2d8bc861cbe5bb3276cd953bf` (`task-5-brief-c9302a3c6b0024c3c3199ba3560f3eed7750f353d8d88590c84525760449b829.md`).
- Step 1 & 2 RED (`task5-red.log`): `just test-one tools/test_hq_pause.py tools/test_turn_pause_allowlist.py tools/test_turn_pause_history.py -k 'history or summaries or coverage or retention or readonly' -q` -> `8 failed, 52 passed` on missing `hq pause history|list` CLI subcommands and `allowlist` read classification.
- Step 3 & 4 Implementation:
  - Added `hq pause history` and `hq pause list` in `tools/hq_cli/pause.py` (`history(args, env)` and `listing(args, env)`) with strict boundary validation (`--session`, `--harness`, `[since, until)` RFC 3339 with explicit UTC offset, `-n 1..1000` default 50, `--json`), version-1 JSON envelope (`observed_at`, `host`, `coverage` with `available|partial|unavailable` and `per_root_atomic` observation, `window`, `events`/`summaries`, `truncated`, `retention`, `cleanup_debt`, `diagnostics`), and zero writes/mutations (`before == after`).
  - Updated `tools/turn_pause/allowlist.py` (`_records`) to classify `hq pause history` and `hq pause list` as `read` (spending paused read grace) while keeping `hq pause status` and `hq pause limits` as `bookkeeping` and excluding `hq pause` from `protected_read`.
  - Created portable A–G and control handoff fixture bundle `tools/fixtures/turn-pause/history/obs-handoff-cases.json` (SHA256 `2f5e852c72c73348e55de29a4addde85b2af5001bc01689398aa1b9f61d43deb`) with separate `hook_events`, `task_evidence`, `session_evidence`, and `expected` classification vectors, and updated `docs/turn-pause-history.md` (SHA256 `0e249f62596d2938928dc2db05d825f04bd638199a3c4ba189774c3826d02bf9`), `docs/runbooks/turn-pause-activation.md`, and `README.md`.
  - Recorded frozen schema/fixture revision on `obs-1450e7`.
- Step 5 & 6 GREEN (`task5-green.log`) and Commit:
  - `just test-one tools/test_hq_pause.py tools/test_turn_pause_allowlist.py tools/test_turn_pause_counters.py tools/test_turn_pause_history.py tools/test_turn_pause_hook.py tools/test_turn_pause_limits.py tools/test_turn_pause_migrate.py tools/test_turn_pause_prompt.py tools/test_turn_pause_replay.py tools/test_turn_pause_state.py tools/test_turn_pause_wiring.py -q` -> `702 passed in 35.33s`; `just check-hygiene` and `git diff --check` exited 0.
  - Note: Task 5 modified only `tools/hq_cli/pause.py`, `tools/turn_pause/allowlist.py` (lazy-loaded only on paused/protected-path matches), fixtures, tests, and docs; the measured non-paused hook entry hot path from Task 4 (`97b2c670`) is unchanged.
  - Committed at `3a377ba7cf377ba79b0d633c7067be8cf0484454` (`feat: expose durable turn-pause history for local reporting`).
Task 4: attempt (status 0, command: just test-one tools/test_turn_pause_hook.py tools/test_turn_pause_history.py tools/test_turn_pause_state.py tools/test_turn_pause_prompt.py tools/test_turn_pause_migrate.py tools/test_turn_pause_replay.py -q, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-4-tests-b7N41V.log)
Task 4: complete (commits 2efc20c5950a0999e2ec086d943eb21ffd77af40..97b2c670c4effdf54a1d3c4d8c4bd2aec438da4b, command: just test-one tools/test_turn_pause_hook.py tools/test_turn_pause_history.py tools/test_turn_pause_state.py tools/test_turn_pause_prompt.py tools/test_turn_pause_migrate.py tools/test_turn_pause_replay.py -q, status: 0, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-4-tests-b7N41V.log)
Task 5: BASE b85b0af33c18a1b2d8bc861cbe5bb3276cd953bf
Task 5: attempt (status 0, command: just test-one tools/test_hq_pause.py tools/test_turn_pause_allowlist.py tools/test_turn_pause_history.py -q, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-5-tests-WpqB9c.log)
Task 5: complete (commits b85b0af33c18a1b2d8bc861cbe5bb3276cd953bf..3a377ba7cf377ba79b0d633c7067be8cf0484454, command: just test-one tools/test_hq_pause.py tools/test_turn_pause_allowlist.py tools/test_turn_pause_history.py -q, status: 0, log: $WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/task-5-tests-WpqB9c.log)

## Whole-branch review and activation handoff (2026-11-05)

- Merged advanced `main` (`6fc35d4cdbf95b6f019c1996767b6a82d38a3661`) into `fix/hq-2dd09b` at `2b5bad660b412457bf2896ea41fe4cd54e98c1fd` and verified `just check-hygiene` clean.
- Dispatched fresh whole-branch reviewer (`conversation://30f5335d-6801-46b5-87dc-17e9d3c0ed7b`) over `6fc35d4cdbf95b6f019c1996767b6a82d38a3661..2b5bad660b412457bf2896ea41fe4cd54e98c1fd` against frozen specs `95773e6e` (SHA256 `be56c498086b686844e793caf6c9cdbe03282555e61d4552f5bc241b9a005214`) and `90740430` (SHA256 `009789ceebccd691d2022335192ce38b8745d0bac285ed4d22fb964c45449130`), plan `docs/plans/2026-11-04-turn-pause-reliability.md`, latency gate report `docs/notes/2026-11-04-turn-pause-latency-gate-report.md`, and the 5 Review Focus areas.
- Verdict: **Approved** (Critical: 0, Important: 0, Minor: 0; deferred minors: none).
- All 5 execution child tasks (`hq-9fc447`, `hq-ec4762`, `hq-cc91d4`, `hq-e60ecb`, `hq-f50d9f`) are complete and closed.
- Added reconsider note (`--no-reviewed`) on `hq-5aa005` as required by `hq-c58737`.
- Next gate: separate user approval for the live operator activation window (`docs/runbooks/turn-pause-activation.md`: quiesce hook writers, back up live `$XDG_STATE_HOME/hq/pause`, run `tools/turn-pause-migrate --source SOURCE --destination STAGE --to-version 1`, merge `fix/hq-2dd09b` into `main` and swap stage into place, and merge `fix/lore-296a0f` in `<LORE_CHECKOUT>`). Controller `hq-c58737` parks on `user` (`decision`) holding `.worktrees/hq-2dd09b` and `$WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/`.
