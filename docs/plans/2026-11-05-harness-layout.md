# Harness layout implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Group the four existing harness directories under `harnesses/` and
Ponytail configuration under `external/`, preserving current behavior and state.

**Architecture:** Make the moves and their active path updates as one coherent
change. Use existing capture/restore and home-link tools, with a small one-time
saved-key rewrite command, for a separately approved activation; no old-path aliases.

**Tech Stack:** Git, Python standard library, existing pytest/just test routes,
TOML/JSON manifests and existing shell launchers. No new dependencies.

**Spec:** `docs/specs/2026-11-05-harness-layout-design.md`, approved by the user
at hq commit `d1399577ffe0fd65feaaa4393332e4f8b3f26498`.
Controller task: hq-b77d0c. Plan status: proposed for user review.

## Global constraints

- Move `agy/`, `claude/`, `codex/`, `pi/` into `harnesses/`; move `ponytail/`
  into `external/`. Leave shared root directories, `local/`, native homes,
  session stores, third-party caches, and lore-owned skill sources in place.
- Do not create empty Crush/OpenCode directories, compatibility aliases, a
  general migration framework, or change runtime pins or Ponytail defaults.
- Move both Codex hook JSON files byte-for-byte; preserve home link names and
  `[hooks.state]` entries. Nobody synthesizes trust hashes.
- Carry main's unfiltered `agentMode: auto` as an uncommitted setting. Neither
  the tracked defaults nor the filter's ownership expands to include it.
- Preserve the filter's fail-closed behavior, agy adoption ownership checks,
  and turn-pause protection of the relocated wiring files.
- Implementation uses `.worktrees/hq-b77d0c`. No host pointer targets that tree.
  Main integration and home reconciliation require separate live approval.
- Honor the invoking checkout's validated `.tt.toml`: fresh focused RED→GREEN
  and `just check-hygiene`; no routine broad run, and no policy skip as a pass.
- All rehearsal subprocesses receive explicit allowlisted environments, fake
  credentials and temporary homes. Omit inherited `GIT_*`; set
  `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, and fixture author/
  committer identity. Assert both fixture Git root and Git-dir containment before
  its first write. Do not use real homes, models, paid APIs, or desktop captures.
- Historical notes, fixture source metadata and native home paths stay historical
  or native. Change current consumers, not every string containing a harness name.

## Review focus

Each condition has an assertion in Task 1's rehearsal or focused checks:

1. An unfiltered local setting accompanies filtered picks: preserve both, keep the
   former dirty at its new path, and stage neither private data nor model picks.
2. A second host receives the new checkout while its agy settings are detached:
   prove old-anchor refusal, repair only verified owned anchors, then preserve
   detached settings and relink. Include a newer repository mtime.
3. Saved records are absent, already migrated, mixed across files, malformed or
   contain both old/new keys: no-op when appropriate; reject ambiguity without
   overwriting data; make a bounded retry possible after partial replacement.
4. A harness saves during the transition or an anchor belongs elsewhere: refuse
   continuation; keep snapshots and ask for a fresh quiescent window.
5. Ignored mod output or a unique untracked file remains under an old root:
   account for each entry; preserve unique bytes and prove old-root absence.

## Setup and execution evidence

Reuse the hydrated, locked worktree; `just setup` already ran. Before code work,
recheck the approved spec, current Git state, claim and test policy. Record the
focused baseline with test counts using the existing-test commands below,
excluding the not-yet-created layout test module. Broad baseline is deliberately
omitted under policy-off. Planning itself runs no runtime tests.

After plan approval, create the execution workspace at
`$WORK_ROOT/hq/hq-b77d0c/plans/harness-layout/`, owned by the open controller.
Record creation immediately and use lore's explicit-path plan helpers. Carry the
five round-1 spec dispositions from the task into its ledger, preserving `Why:`,
`Cost:` and both revision references. There are no deferred spec minors.

Inline execution is the author's choice: these edits share a manifest/consumer
boundary and must land together. Run one final independent whole-branch review
after Task 1, including the migration rehearsal and runbook. Before that review,
merge any advanced main into this branch, resolve conflicts and rerun affected
focused checks; never rebase away ledger revisions. Task 2 operates only on an
accepted build with no unreviewed runtime changes; it needs an operator self-check,
not another pre-invocation reviewer. Apply the repository's corrective-review caps.

## File inventory

| Files | Responsibility |
| --- | --- |
| Entire `agy/`, `claude/`, `codex/`, `pi/`, `ponytail/` trees | Move complete tracked contents, retaining modes and byte-identical files unless a current reference needs changing |
| `links.toml`, `harnesses.toml`, `.gitattributes`, `.gitignore`, `.ops-check.toml`, `justfile` | New declared destinations, exact filter globs, ignores, existing allowances and installer/mod recipe paths |
| `.githooks/codex-trust`, `.githooks/live-picks` | Relocated config name and agy anchor constants |
| `.githooks/harness-state-clean`, `.githooks/harness-state-refresh`, `.githooks/harness_state.py` | Update current path examples/documentation where needed, preserving behavior |
| `harnesses/agy/hook`, `harnesses/agy/hooks.json` | Root-depth calculation, current usage text and invoked adapter paths |
| `harnesses/pi/bin/pi`, moved probe entry points | Current diagnostics/comments; preserve launcher-relative package lookup and native session paths |
| `facts/capabilities.toml` | Relocate the 21 current `probe` fields identified through `tools/harness-facts list` |
| `tools/turn_pause/hook.py` | Relocate three tracked `WIRING` entries; retain the private work entry and home names |
| `tools/relay_cutover_bootstrap/inputs.py` | Relocate the three tracked checkout targets; keep private and historical source-image paths distinct |
| Existing test modules named below | Update fixture trees, paths and contract assertions; do not edit frozen evidence metadata |
| `tools/harness-layout-picks` (new) | Only the finite saved-record key transformation; no merge, capture, linking or service control |
| `tools/test_harness_layout.py` (new) | End-to-end isolated transition and rejection tests, including rollback |
| `README.md`, `AGENTS.md`, `docs/runbooks/adding-a-harness.md`, `docs/runbooks/relay-runtime.md` | Current layout and operator instructions |
| `docs/runbooks/harness-layout.md` (new) | Exact initiating-host, post-sync adoption and rollback commands with preconditions |

Check the rest of the tree for joined path expressions as well as literal strings.
Leave `docs/runbooks/relay-cutover.md`, dated decisions, session-store fixtures,
turn-pause captured payloads and historical fact notes unchanged unless a field is
demonstrably consumed as a current file path. Record each such distinction.

### Task 1: Move the directories and rehearse state-preserving activation

**Files:** All files in the inventory above.

**Interfaces:**
- Consumes: the approved layout, existing `live-picks capture|sync|restore`,
  `codex-trust capture|sync|restore`, `just link --apply`, `just link-check`,
  and their current ownership/locking contracts.
- Produces: the relocated checkout, unchanged Codex hook bytes, a tested runbook,
  and `tools/harness-layout-picks --root PATH --direction forward|reverse [--apply]`.
  Preview is read-only; success exits 0, invalid input exits nonzero. Output lists
  record paths and changed key names, never saved values.
- The small command's pure function is
  `remap_record(record: dict, moves: dict[str, str]) -> dict`.
  Its CLI validates all three files before writing any, under the existing
  `local/harness-state.lock`; uses atomic replacement for each changed file;
  refuses symlink record files and roots that are not the explicit main checkout.
  It does not claim a multi-file transaction. After an interrupted replacement,
  rerun the same direction only after checking the retained snapshots and state.

- [ ] **Step 1: Add failing behavior checks using isolated fixtures.**
  Add these named tests to `tools/test_harness_layout.py`; shared fixture helpers
  build a minimal old main and a candidate tree from the current working files,
  including uncommitted new files, so tests do not accidentally exercise HEAD only.
  Reuse existing fake-owner registry/cleaning patterns from
  `tools/test_harness_links.py`, without using its old fixed directory assumptions.

  | Test | Required assertions |
  | --- | --- |
  | `test_declared_layout_and_filters` | The four manifest configs start with their exact `harnesses/<name>/` path; Ponytail link targets `external/ponytail/config.json`; filter check passes and no moved tracked root remains |
  | `test_record_rekey_roundtrip` | Forward maps only the four declared config keys; nested entry values and reset markers remain equal; reverse returns the original data |
  | `test_record_rekey_absent_and_repeated` | Missing files stay absent; a second same-direction apply writes nothing; mixed per-file old/new states converge |
  | `test_record_rekey_refuses_ambiguity` | Malformed/duplicate JSON keys, unknown config keys, old+new collision, non-object records or symlink files fail before any file changes |
  | `test_record_rekey_checks_snapshot_before_replace` | A file changed between validation and replacement is refused, with its new bytes retained and prior replacements explicitly reported |
  | `test_initiating_host_transition` | Real fixture post-merge hooks see new record keys; model/effort/trust survive; `agentMode == "auto"` remains only an unstaged new-path diff; link-check passes |
  | `test_post_sync_detached_agy_transition` | Old anchors plus a regular settings file first cause refusal; verified-anchor repair and adoption preserve picks and unfiltered detached changes even when the repository file is newer |
  | `test_activation_refuses_unowned_or_changing_inputs` | A foreign anchor or simulated settings writer fails the runbook's preconditions before mutation; later detected changes stop further steps with evidence retained |
  | `test_ignored_contents_and_rollback` | Unique untracked bytes are carried; known disposable cache removal is explicit; old roots vanish; corrective rollback restores layout, records, links and carried settings without deleting task/review history |
  | `test_codex_hook_bytes_and_trust_unchanged` | Both hook files equal their old bytes; native link names and hook-state entries remain equal after transition |

  In the existing turn-pause tests, add/adjust the protected-path parameterization
  so a native write and a shell mutation naming each new tracked wiring path are
  refused, while the existing private/home protections remain covered. Repair any
  touched subprocess fixture to use explicit isolated environments before its RED run.

- [ ] **Step 2: Prove the relevant new assertions fail.**
  Run `just test-one tools/test_harness_layout.py -q` and the changed protected-path
  cases. Record actual failures/counts: old layout, missing key command and old
  protection entries are expected reasons; infrastructure errors are not RED evidence.

- [ ] **Step 3: Make the five moves and update current consumers together.**
  Use `git mv` for the tracked trees, then edit the inventory. Agy's hook root becomes
  `Path(__file__).resolve().parents[2]`. Prefix moved manifest paths/filter globs and
  live-picks anchors with `harnesses/`; change `codex-trust`'s `LIVE_NAME` likewise.
  Keep `local/*` paths and the linked Codex hook JSON bytes unchanged. Query facts
  with `tools/harness-facts list`, then edit only their active probe fields.
  Inspect rename/mode changes with `git diff --summary --find-renames`; executable
  launchers and hooks must retain their modes. Update the direct probe imports in
  `tools/test_subagent_write_probe.py` and `tools/test_successor_link_probe.py`.
  The new command's finite maps are:

  | Record | Forward key mappings |
  | --- | --- |
  | `local/live-picks.json` | `claude/settings.json` → `harnesses/claude/settings.json`; `codex/config.toml` → `harnesses/codex/config.toml` |
  | `local/live-picks-pi.json` | `pi/settings.json` → `harnesses/pi/settings.json` |
  | `local/live-picks-agy.json` | `agy/settings.json` → `harnesses/agy/settings.json` |

  Reverse swaps those mappings. Entries are opaque preserved data; existing
  live-picks validation runs before/after the transition. Accept only these old or
  new keys in their named files, and reject both forms coexisting even if equal.
  Validate every input before replacement, then compare bytes again immediately
  before each replacement. Preserve the existing file permissions. Quiescence is
  still required: the lock and comparison do not block arbitrary harness writers
  or another host. This command is justified by the four explicit key changes,
  not a reusable migration engine or new storage format.

- [ ] **Step 4: Write and rehearse the exact activation runbook.**
  Use the sequence below, expanding it into directly runnable commands and
  explicit checks in `docs/runbooks/harness-layout.md`. The tests must exercise
  those commands/operations, including real fixture merge hooks, not a replacement
  model of them. Keep transition helpers local to the test module; do not build an
  orchestration service. Use a fixed old-layout Git revision and candidate working
  files in fixture construction, recording the old revision in test evidence.

  1. Pin `BEFORE` (main) and `REVIEWED` (accepted branch revision), assert main is
     its ancestor, no staged edits or unrelated dirty paths, and a clean code
     worktree. Audit external/private path consumers without printing values.
     Establish an approved no-writer window on all hosts sharing these configs
     and records; do not stop services or sessions without that authorization.
     If the controller itself is a writer, use a reviewed operator handoff from
     a normal shell after the sessions exit, not an unattended background job.
  2. Create private, persistent snapshots under this task's declared `WORK_ROOT`
     storage: raw tracked config bytes, existing saved records and Codex trust,
     detached agy bytes, symlink targets, and each unique ignored/untracked item.
     Record presence/absence and hashes. Retain snapshots through verification
     and other-host adoption. Inventory each old directory; do not archive or
     delete everything indiscriminately.
  3. Under old paths, run `.githooks/codex-trust sync` and
     `.githooks/live-picks sync`; require successful exits, the old agy settings
     symlink, and preserved unfiltered values. Snapshot the resulting records
     again as a new version. Save `git diff --binary` for the four config paths
     separately from raw bytes. Require the known `agentMode` delta and explicitly
     account for any additional diff; abort on unexplained changes.
  4. With those verified backups and specific activation authority, clear only
     the carried unfiltered config diffs at the old paths using
     `git restore --source="$BEFORE" --worktree -- <the named dirty config paths>`.
     No stash, blanket checkout or unrelated edits. Recheck all guarded inputs
     and absence of writers before the incompatible-key interval.
  5. Run the accepted worktree's `tools/harness-layout-picks` by explicit path
     against main: preview, then forward apply. Immediately run
     `git merge --ff-only "$REVIEWED"` in main with normal hooks enabled.
     This ordering gives post-merge the new keys with the new manifest; no old
     live-picks call may run between rekey and merge. On merge failure, remain
     quiescent, inspect actual HEAD and record state, then use the pre-merge
     recovery below. Never infer hook success from Git's exit status alone.
  6. Reapply the preserved unfiltered patch with
     `git apply --check --directory=harnesses <patch>` followed by
     `git apply --directory=harnesses <patch>`. Require the patch to contain only
     the four mapped config paths, keep it unstaged, and verify its normalized
     content equals the old diff. A conflict stops activation; never replace a
     new tracked config wholesale with an old raw snapshot.
  7. Move each needed ignored/untracked entry to its mapped path with collision
     checks and hash verification; discard only entries proved regenerable and
     recorded as such. Do not recursively remove old roots. From main run
     `just link --apply`, `.githooks/codex-trust sync`, and
     `.githooks/live-picks sync`, checking each exit and stderr. Require
     `just link-check`, `tools/harness-facts check`,
     `python3 .githooks/harness_state.py check`, and `just check-hygiene` to pass.
     Compare selections/trust/hook bytes, unchanged private paths, and the
     unstaged carried diff against the snapshots. Verify all five old roots are
     absent. Only then release the no-writer window on this host.

  **Post-sync host adoption:** require the same approved no-writer window,
  input snapshots and current-revision checks. Validate and forward-rekey records
  only where they still use old keys. If agy is detached, do not call either
  adoption route while anchors are stale. Verify both old anchor symlinks are
  owned, then atomically repoint only those anchors to the new main targets.
  Agy's existing adoption chooses its base using mtimes: a newer synced repo
  file can discard unfiltered detached edits. Compare the detached file's cleaned
  content with the saved old tracked base and the new tracked config; explicitly
  carry its conflict-free unfiltered delta to the new config before sync. Preserve
  the original detached bytes, then align the detached working copy's unfiltered
  content with that verified merged config, keeping its live fields. Both possible
  mtime-selected bases must now have the same unfiltered content, so adoption
  cannot discard either the detached edit or a new tracked setting. If that
  comparison cannot be established, stop and retain both versions. Call
  `live-picks sync`, verify every carried value, then reconcile all links and
  repeat the same verification. No timestamp manipulation, first-run bypass,
  permissive anchor rule, or blind copy of detached bytes onto new tracked content.

  **Recovery:** before main advances, reverse only records actually rekeyed,
  reapply the original unfiltered patch at old paths, verify selections and links,
  and stop. After main advances, keep the window closed and use an approved
  corrective commit restoring the pre-move runtime paths/manifests/current docs
  from `BEFORE`; preserve task records, specs, plan and review history. Prepare the
  exact path list before activation. Preserve current deltas first, reverse-rekey
  for the restored old manifest before its state hooks run, move retained files
  back with conflict checks, reapply carried changes and reconcile old links.
  Rehearse both recovery points. Never reset main or delete newer evidence.

- [ ] **Step 5: Run focused verification and commit the coherent result.**
  Use the commands below. New tests must pass; no expected failure is waved through.
  Existing failures get a specific disposition. Record commands, tested revision,
  counts and skipped scope in the ledger. Run `tasks check`, `git diff --check`,
  `tools/harness-facts check` and `just check-hygiene`, then commit the moves,
  consumers, tests and runbook with a conventional `refactor:` message.
  Stage explicit paths, including renamed source deletions, and never `local/`.

**Focused commands** (run from the task worktree):

```sh
just test-one tools/test_harness_layout.py -q
just test-one .githooks/test_harness_manifest.py .githooks/test_harness_state_clean.py .githooks/test_codex_trust.py .githooks/test_live_picks.py .githooks/test_harness_state_refresh.py .githooks/test_pre_commit.py .githooks/test_pre_commit_facts.py -q
just test-one tools/test_harness_links.py tools/test_harness_facts.py tools/test_agy_hooks.py tools/test_pi_launcher.py tools/test_pi_extension_probe.py tools/test_pi_rpc_probe.py tools/test_worker_defaults.py -q
just test-one tools/test_subagent_write_probe.py tools/test_successor_link_probe.py -q
just test-one tools/test_capture_notice_wiring.py tools/test_claim_guard_wiring.py tools/test_relay_wiring.py tools/test_turn_pause_wiring.py -q
just test-one tools/test_turn_pause_hook.py -k protected -q
just test-one tools/test_relay_cutover_bootstrap.py tools/test_relay_cutover_transport.py tools/test_relay_cutover.py -q
```

The relay selection stays serial, including its signal test. Add a focused case
only when the audit finds another changed consumer; don't widen into the broad
suite. These are unit/fixture checks, not paid probe invocations. If a required
optional local integration cannot run, record its exact limit before review.

**Expected:** all affected focused checks and hygiene pass; isolated forward,
post-sync and rollback cases preserve data; the branch is reviewable and live
main remains unchanged. Final independent review covers this entire deliverable.

### Task 2: Activate the reviewed layout and account for adoption

**Files:** Main's reviewed runtime paths, host links and saved records; task notes
and the existing execution ledger. No new runner code in this operational step.

**Interfaces:** Consumes Task 1's accepted revision, tested runbook and preserved
Codex hook bytes. Produces a verified main layout and a discoverable adoption/
retention record. Requires explicit live activation approval with named hosts,
the no-writer window, exact frozen revision, commands, and conditional rollback.

- [ ] **Step 1: Prepare the concrete activation request.**
  After final review, freeze the exact merge revision and main base. Record the
  per-path preservation/disposal inventory, rollback path list, required host
  actions, snapshot destinations, test evidence and runbook revision. Resolve
  launchers on PATH. If main advances, reconcile and review affected code before
  requesting activation. Park for the user only when this package is ready.
- [ ] **Step 2: Execute the approved runbook in the agreed window.**
  Check that the deployed revision descends from the accepted build with no
  unreviewed runtime edits. Check current hashes/processes rather than reusing
  observations. The acting operator records exact commands, exits and assertions;
  no independent pre-invocation review. Stop on failed gates, use only the approved
  recovery, and retain evidence. An operator handoff stays tracked on this task.
- [ ] **Step 3: Verify one host end to end and document other-host adoption.**
  Use the runbook's checks, not a new paid model probe. One host/profile verifies
  shared rollout mechanics; any different configuration path gets its required
  check. Record which other hosts still need adoption and who performs it.
  Before releasing a shared no-writer window, verify each affected host is either
  adopted or kept quiescent under an explicit user agreement. Keep needed snapshots
  and an open owning task until all remaining adoption/cleanup work has an owner.
- [ ] **Step 4: Finish records and cleanup only after verified integration.**
  Record final focused/hygiene evidence, all rulings, remote evidence if any, pushes,
  surviving processes and other work. Before removal run `tt-report`, inspect all
  ignored files and host pointers, preserve the execution ledger/reports, and
  checkpoint the full retained set. Follow worktree unlock/removal rules. No push
  is part of this plan. Do not close away unfinished adoption or retained evidence.

**Expected:** the approved main layout works, private/uncommitted state survives,
home links converge, old roots are absent, and every remaining host or retained
item has an explicit open owner and next action. If activation is unapproved,
the reviewed build stays parked and main stays untouched.
