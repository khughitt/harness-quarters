"""Capturing files into the archive (spec §3.3): the mirror, versions/, and the manifest."""
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .decide import Stat, capture_action, extends
from .manifest import MIRROR, Manifest, Version, utc_now

CHUNK = 1 << 20


def stat_of(path: Path) -> Stat:
    info = os.stat(path, follow_symlinks=False)
    return Stat(info.st_size, info.st_mtime_ns)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def mirror_path(root: Path, source: str, relpath: str) -> Path:
    return root / source / relpath


def version_location(source: str, relpath: str, captured_at: str) -> str:
    return f"versions/{source}/{relpath}@{captured_at}"


def archived_file(root: Path, version: Version) -> Path:
    if version.location == MIRROR:
        return mirror_path(root, version.source, version.relpath)
    return root / version.location


def stored_stat(root: Path, version: Version | None) -> Stat | None:
    if version is None:
        return None
    try:
        return stat_of(archived_file(root, version))
    except FileNotFoundError:
        return None


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mkdir_synced(path: Path) -> None:
    """Create missing directories, syncing each new entry in its containing parent."""
    if path.is_dir():
        return
    mkdir_synced(path.parent)
    path.mkdir()
    fsync_dir(path.parent)


@dataclass(frozen=True)
class Copied:
    tmp: Path
    size: int
    sha256: str
    prefix_sha256: str | None   # digest of the first `prefix` bytes; None when shorter


def copy_hashed(src: Path, dest_dir: Path, prefix: int | None) -> Copied:
    """Copy src to an fsynced temporary file in dest_dir. One pass hashes the whole file and,
    when prefix is given, its first prefix bytes."""
    mkdir_synced(dest_dir)
    fd, name = tempfile.mkstemp(dir=dest_dir, prefix=".capture-")
    whole, head, seen = hashlib.sha256(), hashlib.sha256(), 0
    try:
        with os.fdopen(fd, "wb") as writer, open(src, "rb") as reader:
            while chunk := reader.read(CHUNK):
                if prefix is not None and seen < prefix:
                    head.update(chunk[: prefix - seen])
                whole.update(chunk)
                writer.write(chunk)
                seen += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    except BaseException:
        os.unlink(name)
        raise
    prefix_sha256 = head.hexdigest() if prefix is not None and seen >= prefix else None
    return Copied(Path(name), seen, whole.hexdigest(), prefix_sha256)


@dataclass(frozen=True)
class Outcome:
    action: str              # unchanged | copied | repaired | diverged | busy
    version: Version | None


def capture_file(root: Path, manifest: Manifest, source: str, relpath: str, path: Path, *,
                 force: bool = False, now=utc_now) -> Outcome:
    """Capture `path` as `source`/`relpath`. `path` is normally the live file; prune passes a
    quarantined one. With force, an unchanged file is copied again (read-back repair)."""
    live = stat_of(path)
    latest = manifest.latest(source, relpath)
    action = capture_action(live, latest, stored_stat(root, latest))
    if action == "skip" and not force:
        return Outcome("unchanged", latest)
    mirror = manifest.mirror(source, relpath)
    mirrored = mirror_path(root, source, relpath)
    copied = copy_hashed(path, mirrored.parent, mirror.size if mirror else None)
    try:
        if stat_of(path) != live:
            return Outcome("busy", None)
        captured_at = now()
        if extends(copied.size, copied.prefix_sha256, mirror):
            location, dest = MIRROR, mirrored
        else:
            location = version_location(source, relpath, captured_at)
            dest = root / location
            mkdir_synced(dest.parent)
        os.utime(copied.tmp, ns=(live.mtime_ns, live.mtime_ns))
        if location == MIRROR:
            os.replace(copied.tmp, dest)
        else:
            os.link(copied.tmp, dest)  # Publish atomically without replacing an archived version.
            copied.tmp.unlink()
        fsync_dir(dest.parent)
        version = Version(source, relpath, location, copied.size, live.mtime_ns, copied.sha256, captured_at)
        manifest.put(version)
        if location != MIRROR:
            return Outcome("diverged", version)
        return Outcome("copied" if action == "copy" else "repaired", version)
    finally:
        copied.tmp.unlink(missing_ok=True)


COUNTS = ("scanned", "copied", "repaired", "diverged", "unchanged", "busy", "vanished", "failed")


def walk_files(top: Path, errors: list | None = None):
    """Every regular file under top, depth first in sorted order, never following or
    yielding symlinks. A directory or entry that cannot be read raises; with `errors`
    given, it is appended there as (path, error) and the walk goes on."""
    stack = [Path(top)]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as scan:
                entries = sorted(scan, key=lambda entry: entry.name)
        except OSError as error:
            if errors is None:
                raise
            errors.append((directory, error))
            continue
        subdirectories = []
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    subdirectories.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
            except OSError as error:
                if errors is None:
                    raise
                errors.append((Path(entry.path), error))
        stack.extend(reversed(subdirectories))


def capture_run(root: Path, manifest: Manifest, sources) -> tuple[dict, bool]:
    report = {}
    for source in sources:
        counts = dict.fromkeys(COUNTS, 0)
        errors, unreadable = [], []
        for path in walk_files(source.root, unreadable):
            relpath = path.relative_to(source.root).as_posix()
            counts["scanned"] += 1
            try:
                counts[capture_file(root, manifest, source.name, relpath, path).action] += 1
            except OSError as error:
                if not os.path.lexists(path):
                    counts["vanished"] += 1
                else:
                    counts["failed"] += 1
                    errors.append(f"{relpath}: {error}")
        for path, error in unreadable:
            counts["failed"] += 1
            errors.append(f"{path.relative_to(source.root).as_posix()}: unreadable: {error}")
        report[source.name] = {**counts, "errors": errors} if errors else counts
    return report, all(entry["failed"] == 0 for entry in report.values())
