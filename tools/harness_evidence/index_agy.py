"""The agy index adapter: discovery facts, the summaries side input, the header and the
index extractor.

Each conversation is brain/<id>/.system_generated/logs/transcript_full.jsonl; its
transcript.jsonl beside it is a truncated mirror and is refused here. Path facts come from
one read of conversation_summaries.db per call (spec rev 2 §4.2); callers resolve them once
per file and derive the side-input fingerprint from that one snapshot.
"""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re

from . import agy_summaries
from .discover import AGY_FULL, AGY_MIRROR
from .header import _lines, _proof
from .index_coverage import applied, count_record, coverage_rows, day_of
from .lines import _finite_float, _reject_constant, ref

__all__ = ["extract", "Restart", "provenance_defaults", "bind", "ABSENT", "WATCHED", "APPLIED", "UNWATCHED",
           "COMMON_READS", "KNOWN_KINDS", "PROVENANCE", "COVERAGE_KEYS", "TOOL_KINDS", "FEATURES",
           "SIDE_INPUTS", "header", "path_facts", "side_inputs", "refusal"]

SIDE_INPUTS = {agy_summaries.NAME: agy_summaries.DECLARATION}
_RULE = "agy_conversation_summaries"


def _conversation(place) -> str:
    return PurePosixPath(place.relpath).parts[1]


def _home(place) -> Path:
    """The agy home: the logical path less its `brain/...` relpath."""
    return place.path.parents[len(PurePosixPath(place.relpath).parts) - 1]


def refusal(place) -> str | None:
    """agy reads only brain/<id>/.system_generated/logs/transcript_full.jsonl."""
    parts = PurePosixPath(place.relpath).parts
    if (len(parts) != 5 or ".." in parts or parts[0] != "brain" or parts[2:4] != (".system_generated", "logs")
            or parts[4] not in (AGY_FULL, AGY_MIRROR)):
        return f"agy index reads brain/<id>/.system_generated/logs/{AGY_FULL}"
    if parts[4] == AGY_MIRROR:
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


# --- index extraction (spec rev 2 §4.3-§4.5) ---------------------------------------------

class Restart(Exception):
    """agy appends steps, so the extractor never invalidates a pass (spec rev 2 §4.5)."""

    def __init__(self, reason, seed):
        super().__init__(reason)
        self.reason, self.seed = reason, seed


_USAGE = ("input_tokens", "cache_read_tokens", "output_tokens")
_WRAPPERS = ("USER_REQUEST", "ADDITIONAL_METADATA", "USER_SETTINGS_CHANGE", "SKILL")
_WRAPPER = {name: re.compile(rf"<{name}>\n?(.*?)\n?</{name}>", re.S) for name in _WRAPPERS}
_SLASH = re.compile(r"(?:^|\n)/(\S+) is a \[Slash Command\]")
_CREATED = re.compile(r"^Created At: (\S+)$", re.M)
_COMPLETED = re.compile(r"^Completed At: (\S+)$", re.M)
_EXIT = re.compile(r"^Command exited with code (-?\d+)\.$", re.M)
_NOTIFIED_EXIT = re.compile(r"Command exited with code (-?\d+)")
_PREVIEW = "The tool's output was truncated due to being too long"
_OUTPUT = "Command output:"
_BACKGROUND = re.compile(r"background task with task id: (\S+)")
_SENDER = re.compile(r"\bsender=(\S+)")
_ENDED = (("finished with result:", "finished"), ("was canceled with result:", "canceled"))
_CHILD = re.compile(r'"conversationId":\s*"([^"]+)"')
_ANSWER = re.compile(r"^(A\d+): ?", re.M)
_HOOK = re.compile(r"injected by an? (\w+) hook")

KNOWN_KINDS = frozenset({"USER_INPUT", "PLANNER_RESPONSE", "GENERIC", "SYSTEM_MESSAGE", "CHECKPOINT",
                         "ERROR_MESSAGE"})
COMMON_READS = ("type", "step_index", "created_at", "source")
WATCHED = {
    "USER_INPUT": {"sources": ("content",), "inputs": {"content": ("content",)}},
    "PLANNER_RESPONSE": {"sources": ("content", "tool_calls", "model", "thinking", *_USAGE),
                         "inputs": {"content": ("content",), "calls": ("tool_calls",), "model": ("model",),
                                    "usage": _USAGE}},
    "GENERIC": {"sources": ("status", "content"), "inputs": {"status": ("status",), "content": ("content",)}},
    "SYSTEM_MESSAGE": {"sources": ("content",), "inputs": {"content": ("content",)}},
    "CHECKPOINT": {"sources": ("content", *_USAGE), "inputs": {"content": ("content",), "usage": _USAGE}},
    "ERROR_MESSAGE": {"sources": ("error",), "inputs": {"error": ("error",)}},
}
APPLIED = {
    "usage": _USAGE,  # each planner or checkpoint step that became a response
    "tool_call": ("name", "args"),  # each planner tool call
    "run_command": ("command",),  # run_command call inputs
    # each GENERIC step; call: a call was waiting for it; calls_known: no ineligible planner
    # step since the last eligible one left the waiting calls unknown
    "result": ("call", "content", "calls_known"),
    "exit_line": ("exit_code",),  # each paired DONE run_command result
    "result_times": ("created", "completed"),  # each paired result
    "background": ("call",),  # each background wake-up; call: its sender was open
    "child": ("conversation",),  # each invoke_subagent result
    "answers": ("answers",),  # each ask_question result
    "user_request": ("request",),  # each USER_EXPLICIT input
}
UNWATCHED = {
    "PLANNER_RESPONSE": {"tool_calls[].name": "applied:tool_call", "tool_calls[].args": "applied:tool_call",
                         "tool_calls[].args.CommandLine": "applied:run_command",
                         "tool_calls[].args.Path": "dimension", "tool_calls[].args.Prompt": "dimension",
                         "tool_calls[].args.questions": "dimension"},
}
_CONVENTION = {
    "flush_response": "agy_step_response", "identity.session": "agy_brain_directory",
    "identity.index_session": "agy_brain_directory", "identity.entrypoint": "agy_entrypoint",
    "response.id": "agy_step_response", "message.origin": "agy_wrappers", "calls[].id": "agy_call_position",
    "calls[].kind": "agy_tool_kind", "calls[].paths": "agy_workspace_paths",
    "calls[].paths_complete": "agy_workspace_paths", "calls[].skill": "agy_skill_block",
    "results[].call_id": "agy_positional_pairing", "results[].native_duration_ms": "agy_result_times",
    "results[].background_id": "agy_background_id", "results[].child_session": "agy_child_conversation",
    "results[].answers": "agy_answer_lines", "results[].truncation": "agy_preview_truncation",
    "results[].exit_code": "agy_exit_line", "injections": "agy_injections",
    "response.usage_present.thinking": "agy_no_thinking_record",
    "notifications": "agy_background_message", "interruption": "agy_stream_interrupted",
}
_SUMMARY_FIELDS = {"identity.parent": "parent_conversation_id", "identity.subagent": "parent_conversation_id",
                   "identity.cwd": "workspace_uris"}
_ABSENT = {
    "identity.agent": "not_recorded", "identity.version": "not_recorded", "response.effort": "not_recorded",
    "response.usage.cache_write": "not_recorded",
    "response.usage.thinking": "not_recorded", "calls[].background": "known_after_call",
    "results[].interrupted": "not_recorded", "results[].agent": "not_recorded",
    "fork_boundary": "no_fork_records", "turn_end": "no_turn_end_records",
}
ABSENT = _ABSENT  # Published in the capabilities index block (spec rev 2 §7).
_SUMMARY = [f"{agy_summaries.TABLE}.{column}" for column in ("parent_conversation_id",)]
PROVENANCE = {
    "native_kind": ["type"], "eligible": ["created_at", "step_index"], "flush_response": ["type"],
    "calls[].block": ["tool_calls"], "identity.session": [], "identity.index_session": [],
    "identity.agent": [], "identity.parent": _SUMMARY, "identity.subagent": _SUMMARY,
    "identity.cwd": [f"{agy_summaries.TABLE}.workspace_uris"], "identity.entrypoint": [],
    "identity.version": [], "at_ms": ["created_at"], "response.id": ["step_index"],
    "response.model": ["model"], "response.effort": [], "response.native": [*_USAGE, "thinking"],
    "response.usage_present.output": ["output_tokens"], "response.usage_present.thinking": [],
    "response.usage.input_uncached": ["input_tokens"], "response.usage.cache_read": ["cache_read_tokens"],
    "response.usage.cache_write": [], "response.usage.output": ["output_tokens"],
    "response.usage.thinking": [], "response.usage.context_total": ["input_tokens", "cache_read_tokens"],
    "response.usage.uncached_total": ["input_tokens"], "message.channel": ["type", "source"],
    "message.origin": ["content", "source"], "message.text": ["content", "error"],
    "message.blocks": ["content", "error"], "message.joined_bytes": ["content", "error"],
    "message.joined_nonempty": ["content", "error"],
    "message.assistant_output_bytes": ["content", "tool_calls[].args"],
    "calls[].id": ["step_index"], "calls[].native_name": ["tool_calls[].name"],
    "calls[].kind": ["tool_calls[].name"], "calls[].input_bytes": ["tool_calls[].args"],
    "calls[].command": ["tool_calls[].args.CommandLine"],
    "calls[].paths": ["tool_calls[].args.Path", f"{agy_summaries.TABLE}.workspace_uris"],
    "calls[].paths_complete": ["tool_calls[].args.Path", f"{agy_summaries.TABLE}.workspace_uris"],
    "calls[].raw_path": ["tool_calls[].args.Path"], "calls[].background": [], "calls[].skill": ["content"],
    "calls[].prompt": ["tool_calls[].args.Prompt"], "calls[].questions": ["tool_calls[].args.questions"],
    "results[].call_id": ["step_index"], "results[].bytes": ["content"], "results[].error": ["status"],
    "results[].interrupted": [], "results[].native_duration_ms": ["content"],
    "results[].background_id": ["content"], "results[].agent": [], "results[].child_session": ["content"],
    "results[].answers": ["content"], "results[].truncation": ["content"], "results[].exit_code": ["content"],
    "injections": ["content", "source"], "notifications": ["content"], "compaction": ["type"],
    "interruption": ["error"], "fork_boundary": [], "turn_end": [],
}
COVERAGE_KEYS = {
    "response.model": ["PLANNER_RESPONSE/input:model"],
    "response.native": ["applied:usage/input:input_tokens", "applied:usage/input:cache_read_tokens",
                        "applied:usage/input:output_tokens"],
    "response.usage.input_uncached": ["applied:usage/input:input_tokens"],
    "response.usage.cache_read": ["applied:usage/input:cache_read_tokens"],
    "response.usage.output": ["applied:usage/input:output_tokens"],
    "response.usage.context_total": ["applied:usage/input:input_tokens", "applied:usage/input:cache_read_tokens"],
    "response.usage.uncached_total": ["applied:usage/input:input_tokens"],
    "calls[].native_name": ["applied:tool_call/input:name"],
    "calls[].input_bytes": ["applied:tool_call/input:args"],
    "calls[].command": ["applied:run_command/input:command"],
    "results[].call_id": ["applied:result/input:call", "applied:result/input:calls_known"],
    "results[].bytes": ["applied:result/input:content"],
    "results[].exit_code": ["applied:exit_line/input:exit_code"],
    "results[].native_duration_ms": ["applied:result_times/input:created", "applied:result_times/input:completed"],
    "results[].child_session": ["applied:child/input:conversation"],
    "results[].answers": ["applied:answers/input:answers"],
    "notifications": ["applied:background/input:call"],
    "message.text": ["USER_INPUT/input:content", "PLANNER_RESPONSE/input:content"],
}
TOOL_KINDS = {"run_command": "shell", "read_file": "file_read", "write_file": "file_edit",
              "edit_file": "file_edit", "invoke_subagent": "dispatch", "ask_question": "question",
              "SKILL": "skill"}  # SKILL: the call a <SKILL> block in a user input becomes
_WRITERS = frozenset({"write_file", "edit_file"})
FEATURES = {"native_skill_events": False, "question_option_labels": False}


def provenance_defaults() -> dict[str, dict]:
    """Owned complete declarations, the same field set as Claude's (spec rev 2 §4.4)."""
    defaults = {}
    for field, paths in PROVENANCE.items():
        proof = {"native_paths": list(paths), "coverage_keys": list(COVERAGE_KEYS.get(field, [])),
                 "basis": "native", "rule": "agy_native"}
        if field in _CONVENTION:
            proof.update(basis="convention", rule=_CONVENTION[field])
        if field in _SUMMARY_FIELDS:
            proof.update(rule=_RULE)
        if field in _ABSENT:
            proof.update(rule="absent:" + _ABSENT[field])
        if field == "compaction":
            proof.update(rule="agy_checkpoint")
        defaults[field] = proof
    return defaults


def bind(state: dict, facts: dict) -> None:
    """The one summaries snapshot the decode uses (spec rev 2 §4.2)."""
    state["path_facts"] = facts


def _size(value) -> int:
    value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return len(value.encode("utf-8"))


def _seconds(text, pattern) -> int | None:
    match = pattern.search(text)
    return _at_ms(match.group(1)) if match else None


def _origin(content: str, native: str) -> dict:
    stripped = content.strip()
    markers = []
    for name in _WRAPPERS:
        tag = f"<{name}>"
        if tag in content:
            markers.append({"name": name, "lead": "start" if content.startswith(tag) else "inside",
                            "joined": "start" if stripped.startswith(tag) else "inside"})
    for name, tag in (("SYSTEM_MESSAGE", "<SYSTEM_MESSAGE>"), ("message_sender", "[Message] sender=")):
        if tag in content:
            markers.append({"name": name, "lead": "start" if content.startswith(tag) else "inside",
                            "joined": "start" if stripped.startswith(tag) else "inside"})
    return {"native_kind": native, "flags": [], "markers": markers,
            "unrecognized_tag": {"lead": False, "joined": False}}


def _message(channel: str, text: str, origin: dict, output_bytes: int = 0) -> dict:
    return {"channel": channel, "origin": origin, "text": text, "joined_nonempty": bool(text.strip()),
            "joined_bytes": _size(text), "assistant_output_bytes": output_bytes,
            "blocks": [{"block": 0, "text": text, "bytes": _size(text)}] if text else []}


def _usage(step: dict, planner: bool) -> tuple[dict, dict, dict]:
    values = {name: step.get(name) for name in _USAGE}
    numbers = {name: value if isinstance(value, int) and not isinstance(value, bool) else None
               for name, value in values.items()}
    uncached, read = numbers["input_tokens"], numbers["cache_read_tokens"]
    usage = {"input_uncached": uncached, "cache_read": read, "cache_write": None,
             "output": numbers["output_tokens"], "thinking": None,
             "context_total": None if uncached is None or read is None else uncached + read,
             "uncached_total": uncached}
    native = {name: value for name, value in values.items() if name in step}
    thinking = step.get("thinking") if planner else None
    if isinstance(thinking, str):
        native["thinking_text_bytes"] = _size(thinking)
    # A presence flag is a boolean: agy never records a thinking count, so the flag is a
    # constant False, declared by convention (agy_no_thinking_record), not absent.
    return usage, {"output": "output_tokens" in step, "thinking": False}, native


def _paths(value, cwd) -> tuple[list[str], bool]:
    if not isinstance(value, str) or not value:
        return [], False
    if posixpath.isabs(value):
        return [posixpath.normpath(value)], True
    if cwd is None:
        return [], False
    return [posixpath.normpath(posixpath.join(cwd, value))], True


def _call(conversation, number, index, call, cwd) -> dict:
    name = call.get("name")
    args = call.get("args")
    args = args if isinstance(args, dict) else {}
    kind = TOOL_KINDS.get(name, "other")
    paths, complete = _paths(args.get("Path"), cwd) if kind in ("file_read", "file_edit") else ([], True)
    raw = args.get("Path") if name in _WRITERS else None
    prompt = args.get("Prompt") if kind == "dispatch" else None
    command = args.get("CommandLine") if kind == "shell" else None
    if kind == "dispatch":  # As Claude's: a dispatch's paths are complete when its prompt is.
        complete = isinstance(prompt, str) and bool(prompt)
    questions = args.get("questions") if kind == "question" else None
    return {"id": f"{conversation}:{number}:{index}", "native_name": name if isinstance(name, str) else None,
            "kind": kind, "input_bytes": _size(args), "command": command if isinstance(command, str) else None,
            "paths": paths, "paths_complete": complete, "raw_path": raw if isinstance(raw, str) and raw else None,
            "background": None, "skill": None, "prompt": prompt if isinstance(prompt, str) and prompt else None,
            "questions": questions if isinstance(questions, list) else [], "block": index}


def _skill(conversation, number, content) -> list[dict]:
    block, slash = _WRAPPER["SKILL"].search(content), _SLASH.search(content)
    if block is None or slash is None:
        return []
    return [{"id": f"{conversation}:{number}:skill", "native_name": "SKILL", "kind": "skill",
             "input_bytes": _size(block.group(1)), "command": None, "paths": [], "paths_complete": True,
             "raw_path": None, "background": None, "skill": slash.group(1), "prompt": None, "questions": [],
             "block": 0}]


def _result(state, session, day, call_id, name, step, content) -> dict:
    status = step.get("status")
    created, completed = _seconds(content, _CREATED), _seconds(content, _COMPLETED)
    applied(state, session, day, "result_times", {"created": created is not None, "completed": completed is not None})
    head = content.split(_OUTPUT, 1)[0]
    exit_code = truncation = child = answers = background = None
    # Only a DONE result can carry the line: a RUNNING one reports its code later in its
    # wake-up (notifications[].exit_code), and an ERROR one is a tool that did not run.
    if name == "run_command" and status == "DONE":
        match = _EXIT.search(head)
        applied(state, session, day, "exit_line", {"exit_code": match is not None})
        exit_code = int(match.group(1)) if match else None
    if name == "run_command" and _PREVIEW in head:
        truncation = {"kind": "tool_preview", "original_tokens": None, "original_bytes": None}
    if status == "RUNNING":
        started = _BACKGROUND.search(content)
        if started is not None:
            background = started.group(1)
            state.setdefault("background", {})[background] = call_id
    if name == "invoke_subagent":
        found = _CHILD.search(content)
        applied(state, session, day, "child", {"conversation": found is not None})
        child = found.group(1) if found else None
    if name == "ask_question":
        # Each answer runs from its A<n>: line to the next one; an answer may span lines.
        marks = list(_ANSWER.finditer(content))
        applied(state, session, day, "answers", {"answers": bool(marks)})
        ends = [mark.start() for mark in marks[1:]] + [len(content)]
        answers = {mark.group(1): content[mark.end():end].rstrip() for mark, end in zip(marks, ends)} or None
    return {"call_id": call_id, "bytes": _size(content), "error": status == "ERROR", "interrupted": None,
            "native_duration_ms": None if created is None or completed is None else completed - created,
            "background_id": background, "agent": None, "child_session": child, "answers": answers,
            "truncation": truncation, "exit_code": exit_code}


def _wake_up(content):
    """(sender, status, result text) of a background task's end; the first sender and the
    first marker are the message's own, the result may quote others."""
    sender = _SENDER.search(content)
    found = [(content.find(marker), marker, status) for marker, status in _ENDED if marker in content]
    if sender is None or not found:
        return None
    at, marker, status = min(found)
    return sender.group(1), status, content[at + len(marker):]


def _without_text(event):
    if event["message"]:
        event["message"].pop("text")
        for block in event["message"]["blocks"]:
            block.pop("text")
    for call in event["calls"]:
        for key in ("command", "paths", "raw_path", "skill", "prompt", "questions"):
            call.pop(key)
    for result in event["results"]:
        result.pop("answers")
    for injection in event["injections"]:
        injection.pop("source")
    event["identity"].pop("cwd")  # As Claude's text-off identity.


def extract(lines, state, *, place, text: bool):
    """One index_event per step line (spec rev 2 §4.3); `state` carries the open calls, the
    open background ids, coverage and the malformed count across resumed passes."""
    facts = state["path_facts"]
    conversation = _conversation(place)
    identity = {"session": conversation, "index_session": conversation, "agent": None,
                "parent": facts["parent"], "subagent": facts["subagent"], "cwd": facts["cwd"],
                "entrypoint": "agy", "version": None}
    # Unknown, not a declared absence: agy records these facts and this row is not available.
    unresolved = ({field: {"native_paths": [], "rule": "unresolved:" + facts["reason"]} for field in _SUMMARY_FIELDS}
                  if facts["reason"] is not None else {})
    number, partial = state.get("next_line", 1), False
    for offset, raw in lines:
        position = {"key": f"E{offset}", "line": number, "offset": offset, "end": offset + len(raw),
                    "ref": ref(place, number), "sha256": hashlib.sha256(raw).hexdigest()}
        if not raw.endswith(b"\n"):
            partial = True
            yield {"object": "unparsed", **position, "reason": "truncated", "provisional": True}
            break
        state["next_line"], state["next_offset"] = number + 1, offset + len(raw)
        number += 1
        try:
            step = json.loads(raw.decode("utf-8", errors="replace"), parse_float=_finite_float,
                              parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            step = None
        if not isinstance(step, dict):
            state["malformed"] = state.get("malformed", 0) + 1
            yield {"object": "unparsed", **position, "reason": "malformed", "provisional": False}
            continue
        kind = str(step.get("type"))
        at_ms = _at_ms(step.get("created_at"))
        index = step.get("step_index")
        eligible = at_ms is not None and isinstance(index, int) and not isinstance(index, bool)
        day = day_of(at_ms) if eligible else state.get("coverage_day")
        if eligible:
            state["coverage_day"] = day
        count_record(state, conversation, day, kind, kind in KNOWN_KINDS, step, WATCHED)
        event = {"object": "index_event", **position, "native_kind": kind, "identity": dict(identity),
                 "at_ms": at_ms, "eligible": eligible, "response": None, "flush_response": False,
                 "message": None, "calls": [], "results": [], "injections": [], "notifications": [],
                 "compaction": None, "interruption": None, "fork_boundary": None, "turn_end": None}
        source = step.get("source")
        if not eligible and kind == "GENERIC" and state.get("pending"):
            state["pending"].pop(0)  # It still answers its call; its fields cannot be trusted.
        elif not eligible and kind == "PLANNER_RESPONSE":
            state["pending"] = None  # Its calls are unknown, so no later result pairs with older ones.
        elif not eligible and kind == "SYSTEM_MESSAGE" and source == "SYSTEM":
            ended = _wake_up(step["content"]) if isinstance(step.get("content"), str) else None
            if ended is not None:  # Its task still ended; a later message cannot be its wake-up.
                state.get("background", {}).pop(ended[0], None)
        if eligible and kind in ("USER_INPUT", "PLANNER_RESPONSE", "CHECKPOINT", "GENERIC", "SYSTEM_MESSAGE"):
            content = step.get("content") if isinstance(step.get("content"), str) else ""
        if eligible and kind == "USER_INPUT":
            if source == "USER_EXPLICIT":
                request = _WRAPPER["USER_REQUEST"].search(content)
                applied(state, conversation, day, "user_request", {"request": request is not None})
                body = request.group(1).strip() if request else ""
                event["injections"] = [
                    {"piece": i, "native_kind": f"agy_wrapper:{name}", "source": name, "bytes": _size(found.group(1))}
                    for i, (name, found) in enumerate((name, _WRAPPER[name].search(content)) for name in _WRAPPERS[1:])
                    if found is not None]
                for piece, injection in enumerate(event["injections"]):
                    injection["piece"] = piece
                event["calls"] = _skill(conversation, index, content)
            else:
                body = content
            event["message"] = _message("user", body, _origin(content, str(source)))
        elif eligible and kind in ("PLANNER_RESPONSE", "CHECKPOINT"):
            usage, present, native = _usage(step, kind == "PLANNER_RESPONSE")
            applied(state, conversation, day, "usage", {name: step.get(name) is not None for name in _USAGE})
            event["flush_response"] = True
            event["response"] = {"id": f"{conversation}:{index}", "model": step.get("model") if kind == "PLANNER_RESPONSE" else None,
                                 "effort": None, "usage": usage, "usage_present": present, "native": native}
            if kind == "CHECKPOINT":
                event["compaction"] = {"summary": True, "basis": "native", "rule": "agy_checkpoint"}
                event["message"] = _message("system", content, _origin(content, str(source)))
                event["injections"] = [{"piece": 0, "native_kind": "compact_summary", "source": None,
                                        "bytes": _size(content)}]
            else:
                pending = []
                calls = step.get("tool_calls")
                for k, call in enumerate(calls if isinstance(calls, list) else []):
                    call = call if isinstance(call, dict) else {}
                    applied(state, conversation, day, "tool_call",
                            {"name": call.get("name") is not None, "args": call.get("args") is not None})
                    decoded = _call(conversation, index, k, call, identity["cwd"])
                    if decoded["kind"] == "shell":
                        applied(state, conversation, day, "run_command", {"command": decoded["command"] is not None})
                    event["calls"].append(decoded)
                    pending.append([decoded["id"], decoded["native_name"]])
                state["pending"] = pending
                event["message"] = _message("assistant", content, _origin(content, str(source)),
                                            _size(content) * bool(content) + sum(c["input_bytes"] for c in event["calls"]))
        elif eligible and kind == "GENERIC":
            known = state.get("pending", []) is not None
            pending = state.get("pending") or []
            applied(state, conversation, day, "result",
                    {"call": bool(pending), "content": "content" in step, "calls_known": known})
            if pending:
                call_id, name = pending.pop(0)
                event["results"] = [_result(state, conversation, day, call_id, name, step, content)]
        elif eligible and kind == "SYSTEM_MESSAGE":
            event["message"] = _message("system", content, _origin(content, str(source)))
            ended = _wake_up(content) if source == "SYSTEM" else None
            if ended is not None:
                call = state.setdefault("background", {}).pop(ended[0], None)
                applied(state, conversation, day, "background", {"call": call is not None})
            if ended is not None and call is not None:
                code = _NOTIFIED_EXIT.search(ended[2])
                event["notifications"] = [{"call_id": call, "status": ended[1],
                                           "exit_code": int(code.group(1)) if code else None}]
            elif source == "SYSTEM_SDK":
                hook = _HOOK.search(content)
                event["injections"] = [{"piece": 0, "native_kind": "agy_hook_injection",
                                        "source": f"{hook.group(1)} hook" if hook else None, "bytes": _size(content)}]
            else:
                event["injections"] = [{"piece": 0, "native_kind": "agy_system_message",
                                        "source": "<SYSTEM_MESSAGE>", "bytes": _size(content)}]
        elif eligible and kind == "ERROR_MESSAGE":
            error = step.get("error") if isinstance(step.get("error"), str) else ""
            event["message"] = _message("system", error, _origin(error, str(source)))
            if "stream was interrupted" in error.lower():
                event["interruption"] = {"user_marker": False, "system": True, "basis": "convention",
                                         "rule": "agy_stream_interrupted"}
        event["provenance"] = copy.deepcopy(unresolved)
        if not text:
            _without_text(event)
        yield event
    counts, fields = coverage_rows(state)
    yield {"object": "coverage", "key": "coverage", "records": counts, "fields": fields,
           "malformed": state.get("malformed", 0), "partial_tail": partial}
