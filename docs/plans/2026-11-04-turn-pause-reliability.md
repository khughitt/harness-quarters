# Turn-pause Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native inline execution, or superpowers:subagent-driven-development if the user overrides that recommendation. Execute task-by-task; steps use checkbox syntax.

**Goal:** Permit safe diagnostics, give approved implementations more spawn headroom, and retain bounded, reviewable turn-pause transitions.

**Architecture:** Reuse the strict reader grammar and existing counter engine. Store current state, private scheduled-prompt guards and transition history in one versioned, atomically replaced per-root record under the existing flock. Keep lifecycle production in the hook, read-only history presentation in the CLI, and self-stop correlation in obs.

**Tech Stack:** Python standard library, existing plain Record classes, JSON, flock, atomic file replacement, pytest through `just test-one`; no new dependency or service.

**Spec:** hq `95773e6eb742a3a4884126de9b93538be3676d84:docs/specs/2026-11-04-turn-pause-reliability-design.md`, SHA256 `be56c498086b686844e793caf6c9cdbe03282555e61d4552f5bc241b9a005214`, amended by hq `907404308e3172de57f81a9175ef7da46f0c988d:docs/specs/2026-11-04-turn-pause-ended-prompt-guards-design.md`, SHA256 `009789ceebccd691d2022335192ce38b8745d0bac285ed4d22fb964c45449130`. The user explicitly approved both revisions. Preserve their bytes. Also read `docs/notes/2026-11-04-reliability-design-r2-report.md` for the supplied implementation guardrails.

**State:** revision 2, proposed continuation awaiting human plan review. Original plan `3c29183b042929a43619ab2b780527fad82dd307` was approved for native inline execution. Tasks 1/2 are complete at `f7e5b618`/`29c7142e`; Task 3's original contract is complete at `f2f704f2`. Task 4 stopped before production lifecycle changes; its recorded-wake regression at `90740430` remains deliberately RED. Task 5 is unstarted. This revision adds Task 3's schema continuation, Task 4's ended-prompt recognition and Task 5's privacy assertions. Native inline execution remains the chosen method. Prepared warning/goal fixes and lore-296a0f remain separately gated for activation.

## Global Constraints

- Default hard limits: `active_seconds = 57600`, `calls = 500`, proposed `spawns = 60`, `compactions = 2`; crossing is strictly `>`, and spawn warning is at 45.
- Preserve explicit budget overrides and existing scaling: 12h gives 45 spawns, 48h gives 180. Preserve root calls, tree spawns, root compactions and unknown Codex compactions separately.
- Protected reads never authorize mutation or reset a pause. Paused reads consume the existing 25-read grace; cancellation/bookkeeping remain available.
- History: at most 128 transitions and 131072 UTF-8 bytes of transition payload per root; ended histories expire after 30 days, at most 512 ended roots, at most 32 deletions per maintenance call. Seven-day idle clearing is separate.
- No prompts, tool input/output, command text, credentials, cwd, notification bodies or private config in history. Directory/file modes 0700/0600. Notification receipt remains unknown.
- Private `prompt_guards` metadata contains stripped-text SHA-256 digests and wake windows only, outside history. It shares root/generation retention and never appears in history/list or portable handoff fixtures. Fingerprints permit guesses for short prompts; they are not anonymization.
- Preserve the normal entry import invariant and normal-call p99 under50ms. No silent threshold, latency-budget or persistence-design substitution.
- Valid `automatic_broad=false`: fresh focused RED to GREEN and mandatory `just check-hygiene`; a broad policy skip is not a pass. Never invoke pytest directly.
- No live-store mutation, shared pointer repointing, merge into live main, service, push or PR without the separate activation/publication authorization.

## Execution Setup and Review

Reuse `.worktrees/hq-2dd09b`, branch `fix/hq-2dd09b`; it is hydrated. Run `tasks prime`, verify claims/halts and policy, and refresh retained inputs before execution. Re-enter using-git-worktrees Setup; record a fresh focused baseline using the modules affected by the first task, not a broad suite. Documentation preparation did not create a runtime-test baseline obligation.

Use one coordinated plan because the deliverables share hook/allowlist and state interfaces. Keep the three original task records as owning goals and the existing five execution children. Tasks 1/2 stay complete. After revision-2 approval, reopen hq-cc91d4 with `tasks edit hq-cc91d4 --status todo`, then `tasks start hq-cc91d4` and its trial arm; execute only Task 3's unchecked continuation steps. Then resume/arm hq-e60ecb for Task 4 and hq-f50d9f for Task 5, in that order. This is an amendment before integration, not a new concerns task. No extra execution child or parallel implementation is needed.

Native inline execution is recommended: five deliverables share small internal interfaces and one worktree. Use a fresh whole-branch reviewer after implementation and fresh scoped corrective re-reviews as the repository rules require. Check/merge an advanced base before that review or measurement. Preserve each task's implementation SHA; never rebase away ledger ancestry.

Resume the existing workspace at `$WORK_ROOT/hq/hq-c58737/plans/turn-pause-reliability/`, owned by open hq-c58737; create no replacement workspace. Its immutable `execution-manifest-20261104-r1.json` attachment on hq-c58737 pins the prior ledger/brief/log bytes. Verify the specific recorded inputs needed for resume. Before editing the ledger, preserve its exact checkpointed bytes under a distinct immutable member and note that locator/hash mapping on the owner. Preserve all existing BASE values and old digest-named briefs. Use the registered lore checkout's explicit `bin/plan-task-start` and `bin/plan-task-done` with the canonical plan-path already recorded there and the newly approved plan bytes; the new digest produces a new brief. The earlier Task 3 completion proves only `f2f704f2`'s contract: append its revision-2 continuation as pending and require a new completion at the implementation HEAD instead of skipping it or deleting the old completion. Task 4's existing BASE also stands. Keep the controller open across activation approval. At actual park/done, preserve the full workspace manifest/checkpoint; content edits alone create no checkpoint boundary.

## Review Focus

1. Real Bash metadata must not make a safe protected read fail; execution-changing fields must never qualify. Task 1 tests the recorded fixture shape and unsafe extras.
2. Late notification outcomes must attach to the original paused turn, including after reset/SessionEnd, without poisoning or resurrecting current state. Task 4 tests the race.
3. An unmarked captured wake after end/idle clearing must match retained guards before state initialization; worker/injected text must not consume a guard. A genuine nonmatching prompt creates one next turn, and a new root initializes only once. Tasks 3/4 test digest normalization, window/cron precedence, restart and serialized end/resume races.
4. Repeated seven-day maintenance must not refresh ended histories and prevent 30-day expiry; cleanup racing a resumed root must not delete active state. Tasks 3/4 test mtime and locked rechecks.
5. CLI filters/truncation/missing stores must expose coverage limits; ordinary decision parks must not become range stops. Task 5 tests handoff fixtures and read-only presentation.

## File Map and Shared Contracts

Modify existing `allowlist.py`/`hook.py` for protected readers, `limits.toml` and dependent fixtures/docs for the cap, and `state.py` for atomic envelopes. Extend existing `prompt.py` with private scheduled-prompt helpers; use its existing test module. `tools/turn_pause/history.py` already supplies cheap event/snapshot primitives; `tools/turn_pause/migrate.py` and the thin `tools/turn-pause-migrate` entry already supply offline conversion. Add `tools/measure_turn_pause.py` for the required isolated latency proof. The migration/measurement programs are not installed into home or invoked by hooks.

Extend `tools/hq_cli/pause.py` for history/list, portable fixtures under `tools/fixtures/turn-pause/history/`, and current references `docs/turn-pause-history.md` and `docs/runbooks/turn-pause-activation.md`. Update README and the relevant existing tests in the task that changes their behavior. Do not alter the frozen design/audit/calibration reports.

The main persistence type is `state.RootRecord(Record)` with fields:

```text
version=1, harness:str, root:str, generation:str (random 128-bit hex),
created_at:float (UTC epoch seconds), turn_serial:int, event_serial:int,
state:RootState|None, ended_at:float|None,
events:list[dict], dropped_count:int, dropped_through:float|None,
prompt_guards:dict = {"cron":[], "wakeups":[]}
```

Counters, serials and stored limits are nonnegative, configured limits positive, floats finite, and bool is not int. Zero stored limits retain the existing engine contract and its hook regression tests; Task 3's recorded execution ruling explains that distinction. Validate exact record/event field sets and identity consistency; reject duplicate JSON keys, non-JSON constants, unsupported versions and malformed state. `created_at` bounds historical coverage, especially after migration; it is not a claim of complete earlier history. Transition sizes refer to compact UTF-8 serialization of the `events` array, including its delimiters.

`prompt_guards` has exactly `cron` and `wakeups`. Cron digests are unique and sorted; wake rows `[digest, not_before, not_after]` are unique and lexicographically sorted. Every digest is exactly 64 lowercase hexadecimal characters, and every window has finite nonnegative UTC seconds with `not_before <= not_after`, excluding booleans. Guards have one digest per distinct pending cron text and one row per distinct pending wake. They may only shrink during late ended-root events; they do not use the evictable event buffer as a registry. The unreleased record remains version 1 with the required new field: old prototype-v1 shapes are refused, not silently accepted. Legacy conversion initializes empty guards and preserves active dictionaries exactly. If a real prior v1 activation is discovered, stop before conversion/activation for a migration decision.

Recognition is limited to retained known schedules. Follow the approved addendum's explicit clearing of guards on a nonmatching genuine resume: prior schedules are then unknown until active-state native evidence records them again. An unmarked wake from an unobserved prior schedule can consequently look genuine; neither this plan nor its coverage output promises permanent wake provenance. Root expiry/eviction also removes guards. Do not silently retain guards across genuine resume or alter active-state/replay matching to broaden this contract.

The prepared `Store.locked(harness, root, *, create=True)` yields RootRecord; its callers/tests have already replaced the old RootState-yielding contract. A fresh record has an empty buffer, serials 0 and a fresh RootState with no turn. With create=False, a missing record yields None and is not written; end/cleanup/late notification use this mode to avoid resurrecting deleted roots. Keep every caller on that one contract, without a compatibility wrapper. `Store.read(harness, root)` remains an active-state query returning `RootState|None`; `Store.read_record(harness, root)` returns the envelope for history. These queries have different meanings, not alternative storage formats.

Event v1 fields are `version`, `harness`, `root`, `generation`, `turn`, `sequence`, `host`, `at` (UTC epoch seconds), `kind`, `reason`, `snapshot`, `notification`, `source="hook"`. Identity is the spec's `(harness,root,generation,turn,sequence)`; sequence increases across the generation. Snapshot contains existing status-style `active/calls/spawns/compactions` used/limit pairs, `limits_sha`, `paused`, `counted` booleans and scopes (`tree_active_seconds`, `root_attempts`, `tree_started`, `root`). It excludes `budget_note` and all other free text.

Kinds: `turn_start`, `warning`, `enforced_pause`, `notification`, `turn_reset`, `turn_resume`, `session_end`. Pause reasons: `active`, `calls`, `spawns`, `compactions`, `limits-changed`. Start reasons: `genuine_user` or `implicit`; reset/resume reason is `genuine_user`; end reason is `session_end` or `idle`. Keep unknown snapshots null rather than manufacture zero counts.

Notification data is null for unrelated events; otherwise it has `outcome` (pending/attempted/error/unknown), `error_code` (null or notify_failed), `desktop="unknown"`, `relay="unknown"`, `receipt="unknown"`, and `pause_sequence` linking to the prepared pause in the same root/generation/turn. Pending is stored with the pause before attempting delivery; completion attaches to that captured identity.

### Task 1: Allow strictly validated protected-path reads

**Owner:** execution child of hq-c58737. **Dependencies:** none.

**Files:** modify `tools/turn_pause/allowlist.py`, `tools/turn_pause/hook.py`, `tools/test_turn_pause_allowlist.py`, `tools/test_turn_pause_hook.py`, README; create `docs/turn-pause-history.md` with the diagnostics section (Task 5 adds its history contract).

**Interfaces:** consume existing `Verdict`, `shell(cmd, owned)`, `_scan` and reader option rules. Produce `allowlist.protected_read(harness: str, tool: str, tool_input: dict) -> bool`. Return true only for positively identified safe readers, never a generic `klass == "read"` result.

- [x] **Step 1: Extend tests before code.** Use existing Driver/fixtures; pin the following behavior:

```python
# test_protected_bash_read_accepts_real_metadata
out, _ = d.pre('Bash', {'command': 'cat ' + shlex.quote(str(d.limits)),
                       'description': 'inspect limits', 'timeout': 1000})
assert not denied(out)
assert d.state().paused is None

# test_readlink_requires_f_and_literal_operands
assert protected_read('codex', 'Bash', {'command': 'readlink -f /srv/bin/tool'})
assert not protected_read('codex', 'Bash', {'command': 'readlink -f -n /srv/bin/tool'})
assert not protected_read('codex', 'Bash', {'command': 'readlink -f ~/bin/*'})
```

  Parameterize both harnesses for Bash and before/after pause. Add native Claude Read/Grep/Glob positives, quoted paths with spaces, the actual fixture metadata,25 accepted paused reads then refusal, unchanged pause/counters/grace semantics, and negative cases for writes, tasks attach/note, cancellation, unknown programs, sed execution, tail-follow, wrappers, substitutions, redirects and compositions. Test wrong description/timeout types (including bool), unknown fields, and every rejected execution field named in the supplied review.
- [x] **Step 2: Run RED.** `just test-one tools/test_turn_pause_allowlist.py tools/test_turn_pause_hook.py -k 'protected or readlink or metadata or grace or hot_path' -q`. Expect new exemption cases to fail on current rejection; record the actual count and reason.
- [x] **Step 3: Implement the narrow exemption.** Preserve `touches_protected` as the cheap pre-check. Only on a hit, lazily import the validator and require a safe read; otherwise keep rejection. Native Claude reader identities require a dict and their string operand (`file_path` for Read, `pattern` for Grep/Glob); do not accept arbitrary custom tool names. Bash accepts only `command:str`, optional `description:str`, optional `timeout:int` excluding bool. Reject every other key. Reuse scanner/argv parsing; accept only the existing filesystem reader identities and the new exact `readlink -f PATH...` form with at least one non-option literal operand. Do not weaken ordinary paused command validation. A qualifying paused call still passes through `_paused` and spends grace.
- [x] **Step 4: Update recovery guidance.** PROTECTED_TEXT must distinguish safe reads from prohibited mutation and tell callers to use concrete expanded absolute or checkout-relative paths, without tilde/globs/composition. Document enumeration of launcher directories, user systemd units and known declared config includes before literal readlink resolution. An unreadable/uninspected entry makes the audit incomplete. No real host audit or pointer repointing is needed for this test.
- [x] **Step 5: Run GREEN.** `just test-one tools/test_turn_pause_allowlist.py tools/test_turn_pause_hook.py -q`; require nonzero executed tests and exit 0, including the importtime assertion.
- [x] **Step 6: Verify mandatory hygiene.** `just check-hygiene` and `git diff --check` must exit 0.
- [x] **Step 7: Commit and record delivery.** Commit by explicit paths: `fix: permit validated read-only pause diagnostics`. Before this owning task's eventual integration, update hq-5aa005 with `tasks note hq-5aa005 --no-reviewed` and the verified finding.

### Task 2: Raise the measured hard spawn cap to 60

**Owner:** execution child of hq-704fe5. **Dependencies:** Task 1 by execution order only.

**Files:** modify `tools/turn_pause/limits.toml`, `tools/test_turn_pause_limits.py`, `tools/test_turn_pause_hook.py`, `tools/test_hq_pause.py`, affected replay tests, README and the current history reference. Search all default-bound callers/fixtures first; leave explicitly isolated 30-agent test limits and frozen historical evidence intact.

**Interfaces:** unchanged `Limits`, `load` and `with_budget`; new default `Limits(57600,500,60,2)`.

- [x] **Step 1: Write RED assertions with default limits.** Pin warning at 45, equality at60, and first subsequent hooked decision after spawn 61 refuses. Exercise Claude's allowed Agent spawn counting and Codex SubagentStart counting, including worker fanout. Preserve duplicate-start suppression and refusal-does-not-spawn behavior.

```python
assert load()[0] == Limits(57600, 500, 60, 2)
assert with_budget(load()[0], Budget(43200, None, None, None)).spawns == 45
assert with_budget(load()[0], Budget(172800, None, None, None)).spawns == 180
assert with_budget(load()[0], Budget(43200, None, 17, None)).spawns == 17
```

  Use an assertion on actual denied/allowed hook calls for both harness boundaries; constants alone do not establish the behavior. Update text/JSON expectations only where defaults change.
- [x] **Step 2: Run RED.** `just test-one tools/test_turn_pause_limits.py tools/test_turn_pause_hook.py tools/test_hq_pause.py tools/test_turn_pause_replay.py -k 'spawn or default or budget or limits or 501st or long_turn' -q`. Confirm failures result from the old default rather than fixture mistakes.
- [x] **Step 3: Change only the default and dependent current expectations/docs.** Set spawns 60, identify the approved design in the limit-file comment, document warning 45 and scaling. Retain strict `>` and limits-changed behavior. No counter/parser/review-workflow algorithm changes.
- [x] **Step 4: Verify focused behavior and frozen evidence.** Run the four focused modules without the selector, then hygiene. Compare the already-retained candidate 60 snapshots and original control refusal; do not rescan live stores or start another sampling pass. If the replay engine itself changes unexpectedly, stop and assess rather than assume the frozen results prove the new engine.
- [x] **Step 5: Commit.** `fix: give approved turn workflows more spawn headroom`.

### Task 3: Persist bounded atomic root records and explicit offline migration

**Owner:** execution child of hq-e10b76. **Dependencies:** Task 2.

**Files:** original delivery modified `state.py`, `Store.locked` callers and their tests, and created `history.py`, `migrate.py`, `tools/turn-pause-migrate`, history/migration tests, portable migration fixtures and `docs/runbooks/turn-pause-activation.md`. The revision-2 continuation modifies `tools/turn_pause/state.py`, `tools/turn_pause/prompt.py`, `tools/turn_pause/migrate.py` only as required by the new factory, `tools/test_turn_pause_state.py`, `tools/test_turn_pause_history.py`, `tools/test_turn_pause_migrate.py`, `tools/test_turn_pause_prompt.py`, and the activation/history reference docs. It does not integrate hook lifecycle behavior before Task 4.

**Progress:** Steps 1–7 are historical completion at `f2f704f2`; do not rerun their implementation sequence. After revision-2 approval reopen hq-cc91d4, preserve its original BASE, and execute unchecked Steps 8–12 for the changed contract.

**Interfaces produced:**

```python
# state.py; existing flock/atomic replace machinery remains the writer
Store.locked(harness: str, root: str, *, create: bool = True) -> context manager[RootRecord | None]
Store.read_record(harness: str, root: str) -> RootRecord | None
Store.read(harness: str, root: str) -> RootState | None
state_dict(state: RootState) -> dict
state_from_dict(data: dict) -> RootState

# history.py; cheap imports only, no state.py import cycle
snapshot(state: RootState | None, *, compactions_counted: bool) -> dict | None
append_event(record: RootRecord, kind: str, now: float, *, reason: str | None,
             snapshot: dict | None, notification: dict | None = None,
             turn: int | None = None) -> dict

# migrate.py; source read-only, destination must not exist
convert(source: str, destination: str, *, to_version: int, now: float) -> dict

# prompt.py; new helpers, hashlib imported inside the digest operation only
empty_guards() -> dict  # fresh {"cron":[], "wakeups":[]}, including fresh lists
capture_guards(state: RootState) -> dict
guarded_prompt_kind(guards: dict, text: str, now: float) -> str  # 'wake' or 'turn'
```

`capture_guards` normalizes exactly as `engine.prompt_kind`: strip text, UTF-8 encode, SHA-256 hex digest; no case folding or Unicode normalization. It returns sorted unique cron digests and wake rows without mutating state. `guarded_prompt_kind` is called only for ended-root text already eligible by agent/genuine checks. It removes expired wake rows (`not_after < now`), consumes the first sorted matching row whose window includes now, otherwise matches cron digests, otherwise returns `turn`. A wake match takes precedence over a cron match, matching the current engine; cron matches are retained. It adds no rows. State parsing validates guards using the existing cheap validation style, without hashing. RootRecord's factory and offline legacy conversion initialize empty guards.

- [x] **Step 1: Add persistence tests with literal bounds/identities.** Adapt existing fixture access from yielded state to `record.state`; preserve the existing state/CLI/hook behavior during this contract change. Extend parallel-update and atomic-replace tests to the whole envelope.

```python
# test_event_bound_and_restart_identity; use synthetic snapshots, no real stores
assert len(reloaded.events) == 128
assert reloaded.dropped_count == 1
assert reloaded.generation == original_generation
assert reloaded.event_serial == 129
assert len(json.dumps(reloaded.events, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')) <= 131072

# test_failed_replace_preserves_state_and_events
assert record_bytes_after_failed_replace == record_bytes_before_attempt
```

  Add byte-bound eviction with non-ASCII payload, unique event IDs under eight concurrent writers, corrupt/duplicate-key/non-finite/bool/version rejection, mode checks and no temporary residue. Reject an oversized individual event rather than returning one that was immediately dropped. Assert snapshots exclude private sentinels placed in cwd, wakeups, budget_note, notify_error and tool bookkeeping. Active `read`, latest-for-cwd and worker lookup ignore ended records.
- [x] **Step 2: Run RED.** `just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py -q`; new record APIs/bounds/conversion must fail before implementation.
- [x] **Step 3: Implement RootRecord and the one-format runtime.** Add strict serialization of the shared contract using existing validation style, plain Record and cheap imports. Persist generation/serials; append events with bounded host/id fields and compact serialization, evicting oldest complete events while updating dropped_count/dropped_through. Keep an exception inside `locked` from committing anything. Fsync the replacement and containing directory for crash durability; preserve the inode recheck on flock. Runtime rejects old unversioned JSON with a migration-needed error. `RootState` still represents only current counters/ownership; the replay engine still consumes it directly. Update all callers without an old-contract wrapper. Temporarily retain existing lifecycle behavior through record.state; Task 4 replaces physical SessionEnd deletion with retained end semantics before activation.
- [x] **Step 4: Implement and test explicit offline conversion.** CLI: `tools/turn-pause-migrate --source DIR --destination DIR --to-version 1|0`. Version 1 converts old active JSON into a new record with exact active fields, generation/turn identity and created_at at conversion; events remain empty and earlier coverage is unknown. Version 0 exports only current active states from v1 records, retaining every source envelope untouched; ended roots are listed as skipped in the receipt. Reject mixed/unexpected formats, unsafe names, symlinks/nonregular inputs, overlapping paths and existing destinations. Never write the source or activate the destination. Failed partial staging remains identified and must not overwrite a retry. `convert` returns a receipt for success or handled failure; CLI emits that JSON on stdout and exits 0 only when complete, otherwise 1. The operator captures it outside both directories; never put receipt.json among state files. Receipt lists versions, relative file names, input/output SHA256, skipped ended roots, completion status and bounded errors. Tests compare complete source active dictionaries, not just counters; test refusal before overwrite, partial conversion and rollback-export after a new v1 turn so old backups cannot silently lose current state.
- [x] **Step 5: Write the activation/rollback runbook.** Require a separately approved window with every old hook writer quiesced. Preserve/hash the exact source store in task-owned persistent storage, run conversion into a fresh sibling staging directory, inspect the receipt, then perform the reviewed code/store cutover while writers remain stopped. Keep launchers on main. Resume only after checking active counters and a new genuine prompt on the new code. A rollback after any new writes must snapshot current v1 bytes and export their active state; never restore a stale pre-cutover backup over new counters/history. Preserve receipts/backups under an open owner. These are prepared operator steps, not authorized actions during execution of this plan.
- [x] **Step 6: Run GREEN and hygiene.** `just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py tools/test_turn_pause_hook.py tools/test_turn_pause_replay.py tools/test_hq_pause.py -q`; then mandatory hygiene. Confirm no runtime import of migration/argparse/pathlib/hashlib has leaked into the entry.
- [x] **Step 7: Commit.** `feat: persist versioned turn-pause state with bounded history`.

**Revision-2 continuation:**

- [ ] **Step 8: Add schema/helper/converter RED tests.** Add `test_prompt_guards_start_empty_and_reject_prototype_shape`, `test_prompt_guards_reject_invalid_shapes`, `test_capture_guards_normalizes_without_mutating_state`, `test_guarded_prompt_kind_windows_and_precedence`, and `test_prompt_guards_conversion_preserves_active_state` in the existing state/history/prompt/migration modules. Use literal expected fields and synthetic strings; no live stores.

```python
assert record.prompt_guards == {'cron': [], 'wakeups': []}
assert empty_guards()['cron'] is not empty_guards()['cron']
# After deleting prompt_guards from a saved envelope, read_record must raise StateError.
assert set(guards) == {'cron', 'wakeups'}
assert guards['cron'] == [sha256(b'x').hexdigest()]  # source texts ' x ' and 'x'
assert guarded_prompt_kind(guards, ' x ', 100) == 'wake'  # inclusive start
assert guards['wakeups'] == []  # consume the one matching one-shot row
assert guarded_prompt_kind(guards, 'x', 101) == 'wake'  # cron still matches
assert guards['cron'] == [sha256(b'x').hexdigest()]
assert converted['state'] == legacy_active_dictionary
assert converted['prompt_guards'] == {'cron': [], 'wakeups': []}
```

  Parameterize malformed outer/inner keys, missing/extra keys, wrong list/row types, wrong digest length/alphabet/case, duplicate or unsorted digests/rows, booleans, negative/nonfinite times and reversed windows. Test inclusive end, before-window, expired-window, whitespace/Unicode matching and wake-before-cron precedence independently. Assert capture leaves the complete source state unchanged and serializes no raw prompt text into guards. Assert snapshot/event field sets still omit all guards; validation errors name fields/categories without echoing private guard values. Conversion/rollback compare full active dictionaries and unchanged source bytes; rollback skips ended roots and rejects a prototype-v1 source missing guards rather than inventing them. Keep the original atomic/mode/concurrency/bounds tests.
- [ ] **Step 9: Run schema/helper RED.** `just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py tools/test_turn_pause_prompt.py -k 'prompt_guards or capture_guards or guarded_prompt or prototype' -q`. Expected: nonzero executed failures for the absent field/helpers, not collection or environment errors; record actual counts. The separate existing late-wake hook regression belongs to Task 4 and is still expected RED here.
- [ ] **Step 10: Extend the unreleased schema and helpers.** Implement the shared-contract field/factory and strict parsing in `state.py`, plus the three prompt helpers above; use only standard-library hashing, lazily. Keep runtime format singular and conversion explicit. Update the runbook with the required guard shape, empty legacy conversion and the stop if a real prototype-v1 cutover is discovered. Document fingerprint guessability, private permissions, recognition windows and post-retention coverage limits in the reference. Do not initialize active state or emit events from a helper. Keep all other counters, history serialization and migration guarantees intact.
- [ ] **Step 11: Run contract GREEN and hygiene.** `just test-one tools/test_turn_pause_state.py tools/test_turn_pause_history.py tools/test_turn_pause_migrate.py tools/test_turn_pause_prompt.py tools/test_turn_pause_replay.py tools/test_hq_pause.py -q`, then `just test-one tools/test_turn_pause_hook.py -k 'hot_path or zero_limit' -q`, mandatory `just check-hygiene` and `git diff --check`. Expected: both focused runs execute nonzero tests and exit 0; hygiene exits 0. Explicitly record that the known late-wake hook regression remains pending Task 4 and is outside this contract-focused gate; do not claim the complete hook module or branch is green. Use the first focused command for Task 3's new `plan-task-done` attempt after committing.
- [ ] **Step 12: Commit the schema continuation.** `feat: retain private scheduled-prompt guards in root records`; close the reopened hq-cc91d4 with its new focused evidence and Task 4's remaining regression disposition. Shared workspace remains owned by open hq-c58737.

### Task 4: Record lifecycle transitions and retain ended history safely

**Owner:** execution child of hq-e10b76. **Dependencies:** Task 3.

**Files:** modify `hook.py`, `history.py`, `state.py`, their state/history/hook tests, and the activation/current reference docs. Consume Task 3's existing prompt helpers; do not create a second matcher or change replay prompt semantics. Add `tools/measure_turn_pause.py` for isolated gate evidence; do not install it or turn it into a service.

**Interfaces consumed:** `RootRecord.prompt_guards`, `prompt.capture_guards(state) -> dict` and `prompt.guarded_prompt_kind(guards, text, now) -> str` from Task 3. RootState remains current active state only; an ended record has `state is None` with private matching metadata on the envelope.

**Interfaces produced:**

```python
# history.py; uses append_event/snapshot from Task 3
start_turn(record: RootRecord, now: float, *, origin: str,
           before: dict | None, after: dict) -> None

# state.py
Store.end(harness: str, root: str, now: float, *,
          compactions_counted: bool, reason: str = 'session_end') -> bool
Store.prune(now: float, *, compactions_counted: dict[str, bool]) -> dict
Store.retention(now: float) -> dict  # read-only eligibility/debt calculation
```

`start_turn` records the old turn_reset/turn_resume closing snapshot before incrementing turn_serial and recording the new turn_start. Reset/resume exists only for a genuine root user prompt; implicit first initialization has a turn_start only. Use the old paused/ended condition to distinguish resume; prior closing data unavailable due retention stays null with diagnostics.

- [ ] **Step 1: Write lifecycle/race RED tests.** Reuse the real Driver and Store. Cover both harnesses, initial prompt, first tool without a prompt, later reset, worker/scheduled injection, warnings for each counted metric, calls/spawns/compactions/active/limits-changed pauses, repeated denials, SessionEnd, notification error and unknown delivery.

```python
# test_initial_genuine_prompt_has_one_turn_start
assert [e['kind'] for e in record.events] == ['turn_start']
assert record.turn_serial == 1
# test_pause_and_state_commit_together; repeated denials add no duplicate pause
assert sum(e['kind'] == 'enforced_pause' for e in record.events) == 1
# test_notification_after_reset_names_original_turn
assert notification_event['turn'] == paused_turn
assert active_record.state.notify_error is None
```

  Add the reset-after-SessionEnd counterpart: a late notification may append to its old turn but never resurrect state. An ended root's late worker/scheduled events must not create a new user turn; late PreToolUse is refused until a genuine root prompt resumes it. A previously unseen record can start implicitly; initial genuine prompt handling must avoid the current lazy-start-then-prompt-start double initialization. Existing legacy turns acquire no fabricated prior events during migration.

  Keep `test_history_late_scheduled_wake_cannot_resume_after_session_end` from `90740430` and add `test_ended_prompt_guards_survive_restart_and_idle_clear`, `test_worker_and_injected_prompts_do_not_consume_ended_guards`, `test_matching_human_text_requires_rephrase`, and `test_end_resume_guards_commit_in_serial_order`. Seed both harnesses with portable cron/wake state; use the recorded unmarked Claude wake for the integration regression. After end or idle clear assert `state is None`, the captured digest/window set persists, the scheduled match returns WAKE_TEXT, `turn_serial` does not advance, and no turn_start/resume is fabricated. Reopen Store before matching to establish restart behavior. Match at both window boundaries, consume a one-shot row exactly once, retain cron matches, and allow a nonmatching eligible genuine prompt to clear guards/ended_at and emit exactly one next turn_start plus its prior-turn resume. An expired one-shot alone no longer matches, preserving the existing active-state recognition window. Worker/injected text must not consume even a matching one-shot row. Late Stop/SubagentStart/PostToolUse payloads cannot add guards. Exercise both root-lock serial orders for end/resume and assert the state/guards/events agree with that order; do not claim a later SessionEnd must preserve a prior resume. Repeated end/prune must not refresh a completed end. Confirm guards disappear with root expiry/capacity eviction and that a later new generation has unknown prior coverage. Add a no-turn imported-state case: end clears it without inventing a positive turn/event identity.
- [ ] **Step 2: Run RED.** `just test-one tools/test_turn_pause_hook.py tools/test_turn_pause_history.py tools/test_turn_pause_state.py -k 'history or transition or session_end or prune or notification or initial or implicit or ended_guards' -q`; require the missing transition/retention/ended-recognition behavior to fail, including the already-recorded late-wake regression.
- [ ] **Step 3: Integrate transitions at existing decision boundaries.** Record first warning additions and first pause in the same locked update as counters; committed refusal means prepared enforcement, not proven harness denial. Capture the pause's generation, turn, snapshot and event identity before releasing the lock for `notify.send`. Record aggregate outcome afterward as attempted/error, use bounded category notify_failed, and leave channel delivery/receipt unknown under the existing notifier's aggregate interface. Reopen with create=False: if the record is gone or its generation changed, emit a bounded unknown-outcome diagnostic without creating a record or attaching old history to a new generation. Apply active notify_error only if generation/turn still match. Never record raw notifier exception text in history. Root genuine reset records the closing snapshot and new start atomically. State-write failures retain existing denial/error behavior; no separate journal write or new notification retry loop.

  In `_decide`, distinguish an ended existing record before the lazy-start path. Reject its late PreToolUse; ignore other late non-prompt lifecycle payloads. For UserPromptSubmit validate text and check worker/genuine eligibility first, then call the guard matcher while still holding the root lock. A match returns the existing WAKE_TEXT context and leaves state null; it can only consume/expire wake rows. A nonmatching eligible prompt creates RootState, clears guards and ended_at, and starts the next turn atomically using the old closing snapshot when retained. Do not let lazy initialization precede this check. An existing active root keeps `engine.prompt_kind` and its pending raw active-state records unchanged.
- [ ] **Step 4: Implement retained end and bounded maintenance.** Replace hook `Store.remove` use with `end`, retaining generation/serial/history, capturing `prompt_guards` from active state, then setting state null and ended_at once in the same atomic update as its closing snapshot/session_end event. Missing/already-ended roots do not generate fake ends or rewrite the file. An imported/uninitialized active record with no turn and turn_serial0 clears without a fabricated event; its retained metadata cannot prove an observed turn. Seven-day idle clearing uses the same capture/end operation only for non-null state; preserve ended_at, guards and mtime on later maintenance. Use catalog lock then each candidate's root lock, never acquire the catalog lock while a root lock is held. Recheck active/ended and idle predicates under that lock. Ended deletion selects expiry or oldest-ended capacity excess (keep newest 512); no active state is evicted. Limit each maintenance pass to32 affected records, with deletions also at most 32, and report unique remaining eligible-record debt. A root resumed while cleanup waits must survive. Keep deletion/lock inode handling safe for waiters, preserving the existing concurrency tests. SessionEnd releases its own root lock before maintenance. CLI `retention(now)` computes debt without writing; guard matching, expiry or a late notification never moves ended_at.
- [ ] **Step 5: Add maintenance and crash assertions, then run GREEN.** Assert ending leaves history readable but active read returns None;8-day active state clears once; day 29 ended history remains with unchanged mtime; after day 30 it is eligible using ended_at, not a late notification's file mtime; capacity 513 removes only the oldest eligible ended record; excess beyond 32 leaves explicit debt and completes in later calls; resumed/locked active records survive. Inject exceptions before replacement and after durable replacement but before output/notification; only committed history survives, with delivery unknown. Assert failed end/capture replacement preserves the old active state and no separately committed guard metadata appears. An error after replacement during directory fsync can leave present bytes with uncertain crash durability: assert fail-closed behavior, not that old bytes necessarily remain. Run `just test-one tools/test_turn_pause_hook.py tools/test_turn_pause_history.py tools/test_turn_pause_state.py tools/test_turn_pause_prompt.py tools/test_turn_pause_migrate.py tools/test_turn_pause_replay.py -q`, then `just check-hygiene` and `git diff --check`. Expected: all named tests, including the original late-wake regression, pass with nonzero counts; hygiene exits0.
- [ ] **Step 6: Run the latency gate before claiming readiness.** Implement a small standard-library measurer using recorded fixture payloads, the real entry script and temporary synthetic stores. It builds every subprocess environment key-by-key, seeds the revised guard-bearing record with a full 128-event buffer, temporarily sets generous test-only limits, uses notification stubs and validates counters/record bounds after the run. Arguments: `--pilot`, `--samples N`, `--output FILE`; output identifies harness, serial/concurrent case, sample count, p50/p99, counts and exit verdict. Concurrent case is two roots with one root/one worker client each; use the positive OPS_WORKERS host-budget grant and refuse rather than claim concurrency coverage if fewer than 4 are granted. Time PreToolUse wall duration; close each synthetic call with PostToolUse. Pilot executes every case end-to-end once and checks its verdict; read it before the 1000-sample run. Run through `host-budget run -- python3 tools/measure_turn_pause.py ...`, with output in the recorded execution workspace, for both harnesses. Require p99<50 ms for each named case and unchanged import invariant; retain the script/result as evidence. A load refusal parks quiet with an estimated duration, rather than weakening the gate. A latency regression returns to design review; do not silently increase the target or swap persistence.
- [ ] **Step 7: Commit verified lifecycle and measurement work.** `feat: retain turn-pause lifecycle transitions across resets and exits`.

### Task 5: Expose read-only history/list and the obs handoff

**Owner:** execution child of hq-e10b76. **Dependencies:** Task 4.

**Files:** modify `tools/hq_cli/pause.py`, `allowlist.py`, `tools/test_hq_pause.py`, allowlist/history tests, README; complete `docs/turn-pause-history.md` and `docs/runbooks/turn-pause-activation.md`; create portable A–G/control fixtures in `tools/fixtures/turn-pause/history/`.

**Interfaces:** retain existing status/limits JSON exactly. Add:

```text
hq pause history [--session ROOT] [--harness claude-code|codex]
                 [--since RFC 3339] [--until RFC 3339] [-n N] [--json]
hq pause list    [same filters]
```

No session selector means all locally available root records, without CODEX_THREAD_ID/cwd fallback. The selector names a root; existing status can resolve a live worker to its root. Window is `[since, until)`, timestamps must include an offset, default limit 50 and range 1..1000. Stable newest-first order is at then harness/root/generation/turn/sequence for events; list emits one root/generation/turn summary ordered by last retained event. Summaries use last snapshot and observed event kinds, with started/ended times nullable after truncation; they never infer self-stop or successful continuation from missing events.

JSON v1 envelope fields: `version`, `observed_at` (UTC epoch seconds), `host`, `coverage`, `window`, `events` OR `summaries`, `truncated`, `retention`, `cleanup_debt`, `diagnostics`. Coverage identifies the local store, available/unavailable/partial, its creation/retained bounds and per-root atomic (not transactional whole-catalog) observation. Retention exposes30days/512 ended/128 events/131072 bytes and dropped metadata. Do not publish private store paths or cwd in portable fixtures. A missing store yields empty rows with unavailable coverage; corrupt/unsupported records fail with exit 1. A disappearing catalog entry is an explicit partial-coverage diagnostic, not a silently complete empty result.

- [ ] **Step 1: Write CLI RED tests with real subprocesses and isolated stores.** Reuse seed/hq helpers, adapting seed to RootRecord. Snapshot store paths/bytes/mtimes before and after every read-only command.

```python
assert data['version'] == 1
assert data['coverage']['status'] == 'unavailable'  # missing store, not no events
assert before == after  # history/list never create a directory or rewrite state
assert parsed['compactions']['used'] is None       # Codex event snapshot
```

  Pin root/harness/date filters, default/global selection despite ambient thread/cwd, exact since-inclusive/until-exclusive timestamps, deterministic ordering, limits 0/1001, invalid/naive dates, missing state with retained history, reset/resume identity, truncation and cleanup debt. Assert status JSON remains unchanged. Add paused allowlist cases where history/list spend grace but status/limits remain bookkeeping; reader commands cannot invoke document providers or mutate through extra subcommands.

  Add `test_history_and_list_do_not_publish_prompt_guards`: seed an ended record with a known raw sentinel in its prior active schedule and a distinctive guard digest. Assert neither sentinel, digest nor the key `prompt_guards` appears in history/list text or JSON, including summaries/retention/diagnostics; snapshots retain only the documented public fields. Keep the raw record private. Assert the portable A–G/control fixtures contain neither raw schedule text nor guard metadata. Roots with no observed turn must not acquire fabricated turn summaries; report their missing prior-turn evidence as a coverage diagnostic.
- [ ] **Step 2: Run RED.** `just test-one tools/test_hq_pause.py tools/test_turn_pause_allowlist.py tools/test_turn_pause_history.py -k 'history or summaries or coverage or retention or readonly' -q`.
- [ ] **Step 3: Implement CLI and close the allowlist boundary.** Add `history(args, env) -> str` and `listing(args, env) -> str` using Store.read_record/retention and strict boundary validation. Leave correlation/transcript reading outside these commands. Adjust `_records` to classify the two new exact pause subcommands as read, not bookkeeping; preserve status/limits. Print concise text that names count scopes, reason and coverage; preserve the versioned JSON contract for obs.
- [ ] **Step 4: Create shared portable evidence fixtures and document consumer rules.** Include A/B enforced pauses, C/D/E/G warning/interpretation self-stops, F proactive spawn stop, one warning with observed continuation, ordinary approval/review gates, genuine user resume and missing/conflicting evidence. Hook events and external `task_evidence`/`session_evidence` are separate arrays. External rows carry qualified session, enclosing human-turn identity/time bounds, task id, timestamp, evidence type and source locator, plus explicit range-stop evidence when present. Expected classification vectors preserve unknowns for ambiguous joins, absent stamps/transcripts and absent continuation evidence. Do not mark every decision park or every warning as an interruption. hq tests validate fixture/schema and faithful hook presentation; obs-1450e7 owns actual association/classification tests and its separate approved design/plan. Record the frozen schema/fixture revision on that task; no obs code or broad alarm work is added here.
- [ ] **Step 5: Run GREEN and hygiene.** Run the full focused state/history/migration/prompt/hook/allowlist/CLI/replay/limits modules through `just test-one`, then mandatory hygiene. Confirm the measured implementation still matches the latency evidence; code affecting the measured path requires a fresh appropriate measurement.
- [ ] **Step 6: Commit.** `feat: expose durable turn-pause history for local reporting`.
- [ ] **Step 7: Obtain whole-branch review.** Merge an advanced main into the branch before final review; rerun only affected focused checks and mandatory hygiene. Dispatch a fresh final reviewer with approved spec/plan, exact base/head, evidence and the 5 Review Focus cases. Resolve Critical/Important findings through the required corrective rounds; record minors and rulings in the execution ledger and task notes.

## Human Gates and Completion Accounting

The original plan passed its human gate before Task 1. This revision requires a new human plan review before Task 3's continuation or dependent Tasks 4–5 resume; design-addendum approval alone is not plan approval. Preserve native inline execution, followed by a fresh whole-branch review and required corrective re-reviews. Plan approval authorizes implementation in the isolated worktree, not live activation. Retain the existing direct-fix and lore branches through the gate; do not close their tasks or claim live behavior changed.

After implementation/review, present the concrete reviewed code, migration/cutover receipt expectations and runbook for separate activation approval. The operator's actual window must account for the limits-changed effect on existing turns and old/new storage format exclusivity. Verify one host/profile end-to-end; the distinct Claude/Codex hook paths each get a synthetic and approved live check. No shared launcher points to the worktree.

Before park/done, refresh task-owned retained sets, preserve the external workspace ledger/reports/logs by the retained-item contract, record focused scope and actual test counts, mandatory hygiene, deliberately skipped broad work, absent/available remote evidence, pushes/processes, other work and each unmerged branch's integration owner. Run host-load and stop owned temporary processes. Preserve hq-b9d356's independent November 11 eligibility. hq-2dd09b cannot close until its owning goals and lore/obs dependencies actually satisfy the original milestone.
