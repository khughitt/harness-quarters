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
