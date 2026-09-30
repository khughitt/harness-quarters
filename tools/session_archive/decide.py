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


INACTIVE_NS = 30 * 86_400 * 10**9


@dataclass(frozen=True)
class ObsFile:
    size: int
    mtime_ms: int
    byte_offset: int
    partial_tail: bool
    schema_current: bool
    missing: bool


@dataclass(frozen=True)
class FileFacts:
    relpath: str
    live: Stat
    live_sha256: str
    mirror: Version | None
    latest: Version | None
    mirror_sha256: str | None
    transcript: bool
    obs: ObsFile | None
    tail_has_newline: bool
    open: bool


def is_transcript(kind: str, relpath: str) -> bool:
    """Whether obs indexes this Claude or Codex path."""
    if not relpath.endswith(".jsonl"):
        return False
    if kind == "codex":
        return True
    parts = relpath.split("/")
    return len(parts) == 2 or (len(parts) == 4 and parts[2] == "subagents")


def file_reason(f: FileFacts, now_ns: int) -> str | None:
    """Return the first prune condition this file fails, or None if it passes."""
    if now_ns - f.live.mtime_ns <= INACTIVE_NS:
        return "active"
    live_key = (f.live.size, f.live.mtime_ns)
    if f.latest is not None and f.latest.location != MIRROR and (f.latest.size, f.latest.mtime_ns) == live_key:
        return "diverged"
    if f.mirror is None or (f.mirror.size, f.mirror.mtime_ns) != live_key or f.live_sha256 != f.mirror.sha256:
        return "uncaptured"
    if f.mirror_sha256 != f.mirror.sha256:
        return "archive-damaged"
    if f.transcript:
        o = f.obs
        if o is None or o.missing:
            return "unindexed"
        read_all = o.byte_offset == f.live.size or (
            o.partial_tail and o.byte_offset < f.live.size and not f.tail_has_newline)
        if (o.size, o.mtime_ms) != (f.live.size, f.live.mtime_ns // 1_000_000) or not o.schema_current or not read_all:
            return "index-stale"
    if f.open:
        return "open"
    return None


def unit_reason(files: list[FileFacts], now_ns: int) -> str | None:
    """Return the first failure across a unit; keep a unit with no files."""
    if not files:
        return "empty"
    for facts in files:
        reason = file_reason(facts, now_ns)
        if reason:
            return reason
    return None
