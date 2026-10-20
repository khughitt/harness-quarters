# Relay cutover bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the interrupted manual cutover with one Zsh-invoked, closed-harness
bootstrap and checked agent-led verification, surface retry and finalization.

**Architecture:** A project-specific Python driver calls the existing
`relay-cutover`, relay installer and `quiesce-timers` helpers through bounded local
processes and one fixed Europa SSH entry. One protected window record and ordered
`touched.tsv` cover both hosts and all four targets. Application stays outside
harnesses; agents resume only after verified migration, with human decisions
carried explicitly from the session into the relevant tool invocation.

**Tech Stack:** Python standard library; pytest through hq's documented commands;
existing relay v0.1.1, Git/npm, systemd user bus and niri IPC. No new dependency.

**Spec:** `.worktrees/relay-cutover/docs/specs/2026-10-20-operator-runbooks-design.md`
(approved for planning after round 6; frozen predecessor `07acc26`).
**Task:** hq-c6c847; parent hq-539508; blocked original window hq-f27918.
**Status:** proposal for human plan review; no implementation or new window run.
**Execution:** preserve the user's subagent-driven choice. Work in the existing
locked, hydrated `.worktrees/relay-cutover/`; do not create another hq worktree.

## Scope and independent work

This plan implements hq's bootstrap/runbook portion. The independent Bash changes
remain dots-55f537, and the instruction changes remain lore-4c1787; each needs its
own project worktree, implementation plan, checks, review and activation approval.
Their plans must carry the approved spec's history safety and real-Claude
credential/snapshot cleanup requirements, and canonical Zsh declaration. Neither
blocks this bootstrap. Do not triage lore-881f7a or lore-8ce941 as part of delivery.

Paths and commands below are written from the main hq checkout. The focused test
route is `uv run -q --with pytest pytest <prefixed-test-path> -q`; the mandatory
precommit route is `just -f .worktrees/relay-cutover/justfile test`. There is no fast
front door or CI here. Run focused RED→GREEN, then the mandatory suite before each
implementation commit. Use a minimal nonsecret test environment retaining `USER`,
HOME, PATH and required task/session identity; omitting USER already caused false
fixture failures. Preserve unrelated live model/trust changes in main.

Task records (unstarted; plan approval pending):

- hq-628027 — Task 1: Durable records and the human-decision boundary
- hq-df06cc — Task 2: Fixed host operations and real-transport prerequisites
- hq-ee2ea1 — Task 3: Preparation, quiescence and the all-target bootstrap
- hq-f74ef6 — Task 4: Full recovery and actual-state reconciliation
- hq-293e38 — Task 5: Surface retry, safe resume, smoke receipts and finish
- hq-0796bc — Task 6: Isolated rehearsal through the production transport
- hq-b742e5 — Task 7: Replacement runbook, inert helper delivery and real-host pilot

## Execution setup before Task 1

Re-enter the worktree skill, verify this task's existing worktree lock and setup,
run its baseline `just -f .worktrees/relay-cutover/justfile test`, and record the
result before the first code edit. Reuse the trial arm on hq-c6c847; after each
start run trial-arm as instructed (the current arm is flow off). Do not turn the
planning approval into permission for a live window, desktop use or global changes.
The current interrupted window is already aborted/restored; never run that old
recovery again as setup. Keep the existing plan workspace and all review evidence.

## Global Constraints

- Relay remains v0.1.1, commit `4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`,
  with `--node /usr/bin/node`.
- Familiar PRE is `00f4899ae523d613d21f44bfc2c456aac67f8e5f`; feature tip is
  `a16f4daa59b04e32f1010764d6f94401ca4eed8b`. Merge that immutable tip, never a
  moving branch. Familiar-theme keeps its existing SSH pin and Git configuration.
- Evidence must exactly match installed `2.1.304 (Claude Code)` on both hosts and
  `codex-cli 0.163.0` on Titan. Drift stops for fresh proof, never auto-update.
- Scope: Claude personal/work on Titan and Europa; Codex personal/work on Titan.
  All four settings targets are shared: apply once on Titan, verify synchronized
  bytes on Europa. Dependencies, registries, snapshots and worktrees are host-local.
- All four targets and familiar are applied with every Claude/Codex session closed
  on both hosts. Stop only identified Codex daemons through the supported CLI;
  strict no-live has no caller exemption. Agents never apply hooks or familiar.
- One writer per harness; retire familiar and add relay in the same install.
  No registry import/merge, compatibility layer, automatic trust or synthetic hash.
- Preserve unrelated settings/model picks, Codex trust and old familiar state.
  Check exact recorded before/expected-image hashes; changes need reviewed inputs.
- Every first target write, including guard removal, follows a durable original,
  artifact-path registration and ordered ledger append. Restore refuses unknown bytes.
- Pre-merge failure automatically aborts both recorded hosts; incomplete abort or
  SIGKILL requires reconciliation/abort before a new window. No forward resume.
- Unverified familiar/apply failures require full recovery. Verified migration plus
  surface-only failure permits `restart-surfaces` and safe harness resume; timers
  remain paused and `finish` stays gated. Rollback remains available by choice.
- Full recovery re-quiesces both hosts even after partial timer restoration,
  restores every touched target, reconciles actual Git state, restores dependencies
  offline, obtains fresh desktop consent, restarts surfaces and restores timers.
- Run from explicit paths. Never repoint a shared launcher/service/include/home at
  a worktree. Reviewed new remote helpers must reach main before the window.
- Keep private state root/directories 0700 and JSON, images, logs and artifacts
  0600. Never print full settings/plans, environments, credentials or arbitrary
  subprocess output in summaries. Preserve evidence and host-local backups.
- Desktop access requires consent for that invocation; plan approval does not grant
  it. Human trust/permission attestations come from the operator, never the agent.
- Owned subprocesses are bounded and reaped on EXIT/INT/TERM/HUP. A disconnected
  SSH channel is not proof its remote process stopped. No detached monitor.
- OpenCode, Darwin, nested code-mode proof and `--with ask` remain excluded.

## Review Focus

1. **Lost SSH reply after a remote mutation:** reconcile recorded remote operation
   identity/completion before another mutation; Task 2 transport tests and Task 4
   recovery tests cover a still-running child and a completed operation with lost reply.
2. **Human consent silently supplied by an agent:** require the actual session
   ask/reply bound to one attempt and inventory/receipt, or an operator TTY answer;
   Task 1 and Task 5 test missing, declined, stale, replayed and mismatched decisions.
3. **Verified migration followed by a dead/replaced desktop process:** expected
   exited PIDs restart; new/changed context blocks only surface work, with safe
   resume and fresh consent; Task 5 tests partial restart and PID reuse.
4. **Interruption in a durability gap:** timer record, snapshot rename, merge commit,
   target registration and restore may complete before their step record; Tasks 3–4
   use actual files/Git plus failure injection, not command-spelling assertions.
5. **Stale smoke/trust evidence or mode confusion:** a different window/home/version
   or a pilot receipt cannot finish live rollout; pilot paths cannot escape scratch
   roots; Tasks 1, 5 and 6 exercise schema/binding, symlinks and live/pilot rejection.

## Files and interfaces

Create these under `.worktrees/relay-cutover/`:

| File | Responsibility |
| --- | --- |
| `tools/relay-cutover-bootstrap` | Thin executable for prepare/check/run/status/restart-surfaces/record-smoke/finish/recover |
| `tools/relay-cutover-host` | Fixed remote JSON request entry; no arbitrary remote commands or scripts |
| `tools/relay-cutover-rehearse` | Separate owned-scratch pilot entry using the same transport/operations |
| `tools/relay_cutover_bootstrap/__init__.py` | Package marker only |
| `tools/relay_cutover_bootstrap/state.py` | Protected prepared/window records, checkpoints, ledger and decisions |
| `tools/relay_cutover_bootstrap/hosts.py` | Explicit host inventory, fixed operations, SSH transport, process ownership and desktop inventory |
| `tools/relay_cutover_bootstrap/window.py` | Ordered run/abort/recover/finish operations using existing helpers |
| `tools/relay_cutover_bootstrap/smoke.py` | Exact safe resume/current-row checks, per-home evidence validation |
| `tools/relay_cutover_bootstrap/cli.py` | CLI dispatch, phase-specific status/messages and pilot entry |
| `tools/test_relay_cutover_bootstrap.py` | State, orchestration, consent, lifecycle and recovery behavior |
| `tools/test_relay_cutover_transport.py` | Local/remote protocol, process lifecycle and scratch boundary behavior |

Modify `.worktrees/relay-cutover/docs/runbooks/relay-cutover.md`,
`.worktrees/relay-cutover/docs/plans/2026-10-19-relay-cutover.md`, and
`.worktrees/relay-cutover/README.md` for the replacement workflow. Keep existing
helper CLIs and their tests unchanged unless a concrete failing orchestration test
requires a correction. Do not edit the reviewed hook images to build this tool.

Use plain JSON dictionaries across the CLI/host boundary, schema `1`; no generic
workflow, plugin or transport framework. Internal functions below take the same
objects: `prepared` is validated immutable preparation data; `window` is the active
record; `context` is validated local mode/root/host data. Paths in JSON are strings.

**Prepared data:** explicit per-host executable/home/root paths, target IDs
`claude`, `claude-work`, `codex`, `codex-work`, resolved paths, before/expected hashes,
image/evidence locations, approved pins, helper SHA manifest, captured controller
native session ID and Codex executable. Never source `operator-env.sh`. Preparation
writes only protected cutover artifacts. `prepare` is the agent's explicit artifact
creation command; `check` and `status` remain read-only.

**Window data:** unique ID; mode; attempted operation IDs; immutable preparation
hash; original per-host timer records; snapshot move/copy states; familiar merge
and revert identity; four originals/artifact paths; verified checkpoints; surfaces
and consent records; per-home smoke receipts; timer/service completion. Keep one
active pointer and immutable prior-window directories. Existing retained abort and
rehearsal directories are inventory, not active records. `touched.tsv` preserves
`target-id<TAB>resolved-target<TAB>artifact` order and original filenames.

**States:** `prepared → quiescing → applying → migrated-surfaces-pending →
ready-for-smokes → finishing → complete`. Failures before familiar mutation lead
to `aborting → aborted` or `abort-incomplete`; unverified migration failures lead
to `recovery-required → recovering → recovered` or a named recovery blocker.
`migrated-surfaces-pending` also covers the interval before the first restart.
State names never substitute for comparing actual bytes, parents, dependencies,
process identity and evidence. Unexpected drift is `inspection-required`.

**Human decision channel:** `--decision-file FILE` carries schema `1`, `kind`
(`desktop` or `smoke-attestation`), action, window/pilot ID, unique attempt ID,
`subject_sha256`, approved/declined verdict, and source. Source is either an actual
operator TTY response or `session` with native harness session ID, the exact ask,
the actual human reply and answer time. The subject is the named host/surface
inventory and impact/duration, or the exact candidate smoke receipt. An agent
previews that subject read-only, asks in the session, waits for the explicit reply,
then writes this private record and passes its path. It never answers a tool-shell
prompt or substitutes `--yes`/`--approved`. Consume an approved decision durably
before its first authorized action; reuse or changed subject requires a new ask.
The subject binds approved commands/socket and recorded process identities; an
expected recorded PID exiting does not change that authorization. CLI consumes a
decision once at invocation entry and passes the resulting record internally.
Initial `run` uses that same invocation's desktop authorization for step 6; only a
later `restart-surfaces` invocation needs another decision. External callers cannot
reuse the already-consumed file. This is an auditable record of conversational
authorization, not cryptographic proof of who typed it. The agent remains responsible for obtaining the actual
reply; syntactically valid fabricated data is never authorization. An operator
invoking directly can answer the same bounded prompt on `/dev/tty`; non-TTY with
no session decision stops with instructions. Bootstrap/recover remain operator-run.

**Smoke receipt schema:** `schema`, live `window_id`, `prepared_sha256`, host,
harness, home, native session ID, observed PID/root-row ID, exact installed/evidence
versions, `matrix` (`full`/`short`), case verdicts with private evidence paths/hash,
and human trust/permission verdicts referencing the consumed decision. Required
full cases: start-idle, allow-working/marker, attribution-denial/no-commit/no-marker,
human needs-approval, turn-done, projection-recovery, normal-exit and abrupt-death/reap.
Claude full additionally requires idle-needs-input after ≥60 s. Full applies to
Titan personal Claude/Codex; short (start, same denial, exit) to work homes and
both Europa Claude homes. Both Codex homes require their own human hook-trust review.
Bind evidence to the actual tested sessions and case operations; no pass-by-filename.
Declined/unanswered human fields cannot pass. Pilot receipts cannot satisfy this gate.

### Task 1: Durable records and the human-decision boundary

**Files:** create state module and bootstrap test file from the map above.
**Interfaces:**

- Consumes: existing private cutover snapshots/manifests, retained-state whitelist
in the spec; the `atomic_write`/directory-fsync pattern in existing `relay-cutover`.
- Produces: in the state module:
`load_record(path: Path) -> dict`, `save_record(path: Path, value: dict) -> None`,
`register_target(window: dict, target_id: str, target: Path, artifact: Path) -> None`,
`consume_decision(window: dict, decision: dict, *, kind: str, action: str,
attempt_id: str, subject_sha256: str) -> dict`.

- [ ] **Step 1:** Add `test_record_validation`, `test_target_registration_durability`
  and `test_decision_is_bound_and_single_use` for private ownership/modes and invalid schema,
  unknown active state, retained abort/rehearsal inventory, one active window,
  original/artifact registration before the first write, fsync ordering including
  new parent directories, interrupted append and consumed-decision persistence.
  Decision table assertions: absent/declined/empty ask or reply/wrong window or
  subject/replayed attempt all refuse before any host mutation; genuine explicitly
  recorded operator/session decisions bind once. Do not claim tests authenticate
  a human or synthesize a user reply for a live call. Record filesystem/child
  actions in the fixture; the ordering assertion is:
  ```python
  assert events.index("fsync:touched.tsv") < events.index("write:target")
  assert writes_after_replayed_decision == []
  ```
- [ ] **Step 2:** Run
  `uv run -q --with pytest pytest .worktrees/relay-cutover/tools/test_relay_cutover_bootstrap.py -q -k 'record or decision or register'`.
  Expected RED from absent module/functions or failed behavioral assertions.
- [ ] **Step 3:** Implement those signatures using exclusive window allocation,
  atomic JSON replacement plus parent fsync, immutable originals and durable TSV
  append. Validate owned regular files/no symlink escape. Persist the preparation
  hash and per-attempt consumed decision before any authorized subprocess starts.
  Reconciliation identifies a torn ledger entry as a blocker, never skips it.
- [ ] **Step 4:** Rerun Step 2: GREEN. Add fault-at-fsync/rename tests proving no
  target writes occur before durable registration and a lost reply cannot reuse
  a consumed approval for a new attempt; expected PID exit preserves the approved
  command scope but never admits an unrecorded new process.
- [ ] **Step 5:** Run the mandatory suite; commit only this deliverable as
  `feat(relay): persist cutover windows and human decisions`.

### Task 2: Fixed host operations and real-transport prerequisites

**Files:** create host module, remote executable and transport test file.
**Interfaces:**

- Consumes: Task 1 record formats; fixed hq/main and familiar roots derived from
that host's HOME; no caller-controlled live root/helper overrides.
- Produces: in the host module:
`request(host: str, mode: str, operation: str, payload: dict, *, timeout: float) -> dict`,
`execute(context: dict, operation: str, payload: dict) -> dict`,
`inventory(context: dict) -> dict`, `reconcile_operation(context: dict, operation_id: str) -> dict`.
The remote executable reads exactly one bounded schema-1 JSON request on stdin,
outputs one sanitized JSON response, and keeps full subprocess output private.

- [ ] **Step 1:** Write `test_remote_payload_is_data`, `test_operation_reply_loss`
  and `test_owned_process_cleanup` with a fake SSH executable and
  throwaway homes/repos. Assert the remote command is a fixed Zsh-safe entry
  `~/d/hq/tools/relay-cutover-host`, invoked with `ssh -4 -o BatchMode=yes europa`;
  roots/argv never enter the shell string. Reject unknown hosts, operations, mode,
  payload keys and oversized/malformed requests. A literal path containing quotes,
  blanks, `$()` or backticks remains data and executes nothing.
  ```python
  assert ssh_argv[-1] == "~/d/hq/tools/relay-cutover-host"
  assert not injected_marker.exists()
  ```
- [ ] **Step 2:** Run
  `uv run -q --with pytest pytest .worktrees/relay-cutover/tools/test_relay_cutover_transport.py -q`.
  Expected RED. Add fixtures for missing USER/user bus, absent SSH_AUTH_SOCK with
  working Git credentials, failed actual pinned-source access, ambiguous desktop
  socket, explained absent surfaces, helper hash drift and unfamiliar executable.
- [ ] **Step 3:** Implement the signatures with explicit allowed operations:
  inventory, daemon-stop, no-live, timer-record/stop/wait/restore/service-check,
  snapshot-refresh/abort, familiar-merge/install/reconcile/restore, target-dry/apply/
  verify/restore, surface-preview/restart, smoke-observe, operation-status and
  pilot-create/cleanup. Derive each argv locally; never expose arbitrary shell/code.
  Use validated PATH/executables, USER and the actual user's runtime bus. Resolve
  the trusted niri context without assuming inherited NIRI_SOCKET. Git auth probe
  uses `git ls-remote` of familiar-theme's pinned SSH source through the same route;
  actual pin install is proved by Task 7's pilot, not the probe alone.
- [ ] **Step 4:** Implement process groups, phase-specific deadlines, INT/TERM/HUP
  cancellation/reaping and private operation PID/start-time/completion records.
  Timer waits retain `--timeout 3600 --poll 30`; source/target sync gets a bounded
  600 s wait; installs get 900 s and report timeout as an interrupted mutation.
  A helper deadline/cancel owns its children; a new status query must settle a lost
  SSH reply before more writes. No background job waits outside harness tracking.
- [ ] **Step 5:** GREEN transport tests must prove timed-out children are gone,
  running remote operation blocks another mutation, completed lost-reply operation
  reconciles without rerunning, and no raw secret-like fixture text reaches output.
  Run mandatory suite; commit `feat(relay): add bounded cutover host transport`.

### Task 3: Preparation, quiescence and the all-target bootstrap

**Files:** create window/CLI modules and bootstrap executable; extend bootstrap tests.
**Interfaces:**

- Consumes: Tasks 1–2 interfaces and existing helper/installer commands.
- Produces: window functions
`prepare(controller_session: str) -> dict`, `check(prepared: dict) -> dict`,
`run_window(prepared: dict, decision: dict) -> dict`, `abort_window(window: dict) -> dict`;
CLI `main(argv: list[str]) -> int` with prepare/check/run/status initially.
`prepare --controller-session ID` writes private `prepared.json`; no live inputs
are changed. CLI loads protected state itself; no source/export requirement.

- [ ] **Step 1:** Add `test_bootstrap_all_targets_both_hosts` and
  `test_second_host_failure_aborts_every_recorded_host` with actual temp files/Git and
  existing helper CLIs against fixture commands. Expected trace: both-host checks,
  strict no-live, timer records/waits, refreshed verified snapshots, one immutable
  familiar merge, each host's source check/install/pin proof, Titan four dry runs
  plus Europa two Claude dry runs, then Titan-only ordered live applies and both
  hosts' verification. Assertion snippets:
  `assert shared_apply_hosts == ['titan'] * 4`;
  `assert [r['id'] for r in touched] == ['claude','claude-work','codex','codex-work']`;
  `assert final_state == 'migrated-surfaces-pending'`.
- [ ] **Step 2:** Run
  `uv run -q --with pytest pytest .worktrees/relay-cutover/tools/test_relay_cutover_bootstrap.py -q -k 'prepare or bootstrap or abort'`.
  Expected RED. Add second-host failure after first timer record, partial snapshot
  copies, version/before-image drift, active session, missing helper, sync timeout
  and source-dirty cases; assert no later mutations and restored original timers.
- [ ] **Step 3:** Implement protected preparation from resolved main paths,
  existing manifests/images and actual native controller session ID. Keep stable
  validated CLI executable paths rather than version-directory targets. Check helper
  bytes across tested worktree/Titan main/Europa main. `check` reports live-session
  blockers read-only during preparation; `run` requires every gate green after
  supported personal/work `app-server daemon stop` on Titan. Never adopt newly
  computed before/image hashes over the reviewed runbook/manifests. No manual daemon kill
  or broad pattern kill is automated; a survivor blocks for inspection.
- [ ] **Step 4:** Implement run/abort. For each host, fsync the existing timer
  helper's completed record and its parent before stopping a timer; do not assume
  that helper itself uses atomic/fsynced writes. Register snapshot moves before
  performing them. Preserve preparation originals; verify refreshed state/dependency
  trees after native writers stop. Reuse the exact runbook sequence for installer
  dry/plan/apply, `--retire familiar`, evidence, artifact and `/usr/bin/node` flags.
  Installer plans stay private; verify generated and applied images with existing
  `relay-cutover verify`, plus captured full-file hashes for cross-host sync and
  byte-gated restore. Preserve unrelated keys, never normalize them to an image.
- [ ] **Step 5:** Mark familiar mutation started before `git merge --no-ff --no-edit`
  of the pinned feature. Install via each host's actual npm `ci --allow-git=root`
  only after verified source sync. Prove package version and lock commit. Before
  each target write require all affected harnesses still closed. Durably register
  original and artifact path before Claude guard removal or any Codex write.
  Mark migration verified only after all four synchronized targets, source,
  host-local dependencies and exact evidence pass. A failed before-merge operation
  attempts abort on every recorded host even if another host is unreachable.
- [ ] **Step 6:** GREEN focused tests plus injected INT/TERM/HUP during timer/sync
  waits. A complete abort allows a fresh window; incomplete cleanup preserves state
  and directs `recover`, never forward resume. Run mandatory suite; commit
  `feat(relay): automate the closed-harness cutover window`.

### Task 4: Full recovery and actual-state reconciliation

**Files:** extend window/host/CLI modules and bootstrap/transport tests.
**Interfaces:**

- Consumes: registered originals/guard images/artifacts, per-host timer records
and saved dependencies; existing `relay-cutover restore` byte gate.
- Produces: `recover_window(window: dict, decision: dict | None) -> dict` and
`reconcile_window(window: dict) -> dict` in the window module; `recover` CLI.
A pre-merge abort needs no desktop decision; full recovery does before desktop use.

- [ ] **Step 1:** Add `test_recovery_requiesces_before_restore` and
  `test_missing_merge_record_uses_actual_parents` using real miniature Git histories and temp
  dependency trees, plus the existing restore helper with actual artifacts. Cover
  guard-only, planned/not-applied, applied/no-step-record and all-four-applied
  failures; unknown bytes must stop without force-copy. One/both timers already
  restored by a failed finish must be stopped/waited before any restore operation.
  ```python
  assert events.index("europa:service-inactive") < events.index("restore:claude")
  assert restored_target_bytes == original_target_bytes
  ```
- [ ] **Step 2:** Run the bootstrap test command with `-k 'recover or reconcile'`:
  RED. Include actual merge committed before its SHA record, merge in progress,
  refused merge at PRE, unexpected parent/HEAD, interrupted revert before record,
  already-complete revert, failed remote sync and interrupted dependency restore.
  Full source recovery ends this window: a later attempt needs newly reviewed
  inputs (the existing runbook describes reverting the recovery revert), not
  blindly merging FEATURE_TIP again or resetting to PRE.
- [ ] **Step 3:** Implement the spec's six-step recovery in order: strict no-live
  and supported daemon stop; re-quiesce both original timer records; reverse ledger
  target restore and both-host originals verification; reconcile/abort or revert
  the exact familiar merge and wait for source sync; restore each host's original
  dependencies offline; fresh-consent native surfaces; original timer/service proof.
  Never npm/fetch/reset, import old state, replace a timer record or blindly revert
  twice. Verify a recovered revert's tree equals PRE and its parent identifies the
  recorded attempted merge; unexpected history stays inspection-required.
- [ ] **Step 4:** Reconcile checkpoint-write interruptions against actual images,
  artifacts, Git parents, dependency pins and evidence. Only a fully verified
  migration may become surfaces-pending. Otherwise block fresh sessions and print
  the complete recover command. Remote operation still running or unknown blocks
  retry/recovery mutations. Pre-merge incomplete abort follows abort only.
- [ ] **Step 5:** GREEN tests must demonstrate offline restoration and all four
  originals equal their initial bytes; all fault cases preserve evidence. Inject
  signals into recovery, retry by reconciliation and verify no repeated destructive
  action. Run mandatory suite; commit `feat(relay): reconcile and recover interrupted cutovers`.

### Task 5: Surface retry, safe resume, smoke receipts and finish

**Files:** create smoke module; extend other modules/executable and bootstrap tests.
**Interfaces:**

- Consumes: verified migration, Task 1 decision channel, host operation interface.
- Produces: window functions `restart_surfaces(window: dict, decision: dict) -> dict`,
`finish_window(window: dict) -> dict`; smoke functions
`resume_argv(prepared: dict, home: str) -> list[str]`,
`check_controller(window: dict, observation: dict) -> None`,
`record_smoke(window: dict, receipt: dict, decision: dict) -> None`,
`validate_smokes(window: dict) -> None`.
CLI adds restart-surfaces/record-smoke/finish; status emits a unique next attempt
and subject digest for an agent's session question, without changing state.
After `run_window` returns the verified checkpoint, the `run` CLI invokes
`restart_surfaces` with that same invocation's consumed desktop authorization
before printing the handoff. A separate retry consumes a fresh decision.

- [ ] **Step 1:** Add `test_surface_only_failure_is_resumable`,
  `test_exited_pid_is_expected`, `test_changed_surface_context_refuses` and
  `test_session_decision_required_without_tty`: a recorded PID exits before restart, PID reuse,
  changed socket/command, an unrecorded surface, partial replacements followed by
  retry, explained absence, declined fresh consent, and no TTY in an agent call.
  Assert an exited recorded surface starts the same command; changed context never
  kills another process. Initial `run` continues into the restart with its already
  consumed invocation authorization; a retry must consume a fresh decision.
  A verified surface failure preserves migrated hooks and
  paused timers, offers safe resume/restart, and never prints the mixed-hooks ban.
  Unverified failures keep the ban/full-recovery path.
  ```python
  assert status["state"] == "migrated-surfaces-pending"
  assert current_target_bytes == verified_migrated_bytes
  assert "Do not open Claude or Codex" not in result.stdout
  ```
- [ ] **Step 2:** Run bootstrap tests with `-k 'surface or consent or resume or smoke or finish'`:
  RED. Receipt tests include wrong window/home/session/version, pilot receipt,
  substituted evidence, absent human trust/approval, denial never attempted or a
  Git identity error, and missing full cases. Controller tests require its own
  fresh native session ID/PID row, not an old matching cwd or stale idle row.
- [ ] **Step 3:** Implement restarts using recorded PID+start-time/command identity,
  TERM/wait only recorded running surfaces, exact niri spawn path and replacement
  validation. Persist each replacement before advancing; retry inventories recorded
  replacements and starts only missing surfaces. All fresh host-use permission
  goes through the operator TTY or explicit session ask/reply decision argument.
  Changed context needs inspection and a new inventory/consent, never automatic
  adoption. Agent permission prompts remain human and may leave the step pending.
- [ ] **Step 4:** Implement concrete Zsh-quoted safe resume output:
  `env CODEX_HOME=<actual-home> <validated-codex> --no-daemon resume <actual-session>`
  for the controller, plus explicit work-home launch. No aliases, placeholders,
  bypass flags, trust hashes or default-policy changes. The first controller
  action checks its fresh live row before further rollout work. Dedicated smokes
  retain Claude `--permission-mode manual` and Codex `--no-daemon --sandbox
  workspace-write --ask-for-approval on-request` for human approval coverage.
- [ ] **Step 5:** Implement the receipt schema above and `record-smoke --receipt FILE
  --decision-file FILE`. Verify event/session/evidence contents and hashes, then
  store the human attestation bound to that receipt. The agent asks the operator
  about only the human trust/permission cases, presenting the relevant host/home
  and observed verdicts; it waits for their answer. Declined or incomplete cannot
  pass. Never infer an approval dialog from a generic relay row.
- [ ] **Step 6:** Implement finish after valid receipts, surface readiness and fresh
  live source/image/dependency/evidence checks. Restore each original timer state,
  explicitly run and wait for familiar-reap.service, require Result=success and
  ExecMainStatus=0, and verify recorded dead rows/intent entries are gone. Preserve
  the current verified controller row; never reap a live controller as a test.
  A partial finish is resumable only after actual timer/service checks, never edits
  hooks/source, and never replaces original timer records. Expose paused/partially
  restored states and full recovery choice on failure.
- [ ] **Step 7:** GREEN focused tests plus mandatory suite; commit
  `feat(relay): verify migration handoffs and finalize with human evidence`.

### Task 6: Isolated rehearsal through the production transport

**Files:** create rehearsal executable; extend CLI/host modules and both test files.
**Interfaces:**

- Consumes: the same request/execute/window/restore interfaces; no alternate
implementation of the live operations.
- Produces: `rehearse(controller_session: str, decision: dict | None) -> dict`
in CLI and `tools/relay-cutover-rehearse`; private machine-readable pilot verdict.

- [ ] **Step 1:** Write `test_pilot_paths_are_contained`,
  `test_live_rejects_pilot_overrides` and `test_pilot_receipt_cannot_finish_live`
  for pilot-create ownership, returned opaque
  root IDs, mode mismatch, arbitrary live roots/helpers, traversal/symlink escape,
  a shared live target disguised as scratch and pilot receipts offered to finish.
  Assert all mutations stay inside owned pilot roots, except the separately
  consented no-window niri `true` spawn. Real timer operations are queries only;
  mutation tests use fixture systemctl. No live surface termination or replacement.
  ```python
  assert outside_files_after == outside_files_before
  assert live_mutation_calls == []
  ```
- [ ] **Step 2:** Run both new test files: RED on the missing pilot entry/contract.
- [ ] **Step 3:** Implement distinct live/pilot request schemas, scratch creation
  and cleanup. Use actual HOME/SSH configuration for Git credentials, not a fake
  HOME accidentally losing them; mutable familiar/config/state/dependency roots
  remain scratch. Use each host's actual npm and validated runtime. Pilot starts
  with one case: clone at PRE, merge feature, install/pin-proof both hosts; dry/
  apply/verify Titan four copies plus Europa Claude copies and remote image checks;
  reverse restore and recover both clones/dependency trees offline to a verdict.
  It never imports registries or launches a real harness against copied hooks.
- [ ] **Step 4:** Exercise the same niri IPC spawn operation with the fixed command
  `true` on each applicable host after invocation-specific consent; record IPC
  acknowledgement. It proves the real spawn route, not persistent surface health.
  An explicitly explained absent desktop is recorded as an exemption, never a
  fabricated pass. Fixtures separately prove replacement liveness and restart
  error handling. Retain private equality/pin/verdict evidence; remove any copied
  credentials if the implementation needed them and prove cleanup without secrets.
- [ ] **Step 5:** GREEN fixture pilot and interruption tests, mandatory suite; commit
  `test(relay): rehearse cutover over the real host protocol`.
  Do not claim the real-host pilot ran yet: Task 7 deploys the inert remote entry.

### Task 7: Replacement runbook, inert helper delivery and real-host pilot

**Files:** update runbook, original plan and README listed above; no live hook images.
**Interfaces:**

- Consumes: Tasks 1–6 reviewed commits and tests. Original Task 7 historical
rehearsals remain evidence, not proof of this runner. Dots/lore do not block.
- Produces: approved-input manifest, retained real-transport pilot report and a
reviewable one-command handoff. Live application remains unperformed.

- [ ] **Step 1:** Replace manual sourced Bash instructions with Zsh-native prepare/
  check/status and the operator command
  `~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap run`.
  Describe observed outcomes, consent channels, trust/smoke/permission interactions,
  surfaces-pending retry, paused timers, finish and complete recover commands.
  Keep precise smoke prompts/verdicts and earlier rollback fixes in the reference;
  operators never paste the reference's old Bash bodies. Amend the original plan's
  execution status/Task 8 arrangement to point to this replacement; historical
  inventories and Tasks 1–7 remain dated, not silently rewritten as current facts.
- [ ] **Step 2:** Self-check every operator code block with `zsh -n`; check the
  replacement plan/runbook cover every global constraint and distinguish fixture,
  pilot, current readiness and still-unrun live evidence. Run
  `python3 .worktrees/relay-cutover/tools/ops-docs check`, `tasks check`, focused
  new/existing relay and timer tests, then mandatory suite. Commit docs as
  `docs(relay): replace manual cutover with executable phases`.
- [ ] **Step 3:** Obtain the final whole-branch implementation review under the
  preserved subagent-driven procedure. Resolve Critical/Important findings through
  the required corrective rounds and retain full reports/notes/ledger. Minor
  deferrals and declined-to-judge behavior need explicit dispositions. This is
  before delivery to main or real-host execution, not after a live failure.
- [ ] **Step 4:** Land only reviewed inert implementation/helper/doc commits into
  main using a bounded prefix/cherry-pick as the original Task 5 did. Never merge
  the whole feature branch: it includes hook after-images that must not activate
  here. Preserve dirty trust/model picks. Verify the delivered tree equals the
  tested helper bytes, sync main to Europa, and create the private SHA manifest
  for bootstrap/package/remote/rehearsal code, existing helpers, runtime launcher,
  subscribers and installer/evidence inputs. No home-link/service changes.
- [ ] **Step 5:** Agent-run read-only checks through the new transport on both
  hosts: credentials, USER/user bus, actual source/versions/runtime, manifest,
  targets, desktop inventory and known retained state. Current controller no-live
  refusal is expected and named; other blockers are resolved before handoff.
  Capture controller native session ID and validated safe executable; run prepare.
  No timer stop, live apply, familiar merge or desktop use occurs in this step.
- [ ] **Step 6:** Ask in the session for the real pilot's no-window `true` spawn
  on the named desktop hosts, explaining that it opens no window and the one-case
  pilot is expected to take at most five minutes. After the explicit reply, pass
  its per-invocation decision into the rehearsal entry and run one end-to-end
  pilot through its verdict, foreground or harness-tracked with a covering timeout.
  Read results before any broader fault matrix. On refusal run only non-desktop
  parts and record the spawn gate pending; do not claim window readiness.
  Analyze any completed parts before retrying, ask fresh consent for another spawn,
  and retain per-host source/target/dependency equality, approved pin and cleanup.
- [ ] **Step 7:** Complete the bounded fixture fault matrix, compare helper bytes
  again if any fix occurred, and rerun only checks justified by that fix. Task-note
  the exact reviewed commit/manifest/pilot verdict and remaining live gates.
  Complete hq-c6c847 only as reviewed workflow/preparation delivery after those
  gates pass; this unblocks its dependent original window task hq-f27918. Park
  hq-f27918 and parent for the operator's session closure/window, naming that live
  smoke/timer evidence is still owed there and final checks belong to original
  Task 9. Do not keep Task 8 dependent on a bootstrap task that waits on Task 8's
  own live results, or claim the rollout done when only preparation is delivered.

## Live handoff after implementation approval and rehearsal

This section names later human gates; approving this plan does not execute them.
The agent prepares everything concrete first. The operator closes every Claude/
Codex session on both hosts, including the current controller, and runs the single
Zsh command. The bootstrap obtains that invocation's desktop consent before any
mutation and executes both-host quiescence, familiar/dependencies and all four targets.

On verified migration, resume only with the printed explicit command and human
personal Codex hook review; first prove the current controller's fresh row. If
surfaces are pending, the agent previews status, asks in the session and records
that answer for `restart-surfaces`; declining leaves it pending without rollback.
Run the exact full/short smokes, including both Codex homes' own TUI trust reviews.
Gather human verdicts through the session/TTY channel and record bound receipts;
permission prompts for SSH/systemctl remain human. Then finish timers and scheduled
reconciliation, verify Task 8 live evidence and perform original Task 9 final checks.
Keep backups/worktree through Task 9. Full recovery remains an operator-run
closed-harness command, with new desktop consent for its restarts.

## Self-review / coverage before handing this plan back

- [x] Map the approved spec: shell/one-command and input manifest → Tasks 2–3, 7;
  all-target record/apply and abort → Tasks 1, 3; actual-state/offline recovery →
  Task 4; safe resume/trust/smokes/timers/surfaces/consent → Tasks 1, 5;
  real-SSH pilot/mode isolation/spawn route → Tasks 2, 6–7;
  independent dots/lore requirements → explicit owning-task handoffs above.
- [x] Check cross-task signatures and data/schema names; all later consumers refer
  to the same defined functions. Keep test assertions behavioral and all live
  mutation roots fixed; no hidden scratch environment escape hatch.
- [x] Confirm all five Review Focus cases have tests in their owning task. No
  implementation/test results or live permission is implied by a checked plan.
- [ ] Human reviews this complete plan before Task 1 implementation begins.
