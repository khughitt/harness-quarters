"""Pure decisions over plain records: capture actions and extension checks."""
from dataclasses import dataclass

from .manifest import MIRROR, Version


@dataclass(frozen=True)
class Stat:
    size: int
    mtime_ns: int


def capture_action(live: Stat, latest: Version | None, stored: Stat | None) -> str:
    """Return skip for an intact newest copy, repair for a damaged one, else copy."""
    if latest is None or (latest.size, latest.mtime_ns) != (live.size, live.mtime_ns):
        return "copy"
    return "skip" if stored == live else "repair"


def extends(size: int, prefix_sha256: str | None, mirror: Version | None) -> bool:
    """Whether these bytes contain the mirror version recorded in the manifest."""
    if mirror is None:
        return True
    return size >= mirror.size and prefix_sha256 == mirror.sha256
