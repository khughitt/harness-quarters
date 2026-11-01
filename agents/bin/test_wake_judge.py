import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("wake-judge")
spec = importlib.util.spec_from_loader("wake_judge", loader=None)
wj = importlib.util.module_from_spec(spec)
sys.modules["wake_judge"] = wj
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), wj.__dict__)

PROMPT = 'Start a background subagent whose only job is to run "sleep 60; cat /s/nonce". End your turn with WAITING.'
NONCE = "5f1c0ffee0dd1234"


def u(content, **extra):
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


def a(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def text(t):
    return {"type": "text", "text": t}


def use(tool_id, name="Agent", **tool_input):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}


def result(tool_id, t):
    return {"type": "tool_result", "tool_use_id": tool_id, "content": t}


def claude_wake():
    return [
        u(PROMPT),
        a(use("toolu_01A")),
        u([result("toolu_01A", "Async agent launched. agentId: a1b2c3d4")]),
        a(text("WAITING")),
        u(f"<task-notification><task-id>a1b2c3d4</task-id><result>{NONCE}</result></task-notification>"),
        a(text(NONCE)),
    ]


def verdict(harness, records):
    return wj.judge(harness, records, NONCE, PROMPT)


def test_claude_wake_passes():
    assert verdict("claude-code", claude_wake()) == "PASS"


def test_claude_waiting_beside_a_tool_call_is_not_a_turn_end():
    # Review 2026-09-24: WAITING in a record that also calls TaskOutput; the controller
    # never ended its turn, and the tool result must not count as a notification.
    records = [
        u(PROMPT),
        a(use("toolu_01A")),
        u([result("toolu_01A", "agentId: a1b2c3d4")]),
        a(text("WAITING"), use("toolu_02B", "TaskOutput")),
        u([result("toolu_02B", f"<task-notification>a1b2c3d4 {NONCE}</task-notification>")]),
        a(text(NONCE)),
    ]
    assert verdict("claude-code", records).startswith("FAIL: no completion notification")


def test_claude_notification_while_a_tool_runs_is_not_a_wake():
    records = claude_wake()
    records[3] = a(text("WAITING"), use("toolu_02B", "TaskOutput"))
    assert verdict("claude-code", records).startswith("FAIL: the controller's turn had not ended")


def test_claude_second_human_prompt_fails():
    records = claude_wake()
    records.insert(4, u(PROMPT))
    assert verdict("claude-code", records).startswith("FAIL: 2 human prompts")


def test_claude_unclassified_input_fails():
    records = claude_wake()
    records.insert(4, u("Did the subagent report?"))
    assert verdict("claude-code", records).startswith("FAIL: unclassified input")


def test_claude_unknown_record_type_fails():
    records = claude_wake()
    records.insert(4, {"type": "mystery-record"})
    assert verdict("claude-code", records).startswith("FAIL: unclassified record type")


def test_claude_nonce_before_notification_fails():
    records = claude_wake()
    records.insert(3, a(text(f"peeked: {NONCE}")))
    assert verdict("claude-code", records).startswith("FAIL: the nonce appeared before")


def test_claude_notification_for_another_child_fails():
    records = claude_wake()
    records[4] = u(f"<task-notification><task-id>zzzz9999</task-id><result>{NONCE}</result></task-notification>")
    assert verdict("claude-code", records).startswith("FAIL: the notification does not name")


def test_claude_no_reply_after_notification_fails():
    assert verdict("claude-code", claude_wake()[:-1]).startswith("FAIL: no controller reply")


def test_claude_context_records_are_allowed():
    records = claude_wake()
    records.insert(4, u("<system-reminder>ctx</system-reminder>"))
    records.insert(1, u("hook context", isMeta=True))
    assert verdict("claude-code", records) == "PASS"


def test_claude_remote_session_change_is_harness_context():
    records = claude_wake()
    records.insert(1, {
        "type": "attachment",
        "attachment": {
            "type": "remote_session_change", "url": None,
            "commit": "", "pr": "", "sendUserFileHint": False,
            "managedCommit": False, "managedPr": False,
        },
        "rendered": [{"content": "<system-reminder>Harness attribution settings</system-reminder>"}],
        "renderedRole": "user", "renderedBesideToolResult": True,
    })
    assert verdict("claude-code", records) == "PASS"


def test_claude_exit_cost_state_does_not_hide_a_wake():
    records = claude_wake()
    records.append({
        "type": "cost-state", "sessionId": "probe-session",
        "totalCostUSD": 0.1, "totalAPIDuration": 1000,
        "totalAPIDurationWithoutRetries": 1000, "totalToolDuration": 60,
        "totalLinesAdded": 0, "totalLinesRemoved": 0,
        "totalDuration": 310000, "startTime": 1791501725540,
        "modelUsage": {"probe-model": {
            "inputTokens": 10, "outputTokens": 20, "thinkingTokens": 0,
            "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
            "webSearchRequests": 0, "costUSD": 0.1,
        }},
        "hasUnknownModelCost": False,
    })
    assert verdict("claude-code", records) == "PASS"


def ev(kind, **extra):
    return {"type": "event_msg", "payload": {"type": kind, **extra}}


def msg(role, t):
    item = "output_text" if role == "assistant" else "input_text"
    return {"type": "response_item", "payload": {"type": "message", "role": role, "content": [{"type": item, "text": t}]}}


def call(call_id):
    return {"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": call_id, "arguments": "{}"}}


def out(call_id, t):
    return {"type": "response_item", "payload": {"type": "function_call_output", "call_id": call_id, "output": t}}


def codex_first_turn():
    return [
        {"type": "session_meta", "payload": {"id": "x", "cwd": "/s"}},
        ev("task_started"), msg("developer", "permissions"), msg("user", "<environment_context>…"),
        msg("user", PROMPT), ev("user_message", message=PROMPT),
        call("call_1"), out("call_1", "agent_id: ag42"), ev("token_count"),
        {"type": "response_item", "payload": {"type": "reasoning", "summary": []}},
        msg("assistant", "WAITING"), ev("agent_message", message="WAITING"), ev("task_complete"),
    ]


def test_codex_without_a_notification_fails():
    # Review 2026-09-24: complete, start, and a later nonce are not a wake by themselves.
    records = codex_first_turn() + [ev("task_started"), msg("assistant", NONCE), ev("task_complete")]
    assert verdict("codex", records).startswith("FAIL: no completion notification")


def test_codex_unclassified_input_fails():
    records = codex_first_turn() + [msg("user", "child finished: ag42"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: unclassified input")


def test_codex_unknown_record_type_fails():
    records = codex_first_turn() + [{"type": "mystery", "payload": {}}]
    assert verdict("codex", records).startswith("FAIL: unclassified record type")


def test_codex_has_no_known_notification_form_yet():
    assert wj.CODEX_NOTIFICATION_PREFIXES == ()


def test_codex_wake_passes_once_a_form_is_known(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn() + [msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE), ev("task_complete")]
    assert verdict("codex", records) == "PASS"


def test_codex_second_human_prompt_fails():
    records = codex_first_turn() + [msg("user", PROMPT)]
    assert verdict("codex", records).startswith("FAIL: 2 human prompts")


def test_codex_turn_ending_in_a_tool_call_fails(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn()
    records.insert(12, call("call_2"))
    records += [msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: the first turn did not end with a reply of exactly WAITING")


def test_claude_waiting_mentioned_but_not_the_final_reply_fails():
    # Review 2026-09-24: a reply that only mentions WAITING is not the specified turn end.
    records = claude_wake()
    records[3] = a(text("I will say WAITING when done; I am still working"))
    assert verdict("claude-code", records).startswith("FAIL: the controller's turn did not end with a reply of exactly WAITING")


def test_codex_waiting_mentioned_but_not_the_final_reply_fails(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn()
    records[10] = msg("assistant", "I will say WAITING when done; I am still working")
    records += [msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: the first turn did not end with a reply of exactly WAITING")


def test_codex_unknown_event_subtype_fails_even_with_a_known_form(monkeypatch):
    # Review 2026-09-24: an unknown event was skipped and the run still passed.
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn() + [ev("mystery_input", message="x"), msg("user", "<agent_done>ag42</agent_done>"),
                                     ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: unclassified event subtype 'mystery_input'")


def test_codex_unknown_response_item_fails_even_with_a_known_form(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn() + [{"type": "response_item", "payload": {"type": "mystery"}},
                                     msg("user", "<agent_done>ag42</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: unclassified response item 'mystery'")


def test_claude_id_from_an_unrelated_tool_result_does_not_count():
    records = claude_wake()
    records[1:1] = [a(use("toolu_00R", "Read")), u([result("toolu_00R", "task id: zzzz9999")])]
    records[-2] = u(f"<task-notification><task-id>zzzz9999</task-id><result>{NONCE}</result></task-notification>")
    assert verdict("claude-code", records).startswith("FAIL: the notification does not name")


def test_claude_without_a_launching_call_fails():
    records = claude_wake()
    records[1] = a(use("toolu_01A", "Read"))
    assert verdict("claude-code", records).startswith("FAIL: no child was launched")


def test_claude_background_bash_launch_passes_on_its_tool_use_id():
    records = claude_wake()
    records[1] = a(use("toolu_01B", "Bash", command="sleep 60; cat /s/nonce", run_in_background=True))
    records[2] = u([result("toolu_01B", "Command running in background")])
    records[4] = u(f"<task-notification><tool-use-id>toolu_01B</tool-use-id><result>{NONCE}</result></task-notification>")
    assert verdict("claude-code", records) == "PASS"


def test_claude_record_without_message_fails():
    records = claude_wake()
    records.insert(2, {"type": "user"})
    assert verdict("claude-code", records).startswith("FAIL: user record without message content")


def test_codex_id_from_an_unrelated_call_does_not_count(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn()
    records[6:6] = [{"type": "response_item", "payload": {"type": "function_call", "name": "shell", "call_id": "call_0", "arguments": "{}"}},
                    out("call_0", "task_id: zz99zz")]
    records += [msg("user", "<agent_done>zz99zz</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: the notification does not name")


def test_claude_empty_launch_id_does_not_match_everything():
    records = claude_wake()
    records[1] = a(use("", "Agent"))
    records[2] = u([result("", "Async agent launched.")])
    records[4] = u(f"<task-notification><task-id>zzzz9999</task-id><result>{NONCE}</result></task-notification>")
    assert verdict("claude-code", records).startswith("FAIL: the notification does not name")


def test_codex_empty_call_id_does_not_match_everything(monkeypatch):
    monkeypatch.setattr(wj, "CODEX_NOTIFICATION_PREFIXES", ("<agent_done>",))
    records = codex_first_turn()
    records[6] = call("")
    records[7] = out("", "spawned")
    records += [msg("user", "<agent_done>zz99zz</agent_done>"), ev("task_started"), msg("assistant", NONCE)]
    assert verdict("codex", records).startswith("FAIL: the notification does not name")


# Record forms from the Claude Code 2.1.282 wake probe (2026-09-24), ids and paths replaced.
def claude_probe_metadata():
    return [
        {"type": "ai-title", "aiTitle": "Background subagent file polling"},
        {"type": "atis-latch", "atis": ""},
        {"type": "mode", "mode": "normal"},
        {"type": "permission-mode", "permissionMode": "default"},
        {"type": "last-prompt", "lastPrompt": "Start a background subagent…", "leafUuid": "x"},
        {"type": "attachment", "attachment": {"type": "hook_additional_context"}},
        {"type": "attachment", "attachment": {"type": "date"}},
        {"type": "queue-operation", "operation": "enqueue", "content": "<task-notification>\n<task-id>a1b2c3d4</task-id>"},
        {"type": "queue-operation", "operation": "dequeue"},
    ]


def test_claude_probe_metadata_records_are_not_input():
    records = claude_wake()
    records[4:4] = claude_probe_metadata()
    assert verdict("claude-code", records) == "PASS"


def test_claude_unknown_attachment_fails():
    records = claude_wake()
    records.insert(4, {"type": "attachment", "attachment": {"type": "queued_command"}})
    assert verdict("claude-code", records).startswith("FAIL: unclassified attachment 'queued_command'")


def test_claude_queued_human_input_fails():
    records = claude_wake()
    records.insert(4, {"type": "queue-operation", "operation": "enqueue", "content": "Did the subagent report?"})
    assert verdict("claude-code", records).startswith("FAIL: queued input that is not a notification")


def test_claude_non_dict_content_block_fails():
    records = claude_wake()
    records[3] = {"type": "assistant", "message": {"role": "assistant", "content": ["WAITING"]}}
    assert verdict("claude-code", records).startswith("FAIL: malformed record")


def test_corrupt_transcript_line_fails(tmp_path, capsys):
    t = tmp_path / "t.jsonl"; t.write_text('{"type": "user"\n')
    p = tmp_path / "prompt"; p.write_text(PROMPT)
    assert wj.main(["claude-code", str(t), NONCE, str(p)]) == 1
    assert capsys.readouterr().out.startswith("FAIL: unreadable transcript line")


# Record forms from the Antigravity CLI (agy) 1.4.12 wake probes (2026-10-31), ids and paths replaced.
AGY_CONV = "1e9adf4a-ae3b-4261-896c-648dd48c3388"
AGY_SUB = "abb9b545-1003-45c7-9ddf-07a269c1ff5c"


def agy_user(request_text, extra_tail="", source="USER_EXPLICIT"):
    body = (
        f"<USER_REQUEST>\n{request_text}\n</USER_REQUEST>\n"
        "<ADDITIONAL_METADATA>\nThe current local time is: 2026-10-31T22:19:25-04:00.\n</ADDITIONAL_METADATA>\n"
        "<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from None to Gemini 3.8 Flash (Low).\n</USER_SETTINGS_CHANGE>"
        + extra_tail
    )
    return {"step_index": 0, "source": source, "type": "USER_INPUT", "status": "DONE", "content": body}


def agy_plan(content=None, tool_calls=None, source="MODEL"):
    rec = {"source": source, "type": "PLANNER_RESPONSE", "status": "DONE"}
    if content is not None:
        rec["content"] = content
    if tool_calls is not None:
        rec["tool_calls"] = tool_calls
    return rec


def agy_generic(content, status="DONE", source="MODEL"):
    return {"source": source, "type": "GENERIC", "status": status, "content": content}


def agy_sysmsg(inner, source="SYSTEM"):
    body = (
        "The following is a <SYSTEM_MESSAGE> not actually sent by the user. "
        "It is provided by the system as important information to pay attention to.\n\n"
        f"<SYSTEM_MESSAGE>\n{inner}\n</SYSTEM_MESSAGE>"
    )
    return {"source": source, "type": "SYSTEM_MESSAGE", "status": "DONE", "content": body}


def agy_subagent_wake():
    return [
        agy_user(PROMPT),
        agy_plan(tool_calls=[{"name": "invoke_subagent", "args": {"Prompt": "run", "Role": "Reader", "TypeName": "self"}}]),
        agy_generic(
            "Created At: 2026-10-31T22:19:31-04:00\nCompleted At: 2026-10-31T22:19:31-04:00\n"
            f'Created the following subagent:\n{{\n  "conversationId":  "{AGY_SUB}",\n  "logAbsoluteUri":  "file:///s/t.jsonl"\n}}\n'
            "The subagent will send you a message when it has completed its task or requires guidance."
        ),
        agy_plan(content="WAITING"),
        agy_sysmsg(f"[Message] timestamp=2026-11-01T02:19:56Z sender={AGY_SUB} priority=MESSAGE_PRIORITY_HIGH content={NONCE}"),
        agy_plan(content=NONCE),
    ]


def agy_shell_wake(is_daemon=False):
    return [
        agy_user(PROMPT),
        agy_plan(tool_calls=[{"name": "run_command", "args": {"CommandLine": "sleep 20; cat /s/nonce", "IsDaemon": is_daemon, "WaitMsBeforeAsync": 500}}]),
        agy_generic(
            "Created At: 2026-10-31T22:19:31-04:00\n"
            f"Tool is running as a background task with task id: {AGY_CONV}/task-2\n"
            "Task Description: sleep 20; cat /s/nonce",
            status="RUNNING",
        ),
        agy_plan(content="WAITING"),
        agy_sysmsg(
            f'[Message] timestamp=2026-11-01T02:19:51Z sender={AGY_CONV}/task-2 priority=MESSAGE_PRIORITY_HIGH '
            f'content=Task id "{AGY_CONV}/task-2" finished with result:\nCommand exited with code 0.\n\nCommand output:\n{NONCE}'
        ),
        agy_plan(content=NONCE),
    ]


def test_agy_subagent_wake_passes():
    assert verdict("agy", agy_subagent_wake()) == "PASS"


def test_agy_shell_wake_passes_with_native_and_stringified_args():
    assert verdict("agy", agy_shell_wake(is_daemon=False)) == "PASS"
    assert verdict("agy", agy_shell_wake(is_daemon="false")) == "PASS"


def test_agy_session_start_hook_context_is_allowed():
    records = agy_subagent_wake()
    records.insert(1, agy_sysmsg("The following system message was injected by a SessionStart hook:\nprofile: personal", source="SYSTEM_SDK"))
    assert verdict("agy", records) == "PASS"


def test_agy_stop_hook_continuation_is_not_a_wake():
    records = agy_subagent_wake()
    records[4] = agy_sysmsg(f"Stop hook blocked termination: report {AGY_SUB}")
    assert verdict("agy", records).startswith("FAIL: unclassified system message")


def test_agy_waiting_beside_a_tool_call_is_not_a_turn_end():
    records = agy_subagent_wake()
    records[3] = agy_plan(content="WAITING", tool_calls=[{"name": "manage_subagents", "args": {"Action": "list"}}])
    assert verdict("agy", records).startswith("FAIL: the controller's turn had not ended")


def test_agy_waiting_mentioned_but_not_final_reply_fails():
    records = agy_subagent_wake()
    records[3] = agy_plan(content="I will say WAITING soon")
    assert verdict("agy", records).startswith("FAIL: the controller's turn did not end with a reply of exactly WAITING")


def test_agy_second_human_prompt_fails():
    records = agy_subagent_wake()
    records.insert(4, agy_user(PROMPT))
    assert verdict("agy", records).startswith("FAIL: 2 human prompts")


def test_agy_unclassified_user_input_and_unknown_metadata_fail():
    records = agy_subagent_wake()
    records.insert(4, agy_user("Did it finish?"))
    assert verdict("agy", records).startswith("FAIL: unclassified input")
    extra_tag = agy_subagent_wake()
    extra_tag[0] = agy_user(PROMPT, extra_tail="\n<QUEUED_USER_NOTE>poke</QUEUED_USER_NOTE>")
    assert verdict("agy", extra_tag).startswith("FAIL: unclassified input")
    mismatched_tag = agy_subagent_wake()
    mismatched_tag[0] = agy_user(
        PROMPT,
        extra_tail="\n<ADDITIONAL_METADATA>sneaky user text</USER_SETTINGS_CHANGE>",
    )
    assert verdict("agy", mismatched_tag).startswith("FAIL: unclassified input")


def test_agy_unknown_record_type_or_source_fails():
    records = agy_subagent_wake()
    records.insert(4, {"source": "MODEL", "type": "MYSTERY_STEP", "content": ""})
    assert verdict("agy", records).startswith("FAIL: unclassified record type")
    bad_source = agy_subagent_wake()
    bad_source[0] = agy_user(PROMPT, source="SYSTEM")
    assert verdict("agy", bad_source).startswith("FAIL: unclassified record source")


def test_agy_truncated_record_fails():
    records = agy_shell_wake()
    records[2] = {**records[2], "truncated_fields": ["content"]}
    assert verdict("agy", records).startswith("FAIL: truncated record")


def test_agy_nonce_before_notification_fails():
    records = agy_subagent_wake()
    records.insert(3, agy_plan(content=f"peeked: {NONCE}"))
    assert verdict("agy", records).startswith("FAIL: the nonce appeared before")


def test_agy_notification_for_another_task_in_same_conversation_fails():
    records = agy_shell_wake()
    records[4] = agy_sysmsg(
        f'[Message] timestamp=2026-11-01T02:19:51Z sender={AGY_CONV}/task-9 priority=MESSAGE_PRIORITY_HIGH content={NONCE}'
    )
    assert verdict("agy", records).startswith("FAIL: the notification does not name")


def test_agy_id_from_an_unrelated_tool_result_does_not_count():
    records = agy_shell_wake()
    records[1:1] = [
        agy_plan(tool_calls=[{"name": "read_file", "args": {"Path": "/s/log"}}]),
        agy_generic(f"Tool is running as a background task with task id: {AGY_CONV}/task-9"),
    ]
    records[-2] = agy_sysmsg(
        f'[Message] timestamp=2026-11-01T02:19:51Z sender={AGY_CONV}/task-9 priority=MESSAGE_PRIORITY_HIGH content={NONCE}'
    )
    assert verdict("agy", records).startswith("FAIL: the notification does not name")


def test_agy_daemon_command_is_not_a_waking_child():
    assert verdict("agy", agy_shell_wake(is_daemon=True)).startswith("FAIL: no child was launched")
    assert verdict("agy", agy_shell_wake(is_daemon="true")).startswith("FAIL: no child was launched")


def test_agy_no_reply_after_notification_fails():
    assert verdict("agy", agy_subagent_wake()[:-1]).startswith("FAIL: no controller reply")


def test_cli_accepts_agy(tmp_path, capsys):
    import json
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(r) for r in agy_shell_wake()) + "\n")
    p = tmp_path / "prompt"
    p.write_text(PROMPT)
    assert wj.main(["agy", str(t), NONCE, str(p)]) == 0
    assert capsys.readouterr().out.strip() == "PASS"
