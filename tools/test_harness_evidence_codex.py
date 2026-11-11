import json
import tempfile
import unittest
from pathlib import Path

from harness_evidence import records as rec
from harness_evidence_testing import CAPTURES, FIXTURES, PATHS, no_parent, ref_of
from harness_evidence.lines import Place

def meta(thread, parent=None, agent_path=None, thread_source=None, **extra):
    payload = {"id": thread, "session_id": thread, "cwd": "/w/x", "cli_version": "0.164.0",
               "base_instructions": {"provenance": {"type": "model", "model": "creation-model"}}}
    if parent is not None or agent_path is not None:
        spawn = {"depth": 1}
        if parent is not None:
            spawn["parent_thread_id"] = parent
        if agent_path is not None:
            spawn["agent_path"] = agent_path
        payload["source"] = {"subagent": {"thread_spawn": spawn}}
        payload["thread_source"] = "subagent"
    else:
        payload["source"] = "cli"
        payload["thread_source"] = "user"
    if thread_source is not None:
        payload["thread_source"] = thread_source
    payload.update(extra)
    return {"timestamp": "2026-10-12T10:00:00.000Z", "type": "session_meta", "payload": payload}


def event(kind, **payload):
    return {"timestamp": "2026-10-12T10:00:01.000Z", "type": "event_msg",
            "payload": {"type": kind, **payload}}


def started(turn):
    return event("task_started", turn_id=turn)


def complete(turn, last="done"):
    return event("task_complete", turn_id=turn, last_agent_message=last)


def item(kind, **body):
    return {"timestamp": "2026-10-12T10:00:02.000Z", "type": "response_item",
            "payload": {"type": kind, **body}}


def message(role, text, **extra):
    block = "output_text" if role == "assistant" else "input_text"
    return item("message", role=role, content=[{"type": block, "text": text}], **extra)


class InlineRollouts(unittest.TestCase):
    def write(self, rows, name="rollout-2026-10-12T10-00-00-01900000-0000-7000-8000-0000000000ff.jsonl"):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        sub = "sessions/2026/10/12"
        path = Path(d.name) / sub / name
        path.parent.mkdir(parents=True)
        data = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
        path.write_bytes(data)
        return Place("codex", "codex", "personal", "live", f"{sub}/{name}", path), len(data)

    def read_inline(self, rows, inherited=no_parent, **kw):
        place, size = self.write(rows, **kw)
        return rec.codex_read(place, size, inherited)


XP_ID = "01900000-0000-7000-8000-0000000000a1"
XC_ID = "01900000-0000-7000-8000-0000000000c1"
XG_ID = "01900000-0000-7000-8000-0000000000c2"
XK_ID = "01900000-0000-7000-8000-0000000000f2"
XK_INHERITED = "01900000-0000-7000-8000-0000000000f9"
BASES = {"origin", "local_command", "prefix_rule", "agent_path", "structure", "kind"}
# envelope, in field order, for a whole record (no `block`, no `agent`).
ENVELOPE = ["type", "ref", "sha256", "line", "harness", "home", "profile", "store", "session",
            "at", "role", "role_basis", "kind"]


def codex_place(short):
    _fixture, dot, under = PATHS[short].split("/", 2)
    home = dot[1:]
    profile = "work" if home.endswith("-work") else "personal"
    store = "archived" if "/archived_sessions/" in f"/{under}" else "live"
    return Place("codex", home, profile, store, under, FIXTURES / PATHS[short])


def read_codex(short, inherited=no_parent):
    place = codex_place(short)
    return rec.codex_read(place, place.path.stat().st_size, inherited)


def by_ref(read):
    return {r["ref"]: r for r in read.records}


def at_line(read, line):
    return [r for r in read.records if r["line"] == line]


# -- inline rollouts -----------------------------------------------------------------------

def context(turn, model="runtime-model"):
    return {"timestamp": "2026-10-12T10:00:01.000Z", "type": "turn_context",
            "payload": {"turn_id": turn, "model": model}}


def agent_message(author, text, recipient="/root/x"):
    return item("agent_message", author=author, recipient=recipient,
                content=[{"type": "input_text", "text": text}])


def completed(kind, **body):
    return event("item_completed", thread_id="t", turn_id="u", item={"type": kind, **body})


def turn(turn_id, prompt="do it", answer="done"):
    return [started(turn_id), context(turn_id), message("user", prompt),
            message("assistant", answer, phase="final_answer"), complete(turn_id, answer)]


# -- fixtures --------------------------------------------------------------------------------

class FixtureTest(unittest.TestCase):
    def test_xc_identity_and_models(self):
        read = read_codex("XC")
        self.assertEqual(read.header["session"], XC_ID)
        self.assertEqual(read.header["parent"], XP_ID)
        self.assertEqual(read.header["identity_basis"], "session_meta")
        self.assertTrue(read.header["child"])
        self.assertEqual(read.header["agent_path"], "/root/filer")
        self.assertEqual(read.header["depth"], 1)
        self.assertIsNone(read.header["inherited_id"])
        self.assertEqual({r["session"] for r in read.records}, {XC_ID})
        got = by_ref(read)
        self.assertEqual(got[ref_of("XC:3")]["model"], {"value": "codex-model-b", "basis": "runtime"})
        self.assertEqual(got[ref_of("XC:1")]["model"], {"value": "codex-model-a", "basis": "creation"})
        models = read.header["models"]
        self.assertIn({"value": "codex-model-a", "basis": "creation", "ref": ref_of("XC:1")}, models)
        self.assertIn({"value": "codex-model-b", "basis": "runtime", "ref": ref_of("XC:3")}, models)
        self.assertNotIn(("codex-model-a", "runtime"), {(m["value"], m["basis"]) for m in models})
        self.assertEqual(read.header["turn_ids"], ["turn-c1"])
        self.assertEqual(read.header["own_turn_ids"], ["turn-c1"])
        self.assertEqual(read.header["lines"], 8)
        self.assertEqual(read.header["cwd"], "/w/alpha")

    def test_xc_dispatch_is_encrypted_and_by_agent_path(self):
        read = read_codex("XC")
        brief = at_line(read, 4)
        self.assertEqual([r["ref"] for r in brief], [ref_of("XC:4#0"), ref_of("XC:4#1")])
        for r in brief:
            self.assertEqual((r["role"], r["role_basis"]), ("dispatch", "agent_path"))
            self.assertEqual(r["kind"], "response_item/agent_message")
        self.assertEqual(brief[0]["text"], "Message from /root")
        self.assertNotIn("encrypted", brief[0])
        self.assertTrue(brief[1]["encrypted"])
        self.assertNotIn("text", brief[1])
        self.assertEqual(brief[1]["block_type"], "encrypted_content")

    def test_xc_calls_pair_and_outputs_are_whole_records(self):
        read = read_codex("XC")
        got = by_ref(read)
        call, output = got[ref_of("XC:5")], got[ref_of("XC:6")]
        self.assertEqual((call["role"], call["call"]["id"], call["call"]["tool"]),
                         ("tool_call", "call_fx_file", "exec"))
        self.assertIn("tasks feedback", call["text"])
        self.assertEqual(call["call"]["peer"], output["ref"])
        self.assertEqual(output["role"], "tool_output")
        self.assertEqual(output["call"]["peer"], call["ref"])
        self.assertIn("zz-0000f1", output["text"])
        self.assertEqual(got[ref_of("XC:2")]["role"], "metadata")
        self.assertEqual(got[ref_of("XC:7#0")]["role"], "assistant")

    def test_xp_injected_prefixes_and_human(self):
        read = read_codex("XP")
        got = by_ref(read)
        for short in ("XP:4#0", "XP:5#0"):
            self.assertEqual((got[ref_of(short)]["role"], got[ref_of(short)]["role_basis"]),
                             ("injected", "prefix_rule"), short)
        self.assertEqual((got[ref_of("XP:6#0")]["role"], got[ref_of("XP:6#0")]["role_basis"]),
                         ("human", "prefix_rule"))
        self.assertEqual([r["ref"] for r in read.records if r["role"] == "human"], [ref_of("XP:6#0")])
        self.assertFalse(read.header["child"])
        self.assertIsNone(read.header["parent"])
        self.assertEqual(read.header["agent_path"], "/root")
        self.assertEqual(read.header["depth"], 0)
        spawn = got[ref_of("XP:7")]
        self.assertEqual(spawn["call"]["peer"], ref_of("XP:9"))
        self.assertEqual(got[ref_of("XP:10")]["call"]["peer"], ref_of("XP:12"))
        self.assertIn({"value": "codex-model-b", "basis": "requested", "ref": ref_of("XP:7")},
                      read.header["models"])
        activity = got[ref_of("XP:8")]
        self.assertEqual((activity["role"], activity["kind"]),
                         ("metadata", "event_msg/item_completed/SubAgentActivity"))
        self.assertEqual(activity["_subagent"], {"call": "call_fx_spawn", "thread": XC_ID,
                                                 "agent_path": "/root/filer", "kind": "started"})
        self.assertEqual(got[ref_of("XP:13#0")]["role"], "assistant")

    def test_root_thread_agent_message_is_injected(self):
        xe = by_ref(read_codex("XE"))
        report = xe[ref_of("XE:42#0")]
        self.assertEqual((report["role"], report["role_basis"]), ("injected", "agent_path"))
        xf_read = read_codex("XF")
        xf = by_ref(xf_read)
        for short in ("XF:4#0", "XF:4#1"):
            self.assertEqual((xf[ref_of(short)]["role"], xf[ref_of(short)]["role_basis"]),
                             ("dispatch", "agent_path"))
        self.assertTrue(xf[ref_of("XF:4#1")]["encrypted"])
        self.assertEqual(xf_read.header["agent_path"], "/root/worker")

    def test_xe_phases_mirrors_and_turn_events(self):
        read = read_codex("XE")
        got = by_ref(read)
        self.assertEqual(got[ref_of("XE:5#0")]["phase"], "commentary")
        self.assertEqual(got[ref_of("XE:7#0")]["phase"], "final_answer")
        self.assertNotIn("phase", got[ref_of("XE:30#0")])
        for short, original in (("XE:6", "XE:5#0"), ("XE:8", "XE:7#0"), ("XE:14", "XE:13#0")):
            mirror = got[ref_of(short)]
            self.assertEqual((mirror["role"], mirror["copy"]), ("metadata", "event_mirror"), short)
            self.assertEqual(mirror["original"], ref_of(original))
        self.assertIn("asks_user", got[ref_of("XE:14")]["_flags"])
        self.assertNotIn("asks_user", got[ref_of("XE:8")]["_flags"])
        self.assertEqual(read.header["turn_ids"], ["te1", "te2", "te3", "te4", "te5", "te6", "te7"])
        self.assertEqual(read.header["own_turn_ids"], read.header["turn_ids"])
        start = got[ref_of("XE:2")]
        self.assertIn("task_started", start["_flags"])
        self.assertEqual(start["_turn_id"], "te1")
        self.assertIn("turn_context", got[ref_of("XE:3")]["_flags"])
        done = got[ref_of("XE:9")]
        self.assertIn("task_complete", done["_flags"])
        self.assertEqual(done["_last_agent_message"], "Gamma holds four Claude and three Codex fixtures.")
        null_final = got[ref_of("XE:26")]
        self.assertIn("_last_agent_message", null_final)
        self.assertIsNone(null_final["_last_agent_message"])
        aborted = got[ref_of("XE:20")]
        self.assertIn("turn_aborted", aborted["_flags"])
        self.assertEqual(aborted["_abort_reason"], "interrupted")
        self.assertEqual(got[ref_of("XE:24")]["call"]["peer"], ref_of("XE:25"))
        self.assertEqual(got[ref_of("XE:24")]["call"]["command"], "wc -l fixtures/*.jsonl")
        self.assertEqual(got[ref_of("XE:4#0")]["message_id"], "msg_fx_e1_u1")
        self.assertIn("prompt", got[ref_of("XE:4#0")]["_flags"])

    def test_xa_task_complete_without_last_message(self):
        read = read_codex("XA")
        done = by_ref(read)[ref_of("XA:7")]
        self.assertNotIn("_last_agent_message", done)
        self.assertEqual(read.records[0]["store"], "archived")
        self.assertEqual(by_ref(read)[ref_of("XA:5#0")]["role"], "human")

    def test_xg_depth_two_identity_and_controller(self):
        read = read_codex("XG")
        self.assertEqual(read.header["session"], XG_ID)
        self.assertEqual(read.header["parent"], XC_ID)
        self.assertEqual(read.header["depth"], 2)
        self.assertEqual(read.header["agent_path"], "/root/filer/reviewer")
        self.assertTrue(read.header["child"])
        got = by_ref(read)
        self.assertEqual(got[ref_of("XG:3")]["model"], {"value": "codex-model-c", "basis": "runtime"})
        for short in ("XG:4#0", "XG:4#1"):
            self.assertEqual((got[ref_of(short)]["role"], got[ref_of(short)]["role_basis"]),
                             ("dispatch", "agent_path"))
        self.assertEqual({r["session"] for r in read.records}, {XG_ID})
        header_ids = {read.header[k] for k in ("session", "parent", "inherited_id")}
        self.assertNotIn(XP_ID, header_ids)

    def test_fork_without_parent_is_ambiguous_to_the_end(self):
        asked = []

        def unreadable(inherited_id):
            asked.append(inherited_id)
            return None
        read = read_codex("XK", unreadable)
        self.assertEqual(asked, [XK_INHERITED])
        self.assertEqual(read.header["session"], XK_ID)
        self.assertEqual(read.header["inherited_id"], XK_INHERITED)
        self.assertEqual(read.header["parent"], XK_INHERITED)
        got = by_ref(read)
        for short in ("XK:1", "XK:2"):
            self.assertEqual(got[ref_of(short)]["role"], "metadata")
            self.assertNotIn("copy", got[ref_of(short)])
        later = [r for r in read.records if r["line"] >= 3]
        self.assertEqual({r["line"] for r in later}, {3, 4, 5, 6, 7})
        for r in later:
            self.assertEqual(r["copy"], "ambiguous", r["ref"])
        self.assertEqual(read.header["turn_ids"], ["tk-copied"])
        self.assertEqual(read.header["own_turn_ids"], [])
        # An ambiguous range keeps the native turn facts: a turn is still built from it.
        self.assertIn("task_started", got[ref_of("XK:3")]["_flags"])
        self.assertIn("task_complete", got[ref_of("XK:7")]["_flags"])
        # R24: an ambiguous line is not known to be a copy, so it keeps and lists its model.
        self.assertEqual(got[ref_of("XK:4")]["model"], {"value": "codex-model-a", "basis": "runtime"})
        self.assertEqual({(m["value"], m["basis"], m["ref"]) for m in read.header["models"]},
                         {("codex-model-b", "creation", ref_of("XK:1")),
                          ("codex-model-a", "runtime", ref_of("XK:4"))})


# -- inline rollouts -------------------------------------------------------------------------

class InlineTest(InlineRollouts):
    def test_event_mirrors_and_command_executions(self):
        read = self.read_inline([
            meta("T"), started("u"),
            message("user", "hello", id="m_u"),
            completed("UserMessage", id="m_u", content=[{"type": "Text", "text": "hello"}]),
            message("assistant", "hi there", id="m_a", phase="final_answer"),
            completed("AgentMessage", id="m_a", content=[{"type": "Text", "text": "hi there"}],
                      phase="final_answer"),
            event("user_message", message="older hello"),
            event("agent_message", message="older hi"),
            completed("CommandExecution", id="ce1", command=["bash", "-lc", "ls"], cwd="/w/x",
                      status="completed", exit_code=0, aggregated_output="a\n"),
            completed("Reasoning", id="r1", summary_text=[]),
        ])
        mirrors = [r for r in read.records if r.get("copy") == "event_mirror"]
        self.assertEqual([r["line"] for r in mirrors], [4, 6, 7, 8])
        for r in mirrors:
            self.assertEqual((r["role"], r["role_basis"]), ("metadata", "structure"))
        got = {r["line"]: r for r in read.records}
        self.assertEqual(got[4]["kind"], "event_msg/item_completed/UserMessage")
        self.assertEqual(got[4]["text"], "hello")
        self.assertEqual(got[4]["original"], got[3]["ref"])
        self.assertEqual(got[6]["original"], got[5]["ref"])
        self.assertEqual(got[6]["phase"], "final_answer")
        self.assertEqual((got[7]["kind"], got[7]["text"]), ("event_msg/user_message", "older hello"))
        self.assertNotIn("original", got[7])
        self.assertEqual(got[8]["text"], "older hi")
        command = got[9]
        self.assertEqual((command["role"], command["kind"]),
                         ("metadata", "event_msg/item_completed/CommandExecution"))
        self.assertNotIn("copy", command)
        self.assertNotIn("call", command)
        self.assertEqual(command["execution"], {"command": ["bash", "-lc", "ls"], "exit_code": 0,
                                                "cwd": "/w/x", "status": "completed"})
        self.assertEqual((got[10]["role"], got[10].get("copy")), ("metadata", None))
        self.assertEqual(got[3]["role"], "human")

    def test_compaction_history_is_copied(self):
        read = self.read_inline([
            meta("T"), started("u"),
            {"timestamp": "2026-10-12T10:00:05.000Z", "type": "compacted",
             "payload": {"message": "summary", "replacement_history": [
                 {"type": "message", "role": "user",
                  "content": [{"type": "input_text", "text": "earlier ask"}]},
                 {"type": "message", "role": "assistant",
                  "content": [{"type": "output_text", "text": "earlier answer"}]}]}},
        ])
        line = [r for r in read.records if r["line"] == 3]
        self.assertEqual(len(line), 3)
        whole, *copies = line
        self.assertEqual((whole["role"], whole["kind"]), ("metadata", "compacted"))
        self.assertNotIn("copy", whole)
        self.assertNotIn("earlier answer", whole["text"])
        self.assertEqual(len(copies), 2)
        for index, r in enumerate(copies):
            self.assertEqual(r["copy"], "compaction_history")
            self.assertEqual(r["block"], index)
            self.assertEqual(r["kind"], "compacted")
            self.assertEqual(r["_flags"], frozenset())
        self.assertEqual([(r["role"], r["text"]) for r in copies],
                         [("human", "earlier ask"), ("assistant", "earlier answer")])

    def test_fork_history_ends_at_first_unknown_turn(self):
        asked = []

        def parent(inherited_id):
            asked.append(inherited_id)
            return {"t1", "t2"} if inherited_id == "P" else None
        rows = [meta("F", parent="P", agent_path="/root/f"), meta("P"),
                *turn("t1"), *turn("t2"), *turn("own1", prompt="mine", answer="own answer")]
        read = self.read_inline(rows, parent)
        self.assertEqual(asked, ["P"])
        self.assertEqual(read.header["session"], "F")
        self.assertEqual(read.header["inherited_id"], "P")
        copies = {r["line"]: r.get("copy") for r in read.records}
        self.assertEqual([copies[n] for n in (1, 2)], [None, None])
        self.assertEqual({copies[n] for n in range(3, 13)}, {"fork_history"})
        self.assertEqual({copies[n] for n in range(13, 18)}, {None})
        self.assertEqual(read.header["turn_ids"], ["t1", "t2", "own1"])
        self.assertEqual(read.header["own_turn_ids"], ["own1"])
        # Copied turns are not this file's: no runtime model, no native turn flags.
        copied_context = next(r for r in read.records if r["line"] == 4)
        self.assertNotIn("model", copied_context)
        self.assertEqual(copied_context["_flags"], frozenset())
        own_context = next(r for r in read.records if r["line"] == 14)
        self.assertEqual(own_context["model"], {"value": "runtime-model", "basis": "runtime"})
        self.assertEqual([m["ref"] for m in read.header["models"] if m["basis"] == "runtime"],
                         [own_context["ref"]])
        self.assertEqual({(m["value"], m["basis"]) for m in read.header["models"]},
                         {("creation-model", "creation"), ("runtime-model", "runtime")})
        self.assertEqual(sum(m["basis"] == "creation" for m in read.header["models"]), 1)

    def test_nested_fork_copies_grandparent_turns(self):
        p_rows = [meta("P", parent="G", agent_path="/root/p"), meta("G"), *turn("g1"), *turn("p1")]
        p_place, p_size = self.write(p_rows, name="rollout-p.jsonl")
        p_read = rec.codex_read(p_place, p_size, lambda i: {"g1"} if i == "G" else None)
        self.assertEqual(p_read.header["turn_ids"], ["g1", "p1"])
        self.assertEqual(p_read.header["own_turn_ids"], ["p1"])
        c_rows = [meta("C", parent="P", agent_path="/root/p/c"), meta("P"),
                  *turn("g1"), *turn("p1"), *turn("c1")]
        lookup = {"P": p_read.header["turn_ids"]}
        read = self.read_inline(c_rows, lambda i: lookup.get(i), name="rollout-c.jsonl")
        by_turn = {}
        current = None
        for r in read.records:
            if r["line"] <= 2:
                continue
            if r["kind"] == "event_msg/task_started":
                current = r["_turn_id"]
            by_turn.setdefault(current, set()).add(r.get("copy"))
        self.assertEqual(by_turn, {"g1": {"fork_history"}, "p1": {"fork_history"}, "c1": {None}})
        self.assertEqual(read.header["own_turn_ids"], ["c1"])
        # With only P's owned ids, g1 would be taken as C's own turn: the full list prevents it.
        wrong = self.read_inline(c_rows, lambda i: set(p_read.header["own_turn_ids"]),
                                 name="rollout-c2.jsonl")
        self.assertIn("g1", wrong.header["own_turn_ids"])
        self.assertNotIn("g1", read.header["own_turn_ids"])

    def test_child_without_agent_path_leaves_agent_messages_unknown(self):
        read = self.read_inline([meta("T", parent="P"), started("u"),
                                 agent_message("/root", "brief")])
        self.assertTrue(read.header["child"])
        self.assertIsNone(read.header["agent_path"])
        (brief,) = [r for r in read.records if r["line"] == 3]
        self.assertEqual((brief["role"], brief["role_basis"]), ("unknown", "agent_path"))

    def test_child_rule_and_controller_direction(self):
        read = self.read_inline([
            meta("T", thread_source="review", source="exec"), started("u"),
            message("user", "check this"),
            message("user", "<environment_context>x</environment_context>"),
            message("developer", "rules"),
        ])
        self.assertTrue(read.header["child"])
        roles = [(r["role"], r["role_basis"]) for r in read.records if r["line"] >= 3]
        self.assertEqual(roles, [("dispatch", "prefix_rule"), ("injected", "prefix_rule"),
                                 ("injected", "structure")])
        child = self.read_inline([
            meta("T", parent="P", agent_path="/root/a/b"), started("u"),
            agent_message("/root/a", "from the controller"),
            agent_message("/root", "from higher up"),
            agent_message("/root/a/c", "from a sibling"),
            agent_message("/root/a/b/d", "from my child"),
            item("agent_message", content=[{"type": "input_text", "text": "no author"}]),
        ], name="rollout-child.jsonl")
        self.assertEqual([r["role"] for r in child.records if r["line"] >= 3],
                         ["dispatch", "injected", "injected", "injected", "unknown"])
        root = self.read_inline([meta("R", parent=None), agent_message("/root", "self")],
                                name="rollout-root.jsonl")
        self.assertFalse(root.header["child"])
        self.assertEqual(root.records[-1]["role"], "injected")

    def test_table_rows_for_calls_reasoning_and_unknown(self):
        read = self.read_inline([
            meta("T"),
            item("local_shell_call", call_id="ls1", action={"type": "exec", "command": ["ls", "-a"]}),
            item("local_shell_call_output", call_id="ls1", output="x"),
            item("web_search_call", call_id="ws1", action={"type": "search", "query": "q"}),
            item("function_call", name="exec_command", call_id="fc1", arguments="not json"),
            item("function_call_output", call_id="fc1", output={"content": "boom", "success": False}),
            item("reasoning", summary=[{"type": "summary_text", "text": "thought"}],
                 encrypted_content="opaque"),
            item("reasoning", summary=[], encrypted_content="opaque"),
            item("tool_search_call", call_id="x"),
            {"type": "inter_agent_communication_metadata", "payload": {}},
            {"type": "token_usage_record", "payload": {}},
            {"type": "world_state", "payload": {}},
            event("token_count", info=None),
            {"type": "brand_new", "payload": {}},
            message("system", "odd role"),
        ])
        got = {r["line"]: r for r in read.records}
        self.assertEqual((got[2]["role"], got[2]["call"]["command"]), ("tool_call", "ls -a"))
        self.assertEqual(got[2]["call"]["peer"], got[3]["ref"])
        self.assertEqual(got[3]["role"], "tool_output")
        self.assertEqual((got[4]["role"], got[4]["call"]["id"]), ("tool_call", "ws1"))
        self.assertNotIn("command", got[5]["call"])
        self.assertEqual(got[5]["text"], "not json")
        self.assertTrue(got[6]["call"]["is_error"])
        self.assertEqual(got[6]["text"], "boom")
        self.assertEqual((got[7]["role"], got[7]["block_type"], got[7]["text"]),
                         ("assistant", "reasoning", "thought"))
        self.assertTrue(got[7]["encrypted"])
        self.assertTrue(got[8]["encrypted"])
        self.assertNotIn("text", got[8])
        self.assertEqual((got[9]["role"], got[9]["role_basis"]), ("unknown", "kind"))
        self.assertEqual({got[n]["role"] for n in (10, 11, 12)}, {"metadata"})
        self.assertEqual((got[13]["role"], got[13]["kind"]), ("unknown", "event_msg/token_count"))
        self.assertEqual((got[14]["role"], got[14]["kind"]), ("unknown", "brand_new"))
        self.assertEqual(got[15]["role"], "unknown")
        for r in read.records:
            self.assertIn(r["role_basis"], BASES)
            self.assertNotIn("turn", r)

    def test_odd_values_do_not_abort_a_read(self):
        read = self.read_inline([
            meta("T", parent=["P"], agent_path={"x": 1}),
            {"type": ["event_msg"], "payload": {}},
            {"type": "event_msg", "payload": {"type": ["task_started"], "turn_id": 3}},
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": ["u"]}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": {"a": 1}}}},
            {"type": "response_item", "payload": "not an object"},
            item("message", role=["user"], content=[{"type": "input_text", "text": 5}]),
            item("message", role="user", content="plain string"),
            item("agent_message", author=["/root"], content=[{"type": ["x"], "text": {}}]),
            item("function_call", name=["exec_command"], call_id=4, arguments={"cmd": "ls"}),
            item("reasoning", summary="no list", encrypted_content=5),
            {"type": "turn_context", "payload": {"model": ["m"]}},
            {"type": "compacted", "payload": {"replacement_history": "no list"}},
            {"type": "session_meta", "payload": ["odd"]},
            {"timestamp": 5, "type": "world_state"},
        ])
        self.assertEqual(read.unparsed, [])
        self.assertEqual(read.header["session"], "T")
        self.assertIsNone(read.header["parent"])
        self.assertIsNone(read.header["agent_path"])
        self.assertEqual(read.header["turn_ids"], [])
        for r in read.records:
            self.assertIsInstance(r.get("text", ""), str, r["ref"])
            self.assertIn(r["role_basis"], BASES, r["ref"])
            if "kind" in r and r["kind"] is not None:
                self.assertIsInstance(r["kind"], str)
        self.assertIsNone(read.records[-1]["at"])

    def test_envelope_is_shared_with_claude(self):
        read = self.read_inline([meta("T"), started("u")])
        self.assertEqual(list(read.records[1])[:len(ENVELOPE)], ENVELOPE)
        claude_rows = {"type": "user", "sessionId": "c0000000-0000-4000-8000-0000000000ff",
                       "timestamp": "2026-10-12T09:00:00.000Z", "message": {"content": "hi"}}
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / "c0000000-0000-4000-8000-0000000000ff.jsonl"
        data = json.dumps(claude_rows).encode() + b"\n"
        path.write_bytes(data)
        place = Place("claude-code", "claude", "personal", "live", path.name, path)
        claude = rec.claude_read(place, len(data))
        self.assertEqual(list(claude.records[0])[:len(ENVELOPE)], ENVELOPE)


# -- SDK ---------------------------------------------------------------------------------------

class SdkTest(unittest.TestCase):
    def read_sdk(self):
        given = f"tools/fixtures/session-logs/{CAPTURES['SDK']}"
        path = FIXTURES / CAPTURES["SDK"]
        place = Place("claude-code", "file", None, "explicit", given, path)
        return rec.sdk_read(place, path.stat().st_size), given

    def test_sdk_dispatch_links(self):
        read, given = self.read_sdk()
        got = by_ref(read)

        def one(short):
            return got[ref_of(short, given)]
        for short, dispatch in (("SDK:4#0", "toolu_fx_dA"), ("SDK:5#0", "toolu_fx_dB"),
                                ("SDK:6#0", "toolu_fx_dB"), ("SDK:7#0", "toolu_fx_dA")):
            self.assertEqual(one(short)["dispatch"], {"kind": "sdk_dispatch", "call": dispatch}, short)
        for short in ("SDK:2#0", "SDK:3#0", "SDK:8#0", "SDK:9#0", "SDK:1", "SDK:10"):
            self.assertNotIn("dispatch", one(short), short)
        refused = one("SDK:6#0")
        self.assertEqual(refused["role"], "tool_output")
        self.assertEqual(refused["call"]["peer"], ref_of("SDK:5#0", given))
        self.assertTrue(refused["call"]["is_error"])
        self.assertEqual(one("SDK:5#0")["call"]["peer"], ref_of("SDK:6#0", given))
        self.assertEqual(one("SDK:4#0")["call"]["peer"], ref_of("SDK:7#0", given))
        self.assertFalse(one("SDK:7#0")["call"]["is_error"])
        self.assertEqual(one("SDK:2#0")["call"]["peer"], ref_of("SDK:8#0", given))
        self.assertEqual(one("SDK:3#0")["call"]["peer"], ref_of("SDK:9#0", given))
        self.assertEqual(one("SDK:4#0")["role"], "tool_call")
        self.assertEqual(one("SDK:1")["role"], "metadata")
        self.assertEqual(one("SDK:1")["kind"], "system/init")
        self.assertEqual(one("SDK:10")["role"], "metadata")
        self.assertEqual(one("SDK:4#0")["store"], "explicit")

    def test_sdk_identity_is_the_shared_session_and_never_a_link(self):
        read, _given = self.read_sdk()
        self.assertEqual(read.header["session"], "c0000000-0000-4000-8000-000000000051")
        self.assertEqual(read.header["identity_basis"], "session_id")
        self.assertIsNone(read.header["parent"])
        self.assertEqual({r["session"] for r in read.records}, {"c0000000-0000-4000-8000-000000000051"})
        self.assertEqual(read.header["lines"], 10)

    def test_sdk_child_prompt_is_dispatch(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        rows = [
            {"type": "user", "session_id": "s", "parent_tool_use_id": None,
             "message": {"role": "user", "content": "the person's ask"}},
            {"type": "user", "session_id": "s", "parent_tool_use_id": "toolu_d",
             "message": {"role": "user", "content": [{"type": "text", "text": "the brief"}]}},
            {"type": ["odd"], "session_id": "s", "parent_tool_use_id": 5},
            {"type": "stream_event", "session_id": "s"},
        ]
        path = Path(d.name) / "sdk.jsonl"
        data = b"".join(json.dumps(r).encode() + b"\n" for r in rows)
        path.write_bytes(data)
        read = rec.sdk_read(Place("claude-code", "file", None, "explicit", str(path), path), len(data))
        human, brief, odd, stream = read.records
        self.assertEqual(human["role"], "human")
        self.assertEqual((brief["role"], brief["role_basis"]), ("dispatch", "structure"))
        self.assertEqual(brief["dispatch"], {"kind": "sdk_dispatch", "call": "toolu_d"})
        self.assertEqual((odd["role"], odd["kind"]), ("unknown", None))
        self.assertNotIn("dispatch", odd)
        self.assertEqual((stream["role"], stream["kind"]), ("unknown", "stream_event"))


class StepSixFollowUpTest(InlineRollouts):
    """Step-4 review follow-ups (R17, R18, call tool and id) and the Codex entrypoint."""

    def test_call_tool_is_a_string_and_a_null_call_id_falls_back_to_id(self):
        read = self.read_inline([
            meta("T"),
            item("function_call", name=["exec_command"], call_id=None, id="fc_1", arguments="{}"),
            item("custom_tool_call", name=5, call_id="ct_1", input="x"),
            item("function_call", name="exec_command", call_id="fc_2", id="other", arguments="{}"),
        ])
        bad_name, custom, plain = read.records[1:]
        self.assertEqual((bad_name["call"]["tool"], bad_name["call"]["id"]), ("function", "fc_1"))
        self.assertEqual((custom["call"]["tool"], custom["call"]["id"]), ("custom_tool", "ct_1"))
        self.assertEqual((plain["call"]["tool"], plain["call"]["id"]), ("exec_command", "fc_2"))

    def test_ambiguous_range_calls_pair_in_their_own_file(self):
        read = self.read_inline([
            meta("T", parent="P", forked_from_id="P"),
            meta("P"),
            started("tp"),
            item("function_call", name="exec_command", call_id="c1", arguments='{"cmd": "ls"}'),
            item("function_call_output", call_id="c1", output="ok"),
        ], inherited=lambda _inherited: None)
        call, output = read.records[3:]
        self.assertEqual((call["copy"], output["copy"]), ("ambiguous", "ambiguous"))
        self.assertEqual(read.unparsed, [])
        self.assertEqual(call["call"]["peer"], output["ref"])
        self.assertEqual(output["call"]["peer"], call["ref"])

    def test_output_content_array_is_one_object(self):
        read = read_codex("XC")
        output = at_line(read, 6)
        self.assertEqual(len(output), 1)
        self.assertNotIn("block", output[0])
        self.assertIn("Script completed", output[0]["text"])
        self.assertIn("zz-0000f1", output[0]["text"])

    def test_entrypoint_is_the_originator(self):
        self.assertEqual(read_codex("XC").header["entrypoint"], "codex-tui")


if __name__ == "__main__":
    unittest.main()
