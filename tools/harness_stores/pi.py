"""pi: one session tree per file at `<home>/sessions/<cwd-slug>/<timestamp>_<id>.jsonl`, the
`session` header first. pi keeps no index beside the files, so the header is the metadata.
Contract: docs/sessions.md."""
import json
import os
import re
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from harness_evidence.homes import homes as evidence_homes
from hq_cli import color

from .model import Adapter, Home, Session, SourceError

if TYPE_CHECKING:
    from session_archive.config import Source

DRIFT = "pi's session format changed"
VERSION = 3   # the format pi 1.1.0 writes; it migrates older files when it opens them
SESSION_FILE_RE = re.compile(r"[^/]+/[^/]+\.jsonl")   # <cwd-slug>/<file>, the only files pi lists


homes = partial(evidence_homes, harness="pi")


def session_files(root: Path) -> list[Path]:
    """The files pi's own session picker reads: `*.jsonl` directly inside each directory
    directly under `sessions/`. Anything else there is not a session to pi either."""
    if not root.is_dir():
        return []   # pi creates sessions/ with its first saved session
    return sorted(path for directory in root.iterdir() if directory.is_dir()
                  for path in directory.iterdir() if path.suffix == ".jsonl" and path.is_file())


def parse_time(path: Path, value) -> int:
    """Milliseconds since the epoch from the header's ISO 8601 timestamp with a zone."""
    if isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            moment = None
        if moment is not None and moment.tzinfo is not None:
            return int(moment.timestamp() * 1000)
    raise SourceError(f"{path}: header timestamp = {value!r}; {DRIFT}")


def read_header(path: Path, first: bytes) -> dict:
    """The first line, a version-3 `session` record with an id, a timestamp and an absolute
    cwd; anything else stops the listing."""
    try:
        header = json.loads(first)
    except (json.JSONDecodeError, UnicodeDecodeError):
        header = None
    if not isinstance(header, dict) or header.get("type") != "session":
        raise SourceError(f"{path}: the first line is not a session header; {DRIFT}")
    if header.get("version") != VERSION:
        raise SourceError(f"{path}: header version = {header.get('version')!r}, not {VERSION}; {DRIFT}")
    if not (isinstance(header.get("id"), str) and header["id"]):
        raise SourceError(f"{path}: header id = {header.get('id')!r}; {DRIFT}")
    cwd = header.get("cwd")
    if not (isinstance(cwd, str) and os.path.isabs(cwd)):
        raise SourceError(f"{path}: header cwd = {cwd!r}; {DRIFT}")
    parse_time(path, header.get("timestamp"))
    return header


def text_of(content) -> str:
    """A message's text as pi's picker shows it: a string, or its text blocks joined by spaces."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(block["text"] for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                        and isinstance(block.get("text"), str))
    return ""


def label_of(lines: list[bytes]) -> str:
    """pi's own rule: the latest `session_info` name (an empty one clears it), else the first
    user message with text. A line that is not JSON (an unfinished last line) is skipped,
    as pi skips it."""
    name, prompt = None, None
    for line in lines:
        if b'"session_info"' not in line and (prompt is not None or b'"user"' not in line):
            continue   # cheap filter: only these two kinds of line can change the label
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "session_info":
            value = entry.get("name")
            name = (value.strip() or None) if isinstance(value, str) else None
        elif prompt is None and entry.get("type") == "message":
            message = entry.get("message")
            if isinstance(message, dict) and message.get("role") == "user":
                prompt = text_of(message.get("content")) or None
    return name or prompt or ""


def read_pi(home: Home) -> tuple[list[Session], dict[str, int]]:
    """Every session file pi would list. Recency is the file's mtime: pi appends every entry,
    so it is the time of the last one (pi's picker orders by the last message instead)."""
    sessions = []
    for path in session_files(home.path / "sessions"):
        try:
            with path.open("rb") as handle:
                lines = handle.read().splitlines(keepends=True)
                mtime_ns = os.fstat(handle.fileno()).st_mtime_ns
        except OSError as error:
            raise SourceError(f"{path}: {error.strerror or error}") from None
        header = read_header(path, lines[0] if lines else b"")
        sessions.append(Session(home=home, id=header["id"], cwd=header["cwd"], recency_ms=mtime_ns // 1_000_000,
                                label=label_of(lines[1:]), transcript=path))
    return sessions, {}


def resume_argv(session: Session, flags: list[str]) -> list[str]:
    """pi opens a `--session` value containing `/` as that file, wherever its cwd directory is."""
    return ["pi", *flags, "--session", str(session.transcript)]


def archive_sources(user_home: Path) -> tuple["Source", ...]:
    """One optional, unpruned row: the session files in each cwd directory. pi appends to a
    file and rewrites it only to migrate an older format, which the archive keeps as a
    diverged version."""
    from session_archive.config import Source
    home = homes(user_home)[0].path
    return (Source("pi", "pi", home, home / "sessions", None, required=False, append_only=True,
                   descend=lambda relpath: "/" not in relpath,
                   select=lambda relpath: SESSION_FILE_RE.fullmatch(relpath) is not None),)


ADAPTER = Adapter(
    slug="pi", alias="pi", colour=color.PI, home_variable="PI_CODING_AGENT_DIR",
    homes=homes, list_sessions=lambda home, archived: read_pi(home), notes_segment=lambda notes: None,
    exclusion_reasons=(), resume_argv=resume_argv,
    short_id=lambda sid: sid[-8:],   # a UUIDv7 starts with its timestamp; the tail is random
    archive_sources=archive_sources, episode_env="SESSION_LOGS_PI",
    episode_root=lambda user_home: homes(user_home)[0].path / "sessions")
