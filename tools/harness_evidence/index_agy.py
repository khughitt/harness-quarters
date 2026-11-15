"""The agy index adapter: discovery facts, the summaries side input and the header.

Each conversation is brain/<id>/.system_generated/logs/transcript_full.jsonl; its
transcript.jsonl beside it is a truncated mirror and is refused here. Path facts come from
one read of conversation_summaries.db per call (spec rev 2 §4.2); callers resolve them once
per file and derive the side-input fingerprint from that one snapshot.
"""
from datetime import datetime
import json
from pathlib import Path, PurePosixPath

from . import agy_summaries
from .discover import AGY_FULL, AGY_MIRROR
from .header import _lines, _proof
from .lines import ref

__all__ = ["path_facts", "side_inputs", "header", "refusal", "SIDE_INPUTS"]

SIDE_INPUTS = {agy_summaries.NAME: agy_summaries.DECLARATION}
_RULE = "agy_conversation_summaries"


def _conversation(place) -> str:
    return PurePosixPath(place.relpath).parts[1]


def _home(place) -> Path:
    """The agy home: the logical path less its `brain/...` relpath."""
    return place.path.parents[len(PurePosixPath(place.relpath).parts) - 1]


def refusal(place) -> str | None:
    if place.path.name == AGY_MIRROR:
        return f"agy index reads {AGY_FULL}"
    return None


def path_facts(place) -> dict:
    """Summary facts for the conversation, read once from the database."""
    resolved = agy_summaries.resolve(_home(place) / agy_summaries.DATABASE, _conversation(place))
    facts = resolved.get("facts") or dict.fromkeys(agy_summaries.FACTS)
    return {**facts, "reason": None if resolved["status"] == "resolved" else resolved["status"],
            "basis": "native", "rule": _RULE, "ref": ref(place)}


def side_inputs(facts: dict) -> dict:
    """The fingerprint of the snapshot `facts` came from."""
    resolved = ({"status": facts["reason"]} if facts["reason"] is not None else
                {"status": "resolved", "facts": {name: facts[name] for name in agy_summaries.FACTS}})
    return {agy_summaries.NAME: agy_summaries.fingerprint(resolved)}


def _at_ms(value) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return int(when.timestamp() * 1000) if when.tzinfo is not None else None


def header(place, handle, *, size, envelope, result):
    """Session from the brain directory, start from the first `created_at` in fifty lines,
    and cwd, parent and subagent from one summaries snapshot (spec rev 2 §4.6)."""
    facts = path_facts(place)
    revision = envelope["decoder"]["revision"]
    session = _conversation(place)
    result["header"].update(session=session, cwd=facts["cwd"], parent=facts["parent"],
                            subagent=facts["subagent"])
    result["provenance"]["session"] = {"native_paths": [], "basis": "convention",
                                       "rule": "agy_brain_directory", "revision": revision,
                                       "ref": ref(place)}
    for name, column in (("cwd", "workspace_uris"), ("parent", "parent_conversation_id"),
                         ("subagent", "parent_conversation_id")):
        result["provenance"][name] = {
            "native_paths": [f"{agy_summaries.TABLE}.{column}"], "basis": "native", "rule": _RULE,
            "revision": revision, "ref": ref(place), "reason": facts["reason"]}
    lines = _lines(handle, size)
    for number in range(1, 51):
        item = next(lines, None)
        if item is None:
            break
        offset, raw = item
        try:
            record = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            raise ValueError("header source record must be an object")
        start = _at_ms(record.get("created_at"))
        if start is not None:
            result["header"]["start_ms"] = start
            result["provenance"]["start_ms"] = _proof(place, number, offset, raw, envelope, ["created_at"])
            break
