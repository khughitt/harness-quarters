"""Tests for session_archive.replica: disk resolution, replica gate, replicate, verify_replica."""
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import harness_stores
from session_archive import capture, config, replica
from session_archive.manifest import FILENAME, Manifest, Run
from session_archive.status import status_report
from session_archive.testing import claude_session, codex_rollout, write


@dataclass(frozen=True)
class FakeStat:
    st_dev: int


def make_sysfs(root: Path) -> Path:
    """Build a realistic sysfs tree under root/sys where dev/block, class/block and slaves
    entries are symlinks into devices/.../block/."""
    sysfs = root / "sys"
    (sysfs / "dev" / "block").mkdir(parents=True)
    (sysfs / "class" / "block").mkdir(parents=True)
    return sysfs


def add_disk(sysfs: Path, name: str, major: int, minor: int) -> Path:
    dev = sysfs / "devices" / "pci0000:00" / "block" / name
    (dev / "slaves").mkdir(parents=True)
    (sysfs / "dev" / "block" / f"{major}:{minor}").symlink_to(dev, target_is_directory=True)
    (sysfs / "class" / "block" / name).symlink_to(dev, target_is_directory=True)
    return dev


def add_partition(sysfs: Path, disk_dev: Path, name: str, major: int, minor: int) -> Path:
    part = disk_dev / name
    part.mkdir(parents=True)
    (part / "partition").write_text("1\n")
    (sysfs / "dev" / "block" / f"{major}:{minor}").symlink_to(part, target_is_directory=True)
    (sysfs / "class" / "block" / name).symlink_to(part, target_is_directory=True)
    return part


def add_dm(sysfs: Path, name: str, major: int, minor: int, slave_names: list[str]) -> Path:
    dm = sysfs / "devices" / "virtual" / "block" / name
    slaves = dm / "slaves"
    slaves.mkdir(parents=True)
    for slave in slave_names:
        # Point slave symlink into class/block/<slave> (which itself is a symlink to devices/...)
        (slaves / slave).symlink_to(sysfs / "class" / "block" / slave, target_is_directory=True)
    (sysfs / "dev" / "block" / f"{major}:{minor}").symlink_to(dm, target_is_directory=True)
    (sysfs / "class" / "block" / name).symlink_to(dm, target_is_directory=True)
    return dm


def test_disks_of_resolves_disk_partition_dm_and_virtual(tmp_path):
    sysfs = make_sysfs(tmp_path)
    add_disk(sysfs, "sdc", 8, 32)
    sdb = add_disk(sysfs, "sdb", 8, 16)
    add_partition(sysfs, sdb, "sdb1", 8, 17)
    add_partition(sysfs, sdb, "sdb2", 8, 18)
    add_dm(sysfs, "dm-0", 253, 0, ["sdb1"])

    devs = {
        tmp_path / "plain": os.makedev(8, 32),
        tmp_path / "part1": os.makedev(8, 17),
        tmp_path / "part2": os.makedev(8, 18),
        tmp_path / "dm": os.makedev(253, 0),
        tmp_path / "tmpfs": os.makedev(0, 42),
        tmp_path / "missing": os.makedev(9, 99),
    }
    fake_stat = lambda p: FakeStat(devs[Path(p)])

    assert replica.disks_of(tmp_path / "plain", sysfs, stat=fake_stat) == frozenset({"sdc"})
    assert replica.disks_of(tmp_path / "part1", sysfs, stat=fake_stat) == frozenset({"sdb"})
    assert replica.disks_of(tmp_path / "part2", sysfs, stat=fake_stat) == frozenset({"sdb"})
    assert replica.disks_of(tmp_path / "dm", sysfs, stat=fake_stat) == frozenset({"sdb"})
    assert (
        replica.disks_of(tmp_path / "part1", sysfs, stat=fake_stat)
        & replica.disks_of(tmp_path / "part2", sysfs, stat=fake_stat)
    ) == frozenset({"sdb"})
    assert replica.disks_of(tmp_path / "tmpfs", sysfs, stat=fake_stat) == frozenset()
    assert replica.disks_of(tmp_path / "missing", sysfs, stat=fake_stat) == frozenset()


def test_disks_of_unreadable_slaves_raises_gate_error(tmp_path):
    sysfs = make_sysfs(tmp_path)
    sdb = add_disk(sysfs, "sdb", 8, 16)
    add_partition(sysfs, sdb, "sdb1", 8, 17)
    dm = add_dm(sysfs, "dm-0", 253, 0, ["sdb1"])
    slaves = dm / "slaves"
    slaves.chmod(0o000)
    try:
        with pytest.raises(replica.ReplicaGateError):
            replica.disks_of(
                tmp_path / "dm",
                sysfs,
                stat=lambda _p: FakeStat(os.makedev(253, 0)),
            )
    finally:
        slaves.chmod(0o755)


def test_check_replica_refusals_and_success(tmp_path, archive):
    unconfigured = config.Config(archive, ("obs",), (), None)
    with pytest.raises(replica.ReplicaGateError, match="no replica is configured on this host"):
        replica.check_replica(unconfigured, lambda _p: frozenset({"sdc"}))

    absent = tmp_path / "absent-replica"
    cfg_absent = config.Config(archive, ("obs",), (), absent)
    with pytest.raises(replica.ReplicaGateError, match="is the replica disk mounted"):
        replica.check_replica(cfg_absent, lambda _p: frozenset({"sdb"}))
    assert not absent.exists()

    rep = tmp_path / "replica"
    rep.mkdir()
    cfg = config.Config(archive, ("obs",), (), rep)
    with pytest.raises(replica.ReplicaGateError, match="lacks the marker file .session-archive-replica"):
        replica.check_replica(cfg, lambda _p: frozenset({"sdb"}))
    assert list(rep.iterdir()) == []

    (rep / replica.MARKER).touch()

    with pytest.raises(replica.ReplicaGateError, match="cannot resolve physical disk"):
        replica.check_replica(cfg, lambda _p: frozenset())

    with pytest.raises(replica.ReplicaGateError, match="same physical disk.*sdc"):
        replica.check_replica(cfg, lambda _p: frozenset({"sdc"}))

    sysfs = make_sysfs(tmp_path)
    sdc = add_disk(sysfs, "sdc", 8, 32)
    add_partition(sysfs, sdc, "sdc1", 8, 33)
    add_dm(sysfs, "dm-0", 253, 0, ["sdc1"])
    dev_map = {archive: os.makedev(8, 33), rep: os.makedev(253, 0)}
    with pytest.raises(replica.ReplicaGateError, match="same physical disk.*sdc"):
        replica.check_replica(
            cfg,
            lambda p: replica.disks_of(p, sysfs, stat=lambda q: FakeStat(dev_map[Path(q)])),
        )
    assert [p.name for p in rep.iterdir()] == [replica.MARKER]

    info = replica.check_replica(
        cfg,
        lambda p: frozenset({"sdc"}) if Path(p) == archive else frozenset({"sdb"}),
    )
    assert info == replica.ReplicaInfo(frozenset({"sdc"}), frozenset({"sdb"}))


DISKS = replica.ReplicaInfo(frozenset({"sdc"}), frozenset({"sdb"}))
T0 = datetime(2026, 11, 8, 6, 0, 12, 345678, tzinfo=timezone.utc)


def _seed_archive(home: Path, archive: Path, manifest: Manifest, now: datetime = T0) -> tuple[Path, Path]:
    sources = harness_stores.archive_sources(home)
    by_name = {s.name: s.root for s in sources}
    claude_main = claude_session(by_name["claude"])
    codex_file = codex_rollout(by_name["codex"])
    report, ok = capture.capture_run(archive, manifest, sources)
    assert ok
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    manifest.record_run(Run("cap-1", "capture", "apply", stamp, stamp, True, report))
    return claude_main, codex_file


def test_replicate_first_generation_and_scratch_restore(tmp_path, home, archive, manifest):
    _seed_archive(home, archive, manifest, T0)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()

    report = replica.replicate(archive, rep, manifest, DISKS, now=lambda: T0)
    expected_stamp = "20261108T060012.345678Z"
    assert report["generation"] == expected_stamp
    assert report["verified"] is True
    assert report["rows"] == 4
    assert report["files_copied"] == 4
    assert report["files_linked"] == 0
    assert report["bytes_copied"] > 0
    assert report["bytes_linked"] == 0
    assert report["archive_disks"] == ["sdc"]
    assert report["replica_disks"] == ["sdb"]

    current = rep / "current"
    assert current.is_symlink()
    assert os.readlink(current) == f"generations/{expected_stamp}"
    gen_dir = rep / "generations" / expected_stamp
    assert gen_dir.is_dir()

    receipt = json.loads((gen_dir / "receipt.json").read_text())
    assert receipt["verified"] is True
    assert receipt["rows"] == 4
    assert receipt["files_copied"] == 4
    assert receipt["files_linked"] == 0

    # No SQLite sidecars (-wal, -shm, -journal) in the generation
    assert not list(gen_dir.glob("manifest.sqlite-*"))

    # Every row's file exists in the generation with matching bytes and hash
    gen_manifest = Manifest.open_readonly(gen_dir)
    try:
        cursor = gen_manifest.conn.execute(
            "SELECT source, relpath, location, size, mtime_ns, sha256, captured_at FROM versions"
        )
        rows = [capture.Version(*row) for row in cursor]
    finally:
        gen_manifest.close()
    assert len(rows) == 4
    for v in rows:
        gen_file = capture.archived_file(gen_dir, v)
        assert gen_file.is_file() and not gen_file.is_symlink()
        assert capture.hash_file(gen_file) == v.sha256
        assert gen_file.stat().st_size == v.size

    # Scratch copy with .session-archive-root opens with Manifest.open_readonly and status_report
    scratch_archive = tmp_path / "scratch-archive"
    shutil.copytree(current, scratch_archive, symlinks=True)
    (scratch_archive / config.MARKER).touch()
    restored = Manifest.open_readonly(scratch_archive)
    try:
        st_report, st_ok = status_report(restored, [home], T0 + timedelta(hours=1))
    finally:
        restored.close()
    assert st_ok is True
    assert st_report["archive_bytes"] == report["bytes_copied"]


def test_replicate_second_generation_hardlinks_unchanged_and_copies_changed(
    tmp_path, home, archive, manifest
):
    claude_main, codex_file = _seed_archive(home, archive, manifest, T0)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()

    r1 = replica.replicate(archive, rep, manifest, DISKS, now=lambda: T0)
    gen1 = rep / "generations" / r1["generation"]

    # Append to claude_main (updates mirror in place) and overwrite codex_file (creates a versions/ entry)
    write(claude_main, claude_main.read_bytes() + b'{"a":2}\n', age_days=10)
    write(codex_file, b'{"rewritten":true}\n', age_days=10)
    sources = harness_stores.archive_sources(home)
    _, ok = capture.capture_run(archive, manifest, sources)
    assert ok

    t1 = T0 + timedelta(days=1)
    r2 = replica.replicate(archive, rep, manifest, DISKS, now=lambda: t1)
    gen2 = rep / "generations" / r2["generation"]

    # 4 original rows -> claude_main mirror updated, codex_file kept original mirror + added 1 diverged version = 5 rows
    # Unchanged: subagent transcript (1), tool result (1), original codex mirror (1) = 3 linked
    # Changed/new: updated claude_main mirror (1), new codex diverged version (1) = 2 copied
    assert r2["rows"] == 5
    assert r2["files_linked"] == 3
    assert r2["files_copied"] == 2

    rel_sub = f"-p/{claude_main.stem}/subagents/agent-1.jsonl"
    rel_main = f"-p/{claude_main.name}"
    assert (gen1 / "claude" / rel_sub).stat().st_ino == (gen2 / "claude" / rel_sub).stat().st_ino
    assert (gen1 / "claude" / rel_main).stat().st_ino != (gen2 / "claude" / rel_main).stat().st_ino


def test_replicate_damaged_archive_file_fails_and_preserves_current(
    tmp_path, home, archive, manifest
):
    claude_main, _ = _seed_archive(home, archive, manifest, T0)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()

    r1 = replica.replicate(archive, rep, manifest, DISKS, now=lambda: T0)
    old_target = os.readlink(rep / "current")

    # Append to claude_main, capture it, then flip one byte in the archive file while keeping size and mtime_ns
    write(claude_main, b'{"a":1}\n{"a":2}\n', age_days=10)
    _, ok = capture.capture_run(archive, manifest, harness_stores.archive_sources(home))
    assert ok

    rel_main = f"claude/-p/{claude_main.name}"
    archived_main = archive / rel_main
    orig_st = archived_main.stat()
    archived_main.write_bytes(b'{"a":1}\n{"a":9}\n')
    os.utime(archived_main, ns=(orig_st.st_mtime_ns, orig_st.st_mtime_ns))

    t1 = T0 + timedelta(days=1)
    with pytest.raises(replica.ReplicateFailed, match=rel_main) as exc_info:
        replica.replicate(archive, rep, manifest, DISKS, now=lambda: t1)
    assert rel_main in exc_info.value.report["error"]
    assert exc_info.value.report["verified"] is False
    assert os.readlink(rep / "current") == old_target
    assert not (rep / "generations" / t1.strftime("%Y%m%dT%H%M%S.%fZ")).exists()
    assert (rep / "generations" / r1["generation"] / rel_main).read_bytes() == b'{"a":1}\n'


def test_replicate_interrupted_before_publish_leaves_partial_and_next_run_recovers(
    tmp_path, home, archive, manifest
):
    _seed_archive(home, archive, manifest, T0)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()

    r1 = replica.replicate(archive, rep, manifest, DISKS, now=lambda: T0)
    old_target = os.readlink(rep / "current")

    t1 = T0 + timedelta(days=1)
    stamp1 = t1.strftime("%Y%m%dT%H%M%S.%fZ")

    def boom(_partial_dir: Path) -> None:
        raise OSError("simulated interruption before publish")

    with pytest.raises(replica.ReplicateFailed, match="simulated interruption before publish"):
        replica.replicate(archive, rep, manifest, DISKS, now=lambda: t1, before_publish=boom)

    assert os.readlink(rep / "current") == old_target
    assert (rep / "generations" / f"{stamp1}.partial").is_dir()
    assert not (rep / "generations" / stamp1).exists()

    # Next run removes the stale partial and publishes
    t2 = T0 + timedelta(days=2)
    r2 = replica.replicate(archive, rep, manifest, DISKS, now=lambda: t2)
    assert not list((rep / "generations").glob("*.partial"))
    assert os.readlink(rep / "current") == f"generations/{r2['generation']}"
    assert (rep / "generations" / r1["generation"]).is_dir()
    assert (rep / "generations" / r2["generation"]).is_dir()


def test_replicate_retention_keeps_seven_and_repeated_stamp_fails(
    tmp_path, home, archive, manifest
):
    _seed_archive(home, archive, manifest, T0)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()

    stamps = []
    for day in range(9):
        t = T0 + timedelta(days=day)
        res = replica.replicate(archive, rep, manifest, DISKS, now=lambda t=t: t)
        stamps.append(res["generation"])

    kept = sorted(p.name for p in (rep / "generations").iterdir())
    assert len(kept) == 7
    assert kept == stamps[2:]

    # Oldest kept generation still has all files with valid hashes even though stamps[0..1] were removed
    oldest_kept = rep / "generations" / stamps[2]
    oldest_manifest = Manifest.open_readonly(oldest_kept)
    try:
        rows = [
            capture.Version(*row)
            for row in oldest_manifest.conn.execute(
                "SELECT source, relpath, location, size, mtime_ns, sha256, captured_at FROM versions"
            )
        ]
    finally:
        oldest_manifest.close()
    assert len(rows) == 4
    for v in rows:
        f = capture.archived_file(oldest_kept, v)
        assert f.is_file() and capture.hash_file(f) == v.sha256

    # Repeated stamp fails without modifying current
    last_time = T0 + timedelta(days=8)
    with pytest.raises(replica.ReplicateFailed, match="already exists"):
        replica.replicate(archive, rep, manifest, DISKS, now=lambda: last_time)
    assert os.readlink(rep / "current") == f"generations/{stamps[-1]}"


def test_replicate_copies_instead_of_linking_when_current_file_mtime_or_size_changed(
    tmp_path, home, archive, manifest
):
    claude_main, _ = _seed_archive(home, archive, manifest, T0)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()

    r1 = replica.replicate(archive, rep, manifest, DISKS, now=lambda: T0)
    gen1 = rep / "generations" / r1["generation"]

    # Touch mtime of one file and alter size of another in current (gen1)
    rel_main = f"claude/-p/{claude_main.name}"
    rel_tool = f"claude/-p/{claude_main.stem}/tool-results/r.txt"
    gen1_main = gen1 / rel_main
    gen1_tool = gen1 / rel_tool
    st_main = gen1_main.stat()
    os.utime(gen1_main, ns=(st_main.st_mtime_ns + 1_000_000, st_main.st_mtime_ns + 1_000_000))
    gen1_tool.write_bytes(b"tampered-length")

    t1 = T0 + timedelta(days=1)
    r2 = replica.replicate(archive, rep, manifest, DISKS, now=lambda: t1)
    gen2 = rep / "generations" / r2["generation"]

    assert r2["files_copied"] == 2
    assert r2["files_linked"] == 2
    assert (gen2 / rel_main).stat().st_ino != gen1_main.stat().st_ino
    assert (gen2 / rel_tool).stat().st_ino != gen1_tool.stat().st_ino
    assert (gen2 / rel_tool).read_bytes() == b"result"

