"""Index evidence from Pi CLI/RPC's append-only v3 session tree."""
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import stat

from .header import _proof
from .index_coverage import applied, count_record, coverage_rows, day_of
from .lines import _finite_float, _reject_constant, ref

__all__ = [
    "extract", "Restart", "provenance_defaults", "bind", "ABSENT", "WATCHED", "APPLIED",
    "UNWATCHED", "COMMON_READS", "KNOWN_KINDS", "PROVENANCE", "COVERAGE_KEYS", "TOOL_KINDS",
    "FEATURES", "SIDE_INPUTS", "header", "path_facts", "side_inputs", "refusal",
]

KNOWN_KINDS = frozenset({
    "session", "message", "model_change", "thinking_level_change", "usage", "compaction",
    "branch_summary", "custom", "custom_message", "context_edit", "label", "session_info",
})
_MILLISECOND = timedelta(milliseconds=1)
_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00Z")
_COUNTERS = ("input", "cacheRead", "cacheWrite", "output", "reasoning", "totalTokens")
_SUMMARIES = ("compaction", "branch_summary")
_USAGE_SITES = (*_SUMMARIES, "usage")
COMMON_READS = ("type", "timestamp", "id", "parentId")
WATCHED = {
    "session": {"sources": ("version", "cwd", "parentSession"), "inputs": {}},
    "model_change": {"sources": ("modelId",), "inputs": {"model": ("modelId",)}},
    "thinking_level_change": {"sources": ("thinkingLevel",), "inputs": {"effort": ("thinkingLevel",)}},
    "message": {"sources": ("message.role", "message.model", "message.responseModel", "message.content",
                            "message.thinkingLevel", "message.providerThinkingLevel", "message.usage",
                            "message.stopReason"), "inputs": {}},
    **{kind: {"sources": ("usage",), "inputs": {}} for kind in _USAGE_SITES},
}
APPLIED = {"usage": _COUNTERS, "fork_origin": ("verified",)}
UNWATCHED = {}
TOOL_KINDS = {}
FEATURES = {"native_skill_events": False, "question_option_labels": False}
ABSENT = {
    "identity.version": "not_recorded",  # Session format version is not the CLI version.
    "identity.entrypoint": "not_recorded",
    "identity.agent": "not_recorded",
    "identity.subagent": "not_recorded",
    "response.usage.cache_write": "not_recorded",
    "response.usage.thinking": "not_recorded",
    "turn_end": "no_turn_end_records",
}


def _counter_paths(*names):
    return [f"{prefix}usage.{name}" for prefix in ("message.", "") for name in names]


PROVENANCE = {
    "native_kind": ["type"], "eligible": ["id", "timestamp", "version"],
    "flush_response": ["type"], "identity.session": ["id"], "identity.index_session": ["id"],
    "identity.cwd": ["cwd"], "identity.parent": ["parentSession"], "identity.agent": [],
    "identity.subagent": [], "identity.entrypoint": [], "identity.version": [],
    "at_ms": ["timestamp"], "response.id": ["id", "parentSession"],
    "response.model": ["message.responseModel", "message.model", "modelId", "model"],
    "response.effort": ["message.providerThinkingLevel"],
    "response.native": [*_counter_paths(*_COUNTERS), "message.stopReason", "message.api",
                        "message.provider", "provider", "kind", "message.model", "modelId",
                        "message.thinkingLevel", "thinkingLevel"],
    "response.usage_present.output": _counter_paths("output"),
    "response.usage_present.thinking": [],
    "response.usage.input_uncached": _counter_paths("input"),
    "response.usage.cache_read": _counter_paths("cacheRead"),
    "response.usage.cache_write": [],
    "response.usage.output": _counter_paths("output"), "response.usage.thinking": [],
    "response.usage.context_total": _counter_paths("input", "cacheRead", "cacheWrite"),
    "response.usage.uncached_total": _counter_paths("input"),
    "message.channel": ["message.role", "type"],
    "message.origin": ["message.role", "type"],
    "message.text": ["message.content", "summary"], "message.blocks": ["message.content", "summary"],
    "message.joined_bytes": ["message.content", "summary"],
    "message.joined_nonempty": ["message.content", "summary"],
    "message.assistant_output_bytes": ["message.content"],
    "fork_boundary": ["id", "parentSession"], "compaction": ["type", "id"], "turn_end": [],
    "interruption": ["message.stopReason"],
}
COVERAGE_KEYS = {
    "response.usage.input_uncached": ["applied:usage/input:input"],
    "response.usage.cache_read": ["applied:usage/input:cacheRead"],
    "response.usage.output": ["applied:usage/input:output"],
    "response.id": ["applied:fork_origin/input:verified"],
}
_ANCESTRY = "pi_parent_sessions"
SIDE_INPUTS = {_ANCESTRY: {
    "path": "parentSession", "relative_to": "session store",
    "fingerprint": "sha256 of the complete-line ancestor snapshots and resolution status",
}}


class Restart(Exception):
    """The shared index stream handles changed prefixes and side inputs."""

    def __init__(self, reason, seed):
        super().__init__(reason)
        self.reason, self.seed = reason, seed


def _string(value):
    return value if isinstance(value, str) and value else None


def _at_ms(value):
    if _string(value) is None:
        return None
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is not None:
            at = (stamp - _EPOCH) // _MILLISECOND
            day_of(at)  # Outside Python's UTC date range cannot form a coverage day.
            return at
    except (ValueError, OverflowError, OSError):
        pass
    return None


def _record(raw):
    try:
        value = json.loads(raw, parse_float=_finite_float, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _header(row):
    return (row and row.get("type") == "session" and row.get("version") == 3
            and _string(row.get("id")) is not None and "\t" not in row["id"]
            and _at_ms(row.get("timestamp")) is not None)


def _open_file(path, *, dir_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=dir_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError("not a regular session file")
    return os.fdopen(fd, "rb")


def _open_parent(root, path):
    """Open only regular JSONL descendants of the declared store, without symlinks."""
    parts = path.relative_to(root).parts
    if not parts or ".." in parts or path.suffix != ".jsonl":
        raise ValueError("parent outside the session store")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return _open_file(parts[-1], dir_fd=fd)
    finally:
        os.close(fd)


def _first(handle, size=65536):
    raw = handle.readline(min(size, 65536))
    return _record(raw) if raw.endswith(b"\n") else None


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _entry_digest(row):
    # createBranchedSession rechains parent links after stripping labels and remaps
    # firstKeptEntryId. The entry ID, timestamp and the rest of its evidence survive.
    return _digest({key: value for key, value in row.items()
                    if key != "parentId" and not (key == "firstKeptEntryId" and row["type"] == "compaction")})


def _is_response(row):
    kind = row.get("type")
    if kind == "message":
        message = row.get("message")
        return isinstance(message, dict) and message.get("role") == "assistant"
    if kind == "usage":
        return True
    if kind not in _SUMMARIES:
        return False
    if isinstance(row.get("usage"), dict):
        return True
    # Pi 1.1.0's branch summarizer returns this before calling a provider.
    return row.get("fromHook") is not True and not (
        kind == "branch_summary" and row.get("summary") == "No content to summarize"
    )


def _parent_chain(place, origin):
    if not _header(origin):
        return [], "no_session_header"
    root = place.path.absolute().parents[len(Path(place.relpath).parts) - 2]
    path = place.path.absolute()
    seen_paths, seen_sessions = {path}, {origin["id"]}
    chain = []
    while (parent := origin.get("parentSession")) is not None:
        if not isinstance(parent, str) or not parent or "\x00" in parent:
            return chain, "invalid_parent"
        candidate = Path(parent)
        if not candidate.is_absolute() or candidate in seen_paths:
            return chain, "invalid_parent"
        try:
            with _open_parent(root, candidate) as handle:
                limit = os.fstat(handle.fileno()).st_size
                ancestor = _first(handle, limit)
                if not _header(ancestor) or ancestor["id"] in seen_sessions:
                    return chain, "invalid_parent_header"
                # Compare complete native entries from a fixed span. The fork header's
                # clock is independent of the timestamps on copied entries.
                entries = {}
                complete = True
                while (remaining := limit - handle.tell()) > 0:
                    raw = handle.readline(remaining)
                    if not raw.endswith(b"\n"):
                        complete = False
                        break
                    row = _record(raw)
                    if row is None:
                        complete = False
                        continue
                    if not _is_response(row):
                        continue
                    entry = _string(row.get("id"))
                    if entry is not None and _at_ms(row.get("timestamp")) is not None:
                        entries[entry] = None if entry in entries else _entry_digest(row)
        except (OSError, ValueError, RecursionError):
            return chain, "parent_unavailable"
        chain.append((ancestor["id"], entries, complete))
        seen_paths.add(candidate)
        seen_sessions.add(ancestor["id"])
        origin = ancestor
    return chain, None


class _Facts(dict):
    """Public path facts plus the private snapshot needed to bind one extraction."""

    def __init__(self, public, chain=(), parent=None, session=None):
        super().__init__(public)
        self.chain = chain
        self.parent = parent
        self.session = session


def refusal(place) -> str | None:
    parts = Path(place.relpath).parts
    if len(parts) < 2 or ".." in parts or place.path.suffix != ".jsonl" or place.store != "live":
        return "Pi index reads JSONL files under a declared CLI/RPC session store"
    return None


def path_facts(place) -> dict:
    """Read the header and bounded ancestor snapshots without publishing their contents."""
    try:
        with _open_file(place.read_path or place.path) as handle:
            row = _first(handle)
    except OSError:
        row = None
    chain, reason = _parent_chain(place, row)
    public = {"basis": "native", "rule": "pi_session_ancestry", "ref": ref(place), "reason": reason,
              "ancestry_sha256": _digest([chain, reason])}
    return _Facts(public, chain, row.get("parentSession"), row["id"]) if _header(row) else _Facts(public)


def side_inputs(facts) -> dict:
    return {_ANCESTRY: facts["ancestry_sha256"]}


def bind(state, facts) -> None:
    state["ancestry"] = list(getattr(facts, "chain", ()))
    state["ancestry_complete"] = "reason" in facts and facts["reason"] is None
    state["snapshot_header"] = [getattr(facts, "session", None), getattr(facts, "parent", None)]


def header(place, handle, *, size, envelope, result):
    raw = handle.readline(min(size, 65536))
    row = _record(raw) if raw.endswith(b"\n") else None
    if not _header(row):
        raise ValueError("missing complete Pi session v3 header")
    for field, key, value in (
        ("session", "id", row["id"]), ("start_ms", "timestamp", _at_ms(row["timestamp"])),
        ("cwd", "cwd", _string(row.get("cwd"))),
    ):
        result["header"][field] = value
        if value is not None:
            result["provenance"][field] = _proof(place, 1, 0, raw, envelope, [key])


def provenance_defaults() -> dict[str, dict]:
    defaults = {}
    for field, paths in PROVENANCE.items():
        rule = "absent:" + ABSENT[field] if field in ABSENT else "pi_session_entry"
        basis = "convention" if field == "response.usage_present.thinking" else "native"
        defaults[field] = {"native_paths": list(paths), "coverage_keys": list(COVERAGE_KEYS.get(field, ())),
                           "basis": basis, "rule": rule}
    return defaults


def _origin(row, session, state):
    """Follow exact copies back to the physical owner without wall-clock ordering."""
    local = session, "pi_session_entry"
    if not state["has_parent"]:
        return local
    unresolved = session, "unresolved:pi_fork_origin"
    owner = session
    digest = _entry_digest(row)
    for ancestor, entries, readable in state["ancestry"]:
        if row["id"] not in entries:
            if not readable:
                return unresolved
            return local if owner == session else (owner, "pi_verified_parent_entry")
        if entries[row["id"]] != digest:
            return unresolved
        owner = ancestor
    if not state["ancestry_complete"]:
        return unresolved
    return local if owner == session else (owner, "pi_verified_parent_entry")


def _counter(usage, key):
    value = usage.get(key)
    # Native usage has no per-counter presence flag. The transport can write a zero
    # for an omitted field, even beside a positive counter in the same usage object.
    return value if type(value) is int and value > 0 else None


def _response(row, identity, model, effort, state):
    kind = row["type"]
    message = row.get("message") if kind == "message" else {}
    usage = message.get("usage") if kind == "message" else row.get("usage")
    raw = usage if isinstance(usage, dict) else {}
    native = {key: raw[key] for key in _COUNTERS if type(raw.get(key)) in (int, float)}
    provider = _string((message if kind == "message" else row).get("provider"))
    api = _string(message.get("api"))
    if provider is not None:
        native["provider"] = provider
    if api is not None:
        native["api"] = api
    if kind == "usage" and _string(row.get("kind")):
        native["kind"] = row["kind"]
    stop = message.get("stopReason")
    if stop in ("stop", "length", "toolUse", "error", "aborted"):
        native["stopReason"] = stop
    if kind == "message":
        if model := _string(message.get("model")) or model:
            native["requestedModel"] = model
        if selected_effort := _string(message.get("thinkingLevel")) or effort:
            native["requestedThinkingLevel"] = selected_effort
        model = _string(message.get("responseModel")) or model
        effort = _string(message.get("providerThinkingLevel"))
    inp, read, write, out = (_counter(raw, name) for name in ("input", "cacheRead", "cacheWrite", "output"))
    context_read = read
    if (api == "openai-completions" and inp is not None
            and type(raw.get("cacheRead")) is int and raw["cacheRead"] == 0
            and type(raw.get("cacheWrite")) is int and raw["cacheWrite"] >= 0):
        # Positive net input means Pi subtracted its cache components from an
        # observed prompt total. That total is recoverable even if read is unknown.
        context_read = 0
    usage = {
        "input_uncached": inp, "cache_read": read, "cache_write": None, "output": out,
        "thinking": None, "context_total": None if inp is None or context_read is None else inp + context_read + (write or 0),
        "uncached_total": None if inp is None else inp + (write or 0),
    }
    owner, rule = _origin(row, identity["session"], state)
    return {
        "id": f"{owner}:{row['id']}", "model": model, "effort": effort, "usage": usage,
        "usage_present": {"output": out is not None, "thinking": False}, "native": native,
    }, rule


def _message(channel, content, text):
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    blocks, body = [], []
    for index, item in enumerate(content if isinstance(content, list) else []):
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            value = item["text"]
            body.append(value)
            blocks.append({"block": index, "bytes": len(value.encode("utf-8", errors="replace")),
                           **({"text": value} if text else {})})
    joined = "\n".join(body)
    size = len(joined.encode("utf-8", errors="replace"))
    return {
        "channel": channel, "origin": {"native_kind": channel, "flags": [], "markers": [],
                                       "unrecognized_tag": {"lead": False, "joined": False}},
        "joined_bytes": size, "joined_nonempty": bool(joined.strip()),
        "assistant_output_bytes": size if channel == "assistant" else 0, "blocks": blocks,
        **({"text": joined} if text else {}),
    }


def _event(row, position, state, text):
    kind = _string(row.get("type")) or "unknown"
    if "\t" in kind:
        kind = "unknown"
    at = _at_ms(row.get("timestamp"))
    entry = _string(row.get("id"))
    if position["line"] == 1 and _header(row):
        state["has_parent"] = row.get("parentSession") is not None
        chain = state.get("ancestry", ())
        snapshot = state.get("snapshot_header")
        if snapshot != [entry, row.get("parentSession")]:
            state["ancestry"] = chain = []
            state["ancestry_complete"] = False
        state["identity"] = {"session": entry, "index_session": entry, "agent": None,
                             "parent": chain[0][0] if chain else None, "subagent": None,
                             "cwd": _string(row.get("cwd")) if text else None,
                             "entrypoint": None, "version": None}
    identity = state.get("identity")
    if identity is None:
        return None
    session = identity["session"]
    day = day_of(at)
    count_record(state, session, day, kind, kind in KNOWN_KINDS, row, WATCHED)
    eligible = entry is not None and at is not None
    event = {"object": "index_event", **position, "native_kind": kind, "identity": dict(identity),
             "at_ms": at, "eligible": eligible, "response": None, "flush_response": False,
             "message": None, "calls": [], "results": [], "injections": [], "notifications": [],
             "compaction": None, "interruption": None, "fork_boundary": None, "turn_end": None,
             "provenance": {}}
    if state["has_parent"] and identity["parent"] is None:
        event["provenance"]["identity.parent"] = {"rule": "unresolved:pi_parent_session"}
    if not eligible or kind == "session":
        return event
    configurations = state.setdefault("branch_configuration", {})
    model, effort = configurations.get(_string(row.get("parentId")), (None, None))
    if kind == "model_change":
        model = _string(row.get("modelId"))
    elif kind == "thinking_level_change":
        effort = _string(row.get("thinkingLevel"))
    configurations[entry] = [model, effort]
    message = row.get("message")
    if kind == "message" and isinstance(message, dict):
        channel = message.get("role")
        if channel in ("user", "assistant", "system"):
            event["message"] = _message(channel, message.get("content"), text)
        if message.get("stopReason") in ("aborted", "error"):
            event["interruption"] = {"user_marker": False, "system": True,
                                     "basis": "native", "rule": "pi_assistant_stop_reason"}
        if channel == "assistant" and _string(message.get("responseModel")) is None:
            path = "message.model" if _string(message.get("model")) else "modelId"
            if _string(message.get("model")) or model:
                event["provenance"]["response.model"] = {
                    "native_paths": [path], "basis": "convention", "rule": "pi_requested_model",
                }
    elif kind in _SUMMARIES:
        event["message"] = _message("system", row.get("summary"), text)
        if kind == "compaction":
            event["compaction"] = {"summary": True, "id": entry, "basis": "native", "rule": "pi_compaction"}
        # The v3 summary entry stores usage but no observed model or effort.
        model = effort = None
    elif kind == "usage":
        event["message"] = _message("system", None, text)
        model, effort = _string(row.get("model")), None
    if _is_response(row):
        response, rule = _response(row, identity, model, effort, state)
        event.update(response=response, flush_response=True)
        event["provenance"]["response.id"] = {"rule": rule}
        if rule == "pi_verified_parent_entry":
            event["fork_boundary"] = {"next_response": False, "copied_response": True,
                                      "basis": "native", "rule": rule}
        if state["has_parent"]:
            applied(state, session, day, "fork_origin", {"verified": rule != "unresolved:pi_fork_origin"})
        present = {name: name in response["native"] for name in _COUNTERS}
        for name, field in (("input", "input_uncached"), ("cacheRead", "cache_read"), ("output", "output")):
            present[name] = response["usage"][field] is not None
        applied(state, session, day, "usage", present)
    return event


def extract(lines, state, *, place, text: bool):
    """Emit physical entries and retain branch state for append-only resume."""
    number, partial = state.get("next_line", 1), False
    for offset, raw in lines:
        end = offset + len(raw)
        position = {"key": f"E{offset}", "line": number, "offset": offset, "end": end,
                    "ref": ref(place, number), "sha256": hashlib.sha256(raw).hexdigest()}
        if not raw.endswith(b"\n"):
            partial = True
            yield {"object": "unparsed", **position, "reason": "truncated", "provisional": True}
            break
        state["next_line"], state["next_offset"] = number + 1, end
        number += 1
        row = _record(raw)
        event = _event(row, position, state, text) if row is not None else None
        if event is None:
            state["malformed"] = state.get("malformed", 0) + 1
            yield {"object": "unparsed", **position, "reason": "malformed", "provisional": False}
        else:
            yield event
    state.pop("ancestry", None)
    state.pop("ancestry_complete", None)
    state.pop("snapshot_header", None)
    counts, fields = coverage_rows(state)
    yield {"object": "coverage", "key": "coverage", "records": counts, "fields": fields,
           "malformed": state.get("malformed", 0), "partial_tail": partial}
