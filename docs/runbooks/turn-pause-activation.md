# Activating turn-pause reliability changes

Type: runbook. These steps require a separately approved live activation window.
Preparing or testing the branch does not authorize them.

## Preparation

Use the reviewed code revision and frozen design/plan named by the task. Confirm
focused correctness, mandatory hygiene, the full-buffer latency gate and final
whole-branch review. Account for all retained worktrees/evidence on the executing
host. Keep the controller task open until activation and evidence disposition.

The unreleased version-1 envelope requires `prompt_guards` with exactly `cron`
and `wakeups` lists. Legacy conversion initializes both empty while preserving
the complete active dictionary; end/idle clearing later captures fingerprints.
An earlier synthetic prototype-v1 envelope without that field is unsupported.
Recreate synthetic test data; never silently repair a live store. If any real
prototype-v1 activation is discovered, stop for a migration decision before
conversion or cutover. Guards remain private matching metadata, never public
history, and their hashes do not anonymize short prompt text.

Identify the real installed launcher and its registered main checkout before
handoff. Leave every shared launcher/config include pointing to main. Test the
worktree only by its explicit entry path and synthetic environment overrides.

## Approved operator window

1. Quiesce every old hook writer, across harness homes/profiles. The operator must
   keep them stopped throughout code and directory replacement; concurrent old
   hooks could overwrite a migrated record. A normal active session is not proof
   of quiescence. Stop if this cannot be established.
2. Locate the current state directory from its configured XDG state home (or its
   documented home default). Preserve its exact raw bytes and a hash manifest in
   task-owned persistent storage; record owner/host/path immediately. Do not
   mutate the only copy or use a temporary directory as canonical backup.
3. From the reviewed checkout run `tools/turn-pause-migrate --source SOURCE
   --destination FRESH_SIBLING_STAGE --to-version 1`, capturing stdout as a receipt
   outside both stores. Require exit0 and complete:true, inspect every input and
   output digest, and compare every active field (counters, old limits, pause,
   grace, workers, wakeups, pending tools and ownership). Source remains unchanged.
   Old history is unavailable; conversion creates no historical events.
4. While writers remain quiesced, integrate the approved branch into main and
   switch the current directory with the verified sibling stage. Keep an exact
   backup and a durable note for each intermediate path so interruption is
   recoverable. Ensure source/stage and their parent are on the same filesystem
   before relying on directory rename. Do not run old code against v1 state or
   new code against old state, and do not reset counters to avoid migration.
5. Recheck main's launcher resolution, storage modes and active snapshots before
   resuming. A changed default-limit digest can legitimately give old turns a
   limits-changed pause; a new genuine user prompt starts with new defaults.
   Verify one host/profile end-to-end and both distinct Claude/Codex hook paths
   under the approved window. Observe notification attempts separately from
   actual receipt. Preserve the run outputs/receipt on the task.

Paths in this runbook are placeholders resolved on the executing host, not shell
variables to evaluate from untrusted text. A failed conversion leaves identified
partial staging; preserve or explicitly dispose of it, then choose a fresh
destination. Never retry over it or weaken runtime version validation.

## Rollback

Quiesce writers again. After any new v1 writes, the original old-format backup is
stale: restoring it would lose current counters/history. Preserve the complete
current v1 store and its hashes, then use the reviewed converter with
`--to-version 0` into a fresh sibling stage. Compare all exported current fields
and retain every skipped ended-root envelope in the v1 backup. Capture/inspect
the receipt outside the stores. Only then switch code and active store together
while writers stay stopped. The export does not remove its source or history.

Before resuming, verify launcher, counters and ownership against that fresh
export. Keep raw stores, manifests and receipts owned by an open task until the
retained-item procedure verifies their disposition; a successful merge or a
rollback is not deletion permission. No service or timer is introduced here.
