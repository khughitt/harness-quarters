"""Host gate, the fixed source table, and the archive lock (spec §3.1–3.2)."""
import fcntl
import os
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

MARKER = ".session-archive-root"
EX_HOST = 2
EX_TEMPFAIL = 75


class HostGateError(Exception):
    """This host has no usable archive; the command line exits 2 with the message."""


class LockHeld(Exception):
    """Another capture, prune, promote or probe holds the archive lock; exit 75."""


@dataclass(frozen=True)
class Source:
    name: str
    kind: str        # "claude" or "codex"
    home: Path       # the harness home: parent of the quarantine; CODEX_HOME for codex
    root: Path       # the live root the archive mirrors
    pruned: bool     # prune covers it (spec §3.2)


def sources(home: Path) -> tuple[Source, ...]:
    claude, claude_work = home / ".claude", home / ".claude-work"
    codex, codex_work = home / ".codex", home / ".codex-work"
    return (
        Source("claude", "claude", claude, claude / "projects", True),
        Source("claude-work", "claude", claude_work, claude_work / "projects", True),
        Source("codex", "codex", codex, codex / "sessions", True),
        Source("codex-archived", "codex", codex, codex / "archived_sessions", False),
        Source("codex-work", "codex", codex_work, codex_work / "sessions", False),
    )


@dataclass(frozen=True)
class Config:
    archive_root: Path
    obs_command: tuple[str, ...]
    uninspectable_ok: tuple[str, ...]   # comm names whose open files may go uninspected


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise HostGateError(f"session-archive is not configured on this host ({path} is missing)")
    data = tomllib.loads(path.read_text())
    for key in ("archive_root", "obs_command"):
        if key not in data:
            raise HostGateError(f"{path}: missing key {key!r}")
    command = data["obs_command"]
    if not (isinstance(command, list) and command and all(isinstance(part, str) for part in command)):
        raise HostGateError(f"{path}: obs_command must be a non-empty list of strings")
    root = Path(os.path.expanduser(data["archive_root"]))
    if not root.is_dir():
        raise HostGateError(f"archive_root {root} does not exist (is the backup disk mounted?)")
    if not (root / MARKER).is_file():
        raise HostGateError(f"archive_root {root} lacks the marker file {MARKER}")
    allowed = data.get("uninspectable_ok", [])
    if not (isinstance(allowed, list) and all(isinstance(name, str) for name in allowed)):
        raise HostGateError(f"{path}: uninspectable_ok must be a list of strings")
    return Config(root, tuple(os.path.expanduser(part) for part in command), tuple(allowed))


def check_sources(table) -> None:
    missing = [str(source.root) for source in table if not source.root.is_dir()]
    if missing:
        raise HostGateError("source root missing: " + ", ".join(missing))


@contextmanager
def archive_lock(root: Path):
    fd = os.open(root / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LockHeld(f"another session-archive run holds {root / '.lock'}") from None
        yield
    finally:
        os.close(fd)
