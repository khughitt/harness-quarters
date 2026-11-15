"""Codex native declarations relocated from OBS 1e0afad1.

Only sites actually visited by the extractor contribute populations.
Unwatched native candidate dimensions do not change the historical populations.
"""
from .index_coverage import day_of, count_record, applied, coverage_rows

QUALIFIED = ("event_msg", "response_item")

HANDLED_KINDS = frozenset({
    "session_meta", "turn_context", "token_usage_record", "compacted",
    "event_msg:token_count", "event_msg:turn_aborted", "response_item:message",
    "response_item:function_call", "response_item:custom_tool_call",
    "response_item:function_call_output", "response_item:custom_tool_call_output",
    "event_msg:exec_command_end", "event_msg:patch_apply_end", "event_msg:mcp_tool_call_end",
    "event_msg:item_completed"})

IGNORED_KINDS = frozenset({
    "event_msg:task_started", "event_msg:task_complete",
    "event_msg:thread_settings_applied", "event_msg:agent_message",
    "event_msg:agent_reasoning", "event_msg:collab_agent_interaction_end",
    "event_msg:collab_agent_spawn_end", "event_msg:collab_close_end",
    "event_msg:collab_resume_end", "event_msg:collab_waiting_end",
    "event_msg:context_compacted", "event_msg:error", "event_msg:sub_agent_activity",
    "event_msg:thread_rolled_back",
    "event_msg:user_message", "event_msg:view_image_tool_call",
    "event_msg:web_search_end", "response_item:reasoning", "response_item:agent_message",
    "response_item:tool_search_call", "response_item:tool_search_output",
    "response_item:web_search_call", "inter_agent_communication_metadata", "world_state"})

KNOWN_KINDS = HANDLED_KINDS | IGNORED_KINDS

COMMON_READS = ("type", "timestamp", "payload", "payload.type", "payload.timestamp")

COUNTERS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
            "output_tokens", "reasoning_output_tokens")

WATCHED = {
    "session_meta": {
        "sources": ("payload.id", "payload.cwd", "payload.originator", "payload.cli_version",
                    "payload.thread_source"),
        "inputs": {"session": ("payload.id",), "version": ("payload.cli_version",),
                   "entrypoint": ("payload.originator",)}},
    "turn_context": {
        "sources": ("payload.model", "payload.effort",
                    "payload.collaboration_mode.settings.reasoning_effort"),
        "inputs": {"model": ("payload.model",),
                   "effort": ("payload.effort",
                              "payload.collaboration_mode.settings.reasoning_effort")}},
    "token_usage_record": {
        "sources": ("payload.response_id", *(f"payload.usage.{name}" for name in COUNTERS)),
        "inputs": {"response": ("payload.response_id",)},
        "feeds": {f"payload.usage.{name}": (f"applied:usage/input:{name}",) for name in COUNTERS}},
    "event_msg:token_count": {
        "sources": ("payload.info.total_token_usage", "payload.info.model_context_window",
                    *(f"payload.info.last_token_usage.{name}" for name in COUNTERS)),
        "inputs": {"context_window": ("payload.info.model_context_window",)},
        "feeds": {f"payload.info.last_token_usage.{name}": (f"applied:usage/input:{name}",)
                  for name in COUNTERS}},
    "response_item:message": {
        "sources": ("payload.role", "payload.content"),
        "inputs": {"content": ("payload.content",)},
        "feeds": {"payload.content": ("applied:text_block/input:text",)}},
    "response_item:function_call": {
        "sources": ("payload.call_id", "payload.name", "payload.arguments"), "inputs": {},
        "feeds": {"payload.call_id": ("applied:tool_call/input:call_id",),
                  "payload.name": ("applied:tool_call/input:name",),
                  "payload.arguments": ("applied:tool_call/input:value",)}},
    "response_item:custom_tool_call": {
        "sources": ("payload.call_id", "payload.name", "payload.input"), "inputs": {},
        "feeds": {"payload.call_id": ("applied:tool_call/input:call_id",),
                  "payload.name": ("applied:tool_call/input:name",),
                  "payload.input": ("applied:tool_call/input:value",)}},
    "response_item:function_call_output": {
        "sources": ("payload.call_id", "payload.output"), "inputs": {},
        "feeds": {"payload.output": ("applied:tool_output/input:output",)}},
    "response_item:custom_tool_call_output": {
        "sources": ("payload.call_id", "payload.output"), "inputs": {},
        "feeds": {"payload.output": ("applied:tool_output/input:output",)}},
    "compacted": {
        "sources": ("payload.replacement_history",),
        "inputs": {"history": ("payload.replacement_history",)}},
}

APPLIED = {
    "usage": COUNTERS,                         # the usage object that became a turn
    "text_block": ("text",),                   # each input_text/output_text block
    "tool_call": ("call_id", "name", "value"), # each function or custom tool call
    "tool_output": ("call_id", "output"),      # each tool call output
    "spawn": ("parent_thread_id",),            # session_meta whose source names a subagent
    "base_instructions": ("text",),            # session_meta carrying base instructions
    "exec_end": ("call_id", "exit_code", "duration"),   # each exec_command_end
    "patch_end": ("call_id", "success"),                # each patch_apply_end
    "mcp_end": ("call_id", "result"),                   # each mcp_tool_call_end
    "command_item": ("id", "exit_code", "process_id", "started_at_ms", "completed_at_ms"),
    "tool_item": ("status",),                  # each FileChange / McpToolCall item
    "shell_arguments": ("workdir",),           # each shell function call's JSON arguments
}

UNWATCHED = {
    "session_meta": {"payload.source.subagent.thread_spawn.parent_thread_id": "applied:spawn",
                     "payload.parent_thread_id": "applied:spawn",
                     "payload.base_instructions.text": "applied:base_instructions",
                     "payload.forked_from_id": "dimension"},
    "turn_context": {"payload.cwd": "dimension"},
    "response_item:message": {"payload.content[].type": "applied:text_block",
                              "payload.content[].text": "applied:text_block"},
    "event_msg:exec_command_end": {"payload.call_id": "applied:exec_end",
                                   "payload.exit_code": "applied:exec_end",
                                   "payload.duration": "applied:exec_end",
                                   "payload.duration.secs": "applied:exec_end",
                                   "payload.duration.nanos": "applied:exec_end"},
    "event_msg:patch_apply_end": {"payload.call_id": "applied:patch_end",
                                  "payload.success": "applied:patch_end"},
    "event_msg:mcp_tool_call_end": {"payload.call_id": "applied:mcp_end",
                                    "payload.result": "applied:mcp_end",
                                    "payload.result.Err": "applied:mcp_end",
                                    "payload.result.Ok": "applied:mcp_end",
                                    "payload.result.Ok.isError": "applied:mcp_end"},
    "event_msg:item_completed": {"payload.item": "applied:command_item",
                                 "payload.item.type": "dimension",
                                 # a command item's id, and the key of a FileChange's writes
                                 "payload.item.id": ("applied:command_item", "dimension"),
                                 "payload.item.exit_code": "applied:command_item",
                                 "payload.item.process_id": "applied:command_item",
                                 "payload.item.status": "applied:tool_item",
                                 "payload.item.changes": "dimension",
                                 "payload.started_at_ms": "applied:command_item",
                                 "payload.completed_at_ms": "applied:command_item"},
    "response_item:function_call": {"payload.arguments.message": "dimension"},
    "response_item:custom_tool_call": {"payload.input.message": "dimension"},
    "response_item:function_call_output": {"payload.output[].text": "applied:tool_output"},
    "response_item:custom_tool_call_output": {"payload.output[].text": "applied:tool_output"},
}

def record_kind(record):
    kind = str(record.get("type"))
    if kind in QUALIFIED:
        return f"{kind}:{(record.get('payload') or {}).get('type')}"
    return kind
