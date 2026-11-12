"""Native Claude index evidence; measurement rules belong to the consumer.

Coverage declarations and population arithmetic preserve obs0a09481c's native
extraction sites, including historical EOF response-flush contributions.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import posixpath
import re

from . import discover, labels
from .lines import Place, ref, _finite_float, _reject_constant

HANDLED_KINDS = frozenset({"assistant", "user", "attachment", "system"})

IGNORED_KINDS = frozenset(
    {
        "atis-latch",
        "last-prompt",
        "ai-title",
        "mode",
        "permission-mode",
        "queue-operation",
        "cost-state",
        "file-history-snapshot",
        "file-history-delta",
        "bridge-session",
        "custom-title",
        "agent-name",
        "summary",
        "relocated",
        "worktree-state",
        "agent-color",
        "pr-link",
        "continued-in",
        "fork-context-ref",
    }
)

KNOWN_KINDS = HANDLED_KINDS | IGNORED_KINDS

COMMON_READS = (
    "type",
    "timestamp",
    "sessionId",
    "isSidechain",
    "agentId",
    "cwd",
    "entrypoint",
    "version",
    "message",
)

USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")

ATTACHMENT_BODY = {"prompt_snapshot": "systemPrompt", "instructions": "files"}

STOP_EVENTS = frozenset({"Stop", "SubagentStop"})

WATCHED = {
    "assistant": {
        "sources": (
            "requestId",
            "message.id",
            "message.model",
            "message.content",
            "effort",
            "version",
            *(f"message.usage.{name}" for name in USAGE),
        ),
        "inputs": {
            "response": ("requestId", "message.id"),
            "model": ("message.model",),
            "content": ("message.content",),
            "effort": ("effort",),
            "version": ("version",),
        },
        "feeds": {
            "message.content": ("applied:text_block/input:text", "applied:tool_use/input:name"),
            **{f"message.usage.{name}": (f"applied:usage/input:{name}",) for name in USAGE},
        },
    },
    "user": {
        "sources": ("message.content",),
        "inputs": {"content": ("message.content",)},
        "feeds": {
            "message.content": (
                "applied:tool_result/input:content",
                "applied:text_block/input:text",
            )
        },
    },
    "attachment": {
        "sources": ("attachment", "attachment.type"),
        "inputs": {"attachment": ("attachment",)},
    },
    "system": {"sources": ("subtype",), "inputs": {"subtype": ("subtype",)}},
}

APPLIED = {
    "usage": (*USAGE, "thinking_tokens"),  # the usage a flushed response became
    "text_block": ("text",),  # each assistant text block
    "tool_use": ("id", "name", "input"),  # each assistant tool_use block
    "bash": ("command",),  # Bash tool_use inputs
    "skill": ("skill",),  # Skill tool_use inputs
    "ask": ("questions",),  # AskUserQuestion tool_use inputs
    "question": ("question", "options", "labels"),  # each asked question
    "tool_result": ("tool_use_id", "content"),  # each user tool_result block
    "tool_result_meta": ("duration",),  # tool results carrying a toolUseResult object
    "truncation": ("persisted_size",),  # results opening with a persisted-output notice
    "answers": ("answers",),  # results answering a pending question
    "attachment": ("body",),  # each attachment's type-specific body
    "stop_block": ("turn", "command", "reason"),  # Stop hook_blocking_error attachments
    "turn_end": ("id", "turn", "hooks", "errors"),  # each stop_hook_summary record
    "hook_run": ("command", "duration"),  # each hook a turn end ran
}

UNWATCHED = {
    "assistant": {
        "message.content[].type": "applied:text_block",
        "message.content[].text": "applied:text_block",
        "message.content[].id": "applied:tool_use",
        "message.content[].name": "applied:tool_use",
        "message.content[].input": "applied:tool_use",
        "message.content[].input.command": "applied:bash",
        "message.content[].input.file_path": "dimension",
        "message.content[].input.notebook_path": "dimension",
        "message.content[].input.run_in_background": "flag",
        "message.content[].input.skill": "applied:skill",
        "message.content[].input.prompt": "dimension",
        "message.content[].input.questions": "applied:ask",
        "message.content[].input.questions[].question": "applied:question",
        "message.content[].input.questions[].options": "applied:question",
        "message.content[].input.questions[].options[].label": "applied:question",
        "message.usage.output_tokens_details.thinking_tokens": "applied:usage",
    },
    "user": {
        "isCompactSummary": "flag",
        "isMeta": "flag",
        "message.content[].type": "applied:text_block",
        "message.content[].text": "applied:text_block",
        "message.content[].tool_use_id": "applied:tool_result",
        "message.content[].content": "applied:tool_result",
        "message.content[].is_error": "flag",
        "toolUseResult": "applied:tool_result_meta",
        "toolUseResult.durationMs": "applied:tool_result_meta",
        "toolUseResult.interrupted": "flag",
        "toolUseResult.persistedOutputSize": "applied:truncation",
        "toolUseResult.backgroundTaskId": "flag",
        "toolUseResult.agentId": "dimension",
        "toolUseResult.answers": "applied:answers",
    },
    "attachment": {
        "attachment.content": "applied:attachment",
        "attachment.systemPrompt": "applied:attachment",
        "attachment.files": "applied:attachment",
        "attachment.files[].path": "dimension",
        "attachment.files[].content": "applied:attachment",
        "attachment.command": "dimension",
        "attachment.hookEvent": "dimension",
        "attachment.toolUseID": "applied:stop_block",
        "attachment.blockingError": "applied:stop_block",
        "attachment.blockingError.command": ("dimension", "applied:stop_block"),
        "attachment.blockingError.blockingError": "applied:stop_block",
    },
    "system": {
        "uuid": "applied:turn_end",
        "toolUseID": "applied:turn_end",
        "hookInfos": "applied:turn_end",
        "hookInfos[].command": "applied:hook_run",
        "hookInfos[].durationMs": "applied:hook_run",
        "hookErrors": "applied:turn_end",
    },
}


def get_path(record, path):
    """The value at a dotted path, or None when any step is missing or not a mapping."""
    value = record
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def day_of(at_ms):
    if at_ms is None:
        return None
    return datetime.fromtimestamp(at_ms / 1000, timezone.utc).date().isoformat()


def _bucket(state):
    return state.setdefault("coverage", {"records": {}, "fields": {}})


def count_record(state, session_id, day, kind, known, record, watched):
    """Count one record of `kind`; for a watched kind, count each source field and each
    input (present when any of its fallback fields is). Undated records are not counted."""
    if day is None:
        return
    bucket = _bucket(state)
    key = f"{session_id or ''}\t{day}\t{kind}"
    entry = bucket["records"].setdefault(key, [int(bool(known)), 0])
    entry[1] += 1
    spec = watched.get(kind)
    if spec is None:
        return
    for path in spec["sources"]:
        _field(bucket, key, path, get_path(record, path) is not None)
    for name, paths in spec["inputs"].items():
        _field(
            bucket, key, f"input:{name}", any(get_path(record, path) is not None for path in paths)
        )


def applied(state, session_id, day, site, inputs):
    """Count native presence at an extraction site: for each input, whether
    the record the parser actually drew the value from carried it. This is effective input
    coverage, over exactly the population the value comes from."""
    if day is None:
        return
    bucket = _bucket(state)
    key = f"{session_id or ''}\t{day}\tapplied:{site}"
    for name, present in inputs.items():
        _field(bucket, key, f"input:{name}", present)


def _field(bucket, key, field, present):
    entry = bucket["fields"].setdefault(f"{key}\t{field}", [0, 0])
    entry[0] += 1
    entry[1] += int(present)


def coverage_rows(state):
    """(record_counts rows, field_presence rows) accumulated in `state`, without file_id."""
    bucket = state.get("coverage") or {"records": {}, "fields": {}}
    records = []
    for key, (known, total) in sorted(bucket["records"].items()):
        session_id, day, kind = key.split("\t")
        records.append(
            {
                "session_id": session_id,
                "day": day,
                "record_kind": kind,
                "known": known,
                "records": total,
            }
        )
    fields = []
    for key, (seen, present) in sorted(bucket["fields"].items()):
        session_id, day, kind, field = key.split("\t")
        fields.append(
            {
                "session_id": session_id,
                "day": day,
                "record_kind": kind,
                "field": field,
                "seen": seen,
                "present": present,
            }
        )
    return records, fields


PATH_FIELDS = {
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
    "Glob": "path",
    "Grep": "path",
}
WRITERS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
DISPATCH = frozenset({"Agent", "Task"})
NOTIFICATION = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
NOTIFIED_ID = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>")
NOTIFIED_STATUS = re.compile(r"<status>([^<]+)</status>")
NOTIFIED_EXIT = re.compile(r"\(exit code (-?\d+)\)")
ELISION = re.compile(r"\n\n\.\.\. \[\d+ characters truncated\] \.\.\.\n\n")

# Native sources are declarations, not a consumer's metric catalogue.
PROVENANCE = {
    "native_kind": ["type"],
    "eligible": ["timestamp", "sessionId"],
    "flush_response": ["type", "requestId", "message.id"],
    "calls[].block": ["message.content"],
    "identity.session": ["sessionId"],
    "identity.index_session": ["sessionId", "agentId", "isSidechain"],
    "identity.agent": ["agentId"],
    "identity.parent": ["sessionId", "agentId", "isSidechain"],
    "identity.subagent": ["isSidechain", "agentId", "entrypoint"],
    "identity.cwd": ["cwd"],
    "identity.entrypoint": ["entrypoint"],
    "identity.version": ["version"],
    "at_ms": ["timestamp"],
    "response.id": ["requestId", "message.id"],
    "response.model": ["message.model"],
    "response.effort": ["effort"],
    "response.native": ["message.usage"],
    "response.usage.input_uncached": ["message.usage.input_tokens"],
    "response.usage.cache_read": ["message.usage.cache_read_input_tokens"],
    "response.usage.cache_write": ["message.usage.cache_creation_input_tokens"],
    "response.usage.output": ["message.usage.output_tokens"],
    "response.usage.thinking": ["message.usage.output_tokens_details.thinking_tokens"],
    "response.usage.context_total": [
        "message.usage.input_tokens",
        "message.usage.cache_creation_input_tokens",
        "message.usage.cache_read_input_tokens",
    ],
    "response.usage.uncached_total": [
        "message.usage.input_tokens",
        "message.usage.cache_creation_input_tokens",
    ],
    "message.channel": ["type"],
    "message.origin": ["message.content", "origin.kind", "isMeta", "isCompactSummary"],
    "message.text": ["message.content", "message.content[].text"],
    "message.blocks": ["message.content[].text"],
    "message.joined_bytes": ["message.content", "message.content[].text"],
    "message.joined_nonempty": ["message.content", "message.content[].text"],
    "message.assistant_output_bytes": ["message.content[].text", "message.content[].input"],
    "calls[].id": ["message.content[].id"],
    "calls[].native_name": ["message.content[].name"],
    "calls[].kind": ["message.content[].name"],
    "calls[].input_bytes": ["message.content[].input"],
    "calls[].command": ["message.content[].input.command"],
    "calls[].paths": [
        "message.content[].input.file_path",
        "message.content[].input.notebook_path",
        "message.content[].input.path",
        "cwd",
    ],
    "calls[].paths_complete": [
        "message.content[].input.file_path",
        "message.content[].input.notebook_path",
        "message.content[].input.path",
        "cwd",
    ],
    "calls[].raw_path": [
        "message.content[].input.file_path",
        "message.content[].input.notebook_path",
    ],
    "calls[].background": ["message.content[].input.run_in_background"],
    "calls[].skill": ["message.content[].input.skill"],
    "calls[].prompt": ["message.content[].input.prompt"],
    "calls[].questions": ["message.content[].input.questions"],
    "results[].call_id": ["message.content[].tool_use_id"],
    "results[].bytes": ["message.content[].content"],
    "results[].error": ["message.content[].is_error"],
    "results[].interrupted": ["toolUseResult.interrupted"],
    "results[].native_duration_ms": ["toolUseResult.durationMs"],
    "results[].background_id": ["toolUseResult.backgroundTaskId"],
    "results[].agent": ["toolUseResult.agentId"],
    "results[].child_session": ["toolUseResult.agentId"],
    "results[].answers": ["toolUseResult.answers"],
    "results[].truncation": ["message.content[].content", "toolUseResult.persistedOutputSize"],
    "injections": [
        "attachment",
        "attachment.type",
        "attachment.content",
        "attachment.files",
        "attachment.systemPrompt",
        "message.content",
    ],
    "notifications": [""],
    "compaction": ["isCompactSummary"],
    "interruption": ["message.content", "subtype"],
    "fork_boundary": ["type"],
    "turn_end": ["uuid", "toolUseID", "hookInfos", "hookErrors"],
}

COVERAGE_KEYS = {
    "response.id": ["assistant/input:response"],
    "response.model": ["assistant/input:model"],
    "response.effort": ["assistant/input:effort"],
    "identity.version": ["assistant/input:version"],
    "message.text": ["applied:text_block/input:text"],
    "message.blocks": ["applied:text_block/input:text"],
    "calls[].id": ["applied:tool_use/input:id"],
    "calls[].native_name": ["applied:tool_use/input:name"],
    "calls[].input_bytes": ["applied:tool_use/input:input"],
    "calls[].command": ["applied:bash/input:command"],
    "calls[].skill": ["applied:skill/input:skill"],
    "calls[].questions": [
        "applied:ask/input:questions",
        "applied:question/input:question",
        "applied:question/input:options",
        "applied:question/input:labels",
    ],
    "results[].call_id": ["applied:tool_result/input:tool_use_id"],
    "results[].bytes": ["applied:tool_result/input:content"],
    "results[].native_duration_ms": ["applied:tool_result_meta/input:duration"],
    "results[].answers": ["applied:answers/input:answers"],
    "results[].truncation": ["applied:truncation/input:persisted_size"],
    "injections": ["applied:attachment/input:body"],
    "turn_end": [
        "applied:turn_end/input:id",
        "applied:turn_end/input:turn",
        "applied:turn_end/input:hooks",
        "applied:turn_end/input:errors",
        "applied:hook_run/input:command",
        "applied:hook_run/input:duration",
        "applied:stop_block/input:turn",
        "applied:stop_block/input:command",
        "applied:stop_block/input:reason",
    ],
}
for _usage_field, _native in [
    ("input_uncached", "input_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
    ("output", "output_tokens"),
    ("thinking", "thinking_tokens"),
]:
    COVERAGE_KEYS["response.usage." + _usage_field] = ["applied:usage/input:" + _native]
for _usage_field, _components in [("context_total", USAGE[:3]), ("uncached_total", USAGE[:2])]:
    COVERAGE_KEYS["response.usage." + _usage_field] = [
        "applied:usage/input:" + name for name in _components
    ]


def _size(value):
    value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return len(value.encode("utf-8"))


def _at_ms(timestamp):
    return int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1000)


def _text_blocks(content):
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        ]
    return []


def _usage_total(values):
    """An unavailable wire total does not erase the original finite components."""
    if any(value is None for value in values):
        return None
    try:
        total = sum(values)
    except OverflowError:
        return None
    return None if isinstance(total, float) and not math.isfinite(total) else total


def _usage(raw):
    # Fragments may be replaced before the old flush site validates their values.
    mapping = raw if isinstance(raw, dict) else {}
    details = mapping.get("output_tokens_details")
    values = [mapping.get(name) for name in USAGE[:3]]
    values = [v if isinstance(v, (int, float)) else None for v in values]
    return {
        "input_uncached": values[0],
        "cache_write": values[1],
        "cache_read": values[2],
        "output": mapping.get("output_tokens"),
        "thinking": details.get("thinking_tokens") if isinstance(details, dict) else None,
        "context_total": _usage_total(values),
        "uncached_total": _usage_total(values[:2]),
    }


def _flush(state):
    request_id = state.pop("open_request", None)
    if request_id is None:
        return
    request = state["requests"][request_id]
    raw = request["usage"]
    applied(
        state,
        request["session"],
        day_of(request["at_ms"]),
        "usage",
        {
            **{name: raw.get(name) is not None for name in USAGE},
            "thinking_tokens": (raw.get("output_tokens_details") or {}).get("thinking_tokens")
            is not None,
        },
    )
    # The old adapter validates arithmetic only when the last fragment is flushed.
    inp, write, read = (raw.get(name, 0) for name in USAGE[:3])
    _ = inp + write + read


def _join(path, cwd):
    if path.startswith("~/"):
        below = posixpath.normpath(path[2:])
        return (
            None
            if below == ".." or below.startswith("../")
            else posixpath.join("~/", below).removesuffix("/.")
        )
    if path.startswith("~"):
        return None
    if posixpath.isabs(path):
        return posixpath.normpath(path)
    if isinstance(cwd, str) and posixpath.isabs(cwd):
        return posixpath.normpath(posixpath.join(cwd, path))
    return None


def _paths(name, value, cwd):
    key = PATH_FIELDS.get(name)
    if key is None:
        return [], True
    # Old candidate extraction accepts a serialized object; writer extraction does not.
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError:
        decoded = None
    found = decoded.get(key) if isinstance(decoded, dict) else None
    if not isinstance(found, str) or not found:
        return [], name in {"Glob", "Grep"} and isinstance(decoded, dict) and key not in decoded
    joined = _join(found, cwd)
    return ([joined], True) if joined is not None else ([], False)


def _call(block, number, cwd):
    value = block.get("input") or {}
    name = block.get("name", "")
    kind = (
        "shell"
        if name == "Bash"
        else "file_edit"
        if name in WRITERS
        else "file_read"
        if name in PATH_FIELDS
        else "dispatch"
        if name in DISPATCH
        else "question"
        if name == "AskUserQuestion"
        else "skill"
        if name == "Skill"
        else "other"
    )
    raw = value.get(PATH_FIELDS[name]) if name in WRITERS else None
    paths, complete = _paths(name, value, cwd)
    prompt = value.get("prompt") if kind == "dispatch" else None
    prompt = prompt if isinstance(prompt, str) and prompt else None
    skill = value.get("skill") if kind == "skill" else None
    skill = skill if isinstance(skill, str) and skill else None
    if kind == "dispatch":
        complete = prompt is not None
    # Bash, questions, skill and dispatch follow their old direct object reads.
    command = str(value.get("command", "")) if kind == "shell" else None
    return {
        "id": block.get("id"),
        "native_name": name,
        "kind": kind,
        "input_bytes": _size(value),
        "command": command,
        "paths": paths,
        "paths_complete": complete,
        "raw_path": raw if isinstance(raw, str) and raw else None,
        "background": bool(value.get("run_in_background")) if kind == "shell" else None,
        "skill": skill,
        "prompt": prompt,
        "questions": value.get("questions") or [] if kind == "question" else [],
        "block": number,
    }


def _truncation(content, result):
    texts = (
        [content]
        if isinstance(content, str)
        else [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and isinstance(b.get("text"), str)
        ]
        if isinstance(content, list)
        else []
    )
    if texts and texts[0].lstrip().startswith("<persisted-output>"):
        size = result.get("persistedOutputSize")
        return {
            "kind": "persisted",
            "original_tokens": None,
            "original_bytes": size if type(size) is int else None,
        }
    return {
        "kind": "dropped" if any(ELISION.search(t) for t in texts) else "none",
        "original_tokens": None,
        "original_bytes": None,
    }


def _command_key(command):
    """Stable matching evidence without persisting command text; keep JSON equality."""

    def comparable(value):
        if isinstance(value, bool) or isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [comparable(item) for item in value]
        if isinstance(value, dict):
            return {key: comparable(item) for key, item in value.items()}
        return value

    encoded = json.dumps(
        comparable(command), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _attachment(record, state, session, day):
    attachment = record.get("attachment") or {}
    kind = attachment.get("type", "attachment")
    body = ATTACHMENT_BODY.get(kind, "content")
    applied(state, session, day, "attachment", {"body": attachment.get(body) is not None})
    if kind == "hook_blocking_error" and attachment.get("hookEvent") in STOP_EVENTS:
        blocking = attachment.get("blockingError") or {}
        turn, command, reason = (
            attachment.get("toolUseID"),
            blocking.get("command"),
            blocking.get("blockingError"),
        )
        applied(
            state,
            session,
            day,
            "stop_block",
            {
                "turn": turn is not None,
                "command": command is not None,
                "reason": reason is not None,
            },
        )
        state.setdefault("stop_blocks", {}).setdefault(turn, []).append(
            [_command_key(command), _size(reason or "")]
        )
    if kind == "prompt_snapshot":
        pieces = [
            (i, f"section:{i}", section)
            for i, section in enumerate(attachment.get("systemPrompt") or [])
        ]
    elif kind == "instructions":
        pieces = [
            (i, item.get("path"), item.get("content", ""))
            for i, item in enumerate(attachment.get("files") or [])
        ]
    else:
        source = (
            (attachment.get("blockingError") or {}).get("command")
            if kind == "hook_blocking_error"
            else attachment.get("command")
            if kind in {"hook_success", "hook_non_blocking_error"}
            else None
        )
        pieces = [(0, source, attachment.get("content") if "content" in attachment else attachment)]
    return [
        {"piece": i, "native_kind": kind, "source": source, "bytes": _size(value)}
        for i, source, value in pieces
    ]


def _turn_end(record, state, session, day):
    id_, turn = record.get("uuid"), record.get("toolUseID")
    infos, errors = record.get("hookInfos"), record.get("hookErrors")
    applied(
        state,
        session,
        day,
        "turn_end",
        {
            "id": id_ is not None,
            "turn": turn is not None,
            "hooks": infos is not None,
            "errors": errors is not None,
        },
    )
    if id_ is None:
        raise ValueError("Claude stop_hook_summary record has no uuid")
    blocks = state.setdefault("stop_blocks", {}).pop(turn, [])
    hooks = []
    for info in infos or []:
        command = info.get("command")
        applied(
            state,
            session,
            day,
            "hook_run",
            {"command": command is not None, "duration": info.get("durationMs") is not None},
        )
        command_key = _command_key(command)
        block = next((b for b in blocks if b[0] == command_key), None)
        if block is not None:
            blocks.remove(block)
        hooks.append(
            {
                "command": command,
                "duration_ms": info.get("durationMs"),
                "blocked": block is not None,
                "reason_bytes": None if block is None else block[1],
            }
        )
    return {
        "id": id_,
        "turn": turn,
        "hooks": hooks,
        "errors_bytes": sum(_size(e) for e in errors or []),
        "blocked": bool(errors),
    }


def _message(record, kind):
    if kind == "attachment":
        return None
    content = (record.get("message") or {}).get("content")
    if kind != "assistant" and kind != "user":
        return None
    if kind == "user" and not record.get("isCompactSummary") and isinstance(content, list):
        if any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content):
            return None
    texts = _text_blocks(content)
    joined = "\n".join(texts)
    flags = [
        name
        for name, key in [("meta", "isMeta"), ("compaction_summary", "isCompactSummary")]
        if record.get(key)
    ]
    native = record.get("origin")
    native = native.get("kind") if isinstance(native, dict) else None
    evidence = labels.origin(content, "claude-code", native, flags)
    # Missing-key text placeholders participate in old joined-text semantics.
    joined_evidence = labels.origin(joined, "claude-code", native, flags)
    evidence["unrecognized_tag"]["joined"] = joined_evidence["unrecognized_tag"]["joined"]
    evidence["markers"] = [
        {
            **m,
            "joined": next(
                (j["joined"] for j in joined_evidence["markers"] if j["name"] == m["name"]), None
            ),
        }
        for m in evidence["markers"]
    ]
    blocks = (
        [
            {"block": i, "text": block.get("text", ""), "bytes": _size(block.get("text", ""))}
            for i, block in enumerate(content)
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if isinstance(content, list)
        else [{"block": 0, "text": content, "bytes": _size(content)}]
        if isinstance(content, str)
        else []
    )
    if kind == "assistant" and not isinstance(content, list):
        blocks = []
    return {
        "channel": kind,
        "origin": evidence,
        "text": joined,
        "joined_nonempty": bool(joined.strip()),
        "joined_bytes": _size(joined),
        "assistant_output_bytes": sum(b["bytes"] for b in blocks) if kind == "assistant" else 0,
        "blocks": blocks,
    }


def _provenance(reference, identity):
    out = {
        field: {
            "native_paths": paths,
            "coverage_keys": COVERAGE_KEYS.get(field, []),
            "basis": "native",
            "rule": "claude_native",
            "ref": reference,
        }
        for field, paths in PROVENANCE.items()
    }
    for field in [
        "message.origin",
        "flush_response",
        "identity.index_session",
        "identity.parent",
        "identity.subagent",
        "calls[].kind",
        "calls[].paths",
        "calls[].paths_complete",
        "results[].child_session",
        "results[].truncation",
        "notifications",
    ]:
        out[field].update(
            basis="convention", rule="claude_" + field.replace(".", "_").replace("[]", "")
        )
    if identity["parent"] is not None:
        out["identity.parent"]["rule"] = "claude_child_parent"
    return out


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
    if event["turn_end"]:
        for hook in event["turn_end"]["hooks"]:
            hook.pop("command")
    event["identity"].pop("cwd")


def _identity_subagent(state, session, record, sidechain, place, reference):
    """The old first-nonempty entrypoint and cumulative native child evidence."""
    facts = state.setdefault("identity_facts", {}).setdefault(
        session, {"entrypoint": None, "entrypoint_ref": None, "subagent": None}
    )
    if not facts["entrypoint"]:
        facts["entrypoint"] = record.get("entrypoint")
        facts["entrypoint_ref"] = reference
    if facts["subagent"] is None:
        if record.get("isSidechain"):
            facts["subagent"] = {"basis": "native", "rule": "is_sidechain", "ref": reference}
        elif sidechain:
            facts["subagent"] = {
                "basis": "convention",
                "rule": "claude_path_layout",
                "ref": ref(place),
            }
        elif facts["entrypoint"] == "sdk-py":
            facts["subagent"] = {
                "basis": "convention",
                "rule": "claude_sdk_entrypoint",
                "ref": facts["entrypoint_ref"],
            }
    proof = facts["subagent"] or {
        "basis": "native" if "isSidechain" in record else "heuristic",
        "rule": "is_sidechain" if "isSidechain" in record else "no_sidechain_evidence",
        "ref": reference,
    }
    return facts["subagent"] is not None, proof


def extract(lines, state, *, place: Place, text: bool):
    """Yield physical native events, then cumulative native coverage, without table rows."""
    facts = discover.path_facts(place) or {}
    parent = state.setdefault(
        "parent_session", facts.get("parent") if facts.get("subagent") else None
    )
    number = state.get("next_line", 1)
    offset = state.get("next_offset", 0)
    partial = False
    for offset, raw in lines:
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        reference = ref(place, number)
        position = {
            "key": f"E{offset}",
            "line": number,
            "offset": offset,
            "end": offset + len(raw),
            "ref": reference,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if not raw.endswith(b"\n"):
            partial = True
            yield {"object": "unparsed", **position, "reason": "truncated", "provisional": True}
            break
        state["next_line"], state["next_offset"] = number + 1, offset + len(raw)
        number += 1
        try:
            record = json.loads(
                raw.decode("utf-8", errors="replace"),
                parse_float=_finite_float,
                parse_constant=_reject_constant,
            )
        except (ValueError, RecursionError):
            state["malformed"] = state.get("malformed", 0) + 1
            yield {"object": "unparsed", **position, "reason": "malformed", "provisional": False}
            continue
        # Do not turn the old non-object/invalid-field failures into repaired data.
        eligible = "timestamp" in record and "sessionId" in record
        kind = record.get("type")
        session = record.get("sessionId")
        agent = record.get("agentId")
        sidechain = bool(record.get("isSidechain") or (parent and agent))
        index_session = f"agent-{agent}" if agent and sidechain else session
        identity = {
            "session": session,
            "index_session": index_session,
            "agent": agent,
            "parent": parent or session if sidechain and agent else None,
            "subagent": sidechain or record.get("entrypoint") == "sdk-py",
            "cwd": record.get("cwd"),
            "entrypoint": record.get("entrypoint"),
            "version": record.get("version"),
        }
        at_ms = _at_ms(record["timestamp"]) if eligible else None
        subagent_proof = None
        if eligible:
            identity["subagent"], subagent_proof = _identity_subagent(
                state, index_session, record, sidechain, place, reference
            )
        flush = eligible and kind != "assistant"
        if flush:
            _flush(state)
        if eligible:
            day = day_of(at_ms)
            state["coverage_session"], state["coverage_day"] = index_session, day
        else:
            day = state.get("coverage_day")
        count_record(
            state,
            index_session if eligible else state.get("coverage_session"),
            day,
            str(kind),
            str(kind) in KNOWN_KINDS,
            record,
            WATCHED,
        )
        event = {
            "object": "index_event",
            **position,
            "native_kind": str(kind),
            "identity": identity,
            "at_ms": at_ms,
            "eligible": eligible,
            "response": None,
            "flush_response": flush,
            "message": _message(record, kind) if eligible else None,
            "calls": [],
            "results": [],
            "injections": [],
            "notifications": [],
            "compaction": None,
            "interruption": None,
            "fork_boundary": None,
            "turn_end": None,
        }
        if not eligible:
            if kind == "fork-context-ref":
                state["fork_copy_next"] = True
                event["fork_boundary"] = {
                    "next_response": True,
                    "copied_response": False,
                    "basis": "native",
                    "rule": "fork_context_ref",
                }
        else:
            source_line = raw.decode("utf-8", errors="replace")
            for notification in NOTIFICATION.findall(source_line):
                id_, status, exit_ = (
                    NOTIFIED_ID.search(notification),
                    NOTIFIED_STATUS.search(notification),
                    NOTIFIED_EXIT.search(notification),
                )
                event["notifications"].append(
                    {
                        "call_id": id_.group(1) if id_ else None,
                        "status": status.group(1) if status else None,
                        "exit_code": int(exit_.group(1)) if exit_ else None,
                    }
                )
            if kind == "attachment":
                event["injections"] = _attachment(record, state, index_session, day)
            elif kind == "assistant":
                message = record.get("message") or {}
                request_id = record.get("requestId") or message.get("id")
                if request_id is None:
                    raise ValueError("Claude assistant record has no response identity")
                if state.get("open_request") is not None and state["open_request"] != request_id:
                    _flush(state)
                    event["flush_response"] = True
                request = state.setdefault("requests", {}).setdefault(
                    request_id, {"session": index_session}
                )
                request.update(at_ms=at_ms, usage=message.get("usage") or {})
                state["open_request"] = request_id
                if state.pop("fork_copy_next", False):
                    state["fork_copy_request"] = request_id
                event["fork_boundary"] = {
                    "next_response": False,
                    "copied_response": state.get("fork_copy_request") == request_id,
                    "basis": "native",
                    "rule": "fork_context_ref",
                }
                event["response"] = {
                    "id": request_id,
                    "model": message.get("model"),
                    "effort": record.get("effort"),
                    "usage": _usage(request["usage"]),
                    "native": request["usage"],
                }
                for i, block in enumerate(message.get("content") or []):
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        applied(
                            state,
                            index_session,
                            day,
                            "text_block",
                            {"text": block.get("text") is not None},
                        )
                    elif block.get("type") == "tool_use":
                        call = _call(block, i, record.get("cwd"))
                        event["calls"].append(call)
                        event["message"]["assistant_output_bytes"] += call["input_bytes"]
                        applied(
                            state,
                            index_session,
                            day,
                            "tool_use",
                            {
                                "id": block.get("id") is not None,
                                "name": block.get("name") is not None,
                                "input": block.get("input") is not None,
                            },
                        )
                        state.setdefault("pending_tools", {})[call["id"]] = index_session
                        value = block.get("input") or {}
                        if call["kind"] == "shell":
                            applied(
                                state,
                                index_session,
                                day,
                                "bash",
                                {"command": value.get("command") is not None},
                            )
                        elif call["kind"] == "skill":
                            applied(
                                state,
                                index_session,
                                day,
                                "skill",
                                {"skill": value.get("skill") is not None},
                            )
                        elif call["kind"] == "question":
                            applied(
                                state,
                                index_session,
                                day,
                                "ask",
                                {"questions": value.get("questions") is not None},
                            )
                            state.setdefault("pending_questions", {})[call["id"]] = True
                            for question in value.get("questions") or []:
                                options = question.get("options")
                                applied(
                                    state,
                                    index_session,
                                    day,
                                    "question",
                                    {
                                        "question": question.get("question") is not None,
                                        "options": options is not None,
                                        "labels": all(
                                            o.get("label") is not None for o in options or []
                                        ),
                                    },
                                )
            elif kind == "user":
                content = (record.get("message") or {}).get("content")
                msg = event["message"]
                if record.get("isCompactSummary"):
                    event["compaction"] = {
                        "summary": True,
                        "basis": "native",
                        "rule": "compact_summary",
                    }
                    event["injections"] = [
                        {
                            "piece": 0,
                            "native_kind": "compact_summary",
                            "source": None,
                            "bytes": msg["joined_bytes"],
                        }
                    ]
                else:
                    results = (
                        [
                            b
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "tool_result"
                        ]
                        if isinstance(content, list)
                        else []
                    )
                    if results:
                        for block in results:
                            call_id = block.get("tool_use_id")
                            applied(
                                state,
                                index_session,
                                day,
                                "tool_result",
                                {
                                    "tool_use_id": call_id is not None,
                                    "content": block.get("content") is not None,
                                },
                            )
                            meta = record.get("toolUseResult")
                            if isinstance(meta, dict):
                                applied(
                                    state,
                                    index_session,
                                    day,
                                    "tool_result_meta",
                                    {"duration": meta.get("durationMs") is not None},
                                )
                            pending = state.setdefault("pending_questions", {}).pop(call_id, None)
                            if pending is not None:
                                applied(
                                    state,
                                    index_session,
                                    day,
                                    "answers",
                                    {
                                        "answers": isinstance(meta, dict)
                                        and meta.get("answers") is not None
                                    },
                                )
                            meta = meta if isinstance(meta, dict) else {}
                            cut = _truncation(block.get("content", ""), meta)
                            pending_tools = state.setdefault("pending_tools", {})
                            matched = call_id in pending_tools
                            owner = pending_tools.pop(call_id, None)
                            if matched and cut["kind"] == "persisted":
                                applied(
                                    state,
                                    owner,
                                    day,
                                    "truncation",
                                    {"persisted_size": cut["original_bytes"] is not None},
                                )
                            agent = meta.get("agentId")
                            event["results"].append(
                                {
                                    "call_id": call_id,
                                    "bytes": _size(block.get("content", "")),
                                    "error": bool(block["is_error"])
                                    if "is_error" in block
                                    else None,
                                    "interrupted": bool(meta["interrupted"])
                                    if "interrupted" in meta
                                    else None,
                                    "native_duration_ms": meta.get("durationMs"),
                                    "background_id": meta.get("backgroundTaskId"),
                                    "agent": agent,
                                    "child_session": f"agent-{agent}"
                                    if isinstance(agent, str) and agent
                                    else None,
                                    "answers": meta.get("answers"),
                                    "truncation": cut,
                                }
                            )
                    else:
                        for block in content if isinstance(content, list) else []:
                            if isinstance(block, dict) and block.get("type") == "text":
                                applied(
                                    state,
                                    index_session,
                                    day,
                                    "text_block",
                                    {"text": block.get("text") is not None},
                                )
                        if msg["text"].strip().startswith("<task-notification>"):
                            event["injections"] = [
                                {
                                    "piece": 0,
                                    "native_kind": "user_injection:<task-notification>",
                                    "source": "<task-notification>",
                                    "bytes": msg["joined_bytes"],
                                }
                            ]
                        elif "[Request interrupted by user" in msg["text"].strip():
                            event["interruption"] = {
                                "user_marker": True,
                                "system": False,
                                "basis": "convention",
                                "rule": "interrupt_marker",
                            }
            elif kind == "system":
                if record.get("subtype") == "interrupted":
                    event["interruption"] = {
                        "user_marker": False,
                        "system": True,
                        "basis": "native",
                        "rule": "system_interrupted",
                    }
                elif record.get("subtype") == "stop_hook_summary":
                    event["turn_end"] = _turn_end(record, state, index_session, day)
        event["provenance"] = _provenance(reference, identity)
        if index_session == session:
            event["provenance"]["identity.index_session"].update(basis="native", rule="session_id")
        if subagent_proof is not None:
            event["provenance"]["identity.subagent"].update(subagent_proof)
        if parent and sidechain and agent:
            event["provenance"]["identity.parent"].update(ref=ref(place), rule="claude_path_layout")
        event["provenance"]["notifications"].update(
            rule="claude_notification_xml", source="physical_line"
        )
        if not text:
            _without_text(event)
        yield event
    _flush(state)
    counts, fields = coverage_rows(state)
    yield {
        "object": "coverage",
        "key": "coverage",
        "records": counts,
        "fields": fields,
        "malformed": state.get("malformed", 0),
        "partial_tail": partial,
    }
