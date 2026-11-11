"""Copy/link conformance moved from obs tests/session_logs/test_sessions.py.
Source revision: fe61869f0041eff423ed495d10845ef3cf3d5638.
Index and session-object assertions remain in obs.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from harness_evidence import records as rec
from harness_evidence import copies, links as native
from harness_evidence_testing import CAPTURES, FIXTURES, PATHS, materialize, no_parent, ref_of
from harness_evidence.lines import Place, ref
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


def item(kind, **body):
    return {"timestamp": "2026-10-12T10:00:02.000Z", "type": "response_item",
            "payload": {"type": kind, **body}}


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


CA_ID = "c0000000-0000-4000-8000-00000000000a"
AG = "agent-a0000000000000b01"
XP_ID = "01900000-0000-7000-8000-0000000000a1"
XC_ID = "01900000-0000-7000-8000-0000000000c1"
XG_ID = "01900000-0000-7000-8000-0000000000c2"
A_ID = "c0000000-0000-4000-8000-0000000000a1"
B_ID = "c0000000-0000-4000-8000-0000000000b1"
SEGMENT_A = "01900000-0000-7000-8000-0000000000a7"
SEGMENT_B = "01900000-0000-7000-8000-0000000000a8"


def under_home(short):
    return PATHS[short].split("/", 1)[1]



def file_ref(short):
    """A fixture's file ref (no line), as a session object spells it."""
    return ref_of(f"{short}:1")[:-len("#L1")]



def activity(call, thread):
    """A Codex `SubAgentActivity` `started` item binding a call id to a child thread."""
    return event("item_completed", thread_id="T", turn_id="u",
                 item={"type": "SubAgentActivity", "id": call, "kind": "started",
                       "agent_thread_id": thread, "agent_path": "/root/k"})



class CodexLinkTest(InlineRollouts):
    FORK = [meta("T", parent="P", forked_from_id="P"), meta("P"), started("tp"),
            item("function_call", name="spawn_agent", call_id="s1", arguments='{"model": "m"}'),
            activity("s1", "K"),
            item("function_call_output", call_id="s1", output="{}")]

    def test_links_in_an_ambiguous_fork_range_are_marked(self):
        read = self.read_inline(self.FORK, inherited=lambda _inherited: None)
        parent, binding = native.native_links(read)
        self.assertEqual((parent["kind"], parent["target"]), ("child_to_parent", "P"))
        self.assertNotIn("copy", parent)
        self.assertEqual((binding["kind"], binding["target"], binding["copy"]),
                         ("dispatch_binding", "K", "ambiguous"))
        self.assertEqual(binding["call"], {"id": "s1", "ref": ref(read.place, 4)})

    def test_fork_history_records_no_links_and_own_turns_do(self):
        own = [started("own"),
               item("function_call", name="spawn_agent", call_id="s2", arguments="{}"),
               activity("s2", "K2")]
        read = self.read_inline(self.FORK + own, inherited=lambda _inherited: ["tp"])
        self.assertEqual([(link["kind"], link["target"], link.get("copy"))
                          for link in native.native_links(read)],
                         [("child_to_parent", "P", None), ("dispatch_binding", "K2", None)])

    def test_binding_needs_a_spawn_call(self):
        read = self.read_inline([
            meta("T"),
            item("function_call", name="exec_command", call_id="e1", arguments="{}"),
            activity("e1", "K")])
        self.assertEqual(native.native_links(read), [])



def fixture_place(short, home=None):
    """A fixture's Place, under a materialized home when given, else the vendored copy."""
    fixture, dot, under = PATHS[short].split("/", 2)
    name = dot[1:]
    base = Path(home) if home is not None else FIXTURES / fixture
    harness = "codex" if name.startswith("codex") else "claude-code"
    store = "archived" if under.startswith("archived_sessions/") else "live"
    return Place(harness, name, "work" if name.endswith("-work") else "personal", store, under,
                 base / dot / under)



def read_file(place):
    size = place.path.stat().st_size
    if place.harness == "claude-code":
        return rec.claude_read(place, size)
    return rec.codex_read(place, size, lambda _inherited: None)



def by_ref(read):
    return {r["ref"]: r for r in read.records}



def row(kind, uuid, at, session, **extra):
    body = {"role": kind, "content": f"{kind} {uuid}"}
    if kind == "assistant":
        body.update(model="claude-model-a", id=f"msg_{uuid}")
    return {"type": kind, "uuid": uuid, "timestamp": at, "sessionId": session,
            "message": body, **extra}



def shared(session):
    """Two records both files of a pair hold: a prompt and a reply with a call and its result."""
    call = {"type": "assistant", "uuid": "u2", "timestamp": "2026-10-12T09:00:05.000Z",
            "sessionId": session,
            "message": {"role": "assistant", "model": "claude-model-a", "id": "msg_u2",
                        "content": [{"type": "tool_use", "id": "toolu_s", "name": "Bash",
                                     "input": {"command": "ls"}}]}}
    result = {"type": "user", "uuid": "u3", "timestamp": "2026-10-12T09:00:06.000Z",
              "sessionId": session,
              "message": {"role": "user", "content": [{"type": "tool_result",
                                                        "tool_use_id": "toolu_s", "content": "ok"}]}}
    return [row("user", "u1", "2026-10-12T09:00:00.000Z", session, origin={"kind": "human"}),
            call, result]



class InlinePair(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def write(self, session, rows, sub="projects/-w-x"):
        path = self.tmp / ".claude" / sub / f"{session}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(json.dumps(r).encode() + b"\n" for r in rows))
        place = Place("claude-code", "claude", "personal", "live", f"{sub}/{session}.jsonl", path)
        return rec.claude_read(place, path.stat().st_size)



class ResumeTest(InlinePair):
    def test_resume_copy_by_timing(self):
        cw = read_file(fixture_place("CW"))
        cw2 = read_file(fixture_place("CW2"))
        copies.mark_resume_copies([cw, cw2])
        got = by_ref(cw2)
        for short, original in (("CW2:1", "CW:1"), ("CW2:2#0", "CW:2#0"), ("CW2:3#0", "CW:3#0")):
            self.assertEqual(got[ref_of(short)]["copy"], "resume_history", short)
            self.assertEqual(got[ref_of(short)]["original"], ref_of(original), short)
        for r in cw2.records:
            if r["line"] >= 4:
                self.assertNotIn("copy", r, r["ref"])
        for r in cw.records:
            if r["line"] != 7:  # CW:7 is the request blob
                self.assertNotIn("copy", r, r["ref"])
        # The copied call is not a second call; the copy's model is not CW2's runtime evidence.
        self.assertIsNone(got[ref_of("CW2:2#0")]["call"]["peer"])
        self.assertNotIn("status", got[ref_of("CW2:2#0")]["call"])
        self.assertNotIn("model", got[ref_of("CW2:2#0")])
        self.assertEqual(got[ref_of("CW2:5#0")]["call"]["peer"], ref_of("CW2:6#0"))
        runtime = [m for m in cw2.header["models"] if m["basis"] == "runtime"]
        self.assertEqual(runtime, [{"value": "claude-model-a", "basis": "runtime",
                                    "ref": ref_of("CW2:5")}])
        # CW keeps its own calls paired and its models where they were.
        self.assertEqual(by_ref(cw)[ref_of("CW:2#0")]["call"]["peer"], ref_of("CW:3#0"))

    def test_resume_copy_by_continued_in_wins(self):
        def pair(native):
            a_rows = shared(A_ID)
            if native:
                a_rows.append({"type": "continued-in", "sessionId": A_ID,
                               "continuedInSessionId": B_ID,
                               "timestamp": "2026-10-12T09:30:00.000Z"})
            a_rows.append(row("user", "a5", "2026-10-12T11:00:00.000Z", A_ID,
                              origin={"kind": "human"}))
            b_rows = shared(B_ID) + [row("user", "b4", "2026-10-12T10:00:00.000Z", B_ID,
                                         origin={"kind": "human"})]
            a, b = self.write(A_ID, a_rows), self.write(B_ID, b_rows)
            copies.mark_resume_copies([a, b])
            return a, b

        # Timing alone makes A the copy: its first unshared record is later than all of B.
        a, b = pair(native=False)
        self.assertEqual({r["copy"] for r in a.records if r["line"] <= 3}, {"resume_history"})
        self.assertFalse(any("copy" in r for r in b.records))
        # A continued-in record in A naming B makes B the copy instead.
        a, b = pair(native=True)
        self.assertFalse(any("copy" in r for r in a.records))
        for r in b.records:
            if r["line"] <= 3:
                self.assertEqual(r["copy"], "resume_history", r["ref"])
                self.assertEqual(r["original"], r["ref"].replace(B_ID, A_ID))
            else:
                self.assertNotIn("copy", r)
        links = native.native_links(a)
        self.assertIn({"kind": "continued_in", "target": B_ID, "basis": "native_metadata",
                       "ref": ref(a.place, 4)}, links)
        self.assertEqual(native.native_links(b), [])

    def test_resume_tie_is_ambiguous(self):
        a = self.write(A_ID, shared(A_ID) + [
            row("user", "a4", "2026-10-12T10:00:00.000Z", A_ID, origin={"kind": "human"}),
            row("assistant", "a5", "2026-10-12T10:20:00.000Z", A_ID)])
        b = self.write(B_ID, shared(B_ID) + [
            row("user", "b4", "2026-10-12T10:10:00.000Z", B_ID, origin={"kind": "human"})])
        copies.mark_resume_copies([b, a])
        for read in (a, b):
            for r in read.records:
                if r["line"] <= 3:
                    self.assertEqual(r["copy"], "ambiguous", r["ref"])
                    self.assertNotIn("original", r)
                else:
                    self.assertNotIn("copy", r, r["ref"])
            # An ambiguous range may hold the file's own calls: they pair within the file.
            got = {r["line"]: r for r in read.records}
            self.assertEqual(got[2]["call"]["peer"], got[3]["ref"])
            self.assertEqual(got[3]["call"]["peer"], got[2]["ref"])
            # R24: an ambiguous line is not a known copy, so it keeps its model.
            self.assertEqual(got[2]["model"], {"value": "claude-model-a", "basis": "runtime"})
            self.assertIn({"value": "claude-model-a", "basis": "runtime", "ref": ref(read.place, 2)},
                          read.header["models"])

    def test_files_sharing_nothing_or_in_other_projects_are_untouched(self):
        a = self.write(A_ID, shared(A_ID))
        b = self.write(B_ID, shared(B_ID), sub="projects/-w-other")
        c_id = "c0000000-0000-4000-8000-0000000000c1"
        c = self.write(c_id, [row("user", "z1", "2026-10-12T12:00:00.000Z", c_id)])
        copies.mark_resume_copies([a, b, c])
        for read in (a, b, c):
            self.assertFalse(any("copy" in r for r in read.records))

    def test_identical_files_without_unshared_records_tie(self):
        a = self.write(A_ID, shared(A_ID))
        b = self.write(B_ID, shared(B_ID))
        copies.mark_resume_copies([a, b])
        for read in (a, b):
            self.assertEqual({r["copy"] for r in read.records}, {"ambiguous"})

    def test_wholly_copied_original_is_a_decided_resume(self):
        # R26: A has no unshared record, so it cannot meet the timing test; B, which adds a
        # later record, does. The resume is the copy, not a tie.
        a = self.write(A_ID, shared(A_ID))
        b = self.write(B_ID, shared(B_ID) + [
            row("user", "b4", "2026-10-12T10:00:00.000Z", B_ID, origin={"kind": "human"})])
        copies.mark_resume_copies([a, b])
        self.assertFalse(any("copy" in r for r in a.records))
        for r in b.records:
            if r["line"] <= 3:
                self.assertEqual((r["copy"], r["original"]),
                                 ("resume_history", r["ref"].replace(B_ID, A_ID)))
            else:
                self.assertNotIn("copy", r)

    def test_resume_chain_points_at_the_first_holder(self):
        c_id = "c0000000-0000-4000-8000-0000000000c1"
        b4 = row("user", "b4", "2026-10-12T10:00:00.000Z", B_ID, origin={"kind": "human"})
        for order in ((0, 1, 2), (2, 1, 0), (1, 2, 0)):
            a = self.write(A_ID, shared(A_ID))
            b = self.write(B_ID, shared(B_ID) + [b4])
            c = self.write(c_id, shared(c_id) + [{**b4, "sessionId": c_id}, row(
                "user", "c5", "2026-10-12T11:00:00.000Z", c_id, origin={"kind": "human"})])
            reads = [a, b, c]
            copies.mark_resume_copies([reads[n] for n in order])
            self.assertFalse(any("copy" in r for r in a.records), order)
            for r in b.records:
                if r["line"] <= 3:
                    self.assertEqual(r["original"], r["ref"].replace(B_ID, A_ID), order)
            for r in c.records:
                if r["line"] <= 3:
                    self.assertEqual(r["original"], r["ref"].replace(c_id, A_ID), order)
                elif r["line"] == 4:
                    self.assertEqual(r["original"], ref(b.place, 4), order)
                else:
                    self.assertNotIn("copy", r, order)

    def test_non_contiguous_shared_records(self):
        a = self.write(A_ID, [
            row("user", "u1", "2026-10-12T09:00:00.000Z", A_ID, origin={"kind": "human"}),
            row("assistant", "a2", "2026-10-12T09:01:00.000Z", A_ID),
            row("assistant", "u3", "2026-10-12T09:02:00.000Z", A_ID)])
        b = self.write(B_ID, [
            row("user", "u1", "2026-10-12T09:00:00.000Z", B_ID, origin={"kind": "human"}),
            row("user", "b2", "2026-10-12T10:00:00.000Z", B_ID, origin={"kind": "human"}),
            row("assistant", "u3", "2026-10-12T09:02:00.000Z", B_ID)])
        copies.mark_resume_copies([a, b])
        self.assertFalse(any("copy" in r for r in a.records))
        got = {r["line"]: r for r in b.records}
        self.assertEqual((got[1]["copy"], got[1]["original"]), ("resume_history", ref(a.place, 1)))
        self.assertEqual((got[3]["copy"], got[3]["original"]), ("resume_history", ref(a.place, 3)))
        self.assertNotIn("copy", got[2])

    def test_links_in_ambiguous_ranges_are_marked_and_copies_record_none(self):
        def launch(session):
            return {"type": "user", "uuid": "u4", "timestamp": "2026-10-12T09:00:07.000Z",
                    "sessionId": session, "toolUseResult": {"agentId": "a0000000000000c01"},
                    "message": {"role": "user", "content": [{"type": "tool_result",
                                                             "tool_use_id": "toolu_s",
                                                             "content": "launched"}]}}
        later = {A_ID: "2026-10-12T10:20:00.000Z", B_ID: "2026-10-12T10:10:00.000Z"}
        a = self.write(A_ID, shared(A_ID) + [launch(A_ID)] + [
            row("user", "a5", "2026-10-12T10:00:00.000Z", A_ID, origin={"kind": "human"}),
            row("assistant", "a6", later[A_ID], A_ID)])
        b = self.write(B_ID, shared(B_ID) + [launch(B_ID)] + [
            row("user", "b5", later[B_ID], B_ID, origin={"kind": "human"})])
        copies.mark_resume_copies([a, b])
        for read in (a, b):
            self.assertEqual(native.native_links(read), [{
                "kind": "parent_to_child", "target": "agent-a0000000000000c01",
                "basis": "native_metadata", "ref": ref(read.place, 4),
                "call": {"id": "toolu_s", "ref": None}, "copy": "ambiguous"}])
        # A decided resume: the copy's launch line records no link; the original's does.
        a = self.write(A_ID, shared(A_ID) + [launch(A_ID)])
        b = self.write(B_ID, shared(B_ID) + [launch(B_ID)] + [
            row("user", "b5", later[B_ID], B_ID, origin={"kind": "human"})])
        copies.mark_resume_copies([a, b])
        self.assertEqual(native.native_links(b), [])
        self.assertEqual([link.get("copy") for link in native.native_links(a)], [None])



class CopyHomeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = materialize("home", Path(tmp.name))

    def place(self, short):
        return fixture_place(short, self.home)

    def place_path(self, path):
        dot, under = path.relative_to(self.home).parts[0], path.relative_to(self.home).as_posix().split("/", 1)[1]
        name = dot[1:]
        return Place("codex", name, "work" if name.endswith("-work") else "personal",
                     "archived" if under.startswith("archived_sessions/") else "live", under, path)


class DuplicateTest(CopyHomeTest):
    def archived_copy(self):
        live = self.home / under_home("XP")
        copy = self.home / ".codex/archived_sessions" / live.name
        shutil.copyfile(live, copy)
        return live, copy

    def test_duplicate_file_collapses_into_earlier_root(self):
        live, copy = self.archived_copy()
        live_read = read_file(self.place_path(live))
        copy_read = read_file(self.place_path(copy))
        before = deepcopy(live_read.records)
        copies.mark_duplicate_files([copy_read, live_read])  # root order, not argument order
        for r in copy_read.records:
            self.assertEqual(r["copy"], "duplicate_file", r["ref"])
            self.assertEqual(r["original"], r["ref"].replace("archived_sessions/",
                                                             "sessions/2026/10/08/"))
        self.assertEqual(live_read.records, before)
        self.assertNotIn("divergent", live_read.header)
        self.assertNotIn("divergent", copy_read.header)
        self.assertEqual(copy_read.header["models"], [])

        # An edit to the copy: the edited line is no copy, and both files are divergent.
        data = copy.read_bytes().splitlines(keepends=True)
        data[12] = data[12].replace(b"The worker filed", b"The worker reported")
        copy.write_bytes(b"".join(data))
        live_read = read_file(self.place_path(live))
        copy_read = read_file(self.place_path(copy))
        copies.mark_duplicate_files([live_read, copy_read])
        edited = [r for r in copy_read.records if r["line"] == 13]
        self.assertTrue(edited)
        for r in edited:
            self.assertNotIn("copy", r)
        self.assertEqual({r["copy"] for r in copy_read.records if r["line"] != 13},
                         {"duplicate_file"})
        self.assertTrue(live_read.header["divergent"])
        self.assertTrue(copy_read.header["divergent"])

    def test_segments_of_one_thread_are_ordered_parts_not_copies(self):
        """Codex 0.165+ continues a thread in `rollout-<ts>-<thread>_<segment>.jsonl`: the base
        and each segment are parts of the thread, never compared as copies, even where a
        segment's line equals the base's line at the same number. A copy of one segment (its
        own name under the archive) still collapses into the live file."""
        live = self.home / under_home("XP")
        lines = live.read_text().splitlines(keepends=True)
        first = live.with_name(f"rollout-2026-10-08T12-00-00-{XP_ID}_{SEGMENT_A}.jsonl")
        second = live.with_name(f"rollout-2026-10-08T13-00-00-{XP_ID}_{SEGMENT_B}.jsonl")
        first.write_text("".join(lines[:3]))  # each line equals the base's at its number
        second.write_text("".join(lines[:3]))
        archived = self.home / ".codex/archived_sessions" / first.name
        shutil.copyfile(first, archived)
        base_read, first_read, second_read, archived_read = (
            read_file(self.place_path(path)) for path in (live, first, second, archived))
        segments = (base_read, first_read, second_read)
        before = [deepcopy(read.records) for read in segments]
        copies.mark_duplicate_files([base_read, first_read, second_read, archived_read])
        self.assertEqual([read.records for read in segments], before)
        for read in segments:
            self.assertNotIn("divergent", read.header, read.place.relpath)
        self.assertTrue(archived_read.records)
        for r in archived_read.records:
            self.assertEqual(r["copy"], "duplicate_file", r["ref"])
            self.assertEqual(r["original"], r["ref"].replace("archived_sessions/",
                                                             "sessions/2026/10/08/"))
        self.assertNotIn("divergent", archived_read.header)

    def test_different_identities_are_never_duplicates(self):
        xp = read_file(self.place("XP"))
        xc = read_file(self.place("XC"))
        copies.mark_duplicate_files([xp, xc])
        self.assertFalse(any(r.get("copy") == "duplicate_file" for r in xp.records + xc.records))
        self.assertNotIn("divergent", xp.header)



class LinkTest(CopyHomeTest):
    def test_sdk_dispatch_links_name_calls(self):
        place = Place("claude-code", "file", None, "explicit", CAPTURES["SDK"],
                      FIXTURES / CAPTURES["SDK"])
        read = rec.sdk_read(place, place.path.stat().st_size)
        links = native.native_links(read)
        self.assertEqual({link["kind"] for link in links}, {"sdk_dispatch"})
        self.assertEqual({link["basis"] for link in links}, {"native_metadata"})
        calls = {r["dispatch"]["call"] for r in read.records if "dispatch" in r}
        self.assertEqual({link["target"] for link in links}, calls)
        self.assertEqual(len(links), len(calls))


    def test_native_claude_paths_and_optional_meta(self):
        parent = read_file(self.place("CA"))
        child = read_file(self.place("AG"))
        self.assertEqual({(link["kind"], link["target"], link["basis"])
                          for link in native.native_links(parent)},
                         {("parent_to_child", AG, "native_metadata"),
                          ("parent_to_child", AG, "path")})
        self.assertEqual(native.native_links(child)[0]["call"],
                         {"id": "toolu_fx_agent", "ref": None})
        self.place("AG").path.with_suffix(".meta.json").unlink()
        self.assertNotIn("call", native.native_links(child)[0])
        self.place("AG").path.unlink()
        self.assertEqual(len(native.native_links(parent)), 1)
