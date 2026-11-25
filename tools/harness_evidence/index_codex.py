"""Codex index facts, independent of the consumer's measurement policy.

Native grammar and associations preserve OBS 1e0afad1. Consumer measurement
policy and accumulated turn replacement remain outside the decoder.
"""
import copy
import hashlib
import json
import math
import posixpath
import re

from . import labels, index_codex_runs as runs, index_codex_tools as tools
from . import _index_codex_skills as skills, _index_codex_outcomes as outcomes
from .index_events import Restart, _at_ms, _size, _join
from .index_codex_coverage import (COUNTERS, KNOWN_KINDS, RATE_LIMIT_PATHS, WATCHED, APPLIED, UNWATCHED,
                                   COMMON_READS, record_kind, day_of, count_record, applied, coverage_rows)
from .lines import Place, ref, _finite_float, _reject_constant

USAGE = {"cache_read": "cached_input_tokens", "cache_write": "cache_write_input_tokens",
         "output": "output_tokens", "thinking": "reasoning_output_tokens", "context_total": "input_tokens"}
INJECTED = ("# AGENTS.md", "<environment_context>", "<INSTRUCTIONS>",
            "<skills_instruct", "<turn_aborted>", "<permissions",
            "<user_shell", "<collaboration_mode")
SHELL = frozenset({"exec_command", "shell_command", "shell"})
DISPATCH = frozenset({"spawn_agent", "send_message", "followup_task"})
TOOL_KINDS = {**dict.fromkeys(SHELL, "shell"), "apply_patch": "patch", "exec": "script",
              "write_stdin": "poll", "wait": "poll", "wait_agent": "other",
              "request_user_input": "question", **dict.fromkeys(DISPATCH, "dispatch")}
EXECUTION_ORIGIN_TOOLS = [runs.SCRIPT_TOOL, *runs.DIRECT_TOOLS]
FEATURES = {"native_skill_events": False, "question_option_labels": False,
            "stateful_execution": True}
SIDE_INPUTS = {}


def header(place, handle, *, size, envelope, result):
    """Keep the historical fifty-line Codex project-selection window."""
    from .header import _lines, _scan
    _scan(_lines(handle, size), place, envelope, result)


def path_facts(place):
    from . import discover
    return discover.path_facts(place)


def side_inputs(_facts):
    return None


def bind(_state, _facts):
    """Codex derives identity from the selected transcript, without side inputs."""


def refusal(_place):
    return None


PATCH_PATH = re.compile(r"\*\*\* (?:(?:Update|Add|Delete) File|Move to): (.+?)(?=\\n|\n|[\"'`]|$)")

PROVENANCE = {
    "native_kind": ["type", "payload.type"], "eligible": ["payload.id"],
    "flush_response": ["type"],
    "execution": ["type"], "notifications": ["type"],
    "fork_boundary": ["type"], "turn_end": ["type"],
    "at_ms": ["timestamp", "payload.timestamp"],
    "rate_limits": ["type", "payload.type", "timestamp", "payload.timestamp", *RATE_LIMIT_PATHS],
    "identity.session": ["payload.id"], "identity.index_session": ["payload.id"],
    "identity.agent": ["payload.id", "payload.thread_source"],
    "identity.parent": ["payload.parent_thread_id", "payload.source.subagent.thread_spawn.parent_thread_id"],
    "identity.subagent": ["payload.thread_source", "payload.parent_thread_id", "payload.source.subagent.thread_spawn.parent_thread_id"],
    "identity.cwd": ["payload.cwd"], "identity.entrypoint": ["payload.originator"],
    "identity.version": ["payload.cli_version"],
    "context.model": ["payload.model"],
    "context.effort": ["payload.effort", "payload.collaboration_mode.settings.reasoning_effort"],
    "context.cwd": ["payload.cwd"], "context.context_window": ["payload.info.model_context_window"],
    "response.phase": ["type", "payload.type"],
    "response.id": ["payload.response_id", "payload.info.total_token_usage"],
    "response.model": ["payload.model"], "response.effort": ["payload.effort", "payload.collaboration_mode.settings.reasoning_effort"],
    "response.native": ["payload.usage", "payload.info.last_token_usage"],
    "message.channel": ["payload.role"], "message.origin": ["payload.content"],
    "message.text": ["payload.content[].text"], "message.blocks": ["payload.content[].text"],
    "message.joined_bytes": ["payload.content[].text"], "message.joined_nonempty": ["payload.content[].text"],
    "message.assistant_output_bytes": ["payload.content[].text"],
    "calls[].block": ["payload.type"], "calls[].id": ["payload.call_id"],
    "calls[].native_name": ["payload.name"], "calls[].kind": ["payload.name"],
    "calls[].input_bytes": ["payload.arguments", "payload.input"],
    "calls[].input_text": ["payload.arguments", "payload.input"],
    "calls[].command": ["payload.arguments", "payload.input"],
    "calls[].commands": ["payload.arguments", "payload.input", "payload.cwd"],
    "calls[].prompt": ["payload.arguments.message", "payload.input.message"],
    "calls[].patch_paths": ["payload.arguments", "payload.input"],
    "calls[].paths": ["payload.arguments", "payload.input", "payload.cwd"],
    "calls[].paths_complete": ["payload.arguments", "payload.input", "payload.cwd"],
    "injections": ["payload.base_instructions.text", "payload.content", "payload.replacement_history"],
    "compaction": ["payload.replacement_history"], "interruption": ["payload.type"],
    "identity.own": ["payload.id"],
    "turn.id": ["payload.turn_id"], "turn.start": ["type", "payload.type"],
    "occupancy.input_tokens": ["payload.info.last_token_usage.input_tokens"],
    "occupancy.context_window": ["payload.info.model_context_window"],
    "compaction.id": ["payload.compaction_response_id"],
    "compaction.trigger": [], "compaction.reason": [],
    "compaction.usage_record": ["payload.latest_token_usage_record.turn_id",
                                "payload.latest_token_usage_record.response_id",
                                "payload.latest_token_usage_record.usage.input_tokens",
                                "payload.resume_metadata.previous_turn_settings.model"],
}
COVERAGE_KEYS = {
    "identity.session": ["session_meta/input:session"],
    "identity.index_session": ["session_meta/input:session"],
    "identity.version": ["session_meta/input:version"],
    "identity.entrypoint": ["session_meta/input:entrypoint"],
    "identity.cwd": ["session_meta/payload.cwd"],
    "message.channel": ["response_item:message/payload.role"],
    "response.native": [f"applied:usage/input:{name}" for name in COUNTERS],
    "identity.parent": ["applied:spawn/input:parent_thread_id"],
    "context.model": ["turn_context/input:model"],
    "context.effort": ["turn_context/input:effort"],
    "context.context_window": ["event_msg:token_count/input:context_window"],
    "response.id": ["token_usage_record/input:response", "event_msg:token_count/payload.info.total_token_usage"],
    "response.model": ["turn_context/input:model"], "response.effort": ["turn_context/input:effort"],
    "message.text": ["applied:text_block/input:text"], "message.blocks": ["applied:text_block/input:text"],
    "message.joined_bytes": ["response_item:message/input:content"],
    "message.joined_nonempty": ["response_item:message/input:content"],
    "message.assistant_output_bytes": ["applied:text_block/input:text"],
    "calls[].id": ["applied:tool_call/input:call_id"],
    "calls[].native_name": ["applied:tool_call/input:name"],
    "calls[].input_bytes": ["applied:tool_call/input:value"],
    "calls[].input_text": ["applied:tool_call/input:value"],
    "calls[].commands": ["applied:tool_call/input:value", "applied:shell_arguments/input:workdir"],
    "injections": ["applied:base_instructions/input:text", "applied:text_block/input:text", "compacted/input:history"],
    "compaction": ["compacted/input:history"],
    "identity.own": ["session_meta/input:session"],
    "occupancy.input_tokens": ["event_msg:token_count/payload.info.last_token_usage.input_tokens"],
    "occupancy.context_window": ["event_msg:token_count/input:context_window"],
    "calls[].kind": ["applied:tool_call/input:name"],
    "calls[].prompt": ["applied:tool_call/input:value"],
    **{field: ["applied:tool_call/input:value"] for field in
       ("calls[].command", "calls[].patch_paths", "calls[].paths", "calls[].paths_complete")},
}
for _field in (*USAGE, "input_uncached", "uncached_total"):
    _names = ("input_tokens", "cached_input_tokens") if _field in {"input_uncached", "uncached_total"} else (USAGE[_field],)
    _paths = [f"payload.{container}.{name}" for container in ("usage", "info.last_token_usage") for name in _names]
    for _prefix in ("response.usage.", "response.usage_present."):
        PROVENANCE[_prefix + _field] = _paths
        COVERAGE_KEYS[_prefix + _field] = [f"applied:usage/input:{name}" for name in _names]

CONVENTIONS = frozenset({"flush_response", "execution", "notifications", "fork_boundary", "turn_end", "response.phase", "response.id", "message.origin", "identity.subagent", "identity.own",
                          "calls[].kind", "calls[].paths", "calls[].paths_complete", "calls[].commands"})



EXEC_PATHS = ["timestamp", "payload.timestamp", "payload.call_id", "payload.name", "payload.arguments", "payload.input",
              "payload.output", "payload.item", "payload.exit_code", "payload.duration",
              "payload.success", "payload.result", "payload.started_at_ms", "payload.completed_at_ms"]
EXEC_COVERAGE = ["applied:tool_call/input:call_id", "applied:tool_output/input:output",
                "applied:exec_end/input:exit_code", "applied:command_item/input:id",
                "applied:patch_end/input:success", "applied:mcp_end/input:result"]
for _group in ("runs", "commands", "call_updates", "writes", "operations", "diagnostics"):
    PROVENANCE["execution." + _group] = EXEC_PATHS
    COVERAGE_KEYS["execution." + _group] = EXEC_COVERAGE
for _field in ("operations", "skills"):
    PROVENANCE["calls[]." + _field] = ["payload.name", "payload.arguments", "payload.input"]
    COVERAGE_KEYS["calls[]." + _field] = ["applied:tool_call/input:name", "applied:tool_call/input:value"]
    CONVENTIONS |= {"calls[]." + _field}
for _field in ("call_id", "bytes", "error", "interrupted", "native_duration_ms", "background_id",
               "agent", "child_session", "answers", "truncation", "empty", "diagnostic", "harness_text"):
    PROVENANCE["results[]." + _field] = ["payload.call_id", "payload.output"]
    COVERAGE_KEYS["results[]." + _field] = ["applied:tool_output/input:call_id", "applied:tool_output/input:output"]
    CONVENTIONS |= {"results[]." + _field}
# Coverage dependencies retain the original extraction sites, independently of
# association evidence (a result's call id is not an input to its byte count).
COVERAGE_KEYS.update({
    "calls[].skills": ["applied:tool_call/input:value"],
    "results[].call_id": ["applied:tool_output/input:call_id"],
    "results[].error": ["applied:tool_output/input:output"],
    "execution.call_updates[].error": ["applied:command_item/input:exit_code"],
    **{f"results[].{name}": ["applied:tool_output/input:output"] for name in
       ("bytes", "interrupted", "truncation", "empty", "diagnostic", "harness_text")},
})
# A function output records no exit code of its own (spec §5.2 null-for-absent); command
# exits stay on the associated execution facts.
PROVENANCE["results[].exit_code"] = []
PROVENANCE["execution.call_updates[].error"] = ["payload.item.exit_code", "payload.exit_code",
                                                "payload.success", "payload.result", "payload.output"]
CONVENTIONS |= {"execution.call_updates[].error"}
PROVENANCE.update({
    "execution.commands[].command": ["payload.item.command"],
    "execution.commands[].diagnostic": ["payload.item.aggregated_output", "payload.output"],
    "execution.call_updates[].diagnostic": ["payload.result.Err", "payload.result.Ok.content[].text"],
})
COVERAGE_KEYS.update({
    "execution.commands[].command": ["applied:command_item/input:command"],
    "execution.commands[].diagnostic": ["applied:command_item/input:output", "applied:tool_output/input:output"],
    "execution.call_updates[].diagnostic": ["applied:mcp_end/input:result"],
})
CONVENTIONS |= {"execution.commands[].command", "execution.commands[].diagnostic",
                "execution.call_updates[].diagnostic"}

METADATA_PROVENANCE = {
    "metadata.identity.thread_id": ["payload.id"],
    "metadata.identity.ancestors": ["payload.forked_from_id", "payload.parent_thread_id",
        "payload.source.subagent.thread_spawn.parent_thread_id"],
    "metadata.identity.conflicts": ["payload.id", "payload.forked_from_id", "payload.parent_thread_id",
        "payload.source.subagent.thread_spawn.parent_thread_id"],
    "metadata.usage_source": ["type", "payload.type", "payload.info.total_token_usage"],
    **{"metadata.run_diagnostics." + name: EXEC_PATHS for name in runs.COUNTERS},
    **{"metadata.command_diagnostics." + name: EXEC_PATHS for name in outcomes.COUNTERS},
}
PROVENANCE.update(METADATA_PROVENANCE)
for _field in METADATA_PROVENANCE:
    COVERAGE_KEYS[_field] = EXEC_COVERAGE if "diagnostics" in _field else ["session_meta/input:session"] if "identity" in _field else ["token_usage_record/input:response", "event_msg:token_count/payload.info.total_token_usage"]


def metadata(state):
    """Declared cumulative facts; absence retains the original uninitialized maps."""
    return copy.deepcopy({key: state.get(key) for key in
                          ("identity", "usage_source", "run_diagnostics", "command_diagnostics")})


def provenance_defaults():
    """Sparse default proofs; per-event exceptions carry only changed attributes."""
    defaults = {field: {"native_paths": list(paths), "coverage_keys": list(COVERAGE_KEYS.get(field, [])),
                    "basis": "convention" if field in CONVENTIONS else "native",
                    "rule": "codex_" + field.replace("[]", "").replace(".", "_")}
            for field, paths in PROVENANCE.items()}
    defaults["context.context_window"]["source"] = "context_window_snapshot"
    defaults["results[].exit_code"]["rule"] = "absent:not_decoded"
    for field in ("compaction.trigger", "compaction.reason"):
        defaults[field]["rule"] = "absent:not_recorded"
    for field in ("calls[].skills", "execution.runs", "execution.commands", "execution.call_updates", "execution.writes", "execution.operations"):
        defaults[field]["basis"] = "heuristic"
    for field in METADATA_PROVENANCE:
        defaults[field]["basis"] = "convention"
        defaults[field]["rule"] = "codex_cumulative_" + field.removeprefix("metadata.").replace(".", "_")
    return defaults


def _parent(payload):
    source = payload.get("source")
    subagent = source.get("subagent") if isinstance(source, dict) else None
    spawn = (subagent.get("thread_spawn") or {}) if isinstance(subagent, dict) else {}
    return spawn.get("parent_thread_id") or payload.get("parent_thread_id")


def _identity(state, payload):
    """Record the file's own thread (its first session_meta id), the parents its records
    declare, and any later id outside that ancestry. A fork or
    subagent rollout inherits its parent's session_meta as history; that is ancestry, not
    a conflict."""
    thread = payload.get("id")
    if not thread:
        return
    identity = state.setdefault("identity", {"thread_id": None, "ancestors": [], "conflicts": []})
    if identity["thread_id"] is None:
        identity["thread_id"] = thread
    elif thread != identity["thread_id"] and thread not in identity["ancestors"]:
        if thread not in identity["conflicts"]:
            identity["conflicts"].append(thread)
        return
    for parent in (payload.get("forked_from_id"), _parent(payload)):
        if parent and parent not in identity["ancestors"]:
            identity["ancestors"].append(parent)


def _object(value, name):
    """A nested native object, read as the original reader reads it (absent when falsy)."""
    if value and not isinstance(value, dict):
        raise TypeError(f"Codex compacted {name} is not an object")
    return value or {}


def _compaction(payload):
    """The compaction's response id and the latest usage record it embeds, unrepaired.

    Matching the record to the compaction's turn and model is the consumer's rule."""
    event_id = payload.get("compaction_response_id")
    if event_id is not None and not isinstance(event_id, str):
        raise TypeError("Codex compacted compaction_response_id is not a string")
    usage, record = payload.get("latest_token_usage_record"), None
    if isinstance(usage, dict):
        settings = _object(_object(payload.get("resume_metadata"), "resume_metadata").get(
            "previous_turn_settings"), "previous_turn_settings")
        record = {"turn_id": usage.get("turn_id"), "response_id": usage.get("response_id"),
                  "input_tokens": _object(usage.get("usage"), "latest_token_usage_record usage").get("input_tokens"),
                  "model": settings.get("model")}
    return {"summary": True, "basis": "native", "rule": "codex_compacted", "id": event_id,
            "trigger": None, "reason": None, "usage_record": record}


def _usage(raw):
    inp, cached = raw.get("input_tokens", 0), raw.get("cached_input_tokens", 0)
    # Missing operands default exactly as the oracle; present null still fails.
    uncached = inp - cached
    selected = "input_tokens" in raw or "cached_input_tokens" in raw
    usage = {field: raw.get(name) for field, name in USAGE.items()}
    usage.update(input_uncached=uncached if selected else None, uncached_total=uncached if selected else None)
    present = {field: name in raw for field, name in USAGE.items()}
    present.update(input_uncached=selected, uncached_total=selected)
    return usage, present


def _message(payload):
    blocks = [{"block": i, "text": block.get("text", ""), "bytes": _size(block.get("text", ""))}
              for i, block in enumerate(payload.get("content") or [])
              if isinstance(block, dict) and block.get("type") in ("input_text", "output_text")]
    joined = "\n".join(block["text"] for block in blocks)
    channel = payload.get("role")
    return {"channel": channel, "origin": labels.origin(payload.get("content"), "codex"),
            "text": joined, "joined_nonempty": bool(joined.strip()), "joined_bytes": _size(joined),
            "assistant_output_bytes": sum(b["bytes"] for b in blocks) if channel == "assistant" else 0,
            "blocks": blocks}


def _call(payload, cwd):
    name = payload.get("name", "")
    value = payload.get("arguments" if payload.get("type") == "function_call" else "input", "")
    text, command, commands = str(value), None, []
    arguments, normalization = None, None
    if name in SHELL:
        try:
            arguments = json.loads(text)
        except ValueError:
            pass
        if isinstance(arguments, dict):
            command = arguments.get("cmd", arguments.get("command"))
            command = " ".join(command) if isinstance(command, list) else command
            if type(command) is dict and not command:
                # The original adapter treats an empty object exactly like empty text.
                command, normalization = "", "codex_empty_command_object"
            elif command is not None and not isinstance(command, str):
                raise TypeError("Codex direct command must be a string or null")
        elif name == "shell" and not text.lstrip().startswith("{"):
            command = text
        directory = cwd
        if isinstance(arguments, dict) and "workdir" in arguments:
            workdir = arguments["workdir"]
            directory = (workdir if posixpath.isabs(workdir) else posixpath.join(cwd, workdir) if cwd else None) \
                if isinstance(workdir, str) and workdir else None
        commands = [{"command": command, "cwd": directory}]
    if name not in SHELL:
        commands = [{"command": cmd, "cwd": here} for cmd, here in zip(
            tools.codex_commands(name, value), tools.codex_directories(name, value, cwd), strict=True)]
    patch = name == "apply_patch" or name == "exec" and "tools.apply_patch(" in text
    raw_paths = ([m.group(1).strip() for m in PATCH_PATH.finditer(text)] or [None]) if patch else []
    candidate_text = value if isinstance(value, str) else json.dumps(value)
    candidate_paths = ([m.group(1).strip() for m in PATCH_PATH.finditer(candidate_text)] or [None]) if patch else []
    candidates = [_join(path, cwd) if path is not None else None for path in candidate_paths]
    call = {"id": payload.get("call_id"), "native_name": name,
            "kind": "shell" if name in SHELL else "script" if name == "exec" else "patch" if patch else "question" if name == "request_user_input" else "poll" if name in {"write_stdin", "wait"} else "dispatch" if name in DISPATCH else "other",
            "input_bytes": _size(value), "input_text": text, "command": command,
            "commands": commands, "operations": runs.operations(text) if name == "exec" else None,
            "skills": skills.from_call(name, value), "patch_paths": raw_paths,
            "paths": sorted(set(p for p in candidates if p is not None)),
            "paths_complete": all(p is not None for p in candidates), "block": 0}
    if name in DISPATCH:
        decoded = value
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except ValueError:
                decoded = None
        message = decoded.get("message") if isinstance(decoded, dict) else None
        call["prompt"] = message if isinstance(message, str) and message else None
        call["paths_complete"] = call["prompt"] is not None
    return call, arguments, normalization


def _meter_number(value, field):
    if value is None:
        return None
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f"{field} must be a finite number") from None
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def codex_rate_limits(record: object) -> dict | None:
    """Read the native Codex credit balance and weekly limit, independently of usage."""
    if not isinstance(record, dict) or record.get("type") != "event_msg":
        return None
    payload = record.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    limits = payload.get("rate_limits")
    if limits is None:
        return None

    provenance = {"basis": "native", "rule": "codex_rate_limits"}
    try:
        if not isinstance(limits, dict):
            raise ValueError("rate_limits must be an object")
        credits = limits.get("credits")
        if credits is not None and not isinstance(credits, dict):
            raise ValueError("credits must be an object or null")
        timestamp = record.get("timestamp") or payload.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError("rate_limits requires an ISO timestamp")
        at_ms = _at_ms(timestamp)
        balance = _meter_number(credits.get("balance") if credits is not None else None, "balance")
        weekly = None
        for name in ("primary", "secondary"):
            window = limits.get(name)
            if isinstance(window, dict) and window.get("window_minutes") == 10080:
                weekly = _meter_number(window.get("used_percent"), "used_percent")
                break
    except (ValueError, OverflowError, OSError) as error:
        return {"status": "malformed", "reason": str(error), **provenance}
    return {"status": "ok", "at_ms": at_ms, "balance": balance,
            "weekly_used_percent": weekly, **provenance}


def extract(lines, state, *, place: Place, text: bool):
    """Yield independent physical facts and cumulative native coverage."""
    state.setdefault("usage_source", "none")
    number, partial = state.get("next_line", 1), False
    for offset, raw in lines:
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        position = {"key": f"E{offset}", "line": number, "offset": offset, "end": offset + len(raw),
                    "ref": ref(place, number), "sha256": hashlib.sha256(raw).hexdigest()}
        if not raw.endswith(b"\n"):
            partial = True
            yield {"object": "unparsed", **position, "reason": "truncated", "provisional": True}
            break
        state["next_line"], state["next_offset"] = number + 1, offset + len(raw)
        number += 1
        line = raw.decode("utf-8", errors="replace")
        try:
            record = json.loads(line, parse_float=_finite_float, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            state["malformed"] = state.get("malformed", 0) + 1
            unparsed = {"object": "unparsed", **position, "reason": "malformed", "provisional": False}
            # Live spend read meter facts with ordinary JSON numeric parsing.
            try:
                meter_record = json.loads(line)
            except (ValueError, RecursionError):
                meter_record = None
            meter = codex_rate_limits(meter_record)
            if meter is not None:
                unparsed["rate_limits"] = meter
            yield unparsed
            continue
        payload, kind = record.get("payload") or {}, record.get("type")
        if kind == "token_usage_record":
            if state["usage_source"] == "count":
                raise Restart("token_usage_record after token_count", {"usage_source": "record"})
            state["usage_source"] = "record"
        if kind == "session_meta":
            session = payload.get("id") or state.get("session_id")
            if session is not None:
                state["session_id"] = session
                identities = state.setdefault("sessions", {})
                identity = identities.setdefault(session, {"session": session, "index_session": session,
                    "agent": None, "parent": None, "subagent": False, "cwd": None,
                    "entrypoint": None, "version": None})
                identity["cwd"] = identity["cwd"] or payload.get("cwd")
                identity["entrypoint"] = identity["entrypoint"] or payload.get("originator")
                identity["version"] = identity["version"] or payload.get("cli_version")
                identity["parent"] = identity["parent"] or _parent(payload)
                identity["subagent"] = identity["subagent"] or payload.get("thread_source") not in (None, "user") or bool(_parent(payload))
        session = state.get("session_id")
        identity = dict(state.get("sessions", {}).get(session) or dict.fromkeys(
            ("session", "index_session", "agent", "parent", "subagent", "cwd", "entrypoint", "version")))
        timestamp = record.get("timestamp") or payload.get("timestamp")
        at_ms = _at_ms(timestamp) if timestamp else None
        day, native_kind = day_of(at_ms), record_kind(record)
        count_record(state, session, day, native_kind, native_kind in KNOWN_KINDS, record, WATCHED)
        event = {"object": "index_event", **position, "native_kind": native_kind,
                 "identity": identity, "at_ms": at_ms, "eligible": session is not None,
                 "rate_limits": codex_rate_limits(record),
                 "response": None, "flush_response": False, "message": None, "context": None,
                 "calls": [], "results": [], "injections": [], "notifications": [],
                 "compaction": None, "interruption": None, "fork_boundary": None, "turn_end": None,
                 "turn": None, "occupancy": None,
                 "execution": {"runs": [], "commands": [], "call_updates": [], "writes": [],
                               "operations": [], "diagnostics": {}}, "provenance": {}}
        if kind == "session_meta":
            _identity(state, payload)
            base = (payload.get("base_instructions") or {}).get("text")
            if base is not None:
                if session is None:
                    raise TypeError("session_meta instructions require a session")
                event["injections"] = [{"piece": 0, "native_kind": "base_instructions", "source": "session_meta", "bytes": _size(base)}]
            base_object = payload.get("base_instructions")
            if isinstance(base_object, dict):
                applied(state, session, day, "base_instructions", {"text": base_object.get("text") is not None})
            source = payload.get("source")
            if isinstance(source, dict) and "subagent" in source:
                applied(state, session, day, "spawn", {"parent_thread_id": _parent(payload) is not None})
        # After this record's identity: the file's first session_meta is its own thread.
        event["identity"]["own"] = session is not None and session == state.get("identity", {}).get("thread_id")
        if session is not None:
            if native_kind in ("event_msg:task_started", "event_msg:turn_started"):
                event["turn"] = {"id": payload.get("turn_id"), "start": True}
            if kind == "turn_context":
                event["turn"] = {"id": payload.get("turn_id"), "start": False}
                settings = (payload.get("collaboration_mode") or {}).get("settings") or {}
                state.update(model=payload.get("model"), effort=payload.get("effort") or settings.get("reasoning_effort"), turn_cwd=payload.get("cwd"))
                event["context"] = {"model": state["model"], "effort": state["effort"], "cwd": state["turn_cwd"], "context_window": state.get("context_window")}
            selected = None
            if kind == "token_usage_record":
                selected = (payload.get("response_id"), payload.get("usage") or {})
                event["provenance"]["response.id"] = {"basis": "native"}
            elif native_kind == "event_msg:token_count":
                info = payload.get("info")
                if info is not None:
                    window = info.get("model_context_window")
                    last = info.get("last_token_usage") or {}
                    if not isinstance(last, dict):
                        raise TypeError("Codex token_count last_token_usage is not an object")
                    event["occupancy"] = {"input_tokens": last.get("input_tokens"), "context_window": window}
                    if window is not None:
                        state["context_window"] = window
                        event["context"] = {"model": state.get("model"), "effort": state.get("effort"), "cwd": state.get("turn_cwd"), "context_window": window}
                        event["provenance"]["context.context_window"] = {
                            "source": "context_window_observation", "rule": "codex_recorded_context_window"}
                    total = info.get("total_token_usage")
                    if state["usage_source"] != "record" and total != state.get("last_total"):
                        state.update(usage_source="count", last_total=total)
                        selected = (f"tc:{session}:{offset}", info.get("last_token_usage") or {})
            if selected is not None:
                response_id, usage = selected
                event["context"] = {"model": state.get("model"), "effort": state.get("effort"),
                    "cwd": state.get("turn_cwd"), "context_window":
                    window if native_kind == "event_msg:token_count" else state.get("context_window")}
                normalized, present = _usage(usage)
                applied(state, session, day, "usage", {name: usage.get(name) is not None for name in COUNTERS})
                event["response"] = {"id": response_id, "phase": "terminal", "model": state.get("model"), "effort": state.get("effort"),
                                     "native": usage, "usage": normalized, "usage_present": present}
                tools.on_usage(state, response_id)
            if native_kind == "response_item:message":
                event["message"] = _message(payload)
                if payload.get("role") == "user":
                    joined = event["message"]["text"]
                    prefix = next((prefix for prefix in INJECTED if joined.strip().startswith(prefix)), None)
                    if prefix is not None:
                        event["injections"] = [{"piece": 0, "native_kind": "user_injection:" + prefix,
                                                "source": prefix, "bytes": _size(joined)}]
                for block in payload.get("content") or []:
                    if isinstance(block, dict) and block.get("type") in ("input_text", "output_text"):
                        applied(state, session, day, "text_block", {"text": block.get("text") is not None})
            elif native_kind in ("response_item:function_call", "response_item:custom_tool_call"):
                call, arguments, normalization = _call(payload, state.get("turn_cwd"))
                event["calls"].append(call)
                field = "arguments" if payload.get("type") == "function_call" else "input"
                tools.on_call(state, event, call, payload.get(field, ""))
                if normalization is not None:
                    event["provenance"]["calls[].command"] = {"basis": "convention", "rule": normalization}
                    event["provenance"]["calls[].commands"] = {"rule": normalization}
                field = "arguments" if payload.get("type") == "function_call" else "input"
                applied(state, session, day, "tool_call", {"call_id": payload.get("call_id") is not None, "name": payload.get("name") is not None, "value": payload.get(field) is not None})
                if isinstance(arguments, dict):
                    applied(state, session, day, "shell_arguments", {"workdir": isinstance(arguments.get("workdir"), str)})
            elif native_kind in ("response_item:function_call_output", "response_item:custom_tool_call_output"):
                tools.on_output(state, event, payload, day)
            elif kind == "compacted":
                event["compaction"] = _compaction(payload)
                event["injections"] = [{"piece": 0, "native_kind": "compact_summary", "source": None,
                                        "bytes": _size(payload.get("replacement_history") or [])}]
            elif native_kind == "event_msg:turn_aborted":
                event["interruption"] = {"user_marker": False, "system": True, "basis": "native", "rule": "codex_turn_aborted"}
            if kind == "event_msg":
                tools.on_event(state, event, payload, day)
        event["execution"]["diagnostics"] = {**state.get("run_diagnostics", {}), **state.get("command_diagnostics", {})}
        if not text:
            if event["message"]:
                event["message"].pop("text")
                for block in event["message"]["blocks"]:
                    block.pop("text")
            for call in event["calls"]:
                for key in ("input_text", "command", "commands", "operations", "patch_paths", "paths", "prompt"):
                    call.pop(key, None)
            for fact in (*event["results"], *event["execution"]["commands"],
                         *event["execution"]["call_updates"]):
                for key in ("command", "diagnostic"):
                    fact.pop(key, None)
            for injection in event["injections"]:
                injection.pop("source")
        yield event
    counts, fields = coverage_rows(state)
    yield {"object": "coverage", "key": "coverage", "records": counts, "fields": fields,
           "malformed": state.get("malformed", 0), "partial_tail": partial}
