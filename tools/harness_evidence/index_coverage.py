"""Claude native presence declarations and cumulative extraction-site populations.

Relocated from frozen obs0a09481c. Historical usage flushes remain schedule-dependent.
"""
from datetime import datetime, timezone

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
        "isMeta": "flag",
        "isCompactSummary": "flag",
        "origin.kind": "dimension",
        "message.content[].type": "applied:text_block",
        "message.content[].text": "applied:text_block",
        "message.content[].id": "applied:tool_use",
        "message.content[].name": "applied:tool_use",
        "message.content[].input": "applied:tool_use",
        "message.content[].input.command": "applied:bash",
        "message.content[].input.file_path": "dimension",
        "message.content[].input.path": "dimension",
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
        "uuid": "dimension",
        "parentUuid": "dimension",
        "isMeta": "flag",
        "origin.kind": "dimension",
        "message.content[].content[].text": "dimension",
        "message.content[].content[].type": "dimension",
        "message.content[].type": "applied:text_block",
        "message.content[].text": "applied:text_block",
        "message.content[].tool_use_id": "applied:tool_result",
        "message.content[].content": "applied:tool_result",
        "message.content[].is_error": "flag",
        "toolUseResult": "applied:tool_result_meta",
        "toolUseResult.durationMs": "applied:tool_result_meta",
        "toolUseResult.interrupted": "flag",
        "toolUseResult.stdout": "flag",
        "toolUseResult.stderr": "flag",
        "toolUseResult.persistedOutputSize": "applied:truncation",
        "toolUseResult.backgroundTaskId": "flag",
        "toolUseResult.agentId": "dimension",
        "toolUseResult.answers": "applied:answers",
    },
    "attachment": {
        "uuid": "dimension",
        "parentUuid": "dimension",
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
        "uuid": ("applied:turn_end", "dimension"),
        "parentUuid": "dimension",
        "compactMetadata.trigger": "dimension",
        "content": "dimension",
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
