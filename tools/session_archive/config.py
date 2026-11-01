"""Host gate, the fixed source table, and the archive lock (spec §3.1–3.2)."""
import fcntl
import os
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .inputs import Unit
    from .prune import Context

MARKER = ".session-archive-root"
EX_HOST = 2
EX_TEMPFAIL = 75


class HostGateError(Exception):
    """This host has no usable archive; the command line exits 2 with the message."""


class LockHeld(Exception):
    """Another capture, prune, promote or probe holds the archive lock; exit 75."""


def ALL(relpath: str) -> bool:
    return True


@dataclass(frozen=True)
class PruneHooks:
    """What prune needs from a harness: unit discovery, the deletion protocol and the facts
    obs is compared against (spec §3.4)."""
    harness: str     # the obs harness label
    units: Callable[["Source"], list["Unit"]]
    delete_unit: Callable[["Unit", "Context"], str]
    is_transcript: Callable[[str], bool]    # whether obs indexes this path
    thread_id: Callable[[Path], str | None]
    needs_probe: bool         # deletion waits for the harness's delete probe
    thread_identity: bool     # obs's thread identity must match the filename


@dataclass(frozen=True)
class Source:
    name: str
    harness: str     # the adapter's canonical slug
    home: Path       # the harness home: parent of the quarantine
    root: Path       # the live root the archive mirrors
    prune: PruneHooks | None    # None: prune does not cover it (spec §3.2)
    required: bool = True
    append_only: bool = True
    descend: Callable[[str], bool] = ALL
    select: Callable[[str], bool] = ALL


@dataclass(frozen=True)
class Config:
    archive_root: Path
    obs_command: tuple[str, ...]
    uninspectable_ok: tuple[str, ...]   # comm names whose open files may go uninspected


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise HostGateError(f"session-archive is not configured on this host ({path} is missing)")
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise HostGateError(f"{path}: cannot read configuration: {error}") from None
    for key in ("archive_root", "obs_command"):
        if key not in data:
            raise HostGateError(f"{path}: missing key {key!r}")
    command = data["obs_command"]
    if not (isinstance(command, list) and command and all(isinstance(part, str) for part in command)):
        raise HostGateError(f"{path}: obs_command must be a non-empty list of strings")
    if not isinstance(data["archive_root"], str):
        raise HostGateError(f"{path}: archive_root must be a string")
    root = Path(os.path.expanduser(data["archive_root"]))
    if not root.is_dir():
        raise HostGateError(f"archive_root {root} does not exist (is the backup disk mounted?)")
    if not (root / MARKER).is_file():
        raise HostGateError(f"archive_root {root} lacks the marker file {MARKER}")
    allowed = data.get("uninspectable_ok", [])
    if not (isinstance(allowed, list) and all(isinstance(name, str) for name in allowed)):
        raise HostGateError(f"{path}: uninspectable_ok must be a list of strings")
    return Config(root, tuple(os.path.expanduser(part) for part in command), tuple(allowed))


def check_sources(table, captured: Callable[[str], bool]) -> dict[str, str]:
    """Refuse linked homes or roots and absent roots that must exist. Return the optional
    sources skipped because their root is absent and they were never captured."""
    linked = [str(path) for source in table for path in (source.home, source.root)
              if path.is_symlink()]
    if linked:
        raise HostGateError("source root is a symlink: " + ", ".join(linked))
    missing, skipped = [], {}
    for source in table:
        if os.path.lexists(source.root):
            continue
        if source.required or captured(source.name):
            missing.append(str(source.root))
        else:
            skipped[source.name] = "root absent, never captured"
    if missing:
        raise HostGateError("source root missing: " + ", ".join(missing))
    return skipped


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
