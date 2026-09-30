"""Prune (spec §3.4): evaluate units against the manifest and obs, then delete eligible ones
only through the quarantine protocols."""
import errno
import hashlib
import os
import stat
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .capture import archived_file, capture_file, mirror_path, open_nofollow, stat_of, walk_files
from .decide import INACTIVE_NS, FileFacts, ObsFile, Stat, is_transcript, unit_reason
from .inputs import InspectionFailed, Unit
from .manifest import Manifest
from .quarantine import QUARANTINE, _rename_at, inodes, quarantine_dir, release, remove_empty_dirs


class ArchiveUnreadable(Exception):
    """An archived copy could not be read back; the run stops before deleting anything."""


class LeftoverQuarantine(Exception):
    """A quarantine holds files from an earlier run; a person looks first (spec §3.4.4)."""


def _noop(unit):
    pass


@dataclass
class Hooks:
    """Seams between protocol steps for the deletion-window tests; no-ops in production."""
    after_precheck: Callable[[Unit], None] = _noop
    after_quarantine: Callable[[Unit], None] = _noop
    before_delete: Callable[[Unit], None] = _noop


@dataclass
class Context:
    archive_root: Path
    manifest: Manifest
    obs: dict[str, ObsFile]
    held: Callable[[], set[tuple[int, int]]]   # fresh snapshot of open inodes
    now_ns: int
    run_id: str
    codex_bin: str = "codex"
    codex_timeout: float = 120
    hooks: Hooks = field(default_factory=Hooks)


def _read_file(path: Path, offset: int | None = None):
    """Read one regular inode, rejecting symlinks and changes during the read."""
    with os.fdopen(open_nofollow(path, os.O_RDONLY | os.O_NONBLOCK), "rb") as reader:
        info = os.fstat(reader.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EINVAL, "not a regular file", str(path))
        sha = hashlib.file_digest(reader, "sha256").hexdigest()
        tail = False
        if offset is not None:
            reader.seek(offset)
            tail = b"\n" in reader.read()
        fd = open_nofollow(path, os.O_PATH)
        try:
            current = os.fstat(fd)
        finally:
            os.close(fd)
        if (not os.path.samestat(info, current)
                or (info.st_size, info.st_mtime_ns) != (current.st_size, current.st_mtime_ns)):
            raise OSError(errno.ESTALE, "file changed during read", str(path))
    return info, sha, tail


def _read_back(path: Path) -> str | None:
    try:
        return _read_file(path)[1]
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ArchiveUnreadable(f"cannot read back {path}: {error}") from error


def _facts(source, relpath: str, ctx: Context, held) -> FileFacts:
    path = source.root / relpath
    mirror = ctx.manifest.mirror(source.name, relpath)
    obs = ctx.obs.get(os.path.realpath(path))
    info, sha, tail = _read_file(path, obs.byte_offset if obs else None)
    return FileFacts(
        relpath=relpath,
        live=Stat(info.st_size, info.st_mtime_ns),
        live_sha256=sha,
        mirror=mirror,
        latest=ctx.manifest.latest(source.name, relpath),
        mirror_sha256=_read_back(mirror_path(ctx.archive_root, source.name, relpath)) if mirror else None,
        transcript=is_transcript(source.kind, relpath),
        obs=obs,
        tail_has_newline=tail,
        open=(info.st_dev, info.st_ino) in held)


def evaluate(unit: Unit, ctx: Context, held) -> str | None:
    """The first condition the unit fails, or None. An active unit is rejected on its stat
    alone, before any hashing."""
    for relpath in unit.files:
        if ctx.now_ns - stat_of(unit.source.root / relpath).mtime_ns <= INACTIVE_NS:
            return "active"
    return unit_reason([_facts(unit.source, relpath, ctx, held) for relpath in unit.files], ctx.now_ns)


def preserver(ctx: Context, source, relpath: str) -> Callable[[Path], bool]:
    """Rule (b) for one file: true once the archive holds the entry's exact bytes, verified by
    read-back, recapturing the entry first when it does not."""
    def preserve(entry: Path) -> bool:
        try:
            sha = _read_file(entry)[1]
            if any(v.sha256 == sha and _read_back(archived_file(ctx.archive_root, v)) == sha
                   for v in ctx.manifest.rows(source.name, relpath)):
                return True
            outcome = capture_file(ctx.archive_root, ctx.manifest, source.name, relpath, entry, force=True)
            return (outcome.version is not None and outcome.version.sha256 == sha
                    and _read_back(archived_file(ctx.archive_root, outcome.version)) == sha)
        except (OSError, ArchiveUnreadable):
            return False
    return preserve


def _move(src: Path, dst: Path) -> None:
    """No-replace rename through held parents; a parent swap never follows a symlink."""
    with ExitStack() as cleanup:
        source = open_nofollow(src.parent, os.O_RDONLY | os.O_DIRECTORY)
        cleanup.callback(os.close, source)
        target = open_nofollow(dst.parent, os.O_RDONLY | os.O_DIRECTORY)
        cleanup.callback(os.close, target)
        _rename_at(source, src.name, target, dst.name)


def _restore(moved, qdir: Path, stop: Path, outcome: str) -> str:
    recreated = False
    for live, quarantined in moved:
        try:
            _move(quarantined, live)
        except FileExistsError:
            recreated = True
        except OSError:
            return "failed:release"
    remove_empty_dirs(qdir, stop)
    return "failed:recreated" if recreated else outcome


def delete_claude_unit(unit: Unit, ctx: Context) -> str:
    """Spec §3.4.2: quarantine, settle, re-verify, recreation check, remove."""
    stop = unit.source.home / QUARANTINE
    qdir = quarantine_dir(unit.source.home, ctx.run_id) / unit.key
    qdir.mkdir(parents=True)
    moved = []
    for live in unit.paths:
        quarantined = qdir / live.name
        try:
            _move(live, quarantined)
        except FileNotFoundError:
            return _restore(moved, qdir, stop, "kept:vanished")
        except OSError:
            return _restore(moved, qdir, stop, "failed:release")
        moved.append((live, quarantined))
    ctx.hooks.after_quarantine(unit)
    try:
        holders = ctx.held()
    except InspectionFailed:
        return _restore(moved, qdir, stop, "failed:uninspectable")
    try:
        if inodes([q for _, q in moved]) & holders:
            return _restore(moved, qdir, stop, "kept:open")
        project = unit.key.split("/")[0]
        present = {f"{project}/{p.relative_to(qdir).as_posix()}": p for p in walk_files(qdir)}
        changed = []
        for rel, path in sorted(present.items()):
            info, sha, _ = _read_file(path)
            mirror = ctx.manifest.mirror(unit.source.name, rel)
            if (mirror is None or (mirror.size, mirror.mtime_ns) != (info.st_size, info.st_mtime_ns)
                    or mirror.sha256 != sha
                    or _read_back(mirror_path(ctx.archive_root, unit.source.name, rel)) != sha):
                changed.append(rel)
    except OSError:
        return "failed:release"
    if changed:
        for rel in changed:
            try:
                outcome = capture_file(ctx.archive_root, ctx.manifest, unit.source.name, rel,
                                       present[rel], force=True)
            except OSError:
                return "failed:recapture"
            if outcome.version is None or not preserver(ctx, unit.source, rel)(present[rel]):
                return "failed:recapture"
        return _restore(moved, qdir, stop, "kept:changed")
    ctx.hooks.before_delete(unit)
    session_dir = unit.source.root / unit.key
    if any(os.path.lexists(path) for path in (session_dir, session_dir.with_suffix(".jsonl"))):
        return "failed:recreated"
    for rel, quarantined in sorted(present.items()):
        try:
            if not release(quarantined, unit.source.root / rel, preserver(ctx, unit.source, rel)):
                return "failed:release"
        except OSError:
            return "failed:release"
    remove_empty_dirs(qdir, stop)
    return "failed:release" if os.path.lexists(qdir) else "pruned"
