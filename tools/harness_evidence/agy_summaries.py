"""agy's conversation_summaries.db, read only, as one snapshot of facts per transcript.

The database sits in the agy home beside `brain/`. It is opened through a read-only SQLite
URI and never written. A conversation resolves to its facts, or to a status when it has no
row (`no_summary_row`) or the database cannot be read (`summaries_unreadable`). There is no
fallback to a heuristic from the transcript: unknown stays unknown.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import unquote, urlparse

DATABASE = "conversation_summaries.db"
TABLE = "conversation_summaries"
KEY = "conversation_id"
COLUMNS = ("conversation_id", "parent_conversation_id", "workspace_uris", "agent_name")
FACTS = ("parent", "subagent", "cwd", "agent_name")
NAME = "agy_conversation_summaries"
DECLARATION = {
    "path": DATABASE, "relative_to": "home", "table": TABLE, "key": KEY, "columns": list(COLUMNS),
    "open": "read-only SQLite URI (mode=ro)",
    "fingerprint": ("sha256 of the canonical JSON of the resolved facts {parent, subagent, cwd, "
                    "agent_name}, or of {\"status\": \"no_summary_row\"} or "
                    "{\"status\": \"summaries_unreadable\"}"),
}


class _Unreadable(Exception):
    """The database, or a row it returned, is not in the shape agy writes."""


def _cwd(workspace_uris) -> str | None:
    uris = json.loads(workspace_uris)
    if not isinstance(uris, list) or not all(isinstance(uri, str) for uri in uris):
        raise _Unreadable("workspace_uris is not a JSON array of strings")
    if not uris:
        return None
    parsed = urlparse(uris[0])
    return unquote(parsed.path) if parsed.scheme == "file" and parsed.path else None


def resolve(database: Path, conversation: str) -> dict:
    """`{"status": "resolved", "facts": {...}}`, or `{"status": <reason>}` with no facts."""
    try:
        connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    except (sqlite3.Error, ValueError):
        return {"status": "summaries_unreadable"}
    try:
        row = connection.execute(
            f"SELECT {', '.join(COLUMNS[1:])} FROM {TABLE} WHERE {KEY} = ?", (conversation,)).fetchone()
        if row is None:
            return {"status": "no_summary_row"}
        parent, workspace_uris, agent_name = row
        if not all(isinstance(value, str) for value in row):
            raise _Unreadable("a summary column is not text")
        return {"status": "resolved", "facts": {
            "parent": parent or None, "subagent": bool(parent), "cwd": _cwd(workspace_uris),
            "agent_name": agent_name}}
    except (sqlite3.Error, ValueError, _Unreadable):
        return {"status": "summaries_unreadable"}
    finally:
        connection.close()


def fingerprint(resolved: dict) -> str:
    """Spec §4.2: the sha256 of the canonical JSON of the facts, or of the status object."""
    value = resolved["facts"] if resolved["status"] == "resolved" else {"status": resolved["status"]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()
