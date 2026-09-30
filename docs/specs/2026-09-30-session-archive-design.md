# Session archive: daily capture, verified prune

Status: approved 2026-09-30 after review rounds 1–4 (codex, then the user). Task: `tack-401088` (goal `tack-1a3278`: keep agent session
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
obs_command = ["python3", "~/d/obs/obs.py"]   # obs is not on PATH; `--json index-state` is appended
uninspectable_ok = []                          # optional; see §3.4, open files
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

The archive layout is `<archive_root>/<source name>/<path relative to the live root>`
(the mirror), `<archive_root>/versions/` for versions that do not extend the mirrored
copy (below), and a manifest, `<archive_root>/manifest.sqlite`. The manifest has one
row per archived file version: source, relative path, where it is stored (`mirror`, or
its path under `versions/`), size, `mtime_ns`, sha256 and `captured_at`.

For each regular file under each source root:

1. Skip it only when the manifest has a row with the same size and `mtime_ns` **and**
   the archived copy exists with that size and `mtime_ns` (capture sets the copy's
   mtime to the source's). A copy that is missing or differs in either is recaptured and
   counted as `repaired`. The daily run does not rehash the archive. Damage that leaves
   size and mtime intact is caught by prune's read-back (§3.4), which recaptures
   from the live file.
2. Otherwise copy it to a temporary name in its archive directory, hashing while
   copying, and `fsync` the copy. When the manifest has a mirror row for this file, let
   N and D be that row's recorded size and sha256, and also take the digest of the
   source's first N bytes during the same pass. N and D come from the manifest, never
   from the mirrored file on disk, which may be damaged.
3. Stat the source again. If its size or `mtime_ns` changed during the copy, drop the
   temporary file and count the file as `busy`; the next run captures it.
4. **Extension check.** The new version replaces the mirrored copy only when it extends
   the recorded mirror version: its size is at least N, and its first-N-bytes digest
   equals D. The same test repairs a damaged mirror: a truncated or corrupted mirrored
   file does not change N or D, so an intact live file passes and rewrites the mirror.
   Otherwise the new version has been rewritten, truncated, or recreated as a
   fragment. It goes to
   `versions/<source name>/<relative path>@<captured_at>`, the mirror is left untouched,
   and the file is counted as `diverged`.
5. Rename the copy into place, `fsync` the directory, and write the manifest row.

A mirrored copy is only ever replaced by a version that contains the recorded mirror
version, and nothing else in the archive is ever replaced. Transcripts are
append-only, so `diverged` is rare and always worth a look. `status` lists each
diverged file.

**Reconciling a divergence.** A diverged file stays diverged until a person runs
`session-archive promote <source> <relative path>`. This makes the file's latest
captured version the mirror version. The old mirrored copy moves under `versions/`,
the manifest's mirror row changes, and nothing is deleted. Promote is for a transcript
that was truly rewritten. A recreated fragment (§3.4.2) is instead merged back into the
live file by hand. The merged file then extends the mirror, and the next capture
reconciles it on its own. The archive never deletes a file because its source
disappeared. Claude's own cleanup and `codex delete` shrink the live store, not the
archive.

Output is one JSON line per run with counts per source: `scanned`, `copied`,
`repaired`, `diverged`, `unchanged`, `busy`, `vanished`, `failed`. `vanished` counts a
file its harness deleted between the walk and the copy, which is not a failure. A
directory or entry capture cannot read is a failure: it is counted, named in the
report, and fails the run, never skipped silently. Any `failed` count makes the exit code 1.

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
- the set of files any process holds open, from `/proc/*/fd`. The scope is every process
  owned by this user, since transcript writers run as the user. A process that exits
  mid-scan, or a descriptor that closes mid-scan, is skipped. A same-user process
  whose descriptors cannot be read fails the inspection, and prune refuses to delete.
  The exceptions are processes whose `comm` the config lists in `uninspectable_ok`: a
  person names each one. On titan these are `(sd-pam)`, which is non-dumpable, and the
  `systemd` user manager, whose descriptors can be listed but not followed. A failed
  inspection is never read as "nothing is open".

A unit is eligible only when every file in it satisfies all of the following:

1. **Inactive:** its `mtime` is more than 30 days before the run.
2. **Captured exactly, in the mirror:** the manifest's mirror row for this file has the
   live size and `mtime_ns`. The sha256 of the live file, of the mirrored copy as read
   back now, and of that row are equal. A file whose latest version sits only under
   `versions/` fails this condition and is recorded as `kept:diverged`. obs re-reads
   the mirror (`obs-de84cb`), so a version kept only under `versions/` would not come
   back on a re-read. Re-reading versions can wait until something needs it.
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

#### 3.4.1 Quarantine rules

Both protocols below move or link a unit into
`<harness home>/session-archive-quarantine/<run id>/`, on the same filesystem as the
live root. Two rules govern everything that leaves the quarantine:

- **Restore never replaces.** Moving a unit back to its live path uses
  `renameat2(RENAME_NOREPLACE)`, called through `ctypes` because Python's `os.rename`
  replaces an existing target. This works for both files and directories, and titan is
  Linux. If the target exists, because a writer recreated the path meanwhile, the call
  fails with `EEXIST`. Both copies are kept, and the unit is recorded as
  `failed:recreated`.
- **Release only what is preserved.** A quarantined file or link is removed only when
  one of these holds:
  - (a) its inode is still reachable at its live path, so the quarantine entry is a
    second name for bytes Codex or Claude still holds;
  - (b) the archive holds its exact bytes, verified by reading the archived copy back
    and comparing sha256.

  When neither holds, prune recaptures the quarantined content (§3.3 decides between
  the mirror and `versions/`), verifies it by read-back, and only then removes the
  entry. If the recapture fails, the entry stays, and the leftover rule (§3.4.4) stops
  the next run.

#### 3.4.2 Deleting a Claude unit

Claude Code has no writer lock, so prune takes the unit out of reach by path:

1. **Quarantine.** Rename the unit's files (`<id>.jsonl` and the `<id>/` directory) into
   the quarantine. Each rename is atomic. From here on, nothing can open these inodes
   through the paths a harness knows.
2. **Settle.** Scan `/proc/*/fd` for any process holding one of the quarantined inodes,
   matched by device and inode because the path has changed. If one does, restore the
   unit and record `kept:open`, or `failed:recreated` if the restore meets a recreated
   path.
3. **Re-verify.** Once step 2 finds no holder, the content is frozen. No process has a
   descriptor, and none can get one: the old path is gone and the quarantine path is
   unknown to the harness. A writer that closed before step 2 has finished writing, so
   the hash sees its bytes. Condition 2 is checked again on the quarantined files. If
   the content changed after the pre-check, recapture it and verify the recapture,
   then restore the unit and record `kept:changed`, or `failed:recreated` if the
   restore meets a recreated path.
4. **Recreation check.** If `<id>.jsonl` or `<id>/` exists at its original path again,
   a writer appending by path recreated it after step 1, and it holds a fragment. Record
   `failed:recreated` and keep the quarantined unit for a person to merge. The next
   capture stores the fragment under `versions/`, because it does not extend the
   mirrored copy (§3.3), and the full transcript in the mirror stays as it is.
5. **Remove** the quarantined unit. The release rule holds through (b): step 3 verified
   the archive against the quarantined bytes.

#### 3.4.3 Deleting a Codex unit

A live Codex writer holds an exclusive `flock` on
`<CODEX_HOME>/thread-writer-locks/<thread id>.lock` for the life of the session.
Probed in a throwaway `CODEX_HOME`: while that lock is held, `resume` fails with
"thread … already has an active writer", and `codex delete --force` fails with "failed
to delete session". So prune cannot hold the lock across the delete, but Codex's delete
itself excludes writers.

1. **Lock and link.** Take the thread's lock non-blocking; if it is held, record
   `kept:busy`. While holding it, re-run the pre-check for this unit and hard-link the
   rollout into the quarantine. The link keeps the inode alive if Codex unlinks the
   path.
2. **Delete.** Release the lock and run `codex delete --force <thread id>`, where the
   thread id is the UUID in the rollout's filename, with a 120-second timeout. The
   delete has succeeded only when it exits 0 and the rollout path is gone. Anything else
   (a nonzero exit, a timeout, a kill, or the path still present) is `failed:delete`,
   and the link is handled by the release rule, never removed outright:
   - If the rollout path still resolves to the linked inode, (a) holds: remove the link.
   - Otherwise, the delete may have unlinked the rollout and then failed, and the link
     may hold the only copy of bytes a resume appended after step 1. The rule's
     recapture path applies before the link goes. The report names the thread, because
     Codex's own rows may be half-deleted.
3. **Freeze check** (after a successful delete). The protocol does not rely on how
   long `codex delete` holds the writer lock. Instead it re-inspects open files, as the
   Claude settle step does. The rollout's path is gone and the link is the only name
   left, so if no process holds the inode open, nothing can write to it.

   Codex writers keep their rollout open for as long as they run. This was observed on
   titan on 2026-09-30:
   - every process holding a thread writer lock had that thread's rollout open (12 of
     12, including the app-server daemon);
   - a live `codex exec` held both the lock and the rollout in 182 of 182 and 102 of
     102 samples.

   If a process holds the linked inode, the link stays in quarantine and the unit is
   recorded as `failed:writer-live-quarantined`. A person looks once the writer exits,
   and the leftover rule stops further prunes until then. If the inspection itself
   fails, the outcome is `failed:uninspectable-quarantined`.
4. **Re-verify.** Condition 2 is checked again on the frozen inode. If it changed, a
   resume ran between steps 1 and 2: the bytes are recaptured under the release rule,
   and the unit is recorded as `failed:changed` with the thread id. The bytes are safe,
   but Codex no longer lists the thread. Restoring it goes into a scratch
   `CODEX_HOME`.
5. **Remove** the link, under the release rule.

A `codex-work` unit (once enabled) runs the same steps with
`CODEX_HOME=~/.codex-work`.

#### 3.4.4 Leftovers and reporting

A prune run refuses to start (exit 1, naming the directory) while any
`session-archive-quarantine/` it would use is non-empty. A leftover means an earlier run
died mid-protocol, recorded `failed:recreated`, or could not release an entry under the
release rule. A person looks before anything else is deleted. `status` also exits 1
while a quarantine is non-empty.

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
- **Deletion window** (§3.4.2–3.4.3), through injected hooks between protocol steps:
  - a Claude file appended after the pre-check and before quarantine (`kept:changed`,
    and the mirror holds the appended version);
  - a Claude file held open across the settle scan (`kept:open`, restored);
  - `<id>.jsonl` recreated at its original path after quarantine (`failed:recreated`,
    both kept);
  - recreation combined with a holder at settle, and with a change at re-verify. In
    both, the no-replace restore fails, the recreated fragment is byte-for-byte
    unchanged, and the quarantined unit is still present (`failed:recreated`);
  - a capture run immediately after `failed:recreated`: the fragment lands under
    `versions/` (`diverged`), and the mirror copy keeps the full transcript's hash;
  - a Codex thread lock held at step 1 (`kept:busy`);
  - a Codex rollout appended between releasing the lock and the delete
    (`failed:changed`, and the archive holds the appended version);
  - a Codex rollout appended, then unlinked by a stub delete that exits nonzero:
    `failed:delete`, the appended bytes are recaptured before the link is removed, and
    a stub run where the recapture fails leaves the link in quarantine;
  - a stub delete that exits nonzero without unlinking: `failed:delete`, and the link
    is removed under rule (a) with the rollout untouched;
  - a non-empty quarantine at start (the run refuses).
- **Capture extension check:** an appended file replaces the mirror, while a truncated,
  rewritten or recreated file goes to `versions/` and leaves the mirror unchanged. A
  truncated or corrupted mirrored copy with an intact live file is repaired in the
  mirror itself: the mirror hash is restored and nothing lands under `versions/`.
- **Diverged files are not pruned:** a file aged past 30 days and indexed by obs, whose
  latest version is only under `versions/`, stays live (`kept:diverged`). After
  `promote`, the same file becomes eligible, and the previous mirror copy is still
  present under `versions/`.
- **Probes already run** (throwaway `CODEX_HOME`, 2026-09-30):
  - resume and delete were refused while the writer lock was held;
  - `codex delete --force` on an `archived_sessions/` thread removed both file and row;
  - a live `codex exec` held its lock and its rollout open for as long as it ran. The plan turns these into
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
