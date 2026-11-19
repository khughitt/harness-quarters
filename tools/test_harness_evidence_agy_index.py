"""agy index conformance (spec rev 2 §4.3-§4.5, §5) over the synthetic samples in
fixtures/session-logs/agy-index. Each test decodes a private copy of the store whose
conversation_summaries.db is built from the committed SQL text."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from harness_evidence import DECODER_VERSION, SCHEMA, index_stream

TOOLS = Path(__file__).resolve().parent
STORE = TOOLS / "fixtures/session-logs/agy-index/.gemini/antigravity-cli"
H = "b9000000-0000-4000-8000-000000000001"  # human session: calls, exit codes, truncation, skill
G = "b9000000-0000-4000-8000-000000000002"  # background, system kinds, checkpoint, surplus, unknown
P = "b9000000-0000-4000-8000-000000000003"  # subagent of G: invoke_subagent, ask_question wait
K = "b9000000-0000-4000-8000-000000000004"  # no summary row; malformed line and partial tail
Q = "b9000000-0000-4000-8000-000000000005"  # the child P's invoke_subagent created
# The discovery store's transcripts are catalogued as index samples too.
DISCOVERY = TOOLS / "fixtures/session-logs/agy/.gemini/antigravity-cli"
A1, B1, C1 = (f"a9000000-0000-4000-8000-0000000000{x}1" for x in "abc")
SAMPLES = [("index", c) for c in (H, G, P, K)] + [("discovery", c) for c in (A1, B1, C1)]
ENVELOPE = {"schema": SCHEMA, "decoder": {"version": DECODER_VERSION, "revision": "r" * 40}}


def build(tmp_path, source, home):
    root = tmp_path / home / ".gemini/antigravity-cli"
    shutil.copytree(source, root)
    with sqlite3.connect(root / "conversation_summaries.db") as connection:
        connection.executescript((root / "conversation_summaries.sql").read_text())
    connection.close()
    return root


@pytest.fixture
def store(tmp_path):
    return build(tmp_path, STORE, "home")


@pytest.fixture
def stores(tmp_path):
    return {"index": build(tmp_path, STORE, "home"), "discovery": build(tmp_path, DISCOVERY, "discovery")}


def transcript(root, conversation):
    return root / "brain" / conversation / ".system_generated/logs/transcript_full.jsonl"


def request(root, conversation, *, size=None, state=None, text=True):
    path = transcript(root, conversation)
    info = path.stat()
    source = {"path": str(path), "size": info.st_size if size is None else size,
              "identity": {"device": info.st_dev, "inode": info.st_ino}}
    if state is not None:
        source["state"] = state
    return {"id": 1, "extract": "index", "cross_file": False, "text": text, "raw": False,
            "roots": [{"harness": "agy", "path": str(root / "brain")}], "files": [source]}


def decode(root, conversation, **kw):
    return list(index_stream.objects(request(root, conversation, **kw), ENVELOPE))


def events(out):
    return [o for o in out if o["object"] == "index_event"]


def by_line(out):
    return {e["line"]: e for e in events(out)}


def test_every_step_is_one_event_with_shared_position_and_identity(store):
    out = decode(store, H)
    assert [o["object"] for o in out] == (["file_start"] + ["index_event"] * 11
                                         + ["coverage", "file_end", "request_end"])
    start, end = out[0], out[-2]
    assert start["harness"] == "agy" and start["filename_identity"] is None
    facts = {"parent": None, "subagent": False, "cwd": "/w/alpha", "agent_name": ""}
    assert {k: start["path_facts"][k] for k in facts} == facts
    assert start["side_inputs"] == {"agy_conversation_summaries": hashlib.sha256(json.dumps(
        facts, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()}
    assert end["status"] == "ok" and end["restart"] is None and end["count"] == 12
    assert end["state"]["index"]["side_inputs"] == start["side_inputs"]
    offset = 0
    for event, raw in zip(events(out), transcript(store, H).read_bytes().splitlines(keepends=True)):
        assert event["key"] == f"E{offset}" and event["end"] == offset + len(raw)
        assert event["sha256"] == hashlib.sha256(raw).hexdigest()
        assert event["ref"] == f"agy:brain/{H}/.system_generated/logs/transcript_full.jsonl#L{event['line']}"
        assert event["identity"] == {"session": H, "index_session": H, "agent": None, "parent": None,
                                     "subagent": False, "cwd": "/w/alpha", "entrypoint": "agy", "version": None}
        assert event["eligible"] and event["at_ms"] is not None
        assert event["turn_end"] is None and event["fork_boundary"] is None
        offset += len(raw)


def test_user_input_keeps_the_request_body_and_reports_wrappers_as_injections(store):
    first, skill = by_line(decode(store, H))[1], by_line(decode(store, H))[10]
    assert first["native_kind"] == "USER_INPUT" and first["message"]["channel"] == "user"
    assert first["message"]["text"] == "Run the checks"
    assert first["message"]["origin"]["native_kind"] == "USER_EXPLICIT"
    assert [m["name"] for m in first["message"]["origin"]["markers"]] == [
        "USER_REQUEST", "ADDITIONAL_METADATA", "USER_SETTINGS_CHANGE"]
    assert [i["native_kind"] for i in first["injections"]] == [
        "agy_wrapper:ADDITIONAL_METADATA", "agy_wrapper:USER_SETTINGS_CHANGE"]
    assert all(i["bytes"] > 0 for i in first["injections"])
    assert skill["message"]["text"] == "/review the diff"
    assert [(c["kind"], c["skill"], c["native_name"]) for c in skill["calls"]] == [("skill", "review", "SKILL")]
    assert [i["native_kind"] for i in skill["injections"]] == ["agy_wrapper:SKILL"]


def test_planner_steps_are_complete_responses_with_agy_usage(store):
    planner = by_line(decode(store, H))[2]
    assert planner["flush_response"] is True
    assert planner["response"] == {
        "id": f"{H}:1", "model": "gemini-3-pro-high", "effort": None,
        "usage": {"input_uncached": 120, "cache_read": 4000, "cache_write": None, "output": 55,
                  "thinking": None, "context_total": 4120, "uncached_total": 120},
        "phase": "fragment",
        "usage_present": {"output": True, "thinking": False},  # presence flags are booleans
        "native": {"input_tokens": 120, "cache_read_tokens": 4000, "output_tokens": 55,
                   "thinking_text_bytes": len("Plan: list, read, edit.")}}
    assert planner["message"]["channel"] == "assistant" and planner["message"]["text"] == "Running the checks."
    assert "Plan" not in planner["message"]["text"]
    calls = planner["calls"]
    assert [(c["id"], c["native_name"], c["kind"], c["block"]) for c in calls] == [
        (f"{H}:1:0", "run_command", "shell", 0), (f"{H}:1:1", "read_file", "file_read", 1),
        (f"{H}:1:2", "edit_file", "file_edit", 2)]
    assert calls[0]["command"] == "just check" and calls[0]["background"] is None
    assert calls[1]["paths"] == ["/w/alpha/notes/todo.md"] and calls[1]["paths_complete"] is True
    assert calls[2]["paths"] == ["/w/alpha/README.md"] and calls[2]["raw_path"] == "/w/alpha/README.md"
    assert planner["message"]["assistant_output_bytes"] == len("Running the checks.") + sum(
        c["input_bytes"] for c in calls)
    assert by_line(decode(store, G))[3]["response"]["model"] is None  # model absent


def result(out, line):
    [only] = by_line(out)[line]["results"]
    return only


def test_results_pair_positionally_and_keep_exit_status_apart_from_error(store):
    out = decode(store, H)
    ok, read, failed = result(out, 3), result(out, 4), result(out, 5)
    assert (ok["call_id"], ok["error"], ok["exit_code"], ok["native_duration_ms"]) == (f"{H}:1:0", False, 0, 3000)
    assert ok["truncation"] is None
    # A read_file result quoting an exit line or the truncation sentence is neither.
    assert (read["call_id"], read["exit_code"], read["truncation"]) == (f"{H}:1:1", None, None)
    assert (failed["call_id"], failed["error"], failed["exit_code"]) == (f"{H}:1:2", True, None)
    nonzero = result(out, 7)
    assert (nonzero["call_id"], nonzero["error"], nonzero["exit_code"]) == (f"{H}:5:0", False, 2)
    assert nonzero["truncation"] == {"kind": "tool_preview", "original_tokens": None, "original_bytes": None}
    plain = result(out, 9)
    assert (plain["exit_code"], plain["truncation"]) == (None, None)  # "truncated" only in output
    for value in (ok, read, failed, nonzero, plain):
        assert value["interrupted"] is None and value["agent"] is None and value["background_id"] is None


def test_background_calls_report_through_notifications(store):
    out = by_line(decode(store, G))
    first, second = result(decode(store, G), 4), result(decode(store, G), 5)
    assert (first["call_id"], first["background_id"], first["native_duration_ms"]) == (f"{G}:2:0", f"{G}/task-1", None)
    assert (second["call_id"], second["background_id"]) == (f"{G}:2:1", f"{G}/task-2")
    assert all(c["background"] is None for c in out[3]["calls"])
    assert out[7]["notifications"] == [{"call_id": f"{G}:2:0", "status": "finished", "exit_code": 1}]
    assert out[8]["notifications"] == [{"call_id": f"{G}:2:1", "status": "canceled", "exit_code": None}]
    assert out[7]["injections"] == [] and out[9]["notifications"] == []
    assert [i["native_kind"] for i in out[9]["injections"]] == ["agy_system_message"]
    hook = out[2]
    assert hook["message"]["channel"] == "system"
    assert [(i["native_kind"], i["source"]) for i in hook["injections"]] == [("agy_hook_injection", "SessionStart hook")]


def test_checkpoint_surplus_unknown_and_interruption(store):
    out = decode(store, G)
    lines = by_line(out)
    checkpoint = lines[10]
    assert checkpoint["compaction"] == {"summary": True, "basis": "native", "rule": "agy_checkpoint"}
    assert checkpoint["response"]["id"] == f"{G}:9" and checkpoint["flush_response"] is True
    assert checkpoint["response"]["usage"]["input_uncached"] == 5000
    assert lines[11]["results"] == []  # surplus GENERIC: no call waiting
    assert [r["call_id"] for r in lines[13]["results"]] == [f"{G}:11:0"]  # second call unpaired
    unknown = lines[14]
    assert unknown["native_kind"] == "FUTURE_STEP" and unknown["message"] is None
    error = lines[15]
    assert error["message"]["text"] == "API error: The stream was interrupted"
    assert error["interruption"] == {"user_marker": False, "system": True, "basis": "convention",
                                     "rule": "agy_stream_interrupted"}
    coverage = next(o for o in out if o["object"] == "coverage")
    kinds = {(r["record_kind"], r["known"]) for r in coverage["records"]}
    assert ("FUTURE_STEP", 0) in kinds and ("GENERIC", 1) in kinds
    surplus = [f for f in coverage["fields"] if f["record_kind"] == "applied:result" and f["field"] == "input:call"]
    assert surplus and surplus[0]["seen"] - surplus[0]["present"] == 1


def test_subagent_identity_child_session_and_answers(store):
    out = decode(store, P)
    lines = by_line(out)
    assert all(e["identity"]["parent"] == G and e["identity"]["subagent"] is True for e in events(out))
    # A live subagent opens with the hook injection, then its parent's message: no user input.
    assert [(i["native_kind"], i["source"]) for i in lines[1]["injections"]] == [
        ("agy_hook_injection", "SessionStart hook")]
    assert lines[2]["message"]["channel"] == "system" and lines[2]["notifications"] == []
    assert [i["native_kind"] for i in lines[2]["injections"]] == ["agy_system_message"]
    assert all(e["message"] is None or e["message"]["channel"] != "user" for e in events(out))
    dispatch, question = lines[3]["calls"]
    assert (dispatch["kind"], dispatch["prompt"], question["kind"]) == ("dispatch", "Read the log", "question")
    assert dispatch["paths_complete"] is True  # as Claude's: complete when the prompt is present
    assert question["questions"] == [{"question": "Which suite?", "options": ["unit", "full"]}]
    assert result(out, 4)["child_session"] == Q
    assert result(out, 5)["answers"] == {"A1": "unit"}
    assert lines[6]["calls"][0]["kind"] == "question" and lines[6]["results"] == []


def test_an_answer_runs_to_the_next_answer_line(store):
    planner = {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
               "created_at": "2026-11-03T15:00:02Z", "tool_calls": [{"name": "ask_question", "args": {
                   "questions": [{"question": "Scope?"}, {"question": "When?"}]}}]}
    answer = {"step_index": 2, "source": "MODEL", "type": "GENERIC", "status": "DONE",
              "created_at": "2026-11-03T15:01:00Z",
              "content": ("Created At: 2026-11-03T10:00:02-05:00\nCompleted At: 2026-11-03T10:01:00-05:00\n"
                          "A1: both parts:\n\n- the reader\n- the index\nA2: today\n")}
    [_, paired] = extracted(store, [planner, answer])
    assert paired["results"][0]["answers"] == {"A1": "both parts:\n\n- the reader\n- the index", "A2": "today"}


def test_a_dispatch_without_a_prompt_has_incomplete_paths(store):
    planner = {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
               "created_at": "2026-11-03T15:00:02Z", "tool_calls": [{"name": "invoke_subagent", "args": {}}]}
    [event] = extracted(store, [planner])
    assert (event["calls"][0]["prompt"], event["calls"][0]["paths_complete"]) == (None, False)


def test_a_command_result_reads_its_exit_line_and_preview_only_before_its_output(store):
    planner = {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
               "created_at": "2026-11-03T15:00:02Z", "tool_calls": [{"name": "run_command", "args": {
                   "CommandLine": "cat log"}}]}
    quoted = {"step_index": 2, "source": "MODEL", "type": "GENERIC", "status": "DONE",
              "created_at": "2026-11-03T15:00:04Z",
              "content": ("Command exited with code 0.\n\nCommand output:\nCommand exited with code 3.\n"
                          "The tool's output was truncated due to being too long\n")}
    [_, paired] = extracted(store, [planner, quoted])
    assert (paired["results"][0]["exit_code"], paired["results"][0]["truncation"]) == (0, None)


def wake_up(index, at, sender, ended, text):
    content = (f"<SYSTEM_MESSAGE>\n[Message] timestamp={at} sender={sender} priority=MESSAGE_PRIORITY_HIGH"
               f" content=Task id \"{sender}\" {ended} with result:\n{text}\n</SYSTEM_MESSAGE>")
    step = {"step_index": index, "source": "SYSTEM", "type": "SYSTEM_MESSAGE", "status": "DONE", "content": content}
    return step if at is None else {**step, "created_at": at}


def background_start(store):
    planner = {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
               "created_at": "2026-11-03T15:00:02Z", "tool_calls": [
                   {"name": "run_command", "args": {"CommandLine": "a"}},
                   {"name": "run_command", "args": {"CommandLine": "b"}}]}
    running = [{"step_index": i, "source": "MODEL", "type": "GENERIC", "status": "RUNNING",
                "created_at": "2026-11-03T15:00:03Z",
                "content": f"Started a background task with task id: {H}/task-{i - 1}"} for i in (2, 3)]
    return [planner, *running]


def test_a_wake_up_quoting_another_message_reports_only_its_own_sender(store):
    quoting = wake_up(4, "2026-11-03T15:01:00Z", f"{H}/task-1", "finished",
                      f"[Message] sender={H}/task-2 content=Task id \"{H}/task-2\" was canceled with result:\nx")
    own = wake_up(5, "2026-11-03T15:02:00Z", f"{H}/task-2", "was canceled", "stopped")
    out = extracted(store, [*background_start(store), quoting, own])
    assert out[3]["notifications"] == [{"call_id": f"{H}:1:0", "status": "finished", "exit_code": None}]
    assert out[4]["notifications"] == [{"call_id": f"{H}:1:1", "status": "canceled", "exit_code": None}]


def test_an_ineligible_wake_up_still_closes_its_background_id(store):
    ineligible = wake_up(4, None, f"{H}/task-1", "finished", "done")
    repeated = wake_up(5, "2026-11-03T15:02:00Z", f"{H}/task-1", "finished", "done")
    out = extracted(store, [*background_start(store), ineligible, repeated])
    assert out[3]["eligible"] is False and out[4]["notifications"] == []


def test_results_after_an_ineligible_planner_are_counted_apart_from_surplus(store):
    planner = {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
               "created_at": "2026-11-03T15:00:02Z", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "a"}}]}
    generic = {"step_index": 2, "source": "MODEL", "type": "GENERIC", "status": "DONE",
               "created_at": "2026-11-03T15:00:03Z", "content": "Command exited with code 0.\n"}
    surplus = {**generic, "step_index": 3}
    unknown = {**planner, "step_index": 4}
    del unknown["created_at"]
    after = {**generic, "step_index": 5}
    from harness_evidence import discover
    from harness_evidence.index_adapters import ADAPTERS
    place = discover.place_of(transcript(store, H), discover.roots(explicit=[("agy", store / "brain")]))
    state = {}
    ADAPTERS["agy"].bind(state, ADAPTERS["agy"].path_facts(place))
    out = list(ADAPTERS["agy"].extract(raw_lines([planner, generic, surplus, unknown, after]), state,
                                       place=place, text=True))
    fields = {f["field"]: (f["seen"], f["present"]) for f in out[-1]["fields"] if f["record_kind"] == "applied:result"}
    assert fields["input:call"] == (3, 1)  # one paired, one surplus, one after the unknown calls
    assert fields["input:calls_known"] == (3, 2)


def test_a_constant_presence_flag_is_declared_by_convention_not_absent():
    from harness_evidence.index_adapters import ADAPTERS
    proof = ADAPTERS["agy"].provenance_defaults()["response.usage_present.thinking"]
    assert (proof["basis"], proof["native_paths"]) == ("convention", [])
    assert not proof["rule"].startswith("absent:")


def test_the_result_pairing_declares_its_calls_known_input():
    from harness_evidence.index_adapters import ADAPTERS
    keys = ADAPTERS["agy"].provenance_defaults()["results[].call_id"]["coverage_keys"]
    assert "applied:result/input:calls_known" in keys


INELIGIBLE = "b9000000-0000-4000-8000-0000000000f1"  # written by the test; no summary row


def test_resume_across_ineligible_steps_equals_a_full_decode(store):
    steps = [*background_start(store),
             {"step_index": 4, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
              "tool_calls": [{"name": "run_command", "args": {"CommandLine": "c"}}]},  # ineligible
             {"step_index": 5, "source": "MODEL", "type": "GENERIC", "status": "DONE",
              "created_at": "2026-11-03T15:00:05Z", "content": "Command exited with code 0.\n"},
             wake_up(6, None, f"{H}/task-1", "finished", "done"),
             wake_up(7, "2026-11-03T15:02:00Z", f"{H}/task-1", "finished", "done"),
             wake_up(8, "2026-11-03T15:03:00Z", f"{H}/task-2", "finished", "done")]
    path = transcript(store, INELIGIBLE)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"".join(raw for _, raw in raw_lines(steps)))
    full = decode(store, INELIGIBLE)
    assert by_line(full)[7]["notifications"] == []  # closed by the ineligible wake-up
    assert by_line(full)[8]["notifications"][0]["call_id"] == f"{INELIGIBLE}:1:1"
    data = path.read_bytes()
    for size in [i + 1 for i, byte in enumerate(data) if byte == ord("\n")]:
        first = decode(store, INELIGIBLE, size=size)
        second = decode(store, INELIGIBLE, state=first[-2]["state"])
        assert comparable(first) + comparable(second) == comparable(full), size
        assert second[-3] == {**full[-3], "file": second[-3]["file"]}


def test_the_adapter_declares_claudes_provenance_field_set():
    from harness_evidence.index_adapters import ADAPTERS
    assert ADAPTERS["agy"].PROVENANCE.keys() == ADAPTERS["claude-code"].PROVENANCE.keys()


def test_skill_calls_have_a_declared_tool_kind():
    from harness_evidence.index_adapters import ADAPTERS
    assert ADAPTERS["agy"].TOOL_KINDS["SKILL"] == "skill"


def test_the_layout_check_refuses_dot_segments(store):
    from harness_evidence.index_adapters import ADAPTERS
    from harness_evidence.lines import Place
    for relpath in ("brain/../.system_generated/logs/transcript_full.jsonl",):
        place = Place("agy", "agy", "personal", "live", relpath, store / relpath)
        assert ADAPTERS["agy"].refusal(place) is not None, relpath


def test_every_unwatched_declaration_is_read(stores):
    from harness_evidence.index_adapters import ADAPTERS
    adapter, reads = ADAPTERS["agy"], sample_reads(stores)
    unread = sorted((kind, path) for kind, paths in adapter.UNWATCHED.items() for path in paths
                    if (kind, path) not in reads)
    assert unread == []


def test_missing_row_malformed_line_and_partial_tail(store):
    out = decode(store, K)
    assert out[0]["path_facts"]["reason"] == "no_summary_row"
    event = events(out)[0]
    assert (event["identity"]["parent"], event["identity"]["subagent"], event["identity"]["cwd"]) == (None, None, None)
    defaults = out[0]["provenance_defaults"]
    # Unknown, not a declared absence: agy records these facts, the row is missing (spec §4.2).
    assert event["provenance"]["identity.cwd"] == {"native_paths": [], "rule": "unresolved:no_summary_row"}
    assert defaults["identity.cwd"]["rule"] == "agy_conversation_summaries"
    unparsed = [o for o in out if o["object"] == "unparsed"]
    assert [(u["line"], u["reason"], u["provisional"]) for u in unparsed] == [(2, "malformed", False),
                                                                             (4, "truncated", True)]
    coverage = next(o for o in out if o["object"] == "coverage")
    assert coverage["malformed"] == 1 and coverage["partial_tail"] is True


def test_missing_database_nulls_identity_without_a_heuristic(store):
    (store / "conversation_summaries.db").unlink()
    out = decode(store, H)
    assert out[0]["path_facts"]["reason"] == "summaries_unreadable"
    assert all(e["identity"]["subagent"] is None for e in events(out))


def test_text_off_drops_text_and_keeps_sizes(store):
    out = events(decode(store, H, text=False))
    assert all("text" not in (e["message"] or {}) for e in out)
    assert all("command" not in c and "prompt" not in c for e in out for c in e["calls"])
    assert all("answers" not in r for e in out for r in e["results"])
    assert all("source" not in i for e in out for i in e["injections"])
    assert all("cwd" not in e["identity"] for e in out)  # as Claude's text-off identity
    assert by_line(decode(store, H, text=False))[1]["message"]["joined_bytes"] == len("Run the checks")


def comparable(out):
    return [{k: v for k, v in o.items() if k not in ("file", "request")}
            for o in out if o["object"] in ("index_event", "unparsed")]


@pytest.mark.parametrize("name, conversation", SAMPLES)
def test_resume_from_every_line_boundary_equals_a_full_decode(stores, name, conversation):
    store = stores[name]
    full = decode(store, conversation)
    data = transcript(store, conversation).read_bytes()
    boundaries = [i + 1 for i, byte in enumerate(data) if byte == ord("\n")]
    for size in boundaries:
        first = decode(store, conversation, size=size)
        state = first[-2]["state"]
        second = decode(store, conversation, state=state)
        assert second[0]["replaces"] == {"from_line": state["next_line"]}
        assert comparable(first) + comparable(second) == comparable(full), (conversation, size)
        assert second[-3] == {**full[-3], "file": second[-3]["file"]}  # coverage over the whole file


def test_a_running_result_after_a_resume_needs_no_revision_of_the_call(store):
    data = transcript(store, G).read_bytes()
    through_planner = sum(len(line) for line in data.splitlines(keepends=True)[:3])
    first = decode(store, G, size=through_planner)
    call = by_line(first)[3]["calls"][0]
    second = decode(store, G, state=first[-2]["state"])
    running = by_line(second)[4]["results"][0]
    assert call["background"] is None and running["call_id"] == call["id"]
    assert running["background_id"] == f"{G}/task-1"
    assert by_line(second)[7]["notifications"][0]["call_id"] == call["id"]


def test_a_summary_row_added_between_decodes_restarts_from_line_one(store):
    first = decode(store, K)
    state = first[-2]["state"]
    with sqlite3.connect(store / "conversation_summaries.db") as connection:
        connection.execute("INSERT INTO conversation_summaries (conversation_id, last_modified_time, workspace_uris,"
                           " agent_name, parent_conversation_id, last_user_input_time)"
                           " VALUES (?, '2026-11-03 18:00:02', '[\"file:///w/kappa\"]', '', '', '2026-11-03 18:00:00')", (K,))
    connection.close()
    second = decode(store, K, state=state)
    assert second[0]["replaces"] == "all"
    assert second[0]["side_inputs"] != first[0]["side_inputs"]
    assert events(second)[0]["line"] == 1
    assert all(e["identity"]["cwd"] == "/w/kappa" and e["identity"]["subagent"] is False for e in events(second))


def test_one_decode_reads_the_database_once(store, monkeypatch):
    from harness_evidence import agy_summaries
    calls = []
    actual = agy_summaries.resolve

    def counted(database, conversation):
        calls.append(conversation)
        resolved = actual(database, conversation)
        # A second read in the same decode would see a different row.
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE conversation_summaries SET workspace_uris = '[\"file:///w/changed\"]'")
        connection.close()
        return resolved
    monkeypatch.setattr(agy_summaries, "resolve", counted)
    out = decode(store, H)
    assert calls == [H]
    assert out[0]["path_facts"]["cwd"] == "/w/alpha"
    assert all(e["identity"]["cwd"] == "/w/alpha" for e in events(out))


def test_every_event_proof_names_declared_fields_only(store):
    out = decode(store, G)
    defaults = out[0]["provenance_defaults"]
    from harness_evidence.index_adapters import ADAPTERS
    claude = ADAPTERS["claude-code"].provenance_defaults()
    assert defaults.keys() == claude.keys()  # one shared stream schema
    for field, proof in defaults.items():
        if not proof["native_paths"]:
            assert proof["rule"].startswith("absent:") or proof["basis"] == "convention", field
    for event in events(out):
        assert event["provenance"].keys() <= defaults.keys()


def numbered(data):
    offset = 0
    for raw in data.splitlines(keepends=True):
        yield offset, raw
        offset += len(raw)


def sample_reads(stores):
    """Every native read the extractor makes over the catalogued agy samples."""
    from harness_evidence import discover
    from harness_evidence.index_adapters import ADAPTERS
    from harness_evidence_index_tracing import traced_extract
    adapter, reads = ADAPTERS["agy"], set()
    for name, conversation in SAMPLES:
        store = stores[name]
        place = discover.place_of(transcript(store, conversation), discover.roots(explicit=[("agy", store / "brain")]))
        state = {}
        adapter.bind(state, adapter.path_facts(place))
        reads |= traced_extract(adapter, numbered(transcript(store, conversation).read_bytes()), state, place=place)
    return reads


def test_every_native_read_is_declared(stores):
    from harness_evidence.index_adapters import ADAPTERS
    from harness_evidence_index_tracing import covered, declared, feeds_valid, reasons_valid
    adapter = ADAPTERS["agy"]
    assert feeds_valid(adapter) == [] and reasons_valid(adapter) == []
    reads = sample_reads(stores)
    missing = sorted((kind, path) for kind, path in reads if not covered(path, declared(adapter, kind)))
    assert reads and missing == []


def test_capabilities_list_agy_absences_apart_from_conventions():
    from harness_evidence import capabilities
    from harness_evidence.index_adapters import ADAPTERS
    agy = json.loads(capabilities.ARTIFACT.read_text())["harnesses"]["agy"]
    defaults = ADAPTERS["agy"].provenance_defaults()
    absent = {f: p["rule"].removeprefix("absent:") for f, p in defaults.items() if p["rule"].startswith("absent:")}
    assert agy["index"]["absent"] == absent and "turn_end" in absent
    for field, entry in agy["fields"].items():
        if not entry["provenance"]:
            assert field in absent or defaults[field]["basis"] == "convention", field
    assert "identity.session" not in absent


def raw_lines(steps):
    offset, out = 0, []
    for step in steps:
        raw = (json.dumps(step) + "\n").encode()
        out.append((offset, raw))
        offset += len(raw)
    return out


def extracted(store, steps):
    from harness_evidence import discover
    from harness_evidence.index_adapters import ADAPTERS
    adapter = ADAPTERS["agy"]
    place = discover.place_of(transcript(store, H), discover.roots(explicit=[("agy", store / "brain")]))
    state = {}
    adapter.bind(state, adapter.path_facts(place))
    return [e for e in adapter.extract(raw_lines(steps), state, place=place, text=True)
            if e["object"] == "index_event"]


def test_each_catalogued_sample_decodes_to_its_expected_events(stores):
    import tomllib
    catalogue = tomllib.loads((TOOLS / "fixtures/session-logs/CATALOGUE.toml").read_text())["sample"]
    agy = [s for s in catalogue if s["harness"] == "agy" and s.get("profile") == "index"]
    assert sorted(s["path"].split("/")[4] for s in agy) == sorted(c for _, c in SAMPLES)
    for sample in agy:
        name = "index" if sample["path"].startswith("agy-index/") else "discovery"
        out = decode(stores[name], sample["path"].split("/")[4])
        found = events(out)
        assert [e["native_kind"] for e in found] == sample["index_events"], sample["path"]
        assert [o["reason"] for o in out if o["object"] == "unparsed"] == sample["unparsed"], sample["path"]
        for key in ("calls", "results", "notifications"):
            assert sum(len(e[key]) for e in found) == sample[key], (sample["path"], key)


def test_an_ineligible_step_keeps_its_place_in_the_pairing(store):
    planner = {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
               "created_at": "2026-11-03T15:00:02Z", "tool_calls": [
                   {"name": "run_command", "args": {"CommandLine": "true"}},
                   {"name": "read_file", "args": {"Path": "/w/a"}}]}
    broken = {"step_index": 2, "source": "MODEL", "type": "GENERIC", "status": "DONE",
              "content": "Command exited with code 0."}  # no created_at: ineligible
    read = {"step_index": 3, "source": "MODEL", "type": "GENERIC", "status": "DONE",
            "created_at": "2026-11-03T15:00:04Z", "content": "Command exited with code 7.\n"}
    events_ = extracted(store, [planner, broken, read])
    assert events_[1]["eligible"] is False and events_[1]["results"] == []
    [result_] = events_[2]["results"]
    assert result_["call_id"] == f"{H}:1:1" and result_["exit_code"] is None  # read_file, not run_command


def test_an_ineligible_planner_step_closes_the_earlier_calls(store):
    first = {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
             "created_at": "2026-11-03T15:00:02Z", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "a"}},
                                                                   {"name": "run_command", "args": {"CommandLine": "b"}}]}
    generic = {"step_index": 2, "source": "MODEL", "type": "GENERIC", "status": "DONE",
               "created_at": "2026-11-03T15:00:03Z", "content": "Command exited with code 0.\n"}
    second = {"step_index": 3, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
              "tool_calls": [{"name": "read_file", "args": {"Path": "/w/a"}}]}  # no created_at
    late = {**generic, "step_index": 4, "content": "Command exited with code 9.\n"}
    events_ = extracted(store, [first, generic, second, late])
    assert events_[1]["results"][0]["call_id"] == f"{H}:1:0"
    assert events_[3]["results"] == []  # the ineligible planner's calls are unknown; nothing is paired


def test_shared_index_additions_are_constant_and_declared(stores):
    from harness_evidence.index_adapters import ADAPTERS
    defaults = ADAPTERS["agy"].provenance_defaults()
    for field in ("context", "execution"):
        assert defaults[field] == {"native_paths": [], "coverage_keys": [],
                                   "basis": "native", "rule": "absent:not_recorded"}
    assert defaults["response.phase"] == {"native_paths": [], "coverage_keys": [],
                                          "basis": "convention", "rule": "agy_response_phase"}
    for group, conversation in SAMPLES:
        for event in events(decode(stores[group], conversation)):
            assert event["context"] is None
            assert event["execution"] == {"runs": [], "commands": [], "call_updates": [],
                                          "writes": [], "operations": [], "diagnostics": {}}
            if event["response"] is not None:
                assert event["response"]["phase"] == "fragment"
            assert not {"context", "execution", "response.phase"} & event["provenance"].keys()


def test_shared_additions_preserve_original_native_coverage(stores):
    # Captured from the exact index_agy.py at 57f5690c before shared constants were added.
    expected = {
        "a9000000-0000-4000-8000-0000000000a1": "e29f562bb2e2491cf44bcc94e194dababd7d08af2e4440b904996d9b0b4aacba",
        "a9000000-0000-4000-8000-0000000000b1": "29ae50861632bb71c66c53c906a930152cb296ca9980a11544f4851434871dc8",
        "a9000000-0000-4000-8000-0000000000c1": "0da31e88697d74a964f4be5b98b492b046ae6166295ce874f506f2dd36413e58",
        "b9000000-0000-4000-8000-000000000001": "513deda388119c7b4a149c59921306e3df912be718441e059c74fe579ad4bc58",
        "b9000000-0000-4000-8000-000000000002": "dfcfaa71e4663f239fd4c4d43ee4049f4edcc8365b3ca05818a9ced03b06cc37",
        "b9000000-0000-4000-8000-000000000003": "0d99b7830b498a449526da0ff27cf0e29a0d2c75c0618030093a8d714c2360f6",
        "b9000000-0000-4000-8000-000000000004": "ca0259629661b55bbc77b21bb5523b4e7ee482417595b437feb7c65f18681c21"
    }
    for group, conversation in SAMPLES:
        coverage = next(v for v in decode(stores[group], conversation) if v["object"] == "coverage")
        native = {key: coverage[key] for key in ("records", "fields", "malformed", "partial_tail")}
        digest = hashlib.sha256(json.dumps(native, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=True).encode()).hexdigest()
        assert digest == expected[conversation]


def test_shared_additions_preserve_original_agy_capability_block():
    from harness_evidence import capabilities
    agy = json.loads(capabilities.ARTIFACT.read_text())["harnesses"]["agy"]
    for field in ("context", "execution", "response.phase"):
        assert agy["fields"].pop(field) == {"coverage_keys": [], "provenance": []}
    for field in ("context", "execution"):
        assert agy["index"]["absent"].pop(field) == "not_recorded"
    # Entire immutable main57f5690c agy capability block, without only checked additions.
    digest = hashlib.sha256(json.dumps(agy, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=True).encode()).hexdigest()
    assert digest == "6814b8cb5ede33ebe0069b8a7c8d66882c9467a863c03be6cd57af30e0f9a16b"


def test_user_channel_origin_classification_is_published_and_unknown_kinds_stay_unclassified(store):
    from harness_evidence import capabilities, index_agy
    declaration = json.loads(capabilities.ARTIFACT.read_text())["harnesses"]["agy"]["index"]["origin_kinds"]
    assert declaration == {"USER_EXPLICIT": {"class": "user_typed", "basis": "native"}}
    assert declaration == index_agy.ORIGIN_KINDS
    # The adapter passes arbitrary native source strings through. Every other value is
    # deliberately unclassified, including values introduced by a future writer.
    path = transcript(store, H)
    base = json.loads(path.read_text().splitlines()[0])
    for source in ("USER_EXPLICIT", "SYSTEM", "USER_DERIVED", "future-origin", None):
        value = dict(base, source=source)
        path.write_text(json.dumps(value) + "\n")
        [only] = events(decode(store, H))
        kind = only["message"]["origin"]["native_kind"]
        assert kind == str(source)
        classified = declaration.get(kind)
        if source == "USER_EXPLICIT":
            assert classified == {"class": "user_typed", "basis": "native"}
        else:
            assert classified is None  # Deliberate unclassified default, never user_typed.
    assert "origin_kinds" not in json.loads(capabilities.ARTIFACT.read_text())["harnesses"]["claude-code"]["index"]
