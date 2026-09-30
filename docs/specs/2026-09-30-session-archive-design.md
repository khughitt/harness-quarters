# Session archive: daily capture, verified prune

Status: revised after review round 1 (codex); draft for review. Task: `tack-401088` (goal `tack-1a3278`: keep agent session
stores bounded without losing what obs can re-parse). Policy: the Decision section of
`docs/notes/2026-09-29-session-store-retention-brief.md`, adopted 2026-09-30.

## 1. Problem

Claude Code and Codex transcripts are the only raw input obs can re-parse. Codex never
ages them: `~/.codex/sessions` alone is 22G and grows by 3–7G a month. Claude Code
deletes them at `cleanupPeriodDays`, which is now 90 in both Claude homes. That number
buys time; it does not preserve anything. The adopted policy is to archive, then prune.
A daily capture copies every transcript to a backup disk. A monthly prune deletes a
transcript from the live store only after verifying three things: it has been inactive
for 30 days, the archive holds exactly its current bytes, and obs has indexed exactly
that version.

## 2. Goals and non-goals

Goals:

- Every transcript in the five sources below reaches the archive within a day of its
  last change.
- A live transcript is deleted only when all the prune conditions in §3.4 hold. Any
  failure keeps the original and makes the run fail visibly.
- The archive mirrors each source's directory tree, so obs can re-read it under the
  paths it first indexed (`obs-de84cb`).
- On a host without an archive configuration, the job refuses to run.

Non-goals:

- Hosts other than titan. The job is host-gated (§3.1); io is out of scope.
- Restoring into a live harness directory. Restores go to scratch copies. Re-reading
  archives is obs's job (`obs-de84cb`).
- Claude Code's other aging state (`file-history/`, `plans/`, caches). It is not
  re-parse input, and `cleanupPeriodDays` keeps aging it.
- Codex's non-session state (`packages/`, `logs_2.sqlite`, the app-server daemon). The
  superseded-release sweep is its own question under `tack-1a3278`.
- Compression. See §3.3.

## 3. Design

One tool, `tools/session-archive`, a Python script in this repository with two
subcommands, `capture` and `prune`, plus `status`. Two user systemd timers run it. The
decisions about which file may be pruned live in pure functions over plain records
(stat results, manifest rows, obs index-state rows, open-file sets). The shell around
them only gathers inputs and applies decisions. The tests exercise the core without a
filesystem (§5).

### 3.1 Host gate and configuration

The configuration is `~/.config/session-archive/config.toml`. It is host-local, lives
in no repository, and exists only on titan:

```toml
archive_root = "<a directory on the backup disk>"
```

Every subcommand refuses, exiting 2 with a message that names the missing piece, when:

- the config file is absent: "session-archive is not configured on this host";
- `archive_root` does not exist;
- `archive_root` lacks the marker file `.session-archive-root`.

The marker is written once, by hand, when the archive is set up. When the backup disk is
unmounted, the root or its marker is missing, so a run can never write the archive onto
the root filesystem.

A lock file (`flock` on `<archive_root>/.lock`) stops `capture` and `prune` from
overlapping. A run that finds the lock held exits 75 (`EX_TEMPFAIL`), which the unit
treats as a failure.

### 3.2 Sources

| Source name | Live root | Unit of pruning | Pruned |
|---|---|---|---|
| `claude` | `~/.claude/projects` | a session: `<id>.jsonl` plus the `<id>/` directory beside it (`subagents/`, `tool-results/`) | yes |
| `claude-work` | `~/.claude-work/projects` | the same | yes |
| `codex` | `~/.codex/sessions` | a rollout file, removed through `codex delete --force <thread id>` | yes |
| `codex-archived` | `~/.codex/archived_sessions` | the same | deferred |
| `codex-work` | `~/.codex-work/sessions` | the same, with `CODEX_HOME` set to `~/.codex-work` | deferred |

The source list is a constant in the tool. The config cannot extend it, and a missing
source root fails the run: every source listed here exists on titan.

Capture covers all five sources. Prune covers only the sources obs indexes today. obs
reads neither `archived_sessions` (594 rollouts, 1.6G) nor `~/.codex-work/sessions`
(711M), so no file there can pass condition 3 of §3.4. Their pruning is deferred to
`obs-914269`, which indexes both under each rollout's thread identity; prune skips
those sources until the tool's source table marks them pruned. The probe for
`codex delete --force` on a thread in `archived_sessions/` has already passed (in a
throwaway `CODEX_HOME`: it removed both the file and the row), so enabling them later
is a table change.

### 3.3 Capture (daily)

The archive layout is `<archive_root>/<source name>/<path relative to the live root>`,
together with a manifest, `<archive_root>/manifest.sqlite`. The manifest has one row
per archived file: source, relative path, size, `mtime_ns`, sha256 and `captured_at`.

For each regular file under each source root:

1. Skip it only when the manifest has a row with the same size and `mtime_ns` **and**
   the archived copy exists with that size and `mtime_ns` (capture sets the copy's
   mtime to the source's). A copy that is missing or differs in either is recaptured and
   counted as `repaired`. The daily run does not rehash the archive. Damage that leaves
   size and mtime intact is caught by prune's read-back (§3.4), which recaptures
   from the live file.
2. Otherwise copy it to a temporary name in its archive directory, hashing while
   copying, and `fsync` the copy.
3. Stat the source again. If its size or `mtime_ns` changed during the copy, drop the
   temporary file and count the file as `busy`; the next run captures it.
4. Rename the copy into place, `fsync` the directory, and upsert the manifest row.

A newer version replaces the archived one: transcripts are append-only, so the latest
version contains the earlier ones. The archive never deletes a file because its source
disappeared. Claude's own cleanup and `codex delete` shrink the live store, not the
archive.

Output is one JSON line per run with counts per source: `scanned`, `copied`,
`repaired`, `unchanged`, `busy`, `failed`. Any `failed` count makes the exit code 1.

Rejected alternative: monthly tarballs. The review permitted compression but did not
require it. An uncompressed mirror is what `obs-de84cb` can alias to the original roots
without unpacking anything, and its size does not justify compression: the whole store
is about 25G today, growing about 5G a month, against about 2T free. Compression can be
added later as a separate step without changing the prune gate.

### 3.4 Prune (monthly, 1st of the month)

For each pruning unit (§3.2), prune decides using these inputs:

- the live stat of every file in the unit;
- the manifest rows for those files;
- a fresh sha256 of every live file, and of every archived copy read back from the
  archive disk;
- obs's per-file index state, from `obs index-state --json` (`obs-0bc168`);
- the set of files any process holds open, from `/proc/*/fd`.

A unit is eligible only when every file in it satisfies all of the following:

1. **Inactive:** its `mtime` is more than 30 days before the run.
2. **Captured exactly:** a manifest row exists with the live size and `mtime_ns`. The
   sha256 of the live file, of the archived copy as read back now, and of the manifest
   row are equal.
3. **Indexed exactly** (for files obs indexes, i.e. the ones `obs index-state` lists):
   obs's size and `mtime_ms` match the live file; `byte_offset` equals the size, or
   obs has `partial_tail` set and the bytes after `byte_offset` hold no newline (only
   the unterminated last line is unread); the schema is current; and
   `missing_since_ms` is null. A transcript file obs does not list at all fails this
   condition. Tool results and other non-transcript files are not listed by design and
   need only condition 2.
4. **Closed:** no process holds it open.

These checks are a pre-check only. Every one is a snapshot, and the archive lock
excludes only other archive runs. A session could resume and append between the check
and the deletion. The deletion protocols below close that window: a unit is removed
only after its content has been frozen, meaning no writer can reach it any more, and
verified again.

#### 3.4.1 Deleting a Claude unit

Claude Code has no writer lock, so prune takes the unit out of reach by path:

1. **Quarantine.** Rename the unit's files (`<id>.jsonl` and the `<id>/` directory) into
   `<harness home>/session-archive-quarantine/<run id>/`, on the same filesystem, so
   each rename is atomic. From here on, nothing can open these inodes through the paths
   a harness knows.
2. **Settle.** Scan `/proc/*/fd` for any process holding one of the quarantined inodes,
   matched by device and inode because the path has changed. If one does, rename the
   unit back and record `kept:open`.
3. **Re-verify.** Once step 2 finds no holder, the content is frozen. No process has a
   descriptor, and none can get one: the old path is gone and the quarantine path is
   unknown to the harness. A writer that closed before step 2 has finished writing, so
   the hash sees its bytes. Condition 2 is checked again on the quarantined files. If
   the content changed after the pre-check, recapture it into the archive, rename the
   unit back, and record `kept:changed`.
4. **Recreation check.** If a writer appending by path recreated `<id>.jsonl` between
   steps 1 and 2, the original path now holds a fragment. Prune does not merge the two.
   It records `failed:recreated`, leaves the quarantined unit in place and reports both
   paths. The quarantined version is already archived, and the next capture archives the
   fragment. A person resolves it.
5. **Remove** the quarantined unit.

#### 3.4.2 Deleting a Codex unit

A live Codex writer holds an exclusive `flock` on
`<CODEX_HOME>/thread-writer-locks/<thread id>.lock` for the life of the session.
Probed in a throwaway `CODEX_HOME`: while that lock is held, `resume` fails with
"thread … already has an active writer", and `codex delete --force` fails with "failed
to delete session". So prune cannot hold the lock across the delete, but Codex's delete
itself excludes writers.

1. **Lock and link.** Take the thread's lock non-blocking; if it is held, record
   `kept:busy`. While holding it, re-run the pre-check for this unit and hard-link the
   rollout into `<CODEX_HOME>/session-archive-quarantine/<run id>/`. The link keeps the
   inode alive after Codex unlinks the path.
2. **Delete.** Release the lock and run `codex delete --force <thread id>`, where the
   thread id is the UUID in the rollout's filename. A failure, or a rollout path still
   present afterwards, is recorded as `failed:delete`, and the link is removed.
3. **Re-verify.** After a successful delete the inode is frozen. The path and the
   thread's row are gone, so resume cannot find it, and a writer that already had it
   open would have held the lock and made the delete fail. Condition 2 is checked again
   on the linked inode. If it changed, a resume ran in the seconds between steps 1 and
   2: recapture the linked content into the archive and record `failed:changed` with
   the thread id. The bytes are safe, but Codex no longer lists the thread. Restoring it
   goes into a scratch `CODEX_HOME`.
4. **Remove** the link.

A `codex-work` unit (once enabled) runs the same steps with
`CODEX_HOME=~/.codex-work`.

#### 3.4.3 Leftovers and reporting

A prune run refuses to start (exit 1, naming the directory) while any
`session-archive-quarantine/` it would use is non-empty. A leftover means an earlier run
died mid-protocol or recorded `failed:recreated`, and a person looks before anything else
is deleted.

Prune runs without writing anything unless it is given `--apply`. The dry run prints the
same JSON report, marking the units it would remove. Each ineligible unit gets the first
condition it failed, and the report gives totals per source for `eligible`, `pruned`,
`kept:<reason>` and `failed`. With `--apply`, any `failed` makes the exit code 1. If obs
is unavailable or the backup disk fails a read-back, the whole run stops before any
deletion.

Why monthly: pruning is the only destructive step, and batching it keeps the number of
runs anyone needs to read small. Capture carries the safety, so the prune cadence does
not affect loss. `cleanupPeriodDays` at 90 stays above the longest wait: 30 days of
inactivity plus a month to the next run is at most 62.

### 3.5 Status

`session-archive status` prints one JSON object with:

- the last capture's time and counts;
- the last prune's time, mode (dry run or apply) and counts;
- the archive size.

These come from a `runs` table in the manifest. `status` exits 1 when the last
successful capture is more than 48 hours old, or when the last prune run failed. That
gives anything polling health one command to call.

### 3.6 Units and links

`systemd/user/session-archive-capture.{service,timer}` runs daily at 04:00, after the
hourly obs index. `systemd/user/session-archive-prune.{service,timer}` runs on the 1st
at 05:00. Both timers are `Persistent=true`. Both services are `Type=oneshot` and call
the tool from `~/d/tack/tools` (the `%h/d/<checkout>` form obs-index uses). The unit
files are linked into `~/.config/systemd/user` through `links.toml` `[required]`.
Linking puts them on every host but enables them on none: enabling them is a
titan-only rollout step (§4). A unit started on a host without the config fails on the
host gate, which is the intended refusal.

The prune service passes `--apply` only after the rollout's dry-run review (§4).

### 3.7 Dependencies

- **Capture** depends on nothing new.
- **Prune** depends on `obs-0bc168` for obs's per-file index state. Rejected
  alternative: reading obs's `index.sqlite` directly, which would tie this job to obs's
  internal schema.
- **The first `prune --apply`** depends on `obs-de84cb`, the archive re-read
  acceptance check. Rows that obs keeps for a pruned file prove only that the metadata
  survived. The re-read proves the archive can rebuild it. Capture and the dry run do
  not wait for it.
- **Pruning `codex-archived` and `codex-work`** depends on `obs-914269` (§3.2).

## 4. Rollout on titan

1. Create the archive root on the backup disk, write the marker file and the host
   config, then run `capture` by hand. The first run copies about 25G. Read its report
   and `status`.
2. Link the units and enable the capture timer. After two scheduled runs, confirm
   `status` shows them.
3. When `obs-0bc168` lands, run `prune` as a dry run by hand. Review the report with the
   user: which units, how many, and the reason for each unit kept.
4. **Gate:** `obs-de84cb`'s acceptance check has passed against this archive. An
   archived month is re-read into the existing index with no duplicate sessions and no
   live file marked missing. Until then, prune stays a dry run.
5. On approval, run `prune --apply` once by hand. Check that obs still counts the
   pruned files, as missing with their rows kept, and that `codex resume --all` no
   longer lists the deleted threads. Then switch the prune unit to `--apply` and enable
   its timer.

Rollback: disable both timers. The archive is additive, so nothing needs restoring. A
thread that was pruned wrongly is restored from the archive into a scratch
`CODEX_HOME`, never into the live one.

## 5. Testing

- **Pure core:** eligibility over constructed records, with one case per condition in
  §3.4 and per unit shape (a Claude session with subagents and tool results, a Codex
  rollout). Also the capture decisions: skip, copy, busy.
- **Capture integration:** temporary source roots and archive root. Cover the first
  copy, the unchanged skip, a file appended between runs, a file changed during the
  copy (through an injected stat), and a source file removed (the archive keeps it).
- **Host gate:** no config, a missing root, and a missing marker, each exiting 2 with
  its message.
- **Capture repair:** an archived copy deleted, and one truncated, after its manifest
  row was written. The next capture recaptures both and counts them `repaired`.
- **Prune integration:** a temporary Claude root, and a stub `codex` on `PATH`. The stub
  records its arguments and, like the real one, refuses while the thread's writer lock
  is held; otherwise it unlinks the rollout, or fails. Cover the dry run writing
  nothing, `--apply` removing only eligible units, a `codex delete` failure recorded
  with the rollout kept, and an obs-state mismatch kept with its reason.
- **Deletion window** (§3.4.1–3.4.2), through injected hooks between protocol steps:
  - a Claude file appended after the pre-check and before quarantine (`kept:changed`,
    and the archive holds the appended version);
  - a Claude file held open across the settle scan (`kept:open`, renamed back);
  - `<id>.jsonl` recreated at its original path after quarantine (`failed:recreated`,
    both kept);
  - a Codex thread lock held at step 1 (`kept:busy`);
  - a Codex rollout appended between releasing the lock and the delete
    (`failed:changed`, and the archive holds the appended version);
  - a non-empty quarantine at start (the run refuses).
- **Probes already run** (throwaway `CODEX_HOME`, 2026-09-30): resume refused and delete
  refused while the writer lock is held, and `codex delete --force` on an
  `archived_sessions/` thread removed both file and row. The plan turns these into
  `session-archive probe-codex`, which runs them in a throwaway `CODEX_HOME` and records
  the Codex version they passed on in the manifest. `prune --apply` refuses to delete
  Codex units when the installed `codex --version` differs from the last passing one,
  until the probe is rerun. A Codex upgrade that changes lock or delete behavior is
  caught before it matters.

Everything runs under `just test`, which is this repository's suite.

## 6. Open questions

None blocking. Two assumptions the round 1 review accepted:

1. **Location.** The tool and its units live in tack. The goal and the harness store
   knowledge live here too. Rejected: ops `bin/`, which is shared tooling for work
   across projects, and dotfiles, which is the mindful-backup precedent but holds host
   configuration rather than harness logic.
2. **Archive format.** An uncompressed mirror, not tarballs (§3.3).
