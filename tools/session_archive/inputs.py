"""Prune inputs: obs's index state, open inodes, and session units (spec §3.2, §3.4)."""
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .capture import open_nofollow, walk_files
from .config import Source
from .decide import ObsFile

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
SESSION_RE = re.compile(rf"^{UUID}$")
ROLLOUT_RE = re.compile(rf"^rollout-.*-({UUID})\.jsonl$")


class ObsUnavailable(Exception):
    """obs could not report its index state; prune stops before deleting anything."""


def _nonnegative(value) -> bool:
    return type(value) is int and value >= 0


def _text(value) -> bool:
    return isinstance(value, str) and bool(value)


def _strings(value) -> bool:
    return isinstance(value, list) and all(_text(item) for item in value)


def _obs_file(entry, schema: int) -> tuple[str, ObsFile]:
    path, harness = entry["path"], entry["harness"]
    if (not isinstance(path, str) or not os.path.isabs(path) or "\0" in path
            or any(part in ("", ".", "..") for part in path.split("/")[1:])):
        raise ValueError("file path must be absolute, NUL-free and canonically spelled")
    if not _text(harness):
        raise ValueError("harness must be a nonempty string")
    size, mtime, inode, offset = (entry[key] for key in ("size", "mtime_ms", "inode", "byte_offset"))
    device, indexed, missing = (entry[key] for key in ("device", "indexed_schema", "missing_since_ms"))
    if not all(_nonnegative(value) for value in (size, mtime, inode, offset)) or offset > size:
        raise ValueError("file version and cursor must be nonnegative integers; cursor must fit size")
    if any(value is not None and not _nonnegative(value) for value in (device, indexed, missing)):
        raise ValueError("device, indexed_schema and missing_since_ms must be null or nonnegative integers")
    partial, ready, reasons = entry["partial_tail"], entry["ready"], entry["not_ready"]
    if type(partial) is not bool or type(ready) is not bool or not _strings(reasons):
        raise ValueError("partial_tail/ready must be booleans; not_ready must list nonempty strings")
    if ready != (not reasons):
        raise ValueError("ready must agree with not_ready")
    span = entry["indexed_span"]
    length, sha256 = None, None
    if span is not None:
        length, sha256 = span["length"], span["sha256"]
        if (not _nonnegative(length) or length != offset or not isinstance(sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", sha256) is None):
            raise ValueError("indexed_span must cover byte_offset with a lowercase SHA-256 digest")
    observed, observed_error = entry["observed"], entry["observed_error"]
    observed_version = None
    if observed is None:
        if not _text(observed_error):
            raise ValueError("an unavailable observation must have an error")
    else:
        observed_version = tuple(observed[key] for key in ("device", "inode", "size", "mtime_ms"))
        if observed_error is not None or not all(_nonnegative(value) for value in observed_version):
            raise ValueError("observed version must have nonnegative integers and no error")
    if not all(_nonnegative(entry[key]) for key in ("malformed_lines", "unrecognized_records")):
        raise ValueError("diagnostic counts must be nonnegative integers")
    identity = entry["identity"]
    thread, filename, conflicts, identity_current = None, None, [], True
    if harness == "claude-code" and identity is not None:
        raise ValueError("Claude identity must be null")
    if harness == "codex":
        thread, filename = identity["thread_id"], identity["filename_id"]
        ancestors, conflicts = identity["ancestors"], identity["conflicts"]
        if (any(value is not None and not _text(value) for value in (thread, filename))
                or not _strings(ancestors) or not _strings(conflicts)):
            raise ValueError("Codex identity IDs must be nonempty strings or null; ancestry/conflicts must list IDs")
        match = ROLLOUT_RE.fullmatch(Path(path).name)
        identity_current = bool(match) and thread == filename == match[1] and not conflicts
    if ready and (missing is not None or indexed != schema or device is None or partial
                  or offset != size or span is None or observed is None or not identity_current
                  or (device, inode, size, mtime) != observed_version):
        raise ValueError("ready contradicts exported file evidence")
    return path, ObsFile(
        size=size, mtime_ms=mtime, byte_offset=offset, partial_tail=partial,
        schema_current=indexed == schema, missing=missing is not None, harness=harness,
        device=device, inode=inode, ready=ready, not_ready=tuple(reasons),
        span_length=length, span_sha256=sha256, thread_id=thread, filename_id=filename,
        identity_conflicts=tuple(conflicts))


def load_obs_state(command, runner=subprocess.run) -> dict[str, ObsFile]:
    """Require contract-2 evidence; preserve exact path keys without following links."""
    argv = [*command, "--json", "index-state"]
    try:
        result = runner(argv, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ObsUnavailable(f"obs index-state could not run: {error}") from error
    if result.returncode != 0:
        raise ObsUnavailable(f"obs index-state exited {result.returncode}: {result.stderr.strip()[:500]}")
    try:
        data = json.loads(result.stdout)
        contract, schema, observed_at, files = (data[key] for key in ("contract", "schema", "observed_at_ms", "files"))
        if (type(contract) is not int or contract != 2 or not _nonnegative(schema)
                or not _nonnegative(observed_at) or not isinstance(files, list)):
            raise ValueError("expected contract 2, nonnegative schema/observation time and a file list")
        state = {}
        for entry in files:
            path, evidence = _obs_file(entry, schema)
            if path in state:
                raise ValueError(f"duplicate index-state path: {path}")
            state[path] = evidence
        return state
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise ObsUnavailable(f"obs index-state output does not match the contract: {error!r}") from error


class InspectionFailed(Exception):
    """Open-file inspection failed. `processes` contains (pid, comm, reason) entries."""

    def __init__(self, processes: list[tuple[str, str, str]]):
        self.processes = processes
        super().__init__("cannot inspect open files of: "
                         + "; ".join(f"{pid} ({name}): {reason}" for pid, name, reason in processes))


def comm(pid_dir: Path) -> str:
    try:
        return (pid_dir / "comm").read_text().strip()
    except (OSError, UnicodeDecodeError):
        return "?"


def open_inodes(allow: tuple[str, ...] = (), proc: Path = Path("/proc"),
                uid: int | None = None) -> set[tuple[int, int]]:
    """Inspect this user's descriptors, cwd and root. Skip disappearances; fail on other errors
    unless the process's readable comm is explicitly allowed."""
    uid = os.getuid() if uid is None else uid
    held, blocked = set(), []
    try:
        processes = list(proc.iterdir())
    except OSError as error:
        raise InspectionFailed([("?", "?", f"{proc}: {error}")]) from error
    for pid_dir in processes:
        if not pid_dir.name.isdigit():
            continue
        entries, failure = [], None
        try:
            if pid_dir.stat().st_uid != uid:
                continue
            entries = list((pid_dir / "fd").iterdir())
        except (FileNotFoundError, ProcessLookupError) as error:
            try:
                pid_dir.stat()
            except (FileNotFoundError, ProcessLookupError):
                continue
            except OSError as stat_error:
                error = stat_error
            failure = str(error)
        except OSError as error:
            failure = str(error)
        for entry in [*entries, pid_dir / "cwd", pid_dir / "root"]:
            try:
                info = os.stat(entry)
            except (FileNotFoundError, ProcessLookupError):
                continue
            except OSError as error:
                failure = failure or f"{entry.relative_to(pid_dir)}: {error}"
                continue
            held.add((info.st_dev, info.st_ino))
        if failure:
            name = comm(pid_dir)
            if name == "?" or name not in allow:
                blocked.append((pid_dir.name, name, failure))
    if blocked:
        raise InspectionFailed(blocked)
    return held


@dataclass(frozen=True)
class Unit:
    source: Source
    key: str                  # Claude: <project>/<session id>; Codex: rollout relative path
    paths: tuple[Path, ...]    # entries the deletion protocol moves or links
    files: tuple[str, ...]     # regular files relative to source.root
    thread_id: str | None = None


def claude_units(source: Source) -> list[Unit]:
    """Group UUID transcripts and adjacent UUID directories. Ignore memory and symlinks."""
    units = []
    root_fd = open_nofollow(source.root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with os.scandir(root_fd) as scan:
            projects = sorted(p.name for p in scan if p.is_dir(follow_symlinks=False))
        for name in projects:
            project = source.root / name
            transcripts, directories = {}, {}
            project_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
            try:
                with os.scandir(project_fd) as scan:
                    for entry in scan:
                        path = project / entry.name
                        if (SESSION_RE.fullmatch(path.stem) and path.suffix == ".jsonl"
                                and entry.is_file(follow_symlinks=False)):
                            transcripts[path.stem] = path
                        elif SESSION_RE.fullmatch(path.name) and entry.is_dir(follow_symlinks=False):
                            directories[path.name] = path
            finally:
                os.close(project_fd)
            for sid in sorted(transcripts.keys() | directories.keys()):
                paths = tuple(mapping[sid] for mapping in (transcripts, directories) if sid in mapping)
                files = []
                if sid in transcripts:
                    files.append(transcripts[sid].relative_to(source.root).as_posix())
                if sid in directories:
                    files.extend(member.relative_to(source.root).as_posix() for member in walk_files(directories[sid]))
                units.append(Unit(source, f"{project.name}/{sid}", paths, tuple(files)))
    finally:
        os.close(root_fd)
    return units


def codex_units(source: Source) -> list[Unit]:
    units = []
    for path in walk_files(source.root):
        match = ROLLOUT_RE.fullmatch(path.name)
        if match:
            relpath = path.relative_to(source.root).as_posix()
            units.append(Unit(source, relpath, (path,), (relpath,), match.group(1)))
    return units
