"""agy (Antigravity CLI): the `conversation_summaries` table of `<home>/conversation_summaries.db`
and the transcript at `<home>/brain/<id>/.system_generated/logs/transcript_full.jsonl`."""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from hq_cli import color

from .model import Adapter, Home, Session, SourceError

if TYPE_CHECKING:
    from session_archive.config import Source

AGY_COLUMNS = ("conversation_id", "title", "preview", "workspace_uris", "last_modified_time",
               "parent_conversation_id")
DRIFT = "agy's summary schema changed"
LOCK_TIMEOUT_S = 1.0   # a writer holding the database fails the listing rather than hanging it


def homes(user_home: Path) -> tuple[Home, ...]:
    return (Home("agy", "agy", "personal", user_home / ".gemini" / "antigravity-cli"),)


def parse_time(path: Path, cid: str, value) -> int:
    """Milliseconds since the epoch from agy's `2026-11-01 13:20:56.958312173+00:00`; the
    nanosecond fraction is cut to microseconds, which `fromisoformat` takes."""
    if isinstance(value, str):
        text = re.sub(r"(\.\d{6})\d+", r"\1", value)
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            moment = None
        if moment is not None and moment.tzinfo is not None:
            return int(moment.timestamp() * 1000)
    raise SourceError(f"{path}: conversation {cid!r} has last_modified_time = {value!r}; {DRIFT}")


def workspace(path: Path, cid: str, value) -> str | None:
    """The first workspace URI as a local path; None when the conversation has none."""
    try:
        uris = json.loads(value) if isinstance(value, str) else None
    except json.JSONDecodeError:
        uris = None
    if not (isinstance(uris, list) and all(isinstance(uri, str) for uri in uris)):
        raise SourceError(f"{path}: conversation {cid!r} has workspace_uris = {value!r}; {DRIFT}")
    if not uris:
        return None
    parsed = urlparse(uris[0])
    cwd = unquote(parsed.path)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost") or not cwd.startswith("/"):
        raise SourceError(f"{path}: conversation {cid!r} has workspace {uris[0]!r}, "
                          f"not a local file URI; {DRIFT}")
    return cwd


def read_agy(home: Home) -> tuple[list[Session], dict[str, int]]:
    """Every conversation row; subagents, vanished transcripts and rows with no workspace are
    marked excluded so they are counted, not listed."""
    path = home.path / "conversation_summaries.db"
    if not path.is_file():
        raise SourceError(f"{path}: agy summaries database is missing")
    try:
        db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=LOCK_TIMEOUT_S)
    except sqlite3.Error as error:
        raise SourceError(f"{path}: {error}") from None
    try:
        columns = {row[1] for row in db.execute("PRAGMA table_info(conversation_summaries)")}
        if not columns:
            raise SourceError(f"{path}: no conversation_summaries table; {DRIFT}")
        missing = [column for column in AGY_COLUMNS if column not in columns]
        if missing:
            raise SourceError(f"{path}: conversation_summaries lacks {', '.join(missing)}; {DRIFT}")
        rows = db.execute(f"SELECT {', '.join(AGY_COLUMNS)} FROM conversation_summaries").fetchall()
    except sqlite3.Error as error:
        raise SourceError(f"{path}: {error}") from None
    finally:
        db.close()
    sessions = []
    for cid, title, preview, uris, modified, parent in rows:
        if not (isinstance(cid, str) and cid):
            raise SourceError(f"{path}: a conversation has conversation_id = {cid!r}; {DRIFT}")
        for column, value in (("title", title), ("preview", preview), ("parent_conversation_id", parent)):
            if not isinstance(value, str):
                raise SourceError(f"{path}: conversation {cid!r} has {column} = {value!r}; {DRIFT}")
        cwd = workspace(path, cid, uris)
        transcript = home.path / "brain" / cid / ".system_generated" / "logs" / "transcript_full.jsonl"
        if parent:
            excluded = "non-interactive"
        elif not transcript.is_file():
            excluded = "transcript gone"
        elif cwd is None:
            excluded = "no workspace"
        else:
            excluded = None
        sessions.append(Session(home=home, id=cid, cwd=cwd, recency_ms=parse_time(path, cid, modified),
                                label=title or preview, transcript=transcript, excluded=excluded))
    return sessions, {}


def resume_argv(session: Session, flags: list[str]) -> list[str]:
    return ["agy", *flags, "--conversation", session.id]


TRANSCRIPT_RE = re.compile(r"[^/]+/\.system_generated/logs/transcript(_full)?\.jsonl")


def descend_brain(relpath: str) -> bool:
    """Only <id>, <id>/.system_generated and <id>/.system_generated/logs hold transcripts."""
    parts = relpath.split("/")
    return len(parts) == 1 or (parts[1:] in ([".system_generated"], [".system_generated", "logs"])
                               and len(parts) in (2, 3))


def archive_sources(user_home: Path) -> tuple["Source", ...]:
    """Two optional, unpruned rows: the brain transcripts (append-only) and the summaries
    database (rewritten in place, so the mirror rotates it)."""
    from session_archive.config import Source
    home = homes(user_home)[0].path
    return (
        Source("agy", "agy", home, home / "brain", None, required=False, append_only=True,
               descend=descend_brain, select=lambda relpath: TRANSCRIPT_RE.fullmatch(relpath) is not None),
        Source("agy-summaries", "agy", home, home, None, required=False, append_only=False,
               descend=lambda relpath: False, select=lambda relpath: relpath == "conversation_summaries.db"),
    )


ADAPTER = Adapter(
    slug="agy", alias="agy", colour=color.AGY, home_variable=None,
    homes=homes, list_sessions=lambda home, archived: read_agy(home), notes_segment=lambda notes: None,
    exclusion_reasons=("non-interactive", "transcript gone", "no workspace"), resume_argv=resume_argv,
    archive_sources=archive_sources, episode_env="SESSION_LOGS_AGY",
    episode_root=lambda user_home: homes(user_home)[0].path)
