"""Harness homes and their transcript stores, independent of hq's adapters."""
from dataclasses import dataclass
from pathlib import Path

SLUG = {"claude": "claude-code", "codex": "codex", "agy": "agy"}

__all__ = ["Home", "SLUG", "homes", "stores"]


@dataclass(frozen=True)
class Home:
    name: str       # the launch-config key
    harness: str    # the adapter alias: "claude", "codex" or "agy"
    kind: str       # "personal" or "work"
    path: Path


def homes(user_home: Path, harness: str | None = None) -> tuple[Home, ...]:
    by_harness = {
        "claude": (
            Home("claude", "claude", "personal", user_home / ".claude"),
            Home("claude-work", "claude", "work", user_home / ".claude-work"),
        ),
        "codex": (
            Home("codex", "codex", "personal", user_home / ".codex"),
            Home("codex-work", "codex", "work", user_home / ".codex-work"),
        ),
        "agy": (Home("agy", "agy", "personal", user_home / ".gemini" / "antigravity-cli"),),
    }
    if harness is not None:
        return by_harness[harness]
    return tuple(home for group in by_harness.values() for home in group)


def stores(home: Home) -> tuple[tuple[str, Path], ...]:
    paths = {
        "claude": (("live", home.path / "projects"),),
        "codex": (("live", home.path / "sessions"), ("archived", home.path / "archived_sessions")),
        "agy": (("live", home.path / "brain"),),
    }
    return paths[home.harness]
