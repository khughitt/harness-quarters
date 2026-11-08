# Session archive replica: implementation plan

Spec: [replica design](../specs/2026-11-07-session-archive-replica-design.md), revision
`e46d5e87`, approved for planning by the user on 2026-11-08 after agy review rounds 1
(revise) and 2 (accept). Task: hq-adfed6. Branch `feat/hq-adfed6-archive-replica` in
`.worktrees/hq-adfed6`.

Every section reference (§) below is to that spec. Where this plan and the spec disagree,
the spec wins and the disagreement is a finding.

## Conventions for every task

- **Tests first.** Write the task's tests, run them and see them fail for the reason the
  test names, then implement until they pass. Each new test is also seen to fail against
  a targeted break of the behaviour it checks.
- **Focused route.** `just test-one <test files or node ids>` from the worktree root. The
  checkout's `.tt.toml` disables automatic broad runs: do not run `just test` for a commit
  or a task boundary. Run `just check-hygiene` before each commit. A policy skip is not a
  pass; report the focused scope you ran.
- **Environments.** Any subprocess a test starts gets an environment built key by key
  (`testing.run_tool` already does this) with a temporary `HOME` and fake credentials.
- **Reuse, do not fork.** Copy with `capture.copy_hashed`, open with
  `capture.open_nofollow`, sync with `capture.fsync_dir` / `mkdir_synced`, resolve archive
  paths with `capture.archived_file`, read rows through `Manifest`. No second copy helper.
- **No new CLI options.** Two new subcommands only (§3).
- Commit messages are conventional (`feat(session-archive): …`, `test(…)`, `docs(…)`).

New module: `tools/session_archive/replica.py` holds the disk resolver, the replica gate,
`replicate`, `verify_replica` and the replica part of status. New tests:
`tools/test_session_archive_replica.py` (core) and `tools/test_session_archive_replica_cli.py`
(CLI). Existing test files are extended where a task says so.

### Task 1: Configuration, lock wait and the live-source boundary

Spec: §3.1 (first paragraphs and "Live source roots"), §3.5.

- `config.Config` gains `replica_root: Path | None`. `load_config` reads the optional key:
  absent gives `None`; a non-string raises `HostGateError` naming the key; a string is
  `expanduser`ed. It never stats the replica path. Why: an unmounted replica disk must not
  stop capture or prune (review round 1, finding 2).
- `config.archive_lock(root, wait=0.0)`: `wait=0` keeps today's non-blocking behaviour for
  every existing caller; `wait>0` retries `LOCK_NB` with a short sleep until the deadline,
  then raises `LockHeld`. Why polling over a blocking `flock`: a bounded wait without
  signals or threads.
- `cli.main`: skip `harness_stores.archive_sources` / `check_sources` for `replicate` and
  `verify-replica` (a constant set beside `LOCKED`). Why: those commands read only the
  archive and the replica (review round 1, finding 1).
- Tests (extend `tools/test_session_archive_config.py`): key absent, non-string, string with
  `~`; a configured replica path that does not exist does not affect `load_config`;
  `archive_lock` with `wait` acquires after the holder releases, and raises `LockHeld` after
  the deadline (hold the lock from a second descriptor in the test; deadline under a
  second). The `main()` boundary is tested in Task 5 once the subcommands exist.

### Task 2: Disk resolver and replica gate

Spec: §3.1 ("Same physical disk", the refusal list).

- `replica.disks_of(path, sysfs_root=Path("/sys")) -> frozenset[str]`: `st_dev` of `path`
  → `<sysfs_root>/dev/block/<major>:<minor>` → `realpath`; if the directory has a
  `partition` file, the whole disk is its parent directory's name; if it has a non-empty
  `slaves/`, recurse into each entry (`<sysfs_root>/class/block/<name>`); otherwise the
  device's own name. Major 0 or a missing entry gives the empty set. An unreadable entry
  raises `ReplicaGateError`. Why recursive slaves: LVM or LUKS over the archive's disk must
  not pass as a different disk.
- `replica.check_replica(cfg, disks) -> ReplicaInfo` (`disks` is the resolver; the CLI
  passes `disks_of`): refuses with `ReplicaGateError` (CLI exit 2) when `replica_root` is
  `None`, the directory is missing, the marker `.session-archive-replica` is missing, either
  disk set is empty, or the sets intersect. The messages are the spec's. Returns the two
  disk sets for the receipt.
- Tests (core file): fake sysfs trees under `tmp_path`, with `st_dev` supplied through a
  stat function parameter on `disks_of` (default `os.stat`): plain disk, partition → parent,
  dm over a partition → parent disk, two partitions of one disk intersect, major 0 → empty,
  unreadable `slaves/` → error. Gate: each refusal with its message, and nothing created
  under the replica root.

### Task 3: replicate

Spec: §3.2, §3.3, §3.5.

- `replica.replicate(archive_root, replica_root, manifest, disks: ReplicaInfo, now) ->
  dict` runs steps 1–7 of §3.3 and returns the report (receipt fields plus `generation`);
  any failure raises `ReplicateFailed(report)` carrying the first failure named. The CLI
  (Task 5) holds the lock and records the run (step 8).
- Stamp: `now()` formatted `%Y%m%dT%H%M%S.%fZ`. An existing `<stamp>` or `<stamp>.partial`
  fails the run. Why: same-second runs in tests and retries (round 1, minor 1).
- Snapshot: `sqlite3` backup API from the archive manifest into the partial; reopen
  read-only, `PRAGMA integrity_check` must return `ok`; read all rows; close before
  populating. Why close: no sidecar file in the partial (round 1, minor 2).
- Populate per row: link from `current` only when its manifest has the identical row and
  `lstat` shows a regular file with that size and `mtime_ns`; otherwise `copy_hashed` from
  the archive file (no-follow), compare size and sha256 with the row, `os.utime` to the row's
  `mtime_ns`, rename into place. Directories created with `mkdir_synced`.
- Completeness, receipt, publish (`rename` partial → stamp, `fsync` `generations/`, new
  symlink under a temporary name renamed over `current`, `fsync` replica root), retention
  (keep the newest seven by stamp; never the one `current` names) exactly as §3.3.
- Failure leaves `current` and verified generations untouched; the partial stays until the
  next run's step 1.
- Tests (core file), using a fixture archive built through `capture.capture_run` on
  temporary sources so rows and files are real: first generation (files, hashes, `current`,
  receipt counts; the generation opens with `Manifest.open_readonly` and `status` logic when
  a `.session-archive-root` is added in a scratch copy); second generation after appending
  to one transcript and creating a `versions/` entry (unchanged files share inodes with the
  first, changed do not); archive file bytes changed behind its row → `ReplicateFailed`
  naming it, no new generation, `current` unchanged; failure injected after populate (a
  hook parameter, or monkeypatching the publish step) leaves the partial and old `current`,
  next run removes it and publishes; nine runs with an injected clock leave seven
  generations and the oldest kept verifies; repeated stamp fails; a `current` file whose
  mtime was changed is copied, not linked.

### Task 4: verify-replica

Spec: §3.4.

- `replica.verify_replica(replica_root, scratch_dir) -> dict` (report) raising
  `VerifyFailed(report)` on any hash, size, missing-file or integrity failure: copy
  `current/manifest.sqlite` into `scratch_dir`, `PRAGMA integrity_check`, read every row;
  hash every described file in `current` against its row; for every row whose `relpath`
  ends in `.jsonl`, split the bytes on `b"\n"`, skip empty segments, `json.loads` each line
  (bytes input), counting `ValueError` (which covers `UnicodeDecodeError` and
  `JSONDecodeError`) as unparseable. The report gives rows, bytes read, failures and the
  unparseable count per file with any.
- Tests (core file): passes on a fresh generation; fails on a flipped byte, a truncated
  file, a missing file and a corrupted manifest copy (overwrite its header bytes); an
  unparseable line, a cut multi-byte UTF-8 sequence at end of file and a `versions/`
  transcript are counted without failing.

### Task 5: CLI subcommands

Spec: §3, §3.1 (resolver attribute), §3.5, §5 (fixture route).

- `build_parser`: `replicate` and `verify-replica`, no options, with help lines.
- `cli.DISKS = replica.disks_of` (module attribute the commands call through). `cli.CLOCK
  = datetime.now(timezone.utc)`-based stamp source passed as `now`.
- `cmd_replicate`: `check_replica(cfg, DISKS)` (exit 2 on `ReplicaGateError`), lock with
  `wait=7200` (exit 75 on `LockHeld`), open the manifest, call `replicate`, record a
  `replicate` run (ok with the receipt, or failed with the report), print the JSON report,
  exit 0 or 1.
- `cmd_verify_replica`: the same gate and lock wait; a `tempfile.TemporaryDirectory` as
  scratch; record a `verify-replica` run; print and exit likewise.
- Tests (CLI file):
  - In process: monkeypatch `HOME` (and the `XDG_*` keys `run_tool` sets) to `tmp_path`
    and `cli.DISKS` to a resolver giving each root its own disk; build the fixture archive;
    `cli.main(["replicate"])`, `cli.main(["verify-replica"])`, `cli.main(["status"])` all
    exit 0 and print JSON whose counts match. This is the spec's small end-to-end fixture
    route.
  - Subprocess (`run_tool`): fixture archive and replica on one filesystem → `replicate`
    exits 2 with the same-disk message, and nothing appears under `generations/`.
  - Boundary: with `replica_root` pointing at a missing directory, `capture` exits 0; with
    a required live source root removed, `capture` exits 2 while in-process
    `replicate`/`verify-replica` exit 0.
  - Lock: hold the archive lock from the test; `replicate` with the wait patched to a short
    value exits 75.

### Task 6: status reports the replica

Spec: §3.6.

- `replica.replica_status(replica_root, manifest, now) -> dict` with `ok` and `reasons`,
  never raising `OSError`, `ValueError` or `json` errors out of it; `status.status_report`
  takes the optional replica root, adds the `replica` key only when configured, and folds
  `replica.ok` into the overall `ok`. `cmd_status` passes `cfg.replica_root`.
- Reasons, one per §3.6 condition: replica directory or marker missing, `current` missing,
  receipt unreadable, receipt `finished_at` older than 48 hours, last `replicate` run
  failed, last `verify-replica` failed, no passing `verify-replica` within 35 days.
- Tests (extend `tools/test_session_archive_status.py`): healthy case; each reason alone
  makes `ok` false with the archive part of the report still present; a manifest with no
  `replicate` rows but a fresh receipt and a passing check is healthy; no `replica` key and
  unchanged health when unconfigured.

### Task 7: Units, links and README

Spec: §3.6, §3.7, §4.

- `systemd/user/session-archive-replicate.{service,timer}` (daily `*-*-* 06:00:00`) and
  `session-archive-verify-replica.{service,timer}` (`*-*-15 06:30:00`), both
  `Persistent=true`, services `Type=oneshot`, `Nice=10`, `IOSchedulingClass=idle`, the same
  `Environment=PATH=…` and `ExecStart=/usr/bin/python3 %h/.local/bin/session-archive <cmd>`
  as capture, and the design comment line naming this spec.
- `links.toml` `[required]`: the four unit links.
- Extend `tools/test_session_archive_units.py`'s parametrized cases to the new services,
  timers and links (they also pass the path allowlist test).
- README's session-archive entry: one paragraph on the replica (what it is, the config key,
  the marker, the two commands and timers) and the restore procedure from §3.7. Add the
  spec to the entry's references.
- Check `docs/` for another reference document describing the archive's commands and
  update it if one exists; the 2026-09-30 spec is a decision record and is not edited.

### Task 8: Activation on the primary host

Spec: §4. Operational; runs only after the final whole-branch review accepts and the
branch is merged to main. Each numbered step below needs the user's approval when it is
reached; plan approval grants none of them.

1. Read-only preflight: `findmnt` both mounts, `disks_of` on both roots through
   `python3 -c` from main's `tools/`, free space on the replica mount.
2. Create the replica directory at the top of the second disk's mount, write
   `.session-archive-replica`, add `replica_root` to `~/.config/session-archive/config.toml`.
3. `session-archive replicate` by hand from the linked tool (first copy, about 40 GB); read
   the report; `ls -l <replica_root>/current`.
4. `session-archive verify-replica`; read the report; `session-archive status`.
5. `just link --apply` from main, `systemctl --user daemon-reload`, enable both timers;
   `systemctl --user list-timers 'session-archive*'`.
6. After two scheduled replicate runs, `session-archive status` shows a fresh replica.
   Record the second-drive identity, first generation receipt, verify report and timer
   state on hq-adfed6 for ops-7b325c's closeout.

Rollback: disable both timers, remove the key from the config. The replica directory is
kept or deleted at the user's word.
