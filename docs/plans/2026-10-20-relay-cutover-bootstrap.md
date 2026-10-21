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
**Status:** accepted in plan round 5 at `df9848b` and approved by Keith, 2026-10-20;
the accepted Minor probe-order clarification is included. Execution is parked for
a fresh subagent-driven session. No implementation or new window run.
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
System-toolchain fixture tests intercept process launch at the Python boundary;
do not prepend fakes to a live system-first PATH or contact the real user bus.
Existing helper-CLI behavior tests use separate owned fixture environments.

Task records (all unstarted; plan approved, execution deferred to a fresh session):

- hq-628027 — Task 1: Durable records and the human-decision boundary
- hq-df06cc — Task 2: Host transport, inventory and operation lifecycle
- hq-ee2ea1 — Task 3: Prepare reviewed inputs, quiesce and abort before merge
- hq-c6c742 — Task 4: Dry-run all six copies before applying familiar and targets
- hq-f74ef6 — Task 5: Restore targets and familiar from reconciled state
- hq-293e38 — Task 6: Consent-bound surface restart and retry
- hq-bc710f — Task 7: Safe resume, smoke receipts and timer finalization
- hq-0796bc — Task 8: Isolated rehearsal through the production transport
- hq-b742e5 — Task 9: Replacement runbook, inert helper delivery and real-host pilot

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
  with `--node /usr/bin/node`. Installs use recorded `/usr/bin/npm` 12.2.1
  with `/usr/bin` first on PATH; record node/git/helper-Python identities too.
- Familiar PRE is `00f4899ae523d613d21f44bfc2c456aac67f8e5f`; feature tip is
  `a16f4daa59b04e32f1010764d6f94401ca4eed8b`. Merge that immutable tip, never a
  moving branch. Familiar-theme keeps its existing SSH pin and Git configuration.
- Claude evidence must exactly match the same installed version on both hosts.
  `2.1.304 (Claude Code)` is the current reviewed baseline, not a permanent pin.
  Task 9 refreshes/reviews proof for the selected actual version if it has moved.
  Hold every Claude launch from bootstrap through finish with `DISABLE_UPDATES=1`;
  agent diagnostics/probes use it individually beforehand without restricting
  ordinary use. Codex remains exactly `codex-cli 0.163.0` unless
  separately re-probed/reviewed. Never silently update a host or relax equality.
- Scope: Claude personal/work on Titan and Europa; Codex personal/work on Titan.
  All four settings targets are shared: apply once on Titan, verify synchronized
  bytes on Europa. Dependencies, registries, snapshots and worktrees are host-local.
- All four targets and familiar are applied with every Claude/Codex session closed
  on both hosts. Stop only identified Codex daemons through the supported CLI;
  strict no-live has no caller exemption. Agents never apply hooks or familiar.
- One writer per harness; retire familiar and add relay in the same install.
  No registry import/merge, compatibility layer, automatic trust or synthetic hash.
- Preserve unrelated settings/model picks, Codex trust and old familiar state.
  Claude pick-only drift follows the shared clean-filter policy below; all other
  drift requires newly reviewed inputs. Window originals remain exact byte snapshots.
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
- Owned subprocesses have deadlines and explicit cancellation/reaping. Local
  controller signals request remote cancellation and reconcile it. Closing SSH
  pipes is not cancellation: remote work finishes or reaches its own deadline,
  persists completion, then replies. No detached monitor or unbounded remote job.
- OpenCode, Darwin, nested code-mode proof and `--with ask` remain excluded.

## Review Focus

1. **Lost SSH reply after a remote mutation:** EOF/EPIPE must not signal or cancel
   the remote operation. Task 2 tests completion-before-reply, explicit cancellation
   and actual pipe closure; Tasks 5 and 8–9 reconcile a still-running operation,
   including dropping a real SSH connection during a scratch install.
2. **Human consent silently supplied by an agent:** Task 1 and Tasks 6–7 require
   actual session ask/reply bound to one attempt and inventory/receipt, or an operator
   TTY response. Missing, declined, stale, replayed and mismatched decisions refuse.
3. **Verified migration followed by a dead/replaced desktop process:** Task 6 tests
   expected exited PIDs, PID reuse, partial restart and changed context; only surface
   work stops, with safe resume and fresh consent for retry.
4. **Interruption in a durability gap:** Tasks 3–5 test timer records, snapshot moves,
   merge/record and ordered target writes/restores using actual files and Git.
5. **Stale preparation or mode confusion:** Task 3 covers live picks/clean-filter
   policy, non-pick image review and system-toolchain drift; Task 4 tests interleaved
   picks and all six dry-run verdicts before merge; Tasks 7–8 cover stale
   smoke evidence, live/pilot confusion, scratch escape and declared cache exceptions.

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
image/evidence locations and their immutable review provenance, approved pins,
per-host toolchain/cache records and helper SHA manifest, captured controller native
session ID and Codex executable. Include `.githooks/harness-state-clean` in the
project-helper manifest. Toolchain identities/hashes are per host, not an assumption
that both hosts have identical OS binaries. Never source `operator-env.sh`. Preparation
writes only protected cutover artifacts. `prepare` is the agent's explicit artifact
creation command; `check` and `status` remain read-only.

### Pick drift and explicit image review

Load `CLAUDE_JSON_KEYS` through `runpy.run_path` on the manifest-verified
`.githooks/harness-state-clean`, as `live-picks` does; never duplicate its list.
For both Claude targets, compare the whole parsed JSON object excluding those
keys with the reviewed native before-image. Reuse original cutover Task 6's retained
`prep/claude.source.json`, `prep/claude-work.source.json` and installer artifacts,
with their immutable review provenance/digests; do not use a mutable main HEAD as
a new review baseline. If their provenance cannot be verified, require image review.
The retained personal source's raw hash differs from the old live hash because
picks differ; that alone is not structural drift.

Default `prepare` accepts only this pick-only difference (plus JSON formatting)
and records eligibility/current originals and reviewed structural expectations.
It does not assemble an exact expected image by inserting picks into a template.
`relay-cutover verify` continues comparing only hooks/statusLine.

During `run`, repeat eligibility checks, pass strict no-live and quiesce both
hosts, then freeze the exact synchronized current files. **Before familiar merge**,
perform all six dry runs: Titan's four targets and Europa's two Claude copies,
using each host's pinned installer/runtime/evidence. Claude copies retire the
native guard first; Codex copies retain the required `hooks.json` basename.

For each dry run, parse the installer's planned `changes[].after` for exactly that
copy, encode that string as UTF-8 without reserialization or an extra newline,
and apply to the copy with a separate dry artifact. Require the copy's exact bytes
to equal the planned bytes. Accept them only if parsed JSON excluding the shared
filter's pick keys equals the reviewed after-image, and the pick keys/values AND
absence equal the frozen current file. For Codex, require the complete parsed
object to equal its reviewed image. The exact expected bytes are the successfully
dry-applied copy's bytes; the controller never chooses pick position, indentation,
escaping or newline. Reject mismatches via the pre-merge abort on every recorded
host, retaining evidence and leaving familiar/targets native.

Seal each frozen original, dry plan/artifact and expected output/hash in the window;
record `effective_inputs_sha256` before familiar/settings mutation. Require both
hosts' Claude outputs to agree byte-for-byte for each shared target. Before live
apply, require unchanged frozen target bytes, installer/evidence/helper identity
and subscribers; verify the live plan's own after bytes equal the sealed dry output.
After apply/sync, check exact bytes against that output. Unknown drift after merge
still requires recovery/inspection. Original reviewed images/provenance and rollback
artifacts remain immutable. Hooks/statusLine verification remains parsed.

For non-pick drift, `prepare` refuses with `input-review-required` and names the
existing original Task 6 procedure. The agent regenerates before/after images,
guard snapshots and installer plans/artifacts **on copies**, obtains their review,
records the actual review note/full report, then stages a new protected input
generation and expected-image manifest on both hosts. Keep previous generations
and all active-window rollback originals untouched. The tool checks the designated
manifest's paths, member hashes, pins and reviewed-baseline comparison; it neither
creates approval nor queries/interprets task-note/report bindings. Never adopt the
current file merely by recomputing hashes. Rerun `prepare` and all six closed-harness
dry runs after the reviewed inputs are staged. No structural-review CLI flags or
custom review-reference resolver are needed.

### Claude update hold and evidence refresh

Use the documented process environment `DISABLE_UPDATES=1`, which blocks automatic
and manual updates, rather than changing any settings/env entry in the four targets
or editing `~/.claude.json`/shared launchers. Preserve the parent's existing
environment/update policy: ordinary terminal launches after finish use their prior
policy; already-held sessions stay held until exit. Do not unset an existing user/admin policy.
Sources: [update controls](https://code.claude.com/docs/en/setup#disable-auto-updates)
and [environment reference](https://code.claude.com/docs/en/env-vars).

This is a scoped hold, not a machine-wide installation lock. Ordinary Claude use,
including `cl`/`clw` and review sessions, remains allowed throughout preparation,
pilot and any wait for the window. Individual agent diagnostics/probes use the flag
so those commands cannot update Claude; they establish no ongoing host-use ban.

Immediately before each request to close sessions, including after a parked wait,
the agent runs fresh held version checks on both hosts against reviewed evidence
and prepared identities. If unchanged, no preparation step repeats. If moved,
repeat Task 9 Steps 5–7 (including the reviewed re-probe), then check again before
asking for closure. Rerun Step 8's pilot only when helper/toolchain bytes differ
from its recorded identities; evidence/version refresh alone does not rerun it.
Do not repeat Task 9 Steps 1–4 or the fault matrix solely for ordinary Claude use
or a version refresh; Step 6 still requires the new evidence's own review/delivery.
Changes to helper/toolchain bytes retain their own checks/review/delivery
requirements before the new pilot.

The operator closes every Claude/Codex session for the bootstrap. From `run` through
finish, use only the printed held Claude commands; explicitly avoid habitual `cl`
and `clw`, unheld Claude/IDE clients, update/install commands and external installers.
`run` first completes held `claude --version` and `claude doctor` probes for every
host/home and waits for all probe processes to exit. Then it passes the final strict
no-live check, before timers pause; no caller-child exemption is allowed.
Require exact versions and the doctor's auto-update-disabled diagnostic. This closes the gap after the
agent's last check. An unproven hold/version mismatch refuses without mutation.
Apply the flag inside the remote helper's child environment; SSH need not forward
it. Printed Codex resume/work launches carry it for their tool children too.

Preparation records selected versions, resolved binary digests and per-command
doctor checks; these are dated observations, not proof of a continuous hold. Only
from bootstrap through finish must known live Claude processes match that identity
and hold key; inspect only that key for owned PIDs, never output full environments.
Unheld sessions during preparation are expected no-live blockers for `run`, not
invalidations of completed preparation or pilot. A mere manifest flag never proves
that the executable honors it.

If installed versions differ from evidence, require operator alignment to one
version (no automatic update/downgrade), then repeat original Task 3's ops probe
with `env DISABLE_UPDATES=1` and its independent evidence review. Land reviewed proof/
docs on ops main, verify both hosts' installer acceptance and refresh the private
input/helper manifest. Image changes require original Task 6 review. The sole
version-refresh repeat scope is Task 9 Steps 5–7, followed by the final held check;
existing identical-version proof is retained. No permanent 2.1.304 pin or waiver.

An unexpected move after bootstrap is a hold breach: stop new smokes, report the
paused timer state and require ordinary-shell full recovery before a fresh
Task 9 Steps 5–7 pass and final held check. Keep this conservative recovery path
rather than adding evidence replacement while a live window is active. `recover` must still work with stale Claude evidence: it uses strict
no-live, pinned relay rollback and byte/Git/dependency proofs, without launching
Claude or requiring its installed version to equal the obsolete evidence. Restore
native state and original timers first; do not leave timers paused waiting for an
in-place re-probe or add automatic mid-window evidence acceptance.

**Until `finish` reports complete, do not change/save Claude model or effort defaults
in either home on either host, including through `/model` or `/effort`.** Print this
in successful and surfaces-pending handoffs and the replacement runbook. If picks
changed anyway, ordinary hooks/statusLine verification can still pass, but unknown
bytes block full recovery for inspection. Do not force restore or add an unreviewed
pick-rewriting branch. After finish the restriction ends.

### Toolchain, environment and permitted cache writes

On each host record `/usr/bin/npm` (must report `12.2.1`), `/usr/bin/node`, resolved
system Git and `/usr/bin/python3`: executable/real-entry paths, exact versions and
SHA256s. Record npm's package version/CLI entry as well as its env-node shebang.
`check`/`run` compare these identities with prepared data and the per-host manifest;
version/path/hash drift stops for fresh preparation/proof. No host package updates.
Run installs as `/usr/bin/npm ci --allow-git=root`, with explicit
`PATH=/usr/bin:/bin:<recorded validated remainder>` so npm's env shebang resolves
`/usr/bin/node`, not nvm. The fixed SSH entry is
`exec /usr/bin/python3 -B ~/d/hq/tools/relay-cutover-host`.

The helper retains the host's startup environment for authentication references,
user bus and host-local cache routing; it overrides PATH as above and sets
`PYTHONDONTWRITEBYTECODE=1` for Python children. `-B` covers the remote entry before
imports. Never clear HOME/authentication or silently fall back to in-checkout
`__pycache__`. Inspect cache routing without logging credentials or the environment.

Pilot application/config/state/dependency/temp roots are owned scratch roots;
set TMPDIR there. Explicit permitted writes outside them are the prepared,
validated host-local cache prefixes (npm_config_cache and any cache roots used by
install/build subprocesses, including inherited CACHE_DIR/PYTHONPYCACHEPREFIX),
existing authentication/SSH runtime bookkeeping, and the consented no-window niri
IPC spawn. Record exact cache prefixes in the pilot report; reject a cache prefix
overlapping Dropbox or any live checkout/settings/state (including an ancestor
that contains them), or a symlink into one. Python
bytecode creation stays disabled despite retaining its configured prefix. Permit
no other tool-owned writes outside scratch, no real timers/surface restarts, and
no mutable pilot path into live project data. Fixture containment assertions exclude
only those declared caches/runtime effects, not arbitrary directories. The pilot
must report these exceptions instead of claiming the whole host stayed byte-equal.

**Window data:** unique ID; mode; attempted operation IDs; immutable preparation
hash plus effective window input hashes; original per-host timer records; snapshot move/copy states; familiar merge
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

### Optional review suggestion

Transcript validation of agent-authored decision records is deferred. The current
session-logs skill documents human/injected-turn classification and episode
extraction, not a live-consent lookup interface. This plan does not add another
classifier or depend on native log flush timing. Actual session asks and explicit
human replies remain mandatory; records remain auditable, not transcript-verified.
A later shared lookup can add that check without changing this cutover's consent
channel. No fallback accepts fabricated or unanswered decisions.

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
  `uv run -q --with pytest pytest .worktrees/relay-cutover/tools/test_relay_cutover_bootstrap.py -q -k 'record or decision or register or registration'`.
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

### Task 2: Host transport, inventory and operation lifecycle

**Files:** create host module, remote executable and transport test file.
**Interfaces:**

- Consumes: Task 1 record formats; fixed hq/main and familiar roots derived from
that host's HOME; no caller-controlled live root/helper overrides.
- Produces: in the host module:
`request(host: str, mode: str, operation: str, payload: dict, *, timeout: float) -> dict`,
`execute(context: dict, operation: str, payload: dict) -> dict`,
`inventory(context: dict) -> dict`, `reconcile_operation(context: dict, operation_id: str) -> dict`,
`claude_hold_env(base: dict) -> dict` (copy with DISABLE_UPDATES=1; never mutate base),
`start_request(host: str, mode: str, operation: str, payload: dict, *, timeout: float)
-> tuple[str, subprocess.Popen]`. `request` wraps `start_request` with bounded
collection/cleanup; the rehearsal owns the returned handle when testing disconnect.
The request envelope carries schema/mode/operation, a caller-known operation ID
and payload. Status/cancel identify that operation; no arbitrary PID is accepted.
The remote executable reads one complete bounded request, writes its durable start
record, outputs one final sanitized JSON response, and keeps full logs private.

- [ ] **Step 1:** Write `test_remote_payload_is_data`, `test_operation_reply_loss`,
  `test_owned_process_cleanup` and `test_claude_hold_env_is_scoped` with a fake SSH executable and
  throwaway homes/repos. Assert the remote command is a fixed Zsh-safe entry
  `exec /usr/bin/python3 -B ~/d/hq/tools/relay-cutover-host`, invoked with `ssh -4 -o BatchMode=yes europa`;
  roots/argv never enter the shell string. Reject unknown hosts, operations, mode,
  payload keys and oversized/malformed requests. A literal path containing quotes,
  blanks, `$()` or backticks remains data and executes nothing.
  ```python
  assert ssh_argv[-1] == "exec /usr/bin/python3 -B ~/d/hq/tools/relay-cutover-host"
  assert not injected_marker.exists()
  ```
- [ ] **Step 2:** Run
  `uv run -q --with pytest pytest .worktrees/relay-cutover/tools/test_relay_cutover_transport.py -q`.
  Expected RED. Add fixtures for missing USER/user bus, absent SSH_AUTH_SOCK with
  working Git credentials, failed actual pinned-source access, ambiguous desktop
  socket, explained absent surfaces, helper hash drift and unfamiliar executable.
  A failed/missing doctor disabled-update diagnostic rejects bootstrap readiness;
  the recorded flag alone cannot pass. Add `test_inventory_reports_unheld_claude`:
  inventory reports ordinary sessions without rejecting its read-only observation;
  phase callers enforce closure/hold only for bootstrap and validation.
- [ ] **Step 3:** Implement only transport/schema/process ownership, inventory,
  read-only prerequisite probes, operation-status and explicit operation-cancel.
  Route Claude diagnostics/children through `claude_hold_env`, including remote
  operations; never rely on SSH forwarding the variable. Tests cover inheritance,
  unchanged parent env and both homes without exposing other environment keys.
  Inventory reports known/unknown/unheld processes; forward callers gate them only
  from bootstrap through finish. It records the version/hold, toolchain/cache
  contract above, user bus, Git auth and
  trusted desktop context. `git ls-remote` probes access; the pilot proves install
  of the actual pinned source. Unknown/unimplemented operations refuse before writes.
  Timer/snapshot operations are added with Task 3 tests, merge/install/target apply
  with Task 4, restoration/service-run/check with Task 5, surfaces with Task 6,
  smoke observation with Task 7, and pilot-create/cleanup with Task 8; no stubs now.
- [ ] **Step 4:** Implement private operation IDs/PIDs/start-times, bounded child
  groups and durable completion records. A complete request followed by EOF/EPIPE
  does not cancel the remote operation: it finishes or reaches its own deadline,
  persists its completion record before trying to reply, and tolerates the broken
  reply pipe. Only operation-cancel or an actual signal/deadline cancels/reaps it.
  Local INT/TERM/HUP sends explicit cancel and reconciles; if unreachable report
  pending bounded remote work, never assume it stopped. Timer waits use 3600 s/poll
  30, source/target sync 600 s, installs 900 s. Operation records survive all replies.
  Fake SSH closes pipes without delivering a signal; tests separately cover explicit
  cancel and signal cleanup. Never detach a monitor; never end a controller turn
  while its own tracked check/child remains running.
- [ ] **Step 5:** GREEN transport tests must prove timed-out children are gone,
  running remote operation blocks another mutation, completed lost-reply operation
  reconciles without rerunning, and no raw secret-like fixture text reaches output.
  Run mandatory suite; commit `feat(relay): add bounded cutover host transport`.

### Task 3: Prepare reviewed inputs, quiesce and abort before merge

**Files:** create window/CLI modules and bootstrap executable; extend bootstrap and
transport tests. Reuse filter key authority; do not modify the filter itself.
**Interfaces:**

- Consumes: Tasks 1–2 state, inventory and request interfaces; reviewed input policy above.
- Produces: window functions `prepare(controller_session: str) -> dict`,
`check(prepared: dict) -> dict`, `quiesce_window(prepared: dict, decision: dict) -> dict`,
`abort_window(window: dict) -> dict`; CLI `main(argv: list[str]) -> int` for
prepare/check/status for eligibility and staged reviewed-manifest validation.
Task 4 adds the closed-harness dry-run gate;
this task does not generate exact expected bytes or expose a live run entry.

- [ ] **Step 1:** Add `test_prepare_preserves_filter_owned_picks`,
  `test_nonpick_drift_names_original_image_review`, `test_run_input_recheck_accepts_pick_only_drift`,
  `test_system_toolchain_wins_over_nvm`, `test_second_host_failure_aborts_both`
  and `test_prepare_allows_ordinary_claude_sessions`. Preparation records sessions
  as future run blockers without demanding closure or a continuing update hold.
  Vary every key loaded from the filter, missing-key deletion and arbitrary nested
  pick values; non-pick/hook/statusLine edits reject. Mutate the fixture filter key
  list to prove reuse. Record current pick values/absence without serializing
  a new after-image; reviewed originals stay unchanged. Fixtures provide their
  own reviewed input manifest, not active checkout hooks; test both native and
  candidate checkout variants. Non-pick drift refuses without mutating/adopting
  inputs and names original Task 6; a corrupt/missing member/pin/path also refuses.
  Task records and full reports remain the review workflow's evidence, not a
  custom authorization format interpreted by this tool.
  ```python
  assert nonpick(current_before, filter_keys) == nonpick(reviewed_before, filter_keys)
  assert recorded_picks_and_absence == current_picks_and_absence
  assert install_env["PATH"].split(":")[0] == "/usr/bin"
  assert npm_executable == "/usr/bin/npm" and npm_version == "12.2.1"
  ```
- [ ] **Step 2:** Run the bootstrap/transport test files with
  `-k 'prepare or pick or manifest or toolchain or quiesce or abort'`: RED. Include invalid
  baseline provenance, corrupt images, npm 11/changed node/Git/Python identity,
  cache inside a live checkout, run refusal for active sessions (prepare records
  them without refusal), partial snapshot copies, signals
  and second-host failure after the first timer record. No later live writes.
- [ ] **Step 3:** Implement eligibility/refusal and the staged reviewed input
  manifest checks above. Capture immutable provenance/current input hashes;
  don't replace reviewed manifests with arbitrary current files. Add daemon-stop,
  no-live, timer-record/stop/wait/restore and snapshot-refresh/abort operations under
  these tests. Supported personal/work `app-server daemon stop` on Titan only;
  survivors block for inspection, no manual/broad kill. `check` remains read-only.
- [ ] **Step 4:** Implement quiesce/abort on both hosts. Fsync timer helper output
  and parent before stopping; register snapshot moves before acting. Preserve old
  snapshots, refresh after native writers stop, verify state/dependency trees.
  Return the quiescent state to Task 4 before any familiar/settings mutation.
  Any pre-merge failure aborts every recorded host; completed abort permits a new
  window, incomplete abort/SIGKILL requires reconciliation and abort first. Add
  `test_failure_returns_to_zsh` with original shell variables retained and sanitized
  step/host/status/log/next-command output. Run focused tests: GREEN.
- [ ] **Step 5:** Mandatory suite; commit
  `feat(relay): prepare pick-safe cutover inputs and quiesce hosts`.

### Task 4: Dry-run all six copies before applying familiar and targets

**Files:** extend window/host/CLI modules and bootstrap/transport tests.
**Interfaces:**

- Consumes: Task 3 `prepare`, `check`, `quiesce_window`, `abort_window`; Tasks 1–2 records/transport.
- Produces: `dry_targets(window: dict) -> dict` and
`run_window(prepared: dict, decision: dict) -> dict` in window; CLI `run` through the
verified migration checkpoint. No structural-review subcommands/resolver are added.
Add target-dry/apply/verify and familiar-merge/install operations with these tests.

- [ ] **Step 1:** Add `test_six_dry_runs_precede_merge`,
  `test_interleaved_picks_use_installer_bytes`, `test_dry_mismatch_aborts_before_merge`,
  `test_all_target_bootstrap_single_writer`, `test_europa_claude_uses_local_installer`,
  `test_sync_before_install`, `test_registration_before_guard_write` and
  `test_bootstrap_probes_exit_before_final_no_live`. Keep probe processes live in
  the fixture until collected; assert all held version/doctor probes have exited
  before the final no-live check and that timers stop only afterward. A surviving
  probe refuses before mutation; no caller-child exemption is accepted.
  The Claude fixture orders `model` before `hooks`, and `effortLevel`/`modelSettings`
  after `alwaysThinkingEnabled`, matching live positions. Also vary removed keys,
  nested values, formatting and non-ASCII text. Compare installer plan string bytes,
  applied-copy bytes and sealed bytes directly, never controller reserialization.
  ```python
  assert expected_bytes == dry_copy.read_bytes() == planned_after.encode("utf-8")
  assert last_dry_verdict_index < merge_start_index
  assert apply_hosts == ["titan"] * 4
  assert target_order == ["claude", "claude-work", "codex", "codex-work"]
  ```
- [ ] **Step 2:** Run both new test files with
  `-k 'dry or interleaved or apply or bootstrap or sync or guard or installer'`: RED.
  Any of six dry plan/apply/semantic/byte failures must abort both timer/snapshot
  windows, leave familiar HEAD at PRE and write no live target/merge marker.
  Include manifest drift and exact-evidence refusal,
  cross-host output disagreement, target drift after freeze and sync timeout.
- [ ] **Step 3:** At run step 1 repeat eligibility/toolchain checks. Complete and
  collect held version/doctor probes for every host/home, then perform the final
  strict no-live check without child exemptions, then quiesce.
  Freeze the exact synchronized current files and complete all six local dry runs
  before merging. Take expected bytes only from their applied copies after plan-
  byte equality and parsed approval/pick checks above. Seal input/output identities
  and effective hashes. Non-pick disagreement points to the original image-review
  procedure; never updates its own approval baseline. Abort before merge on failure.
- [ ] **Step 4:** Only after all six verdicts pass, mark familiar mutation and merge
  the immutable feature. Wait for verified source sync before each system npm
  install/pin proof. Register every original/artifact before the first target write;
  retain frozen native bytes exactly. Apply once on Titan with existing guard
  retirement, relay flags and artifacts. Recheck frozen input and live plan-after
  equality to the sealed dry bytes, then applied/synchronized bytes. No second
  post-merge dry-run phase is needed. Before each write require harnesses closed.
  Verify all hosts' targets/source/dependencies/evidence before marking migration
  verified; post-merge unknown drift still requires full recovery/inspection.
- [ ] **Step 5:** GREEN focused tests and mandatory suite; commit
  `feat(relay): dry-run frozen inputs before the familiar transition`.

### Task 5: Restore targets and familiar from reconciled state

**Files:** extend window/host/CLI modules and bootstrap/transport tests.
**Interfaces:**

- Consumes: Tasks 3–4 registered originals/guard images/artifacts, per-host timer records
and saved dependencies; existing `relay-cutover restore` byte gate.
- Produces: `restore_window(window: dict) -> dict` and
`reconcile_window(window: dict) -> dict` in the window module, plus fixed
service-run/check host operations used by recovery and later finish.
This restoration core returns with native targets/source/dependencies verified,
timers paused and state `recovering`; it cannot report recovery complete. Task 6
adds the full recover CLI by joining native surfaces and original timers/services.
No placeholder surface operation or live recovery entry is exposed in this task.

- [ ] **Step 1:** Add `test_recovery_requiesces_before_restore` and
  `test_missing_merge_record_uses_actual_parents` and `test_service_run_wait_and_result`
  using real miniature Git histories and temp
  dependency trees, plus the existing restore helper with actual artifacts. Cover
  guard-only, planned/not-applied, applied/no-step-record and all-four-applied
  failures; unknown bytes must stop without force-copy. Include
  `test_recovery_works_after_version_hold_breach` to prove stale Claude evidence
  does not block no-live/byte-gated rollback; Task 6 extends it through original
  timer restoration. Never launch the changed Claude during recovery.
  `test_post_resume_pick_drift_refuses_restore`: changing a pick after apply still
  stops recovery for inspection; the handoff freezes picks until finish. One/both timers already
  restored by a failed finish must be stopped/waited before any restore operation.
  ```python
  assert events.index("europa:service-inactive") < events.index("restore:claude")
  assert restored_target_bytes == original_target_bytes
  ```
- [ ] **Step 2:** Run the bootstrap test command with `-k 'recover or reconcile or merge_record or service or pick_drift or hold_breach'`:
  RED. Include actual merge committed before its SHA record, merge in progress,
  refused merge at PRE, unexpected parent/HEAD, interrupted revert before record,
  already-complete revert, failed remote sync and interrupted dependency restore.
  Full source recovery ends this window: a later attempt needs newly reviewed
  inputs (the existing runbook describes reverting the recovery revert), not
  blindly merging FEATURE_TIP again or resetting to PRE.
- [ ] **Step 3:** Add familiar-reconcile/restore, target-restore and service-run/check
  operations under these tests. Implement the restoration core in order: strict
  no-live/supported daemon stop; re-quiesce both original timer records; reverse
  ledger restore and both-host originals proof; reconcile/abort/revert exact familiar
  merge, wait for source sync and restore each host's dependencies offline. Return
  native-surfaces/timer stages as still pending for Task 6's full recovery join.
  Do not call forward check/preflight or Claude diagnostics here: obsolete Claude
  version/evidence/binary identity may differ, while protected rollback inputs,
  pinned relay and restoration byte/source/dependency checks remain mandatory.
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

### Task 6: Consent-bound surface restart and retry

**Files:** extend window/host/CLI modules and bootstrap/transport tests.
**Interfaces:**

- Consumes: verified Task 4 migration, Task 1 consumed invocation decision, Task 2 desktop inventory.
- Produces: `restart_surfaces(window: dict, decision: dict) -> dict` and
`recover_window(window: dict, decision: dict | None) -> dict` in the window module;
CLI restart-surfaces/recover, surface-preview/restart and pilot-only fixed-true probe.
Full recover dispatches pre-merge abort or Task 5's restoration core, then native
surfaces with fresh consent, original timer restore and service success. Until
those pass it retains `recovering` and forbids opening harnesses. Tests assert
this six-stage order, including retry after partial timer restoration and after a
Claude hold breach. Recovery uses desktop-only preview, never full forward
inventory/Claude diagnostics. Initial `run` uses `restart_surfaces` after its verified
checkpoint with the same invocation's consumed authorization. A later retry needs fresh actual consent.

- [ ] **Step 1:** Add `test_exited_pid_is_expected`, `test_surface_failure_is_pending`,
  `test_changed_context_refuses`, `test_partial_restart_retry` and
  `test_session_decision_required_without_tty`. Cover PID reuse, changed socket/
  command, unrecorded new process, explained absence and declined/missing/replayed
  consent. Direct operator TTY and agent session decisions use the same scoped record.
  ```python
  assert status["state"] == "migrated-surfaces-pending"
  assert live_hooks_after == verified_live_hooks_before
  assert "Do not open Claude or Codex" not in failed_surface_result.stdout
  ```
- [ ] **Step 2:** Run bootstrap/transport tests with `-k 'surface or consent or pid or context or restart or decision'`:
  RED. Failed unverified migration must retain the mixed-hooks ban/full-recovery path.
- [ ] **Step 3:** Implement recorded PID+start-time/command identity, TERM/wait only
  recorded live surfaces, exact niri spawn and replacement validation. An exited
  recorded PID starts its same command. Changed context stops for inspection/new
  inventory and consent. Persist each replacement before advancing; retry starts
  only missing recorded surfaces and never kills an unknown process.
- [ ] **Step 4:** Join initial run/recovery desktop stages to this operation without
  consuming one invocation decision twice. Non-TTY agent calls require actual
  session ask/reply and decision-file; no prompt fallback or self-grant flag. Add
  fixed `true` spawn path for pilot use, including explicit per-invocation consent;
  no arbitrary probe command. GREEN focused tests plus signal/partial-reply cases.
- [ ] **Step 5:** Mandatory suite; commit
  `feat(relay): restart and retry recorded surfaces with consent`.

### Task 7: Safe resume, smoke receipts and timer finalization

**Files:** create smoke module; extend window/host/CLI modules and both test files.
**Interfaces:**

- Consumes: Task 6 surface readiness, Task 1 decisions, Task 2 transport and Task 4 verified images.
- Produces: `finish_window(window: dict) -> dict` in window; smoke functions
`resume_argv(prepared: dict, home: str) -> list[str]`,
`check_controller(window: dict, observation: dict) -> None`,
`record_smoke(window: dict, receipt: dict, decision: dict) -> None`,
`validate_smokes(window: dict) -> None`. Add record-smoke/finish CLI and smoke-observe
operations with their own tests; service-run/check reuse Task 5
and timer restore reuses Task 3.

- [ ] **Step 1:** Add `test_resume_has_no_bypass_flags`, `test_current_row_is_fresh`,
  `test_receipt_is_bound_to_real_cases`, `test_human_attestation_is_required` and
  `test_partial_finish_keeps_original_timers`, `test_handoff_freezes_claude_picks`,
  `test_selected_evidenced_version_can_advance_before_window` and
  `test_final_check_names_bounded_refresh`. Assert check/status instructions allow
  normal use while parked, reuse proof for unchanged final versions, name only
  Task 9 Steps 5–7 for version movement and require a new pilot only for changed
  helper/toolchain bytes. Instructions require a fresh held check before each
  closure ask; the agent performs the refresh/review, not an automatic tool loop.
  Both ready and surfaces-pending handoffs name both hosts/homes, no model/effort
  changes and no habitual `cl`/`clw` launches until finish. Stale row/cwd, wrong window/home/
  session/version, pilot receipt, missing/altered evidence or human verdict reject.
  Denial not attempted/Git identity error cannot pass; neither can automatic approval.
  ```python
  assert "--dangerously-bypass-approvals-and-sandbox" not in resume_args
  assert "DISABLE_UPDATES=1" in resume_args
  assert not finish_called_with_incomplete_receipts
  assert timer_records_after == timer_records_before
  ```
- [ ] **Step 2:** Run bootstrap/transport tests with `-k 'resume or smoke or finish or receipt or attestation or handoff or selected_evidenced_version or final_check'`:
  RED. Include surface-pending, declined SSH/systemd permission, one timer restored,
  service still running/failing, hold breach during smokes, and accidental targeting
  of the live controller. New selected versions require reviewed matching evidence
  and fresh receipts; stale proof never passes or permanently pins code to 2.1.304.
- [ ] **Step 3:** Print concrete Zsh-quoted executable/home/native-session argv with
  `--no-daemon resume`, never aliases/bypass flags/placeholders. First controller
  check proves its own fresh native ID/PID row before further rollout work. Work
  home gets its explicit command and human hook review too. Print the Claude
  model/effort freeze and held-launch warnings, naming `cl` and `clw`, before every
  handoff until finish. Do not extend that restriction into preparation or parking.
  Include `DISABLE_UPDATES=1` in Codex argv and explicit Claude personal/work/smoke
  commands; known Claude children/probes use that held env. Controller policies
  use defaults; dedicated smokes keep Claude `--permission-mode manual` and Codex
  `--no-daemon --sandbox workspace-write --ask-for-approval on-request`.
- [ ] **Step 4:** Implement the receipt schema above and `record-smoke --receipt FILE
  --decision-file FILE`. Validate actual session/case/evidence contents and hashes;
  obtain the human trust/permission verdicts through actual session ask/reply or
  operator TTY, bind/consume their decision and persist the receipt. Do not add an
  untested transcript classifier or infer human approval from event delivery.
- [ ] **Step 5:** Implement finish after all receipts, surface readiness and fresh
  source/hooks/statusLine/dependency/evidence checks. Live pick changes after resume
  do not fail hook verification or rewrite rollback originals. Restore original
  per-host timers; run/wait familiar-reap.service; require Result=success and
  ExecMainStatus=0; verify recorded dead rows/intent gone, preserving the current
  controller. Hold/evidence drift stops forward finish and directs full recovery,
  which must restore timers despite obsolete Claude evidence. A successful finish
  releases the workflow restriction; held sessions exit for ordinary update policy.
  Partial finish reconciles actual timers/services before retry; it
  never edits hooks/source or replaces original timer records. GREEN focused tests.
- [ ] **Step 6:** Mandatory suite; commit
  `feat(relay): validate human smoke evidence and finalize timers`.

### Task 8: Isolated rehearsal through the production transport

**Files:** create rehearsal executable; extend CLI/host modules and both test files.
Also modify `.worktrees/relay-cutover/tools/relay-cutover` and
`.worktrees/relay-cutover/tools/test_relay_cutover.py` for explicit scratch roots
in its two read-only familiar checks, proven by a failing fixture first.
**Interfaces:**

- Consumes: Tasks 1–7, using the same request/execute/window/restore interfaces; no alternate
implementation of the live operations.
- Produces: `rehearse(controller_session: str, decision: dict | None) -> dict`
in CLI and `tools/relay-cutover-rehearse`; private machine-readable pilot verdict.

- [ ] **Step 1:** Write `test_pilot_paths_are_contained`,
  `test_live_rejects_pilot_overrides` and `test_pilot_receipt_cannot_finish_live`
  for pilot-create ownership, returned opaque
  root IDs, mode mismatch, arbitrary live roots/helpers, traversal/symlink escape,
  a shared live target disguised as scratch and pilot receipts offered to finish.
  Assert application mutations stay inside owned pilot roots, except the declared
  prepared cache/runtime writes and consented no-window niri `true` spawn above.
  Real timer operations are queries only;
  mutation tests use fixture systemctl. No live surface termination or replacement.
  ```python
  assert outside_application_files_after == outside_application_files_before
  assert live_mutation_calls == []
  ```
- [ ] **Step 2:** Run both new test files: RED on the missing pilot entry/contract.
  Add `test_familiar_checks_use_explicit_root_without_changing_home` to existing
  helper tests: current hardcoded HOME/d/familiar must not inspect the live source
  when a pilot root is requested. Prove actual HOME/authentication stays unchanged.
  Run `uv run -q --with pytest pytest .worktrees/relay-cutover/tools/test_relay_cutover.py -q -k explicit_root`:
  RED for the missing root argument; retain that check in this task's GREEN run.
- [ ] **Step 3:** Extend only existing familiar-source/familiar-check with optional
  `--root <absolute-directory>` (default remains main) for those read-only checks;
  pilot passes its validated owned scratch root, live driver derives fixed main.
  No live run/recover root override or fake HOME credential workaround. Implement
  distinct live/pilot request schemas, scratch creation
  and cleanup, adding pilot-create/cleanup operations here. Retain the actual
  HOME/SSH authentication, user bus and prepared host-local cache routing, with
  fixed system PATH/Python bytecode policy above; TMPDIR and mutable application
  roots stay scratch. Use `/usr/bin/npm` 12.2.1 and recorded `/usr/bin/node`.
  For one case, clone at PRE and freeze copied current targets with interleaved
  picks. Pass the same six dry-run/parsed-approval/exact-byte checks before the
  scratch merge/install; then apply/verify Titan's four separate live-simulation
  target copies and remote image expectations, using those sealed expected bytes;
  use Task 5's same restoration core to restore targets and both clones/dependency
  trees offline to a verdict. Pilot surface/timer mutation stays unexercised, not
  a fabricated full live-recovery pass; the separate true-spawn probe covers IPC.
  It never imports registries or launches a real harness against copied hooks.
- [ ] **Step 4:** Exercise the same niri IPC spawn operation with the fixed command
  `true` on each applicable host after invocation-specific consent; record IPC
  acknowledgement. It proves the real spawn route, not persistent surface health.
  An explicitly explained absent desktop is recorded as an exemption, never a
  fabricated pass. Fixtures separately prove replacement liveness and restart
  error handling. Retain private equality/pin/verdict evidence; remove any copied
  credentials if the implementation needed them and prove cleanup without secrets.
- [ ] **Step 5:** Add `test_disconnect_closes_pipes_without_signal` and the real
  disconnect pilot case: create a second scratch clone/install on Europa through
  `start_request`, query operation-status over a second connection until its durable
  start is visible, then drop only the returned owned local SSH client
  while the install is running, then reconnect by operation ID. The helper reaches
  completion/deadline, persists before reply and never restarts npm from scratch.
  Require a known completion and equality/pin verdict before cleanup. If install
  finishes before the disconnect point, the case is unexercised, not passed; retry
  with an explicit pilot-only latch after npm has actually started (fixtures can
  wrap the scratch install launch), never alter live install timing or pass a
  missing install-start observation. Reap the killed local client; the tracked
  rehearsal keeps reconciling the bounded remote operation before it can exit.
  The fake SSH closes stdin/stdout/reply pipes, sends no remote signal, and proves
  the same result. On deadline/failure recover those scratch dependencies offline.
- [ ] **Step 6:** GREEN fixture pilot and interruption tests, mandatory suite; commit
  `test(relay): rehearse cutover over the real host protocol`.
  Do not claim the real-host pilot ran yet: Task 9 deploys the inert remote entry.

### Task 9: Replacement runbook, inert helper delivery and real-host pilot

**Files:** update runbook, original plan and README listed above; no live hook images.
**Interfaces:**

- Consumes: Tasks 1–8 reviewed commits and tests. Original Task 7 historical
rehearsals remain evidence, not proof of this runner. Dots/lore do not block.
- Produces: approved-input manifest, retained real-transport pilot report and a
reviewable one-command handoff. Live application remains unperformed.

- [ ] **Step 1:** Replace manual sourced Bash instructions with Zsh-native prepare/
  check/status and the operator command
  `~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap run`.
  Describe observed outcomes, consent channels, trust/smoke/permission interactions,
  surfaces-pending retry, paused timers, finish and complete recover commands.
  State that all six frozen-input dry runs precede merge and expected bytes come
  from the installer; include the original image-review procedure, held launch
  commands/evidence refresh loop and Claude pick freeze.
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
  here. Preserve dirty trust/model picks. Run `just test` on the actual delivered
  main tree: it intentionally lacks the feature branch's hook after-images, so the
  worktree suite does not prove this combination. If it fails, inspect/fix/review
  the inert delivery without activating hook images; do not claim it is ready or
  proceed to Europa helper use. After that pass, verify tested helper-byte equality,
  wait for matching main bytes on Europa, and create the private SHA manifest
  for bootstrap/package/remote/rehearsal code, existing helpers, runtime launcher,
  subscribers, clean-filter key authority, installer/evidence inputs and per-host
  npm/node/Git/helper-Python identities/versions/digests. Dropbox may copy inert
  files earlier; main's passing suite gates Europa execution, not a claim that
  automatic synchronization was paused. No home-link/service changes.
- [ ] **Step 5:** Observe both hosts' versions/binary digests and each personal/
  work home's doctor diagnostic using individually held commands. Ordinary Claude
  sessions, including reviewers, may stay online; there is no ongoing hold yet.
  If host versions differ, request operator alignment to one selected version
  without silently updating/downgrading. No timer/source/settings/desktop change.
- [ ] **Step 6:** If actual Claude version differs from shared evidence, execute
  original plan Task 3 and the reviewed hq-7efef3 refresh pattern: locked/hydrated
  ops and detached exact-v0.1.1 relay worktrees, isolated Europa probe homes with
  credential cleanup, `env DISABLE_UPDATES=1` on the probe process, required allow/
  context/deny proof, and version checks before/after on both hosts. Keep excluded/
  unproven surfaces excluded. Run ops's declared checks, obtain an independent
  evidence review and record its standard review note/full report before landing
  reviewed evidence/probe docs on ops main. Use the established shared-proof
  approach only with the same evidenced version on both hosts; verify installer
  acceptance on both copies. Refresh the private evidence/input/helper manifest
  only after review. If new capabilities change images, regenerate/review them
  via original Task 6 first. Do not rerun unchanged Codex evidence. A version move
  repeats only Steps 5–7; unchanged versions reuse proof. Ordinary use alone never
  invalidates preparation. No version waiver or continuous pre-window hold.
- [ ] **Step 7:** Agent-run transport checks on both hosts for credentials, user
  bus, source/runtime, held version/evidence, manifest, targets, desktop inventory
  and retained state. Existing Claude/Codex sessions are expected future no-live
  blockers, not a reason to close sessions now or reject preparation. Capture
  controller identity/safe executable and run prepare. Ordinary use remains allowed
  while parked; no live apply/merge/timer stop/desktop use occurs in this step.
- [ ] **Step 8:** Ask in the session for the real pilot's no-window `true` spawn
  on the named desktop hosts, explaining that it opens no window and the one-case
  pilot is expected to take at most five minutes. After the explicit reply, pass
  its per-invocation decision into the rehearsal entry and run one end-to-end
  pilot through its verdict, foreground or harness-tracked with a covering timeout.
  Read results before any broader fault matrix, then run Task 8's one real
  scratch-install disconnect/reconciliation case through its verdict. On refusal
  run only non-desktop
  parts and record the spawn gate pending; do not claim window readiness.
  Analyze any completed parts before retrying, ask fresh consent for another spawn,
  and retain per-host source/target/dependency equality, approved pin, declared
  cache/runtime-write exceptions, disconnect completion and cleanup.
- [ ] **Step 9:** Complete the bounded fixture fault matrix, compare helper bytes
  again if any fix occurred, and rerun only checks justified by that fix. Task-note
  the exact reviewed commit/manifest/pilot verdict and remaining live gates.
  Complete hq-c6c847 only as reviewed workflow/preparation delivery after those
  gates pass; this unblocks its dependent original window task hq-f27918. Park
  hq-f27918 and parent for the operator's session closure/window, naming that live
  smoke/timer evidence is still owed there and final checks belong to original
  Task 9. Immediately before each closure request, including when hq-f27918 resumes
  after a wait, perform the fresh held version check described above. Unchanged:
  no repeats. Moved: repeat Steps 5–7 and recheck; rerun the pilot only if its helper/
  toolchain bytes changed. No closure request precedes that final check. Do not keep
  original Task 8 dependent on a bootstrap task that waits on its own live results,
  or claim the rollout done when only preparation is delivered.

## Live handoff after implementation approval and rehearsal

This section names later human gates; approving this plan does not execute them.
Ordinary Claude use remains allowed until the window. As the last action before
asking the operator to close sessions, the agent checks both hosts' versions using
held commands. Unchanged versions repeat nothing; movement repeats only Task 9
Steps 5–7 and the final check. Repeat the pilot only for changed helper/toolchain
bytes. The operator then closes every Claude/Codex session on both hosts, including
the current controller, and runs the single Zsh command. From bootstrap through
finish, use only the printed DISABLE_UPDATES=1 launches; avoid `cl` and `clw`.
The bootstrap obtains that invocation's desktop consent before any
mutation, quiesces both hosts, freezes inputs and passes all six dry runs before
familiar/dependency changes and the four target applies.

Until finish reports complete, keep Claude model/effort defaults unchanged in
both homes on both hosts; do not use `/model` or `/effort` to save new defaults.
Pick changes otherwise leave byte-gated recovery blocked for inspection.
On verified migration, resume only with the printed explicit command and human
personal Codex hook review; first prove the current controller's fresh row. If
surfaces are pending, the agent previews status, asks in the session and records
that answer for `restart-surfaces`; declining leaves it pending without rollback.
Run the exact full/short smokes, including both Codex homes' own TUI trust reviews.
Gather human verdicts through the session/TTY channel and record bound receipts;
permission prompts for SSH/systemctl remain human. Then finish timers and scheduled
reconciliation, verify original Task 8 live evidence and perform original Task 9 final checks.
Keep backups/worktree through original Task 9. Full recovery remains an operator-run
closed-harness command, with new desktop consent for its restarts. On unexpected
version drift after bootstrap, use it to restore native state/timers without stale
Claude evidence blocking rollback, then repeat Steps 5–7 and the final held check
before a new window. No in-window re-probe/continuation path is added.

## Self-review / coverage before handing this plan back

- [x] Map approved requirements: durable records/consent → Task 1; transport,
  lifecycle/toolchain/environment → Task 2; pick-safe preparation/quiescence/abort →
  Task 3; application/sync → Task 4; actual-state/offline recovery → Task 5;
  surface retry → Task 6; safe resume/trust/receipts/timers → Task 7;
  mode isolation/spawn/disconnect pilot → Tasks 8–9; delivered-main tests and
  original-window handoff → Task 9; independent dots/lore → their owning tasks.
- [x] Check signatures/data schemas, step granularity and all five Review Focus
  cases. Each mutation operation lands in its consuming task's RED→GREEN cycle.
- [x] Distinguish original reviewed images from effective installer-produced window
  images, pinned system toolchain from login PATH, explicit cancel from pipe loss,
  scratch application writes from declared host-cache/runtime effects, and
  worktree tests from delivered-main tests. All six authoritative installer-byte
  dry runs precede merge; structural drift names the existing image-review process;
  bootstrap-to-finish held launches plus reviewed re-probe replace a permanent
  2.1.304 pin. Ordinary pre-window use is unrestricted; final held checks repeat
  only Steps 5–7 for version movement, with pilot reuse unless helper/toolchain
  bytes change. Handoffs name habitual unheld launchers `cl` and `clw`.
  Hold breach cannot strand rollback behind stale evidence. Handoffs freeze picks
  and preserve updates disabled through finish. No live results are implied.
- [x] Keith approved the complete plan after round 5 acceptance; the Minor probe
  ordering is incorporated. Task 1 starts in a fresh subagent-driven session.

## Amendment 2026-10-21: familiar task-record drift (after Task 9 Step 7)

Implements the spec amendment of the same date (revised after design review rounds 7–11;
rulings R61–R64). One corrective change on the delivered tool, then redelivery:

1. Pins (as the spec's amendment defines, including `core.hooksPath=/dev/null` on every
   mutating familiar git call and the T0 `diff-tree` under the temporary object environment):
   add T0 `f492e3437577c4b79db379e4cc1fb6771f35b3bb` beside PRE and tip (tool constants
   and the manifest's pins). One fixed-options helper for every `merge-tree`/`merge` call,
   with read-only `merge-tree` writing to a temporary object directory.
2. One shared predicate `tasks_only(x, y)` in `familiar.py` (plumbing only, as the spec
   defines), plus base eligibility (clean tree incl. untracked outside `tasks/`, `merge-tree B
   tip` exit 0 and equal to T0 outside `tasks/`).
3. Readiness on both hosts: recompute and compare T0, base rule per host, Europa equal to or an
   ancestor of Titan; report B and its proof.
4. `run`: derive B on Titan after the second strict no-live; new read-only `familiar-sync`
   host operation (one child per poll; deadline `SYNC_SECONDS + CHILD_SECONDS + 60`) waits for Europa HEAD = B
   before either `snapshot-refresh`; `snapshot-refresh` checks HEAD = B without waiting; the
   pre-merge gate rechecks; the mark records B; `familiar-merge` takes B, rechecks, merges with
   the fixed options and proves M (parents, tree, T0).
5. After the mark: tasks-only-descendant source proofs (install sync, `familiar-verify` in run,
   restart-surfaces and finish, dependency-restore sync), Europa not ahead of or diverged from
   Titan's observed HEAD; finish records the observed HEAD.
6. Restoration/recovery (as the spec's amendment defines: temporary-index working-tree
   equality, `index.lock` refusal, index rebuild before `read-tree -m -u`/`update-ref`, the
   abandoned-R and R′ rules, tolerant final proof): first-parent walk to find M and R; classes per the spec; the plumbing
   restore (`commit-tree -p P`, durable R record, `read-tree -m -u P R`, `update-ref HEAD R
   P`) with its rerun rules; `at-base` records B; `_ended` only for `merged`/`reverted`; T0
   proof before reconciliation promotes; a window without a recorded base is refused. Every
   site the round-7 review listed moves from PRE to the recorded B; host operations re-run the
   base rule on the payload's B.
7. Pilot: each host's clone at its own eligible HEAD, recorded per clone.
8. Handoffs, status and runbook: Europa familiar commits forbidden; Titan commits before the
   merge abort, after it are tolerated.
9. Tests, RED first: the round-7 implementer notes plus round 8's: a post-M tasks commit
   touching a path the tip changed (restore succeeds, no conflict); `pull.twohead=resolve` and
   `branch.<b>.mergeOptions` set in the fixture config do not change the merge; a conflicted
   `merge-tree` refuses at prepare; `familiar-sync` timeout is a clean pre-merge abort; the
   plumbing restore's crash points (after `commit-tree`, after `read-tree`, after
   `update-ref`); a stat-dirty live index, an index holding another tree and a stale
   `index.lock` during the restore; an abandoned R after a tolerated Titan tasks commit, and a crash after `read-tree`
   followed by a Titan tasks commit both by pathspec and through the live index; a crash after
   `read-tree`, then a tracker write that defers (modified tracked record, HEAD = P), and
   recovery completes carrying the record; two outside-`tasks/` entries above M refused;
   hooks (`post-merge`, `reference-transaction`) not run; `tasks/` absent in B or P; an
   octopus merge in the tip's history; a Europa-local commit after the mark detected; `at-base` recovery does not
   end the cutover; the unchanged B = PRE fixtures as the baseline.
10. Mandatory suite, scoped review, cherry-pick redelivery with the delivered tree's
    `just test`, Europa helper-byte check, restaged input generation (helper digests and the
    T0 pin), resume Task 9 Step 7, and rerun the pilot.
