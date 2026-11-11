"""Shared shapes of the session-store adapters: homes, sessions and the adapter record."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from harness_evidence.homes import Home
from hq_cli import color


class SourceError(Exception):
    """A source exists but cannot be read as expected; listing stops rather than empties."""


@dataclass(frozen=True)
class Session:
    home: Home
    id: str
    cwd: str | None
    recency_ms: int
    label: str
    transcript: Path
    excluded: str | None = None   # an adapter's exclusion reason: counted, not listed
    archived: bool = False        # an archived Codex thread, listed only under --archived


@dataclass(frozen=True)
class Adapter:
    slug: str                     # canonical harness slug (harnesses.toml, [harnesses.<slug>])
    alias: str                    # the `hq sessions --harness` value
    colour: color.Colour
    home_variable: str | None     # environment variable naming a work home
    homes: Callable[[Path], tuple[Home, ...]]
    list_sessions: Callable[[Home, bool], tuple[list[Session], dict[str, int]]]
    notes_segment: Callable[[dict[str, int]], str | None]
    exclusion_reasons: tuple[str, ...]
    resume_argv: Callable[[Session, list[str]], list[str]]
    short_id: Callable[[str], str]           # the id column: eight characters that tell rows apart
    archive_sources: Callable[[Path], tuple]
    episode_env: str              # environment variable overriding the episode root
    episode_root: Callable[[Path], Path]   # default episode root under a user home
