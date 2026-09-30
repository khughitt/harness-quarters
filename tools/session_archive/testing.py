"""Helpers shared by the session-archive tests."""
import os
import subprocess
import sys
import time
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "session-archive"
DAY_NS = 86_400 * 10**9


def write(path: Path, data: bytes, age_days: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if age_days is not None:
        age(path, age_days)
    return path


def age(path: Path, days: float) -> None:
    stamp = time.time_ns() - int(days * DAY_NS)
    os.utime(path, ns=(stamp, stamp))


def write_config(home: Path, archive: Path, obs_command=("true",), uninspectable_ok=()) -> Path:
    path = home / ".config" / "session-archive" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    command = ", ".join(f'"{part}"' for part in obs_command)
    allowed = ", ".join(f'"{name}"' for name in uninspectable_ok)
    path.write_text(f'archive_root = "{archive}"\nobs_command = [{command}]\nuninspectable_ok = [{allowed}]\n')
    return path


def run_tool(*args: str, home: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], env={**os.environ, "HOME": str(home)},
                          capture_output=True, text=True)


SID = "11111111-2222-4333-8444-555555555555"
TID = "019e0000-0000-7000-8000-000000000001"


def obs_for(*paths: Path) -> dict:
    """An obs index state in which each path is fully indexed at its current version."""
    from session_archive.decide import ObsFile
    state = {}
    for path in paths:
        info = os.stat(path)
        state[os.path.realpath(path)] = ObsFile(info.st_size, info.st_mtime_ns // 1_000_000,
                                                info.st_size, False, True, False)
    return state


def claude_session(root: Path, age_days: float = 40, project: str = "-p", sid: str = SID) -> Path:
    """A session with a transcript, a subagent transcript and a tool result, all aged."""
    write(root / project / sid / "subagents" / "agent-1.jsonl", b'{"sub":1}\n', age_days)
    write(root / project / sid / "tool-results" / "r.txt", b"result", age_days)
    return write(root / project / f"{sid}.jsonl", b'{"a":1}\n', age_days)


def codex_rollout(root: Path, age_days: float = 40, tid: str = TID,
                  data: bytes = b'{"type":"session_meta"}\n') -> Path:
    return write(root / "2026" / "01" / "01" / f"rollout-2026-01-01T00-00-00-{tid}.jsonl", data, age_days)


def uninspectable_comms() -> tuple[str, ...]:
    """comm names of this user's processes whose descriptors this host cannot read (on
    titan: systemd and (sd-pam)); tests allow them so they can watch processes they start."""
    from session_archive.inputs import InspectionFailed, open_inodes
    try:
        open_inodes()
    except InspectionFailed as failure:
        return tuple(sorted({name for _pid, name, _reason in failure.processes}))
    return ()


def lenient_open_inodes() -> set:
    from session_archive.inputs import open_inodes
    return open_inodes(allow=uninspectable_comms())
