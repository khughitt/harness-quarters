"""claude/probes/subagent-write-probe.py classification: what a stream-json transcript and
the probe directory say about each name, and the verdict they add up to."""
import importlib.util
import json
from pathlib import Path

PROBE = Path(__file__).resolve().parent.parent / "claude" / "probes" / "subagent-write-probe.py"
spec = importlib.util.spec_from_file_location("subagent_write_probe", PROBE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

REFUSAL = "<tool_use_error>" + probe.REFUSAL + " Include this content in your final response instead.</tool_use_error>"


def write(tool_id, path, parent="agent-call"):
    return {"type": "assistant", "parent_tool_use_id": parent,
            "message": {"content": [{"type": "tool_use", "id": tool_id, "name": "Write",
                                     "input": {"file_path": str(path), "content": "x"}}]}}


def result(tool_id, text, error, parent="agent-call", listed=False):
    content = [{"type": "text", "text": text}] if listed else text
    return {"type": "user", "parent_tool_use_id": parent,
            "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "is_error": error,
                                     "content": content}]}}


def test_written_refused_and_unattempted(tmp_path):
    (tmp_path / "notes.md").write_text("x")
    events = [write("a", tmp_path / "notes.md"), result("a", "File created", False),
              write("b", tmp_path / "report.md"), result("b", REFUSAL, True, listed=True)]
    rows = {row["name"]: row for row in probe.classify(tmp_path, events, ["notes.md", "report.md", "analysis.md"])}
    assert rows["notes.md"]["observed"] == "written"
    assert rows["report.md"]["observed"] == "refused"
    assert rows["analysis.md"]["observed"] == "not-attempted"


def test_a_refusal_by_the_main_agent_is_not_a_subagent_refusal(tmp_path):
    events = [write("b", tmp_path / "report.md", parent=None), result("b", REFUSAL, True, parent=None)]
    [row] = probe.classify(tmp_path, events, ["report.md"])
    assert row["observed"] == "not-attempted"


def test_another_error_is_failed_not_refused(tmp_path):
    events = [write("b", tmp_path / "report.md"), result("b", "<tool_use_error>denied</tool_use_error>", True)]
    [row] = probe.classify(tmp_path, events, ["report.md"])
    assert row["observed"] == "failed"


def test_rule_is_a_case_insensitive_md_prefix_on_the_basename():
    assert probe.rule_refuses("report.md") and probe.rule_refuses("sub/Summary-x.md")
    assert probe.rule_refuses("reports.md") and probe.rule_refuses("FINDINGS.MD")
    assert not probe.rule_refuses("task-1-report.md")
    assert not probe.rule_refuses("report.txt")
    assert not probe.rule_refuses("report/notes.md")


def test_verdict():
    agree = {"expected": "refused", "observed": "refused"}
    assert probe.verdict([agree, {"expected": "written", "observed": "written"}]) is True
    assert probe.verdict([agree, {"expected": "written", "observed": "refused"}]) is False
    assert probe.verdict([agree, {"expected": "written", "observed": "not-attempted"}]) == "inconclusive"
    assert probe.verdict([agree, {"expected": "written", "observed": "failed"}]) == "inconclusive"


def test_a_file_the_main_agent_wrote_after_a_refusal_stays_refused(tmp_path):
    (tmp_path / "task-1-report.md").write_text("x")
    events = [write("b", tmp_path / "task-1-report.md"), result("b", REFUSAL, True),
              write("m", tmp_path / "task-1-report.md", parent=None), result("m", "File created", False, parent=None)]
    [row] = probe.classify(tmp_path, events, ["task-1-report.md"])
    assert row["observed"] == "refused"


def test_a_file_the_main_agent_wrote_without_a_subagent_result_is_main_wrote(tmp_path):
    (tmp_path / "notes.md").write_text("x")
    events = [write("m", tmp_path / "notes.md", parent=None), result("m", "File created", False, parent=None)]
    [row] = probe.classify(tmp_path, events, ["notes.md"])
    assert row["observed"] == "main-wrote"


def test_session_store_follows_claude_codes_project_naming(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = probe.session_store(Path("/mnt/ssd3/tmp/subagent-write-probe-ab_c1"))
    assert store == tmp_path / ".claude" / "projects" / "-mnt-ssd3-tmp-subagent-write-probe-ab-c1"


def test_a_crash_is_inconclusive_and_keeps_its_directory(monkeypatch, capsys, tmp_path):
    def boom(*args, **kwargs):
        raise FileNotFoundError("claude")
    run = tmp_path / "run"
    monkeypatch.setattr(probe.tempfile, "mkdtemp", lambda **kwargs: (run.mkdir(), str(run))[1])
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(probe.subprocess, "run", boom)
    assert probe.main([]) == 2
    last = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert last["outcome"] == "inconclusive" and last["error"].startswith("FileNotFoundError")
    assert last["dir"] == str(run) and run.is_dir()


def test_a_file_on_disk_without_a_successful_subagent_write_is_not_written(tmp_path):
    (tmp_path / "notes.md").write_text("x")
    [row] = probe.classify(tmp_path, [], ["notes.md"])
    assert row["observed"] == "not-attempted"


def test_a_successful_write_whose_file_is_missing_is_failed(tmp_path):
    events = [write("a", tmp_path / "notes.md"), result("a", "File created", False)]
    [row] = probe.classify(tmp_path, events, ["notes.md"])
    assert row["observed"] == "failed"


def test_the_control_reads_the_main_agent(tmp_path):
    (tmp_path / "main").mkdir()
    events = [write("m", tmp_path / "main" / "report.md", parent=None), result("m", REFUSAL, True, parent=None)]
    assert probe.control(tmp_path, events)["observed"] == "refused"
    (tmp_path / "main" / "report.md").write_text("x")
    events = [write("m", tmp_path / "main" / "report.md", parent=None), result("m", "File created", False, parent=None)]
    assert probe.control(tmp_path, events)["observed"] == "written"


def test_null_content_message_and_input_do_not_crash(tmp_path):
    events = [{"type": "assistant", "parent_tool_use_id": "p", "message": None},
              {"type": "assistant", "parent_tool_use_id": "p",
               "message": {"content": [{"type": "tool_use", "id": "z", "name": "Write", "input": {}}]}},
              write("b", tmp_path / "report.md"),
              {"type": "user", "parent_tool_use_id": "p",
               "message": {"content": [{"type": "tool_result", "tool_use_id": "b", "is_error": True, "content": None}]}}]
    [row] = probe.classify(tmp_path, events, ["report.md"])
    assert row["observed"] == "failed"


def test_main_wrote_is_inconclusive():
    assert probe.verdict([{"expected": "written", "observed": "main-wrote"}]) == "inconclusive"


def test_events_skip_a_malformed_line_and_say_so():
    events, bad = probe.parse('{"type": "user"}\n{"type": \nnot json\n')
    assert events == [{"type": "user"}] and bad == 1
