"""Claude Code: `<home>/history.jsonl`, one line per typed prompt, and the transcript at
`<home>/projects/*/<id>.jsonl`. Contract: docs/notes/2026-10-15-session-discovery-contract.md."""
import json
import os
from pathlib import Path

from hq_cli import color

from .model import Adapter, Home, Session, SourceError


def homes(user_home: Path) -> tuple[Home, ...]:
    return (
        Home("claude", "claude", "personal", user_home / ".claude"),
        Home("claude-work", "claude", "work", user_home / ".claude-work"),
    )


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
    try:
        for directory in sorted(os.scandir(projects), key=lambda entry: entry.name):
            if not directory.is_dir(follow_symlinks=False):
                continue
            for entry in os.scandir(directory.path):
                if entry.name.endswith(".jsonl") and entry.is_file(follow_symlinks=False):
                    found.setdefault(entry.name[:-len(".jsonl")], Path(entry.path))
    except OSError as error:
        raise SourceError(f"{projects}: cannot list transcripts: {error}") from None
    return found


def read_claude(home: Home, archived: bool = False) -> tuple[list[Session], dict[str, int]]:
    path = home.path / "history.jsonl"
    if not path.is_file():
        raise SourceError(f"{path}: Claude Code history is missing")
    without_id = malformed = 0
    first: dict[str, dict] = {}
    last: dict[str, dict] = {}
    try:
        # Split on newlines only: str.splitlines also breaks at U+2028, which JSON strings may hold.
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            lines = handle.read().split("\n")
    except OSError as error:
        raise SourceError(f"{path}: cannot read Claude Code history: {error}") from None
    if lines[-1] == "":
        lines.pop()   # the final newline
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(record, dict):
            malformed += 1
            continue
        sid = record.get("sessionId")
        if sid is None:
            without_id += 1
            continue
        project = record.get("project")
        if not (isinstance(sid, str) and sid and isinstance(project, str) and os.path.isabs(project)
                and isinstance(record.get("timestamp"), int)):
            malformed += 1
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
    return sessions, {"without_id": without_id, "malformed": malformed}


def notes_segment(notes: dict[str, int]) -> str:
    return f"skipped claude history lines: {notes['without_id']} without sessionId, {notes['malformed']} malformed"


def resume_argv(session: Session, flags: list[str]) -> list[str]:
    return ["claude", *flags, "--resume", session.id]


ADAPTER = Adapter(
    slug="claude-code", alias="claude", colour=color.CLAUDE, home_variable="CLAUDE_CONFIG_DIR",
    homes=homes, list_sessions=read_claude, notes_segment=notes_segment,
    exclusion_reasons=("transcript gone",), resume_argv=resume_argv,
    archive_sources=lambda user_home: (), episode_env="SESSION_LOGS_CLAUDE",
    episode_root=lambda user_home: user_home / ".claude" / "projects")
