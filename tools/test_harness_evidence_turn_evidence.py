"""Public evidence for obs turn policy, without assembling turns here."""
import json
from pathlib import Path
import tempfile
import unittest

from harness_evidence import records as rec
from harness_evidence.lines import Place
from harness_evidence_testing import CAPTURES, FIXTURES, PATHS

FLAG_VOCABULARY = {
    "prompt", "meta", "compaction_summary", "turn_duration", "interrupt_marker",
    "local_input", "local_output", "queued", "tool_result", "task_started",
    "task_complete", "turn_aborted", "asks_user", "stop_hook_blocked",
    "stop_hook_ok", "turn_context",
}


def sample_records(short):
    if short == "CWAIT":
        rel = "captures/turn-evidence-claude.jsonl"
    else:
        rel = PATHS.get(short, CAPTURES.get(short))
    path = FIXTURES / rel
    harness = "codex" if "/.codex" in rel else "claude-code"
    place = Place(harness, "file", None, "explicit", rel, path)
    if short == "SDK":
        return rec.sdk_read(place, path.stat().st_size).records
    if harness == "codex":
        return rec.codex_read(place, path.stat().st_size, lambda _id: None).records
    return rec.claude_read(place, path.stat().st_size).records


def all_records():
    return [r for short in [*PATHS, *CAPTURES, "CWAIT"] for r in sample_records(short)]


class TurnEvidenceTest(unittest.TestCase):
    def test_flags_cover_every_value_records_sets(self):
        seen = set()
        for record in all_records():
            self.assertEqual(record["flags"], sorted(set(record["flags"])))
            seen.update(record["flags"])
        self.assertLessEqual(seen, FLAG_VOCABULARY)
        self.assertLessEqual({"meta", "prompt", "task_complete"}, seen)
        self.assertNotIn("isMeta", seen)
        self.assertNotIn("isCompactSummary", seen)

    def test_wait_tools_and_stop_classes_are_normalized(self):
        rs = sample_records("CWAIT")
        calls = [r for r in rs if r["role"] == "tool_call"]
        self.assertEqual([r["waits_for_user"] for r in calls], [True, True, True, False])
        self.assertEqual([r["stop_class"] for r in calls], ["closing", "closing", "other", None])
        answers = [r for r in rs if r["role"] == "assistant" and r["block_type"] == "text"]
        self.assertEqual([r["stop_class"] for r in answers], ["closing", "closing", "other", None])
        self.assertTrue(all(r["readable_text"] for r in answers))
        self.assertFalse(any(r["readable_text"] for r in rs if r["block_type"] != "text"))

    def test_codex_turn_evidence_is_published(self):
        rs = sample_records("XE")
        ends = [r for r in rs if {"task_complete", "turn_aborted"} & set(r["flags"])]
        self.assertTrue(ends)
        self.assertTrue(all(r["turn_id"] for r in ends))
        self.assertTrue(any(r["turn_end_message"] for r in ends if "task_complete" in r["flags"]))
        self.assertEqual([r["abort_reason"] for r in ends if "turn_aborted" in r["flags"]], ["interrupted"])
        self.assertGreaterEqual({r["answer_phase"] for r in rs if r["role"] == "assistant"},
                                {"final", "other", None})

    def test_codex_wait_tool_is_native_to_codex(self):
        rows = [
            {"type": "session_meta", "payload": {"id": "thread"}},
            *[{"type": "response_item", "payload": {"type": "function_call", "name": name,
                "call_id": str(i), "arguments": "{}"}}
              for i, name in enumerate(["request_user_input", "exec_command", "AskUserQuestion"])],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "codex.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            place = Place("codex", "file", None, "explicit", "codex.jsonl", path)
            rs = rec.codex_read(place, path.stat().st_size, lambda _id: None).records
        self.assertEqual([r["waits_for_user"] for r in rs if r["role"] == "tool_call"],
                         [True, False, False])

    def test_published_evidence_preserves_private_values(self):
        for r in all_records():
            self.assertEqual(r["turn_id"], r.get("_turn_id"))
            self.assertEqual(r["abort_reason"], r.get("_abort_reason"))
            self.assertEqual(r["turn_end_message"], r.get("_last_agent_message"))
            self.assertEqual(r["readable_text"], r["role"] == "assistant" and
                             r.get("block_type") in {None, "text", "output_text"})
            if r["role"] == "assistant":
                expected = None if r.get("phase") is None else "final" if r["phase"] == "final_answer" else "other"
                self.assertEqual(r["answer_phase"], expected)
            if r["role"] == "tool_call":
                expected = (r.get("call") or {}).get("tool") in {
                    "AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "request_user_input"}
                self.assertEqual(r["waits_for_user"], expected)
            expected = sorted({{"isMeta": "meta", "isCompactSummary": "compaction_summary"}.get(f, f)
                               for f in r["_flags"]})
            self.assertEqual(r["flags"], expected)
