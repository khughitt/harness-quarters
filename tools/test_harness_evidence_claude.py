import json
import tempfile
import unittest
from pathlib import Path

from harness_evidence import records as rec
from harness_evidence_testing import FIXTURES, PATHS, ref_of
from harness_evidence.lines import Place

CA_ID = "c0000000-0000-4000-8000-00000000000a"
BASES = {"origin", "local_command", "prefix_rule", "agent_path", "structure", "kind"}


def fixture_place(short):
    _fixture, dot, under = PATHS[short].split("/", 2)
    home = dot[1:]
    profile = "work" if home.endswith("-work") else "personal"
    return Place("claude-code", home, profile, "live", under, FIXTURES / PATHS[short])


def read_fixture(short):
    place = fixture_place(short)
    return rec.claude_read(place, place.path.stat().st_size)


def by_ref(read):
    return {r["ref"]: r for r in read.records}


def at_line(read, line):
    return [r for r in read.records if r["line"] == line]


class InlineFiles(unittest.TestCase):
    def read_inline(self, rows, name="c0000000-0000-4000-8000-0000000000ff.jsonl",
                    sub="projects/-w-x", tail=b""):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / sub / name
        path.parent.mkdir(parents=True)
        data = b"".join(json.dumps(row).encode() + b"\n" for row in rows) + tail
        path.write_bytes(data)
        place = Place("claude-code", "claude", "personal", "live", f"{sub}/{name}", path)
        return rec.claude_read(place, len(data))


def user(content, **extra):
    return {"type": "user", "sessionId": "c0000000-0000-4000-8000-0000000000ff",
            "timestamp": "2026-10-12T09:00:00.000Z", "message": {"role": "user", "content": content},
            **extra}


def system(subtype, **extra):
    return {"type": "system", "subtype": subtype, "sessionId": "c0000000-0000-4000-8000-0000000000ff",
            "timestamp": "2026-10-12T09:00:00.000Z", **extra}


def assistant(msg_id, blocks, model="claude-model-a", **extra):
    return {"type": "assistant", "sessionId": "c0000000-0000-4000-8000-0000000000ff",
            "timestamp": "2026-10-12T09:00:01.000Z",
            "message": {"id": msg_id, "model": model, "role": "assistant", "content": blocks,
                        "stop_reason": "end_turn"}, **extra}


class CaTest(unittest.TestCase):
    def test_ca_roles_by_origin(self):
        read = read_fixture("CA")
        got = by_ref(read)
        humans = [r["ref"] for r in read.records if r["role"] == "human"]
        self.assertEqual(humans, [ref_of("CA:1"), ref_of("CA:15")])
        for short in ("CA:1", "CA:15"):
            self.assertEqual(got[ref_of(short)]["role_basis"], "origin")
        self.assertEqual(got[ref_of("CA:2")]["role"], "injected")
        self.assertEqual(got[ref_of("CA:2")]["role_basis"], "structure")
        self.assertEqual(got[ref_of("CA:14")]["role"], "injected")
        self.assertEqual(got[ref_of("CA:14")]["origin_kind"], "task-notification")
        self.assertEqual(got[ref_of("CA:13")]["role"], "metadata")
        self.assertEqual(got[ref_of("CA:16")]["role"], "unknown")
        self.assertEqual(got[ref_of("CA:16")]["kind"], "future-record-kind")
        self.assertEqual(got[ref_of("CA:16")]["role_basis"], "kind")
        self.assertEqual(got[ref_of("CA:1")]["prompt_source"], "typed")
        self.assertNotIn("prompt_source", got[ref_of("CA:15")])

    def test_ca_identity_is_the_file_name_not_session_id(self):
        read = read_fixture("CA")
        self.assertEqual(read.header["session"], CA_ID)
        self.assertEqual(read.header["identity_basis"], "file_name")
        self.assertFalse(read.header["subagent"])
        self.assertIsNone(read.header["parent"])
        self.assertEqual({r["session"] for r in read.records}, {CA_ID})
        self.assertTrue(all("agent" not in r for r in read.records))
        self.assertEqual(read.header["cwd"], "/w/alpha")
        self.assertEqual(read.header["entrypoint"], "cli")
        self.assertEqual(read.header["first_at"], "2026-10-08T12:00:00.000Z")
        self.assertEqual(read.header["last_at"], "2026-10-08T12:04:05.000Z")
        self.assertEqual(read.header["lines"], 19)
        self.assertEqual(read.header["uuids"]["u-a15"], 15)
        self.assertFalse(read.header["markers"])
        self.assertFalse(read.header["forked"])
        self.assertIsNone(read.header["continued_in"])

    def test_ca_calls_pair_by_id_across_reversed_results(self):
        read = read_fixture("CA")
        rec.pair_calls(read.records)
        pairs = {r["ref"]: r["call"]["peer"] for r in read.records
                 if r["role"] == "tool_call" and r["call"].get("peer")}
        expected = {"CA:4#0": "CA:7#0", "CA:5#0": "CA:6#0", "CA:8#0": "CA:9#0",
                    "CA:11#0": "CA:12#0", "CA:17#0": "CA:18#0"}
        self.assertEqual(pairs, {ref_of(k): ref_of(v) for k, v in expected.items()})
        results = {r["ref"]: r["call"]["peer"] for r in read.records if r["role"] == "tool_output"
                   and "copy" not in r}
        self.assertEqual(results, {ref_of(v): ref_of(k) for k, v in expected.items()})
        got = by_ref(read)
        self.assertTrue(got[ref_of("CA:7#0")]["call"]["is_error"])
        self.assertFalse(got[ref_of("CA:6#0")]["call"]["is_error"])
        self.assertEqual(got[ref_of("CA:4#0")]["call"]["command"], "tasks park zz-000001 'review next'")
        self.assertEqual(got[ref_of("CA:4#0")]["call"]["tool"], "Bash")
        self.assertNotIn("command", got[ref_of("CA:11#0")]["call"])
        self.assertTrue(all("status" not in r["call"] for r in read.records if "call" in r))

    def test_ca_request_blob_blocks_are_copies(self):
        read = read_fixture("CA")
        blob = at_line(read, 10)
        self.assertEqual(len(blob), 3)
        self.assertTrue(all(r["copy"] == "request_blob" for r in blob))
        self.assertTrue(all(r["at"] is None for r in blob))
        self.assertEqual([r["role"] for r in blob], ["assistant", "tool_call", "tool_call"])
        self.assertEqual([r["call"]["id"] for r in blob[1:]], ["toolu_fx_park1", "toolu_fx_status"])
        self.assertEqual([r["ref"] for r in blob[1:]], [ref_of("CA:10#1"), ref_of("CA:10#2")])
        self.assertTrue(all(r["call"]["peer"] is None for r in blob[1:]))
        self.assertTrue(all(r["_flags"] == frozenset() for r in blob))

    def test_ca_message_and_runtime_model(self):
        read = read_fixture("CA")
        self.assertEqual({r["message_id"] for line in (3, 4, 5) for r in at_line(read, line)},
                         {"msg_fx_m1"})
        assistants = [r for r in read.records if r["kind"] == "assistant"]
        self.assertEqual(len(assistants), 7)
        for r in assistants:
            self.assertEqual(r["model"], {"value": "claude-model-a", "basis": "runtime"})
            self.assertNotIn("synthetic", r)

    def test_ca_model_bases_in_header(self):
        models = read_fixture("CA").header["models"]
        self.assertIn({"value": "claude-model-a", "basis": "runtime", "ref": ref_of("CA:3")}, models)
        self.assertIn({"value": "claude-model-a", "basis": "requested", "ref": ref_of("CA:3")}, models)
        self.assertIn({"value": "sonnet", "basis": "requested", "ref": ref_of("CA:11#0")}, models)
        self.assertIn({"value": "claude-model-b", "basis": "resolved", "ref": ref_of("CA:12")}, models)
        self.assertEqual(len(models), 4)

    def test_record_shape(self):
        read = read_fixture("CA")
        got = by_ref(read)
        one = got[ref_of("CA:1")]
        self.assertEqual(one["type"], "record")
        self.assertEqual((one["harness"], one["home"], one["profile"], one["store"]),
                         ("claude-code", "claude", "personal", "live"))
        self.assertEqual(one["line"], 1)
        self.assertNotIn("block", one)
        self.assertEqual(one["at"], "2026-10-08T12:00:00.000Z")
        self.assertEqual(one["text"], "Please park zz-000001 and dispatch a reviewer for it.")
        self.assertEqual(len(one["sha256"]), 64)
        call = got[ref_of("CA:4#0")]
        self.assertEqual(call["block"], 0)
        self.assertEqual(call["block_type"], "tool_use")
        self.assertIn("tasks park zz-000001 'review next'", call["text"])
        self.assertEqual(got[ref_of("CA:12#0")]["text"], "Async agent launched successfully.")
        self.assertEqual(got[ref_of("CA:3#0")]["stop_reason"], "tool_use")
        self.assertIn('"future-record-kind"', got[ref_of("CA:16")]["text"])
        for r in read.records:
            self.assertIn(r["role_basis"], BASES)
            self.assertNotIn("turn", r)


class SubagentTest(unittest.TestCase):
    def test_subagent_prompt_is_dispatch_and_identity_is_agent(self):
        read = read_fixture("AG")
        got = by_ref(read)
        first = got[ref_of("AG:1")]
        self.assertEqual(first["role"], "dispatch")
        self.assertEqual(first["role_basis"], "structure")
        self.assertEqual(read.header["session"], "agent-a0000000000000b01")
        self.assertEqual(read.header["agent"], "a0000000000000b01")
        self.assertEqual(read.header["identity_basis"], "agent_id")
        self.assertTrue(read.header["subagent"])
        self.assertEqual(read.header["parent"], CA_ID)
        self.assertEqual({r["session"] for r in read.records}, {"agent-a0000000000000b01"})
        self.assertEqual({r["agent"] for r in read.records}, {"a0000000000000b01"})
        self.assertFalse(any(r["role"] == "human" for r in read.records))
        self.assertEqual(got[ref_of("AG:2#0")]["model"], {"value": "claude-model-b", "basis": "runtime"})


class InlineTest(InlineFiles):
    def test_local_command_shapes_in_both_record_types(self):
        inputs = ["<command-name>/model</command-name>", "<bash-input>ls</bash-input>"]
        outputs = ["<local-command-stdout>ok</local-command-stdout>",
                   "<local-command-stderr>no</local-command-stderr>",
                   "<bash-stdout>a</bash-stdout>", "<bash-stderr>b</bash-stderr>"]
        rows = []
        for text in inputs + outputs:
            rows.append(user(text))
            rows.append(system("local_command", content=text, level="info"))
        read = self.read_inline(rows)
        self.assertEqual(len(read.records), len(rows))
        for r in read.records:
            self.assertEqual(r["role_basis"], "local_command")
        for r in read.records[:2 * len(inputs)]:
            self.assertEqual(r["role"], "human", r)
            self.assertIn("local_input", r["_flags"])
        for r in read.records[2 * len(inputs):]:
            self.assertEqual(r["role"], "injected", r)
            self.assertIn("local_output", r["_flags"])
        self.assertEqual(read.records[1]["kind"], "system/local_command")
        self.assertIn("prompt", read.records[0]["_flags"])
        self.assertNotIn("prompt", read.records[1]["_flags"])

    def test_prefix_rule_and_interrupt_marker_without_origin(self):
        read = self.read_inline([
            user("plain old prompt"),
            user("<system-reminder>x</system-reminder>"),
            user("<pasted_content>p</pasted_content>"),
            user([{"type": "text", "text": "[Request interrupted by user]"}]),
            user("hi", origin={"kind": "human"}, isMeta=True),
            user("summary", isCompactSummary=True),
        ])
        got = [(r["role"], r["role_basis"]) for r in read.records]
        self.assertEqual(got, [("human", "prefix_rule"), ("injected", "prefix_rule"),
                               ("human", "prefix_rule"), ("injected", "structure"),
                               ("injected", "structure"), ("injected", "structure")])
        self.assertIn("interrupt_marker", read.records[3]["_flags"])
        self.assertEqual(read.records[3]["block"], 0)
        self.assertIn("isCompactSummary", read.records[5]["_flags"])

    def test_queued_attachment_takes_its_origin_kind(self):
        def queued(kind):
            return {"type": "attachment", "sessionId": "c0000000-0000-4000-8000-0000000000ff",
                    "timestamp": "2026-10-12T09:00:00.000Z",
                    "attachment": {"type": "queued_command", "prompt": f"from {kind}",
                                   "origin": {"kind": kind}}}
        other = {"type": "attachment", "sessionId": "c0000000-0000-4000-8000-0000000000ff",
                 "attachment": {"type": "hook_blocking_error", "hookName": "Stop"}}
        read = self.read_inline([queued("human"), queued("task-notification"), other])
        human, injected, rest = read.records
        self.assertEqual((human["role"], human["role_basis"], human["queued"]), ("human", "origin", True))
        self.assertEqual(human["kind"], "attachment/queued_command")
        self.assertEqual(human["text"], "from human")
        self.assertIn("queued", human["_flags"])
        self.assertEqual((injected["role"], injected["origin_kind"]), ("injected", "task-notification"))
        self.assertNotIn("queued", injected)
        self.assertEqual((rest["role"], rest["role_basis"]), ("injected", "structure"))
        self.assertEqual(rest["at"], None)

    def test_synthetic_message_is_marked_and_not_runtime(self):
        read = self.read_inline([assistant("msg_s", [{"type": "text", "text": "No response requested."}],
                                           model="<synthetic>")])
        (r,) = read.records
        self.assertEqual(r["role"], "assistant")
        self.assertTrue(r["synthetic"])
        self.assertNotIn("model", r)
        self.assertEqual(read.header["models"], [])

    def test_fork_context_ref_marks_first_response_as_fork_history(self):
        read = self.read_inline([
            {"type": "fork-context-ref", "sessionId": "c0000000-0000-4000-8000-0000000000ff"},
            user("Do the forked part."),
            assistant("msg_parent", [{"type": "text", "text": "Launching."}]),
            assistant("msg_parent", [{"type": "tool_use", "id": "toolu_launch", "name": "Agent",
                                      "input": {"prompt": "p"}}]),
            assistant("msg_own", [{"type": "text", "text": "Doing it."}]),
        ])
        self.assertTrue(read.header["forked"])
        self.assertEqual([r.get("copy") for r in read.records],
                         [None, None, "fork_history", "fork_history", None])
        self.assertEqual(read.records[0]["role"], "metadata")
        self.assertNotIn("status", read.records[3]["call"])

    def test_huge_output_is_cut_and_measured(self):
        big = "x" * 5_000_000
        read = self.read_inline([user([{"type": "tool_result", "tool_use_id": "toolu_big",
                                        "content": big}])])
        (r,) = read.records
        self.assertEqual(r["role"], "tool_output")
        text, size, truncated = rec.cut(r["text"], 2000)
        self.assertTrue(truncated)
        self.assertLessEqual(len(text.encode()), 2000)
        self.assertEqual(size, 5_000_000)

    def test_cut_keeps_whole_characters(self):
        self.assertEqual(rec.cut("aé", 2), ("a", 3, True))
        self.assertEqual(rec.cut("aé", 3), ("aé", 3, False))

    def test_cut_replaces_lone_surrogates(self):
        """R38: a lone surrogate (valid JSON as a `\\ud800` escape, which `json` decodes
        alone) never crashes cut(): each becomes one U+FFFD, in the text and its length."""
        self.assertEqual(rec.cut("a\ud800b", 10), ("a\ufffdb", 5, False))
        self.assertEqual(rec.cut("\udfff\ud800x", 4), ("\ufffd", 7, True))

    def test_malformed_and_truncated_lines_are_unparsed(self):
        place = fixture_place("CD")
        read = rec.claude_read(place, place.path.stat().st_size)
        self.assertEqual([(u["type"], u["ref"], u["reason"]) for u in read.unparsed],
                         [("unparsed", ref_of("CD:2"), "malformed")])
        self.assertTrue(read.unparsed[0]["_raw"].startswith('{"type":"assistant"'))
        self.assertEqual([r["line"] for r in read.records], [1, 3])
        partial = self.read_inline([user("first")], tail=b'{"type":"user","message":{"content":"ha')
        self.assertEqual([u["reason"] for u in partial.unparsed], ["truncated"])
        self.assertEqual(partial.unparsed[0]["_line"], 2)
        self.assertTrue(partial.unparsed[0]["ref"].endswith("#L2"))
        self.assertEqual(partial.header["lines"], 2)

    def test_pending_calls_and_unpaired_results(self):
        read = self.read_inline([
            assistant("m1", [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}]),
            user([{"type": "tool_result", "tool_use_id": "t9", "content": [{"type": "text", "text": "a"}]}]),
        ])
        call, result = read.records
        self.assertEqual(call["call"]["status"], "pending")
        self.assertIsNone(call["call"]["peer"])
        self.assertIsNone(result["call"]["peer"])
        self.assertFalse(result["call"]["is_error"])


class FollowUpTest(InlineFiles):
    """Step-3 review follow-ups: odd values, the interrupt marker, call ids, copy models."""

    def test_odd_values_do_not_abort_a_read(self):
        read = self.read_inline([
            {"type": ["user"], "sessionId": "c0000000-0000-4000-8000-0000000000ff"},
            {"type": {"k": 1}, "sessionId": "c0000000-0000-4000-8000-0000000000ff"},
            user([{"type": "text", "text": {"not": "a string"}}, {"type": ["text"], "text": "x"}]),
            user({"content": "neither a string nor a list"}),
            assistant("m1", [{"type": "text", "text": 5}, {"type": "thinking", "thinking": ["t"]},
                             {"type": "tool_use", "id": "t1", "name": ["Agent"], "input": {"model": 3}}]),
            system(["odd"], content=7),
            {"type": "attachment", "sessionId": "c0000000-0000-4000-8000-0000000000ff",
             "attachment": {"type": ["queued_command"], "prompt": 4}},
            user("blank time", timestamp=""),
            user("x", timestamp=12),
        ])
        self.assertEqual(read.unparsed, [])
        self.assertEqual(len(read.records), 12)
        self.assertEqual(read.header["first_at"], "2026-10-12T09:00:00.000Z")
        for r in read.records:
            self.assertIsInstance(r.get("text", ""), str, r["ref"])
            self.assertIn(r["role_basis"], BASES)
        first, second = read.records[:2]
        self.assertEqual((first["role"], first["kind"]), ("unknown", None))
        self.assertEqual((second["role"], second["kind"]), ("unknown", None))
        self.assertEqual(read.records[2]["text"], "")
        self.assertEqual(read.records[2]["role"], "human")
        self.assertNotIn("block_type", read.records[3])
        self.assertEqual([r["text"] for r in read.records[5:7]], ["", ""])
        self.assertIsNone(read.records[7]["call"]["tool"])  # a tool name is a string or nothing
        self.assertIsNone(read.records[-1]["at"])

    def test_interrupt_marker_wins_over_human_origin(self):
        read = self.read_inline([
            user("[Request interrupted by user]", origin={"kind": "human"}),
            user([{"type": "text", "text": "[Request interrupted by user for tool use]"}],
                 origin={"kind": "task-notification"}),
        ])
        for r in read.records:
            self.assertEqual((r["role"], r["role_basis"]), ("injected", "structure"), r["ref"])
            self.assertIn("interrupt_marker", r["_flags"])

    def test_pair_calls_pairs_string_ids_and_marks_duplicates(self):
        read = self.read_inline([
            assistant("m1", [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "a"}}]),
            assistant("m2", [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "b"}}]),
            assistant("m3", [{"type": "tool_use", "name": "Bash", "input": {"command": "c"}}]),
            assistant("m4", [{"type": "tool_use", "id": 7, "name": "Bash", "input": {"command": "d"}}]),
            user([{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]),
            user([{"type": "tool_result", "tool_use_id": "t1", "content": "again"}]),
            user([{"type": "tool_result", "content": "no id"}]),
        ])
        first, again, no_id, int_id, result, result_again, result_no_id = read.records
        self.assertEqual(first["call"]["peer"], result["ref"])
        self.assertEqual(result["call"]["peer"], first["ref"])
        self.assertNotIn("status", first["call"])
        for r in (again, result_again):
            self.assertEqual(r["call"]["status"], "duplicate_id", r["ref"])
            self.assertIsNone(r["call"]["peer"])
        for r in (no_id, int_id, result_no_id):
            self.assertEqual(r["call"]["status"], "no_id", r["ref"])
            self.assertIsNone(r["call"]["peer"])
        rec.pair_calls(read.records)  # idempotent
        self.assertEqual(again["call"]["status"], "duplicate_id")
        self.assertEqual(first["call"]["peer"], result["ref"])

    def test_copy_requested_model_stays_out_of_header(self):
        read = self.read_inline([
            {"type": "fork-context-ref", "sessionId": "c0000000-0000-4000-8000-0000000000ff"},
            user("Do the forked part."),
            assistant("msg_parent", [{"type": "text", "text": "Launching."}],
                      requestedModel="parent-requested"),
            assistant("msg_own", [{"type": "text", "text": "Doing it."}], requestedModel="own-requested"),
            {"type": "api-request-blob", "requestedModel": "blob-requested",
             "message": {"role": "user", "content": [{"type": "text", "text": "x"}]}},
        ])
        self.assertEqual(read.records[2]["copy"], "fork_history")
        values = {(m["value"], m["basis"]) for m in read.header["models"]}
        self.assertIn(("own-requested", "requested"), values)
        self.assertNotIn(("parent-requested", "requested"), values)
        self.assertNotIn(("blob-requested", "requested"), values)


class StepSixFollowUpTest(InlineFiles):
    """Step-4 review follow-ups and the facts step 6 links and copies read."""

    def test_launch_result_agent_and_continued_in_are_kept(self):
        ca = by_ref(read_fixture("CA"))
        self.assertEqual(ca[ref_of("CA:12#0")]["_launched_agent"], "a0000000000000b01")
        self.assertNotIn("_launched_agent", ca[ref_of("CA:11#0")])
        read = self.read_inline([
            user("hi"),
            {"type": "continued-in", "sessionId": "c0000000-0000-4000-8000-0000000000ff",
             "continuedInSessionId": "c0000000-0000-4000-8000-0000000000ee"},
            {"type": "continued-in", "continuedInSessionId": 5},
        ])
        self.assertEqual(read.records[1]["_continued_in"], "c0000000-0000-4000-8000-0000000000ee")
        self.assertNotIn("_continued_in", read.records[2])

    def test_every_model_occurrence_is_kept_for_relocation(self):
        read = self.read_inline([
            assistant("m1", [{"type": "text", "text": "a"}]),
            assistant("m2", [{"type": "text", "text": "b"}]),
        ])
        self.assertEqual(read.header["models"], [
            {"value": "claude-model-a", "basis": "runtime", "ref": read.records[0]["ref"][:-2]}])
        self.assertEqual(read.header["_model_refs"][("claude-model-a", "runtime")],
                         [(read.records[0]["ref"][:-2], 1), (read.records[1]["ref"][:-2], 2)])
        self.assertNotIn("model_refs", read.header)  # tuple keys: private, never emitted


class NativeFlagsTest(unittest.TestCase):
    def test_native_flags_reach_the_turn_parser(self):
        ca = by_ref(read_fixture("CA"))
        self.assertIn("isMeta", ca[ref_of("CA:2")]["_flags"])
        self.assertIn("prompt", ca[ref_of("CA:1")]["_flags"])
        self.assertIn("tool_result", ca[ref_of("CA:6#0")]["_flags"])
        self.assertNotIn("prompt", ca[ref_of("CA:6#0")]["_flags"])
        cm_read = read_fixture("CM")
        cm = by_ref(cm_read)
        self.assertTrue(cm_read.header["markers"])
        feedback = cm[ref_of("CM:24")]
        self.assertTrue({"isMeta", "prompt"} <= feedback["_flags"])
        self.assertEqual(feedback["role"], "injected")
        self.assertEqual(cm[ref_of("CM:25")]["role"], "injected")
        summaries = [r for r in cm_read.records if r["kind"] == "system/stop_hook_summary"]
        self.assertEqual(len(summaries), 9)
        for r in summaries:
            self.assertEqual(r["role"], "metadata")
            want = "stop_hook_blocked" if r["ref"] == ref_of("CM:26") else "stop_hook_ok"
            self.assertIn(want, r["_flags"], r["ref"])
        durations = [r for r in cm_read.records if "turn_duration" in r["_flags"]]
        self.assertEqual(len(durations), 9)
        skill = cm[ref_of("CM:35#0")]
        self.assertEqual(skill["role"], "injected")
        self.assertEqual(skill["_source_tool_use_id"], cm[ref_of("CM:33#0")]["call"]["id"])
        self.assertEqual(skill["_source_tool_use_id"], "toolu_fx_cm5")
        self.assertEqual(skill["_prompt_id"], cm[ref_of("CM:32")]["_prompt_id"])
        self.assertIn("isMeta", skill["_flags"])
        self.assertIn("local_input", cm[ref_of("CM:9")]["_flags"])
        self.assertEqual(cm[ref_of("CM:9")]["role"], "human")
        self.assertIn("local_output", cm[ref_of("CM:10")]["_flags"])
        self.assertEqual(cm[ref_of("CM:10")]["role"], "injected")
        queued = cm[ref_of("CM:18")]
        self.assertIn("queued", queued["_flags"])
        self.assertEqual((queued["role"], queued["queued"]), ("human", True))
        for short in ("CM:52#0", "CM:54#0"):
            self.assertEqual(cm[ref_of(short)]["role"], "injected")
            self.assertIn("interrupt_marker", cm[ref_of(short)]["_flags"])
        self.assertEqual(cm[ref_of("CM:39")]["role"], "metadata")
        self.assertEqual(cm[ref_of("CM:40")]["role"], "injected")
        self.assertEqual((cm[ref_of("CM:44")]["role"], cm[ref_of("CM:44")]["origin_kind"]),
                         ("injected", "peer"))
        self.assertTrue(cm[ref_of("CM:58#0")]["synthetic"])
        self.assertNotIn("model", cm[ref_of("CM:58#0")])
        for short in ("CM:56#0", "CM:65#0"):
            self.assertEqual(cm[ref_of(short)]["call"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
