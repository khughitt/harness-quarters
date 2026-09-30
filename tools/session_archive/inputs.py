"""Prune inputs: obs's index state, open inodes, and session units (spec §3.2, §3.4)."""
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .capture import walk_files
from .config import Source
from .decide import ObsFile

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
SESSION_RE = re.compile(rf"^{UUID}$")
ROLLOUT_RE = re.compile(rf"^rollout-.*-({UUID})\.jsonl$")


class ObsUnavailable(Exception):
    """obs could not report its index state; prune stops before deleting anything."""


def _nonnegative(value) -> bool:
    return type(value) is int and value >= 0


def load_obs_state(command, runner=subprocess.run) -> dict[str, ObsFile]:
    """Validate obs's index-state contract and key its records by real path."""
    argv = [*command, "--json", "index-state"]
    try:
        result = runner(argv, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ObsUnavailable(f"obs index-state could not run: {error}") from error
    if result.returncode != 0:
        raise ObsUnavailable(f"obs index-state exited {result.returncode}: {result.stderr.strip()[:500]}")
    try:
        data = json.loads(result.stdout)
        schema, files = data["schema"], data["files"]
        if not _nonnegative(schema) or not isinstance(files, list):
            raise ValueError("schema must be an integer and files must be a list")
        state = {}
        for entry in files:
            path = entry["path"]
            size, mtime, offset = entry["size"], entry["mtime_ms"], entry["byte_offset"]
            partial, indexed, missing = entry["partial_tail"], entry["indexed_schema"], entry["missing_since_ms"]
            if not isinstance(path, str) or not os.path.isabs(path) or "\0" in path:
                raise ValueError("file path must be an absolute path without NUL")
            if not all(_nonnegative(value) for value in (size, mtime, offset)) or offset > size:
                raise ValueError("file size, mtime and offset must be nonnegative integers; offset must fit size")
            if not (type(partial) is bool or type(partial) is int and partial in (0, 1)):
                raise ValueError("partial_tail must be boolean or 0/1")
            if any(value is not None and not _nonnegative(value) for value in (indexed, missing)):
                raise ValueError("indexed_schema and missing_since_ms must be null or nonnegative integers")
            state[os.path.realpath(path)] = ObsFile(size, mtime, offset, bool(partial), indexed == schema,
                                                  missing is not None)
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
    """Inspect this user's descriptors. Skip disappearances; fail on other errors
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
        for entry in entries:
            try:
                info = os.stat(entry)
            except (FileNotFoundError, ProcessLookupError):
                continue
            except OSError as error:
                failure = failure or f"fd {entry.name}: {error}"
                continue
            held.add((info.st_dev, info.st_ino))
        if failure:
            name = comm(pid_dir)
            if name == "?" or name not in allow:
                blocked.append((pid_dir.name, name, failure))
    if blocked:
        raise InspectionFailed(blocked)
    return held


def tail_has_newline(path: Path, offset: int) -> bool:
    with open(path, "rb") as handle:
        handle.seek(offset)
        return b"\n" in handle.read()


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
    with os.scandir(source.root) as scan:
        projects = sorted(Path(p.path) for p in scan if p.is_dir(follow_symlinks=False))
    for project in projects:
        transcripts, directories = {}, {}
        with os.scandir(project) as scan:
            for entry in scan:
                path = Path(entry.path)
                if SESSION_RE.fullmatch(path.stem) and path.suffix == ".jsonl" and entry.is_file(follow_symlinks=False):
                    transcripts[path.stem] = path
                elif SESSION_RE.fullmatch(path.name) and entry.is_dir(follow_symlinks=False):
                    directories[path.name] = path
        for sid in sorted(transcripts.keys() | directories.keys()):
            paths = tuple(mapping[sid] for mapping in (transcripts, directories) if sid in mapping)
            files = []
            if sid in transcripts:
                files.append(transcripts[sid].relative_to(source.root).as_posix())
            if sid in directories:
                files.extend(member.relative_to(source.root).as_posix() for member in walk_files(directories[sid]))
            units.append(Unit(source, f"{project.name}/{sid}", paths, tuple(files)))
    return units


def codex_units(source: Source) -> list[Unit]:
    units = []
    for path in walk_files(source.root):
        match = ROLLOUT_RE.fullmatch(path.name)
        if match:
            relpath = path.relative_to(source.root).as_posix()
            units.append(Unit(source, relpath, (path,), (relpath,), match.group(1)))
    return units
