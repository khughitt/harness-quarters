"""Tests for session_archive.replica: disk resolution, replica gate, replicate, verify_replica."""
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from session_archive import config, replica


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
