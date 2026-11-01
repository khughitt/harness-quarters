"""Codex: the `threads` table of `<home>/state_5.sqlite`.
Contract: docs/notes/2026-10-15-session-discovery-contract.md."""
import os
import sqlite3
from pathlib import Path

from hq_cli import color

from .model import Adapter, Home, Session, SourceError


def homes(user_home: Path) -> tuple[Home, ...]:
    return (
        Home("codex", "codex", "personal", user_home / ".codex"),
        Home("codex-work", "codex", "work", user_home / ".codex-work"),
    )


CODEX_COLUMNS = ("id", "rollout_path", "source", "thread_source", "archived", "preview", "cwd",
                 "recency_at_ms", "name", "title")


def check_thread(path: Path, row: dict) -> None:
    """Values the list relies on; anything else is schema drift and stops the list."""
    expected = {
        "id": lambda v: isinstance(v, str) and v != "",
        "source": lambda v: isinstance(v, str),
        "thread_source": lambda v: v is None or isinstance(v, str),
        "cwd": lambda v: isinstance(v, str) and os.path.isabs(v),
        "rollout_path": lambda v: isinstance(v, str) and os.path.isabs(v),
        "recency_at_ms": lambda v: isinstance(v, int),
        "archived": lambda v: v in (0, 1) and isinstance(v, int),
        "name": lambda v: v is None or isinstance(v, str),
        "title": lambda v: v is None or isinstance(v, str),
    }
    for column, valid in expected.items():
        if not valid(row[column]):
            raise SourceError(f"{path}: thread {row['id']!r} has {column} = {row[column]!r}; "
                              "Codex's state schema changed")


def read_codex(home: Home, archived: bool) -> tuple[list[Session], dict[str, int]]:
    """Threads with a preview (Codex's own visible indexes require one); archived ones only
    when asked. Codex's schema is internal: a missing column stops the list."""
    path = home.path / "state_5.sqlite"
    if not path.is_file():
        raise SourceError(f"{path}: Codex state database is missing")
    try:
        db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise SourceError(f"{path}: {error}") from None
    try:
        columns = {row[1] for row in db.execute("PRAGMA table_info(threads)")}
        if not columns:
            raise SourceError(f"{path}: no threads table; Codex's state schema changed")
        missing = [column for column in CODEX_COLUMNS if column not in columns]
        if missing:
            raise SourceError(f"{path}: threads lacks {', '.join(missing)}; Codex's state schema changed")
        query = f"SELECT {', '.join(CODEX_COLUMNS)} FROM threads WHERE preview <> ''"
        if not archived:
            query += " AND archived = 0"
        rows = db.execute(query).fetchall()
    except sqlite3.Error as error:
        raise SourceError(f"{path}: {error}") from None
    finally:
        db.close()
    sessions = []
    for row in rows:
        check_thread(path, dict(zip(CODEX_COLUMNS, row)))
    for tid, rollout, source, thread_source, archived_flag, _, cwd, recency_ms, name, title in rows:
        transcript = Path(rollout)
        # Subagents carry a JSON source, `exec` runs source "exec"; never has_user_event (always 0).
        if source not in ("cli", "vscode") or thread_source not in (None, "user"):
            excluded = "non-interactive"
        elif not transcript.is_file():
            excluded = "transcript gone"
        else:
            excluded = None
        sessions.append(Session(home=home, id=tid, cwd=cwd, recency_ms=recency_ms,
                                label=name if name and name.strip() else (title or ""),
                                transcript=transcript, excluded=excluded, archived=archived_flag == 1))
    return sessions, {}


def resume_argv(session: Session, flags: list[str]) -> list[str]:
    return ["codex", *flags, "resume", session.id]   # Codex takes its flags before the subcommand


ADAPTER = Adapter(
    slug="codex", alias="codex", colour=color.CODEX, home_variable="CODEX_HOME",
    homes=homes, list_sessions=read_codex, notes_segment=lambda notes: None,
    exclusion_reasons=("non-interactive", "transcript gone"), resume_argv=resume_argv,
    archive_sources=lambda user_home: (), episode_env="SESSION_LOGS_CODEX",
    episode_root=lambda user_home: user_home / ".codex" / "sessions")
