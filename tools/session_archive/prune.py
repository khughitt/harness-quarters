"""Prune (spec §3.4): evaluate units against the manifest and obs, then delete eligible ones
only through the quarantine protocols."""
import errno
import fcntl
import hashlib
import os
import stat
import subprocess
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .capture import archived_file, capture_file, fsync_dir, mirror_path, open_nofollow, stat_of, walk_files
from .decide import INACTIVE_NS, FileFacts, ObsFile, Stat, is_transcript, unit_reason
from .inputs import InspectionFailed, Unit, claude_units, codex_units
from .manifest import MIRROR, Manifest
from .quarantine import QUARANTINE, _rename_at, inodes, leftovers, quarantine_dir, release, remove_empty_dirs


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


def run_codex_delete(codex_bin: str, home: Path, thread_id: str, timeout: float) -> bool:
    """True only for exit 0 within the timeout; the caller also checks the rollout is gone."""
    try:
        result = subprocess.run([codex_bin, "delete", "--force", thread_id],
                                env={**os.environ, "CODEX_HOME": str(home)}, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _same_inode(a: Path, b: Path) -> bool:
    with ExitStack() as cleanup:
        try:
            first = open_nofollow(a, os.O_PATH)
            cleanup.callback(os.close, first)
            second = open_nofollow(b, os.O_PATH)
            cleanup.callback(os.close, second)
        except (FileNotFoundError, NotADirectoryError):
            return False
        return os.path.samestat(os.fstat(first), os.fstat(second))


def delete_codex_unit(unit: Unit, ctx: Context) -> str:
    """Spec §3.4.3: lock and link, delete, freeze check, re-verify, release. The freeze check
    runs whenever the rollout's inode is no longer at its live path, whatever the exit status."""
    rollout, relpath, home = unit.paths[0], unit.files[0], unit.source.home
    stop = home / QUARANTINE
    qdir = quarantine_dir(home, ctx.run_id)
    link = qdir / rollout.name
    lock_path = home / "thread-writer-locks" / f"{unit.thread_id}.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with ExitStack() as cleanup:
            parent = open_nofollow(lock_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            cleanup.callback(os.close, parent)
            fd = os.open(lock_path.name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600,
                         dir_fd=parent)
            cleanup.callback(os.close, fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return "kept:busy"
            if not os.path.lexists(rollout):
                return "kept:vanished"
            reason = evaluate(unit, ctx, ctx.held())
            if reason:
                return f"kept:{reason}"
            source = open_nofollow(rollout, os.O_RDONLY | os.O_NONBLOCK)
            cleanup.callback(os.close, source)
            if not stat.S_ISREG(os.fstat(source).st_mode):
                return "failed:release"
            qdir.mkdir(parents=True, exist_ok=True)
            # Existing entries may survive a prior failed sync; persist them on every attempt.
            fsync_dir(home)
            fsync_dir(stop)
            target = open_nofollow(qdir, os.O_RDONLY | os.O_DIRECTORY)
            cleanup.callback(os.close, target)
            # linkat follows this held descriptor, never a replaced rollout path or parent.
            os.link(f"/proc/self/fd/{source}", link.name, dst_dir_fd=target, follow_symlinks=True)
            if not _same_inode(link, rollout):
                return "failed:release"
            os.fsync(target)
    except InspectionFailed:
        return "failed:uninspectable"
    except OSError:
        return "failed:release"
    ctx.hooks.before_delete(unit)
    try:
        if not _same_inode(link, rollout):
            return "failed:release"
    except OSError:
        return "failed:release"
    deleted = run_codex_delete(ctx.codex_bin, home, unit.thread_id, ctx.codex_timeout)
    succeeded = deleted and not os.path.lexists(rollout)

    def freeze(entry):
        try:
            if inodes([entry]) & ctx.held():
                return "failed:writer-live-quarantined"
        except InspectionFailed:
            return "failed:uninspectable-quarantined"
        return None

    refusal = None
    preserve = preserver(ctx, unit.source, relpath)

    def frozen_preserve(entry):
        nonlocal refusal
        # Release may reach rule (b) after a live path disappears between checks.
        refusal = freeze(entry)
        return refusal is None and preserve(entry)

    try:
        if not _same_inode(link, rollout):
            refusal = freeze(link)
            if refusal:
                return refusal
        if not succeeded:
            outcome = "failed:delete"
        else:
            info, sha, _ = _read_file(link)
            mirror = ctx.manifest.mirror(unit.source.name, relpath)
            changed = (mirror is None or (info.st_size, info.st_mtime_ns) != (mirror.size, mirror.mtime_ns)
                       or sha != mirror.sha256
                       or sha != _read_back(mirror_path(ctx.archive_root, unit.source.name, relpath)))
            outcome = "failed:changed" if changed else "pruned"
        with ExitStack() as cleanup:
            parent = open_nofollow(lock_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            cleanup.callback(os.close, parent)
            fd = os.open(lock_path.name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=parent)
            cleanup.callback(os.close, fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return "failed:writer-live-quarantined"
            # Rule (a) must remain true through unlink: exclude a resumed writer for
            # the entire release, including after its live-path snapshot.
            if not release(link, rollout, frozen_preserve):
                return refusal or ("failed:release" if outcome == "pruned" else f"{outcome}-quarantined")
        remove_empty_dirs(qdir, stop)
        return "failed:release" if os.path.lexists(link) else outcome
    except OSError:
        return "failed:release"


def repair_archive(unit: Unit, ctx: Context) -> str:
    """Recapture every file whose mirrored copy no longer reads back to its recorded hash."""
    for relpath in unit.files:
        mirror = ctx.manifest.mirror(unit.source.name, relpath)
        mirrored = mirror_path(ctx.archive_root, unit.source.name, relpath)
        if mirror is None or _read_back(mirrored) == mirror.sha256:
            continue
        try:
            outcome = capture_file(ctx.archive_root, ctx.manifest, unit.source.name, relpath,
                                   unit.source.root / relpath, force=True)
        except OSError:
            return "failed:archive-repair"
        if outcome.version is None or outcome.version.location != MIRROR or _read_back(mirrored) != mirror.sha256:
            return "failed:archive-repair"
    return "kept:archive-repaired"


def _precheck(unit: Unit, ctx: Context, held) -> str | None:
    try:
        return evaluate(unit, ctx, held)
    except FileNotFoundError:
        return "vanished"
    except OSError:
        return "unreadable"


def _decide(unit: Unit, reason: str | None, ctx: Context, apply: bool, codex_probed: bool) -> str:
    if reason == "unreadable":
        return "failed:unreadable"
    if reason == "archive-damaged":
        return repair_archive(unit, ctx) if apply else "kept:archive-damaged"
    if reason:
        return f"kept:{reason}"
    if not apply:
        return "eligible"
    if unit.source.kind == "codex" and not codex_probed:
        return "kept:codex-unprobed"
    ctx.hooks.after_precheck(unit)
    return delete_claude_unit(unit, ctx) if unit.source.kind == "claude" else delete_codex_unit(unit, ctx)


def prune_run(ctx: Context, sources, apply: bool, codex_probed: bool, report: dict) -> bool:
    """Fill `report` as the run goes, so a caller that catches an error keeps what was done.
    Phase one pre-checks every unit, reading the archive back, before anything is deleted:
    ArchiveUnreadable, InspectionFailed and unit discovery errors stop the run there. Phase
    two applies the protocols; an unexpected OSError stops it, and later units are kept."""
    left = leftovers([source.home for source in sources])
    if left:
        raise LeftoverQuarantine("quarantine not empty: " + ", ".join(str(path) for path in left))
    pruned = [source for source in sources if source.pruned]
    held = ctx.held()
    plan = [(unit, _precheck(unit, ctx, held))
            for source in pruned
            for unit in (claude_units(source) if source.kind == "claude" else codex_units(source))]
    for source in pruned:
        report[source.name] = {"totals": {}, "units": []}
    ok, stopped = True, False
    for unit, reason in plan:
        if stopped:
            outcome = "kept:stopped"
        else:
            try:
                outcome = _decide(unit, reason, ctx, apply, codex_probed)
            except OSError as error:
                outcome, stopped = "failed:io", True
                report.setdefault("errors", []).append(f"{unit.source.name}/{unit.key}: {error}")
        if outcome.startswith("failed") or outcome == "kept:codex-unprobed":
            ok = False
        entry = report[unit.source.name]
        entry["totals"][outcome] = entry["totals"].get(outcome, 0) + 1
        if outcome != "kept:active":
            entry["units"].append({"unit": unit.key, "outcome": outcome})
    return ok
