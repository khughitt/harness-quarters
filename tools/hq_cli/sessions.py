"""Recent sessions read from each harness's own metadata; hq keeps no index of its own.

Claude Code: `<home>/history.jsonl`, one line per typed prompt, and the transcript at
`<home>/projects/*/<id>.jsonl`. Codex: the `threads` table of `<home>/state_5.sqlite`.
Contract: docs/notes/2026-10-15-session-discovery-contract.md."""
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class SourceError(Exception):
    """A source exists but cannot be read as expected; listing stops rather than empties."""


@dataclass(frozen=True)
class Home:
    name: str       # the launch-config key
    harness: str    # "claude" or "codex"
    kind: str       # "personal" or "work"
    path: Path


def homes(user_home: Path) -> tuple[Home, ...]:
    """The four homes tools/session_archive/config.py:sources archives."""
    return (
        Home("claude", "claude", "personal", user_home / ".claude"),
        Home("claude-work", "claude", "work", user_home / ".claude-work"),
        Home("codex", "codex", "personal", user_home / ".codex"),
        Home("codex-work", "codex", "work", user_home / ".codex-work"),
    )


@dataclass(frozen=True)
class Session:
    home: Home
    id: str
    cwd: str
    recency_ms: int
    label: str
    transcript: Path
    excluded: str | None = None   # "non-interactive" or "transcript gone": counted, not listed


@dataclass
class Skipped:
    """Claude history lines that name no session."""
    without_id: int = 0
    malformed: int = 0


def claude_recency_ms(transcript: Path, fallback_ms: int) -> int:
    """The transcript's mtime (last activity, as Codex's recency); the last prompt's
    timestamp only when the stat fails."""
    try:
        return os.stat(transcript).st_mtime_ns // 1_000_000
    except OSError:
        return fallback_ms


def claude_transcripts(projects: Path) -> dict[str, Path]:
    """`projects/*/<id>.jsonl` by directory entry: a few transcripts sit under a directory
    other than the cwd's slug, so the slug is never computed."""
    found: dict[str, Path] = {}
    if not projects.is_dir():
        return found
    for directory in sorted(os.scandir(projects), key=lambda entry: entry.name):
        if not directory.is_dir(follow_symlinks=False):
            continue
        for entry in os.scandir(directory.path):
            if entry.name.endswith(".jsonl") and entry.is_file(follow_symlinks=False):
                found.setdefault(entry.name[:-len(".jsonl")], Path(entry.path))
    return found


def read_claude(home: Home) -> tuple[list[Session], Skipped]:
    path = home.path / "history.jsonl"
    if not path.is_file():
        raise SourceError(f"{path}: Claude Code history is missing")
    skipped = Skipped()
    first: dict[str, dict] = {}
    last: dict[str, dict] = {}
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped.malformed += 1
                continue
            if not isinstance(record, dict):
                skipped.malformed += 1
                continue
            sid = record.get("sessionId")
            if sid is None:
                skipped.without_id += 1
                continue
            if not (isinstance(sid, str) and sid and isinstance(record.get("project"), str)
                    and isinstance(record.get("timestamp"), int)):
                skipped.malformed += 1
                continue
            first.setdefault(sid, record)
            last[sid] = record
    transcripts = claude_transcripts(home.path / "projects")
    sessions = []
    for sid, opening in first.items():
        latest = last[sid]
        transcript = transcripts.get(sid)
        display = opening.get("display")
        sessions.append(Session(
            home=home, id=sid, cwd=latest["project"],
            recency_ms=claude_recency_ms(transcript, latest["timestamp"]) if transcript else latest["timestamp"],
            label=display if isinstance(display, str) else "",
            transcript=transcript or home.path / "projects" / "*" / f"{sid}.jsonl",
            excluded=None if transcript else "transcript gone"))
    return sessions, skipped


CODEX_COLUMNS = ("id", "rollout_path", "source", "thread_source", "archived", "preview", "cwd",
                 "recency_at_ms", "name", "title")


def read_codex(home: Home, archived: bool) -> list[Session]:
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
    for tid, rollout, source, thread_source, _, _, cwd, recency_ms, name, title in rows:
        transcript = Path(rollout)
        # Subagents carry a JSON source, `exec` runs source "exec"; never has_user_event (always 0).
        if source not in ("cli", "vscode") or thread_source not in (None, "user"):
            excluded = "non-interactive"
        elif not transcript.exists():
            excluded = "transcript gone"
        else:
            excluded = None
        sessions.append(Session(home=home, id=tid, cwd=cwd, recency_ms=recency_ms,
                                label=name if name and name.strip() else (title or ""),
                                transcript=transcript, excluded=excluded))
    return sessions
