"""Session archive replica: disk resolution, replica gate, daily replicate, and monthly verify-replica
(spec docs/specs/2026-11-07-session-archive-replica-design.md)."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import config

MARKER = ".session-archive-replica"


class ReplicaGateError(config.HostGateError):
    """The replica is unconfigured, unmounted, unmarked, or shares a physical disk with the archive."""


@dataclass(frozen=True)
class ReplicaInfo:
    archive_disks: frozenset[str]
    replica_disks: frozenset[str]


def _resolve_block_device(dev_dir: Path, root_path: Path) -> frozenset[str]:
    real_dir = Path(os.path.realpath(dev_dir))
    try:
        os.stat(real_dir)
    except FileNotFoundError:
        return frozenset()
    except OSError as error:
        raise ReplicaGateError(f"cannot read sysfs block entry for {root_path}: {error}") from None

    try:
        os.lstat(real_dir / "partition")
        is_partition = True
    except FileNotFoundError:
        is_partition = False
    except OSError as error:
        raise ReplicaGateError(f"cannot read sysfs partition marker for {root_path}: {error}") from None
    if is_partition:
        return frozenset({real_dir.parent.name})

    slaves_dir = real_dir / "slaves"
    try:
        with os.scandir(slaves_dir) as scan:
            entries = sorted(scan, key=lambda entry: entry.name)
    except FileNotFoundError:
        entries = []
    except OSError as error:
        raise ReplicaGateError(f"cannot read sysfs slaves for {root_path}: {error}") from None

    if entries:
        resolved: set[str] = set()
        for entry in entries:
            slave_disks = _resolve_block_device(Path(entry.path), root_path)
            if not slave_disks:
                return frozenset()
            resolved.update(slave_disks)
        return frozenset(resolved)

    return frozenset({real_dir.name})


def disks_of(path: Path, sysfs_root: Path = Path("/sys"), stat=os.stat) -> frozenset[str]:
    try:
        st_dev = stat(path).st_dev
    except OSError as error:
        raise ReplicaGateError(f"cannot stat {path}: {error}") from None
    major, minor = os.major(st_dev), os.minor(st_dev)
    if major == 0:
        return frozenset()
    entry = Path(sysfs_root) / "dev" / "block" / f"{major}:{minor}"
    try:
        os.lstat(entry)
    except FileNotFoundError:
        return frozenset()
    except OSError as error:
        raise ReplicaGateError(f"cannot read sysfs block link for {path}: {error}") from None
    return _resolve_block_device(entry, Path(path))


def check_replica(
    cfg: config.Config,
    disks: Callable[[Path], frozenset[str]] = disks_of,
) -> ReplicaInfo:
    if cfg.replica_root is None:
        raise ReplicaGateError("no replica is configured on this host")
    if not cfg.replica_root.is_dir():
        raise ReplicaGateError(f"replica_root {cfg.replica_root} does not exist (is the replica disk mounted?)")
    if not (cfg.replica_root / MARKER).is_file():
        raise ReplicaGateError(f"replica_root {cfg.replica_root} lacks the marker file {MARKER}")
    archive_disks = frozenset(disks(cfg.archive_root))
    if not archive_disks:
        raise ReplicaGateError(f"cannot resolve physical disk for archive_root {cfg.archive_root}")
    replica_disks = frozenset(disks(cfg.replica_root))
    if not replica_disks:
        raise ReplicaGateError(f"cannot resolve physical disk for replica_root {cfg.replica_root}")
    shared = archive_disks & replica_disks
    if shared:
        names = ", ".join(sorted(shared))
        raise ReplicaGateError(
            f"replica_root {cfg.replica_root} is on the same physical disk as archive_root {cfg.archive_root} ({names})"
        )
    return ReplicaInfo(archive_disks, replica_disks)
