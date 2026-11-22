# Transcript archive and replica

Type: protocol, guide; document types 1. The archive command protocol and SQLite
manifest are currently unversioned; pruning requires obs readiness contract 2.
This covers capture, deletion gates and replica recovery. See [sessions](sessions.md)
for discovery and [capabilities](harness-capabilities.md) for observed store limits.

## Participants and configuration

The session-archive command reads live sources through tools/harness_stores/,
maintains a disk archive, and asks the configured obs command for pruning evidence.
User systemd timers are optional callers, not proof that a host is activated.

Configuration is .config/session-archive/config.toml under the executing home:

| Key | Meaning |
| --- | --- |
| archive_root | Existing archive directory with .session-archive-root marker |
| obs_command | Nonempty list of command strings; each element expands home syntax |
| uninspectable_ok | Optional list of process comm names whose open files may be uninspectable |
| replica_root | Optional replica directory, independently gated before replication |

Invalid types, missing keys, missing disk/marker and linked source roots refuse
rather than creating a substitute archive. Optional never-captured absent roots
are skipped explicitly; a required or previously captured source missing now is
an error. Agy capture includes the summaries database and two transcript JSONL
files, not all generation databases or spilled step outputs. Pi capture (source
`pi`, optional, never pruned) takes the `*.jsonl` files directly inside each
directory under ~/.pi/agent/sessions, the files pi lists; a symlinked cwd directory
is not followed. pi appends to a session file and rewrites one only to migrate an
older format on open, which the archive keeps as a diverged version. It does not
capture bash output pi spilled to a temporary file when it truncated a result, or
sessions pi wrote outside the default store.

## Capture exchange

1. Load configuration and source table; validate home/root ownership and source
   availability. Acquire the shared archive lock for capture/prune/promote/probe.
2. For each selected regular source, inspect its size/mtime and archive state.
   An intact recorded newest copy can be skipped; damaged storage is repaired.
3. Copy a stable version, comparing extension bytes with the mirror. Append-only
   extensions advance the mirror; divergence retains a separate version instead
   of overwriting the earlier bytes silently. SQLite sources are snapshotted.
4. Update manifest.sqlite and record a completed run/report. Partial failure is
   reported as failure; absence of an exception is not a backup verification.

The manifest keeps versions keyed by source/relpath/location with size, mtime_ns,
SHA-256 and captured_at. Location is mirror or a versions-relative path. Runs keep
run_id, kind, mode, start/finish, success and JSON report; codex_probe records the
passed-at timestamp for a tested binary version. These are archive bookkeeping,
not an authorization token to delete live data.

## Pruning exchange

`session-archive prune` reports; only its explicit --apply form deletes.
Deletion is a live destructive operation requiring its own approved rollout.

1. Require a usable archive, inspected open-file set and, for applied Codex
   pruning, a passing delete probe for the actual installed Codex version.
2. Discover each deletion unit and require every member to be inactive for more
   than 30 days, non-diverged and captured in the current mirror.
3. Read the mirror back and require the live, recorded and read-back hashes to
   agree. A transcript also needs complete, current obs contract-2 readiness:
   matching bytes/size/mtime, device/inode, harness and where applicable thread
   identity; no partial tail, conflict or not-ready reason.
4. Recheck held/open inodes and apply the harness-specific quarantine protocol,
   rechecking identity/stability at the deletion boundary. Only the inspected
   unit is eligible; a metadata match alone does not justify deleting a path.
5. Preserve/report refused units and leftovers. Leftover quarantine from an
   earlier run requires inspection before another applied prune.

The tools fail on uninspectable process/open-file evidence unless that process
name is explicitly permitted by configuration. An unavailable obs reader is not
permission to treat transcripts as disposable. `session-archive promote SOURCE
RELPATH` is an explicit choice of a diverged file's newest version as mirror.

## Replica exchange and restore

Replica operations require an existing .session-archive-replica marker and physical
disk resolution showing that replica and archive do not share a backing disk.
A second directory/partition on the same disk is insufficient. Unresolvable or
shared device ancestry refuses replication.

`session-archive replicate` waits for the shared archive lock within its bounded
replica wait, snapshots the manifest and copies/hard-links archived files into a
new dated generation. It verifies completeness before updating current. Only a
verified generation becomes current; the newest seven generations are retained.
Partial staging never becomes a successful replica. Replication holds the archive
lock while taking its consistent snapshot.

`session-archive verify-replica` checks current from scratch, including SQLite
integrity and recorded hashes. Status treats replication older than 48 hours and
verification older than 35 days as stale. Code support does not establish live
activation; inspect host configuration, timers and latest reports separately.

For a restore rehearsal, copy current into private scratch, write the archive
marker there and use a scratch config. After actual primary-disk replacement,
restore the verified generation onto the replacement, write its marker, check
status and capture again to collect live changes since that generation. Preserve
failed/old evidence until its owner has verified disposition.

## Commands and scheduling

```text
session-archive capture
session-archive prune [--apply]
session-archive status
session-archive promote SOURCE RELPATH
session-archive probe-codex
session-archive replicate
session-archive verify-replica
```

Capture is daily and prune monthly where configured user units are enabled.
Replication runs daily at 06:00 and verification on the 15th at 06:30. Confirm the
unit files and host configuration before enabling anything. Never reenable a timer
whose unit symlink is managed by home-links: the disable phase can remove that
link. Restore declared links, then enable with the required host authorization.

## Failure modes

Exit 2 is a host/configuration gate; exit 75 means lock held; failed work normally
exits 1. A report's actual outcome matters independently of systemd's start result.
A missing mount, symlinked source, changed inode, incomplete obs span, damaged
archive, unknown Codex deletion behavior or replica-disk collision is a refusal.
Stop and diagnose the named condition; do not loosen identity/hash checks or
create a fallback root. Tests/rehearsals use temporary synthetic stores, never
live transcripts or the only backup copy.
