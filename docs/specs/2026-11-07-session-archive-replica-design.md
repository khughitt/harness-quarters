# Session archive replica: a verified second copy on another physical drive

Status: revision 2 for review, 2026-11-08, addressing spec review round 1 (agy, on
`1a09a6e3`: three important and three minor findings). Task: hq-adfed6 (closeout ops-7b325c).
Builds on [the session archive design](2026-09-30-session-archive-design.md) ("the archive
design" below), whose invariants it keeps.

## 1. Goal and where each requirement came from

The user's words (2026-10-28): "store copies of /mnt/backup/agent-sessions on a second
drive (daily rsync?) in case of hard drive failures."

Added by the agents who filed and scoped the request (ops-7b325c, hq-adfed6), not by the
user: copy the manifest consistently with the bytes it describes, coordinate with the
archive lock rather than a clock delay, refuse absent or wrong mounts, never report an
incomplete copy as verified, keep the last verified copy across failures, report failures
observably, and run a periodic restore check in scratch.

The design keeps all of them, because each one answers how a hard-drive failure would
otherwise still lose data:

- A failing drive often dies under heavy reads, which is what a copy run is. A copy that a
  failure interrupts must leave a usable earlier copy, not a half-updated one.
- A copy taken while capture writes can pair a manifest with bytes it does not describe.
- An unmounted target turns a copy into writes on the root filesystem.
- A copy nobody has read back is a belief, not a backup.

The simplest route that meets those is still a small one: a daily copy, under the lock
capture already takes, into dated directories that share unchanged files by hard link.

## 2. Non-goals

- Off-site or network backup, encryption, compression.
- Any change to capture, prune eligibility or the archive layout.
- The historical import (hq-ef1cb3). The replica copies whatever the manifest describes,
  so an imported source is replicated with no change here.
- Restoring into a live harness home. Restores go to scratch or to a replacement archive
  disk (§3.7).
- Notifications beyond what capture has today (§3.6).

## 3. Design

Two new subcommands of `tools/session-archive`, sharing its configuration, host gate,
lock and manifest code: `replicate` and `verify-replica`. Neither takes an option.
`session-archive` is not in ops's `cli.toml` inventory, and subcommands without options
add no vocabulary, so the cli.toml-first rule does not apply.

### 3.1 Configuration and mount checks

One optional key in the host config `~/.config/session-archive/config.toml`:

```toml
replica_root = "<a directory on a different physical disk>"
```

`load_config` only parses the key: absent means `replica_root = None`, present must be a
string (otherwise exit 2, as for the other keys). It does not touch the replica directory,
so an unmounted replica disk never stops capture, prune or promote.

`replicate` and `verify-replica` then check the replica themselves and refuse, exiting 2
with a message naming the problem (the archive design's host-gate convention), when:

- `replica_root` is absent from the config: "no replica is configured on this host";
- the directory does not exist ("is the replica disk mounted?");
- it lacks the marker file `.session-archive-replica`, written once by hand at setup;
- it is on the same physical disk as `archive_root`.

The marker does for the replica what `.session-archive-root` does for the archive: when the
disk is unmounted, the marker is missing, so a run never writes onto the root filesystem.

**Same physical disk.** `st_dev` alone is not enough: two partitions of one disk have
different `st_dev`. Each root's `st_dev` resolves through `/sys/dev/block/<major>:<minor>`
to the set of whole disks under it: a partition resolves to its parent disk; a device-mapper
or md device resolves recursively through `slaves/`. The run refuses when the two sets
intersect, or when either set is empty or cannot be read. A tmpfs or other virtual
filesystem (major 0, no sysfs entry) resolves to the empty set and is refused. On the
primary host today, the archive is on `sdc` and the candidate replica on `sdb`.

The check is two parts so tests can reach both. `disks_of(path, sysfs_root)` is a pure
function of a path's `st_dev` and a sysfs tree; its unit tests build fake sysfs trees. The
replica commands receive the resolver as a parameter; the CLI passes the real one, held
as a module attribute in `cli.py`. Temporary fixture roots share one filesystem, so the
real resolver correctly refuses them; the CLI fixture route (§5) runs `cli.main` in
process with that attribute replaced by a resolver that gives each root its own disk.
No environment variable or option exposes the override.

**Live source roots.** `main()` checks the live source table (`check_sources`) before
every command today. `replicate` and `verify-replica` read only the archive and the
replica, so `main()` skips that check for them: a missing harness home must not stop a
backup of what is already archived.

Capture, prune and promote ignore `replica_root`. Status reports on it (§3.6).

### 3.2 Replica layout

```
<replica_root>/
  .session-archive-replica       marker (by hand)
  generations/
    20261108T060012.345678Z/     one verified generation
      manifest.sqlite            consistent snapshot of the archive manifest
      claude/…  codex/…  versions/…   every file that manifest describes, at its archive path
      receipt.json               what this generation is and how it was verified
    20261109T060008.012345Z/
    …
  current -> generations/20261109T060008.012345Z     the newest verified generation
```

A stamp is the run's UTC start to the microsecond, taken from a clock the core receives as
a parameter (as `capture_file` takes `now`). A stamp that already exists, as a generation
or a partial, fails the run rather than reusing the directory.

A generation is a complete, self-contained archive: copied to an empty disk with
`.session-archive-root` added, it is an archive root that `session-archive status` opens.
Files that did not change since the previous generation are hard links to it, so a
generation costs only the files that changed that day. An actively appended transcript is
copied whole each day it changes; the archive's 38 GB and an expected daily churn of
a few GB fit within the replica disk's 2.2 TiB free many times over.

Only verified generations sit under `generations/` with a final name. Work in progress
lives in `generations/<stamp>.partial/`.

### 3.3 replicate (daily)

Under the archive lock (§3.5), so no capture, prune or promote can write the archive
during the copy:

1. **Clear stale partials.** Remove every `generations/*.partial/`. A partial is never
   trusted or reused; it can only be the remains of an interrupted run.
2. **Snapshot the manifest** into `<stamp>.partial/manifest.sqlite` with SQLite's online
   backup API, then open the copy read-only and run `PRAGMA integrity_check`. The archive's
   journal mode is `delete`; the backup API gives a consistent database regardless of
   journal state, where a plain file copy could miss a hot journal. Read the rows, then
   close the connection, so SQLite leaves no sidecar file in the partial.
3. **Populate.** For every row of the snapshot (every mirror and `versions/` entry), at its
   archive path (`archived_file` in the archive code):
   - If the previous verified generation (`current`) has the same row in its own manifest
     (source, relpath, location, size, `mtime_ns`, sha256), and `lstat` of its file there
     shows a regular file with that size and `mtime_ns`, hard-link the file from `current`.
     That file was verified when its generation was made.
   - Otherwise copy it from the archive with a no-follow open, hashing while copying, set
     its mtime to the row's, and `fsync` it. The hash must equal the row's sha256 and the
     size the row's size.
4. **Check completeness.** Every snapshot row has a regular file of its recorded size and
   `mtime_ns` in the partial, and the partial holds no other file besides
   `manifest.sqlite`.
5. **Write `receipt.json`**: the archive root, the replica root, the whole disks each
   resolved to, `started_at` and `finished_at` (UTC, the manifest's format), the row count,
   bytes and files copied, bytes and files linked, and `verified: true`. `fsync` every new
   directory, then the receipt.
6. **Publish.** Rename `<stamp>.partial` to `<stamp>`, `fsync` `generations/`, then point
   `current` at it by creating a new symlink under a temporary name and renaming it over
   `current` (atomic), and `fsync` the replica root.
7. **Keep the newest seven generations**; remove older ones. Removing a generation removes
   names, and any file a kept generation still uses survives through its other links.
8. Record the run in the archive manifest's `runs` table as kind `replicate`, with the
   receipt as its report.

**Failure.** Any error before step 6 (a hash or size mismatch, a missing archive file, an
I/O error, the disk failing, an interruption) leaves `current` and every verified
generation untouched. The run exits 1, prints a JSON report naming the first failure, and
records a failed `replicate` run when the manifest is still writable. A mismatch between
an archive file and its manifest row means the primary archive is damaged; the report
names the file, and the next run fails the same way until a person looks. The previous
replica, which holds that file's verified bytes, stays as it is.

Rejected alternatives:

- **`rsync -a` in place, manifest last** (the user's suggestion as written). Each file is
  replaced atomically, but an interruption leaves the old manifest beside newer files: the
  mirror's extended transcripts no longer match their recorded hashes, so the copy that
  survives a failure is not a verified state. It also copies whatever happens to be in the
  archive directory rather than what the manifest describes, and needs its output parsed
  to know what changed.
- **`rsync --link-dest` generations.** It gives the same layout, but verification would
  still be a separate pass in Python over the manifest. Copying by manifest row hashes
  once and refuses as it goes.
- **Copying outside the lock** from a manifest snapshot. Capture replaces mirror files
  during the copy, so hashes would mismatch spuriously. The lock costs capture a few
  minutes' wait at most (§3.5).

### 3.4 verify-replica (monthly restore check)

A restore check that reads the replica alone, never a live harness home:

1. Under the archive lock, so `replicate` cannot rotate generations mid-check.
2. Copy `current/manifest.sqlite` into a scratch directory and open it there:
   `PRAGMA integrity_check`, and read every row. This proves the copied manifest opens by
   itself, without the replica disk's directory around it.
3. Read and hash every file the manifest describes in `current`, comparing its sha256 and
   size with the row. All of them, not a sample: at about 40 GB this is minutes of reads on
   the replica disk once a month, and a sample would miss isolated bit rot.
4. For every row whose `relpath` ends in `.jsonl` (mirror and `versions/` rows alike),
   split the file's bytes on newlines and decode each line with `json.loads`, counting
   lines that do not parse, including a line that is not valid UTF-8 (a multi-byte
   sequence cut at the end of the file). Transcripts may legitimately end with a partial
   line or hold lines a harness wrote malformed, so the count is reported, not a failure;
   a hash match already proves the bytes.
5. Record a `verify-replica` run in the archive manifest and print the JSON report. Any
   hash, size, missing-file or integrity failure exits 1.

### 3.5 Lock

`replicate` and `verify-replica` take the same `flock` on `<archive_root>/.lock` as capture,
prune, promote and probe-codex. Unlike them they wait for it, for up to two hours, so a
replica run that starts during a long prune does not fail. A run that still cannot get the
lock exits 75, as the others do. `archive_lock` gains a wait parameter; the existing callers
keep their non-blocking behaviour.

### 3.6 Schedule and failure reporting

- `systemd/user/session-archive-replicate.{service,timer}`: daily at 06:00 (capture runs at
  04:00, prune on the 1st at 05:00), `Persistent=true`, `Type=oneshot`, `Nice=10`,
  `IOSchedulingClass=idle`, calling the tool as the capture unit does.
- `systemd/user/session-archive-verify-replica.{service,timer}`: monthly on the 15th at
  06:30, `Persistent=true`, same service settings.
- Both units are linked through `links.toml` `[required]` like the existing ones, so they
  land on every host and are enabled on none until activation (§4).

`session-archive status` gains a `replica` object when `replica_root` is configured: the
current generation's stamp and receipt, the last `replicate` and `verify-replica` runs,
`ok`, and, when not ok, the reasons. Status exits 1 (unhealthy) when a replica is
configured and any of these holds:

- the replica directory or its marker is missing (the disk is unmounted), `current` is
  missing, or its `receipt.json` cannot be read;
- the receipt's `finished_at` is more than 48 hours old, the capture threshold. Age comes
  from the receipt on the replica disk, not from the `runs` table: a generation restored
  into a new archive carries a manifest snapshotted before its own run was recorded;
- the last `replicate` run in the manifest failed. This is immediate, as for prune: a
  failure such as a primary hash mismatch repeats every day until a person looks, so
  waiting out the 48 hours would only delay the signal. No `replicate` row at all (a
  restored archive) does not count against it;
- the last `verify-replica` run failed, or none has passed in the last 35 days.

Reading the replica never raises out of status: a missing or unreadable path becomes a
reason in the `replica` object, and the archive part of the report is printed as before.
Without `replica_root`, the report has no `replica` key and health is unchanged.

A failed run also leaves its unit failed in `systemctl --user --failed`. That is the same
reporting capture has today. Nothing pushes a notification; a desktop or phone alert on unit
failure would be a separate host change, and this design adds none.

### 3.7 Restore

Documented in the README beside the archive's own rollback:

- **Scratch check by hand:** copy `current/` (with `cp -a`, keeping hard links) into a
  scratch directory, add `.session-archive-root`, and point a scratch config at it;
  `status` opens it. `verify-replica` does the automatic version of this check.
- **After losing the archive disk:** mount the replacement, `cp -a <replica_root>/current/.
  <new archive root>/`, write `.session-archive-root`, then run `session-archive status` and
  a `capture`. Capture repairs nothing it does not need to: files present with their
  recorded size and mtime are skipped, and sessions changed since the generation are
  captured fresh from the live homes.

## 4. Activation on the primary host (prepared, each step approved when reached)

1. Create `<replica_root>` on the replica disk (proposed: a new `agent-sessions`
   directory at the top of the `sdb` mount), write `.session-archive-replica`, and add
   `replica_root` to the host config.
2. Run `session-archive replicate` by hand. The first run copies the whole archive, about
   40 GB. Read its report.
3. Run `session-archive verify-replica` by hand and read its report.
4. Link the new units with `just link --apply` from main, then enable both timers. After two
   scheduled replicate runs, confirm `status` shows them.

Rollback: disable both timers and remove `replica_root` from the config. The archive is
untouched by every step; whether to keep or delete the replica directory is the user's call.

## 5. Testing

All on temporary archive and replica roots built by the existing test helpers, with
subprocess environments built key by key and a fake sysfs for the disk check:

- Mount checks: missing key, missing directory, missing marker, the same disk (two
  partitions of one fake disk), a device-mapper replica over the archive's disk, a
  virtual filesystem with no sysfs entry, and an unreadable sysfs entry: each refuses with
  its message, and nothing is written. Through the real CLI in a subprocess, fixture
  roots on one filesystem exit 2 as the same disk.
- Boundaries: with a configured but missing replica directory, capture still runs; with a
  live source root missing, `replicate` and `verify-replica` still run while capture
  exits 2.
- First generation: every row's file present with its hash, `current` points at it, the
  receipt counts match, and the generation opens with `status` when given an archive marker.
- Second generation after a capture that appended to one transcript and added a version:
  unchanged files share an inode with the first generation, changed ones do not, and both
  generations verify.
- An archive file whose bytes no longer match its row: the run exits 1 naming it, no new
  generation appears, `current` is unchanged.
- Interruption: a failure injected between populate and publish leaves a partial and the
  old `current`; the next run removes the partial and publishes.
- Retention: after nine runs with an injected clock, seven generations remain, and the
  files of the oldest kept one still verify. A clock that repeats a stamp fails the run.
- Linking: a file in `current` whose size or mtime no longer matches its row is copied
  from the archive instead of linked.
- Lock: a held lock makes the run wait, then exit 75 when the wait expires (a short wait
  in the test).
- `verify-replica`: passes on a good generation; fails on a flipped byte, a truncated
  file, a missing file and a damaged manifest copy; reports unparseable JSONL lines,
  including a cut UTF-8 sequence at end of file and a `versions/` transcript, without
  failing.
- `status`: healthy with a fresh generation and a recent passing check; unhealthy, with a
  reason and the archive report intact, for each condition in §3.6 (unmounted replica,
  missing `current`, unreadable receipt, stale receipt, failed last replicate, failed or
  missing check); healthy on a restored archive with no `replicate` rows; no `replica`
  key when unconfigured.

Before the first live copy, the small fixture route runs end to end: `replicate`, then
`verify-replica`, then `status`, through `cli.main` in process on a fixture archive with
the resolver replaced (§3.1). The first live `replicate` (§4 step 2) is the first run of
the real resolver on real disks.

Test execution follows this checkout's policy: focused `just test-one` runs for the changed
behaviour and `just check-hygiene` before commits.

## 6. Calls made in this design (the agent's, open to change)

- Python subcommands of the existing tool, not rsync (§3.3).
- Seven daily generations kept.
- Replicate daily at 06:00; full restore check monthly on the 15th.
- No push notification on failure (§3.6).
- Replica directory proposed at the top of the second disk's mount; the exact path lives
  only in the host config.
