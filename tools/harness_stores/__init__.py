"""Per-harness session-store adapters; the registry order is the display order."""
from pathlib import Path

from . import claude, codex
from .model import Adapter, Home, Session, SourceError

ADAPTERS: tuple[Adapter, ...] = (claude.ADAPTER, codex.ADAPTER)

__all__ = ["ADAPTERS", "Adapter", "Home", "Session", "SourceError", "by_alias", "archive_sources", "by_slug", "homes"]


def by_alias(alias: str) -> Adapter:
    for adapter in ADAPTERS:
        if adapter.alias == alias:
            return adapter
    raise KeyError(f"no session-store adapter with alias {alias!r}")


def by_slug(slug: str) -> Adapter:
    for adapter in ADAPTERS:
        if adapter.slug == slug:
            return adapter
    raise KeyError(f"no session-store adapter with slug {slug!r}")


def homes(user_home: Path) -> tuple[Home, ...]:
    return tuple(home for adapter in ADAPTERS for home in adapter.homes(user_home))


def archive_sources(user_home: Path) -> tuple:
    return tuple(source for adapter in ADAPTERS for source in adapter.archive_sources(user_home))
