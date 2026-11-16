"""Typed records for the session-logs reader: one object per transcript record or content
block, with its role, copy, call and model, plus the native facts a later
turn parser needs, kept under private `_` keys that are never emitted. Read-only.

Sections: shared helpers (any harness), the Claude Code reader, the Codex reader
and the Claude SDK stream reader."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Callable, Collection

from .lines import Line, Place, decode, lines, ref, sha256
from .labels import label, origin

CLASSIFIER = "session-logs-classifier/1"


@dataclass
class FileRead:
    place: Place
    records: list[dict]
    unparsed: list[dict]
    header: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------------------

_SURROGATE = re.compile("[\ud800-\udfff]")


def cut(text: str, limit: int) -> tuple[str, int, bool]:
    """`text` cut to at most `limit` UTF-8 bytes on a character boundary, the full byte
    length, and whether it was cut. A lone surrogate, which valid JSON can spell as a
    `\\ud800` escape (`json` joins only paired ones), has no UTF-8 form: each becomes one
    U+FFFD, in the text returned and in the length."""
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError:
        text = _SURROGATE.sub("\ufffd", text)
        encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text, len(encoded), False
    return encoded[:limit].decode("utf-8", errors="ignore"), len(encoded), True


# `call.status` values besides `pending`: a call or result whose id is not a string, and a
# second or later non-copy call (or result) with an id already seen. Neither is paired.
NO_ID = "no_id"
DUPLICATE_ID = "duplicate_id"


def pair_calls(records: list[dict]) -> None:
    """Pair calls and results by string call id, first of each id winning. A call with no
    result is `status: pending`; an id that is not a string is `no_id`; a later call or
    result repeating an id already seen is `duplicate_id`. Copies take no part: they are
    never paired, nor given a status. An `ambiguous` record is the exception: its range may
    hold the file's own calls, so it pairs within its file (R18). Idempotent, so a caller
    that marks more copies later can pair again."""
    calls: dict[str, dict] = {}
    results: dict[str, dict] = {}
    for record in records:
        call = record.get("call")
        if call is None:
            continue
        call["peer"] = None
        call.pop("status", None)
        if "copy" in record and record["copy"] != "ambiguous":
            continue
        call_id = call.get("id")
        if not isinstance(call_id, str):
            call["status"] = NO_ID
            continue
        side = results if record["role"] == "tool_output" else calls
        if call_id in side:
            call["status"] = DUPLICATE_ID
            continue
        side[call_id] = record
    for call_id, record in calls.items():
        result = results.get(call_id)
        if result is None:
            record["call"]["status"] = "pending"
        else:
            record["call"]["peer"] = result["ref"]
            result["call"]["peer"] = record["ref"]


def _dict(record, key) -> dict:
    """`record[key]` when both are objects, else an empty dict."""
    value = record.get(key) if isinstance(record, dict) else None
    return value if isinstance(value, dict) else {}


def _str(value) -> str | None:
    return value if isinstance(value, str) else None


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _unparsed(place: Place, line: Line) -> dict:
    return {"type": "unparsed", "ref": ref(place, line.number),
            "reason": "malformed" if line.complete else "truncated",
            "_raw": line.raw.decode("utf-8", errors="replace"), "_line": line.number}


def recorded_identity(place: Place, line: Line, record: dict) -> dict | None:
    """One native identity observation; callers keep the first, without a peek window."""
    if place.harness == "codex":
        if record.get("type") != "session_meta":
            return None
        value = _str(_dict(record, "payload").get("id")) or None
        rule = "session_meta"
    else:
        value = record.get("sessionId")
        if not isinstance(value, str) or record.get("isSidechain"):
            return None
        rule = "session_id"
    return {"session": value, "line": line.number, "ref": ref(place, line.number),
            "sha256": sha256(line), "basis": "native", "rule": rule}


def _decoded(place: Place, size: int, data: bytes | None = None) -> tuple[list[tuple[Line, dict]], list[dict], int, dict | None]:
    """Every line decoded once, retaining its hash in place of its raw bytes."""
    parsed, unparsed, count, identity = [], [], 0, None
    source = data if data is not None else place.read_path if place.read_path is not None else place.path
    for line in lines(source, size):
        count = line.number
        record = decode(line)
        if identity is None and record is not None:
            identity = recorded_identity(place, line, record)
        if record is None or not line.complete:
            unparsed.append(_unparsed(place, line))
        else:
            parsed.append((Line(line.number, b"", line.complete, sha256(line)), record))
    return parsed, unparsed, count, identity


def _text_of(content) -> str:
    """A message's or tool result's text: a string, or its text blocks joined."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b["text"] for b in content
                         if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def _envelope(place: Place, identity: dict, line: Line, block: int | None, at, role: str,
              basis: str, kind) -> dict:
    """The shared leading fields, in order: ref, hash, line and block; the place; the
    file's identity; time, role, its basis and the native kind."""
    out = {"type": "record", "ref": ref(place, line.number, block), "sha256": sha256(line),
           "line": line.number}
    if block is not None:
        out["block"] = block
    out.update({"harness": place.harness, "home": place.home, "profile": place.profile,
                "store": place.store, "session": identity["session"]})
    if identity.get("agent") is not None:
        out["agent"] = identity["agent"]
    out.update({"at": _str(at), "role": role, "role_basis": basis, "kind": _str(kind)})
    return out


def _object(place: Place, identity: dict, line: Line, block: int | None, at, role: str,
            basis: str, kind, fields: dict, flags, private: dict | None = None) -> dict:
    """One object: the envelope, then the fields that apply (None omitted), then the
    private native facts (`_flags` always, a frozenset)."""
    out = _envelope(place, identity, line, block, at, role, basis, kind)
    out.update({k: v for k, v in fields.items() if v is not None})
    out["_flags"] = frozenset(flags)
    if private:
        out.update(private)
    copied = out.get("copy")
    if copied is not None:
        basis, rule = {
            "request_blob": ("native", "api_request_blob"),
            "fork_history": ("convention", "inherited_turn_ids"),
            "compaction_history": ("native", "replacement_history"),
            "event_mirror": ("convention", "event_mirror"),
            "ambiguous": ("heuristic", "unresolved_fork"),
        }[copied]
        if copied == "fork_history" and place.harness == "claude-code":
            basis, rule = "native", "fork_context_ref"
        out.update(copy_basis=basis, copy_rule=rule)
    # Publish evidence without changing the native facts used by existing readers.
    names = {"isMeta": "meta", "isCompactSummary": "compaction_summary"}
    out["flags"] = sorted({names.get(flag, flag) for flag in out["_flags"]})
    out["turn_id"] = out.get("_turn_id")
    out["turn_end_message"] = out.get("_last_agent_message")
    out["abort_reason"] = out.get("_abort_reason")
    out["readable_text"] = role == "assistant" and out.get("block_type") in {None, "text", "output_text"}
    if role == "tool_call":
        tools = {"AskUserQuestion", "EnterPlanMode", "ExitPlanMode"} if place.harness == "claude-code" \
            else {"request_user_input"} if place.harness == "codex" else set()
        out["waits_for_user"] = (out.get("call") or {}).get("tool") in tools
    if role in {"assistant", "tool_call"}:
        stop = out.get("stop_reason")
        out["stop_class"] = None if stop is None else "closing" if stop in ("end_turn", "stop_sequence") else "other"
    if role == "assistant":
        phase = out.get("phase")
        out["answer_phase"] = None if phase is None else "final" if phase == "final_answer" else "other"
    label(out)
    return out


class _Models:
    """The model values seen in a file, each value and basis once, first ref kept. Every
    ref of each value and basis is kept too, with its line (`refs`, the header's private
    `_model_refs`), so a later step that marks lines as copies can move a model's ref to
    the first line that is still the file's own."""

    def __init__(self):
        self.listed: list[dict] = []
        self.refs: dict[tuple[str, str], list[tuple[str, int]]] = {}

    def add(self, value, basis: str, at: str, line: int) -> None:
        if not (isinstance(value, str) and value):
            return
        key = (value, basis)
        if key not in self.refs:
            self.refs[key] = []
            self.listed.append({"value": value, "basis": basis, "ref": at})
        self.refs[key].append((at, line))


def _span(parsed: list[tuple[Line, dict]], key: str = "timestamp") -> tuple[str | None, str | None]:
    stamps = [r[key] for _l, r in parsed if isinstance(r.get(key), str) and r[key]]
    return (min(stamps), max(stamps)) if stamps else (None, None)


# ---------------------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------------------

# Metadata kinds of second-to-last row, besides `system` and `file-history-*`.
_CLAUDE_METADATA = frozenset({
    "queue-operation", "mode", "permission-mode", "ai-title", "custom-title", "last-prompt",
    "agent-name", "agent-setting", "agent-color", "pr-link", "cost-state", "api-request",
    "api-request-shape", "continued-in", "atis-latch", "isolation-latch", "bridge-session",
    "fork-context-ref", "summary", "relocated", "worktree-state",
})
_LOCAL_INPUT = ("<command-name>", "<bash-input>")
_LOCAL_OUTPUT = ("<local-command-stdout>", "<local-command-stderr>", "<bash-stdout>",
                 "<bash-stderr>")
_INTERRUPT = "[Request interrupted by user"
_DISPATCH_TOOLS = frozenset({"Agent", "Task"})
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _local(text: str) -> str | None:
    """`local_input` or `local_output` when the text is a local command's shape."""
    if text.startswith(_LOCAL_INPUT):
        return "local_input"
    if text.startswith(_LOCAL_OUTPUT):
        return "local_output"
    return None


def _lead(content) -> str:
    """The text a prefix rule reads: a string content, or the first text block's text
    (empty unless that text is a string)."""
    if isinstance(content, str):
        return content
    for block in content if isinstance(content, list) else ():
        if isinstance(block, dict) and block.get("type") == "text":
            return _str(block.get("text")) or ""
    return ""


def _user_role(record: dict, text: str) -> tuple[str, str, set[str]]:
    """Build `user` rows for a record's non-tool-result content: the role, its basis and
    the native flags that decided it. The interrupt marker comes first, whatever the
    record's origin; then the rows in table order."""
    if text.startswith(_INTERRUPT):
        return "injected", "structure", {"interrupt_marker"}
    kind = _str(_dict(record, "origin").get("kind"))
    meta = bool(record.get("isMeta") or record.get("isCompactSummary"))
    if kind == "human" and not meta:
        return "human", "origin", set()
    if kind is not None and kind != "human":
        return "injected", "origin", set()
    if meta:
        return "injected", "structure", set()
    local = _local(text)
    if local:
        return ("human" if local == "local_input" else "injected"), "local_command", {local}
    if text.startswith("<") and not text.startswith("<pasted_content"):
        return "injected", "prefix_rule", set()
    return "human", "prefix_rule", set()


def _block_text(block: dict) -> tuple[str | None, bool]:
    """A content block's searchable text and whether its content is encrypted. Only string
    values are text."""
    kind = block.get("type")
    if not isinstance(kind, str):
        return "", False
    if kind == "text":
        return _str(block.get("text")) or "", False
    if kind == "thinking":
        return _str(block.get("thinking")) or "", False
    if kind == "redacted_thinking":
        return None, True
    if kind == "tool_use":
        call_input = block.get("input")
        command = _shell_command(block)
        return _compact(call_input) + (f"\n{command}" if command else ""), False
    if kind == "tool_result":
        return _text_of(block.get("content")), False
    return "", False


def _shell_command(block: dict) -> str | None:
    call_input = block.get("input")
    if block.get("name") == "Bash" and isinstance(call_input, dict) \
            and isinstance(call_input.get("command"), str):
        return call_input["command"]
    return None


def _call(block: dict) -> dict | None:
    if block.get("type") == "tool_use":
        out = {"id": block.get("id"), "tool": _str(block.get("name")), "peer": None}
        command = _shell_command(block)
        if command is not None:
            out["command"] = command
        return out
    if block.get("type") == "tool_result":
        return {"id": block.get("tool_use_id"), "peer": None,
                "is_error": bool(block.get("is_error", False))}
    return None


def _is_dispatch(block: dict) -> bool:
    return block.get("type") == "tool_use" and isinstance(block.get("name"), str) \
        and block["name"] in _DISPATCH_TOOLS and isinstance(block.get("input"), dict)


class _ClaudeFile:
    """One Claude transcript being read: the place, the identity once known, and the
    objects collected so far."""

    def __init__(self, place: Place, identity: dict, subagent: bool, fork_message):
        self.place = place
        self.identity = identity
        self.subagent = subagent
        # The forked file's first assistant response: (line, message id), or None.
        self.fork_message = fork_message
        self.records: list[dict] = []
        self.models = _Models()

    def emit(self, line: Line, record: dict, kind, role: str, basis: str, flags: set[str],
             block: int | None = None, **fields) -> dict:
        native = {"origin_kind": _str(_dict(record, "origin").get("kind")),
                  "prompt_source": record.get("promptSource")}
        private = {}
        if isinstance(record.get("promptId"), str):
            private["_prompt_id"] = record["promptId"]
        if isinstance(record.get("sourceToolUseID"), str):
            private["_source_tool_use_id"] = record["sourceToolUseID"]
        # the launch result's `toolUseResult.agentId` names the child it started (CA:12),
        # and a `continued-in` record names the session that resumed this one.
        launched = _dict(record, "toolUseResult").get("agentId")
        if isinstance(launched, str) and launched:
            private["_launched_agent"] = launched
        if record.get("type") == "continued-in" and isinstance(record.get("continuedInSessionId"), str):
            private["_continued_in"] = record["continuedInSessionId"]
        out = _object(self.place, self.identity, line, block, record.get("timestamp"), role,
                      basis, kind, {**native, **fields}, flags, private)
        self.records.append(out)
        return out

    def fork_copy(self, line: Line, record: dict) -> str | None:
        """`fork_history` for every record of a forked file's first assistant response."""
        if self.fork_message is None or record.get("type") != "assistant":
            return None
        fork_line, fork_id = self.fork_message
        message = _dict(record, "message")
        same = (line.number == fork_line) if fork_id is None else (message.get("id") == fork_id)
        return "fork_history" if same else None

    # -- one native record --------------------------------------------------------------

    def read(self, line: Line, record: dict) -> None:
        kind = record.get("type")
        flags = {name for name in ("isMeta", "isCompactSummary") if record.get(name)}
        copied = kind == "api-request-blob" or self.fork_copy(line, record) is not None
        if not copied:
            self.models.add(record.get("requestedModel"), "requested", ref(self.place, line.number),
                            line.number)
        if not isinstance(kind, str):
            self.emit(line, record, None, "unknown", "kind", flags, text=_compact(record))
        elif kind == "user":
            self.user(line, record, flags)
        elif kind == "assistant":
            self.assistant(line, record, flags)
        elif kind == "attachment":
            self.attachment(line, record, flags)
        elif kind == "api-request-blob":
            self.request_blob(line, record)
        elif kind == "system":
            self.system(line, record, flags)
        elif kind in _CLAUDE_METADATA or kind.startswith("file-history-"):
            self.emit(line, record, kind, "metadata", "structure", flags, text=_compact(record))
        else:
            self.emit(line, record, kind, "unknown", "kind", flags, text=_compact(record))

    def user(self, line: Line, record: dict, flags: set[str], copy: str | None = None) -> None:
        """Build `user` rows. A copy (a request blob's user message) keeps no native flags:
        they describe the record it was copied into, not a prompt of this file."""
        content = _dict(record, "message").get("content")
        blocks = content if isinstance(content, list) else None
        results = [b for b in blocks or () if isinstance(b, dict) and b.get("type") == "tool_result"]
        role, basis, decided = _user_role(record, _lead(content))
        if blocks is None or len(results) < len(blocks):
            flags |= {"prompt"} | decided
        if results:
            flags.add("tool_result")
        if copy:
            flags = set()
        resolved = _dict(record, "toolUseResult").get("resolvedModel")
        model = None
        if copy is None and isinstance(resolved, str):
            model = {"value": resolved, "basis": "resolved"}
            self.models.add(resolved, "resolved", ref(self.place, line.number), line.number)
        role, basis = self.prompt_role(role, basis)
        kind = "api-request-blob" if copy else "user"
        evidence = origin(content, "claude-code", _dict(record, "origin").get("kind"),
                          [name for key, name in (("isMeta", "meta"), ("isCompactSummary", "compaction_summary"))
                           if record.get(key)])
        if blocks is None:
            self.emit(line, record, kind, role, basis, flags, copy=copy, text=_text_of(content), origin=evidence)
            return
        if not blocks:
            self.emit(line, record, kind, role, basis, flags, copy=copy, text="", origin=evidence)
            return
        for index, block in enumerate(blocks):
            block = block if isinstance(block, dict) else {}
            text, encrypted = _block_text(block)
            is_result = block.get("type") == "tool_result"
            self.emit(line, record, kind, "tool_output" if is_result else role,
                      "structure" if is_result else basis, flags, block=index,
                      block_type=_str(block.get("type")), copy=copy, call=_call(block),
                      model=model if is_result else None, text=text, encrypted=encrypted or None, origin=evidence)

    def prompt_role(self, role: str, basis: str) -> tuple[str, str]:
        """In a subagent file every prompt is the dispatch brief, never a human's: the file's
        path or sidechain shape decides, so its basis is `structure`."""
        if role == "human" and self.subagent:
            return "dispatch", "structure"
        return role, basis

    def assistant(self, line: Line, record: dict, flags: set[str], copy: str | None = None) -> None:
        message = _dict(record, "message")
        if copy is None:
            copy = self.fork_copy(line, record)
        value = message.get("model")
        synthetic = value == "<synthetic>"
        model = None
        if isinstance(value, str) and value and not synthetic and copy is None:
            model = {"value": value, "basis": "runtime"}
            self.models.add(value, "runtime", ref(self.place, line.number), line.number)
        kind = "api-request-blob" if copy == "request_blob" else "assistant"
        content = message.get("content")
        blocks = content if isinstance(content, list) else None
        common = {"copy": copy, "message_id": message.get("id"), "stop_reason": message.get("stop_reason"),
                  "synthetic": True if synthetic else None, "model": model}
        if not blocks:
            self.emit(line, record, kind, "assistant", "structure", flags, text=_text_of(content), **common)
            return
        for index, block in enumerate(blocks):
            block = block if isinstance(block, dict) else {}
            text, encrypted = _block_text(block)
            is_call = block.get("type") == "tool_use"
            if copy is None and _is_dispatch(block):
                self.models.add(block["input"].get("model"), "requested",
                                ref(self.place, line.number, index), line.number)
            self.emit(line, record, kind, "tool_call" if is_call else "assistant", "structure", flags,
                      block=index, block_type=_str(block.get("type")), call=_call(block), text=text,
                      encrypted=encrypted or None, **common)

    def attachment(self, line: Line, record: dict, flags: set[str]) -> None:
        body = _dict(record, "attachment")
        sub = _str(body.get("type"))
        kind = f"attachment/{sub}" if sub else "attachment"
        origin_kind = _str(_dict(body, "origin").get("kind"))
        text = body.get("prompt") if isinstance(body.get("prompt"), str) else _compact(body)
        evidence = origin(text, "claude-code", origin_kind)
        queued = sub == "queued_command"
        if queued:
            flags.add("queued")
        if origin_kind is None:
            self.emit(line, record, kind, "injected", "structure", flags, text=text, origin=evidence)
            return
        role, basis = self.prompt_role("human" if origin_kind == "human" else "injected", "origin")
        self.emit(line, record, kind, role, basis, flags, origin_kind=origin_kind,
                  queued=True if queued and origin_kind == "human" else None, text=text, origin=evidence)

    def request_blob(self, line: Line, record: dict) -> None:
        """For an `api-request-blob` row, each block takes its request message's role and is
        a `request_blob` copy."""
        message = _dict(record, "message")
        role = message.get("role")
        if role == "user":
            self.user(line, record, set(), copy="request_blob")
        elif role == "assistant":
            self.assistant(line, record, set(), copy="request_blob")
        elif role == "system":
            self.emit(line, record, "api-request-blob", "injected", "structure", set(),
                      copy="request_blob", text=_text_of(message.get("content")))
        else:
            self.emit(line, record, "api-request-blob", "metadata", "structure", set(),
                      copy="request_blob", text=_compact(record))

    def system(self, line: Line, record: dict, flags: set[str]) -> None:
        sub = _str(record.get("subtype"))
        kind = f"system/{sub}" if sub else "system"
        if sub == "local_command" and isinstance(record.get("content"), str):
            local = _local(record["content"])
            if local:
                flags.add(local)
                role, basis = self.prompt_role("human" if local == "local_input" else "injected",
                                               "local_command")
                self.emit(line, record, kind, role, basis, flags, text=record["content"],
                          origin=origin(record["content"], "claude-code"))
                return
        if sub == "turn_duration":
            flags.add("turn_duration")
        elif sub == "stop_hook_summary":
            flags.add("stop_hook_blocked" if record.get("hookErrors") else "stop_hook_ok")
        self.emit(line, record, kind, "metadata", "structure", flags, text=_compact(record))


def _identity(place: Place, parsed: list[tuple[Line, dict]], subagent: bool) -> dict:
    """A main file is its file name, confirmed by its main-line `sessionId`; a child is
    `agent-<agentId>`, its parent the session directory above `subagents/`. A `session_id`
    field is never identity."""
    stem = Path(place.relpath).stem
    if subagent:
        agent = next((r["agentId"] for _l, r in parsed if isinstance(r.get("agentId"), str)), None)
        if agent is None and stem.startswith("agent-"):
            agent = stem[len("agent-"):]
        if place.path.parent.name == "subagents":
            parent = place.path.parent.parent.name
        else:
            parent = next((r["sessionId"] for _l, r in parsed if isinstance(r.get("sessionId"), str)), None)
        if agent is None:
            return {"session": stem, "agent": None, "identity_basis": "file_name", "parent": parent}
        return {"session": f"agent-{agent}", "agent": agent, "identity_basis": "agent_id",
                "parent": parent}
    recorded = {r["sessionId"] for _l, r in parsed
                if isinstance(r.get("sessionId"), str) and not r.get("isSidechain")}
    if _UUID.fullmatch(stem):
        basis = "file_name" if recorded <= {stem} else "file_name_unconfirmed"
        return {"session": stem, "agent": None, "identity_basis": basis, "parent": None}
    first = next((r["sessionId"] for _l, r in parsed
                  if isinstance(r.get("sessionId"), str) and not r.get("isSidechain")), None)
    return {"session": first, "agent": None, "identity_basis": "session_id" if first else None,
            "parent": None}


def _forked(parsed: list[tuple[Line, dict]]) -> bool:
    """A forked subagent file begins with `fork-context-ref`."""
    return bool(parsed) and parsed[0][0].number == 1 and parsed[0][1].get("type") == "fork-context-ref"


def _fork_message(parsed: list[tuple[Line, dict]]) -> tuple[int, str | None] | None:
    """In a forked file, its first assistant response: that record's line and message id.
    Every record of that message copies the parent's message that held the launching call."""
    if not _forked(parsed):
        return None
    for line, record in parsed:
        if record.get("type") == "assistant":
            return line.number, _str(_dict(record, "message").get("id"))
    return None


def claude_read(place: Place, size: int, *, data: bytes | None = None) -> FileRead:
    """A Claude Code transcript's first `size` bytes as records (without `turn`), the
    unparsed lines, and the file's header."""
    parsed, unparsed, count, observed = _decoded(place, size, data)
    timed = [r for _l, r in parsed if r.get("timestamp")]
    native_sidechain = bool(timed) and all(r.get("isSidechain") is True for r in timed)
    subagent = place.path.parent.name == "subagents" or native_sidechain
    identity = _identity(place, parsed, subagent)
    reader = _ClaudeFile(place, identity, subagent, _fork_message(parsed))
    for line, record in parsed:
        reader.read(line, record)
    pair_calls(reader.records)
    first_at, last_at = _span(parsed)

    def first_with(key):
        return next((r[key] for _l, r in parsed if isinstance(r.get(key), str)), None)
    continued = next((r.get("continuedInSessionId") for _l, r in parsed
                      if r.get("type") == "continued-in"), None)
    header = {
        **identity,
        "recorded_identity": observed,
        "cwd": first_with("cwd"),
        "entrypoint": first_with("entrypoint"),
        "first_at": first_at,
        "last_at": last_at,
        "lines": count,
        "subagent": subagent,
        "subagent_basis": "native" if native_sidechain else "convention" if subagent else "heuristic",
        "forked": _forked(parsed),
        "uuids": {r["uuid"]: line.number for line, r in parsed if isinstance(r.get("uuid"), str)},
        "continued_in": continued,
        "markers": any("turn_duration" in r["_flags"] for r in reader.records),
        "models": reader.models.listed,
        "_model_refs": reader.models.refs,
    }
    return FileRead(place, reader.records, unparsed, header)


# ---------------------------------------------------------------------------------------
# Codex
# ---------------------------------------------------------------------------------------

_CODEX_CALLS = frozenset({"function_call", "custom_tool_call", "local_shell_call", "web_search_call"})
_CODEX_OUTPUTS = frozenset(f"{name}_output" for name in _CODEX_CALLS)
_CODEX_METADATA = frozenset({"inter_agent_communication_metadata", "token_usage_record", "world_state"})
_CODEX_TURN_EVENTS = frozenset({"task_started", "task_complete", "turn_aborted"})
_CODEX_MIRROR_ITEMS = frozenset({"AgentMessage", "UserMessage"})
_CODEX_MIRROR_EVENTS = frozenset({"user_message", "agent_message"})
# Function tools whose JSON arguments carry a shell command (`cmd`, else `command`), as
# obs's Codex adapter reads them.
_CODEX_SHELL = frozenset({"exec_command", "shell_command", "shell"})
# Copies that repeat another turn's records: they carry no native flags, so a turn parser
# cannot count them as this file's. Event mirrors and ambiguous ranges keep theirs.
_HISTORY_COPIES = frozenset({"fork_history", "compaction_history"})


def _injected_prefix(text: str) -> bool:
    """The injected-prefix rule for a `user` message."""
    return text.startswith("# AGENTS.md") or (text.startswith("<") and not text.startswith("<pasted_content"))


def _codex_lead(content) -> str:
    """A message's first text: a string content, or the first block with string text."""
    if isinstance(content, str):
        return content
    for block in content if isinstance(content, list) else ():
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            return block["text"]
    return ""


def _codex_block(block: dict) -> tuple[str | None, bool]:
    """A Codex content block's text and whether it is encrypted (then it has no text)."""
    if block.get("type") == "encrypted_content":
        return None, True
    return _str(block.get("text")) or "", False


def _joined(command) -> str | None:
    if isinstance(command, str):
        return command
    if isinstance(command, list) and command and all(isinstance(p, str) for p in command):
        return " ".join(command)
    return None


def _arguments(value) -> dict:
    """A function call's JSON arguments as an object, or empty."""
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (ValueError, RecursionError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _turn_start(record: dict) -> tuple[bool, str | None]:
    """Whether a record is an `event_msg` `task_started`, and its turn id when a string."""
    payload = _dict(record, "payload")
    if record.get("type") != "event_msg" or payload.get("type") != "task_started":
        return False, None
    return True, _str(payload.get("turn_id"))


def _thread(meta: dict) -> dict:
    """The child identity and agent path, from a first `session_meta` payload."""
    source = meta.get("source")
    subagent = source.get("subagent") if isinstance(source, dict) else None
    spawn = _dict(subagent, "thread_spawn")
    parent = _str(spawn.get("parent_thread_id")) or _str(meta.get("parent_thread_id"))
    thread_source = meta.get("thread_source")
    child = parent is not None or (thread_source is not None and thread_source != "user")
    if not child:
        return {"parent": None, "child": False, "agent_path": "/root", "depth": 0, "controller": None}
    path = _str(spawn.get("agent_path"))
    depth = spawn.get("depth")
    controller = path.rsplit("/", 1)[0] if path and "/" in path else None
    return {"parent": parent, "child": True, "agent_path": path,
            "depth": depth if type(depth) is int else None, "controller": controller or None}


class _CodexFile:
    """One Codex rollout being read: its identity and thread, the copy range each line falls
    in, and the objects collected so far."""

    def __init__(self, place: Place, identity: dict, thread: dict, first_meta: int | None):
        self.place = place
        self.identity = identity
        self.thread = thread
        self.first_meta = first_meta
        self.records: list[dict] = []
        self.models = _Models()
        self.range_copy: str | None = None  # the current line's fork range copy, if any

    def emit(self, line: Line, record: dict, kind, role: str, basis: str, *, copy: str | None = None,
             block: int | None = None, flags=(), private: dict | None = None,
             model: dict | None = None, requested=None, **fields) -> dict:
        """One object. A line inside a fork range takes that range's copy over its own; a
        known copy keeps no model and lists none in the header. An `ambiguous` line is not
        known to be a copy, so it keeps and lists its model (R24)."""
        copy = self.range_copy or copy
        at = ref(self.place, line.number, block)
        if copy in (None, "ambiguous"):
            if model is not None:
                self.models.add(model["value"], model["basis"], at, line.number)
            self.models.add(requested, "requested", at, line.number)
        else:
            model = None
        if copy in _HISTORY_COPIES:
            flags = ()
        out = _object(self.place, self.identity, line, block, record.get("timestamp"), role, basis,
                      kind, {**fields, "copy": copy, "model": model}, flags, private)
        self.records.append(out)
        return out

    # -- one native record --------------------------------------------------------------

    def read(self, line: Line, record: dict, range_copy: str | None) -> None:
        self.range_copy = range_copy
        top = record.get("type")
        payload = _dict(record, "payload")
        if top == "session_meta":
            self.session_meta(line, record, payload)
        elif top == "turn_context":
            model = _str(payload.get("model"))
            self.emit(line, record, top, "metadata", "structure", flags={"turn_context"},
                      private=self.turn_id(payload),
                      model={"value": model, "basis": "runtime"} if model else None,
                      text=_compact(record))
        elif top == "event_msg":
            self.event(line, record, payload)
        elif top == "response_item":
            self.item(line, record, payload)
        elif top == "compacted":
            self.compacted(line, record, payload)
        elif isinstance(top, str) and top in _CODEX_METADATA:
            self.emit(line, record, top, "metadata", "structure", text=_compact(record))
        else:
            self.emit(line, record, top, "unknown", "kind", text=_compact(record))

    @staticmethod
    def turn_id(payload: dict) -> dict:
        turn = _str(payload.get("turn_id"))
        return {"_turn_id": turn} if turn is not None else {}

    def session_meta(self, line: Line, record: dict, payload: dict) -> None:
        """Every `session_meta` is metadata; only the first gives the creation model."""
        model = None
        if line.number == self.first_meta:
            value = _str(_dict(_dict(payload, "base_instructions"), "provenance").get("model"))
            model = {"value": value, "basis": "creation"} if value else None
        self.emit(line, record, "session_meta", "metadata", "structure", model=model,
                  text=_compact(record))

    def event(self, line: Line, record: dict, payload: dict) -> None:
        sub = _str(payload.get("type"))
        kind = f"event_msg/{sub}" if sub else "event_msg"
        if sub in _CODEX_TURN_EVENTS:
            private = self.turn_id(payload)
            if sub == "task_complete" and "last_agent_message" in payload:
                private["_last_agent_message"] = _str(payload["last_agent_message"])
            if sub == "turn_aborted":
                private["_abort_reason"] = _str(payload.get("reason"))
            self.emit(line, record, kind, "metadata", "structure", flags={sub}, private=private,
                      text=_compact(record))
        elif sub == "item_completed":
            self.completed_item(line, record, _dict(payload, "item"))
        elif sub in _CODEX_MIRROR_EVENTS:
            self.emit(line, record, kind, "metadata", "structure", copy="event_mirror",
                      text=_str(payload.get("message")) or "")
        else:
            self.emit(line, record, kind, "unknown", "kind", text=_compact(record))

    def completed_item(self, line: Line, record: dict, item: dict) -> None:
        sub = _str(item.get("type"))
        kind = f"event_msg/item_completed/{sub}" if sub else "event_msg/item_completed"
        if sub in _CODEX_MIRROR_ITEMS:
            questions = item.get("questions")
            self.emit(line, record, kind, "metadata", "structure", copy="event_mirror",
                      flags={"asks_user"} if isinstance(questions, list) and questions else (),
                      phase=_str(item.get("phase")), message_id=_str(item.get("id")),
                      text=_text_of(item.get("content")))
        elif sub == "CommandExecution":
            execution = {k: item.get(k) for k in ("command", "exit_code", "cwd", "status")}
            self.emit(line, record, kind, "metadata", "structure", execution=execution,
                      text=_compact(record))
        elif sub == "SubAgentActivity":
            binding = {"call": _str(item.get("id")), "thread": _str(item.get("agent_thread_id")),
                       "agent_path": _str(item.get("agent_path")), "kind": _str(item.get("kind"))}
            self.emit(line, record, kind, "metadata", "structure", private={"_subagent": binding},
                      text=_compact(record))
        else:
            self.emit(line, record, kind, "metadata", "structure", text=_compact(record))

    def speaker(self, payload: dict) -> tuple[str, str]:
        """The role and basis of a `message` or `agent_message`."""
        if payload.get("type") == "agent_message":
            if not self.thread["child"]:
                return "injected", "agent_path"
            author = payload.get("author")
            if self.thread["controller"] is None or not isinstance(author, str):
                return "unknown", "agent_path"
            return ("dispatch" if author == self.thread["controller"] else "injected"), "agent_path"
        role = payload.get("role")
        if role == "user":
            if _injected_prefix(_codex_lead(payload.get("content"))):
                return "injected", "prefix_rule"
            return ("dispatch" if self.thread["child"] else "human"), "prefix_rule"
        if role == "developer":
            return "injected", "structure"
        if role == "assistant":
            return "assistant", "structure"
        return "unknown", "kind"

    def item(self, line: Line, record: dict, payload: dict, history: int | None = None) -> None:
        """A `response_item` payload, or (with `history`, its index) one entry of a
        `compacted` record's `replacement_history`, which is one object of that record."""
        sub = _str(payload.get("type"))
        if history is not None:
            kind, copy, block = "compacted", "compaction_history", history
        else:
            kind, copy, block = (f"response_item/{sub}" if sub else "response_item"), None, None
        common = {"copy": copy, "block": block}
        if sub in ("message", "agent_message"):
            self.message(line, record, payload, kind, common)
        elif sub in _CODEX_CALLS:
            self.call(line, record, payload, sub, kind, common)
        elif sub in _CODEX_OUTPUTS:
            output = payload.get("output")
            is_error = None
            if isinstance(output, dict):
                is_error = (not output["success"]) if isinstance(output.get("success"), bool) else None
                output = output.get("content")
            text = output if isinstance(output, str) else _text_of(output) if isinstance(output, list) \
                else _compact(output) if output is not None else ""
            self.emit(line, record, kind, "tool_output", "structure", **common,
                      block_type=sub if history is not None else None,
                      call={"id": payload.get("call_id"), "peer": None, "is_error": is_error}, text=text)
        elif sub == "reasoning":
            parts = [b["text"] for key in ("summary", "content")
                     for b in (payload.get(key) if isinstance(payload.get(key), list) else ())
                     if isinstance(b, dict) and isinstance(b.get("text"), str)]
            secret = payload.get("encrypted_content")
            encrypted = isinstance(secret, str) and bool(secret)
            text = "\n".join(parts)
            self.emit(line, record, kind, "assistant", "structure", **common, block_type="reasoning",
                      text=None if encrypted and not text else text, encrypted=encrypted or None)
        else:
            self.emit(line, record, kind, "unknown", "kind", **common,
                      block_type=sub if history is not None else None, text=_compact(payload))

    def message(self, line: Line, record: dict, payload: dict, kind: str, common: dict) -> None:
        role, basis = self.speaker(payload)
        flags = {"prompt"} if role in ("human", "injected", "dispatch") else set()
        fields = {"phase": _str(payload.get("phase")), "message_id": _str(payload.get("id"))}
        content = payload.get("content")
        if payload.get("role") == "user":
            fields["origin"] = origin(content, "codex")
        if common["copy"] is not None or not isinstance(content, list):
            self.emit(line, record, kind, role, basis, **common, flags=flags,
                      block_type=_str(payload.get("type")) if common["copy"] else None,
                      text=_text_of(content), **fields)
            return
        for index, block in enumerate(content):
            block = block if isinstance(block, dict) else {}
            text, encrypted = _codex_block(block)
            self.emit(line, record, kind, role, basis, copy=None, block=index, flags=flags,
                      block_type=_str(block.get("type")), text=text, encrypted=encrypted or None,
                      **fields)

    def call(self, line: Line, record: dict, payload: dict, sub: str, kind: str, common: dict) -> None:
        name = _str(payload.get("name"))
        call = {"id": _str(payload.get("call_id")) or _str(payload.get("id")),
                "tool": name or sub[:-len("_call")], "peer": None}
        requested = None
        if sub == "function_call":
            value = payload.get("arguments")
            arguments = _arguments(value)
            command = _joined(arguments.get("cmd", arguments.get("command"))) if name in _CODEX_SHELL else None
            if name == "spawn_agent":
                requested = arguments.get("model")
        elif sub == "custom_tool_call":
            value, command = payload.get("input"), None
        else:
            value = payload.get("action")
            command = _joined(_dict(payload, "action").get("command")) if sub == "local_shell_call" else None
        if command is not None:
            call["command"] = command
        text = value if isinstance(value, str) else _compact(value)
        self.emit(line, record, kind, "tool_call", "structure", **common, requested=requested,
                  block_type=sub if common["copy"] else None, call=call,
                  text=text + (f"\n{command}" if command else ""))

    def compacted(self, line: Line, record: dict, payload: dict) -> None:
        """The record is metadata (its text without the history it carries); each
        `replacement_history` entry is a `compaction_history` copy, block-numbered."""
        rest = {k: v for k, v in payload.items() if k != "replacement_history"}
        self.emit(line, record, "compacted", "metadata", "structure",
                  text=_compact({**record, "payload": rest}))
        history = payload.get("replacement_history")
        for index, entry in enumerate(history if isinstance(history, list) else ()):
            self.item(line, record, entry if isinstance(entry, dict) else {}, history=index)


def _fork_ranges(parsed: list[tuple[Line, dict]], inherited_line: int | None,
                 known: set[str] | None) -> dict[int, str]:
    """Mark Codex fork copies: each line after the second `session_meta` is `fork_history`
    until the first `task_started` whose turn id the inherited rollout does not hold; with
    that rollout unreadable (`known` None), every such line is `ambiguous` to the end."""
    if inherited_line is None:
        return {}
    copies = {}
    for line, record in parsed:
        if line.number <= inherited_line:
            continue
        if known is None:
            copies[line.number] = "ambiguous"
            continue
        starts, turn = _turn_start(record)
        if starts and turn not in known:
            break
        copies[line.number] = "fork_history"
    return copies


def _mirror_originals(records: list[dict]) -> None:
    """An event mirror's `original`: the first non-copy response message with its id."""
    first: dict[str, str] = {}
    for r in records:
        if r["kind"] in ("response_item/message", "response_item/agent_message") \
                and "copy" not in r and "message_id" in r:
            first.setdefault(r["message_id"], r["ref"])
    for r in records:
        if r.get("copy") == "event_mirror" and r.get("message_id") in first:
            r["original"] = first[r["message_id"]]


def codex_read(place: Place, size: int,
               inherited_turn_ids: Callable[[str], Collection[str] | None], *, data: bytes | None = None) -> FileRead:
    """A Codex rollout's first `size` bytes as records (without `turn`), the
    unparsed lines, and the file's header. Identity is the first `session_meta`'s
    `payload.id`. A second `session_meta` makes the rollout a fork of the thread it
    names: `inherited_turn_ids(id)` gives that thread's full `turn_ids` (copies included),
    or None when its rollout is unreadable."""
    parsed, unparsed, count, observed = _decoded(place, size, data)
    metas = [(line, r) for line, r in parsed if r.get("type") == "session_meta"]
    first = _dict(metas[0][1], "payload") if metas else {}
    session = _str(first.get("id"))
    identity = {"session": session, "agent": None,
                "identity_basis": "session_meta" if session else None}
    thread = _thread(first)
    inherited_line = metas[1][0].number if len(metas) > 1 else None
    inherited_id = _str(_dict(metas[1][1], "payload").get("id")) if len(metas) > 1 else None
    known = None
    if inherited_id is not None:
        found = inherited_turn_ids(inherited_id)
        known = None if found is None else set(found)
    copies = _fork_ranges(parsed, inherited_line, known)
    reader = _CodexFile(place, identity, thread, metas[0][0].number if metas else None)
    for line, record in parsed:
        reader.read(line, record, copies.get(line.number))
    pair_calls(reader.records)
    _mirror_originals(reader.records)
    starts = [r for r in reader.records if r["kind"] == "event_msg/task_started" and "_turn_id" in r]
    first_at, last_at = _span(parsed)
    header = {
        **identity,
        "recorded_identity": observed,
        "parent": thread["parent"],
        "agent_path": thread["agent_path"],
        "depth": thread["depth"],
        "inherited_id": inherited_id,
        "child": thread["child"],
        "child_basis": "native" if thread["parent"] is not None or isinstance(first.get("thread_source"), str)
                       else "heuristic",
        "forked": inherited_line is not None,
        "cwd": _str(first.get("cwd")),
        "entrypoint": _str(first.get("originator")),
        "cli_version": _str(first.get("cli_version")),
        "first_at": first_at,
        "last_at": last_at,
        "lines": count,
        "turn_ids": [r["_turn_id"] for r in starts],
        "own_turn_ids": [r["_turn_id"] for r in starts if "copy" not in r],
        "models": reader.models.listed,
        "_model_refs": reader.models.refs,
    }
    return FileRead(place, reader.records, unparsed, header)


# ---------------------------------------------------------------------------------------
# Claude SDK stream-json capture
# ---------------------------------------------------------------------------------------

def sdk_read(place: Place, size: int, *, data: bytes | None = None) -> FileRead:
    """A Claude SDK `stream-json` capture as records. Identity is the events' shared
    `session_id`, which links nothing (SL9). An event's `parent_tool_use_id` names the
    dispatching call: `dispatch: {kind: sdk_dispatch, call}`; a prompt inside a dispatch is
    the child's brief, `dispatch`."""
    parsed, unparsed, count, observed = _decoded(place, size, data)
    session = next((r["session_id"] for _l, r in parsed if isinstance(r.get("session_id"), str)), None)
    identity = {"session": session, "agent": None,
                "identity_basis": "session_id" if session else None, "parent": None}
    records: list[dict] = []
    models = _Models()
    for line, record in parsed:
        kind = record.get("type")
        parent = _str(record.get("parent_tool_use_id"))
        dispatch = {"kind": "sdk_dispatch", "call": parent} if parent else None

        def emit(role, basis, kind, block=None, flags=(), **fields):
            records.append(_object(place, identity, line, block, record.get("timestamp"), role,
                                   basis, kind, {"dispatch": dispatch, **fields,
                                   **({"origin": evidence} if record.get("type") == "user" else {})}, flags))
        message = _dict(record, "message")
        content = message.get("content")
        evidence = origin(content, "claude-code", _dict(record, "origin").get("kind"),
                          [name for key, name in (("isMeta", "meta"), ("isCompactSummary", "compaction_summary"))
                           if record.get(key)])
        blocks = [b if isinstance(b, dict) else {} for b in content] if isinstance(content, list) else None
        if kind == "assistant":
            value = _str(message.get("model"))
            model = {"value": value, "basis": "runtime"} if value and value != "<synthetic>" else None
            if model:
                models.add(value, "runtime", ref(place, line.number), line.number)
            if not blocks:
                emit("assistant", "structure", kind, text=_text_of(content), model=model)
            for index, block in enumerate(blocks or ()):
                text, encrypted = _block_text(block)
                emit("tool_call" if block.get("type") == "tool_use" else "assistant", "structure",
                     kind, index, block_type=_str(block.get("type")), call=_call(block),
                     message_id=_str(message.get("id")), model=model, text=text,
                     encrypted=encrypted or None)
        elif kind == "user":
            role, basis, decided = _user_role(record, _lead(content))
            if role == "human" and parent:
                role, basis = "dispatch", "structure"
            prompt = {"prompt"} | decided
            if not blocks:
                emit(role, basis, kind, flags=prompt, text=_text_of(content))
            for index, block in enumerate(blocks or ()):
                text, encrypted = _block_text(block)
                result = block.get("type") == "tool_result"
                emit("tool_output" if result else role, "structure" if result else basis, kind, index,
                     flags={"tool_result"} if result else prompt, block_type=_str(block.get("type")),
                     call=_call(block), text=text, encrypted=encrypted or None)
        elif kind in ("system", "result"):
            sub = _str(record.get("subtype"))
            emit("metadata", "structure", f"{kind}/{sub}" if sub else kind, text=_compact(record))
        else:
            emit("unknown", "kind", kind, text=_compact(record))
    pair_calls(records)
    first_at, last_at = _span(parsed)
    header = {**identity, "recorded_identity": observed,
              "first_at": first_at, "last_at": last_at, "lines": count,
              "models": models.listed, "_model_refs": models.refs}
    return FileRead(place, records, unparsed, header)
