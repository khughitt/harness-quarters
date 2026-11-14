"""Session archive replica: disk resolution, replica gate, daily replicate, and monthly verify-replica
(contract docs/session-archive.md)."""
import hashlib
import json
import os
import shutil
import sqlite3
import stat as stat_mod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import capture, config
from .manifest import FILENAME, Manifest, Version

MARKER = ".session-archive-replica"
KEEP_GENERATIONS = 7
REPLICA_STALE = timedelta(hours=48)
VERIFY_STALE = timedelta(days=35)


class ReplicaGateError(config.HostGateError):
    """The replica is unconfigured, unmounted, unmarked, or shares a physical disk with the archive."""


class ReplicateFailed(Exception):
    """A replicate run failed before publishing a verified generation."""

    def __init__(self, report: dict):
        self.report = report
        super().__init__(report.get("error", "replicate failed"))


class VerifyFailed(Exception):
    """A verify-replica restore check failed."""

    def __init__(self, report: dict):
        self.report = report
        failures = report.get("failures") or []
        super().__init__(failures[0] if failures else report.get("error", "verify-replica failed"))


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


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _check_completeness(partial_dir: Path, rows: list[Version]) -> str | None:
    expected: set[str] = {FILENAME}
    for version in rows:
        dest = capture.archived_file(partial_dir, version)
        rel = dest.relative_to(partial_dir).as_posix()
        try:
            st = os.lstat(dest)
        except OSError as error:
            return f"missing populated file {rel}: {error}"
        if not stat_mod.S_ISREG(st.st_mode):
            return f"populated entry {rel} is not a regular file"
        if st.st_size != version.size or st.st_mtime_ns != version.mtime_ns:
            return (
                f"populated file {rel} stat mismatch "
                f"(expected size={version.size} mtime_ns={version.mtime_ns}, "
                f"got size={st.st_size} mtime_ns={st.st_mtime_ns})"
            )
        expected.add(rel)

    for root, dirs, files in os.walk(partial_dir, followlinks=False):
        root_path = Path(root)
        for d in dirs:
            p = root_path / d
            if p.is_symlink():
                return f"unexpected symlink in partial generation: {p.relative_to(partial_dir).as_posix()}"
        for f in files:
            rel = (root_path / f).relative_to(partial_dir).as_posix()
            if rel not in expected:
                return f"unexpected file in partial generation: {rel}"
    return None


def _publish_generation(
    replica_root: Path,
    generations_dir: Path,
    partial_dir: Path,
    final_dir: Path,
    stamp: str,
) -> None:
    os.replace(partial_dir, final_dir)
    capture.fsync_dir(generations_dir)
    tmp_link = replica_root / f".current.{stamp}.tmp"
    tmp_link.unlink(missing_ok=True)
    os.symlink(Path("generations") / stamp, tmp_link)
    os.replace(tmp_link, replica_root / "current")
    capture.fsync_dir(replica_root)


def _prune_old_generations(replica_root: Path, generations_dir: Path, current_stamp: str) -> None:
    entries = sorted(
        entry.name
        for entry in os.scandir(generations_dir)
        if entry.is_dir(follow_symlinks=False) and not entry.name.endswith(".partial")
    )
    if len(entries) <= KEEP_GENERATIONS:
        return
    kept = set(entries[-KEEP_GENERATIONS:])
    kept.add(current_stamp)
    current_link = replica_root / "current"
    if current_link.is_symlink():
        kept.add(Path(os.readlink(current_link)).name)
    removed = False
    for name in entries:
        if name not in kept:
            shutil.rmtree(generations_dir / name)
            removed = True
    if removed:
        capture.fsync_dir(generations_dir)


def replicate(
    archive_root: Path,
    replica_root: Path,
    manifest: Manifest,
    disks: ReplicaInfo,
    now: Callable[[], datetime] = _utc_now_dt,
    before_publish: Callable[[Path], None] | None = None,
) -> dict:
    start_dt = now()
    stamp = start_dt.strftime("%Y%m%dT%H%M%S.%fZ")
    started_at = start_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def fail(message: str) -> ReplicateFailed:
        return ReplicateFailed(
            {
                "generation": stamp,
                "started_at": started_at,
                "verified": False,
                "error": message,
            }
        )

    generations_dir = replica_root / "generations"
    final_dir = generations_dir / stamp
    partial_dir = generations_dir / f"{stamp}.partial"

    try:
        capture.mkdir_synced(generations_dir)
        if final_dir.exists() or partial_dir.exists():
            raise fail(f"generation {stamp} already exists")

        # 1. Clear stale partials
        for entry in os.scandir(generations_dir):
            if entry.name.endswith(".partial") and entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path)

        # 2. Snapshot the manifest into <stamp>.partial/manifest.sqlite
        capture.mkdir_synced(partial_dir)
        snap_path = partial_dir / FILENAME
        dest_conn = sqlite3.connect(snap_path)
        try:
            manifest.conn.backup(dest_conn)
        finally:
            dest_conn.close()
        with open(snap_path, "rb") as handle:
            os.fsync(handle.fileno())

        snap_manifest = Manifest.open_readonly(partial_dir)
        try:
            integrity = snap_manifest.conn.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)]:
                raise fail(f"manifest snapshot failed integrity_check: {integrity}")
            rows = snap_manifest.all_versions()
        finally:
            snap_manifest.close()

        # 3. Populate every row from current (hard link) or archive (copy_hashed)
        current_link = replica_root / "current"
        prev_dir: Path | None = None
        prev_rows: dict[tuple[str, str, str], Version] = {}
        if current_link.is_symlink() and current_link.is_dir():
            prev_dir = Path(os.path.realpath(current_link))
            prev_manifest = Manifest.open_readonly(prev_dir)
            try:
                for v in prev_manifest.all_versions():
                    prev_rows[(v.source, v.relpath, v.location)] = v
            finally:
                prev_manifest.close()

        files_copied = 0
        bytes_copied = 0
        files_linked = 0
        bytes_linked = 0

        for version in rows:
            src_path = capture.archived_file(archive_root, version)
            dest_path = capture.archived_file(partial_dir, version)
            rel_path = dest_path.relative_to(partial_dir).as_posix()

            try:
                src_st = os.lstat(src_path)
            except OSError as error:
                raise fail(f"archive file {rel_path}: {error}") from None
            if not stat_mod.S_ISREG(src_st.st_mode):
                raise fail(f"archive file {rel_path} is not a regular file")

            can_link = False
            if (
                prev_dir is not None
                and src_st.st_size == version.size
                and src_st.st_mtime_ns == version.mtime_ns
            ):
                prev_ver = prev_rows.get((version.source, version.relpath, version.location))
                if prev_ver == version:
                    prev_file = capture.archived_file(prev_dir, version)
                    try:
                        st = os.lstat(prev_file)
                    except OSError:
                        st = None
                    if (
                        st is not None
                        and stat_mod.S_ISREG(st.st_mode)
                        and st.st_size == version.size
                        and st.st_mtime_ns == version.mtime_ns
                    ):
                        can_link = True

            if can_link:
                capture.mkdir_synced(dest_path.parent)
                os.link(prev_file, dest_path)
                files_linked += 1
                bytes_linked += version.size
            else:
                try:
                    copied = capture.copy_hashed(src_path, dest_path.parent, None)
                except OSError as error:
                    raise fail(f"archive file {rel_path}: {error}") from None
                try:
                    if copied.size != version.size or copied.sha256 != version.sha256:
                        raise fail(
                            f"archive file {rel_path} does not match manifest row "
                            f"(expected size={version.size} sha256={version.sha256}, "
                            f"got size={copied.size} sha256={copied.sha256})"
                        )
                    os.utime(copied.tmp, ns=(version.mtime_ns, version.mtime_ns))
                    os.replace(copied.tmp, dest_path)
                finally:
                    copied.tmp.unlink(missing_ok=True)
                files_copied += 1
                bytes_copied += version.size

        # 4. Check completeness
        completeness_err = _check_completeness(partial_dir, rows)
        if completeness_err is not None:
            raise fail(completeness_err)

        # 5. Write receipt.json and fsync every directory bottom-up
        finished_at = now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        receipt = {
            "generation": stamp,
            "archive_root": str(archive_root),
            "replica_root": str(replica_root),
            "archive_disks": sorted(disks.archive_disks),
            "replica_disks": sorted(disks.replica_disks),
            "started_at": started_at,
            "finished_at": finished_at,
            "rows": len(rows),
            "files_copied": files_copied,
            "bytes_copied": bytes_copied,
            "files_linked": files_linked,
            "bytes_linked": bytes_linked,
            "verified": True,
        }
        receipt_path = partial_dir / "receipt.json"
        with open(receipt_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        for root, _dirs, _files in os.walk(partial_dir, topdown=False, followlinks=False):
            capture.fsync_dir(Path(root))

        if before_publish is not None:
            before_publish(partial_dir)

        # 6. Publish
        _publish_generation(replica_root, generations_dir, partial_dir, final_dir, stamp)

        # 7. Keep the newest seven generations
        _prune_old_generations(replica_root, generations_dir, stamp)

        return receipt
    except ReplicateFailed:
        raise
    except (OSError, sqlite3.Error) as error:
        raise fail(f"{type(error).__name__}: {error}") from None


def verify_replica(replica_root: Path, scratch_dir: Path) -> dict:
    current_link = replica_root / "current"
    failures: list[str] = []
    unparseable: dict[str, int] = {}

    if not current_link.is_symlink() or not current_link.is_dir():
        report = {
            "generation": None,
            "rows": 0,
            "bytes_read": 0,
            "failures": ["current generation symlink is missing"],
            "unparseable": unparseable,
        }
        raise VerifyFailed(report)

    generation = Path(os.readlink(current_link)).name
    current_dir = Path(os.path.realpath(current_link))

    try:
        copied_manifest = capture.copy_hashed(current_dir / FILENAME, scratch_dir, None)
        try:
            os.replace(copied_manifest.tmp, scratch_dir / FILENAME)
        finally:
            copied_manifest.tmp.unlink(missing_ok=True)
        scratch_manifest = Manifest.open_readonly(scratch_dir)
        try:
            integrity = scratch_manifest.conn.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)]:
                failures.append(f"manifest integrity_check failed: {integrity}")
                rows: list[Version] = []
            else:
                rows = scratch_manifest.all_versions()
        finally:
            scratch_manifest.close()
    except (OSError, sqlite3.Error) as error:
        failures.append(f"manifest copy in scratch failed: {type(error).__name__}: {error}")
        rows = []

    bytes_read = 0
    for version in rows:
        file_path = capture.archived_file(current_dir, version)
        rel = file_path.relative_to(current_dir).as_posix()
        try:
            st = os.lstat(file_path)
        except OSError as error:
            failures.append(f"{rel}: missing or unreadable: {error}")
            continue
        if not stat_mod.S_ISREG(st.st_mode):
            failures.append(f"{rel}: not a regular file")
            continue

        is_jsonl = version.relpath.endswith(".jsonl")
        digest = hashlib.sha256()
        size = 0
        bad_lines = 0
        buf = b""
        try:
            with os.fdopen(capture.open_nofollow(file_path), "rb") as handle:
                while chunk := handle.read(capture.CHUNK):
                    digest.update(chunk)
                    size += len(chunk)
                    if is_jsonl:
                        buf += chunk
                        parts = buf.split(b"\n")
                        buf = parts.pop()
                        for line in parts:
                            if line:
                                try:
                                    json.loads(line)
                                except ValueError:
                                    bad_lines += 1
            if is_jsonl and buf:
                try:
                    json.loads(buf)
                except ValueError:
                    bad_lines += 1
        except OSError as error:
            failures.append(f"{rel}: read error: {error}")
            continue

        bytes_read += size
        if size != version.size:
            failures.append(f"{rel}: size mismatch (expected {version.size}, got {size})")
        elif digest.hexdigest() != version.sha256:
            failures.append(
                f"{rel}: sha256 mismatch (expected {version.sha256}, got {digest.hexdigest()})"
            )
        if is_jsonl and bad_lines > 0:
            unparseable[rel] = bad_lines

    report = {
        "generation": generation,
        "rows": len(rows),
        "bytes_read": bytes_read,
        "failures": failures,
        "unparseable": unparseable,
    }
    if failures:
        raise VerifyFailed(report)
    return report


def _parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def replica_status(replica_root: Path, manifest: Manifest, now: datetime) -> dict:
    reasons: list[str] = []
    generation: str | None = None
    receipt: dict | None = None

    try:
        has_root = replica_root.is_dir() and (replica_root / MARKER).is_file()
    except OSError:
        has_root = False

    if not has_root:
        reasons.append("replica directory or marker is missing")
    else:
        current_link = replica_root / "current"
        try:
            has_current = current_link.is_symlink() and current_link.is_dir()
            if has_current:
                generation = Path(os.readlink(current_link)).name
        except OSError:
            has_current = False

        if not has_current:
            reasons.append("current generation is missing")
        else:
            receipt_path = current_link / "receipt.json"
            try:
                parsed = json.loads(receipt_path.read_text(encoding="utf-8"))
                if not isinstance(parsed, dict) or not isinstance(parsed.get("finished_at"), str):
                    raise ValueError("missing finished_at")
                finished_dt = _parse_stamp(parsed["finished_at"])
                receipt = parsed
            except (OSError, ValueError):
                reasons.append("receipt.json is unreadable")
            else:
                if now - finished_dt > REPLICA_STALE:
                    reasons.append("current generation receipt is older than 48 hours")

    last_replicate = manifest.last_run("replicate")
    if last_replicate is not None and not last_replicate.ok:
        reasons.append("last replicate run failed")

    last_verify = manifest.last_run("verify-replica")
    if last_verify is not None and not last_verify.ok:
        reasons.append("last verify-replica run failed")

    last_verify_ok = manifest.last_run("verify-replica", ok_only=True)
    verify_fresh = False
    if last_verify_ok is not None:
        try:
            verify_fresh = now - _parse_stamp(last_verify_ok.finished_at) <= VERIFY_STALE
        except ValueError:
            verify_fresh = False
    if not verify_fresh:
        reasons.append("no passing verify-replica run within 35 days")

    ok = not reasons
    return {
        "generation": generation,
        "receipt": receipt,
        "replicate": asdict(last_replicate) if last_replicate else None,
        "verify_replica": asdict(last_verify) if last_verify else None,
        "ok": ok,
        "reasons": reasons,
    }



