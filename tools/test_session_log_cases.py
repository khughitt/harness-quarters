"""The session-log acceptance fixtures reproduce every fact their cases expect.

docs/notes/session-log-acceptance-cases.md defines the cases; tools/fixtures/session-logs/
holds their native-format records. These tests read the fixtures with plain JSON, never
through a session reader, so they prove the expected evidence and negatives are present in
the files themselves. A reader's own acceptance test replays the same fixtures through
materialize() and compares its output to the document.
"""
import json
import os
import re
import shutil
import stat
from pathlib import Path

import pytest

FIXTURES = Path(__file__).with_name("fixtures") / "session-logs"
HOME = FIXTURES / "home"
DEGRADED = FIXTURES / "degraded"
TURNS = FIXTURES / "turns"
SDK = FIXTURES / "captures" / "sdk-stream.jsonl"

CA = "c0000000-0000-4000-8000-00000000000a"
CW = "c0000000-0000-4000-8000-00000000000b"
CW2 = "c0000000-0000-4000-8000-00000000000c"
CD = "c0000000-0000-4000-8000-00000000000d"
CU = "c0000000-0000-4000-8000-00000000000e"
CF = "c0000000-0000-4000-8000-00000000000f"
AG = "a0000000000000b01"
XP = "01900000-0000-7000-8000-0000000000a1"
XC = "01900000-0000-7000-8000-0000000000c1"
XA = "01900000-0000-7000-8000-0000000000a2"
XW = "01900000-0000-7000-8000-0000000000b1"
XD = "01900000-0000-7000-8000-0000000000d1"

ROOTS = (".claude/projects", ".claude-work/projects", ".codex/sessions",
         ".codex/archived_sessions", ".codex-work/sessions", ".codex-work/archived_sessions")
CODEX_INJECTED = ("# AGENTS.md", "<")


def materialize(fixture, dest):
    """The replay: copy a fixture home to dest and make what git cannot store unreadable.
    Returns the home to point a reader's HOME at."""
    home = dest / fixture.name
    shutil.copytree(fixture, home)
    if fixture == DEGRADED:
        unreadable = home / ".claude-work/projects/-w-delta" / f"{CU}.jsonl"
        unreadable.chmod(0)
    return home


def one(home, pattern):
    found = sorted(home.glob(pattern))
    assert len(found) == 1, (pattern, found)
    return found[0]


def lines(path):
    return path.read_bytes().splitlines(keepends=True)


def rec(path, n):
    return json.loads(lines(path)[n - 1])


def records(path):
    return [json.loads(raw) for raw in lines(path)]


def blocks(r):
    content = (r.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def claude(home, sid, slug):
    return one(home, f".claude*/projects/{slug}/{sid}.jsonl")


def codex(home, sid):
    return one(home, f".codex*/*/**/rollout-*-{sid}.jsonl")


def subagent():
    return one(HOME, f".claude/projects/-w-alpha/{CA}/subagents/agent-{AG}.jsonl")


def codex_text(r):
    return "".join(b.get("text", "") for b in r["payload"].get("content") or [] if isinstance(b, dict))


def codex_human(r):
    p = r["payload"]
    return (r["type"] == "response_item" and p.get("type") == "message" and p.get("role") == "user"
            and not codex_text(r).startswith(CODEX_INJECTED))


def every_file(home):
    return sorted(p for p in home.rglob("*") if p.is_file())


# --- SL1: calls, results and content blocks --------------------------------------------

def test_sl1_calls_pair_with_results_by_id_across_split_records():
    path = claude(HOME, CA, "-w-alpha")
    calls = {}
    results = {}
    for n, r in enumerate(records(path), 1):
        if r["type"] not in ("user", "assistant"):
            continue
        for i, b in enumerate(blocks(r)):
            if b.get("type") == "tool_use":
                calls[b["id"]] = (n, i)
            if b.get("type") == "tool_result":
                results[b["tool_use_id"]] = (n, i, b.get("is_error", False))
    assert calls == {"toolu_fx_park1": (4, 0), "toolu_fx_status": (5, 0), "toolu_fx_park2": (8, 0),
                     "toolu_fx_agent": (11, 0), "toolu_fx_show": (17, 0)}
    assert results == {"toolu_fx_status": (6, 0, False), "toolu_fx_park1": (7, 0, True),
                       "toolu_fx_park2": (9, 0, False), "toolu_fx_agent": (12, 0, False),
                       "toolu_fx_show": (18, 0, False)}
    message = [(rec(path, n)["message"]["id"], rec(path, n)["apiBlockIndex"]) for n in (3, 4, 5)]
    assert message == [("msg_fx_m1", 0), ("msg_fx_m1", 1), ("msg_fx_m1", 2)]


def test_sl1_request_blob_recarries_calls_without_new_ids():
    path = claude(HOME, CA, "-w-alpha")
    blob = rec(path, 10)
    assert blob["type"] == "api-request-blob" and "uuid" not in blob and "timestamp" not in blob
    assert [(i, b.get("id")) for i, b in enumerate(blocks(blob)) if b["type"] == "tool_use"] == \
        [(1, "toolu_fx_park1"), (2, "toolu_fx_status")]
    naive = [b for r in records(path) for b in blocks(r) if b.get("type") == "tool_use"]
    assert len(naive) == 7


def test_sl1_unknown_record_kind_and_runtime_model():
    path = claude(HOME, CA, "-w-alpha")
    assert rec(path, 16)["type"] == "future-record-kind"
    kinds = {r["type"] for r in records(path)}
    assert kinds == {"user", "assistant", "api-request-blob", "queue-operation", "future-record-kind"}
    models = {(r["message"]["model"], r["requestedModel"]) for r in records(path) if r["type"] == "assistant"}
    assert models == {("claude-model-a", "claude-model-a")}


# --- SL2: what happened, from outputs rather than inputs --------------------------------

def test_sl2_park_was_denied_then_released_by_a_successful_command():
    path = claude(HOME, CA, "-w-alpha")
    call = blocks(rec(path, 4))[0]
    assert call["input"]["command"].startswith("tasks park zz-000001")
    denied = blocks(rec(path, 7))[0]
    assert denied["tool_use_id"] == "toolu_fx_park1" and denied["is_error"] is True
    assert "hook denied" in denied["content"]
    released = blocks(rec(path, 9))[0]
    assert released["tool_use_id"] == "toolu_fx_park2" and released["is_error"] is False
    assert json.loads(released["content"]) == {"id": "zz-000001", "warnings": []}


def test_sl2_human_records_are_marked_by_origin_not_by_a_leading_bracket():
    path = claude(HOME, CA, "-w-alpha")
    reminder = rec(path, 2)
    assert reminder["isMeta"] is True and reminder["message"]["content"].startswith("<system-reminder>")
    strings = {n: r for n, r in enumerate(records(path), 1)
               if r["type"] == "user" and isinstance(r["message"]["content"], str)}
    humans = [n for n, r in strings.items() if (r.get("origin") or {}).get("kind") == "human"]
    assert humans == [1, 15]
    assert strings[15]["message"]["content"].startswith("<command-message>")
    assert strings[1]["promptSource"] == "typed" and "promptSource" not in strings[15]
    assert strings[14]["origin"]["kind"] == "task-notification"
    bracket_rule = [n for n, r in strings.items() if not r.get("isMeta") and not r["message"]["content"].startswith("<")]
    assert bracket_rule == [1]


# --- SL3: runtime and creation model, controller identity -------------------------------

def test_sl3_codex_child_runtime_model_differs_from_creation_model():
    child = codex(HOME, XC)
    meta = rec(child, 1)["payload"]
    assert meta["base_instructions"]["provenance"]["model"] == "codex-model-a"
    turns = [r["payload"] for r in records(child) if r["type"] == "turn_context"]
    assert rec(child, 3)["type"] == "turn_context"
    assert [(t["turn_id"], t["model"]) for t in turns] == [("turn-c1", "codex-model-b")]
    spawn = rec(codex(HOME, XP), 7)["payload"]
    assert json.loads(spawn["arguments"])["model"] == "codex-model-b"
    parent_turns = [r["payload"]["model"] for r in records(codex(HOME, XP)) if r["type"] == "turn_context"]
    assert parent_turns == ["codex-model-a"]


def test_sl3_child_controller_comes_from_thread_spawn_not_inherited_session_id():
    child = codex(HOME, XC)
    meta = rec(child, 1)["payload"]
    assert meta["id"] == XC
    assert meta["session_id"] == XP  # inherited: not the child's identity
    assert meta["source"]["subagent"]["thread_spawn"]["parent_thread_id"] == XP
    assert "forked_from_id" not in meta
    assert json.loads(rec(codex(HOME, XP), 7)["payload"]["arguments"])["fork_turns"] == "none"
    assert [n for n, r in enumerate(records(child), 1) if r["type"] == "session_meta"] == [1]
    root = rec(codex(HOME, XP), 1)["payload"]
    assert root["source"] == "cli" and root["session_id"] == root["id"] == XP


def test_sl3_claude_child_requested_alias_differs_from_runtime_model():
    parent = claude(HOME, CA, "-w-alpha")
    assert blocks(rec(parent, 11))[0]["input"]["model"] == "sonnet"
    meta = json.loads(subagent().with_suffix(".meta.json").read_text())
    assert meta["model"] == "sonnet"
    assert rec(parent, 12)["toolUseResult"]["resolvedModel"] == "claude-model-b"
    runtime = {r["message"]["model"] for r in records(subagent()) if r["type"] == "assistant"}
    assert runtime == {"claude-model-b"}


# --- SL4: stores, homes and coverage ------------------------------------------------------

def test_sl4_home_routing_and_archived_location():
    present = {root for root in ROOTS if (HOME / root).is_dir()}
    assert present == set(ROOTS) - {".codex-work/archived_sessions"}
    beta = {}
    for path in every_file(HOME):
        if path.suffix != ".jsonl":
            continue
        first = json.loads(lines(path)[0])
        cwd = first.get("cwd") or first.get("payload", {}).get("cwd")
        if cwd == "/w/beta":
            beta[path.relative_to(HOME).parts[0]] = beta.get(path.relative_to(HOME).parts[0], 0) + 1
    assert beta == {".claude-work": 2, ".codex-work": 1}
    archived = codex(HOME, XA)
    assert archived.relative_to(HOME).parts[:2] == (".codex", "archived_sessions")


# --- SL5: recovering a human turn ----------------------------------------------------------

def test_sl5_human_findings_turn_is_the_only_human_match():
    hits = []
    for path in every_file(HOME):
        if path.suffix != ".jsonl" or "rollout-" not in path.name:
            continue
        for n, r in enumerate(records(path), 1):
            if r["type"] == "response_item" and "eight review findings" in codex_text(r):
                hits.append((path.name, n, codex_human(r)))
    name = f"rollout-2026-09-20T09-00-00-{XA}.jsonl"
    assert sorted(hits) == [(name, 4, False), (name, 5, True)]


def test_sl5_resume_copy_repeats_the_human_turn_with_the_same_uuid():
    first, copy = claude(HOME, CW, "-w-beta"), claude(HOME, CW2, "-w-beta")
    a, b = rec(first, 1), rec(copy, 1)
    assert a["message"]["content"] == b["message"]["content"] == "Push the branch."
    assert a["uuid"] == b["uuid"] == "u-w01" and (a["sessionId"], b["sessionId"]) == (CW, CW2)
    assert rec(copy, 4)["message"]["content"] == "Push again after the fix."
    assert rec(copy, 4)["uuid"] not in {r.get("uuid") for r in records(first)}


# --- SL6: an aggregate over tool outputs ----------------------------------------------------

def test_sl6_hook_durations_dedupe_to_three_outputs():
    seen = {}
    occurrences = 0
    for path in sorted((HOME / ".claude-work/projects").rglob("*.jsonl")):
        for r in records(path):
            for b in blocks(r):
                if b.get("type") != "tool_result":
                    continue
                m = re.match(r"pre-push: test-fast (passed|failed) in ([\d.]+)s", b["content"])
                if m:
                    occurrences += 1
                    seen.setdefault(b["tool_use_id"], (m.group(1), float(m.group(2))))
    assert occurrences == 5
    assert seen == {"toolu_fx_push1": ("passed", 41.2), "toolu_fx_push2": ("failed", 63.0),
                    "toolu_fx_push3": ("passed", 38.9)}
    reminder = rec(claude(HOME, CW, "-w-beta"), 4)
    assert reminder["isMeta"] is True and "pre-push" in reminder["message"]["content"]


# --- SL7: tracing a report to its origin ----------------------------------------------------

def test_sl7_report_id_is_in_the_filing_output_and_only_a_read_names_it_as_input():
    child = codex(HOME, XC)
    call, out = rec(child, 5)["payload"], rec(child, 6)["payload"]
    assert call["call_id"] == out["call_id"] == "call_fx_file"
    assert "tasks feedback" in call["input"] and "zz-0000f1" not in call["input"]
    inner = json.loads(out["output"][1]["text"])
    assert inner["exit_code"] == 0 and json.loads(inner["output"])["id"] == "zz-0000f1"
    inputs = []
    for path in every_file(HOME):
        for n, r in enumerate(records(path) if path.suffix == ".jsonl" else [], 1):
            p = r.get("payload") or {}
            if p.get("type") in ("custom_tool_call", "function_call") and \
                    "zz-0000f1" in str(p.get("input", "")) + str(p.get("arguments", "")):
                inputs.append((path.name, n))
            for i, b in enumerate(blocks(r)):
                if b.get("type") == "tool_use" and "zz-0000f1" in json.dumps(b["input"]):
                    inputs.append((path.name, n, i))
    assert inputs == [(f"{CA}.jsonl", 17, 0)]


def test_sl7_origin_human_turn_is_in_the_recorded_parent():
    parent = codex(HOME, XP)
    assert rec(codex(HOME, XC), 1)["payload"]["source"]["subagent"]["thread_spawn"]["parent_thread_id"] == XP
    humans = [n for n, r in enumerate(records(parent), 1) if codex_human(r)]
    assert humans == [6]
    assert codex_text(rec(parent, 4)).startswith("# AGENTS.md") and "tasks feedback" in codex_text(rec(parent, 4))


def test_sl7_brief_is_encrypted_in_child_and_plain_in_parent_spawn():
    content = rec(codex(HOME, XC), 4)["payload"]["content"]
    assert [b["type"] for b in content] == ["input_text", "encrypted_content"]
    parent = codex(HOME, XP)
    spawn, started, spawned = (rec(parent, n)["payload"] for n in (7, 8, 9))
    assert json.loads(spawn["arguments"])["message"].startswith("File feedback about the archive timer")
    assert started["item"]["id"] == spawn["call_id"] == "call_fx_spawn"
    assert started["item"]["kind"] == "started" and started["item"]["agent_thread_id"] == XC
    assert started["item"]["agent_path"] == "/root/filer" == rec(codex(HOME, XC), 1)["payload"]["agent_path"]
    assert spawned["call_id"] == "call_fx_spawn" and json.loads(spawned["output"])["task_name"] == "/root/filer"


def test_sl7_mentions_elsewhere_are_reads_or_text_not_filing():
    parent = claude(HOME, CA, "-w-alpha")
    show = blocks(rec(parent, 17))[0]
    assert show["input"]["command"] == "tasks show zz-0000f1"
    assert "zz-0000f1" in blocks(rec(parent, 18))[0]["content"]
    assert "zz-0000f1" in rec(parent, 15)["message"]["content"]
    mention = rec(codex(HOME, XP), 13)["payload"]
    assert mention["role"] == "assistant" and "zz-0000f1" in codex_text(rec(codex(HOME, XP), 13))


# --- SL8: parent to child, and incidental parent fields ------------------------------------

def test_sl8_parent_result_names_the_child_and_its_completion_precedes_the_notice():
    parent = claude(HOME, CA, "-w-alpha")
    launched = rec(parent, 12)
    assert launched["toolUseResult"]["agentId"] == AG
    assert json.loads(subagent().with_suffix(".meta.json").read_text())["toolUseId"] == "toolu_fx_agent"
    child = records(subagent())
    assert all(r["isSidechain"] and r["agentId"] == AG and r["sessionId"] == CA for r in child)
    assert child[-1]["timestamp"] == "2026-10-08T12:02:40.000Z"
    queued = rec(parent, 13)
    assert queued["type"] == "queue-operation" and queued["operation"] == "enqueue"
    assert queued["timestamp"] == "2026-10-08T12:02:41.000Z"
    notice = rec(parent, 14)
    assert notice["timestamp"] == "2026-10-08T12:03:00.000Z" and notice["origin"]["kind"] == "task-notification"
    assert notice["message"]["content"] == queued["content"] and AG in queued["content"]


def test_sl8_child_first_record_is_the_dispatch_prompt():
    first = records(subagent())[0]
    parent_call = blocks(rec(claude(HOME, CA, "-w-alpha"), 11))[0]
    assert first["type"] == "user" and first["isSidechain"] is True
    assert first["message"]["content"] == parent_call["input"]["prompt"]


def test_sl8_parent_named_fields_that_are_not_session_links():
    root = records(claude(HOME, CA, "-w-alpha"))
    assert root[1]["parentUuid"] == "u-a01"
    assert not any(r.get("isSidechain") or "agentId" in r for r in root)
    turn = rec(codex(HOME, XC), 2)["payload"]["turn_attribution"]
    assert turn["parent_turn_id"] == "turn-p1"
    assert "parent_thread_id" not in rec(codex(HOME, XP), 1)["payload"]


# --- SL9: SDK dispatch links -----------------------------------------------------------------

def test_sl9_child_events_bind_to_dispatch_calls_not_sessions():
    events = records(SDK)
    assert {e["session_id"] for e in events} == {"c0000000-0000-4000-8000-000000000051"}
    by_call = {}
    for n, e in enumerate(events, 1):
        assert len(blocks(e)) <= 1
        for b in blocks(e):
            if b.get("type") == "tool_use":
                by_call[b["id"]] = (n, e["parent_tool_use_id"], b["name"])
            if b.get("type") == "tool_result":
                by_call[b["tool_use_id"]] += (n, e["parent_tool_use_id"], b.get("is_error", False))
    assert by_call == {
        "toolu_fx_dA": (2, None, "Agent", 8, None, False),
        "toolu_fx_dB": (3, None, "Agent", 9, None, False),
        "toolu_fx_wA": (4, "toolu_fx_dA", "Write", 7, "toolu_fx_dA", False),
        "toolu_fx_wB": (5, "toolu_fx_dB", "Write", 6, "toolu_fx_dB", True),
    }


# --- SL10: empty matches carry their coverage --------------------------------------------------

def test_sl10_degraded_home_hides_its_only_matches(tmp_path):
    home = materialize(DEGRADED, tmp_path)
    present = {root for root in ROOTS if (home / root).is_dir()}
    assert present == {".claude/projects", ".claude-work/projects", ".codex/sessions"}

    unreadable = claude(home, CU, "-w-delta")
    assert stat.S_IMODE(unreadable.stat().st_mode) == 0
    if os.geteuid() != 0:  # root reads a mode-0 file; the doc requires a non-root replay
        with pytest.raises(PermissionError):
            unreadable.read_bytes()

    malformed = lines(claude(home, CD, "-w-delta"))
    with pytest.raises(json.JSONDecodeError):
        json.loads(malformed[1])
    assert malformed[1].endswith(b"\n") and b"needle-term" in malformed[1]

    tail = lines(codex(home, XD))
    assert len(tail) == 3 and not tail[2].endswith(b"\n") and b"needle-term" in tail[2]
    with pytest.raises(json.JSONDecodeError):
        json.loads(tail[2])

    parsed = []
    for path in sorted(p for p in home.rglob("*.jsonl") if p != unreadable):
        for raw in lines(path):
            try:
                parsed.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    assert not any("needle-term" in json.dumps(r) for r in parsed)


def test_sl10_missing_session_is_only_mentioned():
    for fixture in (HOME, DEGRADED):
        assert not any(CF in p.name for p in every_file(fixture))
    mention = rec(claude(DEGRADED, CD, "-w-delta"), 3)
    assert mention["type"] == "assistant"
    assert CF in mention["message"]["content"][0]["text"] and "clipped" in mention["message"]["content"][0]["text"]


# --- SL11: turn-final messages, task evidence, forks and escapes ---------------------------------

def test_sl11_marker_session_turn_ends_and_markers():
    cm = one(TURNS, ".claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000021.jsonl")
    rs = records(cm)
    assert sum(1 for r in rs if r.get("type") == "system" and r.get("subtype") == "turn_duration") == 9
    blocked = [r for r in rs if r.get("subtype") == "stop_hook_summary" and r.get("hookErrors")]
    assert len(blocked) == 1
    # Stop-hook continuation in live order: end_turn, isMeta feedback, blocking attachment, summary
    i = rs.index(blocked[0])
    assert rs[i - 1]["type"] == "attachment" and rs[i - 1]["attachment"]["type"] == "hook_blocking_error"
    assert rs[i - 2]["type"] == "user" and rs[i - 2]["isMeta"] is True
    assert rs[i - 3]["message"]["stop_reason"] == "end_turn"


def test_sl11_skill_load_record_shares_the_turn_prompt():
    rs = records(one(TURNS, ".claude/projects/-w-gamma/*000021.jsonl"))
    skill = next(r for r in rs if r.get("isMeta") and r.get("sourceToolUseID"))
    call = next(b for r in rs for b in blocks(r) if b.get("type") == "tool_use" and b["id"] == skill["sourceToolUseID"])
    assert call["name"] == "Skill"
    prompt = rs[31]  # CM:32, turn 5's typed prompt
    assert prompt["origin"]["kind"] == "human" and skill["promptId"] == prompt["promptId"]


def test_sl11_claude_triggers_markers_and_synthetic_end():
    cm = one(TURNS, ".claude/projects/-w-gamma/*000021.jsonl")
    assert rec(cm, 44)["isMeta"] is True and rec(cm, 44)["origin"]["kind"] == "peer"
    assert rec(cm, 60)["origin"]["kind"] == "task-notification"
    assert rec(cm, 40)["isMeta"] is True and rec(cm, 40)["turnOrigin"] == "scheduled"
    for n in (52, 54):
        assert blocks(rec(cm, n))[0]["text"] == "[Request interrupted by user]" and "origin" not in rec(cm, n)
    synthetic = rec(cm, 58)["message"]
    assert (synthetic["model"], synthetic["stop_reason"]) == ("<synthetic>", "stop_sequence")
    assert rec(cm, 59)["subtype"] == "turn_duration"


def test_sl11_local_commands_and_queued_human_attachment():
    rs = records(one(TURNS, ".claude/projects/-w-gamma/*000021.jsonl"))
    local = [r for r in rs if r.get("type") == "system" and r.get("subtype") == "local_command"]
    assert [r["content"].split(">")[0] for r in local] == ["<command-name", "<local-command-stdout"]  # the live field
    queued = next(r for r in rs if r.get("type") == "attachment" and r["attachment"]["type"] == "queued_command")
    assert queued["attachment"]["origin"]["kind"] == "human"
    # live placement: after a tool result (CM:17), not between a call and its result
    assert rs.index(queued) == 17 and blocks(rs[16])[0]["type"] == "tool_result"


def test_sl11_codex_statuses_by_closing_event():
    xe = records(codex(TURNS, "01900000-0000-7000-8000-0000000000e1"))
    starts = [r["payload"]["turn_id"] for r in xe if r["type"] == "event_msg" and r["payload"]["type"] == "task_started"]
    ends = {r["payload"]["turn_id"]: r["payload"]["type"] for r in xe
            if r["type"] == "event_msg" and r["payload"]["type"] in ("task_complete", "turn_aborted")}
    assert starts == ["te1", "te2", "te3", "te4", "te5", "te6", "te7"]
    for path in TURNS.glob(".codex/sessions/**/rollout-*.jsonl"):  # live ordinals count from 0
        assert [r["ordinal"] for r in records(path)] == list(range(len(lines(path))))
    assert ends == {"te1": "task_complete", "te2": "task_complete", "te3": "turn_aborted",
                    "te4": "task_complete", "te5": "task_complete"}


def test_sl11_codex_finals_questions_and_phases():
    path = codex(TURNS, "01900000-0000-7000-8000-0000000000e1")
    assert rec(path, 14)["payload"]["item"]["questions"]
    assert rec(path, 26)["payload"]["last_agent_message"] is None
    phaseless = rec(path, 30)["payload"]
    assert "phase" not in phaseless and rec(path, 31)["payload"]["last_agent_message"] == phaseless["content"][0]["text"]
    assert rec(path, 35)["payload"]["phase"] == "final_answer" and rec(path, 36)["payload"]["type"] == "task_started"


def test_sl11_agent_message_direction():
    xe = records(codex(TURNS, "01900000-0000-7000-8000-0000000000e1"))
    xf = records(codex(TURNS, "01900000-0000-7000-8000-0000000000f1"))
    report = next(r["payload"] for r in xe if r["payload"].get("type") == "agent_message")
    dispatch = next(r["payload"] for r in xf if r["payload"].get("type") == "agent_message")
    assert (report["author"], report["recipient"]) == ("/root/worker", "/root")
    assert (dispatch["author"], dispatch["recipient"]) == ("/root", "/root/worker")
    assert xf[0]["payload"]["source"]["subagent"]["thread_spawn"]["agent_path"] == "/root/worker"


def test_sl11_fork_without_parent_holds_only_copied_history():
    xk = records(codex(TURNS, "01900000-0000-7000-8000-0000000000f2"))
    metas = [r["payload"]["id"] for r in xk if r["type"] == "session_meta"]
    assert metas == ["01900000-0000-7000-8000-0000000000f2", "01900000-0000-7000-8000-0000000000f9"]
    assert xk[5]["payload"]["phase"] == "final_answer"  # XK:6, the absent parent's final
    # the native copy boundary lies past the last record: everything after XK:2 is copied history
    assert xk[0]["payload"]["subagent_history_start_ordinal"] > max(r["ordinal"] for r in xk)
    assert not list(FIXTURES.glob("**/rollout-*-01900000-0000-7000-8000-0000000000f9.jsonl"))


def test_sl11_task_document_and_evidence_sessions():
    doc = json.loads((FIXTURES / "captures" / "tasks-show-zz-000021.json").read_text())
    note = doc["task"]["notes"][0]
    assert note["harness_session"] == "claude-code:c0000000-0000-4000-8000-000000000022"
    ct1 = records(one(TURNS, ".claude/projects/-w-gamma/*000022.jsonl"))
    assert ct1[0]["timestamp"] <= note["at"].replace("Z", ".000Z") <= ct1[-1]["timestamp"]
    assert not any("zz-000021" in json.dumps(r) for r in ct1)
    ct3 = records(one(TURNS, ".claude/projects/-w-gamma/*000024.jsonl"))
    commands = [b["input"]["command"] for r in ct3 for b in blocks(r) if b.get("type") == "tool_use"]
    assert commands == ["tasks start zz-000021", "false && tasks start zz-000021",
                        "tasks start zz-000021 && false"]
    assert all(b.get("is_error") for r in ct3 for b in blocks(r) if b.get("type") == "tool_result")


def test_sl11_escaped_needle_is_absent_from_the_bytes():
    raw = (FIXTURES / "captures" / "escaped.jsonl").read_bytes()
    assert b"needle" not in raw and b"\\u006eeedle" in raw
    assert json.loads(raw)["message"]["content"] == "needle"
    bad = (FIXTURES / "captures" / "escaped-malformed.jsonl").read_bytes().splitlines()
    assert len(bad) == 2 and b"\\u006eeedle" in bad[1]
    assert json.loads(bad[0])["message"]["content"] == "hello"
    with pytest.raises(json.JSONDecodeError):
        json.loads(bad[1])


# --- the corpus itself ---------------------------------------------------------------------------

PRIVATE = re.compile(r"/home/|/mnt/|/Users/|Dropbox|keith|titan|europa|@[a-z]+\.(com|org)|toolu_01"
                     r"|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
SYNTHETIC_UUID = re.compile(r"\b(c0000000-0000-4000-8000|01900000-0000-7000-8000)-[0-9a-f]{12}\b")


def test_fixtures_hold_no_private_paths_or_identifiers():
    for path in every_file(FIXTURES):
        text = SYNTHETIC_UUID.sub("", path.read_text())
        assert not PRIVATE.search(text), (path, PRIVATE.search(text))
        assert not PRIVATE.search(SYNTHETIC_UUID.sub("", str(path.relative_to(FIXTURES))))


def test_every_fixture_file_is_listed_by_the_cases_document():
    doc = (Path(__file__).parents[1] / "docs/notes/session-log-acceptance-cases.md").read_text()
    listed = set(re.findall(r"`((?:home|degraded|captures|turns)/[^`]+)`", doc))
    on_disk = {str(p.relative_to(FIXTURES)) for p in every_file(FIXTURES)}
    assert on_disk == listed
    assert CF in doc
