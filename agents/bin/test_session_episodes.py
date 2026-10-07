# agents/bin/test_session_episodes.py
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("session-episodes")
spec = importlib.util.spec_from_loader("session_episodes", loader=None)
se = importlib.util.module_from_spec(spec)
sys.modules["session_episodes"] = se
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), se.__dict__)

from datetime import datetime, timezone

T0 = "2026-09-17T12:00:00.000Z"
BASE = int(datetime.fromisoformat(T0.replace("Z", "+00:00")).timestamp())


def ts(seconds):
    """T0 plus seconds, as the ISO form both stores write."""
    return datetime.fromtimestamp(BASE + seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ms(seconds):
    return (BASE + seconds) * 1000


# --- Claude fixture ------------------------------------------------------------

def c_user(text, t, uuid, sid="S1", **extra):
    r = {"type": "user", "uuid": uuid, "sessionId": sid, "cwd": "/w", "entrypoint": "cli",
         "timestamp": ts(t), "message": {"role": "user", "content": text}}
    r.update(extra)
    return r


def c_result(call_id, text, t, uuid, sid="S1"):
    return {"type": "user", "uuid": uuid, "sessionId": sid, "cwd": "/w", "entrypoint": "cli",
            "timestamp": ts(t),
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id, "content": text}]}}


def c_assistant(blocks, t, uuid, sid="S1"):
    return {"type": "assistant", "uuid": uuid, "sessionId": sid, "cwd": "/w", "entrypoint": "cli",
            "timestamp": ts(t), "message": {"role": "assistant", "content": blocks}}


def bash(call_id, command):
    return {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}


def text(s):
    return {"type": "text", "text": s}


def claude_file(tmp_path, records, name="S1.jsonl"):
    d = tmp_path / "claude" / "-w"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("".join(json.dumps(r) + "\n" for r in records))
    return p


# --- Codex fixture -------------------------------------------------------------

def x_meta(sid="X1", t=0, originator="codex-tui", thread_source="user"):
    return {"timestamp": ts(t), "type": "session_meta",
            "payload": {"id": sid, "timestamp": ts(t), "cwd": "/w", "originator": originator,
                        "thread_source": thread_source}}


def x_event(kind, t, turn_id="t1"):
    return {"timestamp": ts(t), "type": "event_msg", "payload": {"type": kind, "turn_id": turn_id}}


def x_user(text, t):
    return {"timestamp": ts(t), "type": "response_item",
            "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}}


def x_assistant(text, t):
    return {"timestamp": ts(t), "type": "response_item",
            "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}}


def x_custom(call_id, js, t):
    return {"timestamp": ts(t), "type": "response_item",
            "payload": {"type": "custom_tool_call", "name": "exec", "call_id": call_id, "input": js}}


def x_custom_out(call_id, text, t):
    return {"timestamp": ts(t), "type": "response_item",
            "payload": {"type": "custom_tool_call_output", "call_id": call_id,
                        "output": [{"type": "input_text", "text": "Script completed\nOutput:\n"},
                                   {"type": "input_text", "text": text}]}}


def x_func(call_id, name, arguments, t):
    return {"timestamp": ts(t), "type": "response_item",
            "payload": {"type": "function_call", "name": name, "call_id": call_id, "arguments": arguments}}


def x_func_out(call_id, output, t):
    return {"timestamp": ts(t), "type": "response_item",
            "payload": {"type": "function_call_output", "call_id": call_id, "output": output}}


def codex_file(tmp_path, records, name="rollout-2026-09-17T12-00-00-X1.jsonl"):
    d = tmp_path / "codex" / "2026" / "09" / "17"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("".join(json.dumps(r) + "\n" for r in records))
    return p


# --- readers -------------------------------------------------------------------

def test_at_ms_parses_iso_with_and_without_fraction():
    assert se.at_ms("2026-09-17T12:00:00.000Z") == ms(0)
    assert se.at_ms("2026-09-17T12:00:01Z") == ms(1)


def test_read_claude_yields_human_assistant_tool_events_in_order(tmp_path):
    p = claude_file(tmp_path, [
        c_user("Let's pick up ai-000001", 0, "u1"),
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", '{"id":"ai-000001","warnings":[]}', 2, "u2"),
        c_assistant([text("Started.")], 3, "a2"),
    ])
    s = se.read_claude(p)
    assert s.harness == "claude-code" and s.session_id == "S1" and s.cwd == "/w"
    assert s.entrypoint == "cli" and s.subagent is False and s.malformed == 0
    kinds = [(e.kind, e.line) for e in s.events]
    assert kinds == [("human", 1), ("assistant", 2), ("tool_call", 2), ("tool_result", 3), ("assistant", 4)]
    call = s.events[2]
    assert call.call_id == "toolu_1" and call.tool == "Bash" and call.commands == ("tasks start ai-000001",)
    assert s.events[1].text_only is False and s.events[1].pending == ("toolu_1",)
    assert s.events[3].text == '{"id":"ai-000001","warnings":[]}'
    assert s.events[4].text_only is True and s.events[4].uuid == "a2"


def test_read_claude_skips_meta_injected_sidechain_and_counts_malformed(tmp_path):
    p = claude_file(tmp_path, [
        c_user("<system-reminder>x</system-reminder>", 0, "u0"),
        c_user("meta", 0, "u1", isMeta=True),
        c_user("summary", 0, "u2", isCompactSummary=True),
        c_user("side", 0, "u3", isSidechain=True),
        {"type": "ai-title", "aiTitle": "t"},
        c_user("[Request interrupted by user]", 1, "u4"),
        c_user([text("real")], 2, "u5"),
    ])
    p.write_text(p.read_text() + "{not json\n")
    s = se.read_claude(p)
    assert [e.kind for e in s.events] == ["interrupt", "human"]
    assert s.events[1].text == "real" and s.malformed == 1


def test_read_claude_marks_subagent_file_and_interrupted_result(tmp_path):
    side = claude_file(tmp_path, [c_user("x", 0, "u1", isSidechain=True)], name="agent.jsonl")
    assert se.read_claude(side).subagent is True
    p = claude_file(tmp_path, [
        c_assistant([bash("toolu_1", "sleep 5")], 0, "a1"),
        c_result("toolu_1", "[Request interrupted by user for tool use]", 1, "u1"),
    ])
    s = se.read_claude(p)
    assert s.events[2].kind == "tool_result" and s.events[2].interrupted is True


def test_read_codex_yields_turn_events_and_tool_calls(tmp_path):
    p = codex_file(tmp_path, [
        x_meta(),
        x_event("task_started", 0),
        x_user("go", 0),
        x_custom("c1", 'const r = await tools.exec_command({cmd:"tasks start ai-000001"});', 1),
        x_custom_out("c1", '{"id":"ai-000001","warnings":[]}\n', 2),
        x_func("c2", "shell", json.dumps({"command": ["bash", "-lc", "tasks note ai-000001 hi"]}), 3),
        x_func_out("c2", '{"id":"ai-000001","warnings":[]}\n', 4),
        x_assistant("Done.", 5),
        x_event("task_complete", 5),
    ])
    s = se.read_codex(p)
    assert s.harness == "codex" and s.session_id == "X1" and s.entrypoint == "codex-tui" and s.subagent is False
    kinds = [e.kind for e in s.events]
    assert kinds == ["turn_start", "human", "tool_call", "tool_result", "tool_call", "tool_result", "assistant", "turn_end"]
    assert s.events[2].commands == ("tasks start ai-000001",) and s.events[2].call_id == "c1"
    assert s.events[3].text.endswith('{"id":"ai-000001","warnings":[]}\n')
    assert s.events[4].commands == ("tasks note ai-000001 hi",)
    assert s.events[6].text_only is True and s.events[7].turn_id == "t1"


def test_read_codex_filters_injected_user_text_and_marks_subagent(tmp_path):
    p = codex_file(tmp_path, [
        x_meta(thread_source="subagent"),
        x_user("# AGENTS.md\nrules", 0),
        x_user("<environment_context>x", 0),
        x_user("real question", 1),
        x_event("turn_aborted", 2),
    ])
    s = se.read_codex(p)
    assert s.subagent is True
    assert [e.kind for e in s.events] == ["human", "turn_aborted"]


# --- commands and attribution --------------------------------------------------

LIT_JS = '''const r = await Promise.all([
  tools.exec_command({"cmd":"tasks start lit-f43833","workdir":"/w","yield_time_ms":10000}),
  tools.exec_command({"cmd":"pwd -P; git status --short; sed -n '1,360p' docs/plans/x.md","workdir":"/w"}),
  tools.exec_command({"cmd":"find . -maxdepth 3 -type f | sort | sed -n '1,260p'; just --list 2>/dev/null || true","workdir":"/w"})
]);
text(r.map(x=>x.output).join("\\n\\n"));'''

OK = '{"id":"ai-000001","warnings":[]}\n'


def test_custom_input_literal_forms():
    assert se.commands_of_custom_input('tools.exec_command({"cmd":"tasks start ai-000001"})') == (("tasks start ai-000001",), False)
    assert se.commands_of_custom_input("tools.exec_command({cmd:\"tasks start ai-000001 && ls\"})") == (("tasks start ai-000001 && ls",), False)
    assert se.commands_of_custom_input("tools.exec_command({cmd:'tasks start ai-000001'})") == (("tasks start ai-000001",), False)
    assert se.commands_of_custom_input("tools.exec_command({cmd:`tasks start ai-000001`})") == (("tasks start ai-000001",), False)
    assert se.commands_of_custom_input('({cmd:"echo \\"quoted\\" && tasks start ai-000001"})') == (('echo "quoted" && tasks start ai-000001',), False)
    assert se.commands_of_custom_input("tools.exec_command({cmd:`false && tasks start ai-000001\\ntasks note ai-000001 checked`})") == (("false && tasks start ai-000001\ntasks note ai-000001 checked",), False)


def test_custom_input_unsupported_wrapper_is_flagged_not_lost():
    cmds, unsupported = se.commands_of_custom_input("const id='ai-000001'; tools.exec_command({cmd:`tasks start ${id}`})")
    assert cmds == () and unsupported is True
    cmds, unsupported = se.commands_of_custom_input('tools.exec_command({cmd: "tasks start ai-000001" + " >/dev/null; cat saved.jsonl"})')
    assert cmds == () and unsupported is True  # a literal prefix of a concatenation is not the command
    cmds, unsupported = se.commands_of_custom_input('tools.exec_command({cmd: ok ? "tasks start ai-000001" : "ls"})')
    assert cmds == () and unsupported is True
    cmds, unsupported = se.commands_of_custom_input("tools.exec_command({cmd:`tasks start ai-000001 \\u0041`})")
    assert cmds == () and unsupported is True
    cmds, unsupported = se.commands_of_custom_input("tools.exec_command({cmd:'ls'})")
    assert cmds == ("ls",) and unsupported is False


def test_custom_input_lit_shape_yields_three_commands():
    cmds, unsupported = se.commands_of_custom_input(LIT_JS)
    assert len(cmds) == 3 and cmds[0] == "tasks start lit-f43833" and unsupported is False
    assert se.single_wrapper_command(LIT_JS) is None


@pytest.mark.parametrize("source,expected", [
    ('const r = await tools.exec_command({"cmd":"tasks start ai-000001","workdir":"/w","yield_time_ms":10000}); text(r.output);', "tasks start ai-000001"),
    ("const r=await tools.exec_command({cmd:'tasks start ai-000001'});text(r.output);", "tasks start ai-000001"),
    ("text(await tools.exec_command({cmd: `tasks start ai-000001`}));", "tasks start ai-000001"),
    ("text((await tools.exec_command({cmd:\"tasks start ai-000001\"})).output)", "tasks start ai-000001"),
    ("const out = await tools.exec_command({cmd:\"tasks start ai-000001\"}); text(out);", "tasks start ai-000001"),
    ("const r = await tools.exec_command({cmd:\"tasks start ai-000001\"}); text(r.output); text(await tools.write_stdin({chars:\"y\"}));", None),
    ('const cmd = "cat saved.jsonl";\nif (false) { await tools.exec_command({cmd: "tasks start ai-000001"}); }\ntext(await tools.exec_command({cmd}));', None),
    ("text(await tools.exec_command({cmd: \"tasks start ai-000001\" + \" >/dev/null\"}));", None),
    ("text(await tools.exec_command({cmd: `tasks start ${id}`}));", None),
    ("text(await tools.exec_command({cmd: \"tasks start ai-000001\", env: process.env}));", None),
    ("const r = await tools.exec_command({cmd:\"tasks start ai-000001\"}); text(r.stdout);", None),
])
def test_single_wrapper_command(source, expected):
    assert se.single_wrapper_command(source) == expected


@pytest.mark.parametrize("command,expected", [
    ("tasks start ai-000001", ("start", "ai-000001", False)),
    ("cd /w && tasks start ai-000001", ("start", "ai-000001", False)),
    ("tasks start --force ai-000001", ("start", "ai-000001", False)),
    ("tasks start ai-000001 2>&1", ("start", "ai-000001", False)),
    ("tasks start ai-000001 2>/dev/null", ("start", "ai-000001", False)),
    ("tasks start ai-000001 --pretty", ("start", "ai-000001", True)),
    ("tasks --pretty start ai-000001", ("start", "ai-000001", True)),
    ("tasks -C /w start ai-000001", ("start", "ai-000001", False)),
    ("tasks note \"ai-000001\" \"gate: verified — it's fine\"", ("note", "ai-000001", False)),
    ("tasks park ai-000001 'later' --waiting-on user --reason review", ("park", "ai-000001", False)),
    ("tasks done ai-000001 landed 2>&1", ("done", "ai-000001", False)),
    ("tasks start ai-000001 >/dev/null", None),
    ("tasks start ai-000001 >&2", None),
    ("tasks start ai-000001 2>&1 | tail -1", None),
    ("tasks start ai-000001 && git add tasks", None),
    ("cd /w && tasks start ai-000001 >/dev/null && tasks note ai-000001 'x'", None),
    ("just setup && tasks start ai-000001", None),
    ("cd $HOME && tasks start ai-000001", None),
    ("cd /w; tasks start ai-000001", None),
    ("tasks start ai-000001; tasks note ai-000001 x", None),
    ("tasks start ai-000001\ntasks note ai-000001 x", None),
    ("tasks note ai-000001 \"$(date)\"", None),
    ("tasks note ai-000001 `date`", None),
    ("tasks -C \"$(cat saved.jsonl >&2)\" start ai-000001 2>/dev/null", None),
    ("tasks -C `pwd` start ai-000001", None),
    ("tasks start ai-000001 2>$LOG", None),
    ("tasks start ai-000001 'unbalanced", None),
    ("tasks start ai-000001 &", None),
    ("(tasks start ai-000001)", None),
    ("bash -c 'tasks start ai-000001'", None),
    ("tasks start", None),
    ("echo 'tasks start ai-000001'", None),
    ("cd absent-dir && tasks start ai-000001; MODE=x cat saved.jsonl", None),
    ("cd absent-dir && tasks start ai-000001; printf '{\"%s\":\"%s-%s\",\"warnings\":[]}\\n' id ai 000001", None),
    ("cd absent-dir && tasks start ai-000001; tasks note ai-000001 checked | grep --regexp=id saved.jsonl", None),
    ("cd absent-dir && tasks start ai-000001; tasks note ai-000001 checked >&2", None),
])
def test_single_invocation(command, expected):
    inv = se.single_invocation(command)
    assert (None if inv is None else (inv.subcommand, inv.task_id, inv.pretty)) == expected


def test_start_candidates_loose_and_nested():
    assert se.start_candidates("tasks start ai-000001 && tasks start --force ai-00000a") == ["ai-000001", "ai-00000a"]
    assert se.start_candidates('tasks start "ai-000001"') == ["ai-000001"]
    assert se.start_candidates("tasks --pretty start ai-000001") == ["ai-000001"]
    assert se.start_candidates("tasks -C /w start ai-000001") == ["ai-000001"]
    assert se.start_candidates('tasks -C /w --pretty start "ai-000001" && ls') == ["ai-000001"]  # loose route, same forms
    assert se.transitions_in('tasks park "ai-000001" later && ls') == [("park", "ai-000001")]
    assert se.start_candidates("just setup && tasks start ai-000001 | sed p") == ["ai-000001"]
    assert se.start_candidates("echo tasks start") == []
    assert se.start_candidates("python3 - <<'EOF'\nprint('tasks start ai-000001')\nEOF\ntasks note ai-00000a \"see tasks start ai-00000b\"") == []
    assert se.start_candidates("tasks note ai-000001 'tasks start ai-000001'") == []
    assert se.nested_start_candidates("bash <<'EOF'\ntasks start ai-000001\nEOF") == ["ai-000001"]
    assert se.nested_start_candidates("bash -c 'cd /w && tasks start ai-000001'") == ["ai-000001"]
    assert se.nested_start_candidates('ssh host "tasks start ai-000001"') == ["ai-000001"]
    assert se.nested_start_candidates('echo "$(tasks start ai-000001)"') == ["ai-000001"]
    assert se.nested_start_candidates("tasks note ai-000001 'tasks start ai-000001'") == []
    assert se.transitions_in("tasks park ai-000001 'next' --waiting-on user; tasks done ai-00000a 'x'") == [("park", "ai-000001"), ("done", "ai-00000a")]


def test_id_lines_counts_only_id_warnings_objects():
    out = 'noise\n{"id":"ai-000001","warnings":[]}\n{"task":{"id":"ai-000001"}}\n{"id":"ai-000001","warnings":["w"]}\n{"id":"ai-00000a","warnings":[]}\n'
    assert se.id_lines(out, "ai-000001") == 2
    assert se.id_lines(out, "ai-00000a") == 1
    assert se.ids_in_result(out) == ["ai-000001", "ai-00000a"]
    assert se.id_lines("ai-000001\n", "ai-000001") == 0
    assert se.id_lines("ai-000001\n", "ai-000001", pretty=True) == 1


def test_attribute_rules_from_the_spec():
    assert se.attribute(("tasks start ai-000001",), OK, "ai-000001") == "confirmed"
    assert se.attribute(("cd /w && tasks start ai-000001",), OK, "ai-000001") == "confirmed"
    assert se.attribute(("tasks start ai-000001 2>&1",), OK, "ai-000001") == "confirmed"
    assert se.attribute(("tasks start ai-000001 --pretty",), "ai-000001\n", "ai-000001") == "confirmed"
    assert se.attribute(("tasks start ai-000001",), "", "ai-000001") == "no-id-line"
    assert se.attribute(("tasks start ai-000001",), "warning: something\n", "ai-000001") == "no-id-line"
    assert se.attribute(("tasks start ai-000001",), "error: claimed by another session\n" + OK, "ai-000001") == "error-output"
    assert se.attribute(("tasks start ai-000001", "ls"), OK, "ai-000001") == "outside-grammar"  # two literals, one output
    assert se.attribute(("tasks note ai-000001 x",), OK, "ai-000001") == "outside-grammar"  # not the start
    assert se.attribute(("tasks start ai-00000a",), OK, "ai-000001") == "outside-grammar"  # not this task
    assert se.attribute(("tasks park ai-000001 'later'",), OK, "ai-000001", "park") == "confirmed"
    assert se.attribute(("tasks done ai-000001 landed 2>&1",), OK, "ai-000001", "done") == "confirmed"
    for outside in ("tasks start ai-000001 >/dev/null", "tasks start ai-000001 2>&1 | tail -1",
                    "just setup && tasks start ai-000001", "tasks start ai-000001 && git add tasks",
                    "false && tasks start ai-000001; tasks note ai-000001 'x'",
                    "tasks start ai-000001; cat saved.jsonl", 'echo "$(tasks note ai-000001 checked | sed p)"',
                    "for n in 1 2; do tasks note ai-000001 checked; done", "echo 'tasks start ai-000001'"):
        assert se.attribute((outside,), OK + OK, "ai-000001") == "outside-grammar", outside


def test_attribute_lit_shape_is_outside_the_grammar():
    cmds, _ = se.commands_of_custom_input(LIT_JS)
    assert se.attribute(cmds, '{"id":"lit-f43833","warnings":[]}\n\n\n/w\n M x\n', "lit-f43833") == "outside-grammar"


# --- task records --------------------------------------------------------------

import subprocess

TASK_MD = """---
id: ai-000001
title: T
status: {status}
priority: 2
created: 2026-09-17T11:00:00Z
updated: 2026-09-17T13:00:00Z
{completed}depends: []
---

Body.

## Notes

{notes}"""


def task_file(root, notes, status="doing", completed=None, task_id="ai-000001", started=None):
    d = root / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    stamps = (f"started: {started}\n" if started else "") + (f"completed: {completed}\n" if completed else "")
    body = TASK_MD.format(status=status, notes="\n".join(notes) + ("\n" if notes else ""), completed=stamps)
    (d / f"{task_id}.md").write_text(body.replace("id: ai-000001", f"id: {task_id}"))
    return d / f"{task_id}.md"


def git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return path


def test_task_copies_lists_root_and_worktrees_and_flags_unreadable(tmp_path):
    root = git_repo(tmp_path / "ai")
    (root / "tasks").mkdir()
    wt = tmp_path / "ai-wt"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", str(wt), "-b", "wt"], check=True)
    (wt / "tasks").mkdir()
    gone = tmp_path / "ai-gone"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", str(gone), "-b", "gone"], check=True)
    import shutil
    shutil.rmtree(gone)
    readable, unreadable = se.task_copies(root)
    assert sorted(readable) == sorted([root / "tasks", wt / "tasks"])
    assert unreadable == [gone]


def test_read_task_unions_notes_across_copies_and_parses_provenance(tmp_path):
    root = git_repo(tmp_path / "ai")
    wt = tmp_path / "ai-wt"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", str(wt), "-b", "wt"], check=True)
    task_file(root, ["- 2026-09-17T12:00:05Z (main): started",
                     '  provenance: {"harness_session":"codex:X1","harness_session_source":"CODEX_SESSION_ID"}'])
    task_file(wt, ["- 2026-09-17T12:00:05Z (main): started",
                   '  provenance: {"harness_session":"codex:X1","harness_session_source":"CODEX_SESSION_ID"}',
                   "- 2026-09-17T12:20:00Z (wt): parked (waiting on user, review): look",
                   "- 2026-09-17T12:30:00Z (wt): done"], status="done", completed="2026-09-17T12:30:00Z")
    rec = se.read_task(root, "ai-000001")
    assert rec.status == "doing"  # the root copy is read first; status is informational
    assert [n.text for n in rec.notes] == ["started", "parked (waiting on user, review): look", "done"]
    assert rec.notes[0].harness_session == "codex:X1" and rec.notes[1].harness_session is None
    assert rec.notes[1].at_ms == ms(1200) and rec.notes[1].path == wt / "tasks" / "ai-000001.md" and rec.notes[1].line > 0
    assert rec.completed == [(ms(1800), wt / "tasks" / "ai-000001.md")]
    assert rec.started_ms is None
    assert rec.unreadable == []
    assert se.read_task(root, "ai-ffffff") is None


def test_note_kind():
    assert se.note_kind("started") == "start" and se.note_kind("resumed") == "start"
    assert se.note_kind("parked (waiting on user, review): x") == "park"
    assert se.note_kind("done") == "close" and se.note_kind("dropped") == "close"
    assert se.note_kind("completed; next due 2026-10-17") == "close"
    assert se.note_kind("Done with the thing") is None and se.note_kind("gate: verified") is None


# --- turns and continuation ----------------------------------------------------

def anchor_at(session, call_id):
    return next(i for i, e in enumerate(session.events) if e.kind == "tool_call" and e.call_id == call_id)


def test_claude_turn_completed_ends_at_last_assistant_text(tmp_path):
    s = se.read_claude(claude_file(tmp_path, [
        c_user("go", 0, "u1"),
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", "{}", 2, "u2"),
        c_assistant([text("Started; stopping here.")], 3, "a2"),
        c_user("Is it still running?", 600, "u3"),
        c_assistant([text("No.")], 601, "a3"),
    ]))
    t = se.turn_after(s, anchor_at(s, "toolu_1"))
    assert t.outcome == "completed" and t.ended_at == ms(3)
    nxt = se.next_human_after(s, t.end_index)
    assert nxt.text == "Is it still running?" and nxt.at_ms == ms(600)


def test_claude_turn_trailing_tool_result_is_unknown(tmp_path):
    s = se.read_claude(claude_file(tmp_path, [
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", "{}", 2, "u2"),
    ]))
    t = se.turn_after(s, anchor_at(s, "toolu_1"))
    assert t.outcome == "unknown" and t.ended_at == ms(1)
    assert se.next_human_after(s, t.end_index) is None


def test_claude_turn_pending_ask_is_wait_and_other_pending_is_unknown(tmp_path):
    ask = {"type": "tool_use", "id": "toolu_2", "name": "AskUserQuestion", "input": {"questions": []}}
    s = se.read_claude(claude_file(tmp_path, [
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", "{}", 2, "u2"),
        c_assistant([ask], 3, "a2"),
        c_user("answer", 30, "u3"),
    ]))
    assert se.turn_after(s, anchor_at(s, "toolu_1")).outcome == "wait"
    s2 = se.read_claude(claude_file(tmp_path, [
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", "{}", 2, "u2"),
        c_assistant([bash("toolu_2", "just check")], 3, "a2"),
    ], name="S2.jsonl"))
    assert se.turn_after(s2, anchor_at(s2, "toolu_1")).outcome == "unknown"


def test_claude_turn_interrupted(tmp_path):
    s = se.read_claude(claude_file(tmp_path, [
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", "{}", 2, "u2"),
        c_assistant([bash("toolu_2", "sleep 100")], 3, "a2"),
        c_user("[Request interrupted by user]", 4, "u3"),
        c_user("stop that", 5, "u4"),
    ]))
    t = se.turn_after(s, anchor_at(s, "toolu_1"))
    assert t.outcome == "interrupted"
    assert se.next_human_after(s, t.end_index).text == "stop that"


def test_codex_turn_outcomes(tmp_path):
    done = se.read_codex(codex_file(tmp_path, [
        x_meta(), x_event("task_started", 0), x_user("go", 0),
        x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 1),
        x_custom_out("c1", "{}", 2), x_assistant("ok", 3), x_event("task_complete", 4),
        x_event("task_started", 700, "t2"), x_user("still going?", 700),
    ]))
    t = se.turn_after(done, anchor_at(done, "c1"))
    assert t.outcome == "completed" and t.ended_at == ms(4)
    assert se.next_human_after(done, t.end_index).text == "still going?"

    aborted = se.read_codex(codex_file(tmp_path, [
        x_meta(), x_event("task_started", 0),
        x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 1),
        x_custom_out("c1", "{}", 2), x_event("turn_aborted", 3),
    ], name="rollout-b.jsonl"))
    assert se.turn_after(aborted, anchor_at(aborted, "c1")).outcome == "interrupted"

    waiting = se.read_codex(codex_file(tmp_path, [
        x_meta(), x_event("task_started", 0),
        x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 1),
        x_custom_out("c1", "{}", 2),
        x_func("c2", "request_user_input", "{}", 3),
    ], name="rollout-c.jsonl"))
    assert se.turn_after(waiting, anchor_at(waiting, "c1")).outcome == "wait"

    cut = se.read_codex(codex_file(tmp_path, [
        x_meta(), x_event("task_started", 0),
        x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 1),
        x_custom_out("c1", "{}", 2), x_assistant("mid", 3),
        x_event("task_started", 900, "t2"), x_assistant("later turn", 901), x_event("task_complete", 902, "t2"),
    ], name="rollout-d.jsonl"))
    t = se.turn_after(cut, anchor_at(cut, "c1"))
    assert t.outcome == "unknown" and t.ended_at == ms(3)


def fork_pair(tmp_path, divergent):
    shared = [
        c_user("go", 0, "u1"),
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", '{"id":"ai-000001","warnings":[]}', 2, "u2"),
        c_assistant([text("Started.")], 3, "a2"),
    ]
    original = shared + [c_user("still running?", 600, "u3")]
    if divergent:
        forked = [dict(r, sessionId="S2") for r in shared] + [c_user("different question", 600, "u9", sid="S2"),
                                                             c_assistant([text("...")], 601, "a9", sid="S2")]
    else:
        forked = [dict(r, sessionId="S2") for r in original] + [c_assistant([text("No.")], 601, "a3", sid="S2"),
                                                                 c_user("ok", 700, "u4", sid="S2")]
    a = se.read_claude(claude_file(tmp_path, original, name="S1.jsonl"))
    b = se.read_claude(claude_file(tmp_path, forked, name="S2.jsonl"))
    return a, b


def test_continuation_prefers_the_longer_compatible_fork(tmp_path):
    a, b = fork_pair(tmp_path, divergent=False)
    chosen = se.continuation([(a, anchor_at(a, "toolu_1")), (b, anchor_at(b, "toolu_1"))])
    assert chosen[0] is b


def test_continuation_is_none_when_forks_diverge_before_the_boundary(tmp_path):
    a, b = fork_pair(tmp_path, divergent=True)
    assert se.continuation([(a, anchor_at(a, "toolu_1")), (b, anchor_at(b, "toolu_1"))]) is None


# --- episodes ------------------------------------------------------------------

import os

ROOT_SESSION = "codex:X1"


def project(tmp_path, notes=(), status="doing", completed=None, task_id="ai-000001", started=None):
    root = git_repo(tmp_path / "proj-ai")
    task_file(root, list(notes), status=status, completed=completed, task_id=task_id, started=started)
    return {"ai": root}


def codex_story(tmp_path, *, start_out='{"id":"ai-000001","warnings":[]}\n', next_text="Is it still running?",
                extra=(), name="rollout-2026-09-17T12-00-00-X1.jsonl", start_cmd='text(await tools.exec_command({cmd:"tasks start ai-000001"}));'):
    recs = [x_meta(), x_event("task_started", 0), x_user("go", 0),
            x_custom("c1", start_cmd, 5), x_custom_out("c1", start_out, 6),
            x_assistant("Implementation is underway.", 60), x_event("task_complete", 60), *extra]
    if next_text:
        recs += [x_event("task_started", 660, "t2"), x_user(next_text, 660)]
    return se.read_codex(codex_file(tmp_path, recs, name=name))


def inputs(tmp_path, sessions, roots, now=ms(60) + 10 * 60 * 1000 + 1, labels=None, anchors=None, window_min=10,
           canonical=None):
    return se.Inputs(sessions, roots, labels or {}, anchors or {}, now, window_min * 60 * 1000, None, None,
                     canonical or {})


def test_episode_from_confirmed_start_no_park_status_question(tmp_path):
    s = codex_story(tmp_path)
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert cands == [] and len(eps) == 1
    e = eps[0]
    assert e["id"] == se.episode_id("codex", "c1", "ai-000001")
    assert e["task_id"] == "ai-000001" and e["session_key"] == "codex:X1"
    assert e["started_at"] == ms(5) and e["ended_at"] == ms(60)
    assert e["parked_at"] is None and e["closed_at"] is None and e["closure_source"] is None
    assert e["next_human_at"] == ms(660) and e["status_question"] is True and e["label_source"] == "heuristic"
    assert e["anchor_source"] == "result" and e["join_class"] == "inferred" and e["window_complete"] is True
    assert e["source_refs"][0].startswith("codex:X1:") and e["source_refs"][0].endswith("#L4")
    assert summary["episodes"] == 1 and summary["turns"]["completed"] == 1


def test_episode_uses_stamped_note_for_join_class_and_confirmation(tmp_path):
    s = codex_story(tmp_path, start_out="garbage\n")
    roots = project(tmp_path, notes=["- 2026-09-17T12:00:06Z (main): started",
                                     '  provenance: {"harness_session":"codex:X1","harness_session_source":"CODEX_SESSION_ID"}'])
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [s], roots))
    assert len(eps) == 1 and eps[0]["anchor_source"] == "note" and eps[0]["join_class"] == "stamped"


def test_discarded_output_is_a_candidate_with_the_stamp_as_a_hint(tmp_path):
    s = codex_story(tmp_path, start_cmd='text(await tools.exec_command({cmd:"tasks start ai-000001 >/dev/null && echo ok"}));', start_out="ok\n")
    roots = project(tmp_path, started="2026-09-17T12:00:07Z")
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [s], roots))
    assert eps == [] and cands[0]["reason"] == "outside-grammar" and cands[0]["stamp_delta_s"] == 2
    roots = project(tmp_path, started="2026-09-17T13:00:00Z")
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [s], roots))
    assert eps == [] and cands[0]["reason"] == "outside-grammar" and cands[0]["stamp_delta_s"] is None
    lone = codex_story(tmp_path, start_cmd='text(await tools.exec_command({cmd:"tasks start ai-000001"}));', start_out="", name="rollout-lone.jsonl")
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [lone], roots))
    assert eps == [] and cands[0]["reason"] == "no-id-line"


ID_LINE = '{"id":"ai-000001","warnings":[]}'


@pytest.mark.parametrize("case", ["pipe_file", "quoted_substitution", "chain_suffix", "chain_empty"])
def test_skipped_or_failed_start_is_not_an_episode(tmp_path, case):
    """The plan reviewer's regressions: a start that never ran, run through a bash stub so the
    output is exactly what the shell would produce, plus a record whose started: stamp and
    another session's note agree on the time."""
    saved = tmp_path / "saved.jsonl"
    saved.write_text((ID_LINE + "\n") * 2)
    commands = {
        "pipe_file": f"false && tasks start ai-000001; tasks note ai-000001 checked | head -n 2 {saved}",
        "quoted_substitution": 'false && tasks start ai-000001; echo "$(tasks note ai-000001 checked | sed p)"',
        "chain_suffix": "tasks start ai-000001 >/dev/null 2>&1 && true; printf 'after\\n'",
        "chain_empty": "tasks start ai-000001 >/dev/null 2>&1 && printf success",
    }
    stub = ("tasks() { if [ \"$1\" = start ]; then printf 'error: claimed by another session\\n' >&2; return 1; fi; "
            "printf '%s\\n' '" + ID_LINE + "'; }\n")
    command = commands[case]
    result = subprocess.run(["bash", "-c", stub + command], capture_output=True, text=True)
    assert result.stderr == ""
    session = codex_story(tmp_path, start_cmd="text(await tools.exec_command({cmd:" + json.dumps(command) + "}));", start_out=result.stdout)
    roots = project(tmp_path, started="2026-09-17T12:00:05Z", notes=[
        "- 2026-09-17T12:00:05Z (main): started",
        '  provenance: {"harness_session":"codex:OTHER","harness_session_source":"CODEX_SESSION_ID"}',
    ])
    episodes, _, _ = se.build_episodes(inputs(tmp_path, [session], roots))
    assert episodes == [], [(e["task_id"], e["anchor_source"]) for e in episodes]


@pytest.mark.parametrize("case", ["standalone_reader", "grep_explicit_pattern", "numeric_filename", "quoted_task_id"])
def test_output_from_elsewhere_does_not_confirm_skipped_start(tmp_path, case):
    """Round-4 regressions: id lines that came from a file, a filter's file operand, or a
    quoted task id the counter used to miss."""
    (tmp_path / "saved.jsonl").write_text((ID_LINE + "\n") * 2)
    (tmp_path / "123").write_text((ID_LINE + "\n") * 2)
    commands = {
        "standalone_reader": "false && tasks start ai-000001; cat saved.jsonl",
        "grep_explicit_pattern": "false && tasks start ai-000001; tasks note ai-000001 checked | grep -e id saved.jsonl",
        "numeric_filename": "false && tasks start ai-000001; tasks note ai-000001 checked | head 123",
        "quoted_task_id": 'false && tasks start ai-000001; tasks note "ai-000001" checked',
    }
    stub = "tasks() { if [ \"$1\" = start ]; then return 1; fi; printf '%s\\n' '" + ID_LINE + "'; }\n"
    command = commands[case]
    result = subprocess.run(["bash", "-c", stub + command], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and result.stderr == ""
    session = codex_story(tmp_path, start_cmd="text(await tools.exec_command({cmd:" + json.dumps(command) + "}));", start_out=result.stdout)
    episodes, _, _ = se.build_episodes(inputs(tmp_path, [session], project(tmp_path)))
    assert episodes == [], [(e["task_id"], e["anchor_source"]) for e in episodes]


def test_concatenated_wrapper_command_requires_review(tmp_path):
    """Round-6: a literal prefix of a run-time-assembled command is not the command."""
    (tmp_path / "saved.jsonl").write_text(ID_LINE + "\n")
    prefix, suffix = "tasks start ai-000001", " >/dev/null 2>&1; cat saved.jsonl"
    result = subprocess.run(["bash", "-c", "tasks() { return 1; }\n" + prefix + suffix], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == ID_LINE + "\n"
    js = "text(await tools.exec_command({cmd:" + json.dumps(prefix) + " + " + json.dumps(suffix) + "}));"
    session = codex_story(tmp_path, start_cmd=js, start_out=result.stdout)
    episodes, candidates, summary = se.build_episodes(inputs(tmp_path, [session], project(tmp_path)))
    assert episodes == [] and len(candidates) == 1 and candidates[0]["reason"] == "unsupported-wrapper"


def test_expansion_in_the_dash_c_argument_is_not_readable(tmp_path):
    """Round-8: a substitution anywhere in the invocation can print into the captured output."""
    (tmp_path / "saved.jsonl").write_text(ID_LINE + "\n")
    command = 'tasks -C "$(cat saved.jsonl >&2)" start ai-000001 2>/dev/null'
    result = subprocess.run(["bash", "-c", "tasks() { return 1; }\n" + command], cwd=tmp_path,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert result.stdout == ID_LINE + "\n"
    session = codex_story(tmp_path, start_cmd="text(await tools.exec_command({cmd:" + json.dumps(command) + "}));", start_out=result.stdout)
    episodes, candidates, _ = se.build_episodes(inputs(tmp_path, [session], project(tmp_path)))
    assert episodes == [] and candidates[0]["reason"] == "outside-grammar"


def test_one_extracted_literal_does_not_prove_one_executed_command(tmp_path):
    """Round-7: the wrapper skips the start and runs `cat`; only the whole-wrapper form may be read."""
    source = ('const cmd = "cat saved.jsonl";\n'
              'if (false) { await tools.exec_command({cmd: "tasks start ai-000001"}); }\n'
              'text(await tools.exec_command({cmd}));')
    session = codex_story(tmp_path, start_cmd=source, start_out=ID_LINE + "\n")
    episodes, candidates, _ = se.build_episodes(inputs(tmp_path, [session], project(tmp_path)))
    assert episodes == [] and candidates[0]["reason"] == "outside-grammar"


@pytest.mark.parametrize("command", ['tasks start "ai-000001"', "tasks --pretty start ai-000001", "tasks -C /w start ai-000001"])
def test_supported_start_forms_are_discovered_and_confirmed(tmp_path, command):
    out = "ai-000001\n" if "--pretty" in command else OK
    session = codex_story(tmp_path, start_cmd="text(await tools.exec_command({cmd:" + json.dumps(command) + "}));", start_out=out)
    episodes, candidates, summary = se.build_episodes(inputs(tmp_path, [session], project(tmp_path)))
    assert len(episodes) == 1 and episodes[0]["anchor_source"] == "result", (candidates, summary)


@pytest.mark.parametrize("case", ["assignment_prefix", "printf_format", "grep_long_option", "stderr_is_captured"])
def test_shell_tricks_do_not_confirm_skipped_start(tmp_path, case):
    """Round-5 regressions: an assignment-prefixed reader, a printf that formats an id
    object, a long-option file operand, and stdout sent to a captured stderr."""
    (tmp_path / "saved.jsonl").write_text((ID_LINE + "\n") * 2)
    commands = {
        "assignment_prefix": "cd absent-dir && tasks start ai-000001; MODE=x cat saved.jsonl",
        "printf_format": "cd absent-dir && tasks start ai-000001; printf '{\"%s\":\"%s-%s\",\"warnings\":[]}\\n' id ai 000001",
        "grep_long_option": "cd absent-dir && tasks start ai-000001; tasks note ai-000001 checked | grep --regexp=id saved.jsonl",
        "stderr_is_captured": "cd absent-dir && tasks start ai-000001; tasks note ai-000001 checked >&2",
    }
    stub = "tasks() { if [ \"$1\" = start ]; then return 1; fi; printf '%s\\n' '" + ID_LINE + "'; }\n"
    command = commands[case]
    result = subprocess.run(["bash", "-c", stub + command], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert result.returncode == 0
    session = codex_story(tmp_path, start_cmd="text(await tools.exec_command({cmd:" + json.dumps(command) + "}));", start_out=result.stdout)
    episodes, _, _ = se.build_episodes(inputs(tmp_path, [session], project(tmp_path)))
    assert episodes == [], [(e["task_id"], e["anchor_source"]) for e in episodes]


def test_a_failed_start_is_never_confirmed_by_the_records_timing(tmp_path):
    s = codex_story(tmp_path, start_cmd='text(await tools.exec_command({cmd:"tasks start ai-000001 >/dev/null && ls"}));',
                    start_out="error: claimed by another session\n")
    roots = project(tmp_path, started="2026-09-17T12:00:05Z",
                    notes=["- 2026-09-17T12:00:05Z (main): started",
                           '  provenance: {"harness_session":"codex:OTHER","harness_session_source":"CODEX_SESSION_ID"}'])
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], roots))
    assert eps == [] and cands[0]["reason"] == "error-output" and summary["unconfirmed"]["error-output"] == 1


def test_nested_start_is_a_review_only_candidate(tmp_path):
    js = "tools.exec_command({cmd:\"bash <<'EOF'\\ntasks start ai-000001\\nEOF\"})"
    s = codex_story(tmp_path, start_cmd=js)
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path, started="2026-09-17T12:00:05Z")))
    assert eps == [] and cands[0]["reason"] == "nested" and summary["unconfirmed"]["nested"] == 1
    cid = cands[0]["id"]
    call = next(e for e in s.events if e.kind == "tool_call" and e.call_id == "c1")
    result = next(e for e in s.events if e.kind == "tool_result" and e.call_id == "c1")
    anchors = {cid: {"id": cid, "confirmed": True, "evidence_digest": se.digest("\n".join(call.commands) + call.raw + "\n" + result.text), "confirmed_at": "x"}}
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [s], project(tmp_path), anchors=anchors))
    assert len(eps) == 1 and eps[0]["anchor_source"] == "reviewed"


def test_unconfirmed_start_becomes_candidate_with_reason(tmp_path):
    s = codex_story(tmp_path, start_out="error\n")
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert eps == [] and len(cands) == 1
    assert cands[0]["reason"] == "no-id-line" and cands[0]["id"] == se.episode_id("codex", "c1", "ai-000001")
    assert cands[0]["sessions"] == ["codex:X1"] and summary["unconfirmed"]["no-id-line"] == 1


def test_lit_shape_is_a_candidate_then_a_reviewed_anchor(tmp_path):
    out = '{"id":"lit-f43833","warnings":[]}\n\n\n/w\n M x\n\n\nfoo\n'
    s = codex_story(tmp_path, start_cmd=LIT_JS, start_out=out)
    roots = {"lit": git_repo(tmp_path / "proj-lit")}
    task_file(roots["lit"], [], task_id="lit-f43833")
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [s], roots))
    assert eps == [] and cands[0]["reason"] == "outside-grammar"
    cid = cands[0]["id"]
    call = next(e for e in s.events if e.kind == "tool_call" and e.call_id == "c1")
    result = next(e for e in s.events if e.kind == "tool_result" and e.call_id == "c1")
    evidence = se.digest("\n".join(call.commands) + call.raw + "\n" + result.text)
    anchors = {cid: {"id": cid, "confirmed": True, "evidence_digest": evidence, "confirmed_at": "x"}}
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], roots, anchors=anchors))
    assert len(eps) == 1 and eps[0]["anchor_source"] == "reviewed" and cands == []
    anchors[cid]["evidence_digest"] = "000000000000"
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], roots, anchors=anchors))
    assert eps == [] and summary["stale_confirmations"] == 1
    anchors[cid] = {"id": cid, "confirmed": False, "evidence_digest": evidence, "confirmed_at": "x"}
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [s], roots, anchors=anchors))
    assert eps == [] and cands == []


def test_unsupported_wrapper_is_a_candidate_when_the_result_names_the_task(tmp_path):
    js = "const id='ai-000001'; tools.exec_command({cmd:`tasks start ${id}`})"
    s = codex_story(tmp_path, start_cmd=js)
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert eps == [] and len(cands) == 1 and cands[0]["reason"] == "unsupported-wrapper"
    assert cands[0]["task_id"] == "ai-000001" and summary["unconfirmed"]["unsupported-wrapper"] == 1
    roots = project(tmp_path, notes=["- 2026-09-17T12:00:06Z (main): started",
                                     '  provenance: {"harness_session":"codex:X1","harness_session_source":"CODEX_SESSION_ID"}'])
    eps, cands, _ = se.build_episodes(inputs(tmp_path, [s], roots))
    assert len(eps) == 1 and eps[0]["anchor_source"] == "note" and cands == []
    blind = codex_story(tmp_path, start_cmd=js, start_out="nothing useful\n", name="rollout-blind.jsonl")
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [blind], project(tmp_path)))
    assert eps == [] and cands == [] and summary["unsupported_unknown_task"] == 1


def test_two_starts_of_one_task_in_one_turn_collapse_to_the_first(tmp_path):
    recs = [x_meta(), x_event("task_started", 0), x_user("go", 0),
            x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 5),
            x_custom_out("c1", '{"id":"ai-000001","warnings":[]}\n', 6),
            x_custom("c2", 'text(await tools.exec_command({cmd:"tasks start --force ai-000001"}));', 20),
            x_custom_out("c2", '{"id":"ai-000001","warnings":["took over"]}\n', 21),
            x_assistant("ok", 60), x_event("task_complete", 60),
            x_event("task_started", 700, "t2"), x_user("resume", 700),
            x_custom("c3", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 705),
            x_custom_out("c3", '{"id":"ai-000001","warnings":[]}\n', 706),
            x_assistant("ok", 720), x_event("task_complete", 720, "t2")]
    s = se.read_codex(codex_file(tmp_path, recs))
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path), now=ms(720) + 10 * 60 * 1000 + 1))
    assert [e["started_at"] for e in eps] == [ms(5), ms(705)] and summary["anchors_collapsed"] == 1


def test_only_completed_turns_are_written(tmp_path):
    recs = [x_meta(), x_event("task_started", 0), x_user("go", 0),
            x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 5),
            x_custom_out("c1", '{"id":"ai-000001","warnings":[]}\n', 6), x_event("turn_aborted", 7)]
    s = se.read_codex(codex_file(tmp_path, recs))
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert eps == [] and cands == [] and summary["turns"]["interrupted"] == 1


def test_park_and_close_sources_earliest_wins(tmp_path):
    s = codex_story(tmp_path)
    roots = project(tmp_path, notes=["- 2026-09-17T12:03:00Z (main): parked (waiting on user, review): look"])
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    assert e["parked_at"] == ms(180)
    roots = project(tmp_path, notes=["- 2026-09-17T12:30:00Z (main): done"], status="done", completed="2026-09-17T13:00:00Z")
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    assert e["closed_at"] == ms(1800) and e["closure_source"] == "note"
    roots = project(tmp_path, status="done", completed="2026-09-17T13:00:00Z")
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    assert e["closed_at"] == ms(3600) and e["closure_source"] == "stamp"
    roots = project(tmp_path, notes=["- 2026-09-17T12:30:00Z (main): dropped"])
    assert se.build_episodes(inputs(tmp_path, [s], roots))[0][0]["closed_at"] == ms(1800)


def test_transcript_close_without_note_is_recorded_at_result_time(tmp_path):
    extra = [x_event("task_started", 100, "t2"), x_user("finish it", 100),
             x_custom("c2", 'text(await tools.exec_command({cmd:"tasks done ai-000001 landed"}));', 120),
             x_custom_out("c2", '{"id":"ai-000001","warnings":[]}\n', 130), x_event("task_complete", 131, "t2")]
    s = codex_story(tmp_path, extra=extra, next_text=None)
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    e = eps[0]
    assert e["closed_at"] == ms(130) and e["closure_source"] == "transcript"
    assert e["next_human_at"] == ms(100)
    assert summary["note_missing"] == 1


def test_uncertain_early_park_is_not_hidden_by_a_later_definite_one(tmp_path):
    # call 1's result arrived 660 s after the call (the harness yielded late), so it could have
    # parked anywhere in [120, 780]; call 2 definitely parked at ~705 (its note).
    extra = [x_event("task_started", 100, "t2"), x_user("park it later", 100),
             x_custom("c2", 'text(await tools.exec_command({cmd:"tasks park ai-000001 a"}));', 120),
             x_custom_out("c2", '{"id":"ai-000001","warnings":[]}\n', 780),
             x_custom("c3", 'text(await tools.exec_command({cmd:"tasks park ai-000001 b"}));', 700),
             x_custom_out("c3", '{"id":"ai-000001","warnings":[]}\n', 710), x_event("task_complete", 781, "t2")]
    s = codex_story(tmp_path, extra=extra, next_text=None)
    roots = project(tmp_path, notes=["- 2026-09-17T12:11:45Z (main): parked (waiting on user): b"])
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    assert e["parked_at"] == ms(705) and e["window_complete"] is False  # the note belongs to call 2; call 1 stays open
    roots = project(tmp_path, notes=["- 2026-09-17T12:11:45Z (main): parked (waiting on user): b",
                                     "- 2026-09-17T12:05:00Z (main): parked (waiting on user): a"])
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    assert e["parked_at"] == ms(300) and e["window_complete"] is True  # call 1 now has its own note, inside N


def test_completion_stamp_only_in_a_worktree_copy_is_found(tmp_path):
    s = codex_story(tmp_path)
    roots = project(tmp_path)
    wt = tmp_path / "proj-ai-wt"
    subprocess.run(["git", "-C", str(roots["ai"]), "worktree", "add", "-q", str(wt), "-b", "wt"], check=True)
    task_file(wt, [], status="done", completed="2026-09-17T12:30:00Z")
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    assert e["closed_at"] == ms(1800) and e["closure_source"] == "stamp"


def test_copied_transition_in_a_fork_does_not_break_sorting(tmp_path):
    a, b = fork_pair(tmp_path, divergent=False)
    extra_a = [c_assistant([bash("toolu_5", "tasks park ai-000001 later")], 800, "a5"),
               c_result("toolu_5", '{"id":"ai-000001","warnings":[]}', 801, "u5"),
               c_assistant([text("parked")], 802, "a6")]
    a = se.read_claude(claude_file(tmp_path, [json.loads(l) for l in a.path.read_text().splitlines()] + extra_a, name="S1.jsonl"))
    b = se.read_claude(claude_file(tmp_path, [json.loads(l) for l in b.path.read_text().splitlines()] + [dict(r, sessionId="S2") for r in extra_a], name="S2.jsonl"))
    eps, _, summary = se.build_episodes(inputs(tmp_path, [a, b], project(tmp_path)))
    assert eps[0]["parked_at"] == ms(801) and summary["note_missing"] == 1


def test_session_from_an_unregistered_cwd_still_yields_an_episode(tmp_path):
    recs = [dict(x_meta(), payload=dict(x_meta()["payload"], cwd="/tmp")), x_event("task_started", 0), x_user("go", 0),
            x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 5),
            x_custom_out("c1", '{"id":"ai-000001","warnings":[]}\n', 6), x_assistant("ok", 60), x_event("task_complete", 60)]
    s = se.read_codex(codex_file(tmp_path, recs))
    eps, _, _ = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert len(eps) == 1  # ownership is the task's prefix, not the shell's cwd (spec §4.1, revised at plan review)


def test_transcript_transition_straddling_the_cutoff_makes_window_incomplete(tmp_path):
    extra = [x_event("task_started", 100, "t2"), x_user("park it later", 100),
             x_custom("c2", 'text(await tools.exec_command({cmd:"tasks park ai-000001 later"}));', 120),
             x_custom_out("c2", '{"id":"ai-000001","warnings":[]}\n', 780), x_event("task_complete", 781, "t2")]
    s = codex_story(tmp_path, extra=extra, next_text=None)
    e = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))[0][0]
    assert e["parked_at"] == ms(780) and e["window_complete"] is False


def test_note_inside_call_interval_supplies_the_time(tmp_path):
    extra = [x_event("task_started", 100, "t2"), x_user("park it", 100),
             x_custom("c2", 'text(await tools.exec_command({cmd:"tasks park ai-000001 later"}));', 120),
             x_custom_out("c2", '{"id":"ai-000001","warnings":[]}\n', 151), x_event("task_complete", 152, "t2")]
    s = codex_story(tmp_path, extra=extra, next_text=None)
    roots = project(tmp_path, notes=["- 2026-09-17T12:02:30Z (main): parked (waiting on user): later"])
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    assert e["parked_at"] == ms(150) and e["window_complete"] is True


def test_window_false_when_extraction_is_inside_n_or_a_copy_is_unreadable(tmp_path):
    s = codex_story(tmp_path)
    roots = project(tmp_path)
    assert se.build_episodes(inputs(tmp_path, [s], roots, now=ms(60) + 5 * 60 * 1000))[0][0]["window_complete"] is False
    gone = tmp_path / "gone"
    subprocess.run(["git", "-C", str(roots["ai"]), "worktree", "add", "-q", str(gone), "-b", "gone"], check=True)
    import shutil
    shutil.rmtree(gone)
    assert se.build_episodes(inputs(tmp_path, [s], roots))[0][0]["window_complete"] is False


def test_missing_record_is_unknown_join_and_unregistered_prefix_is_counted(tmp_path):
    s = codex_story(tmp_path)
    roots = {"ai": git_repo(tmp_path / "proj-empty")}
    (roots["ai"] / "tasks").mkdir()
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], roots))
    assert eps[0]["join_class"] == "unknown" and eps[0]["window_complete"] is False
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], {}))
    assert eps == [] and cands == [] and summary["unregistered"] == 1


def test_labels_heuristic_reviewed_and_stale(tmp_path):
    s = codex_story(tmp_path, next_text="Please also add a README section.")
    eps, _, _ = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert eps[0]["status_question"] is False
    eid = eps[0]["id"]
    labels = {eid: {"id": eid, "status_question": True, "message_digest": se.digest("Please also add a README section."), "labelled_at": "x"}}
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path), labels=labels))
    assert eps[0]["status_question"] is True and eps[0]["label_source"] == "reviewed"
    labels[eid]["message_digest"] = "000000000000"
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path), labels=labels))
    assert eps[0]["label_source"] == "heuristic" and summary["stale_labels"] == 1
    s2 = codex_story(tmp_path, next_text=None, name="rollout-e.jsonl")
    assert se.build_episodes(inputs(tmp_path, [s2], project(tmp_path)))[0][0]["status_question"] is None


@pytest.mark.parametrize("text,expected", [
    ("Is the task still running?", True), ("still executing?", True), ("What's the status?", True),
    ("Where are we?", True), ("did it finish?", True), ("Are you still working on it?", True),
    ("What's left?", True), ("Any progress?", True),
    ("Great, now add tests for the parser.", False), ("Looks good.", False),
    # from the labelled baseline: misses the first list lacked
    ("Did it get stuck?", True), ("Is `mind6` currently executing? Or do you need me to do anything?", True),
    ("How are things progressing?", True), ("What is the current status of the run?", True),
    # from the labelled baseline: false positives of the bare words
    ("Run git status and commit.", False), ("The progress bar is broken.", False),
    ("systemctl --user status work-link.service", False), ("What's next?", False),
    ("**P1** the status field is never cleared; progress is lost on restart.", False),
])
def test_heuristic_patterns(text, expected):
    assert se.heuristic_label(text) is expected


def test_fork_keeps_id_and_label_nulls_session_key_without_stamp(tmp_path):
    a, b = fork_pair(tmp_path, divergent=False)
    roots = project(tmp_path)
    eid = se.episode_id("claude-code", "toolu_1", "ai-000001")
    labels = {eid: {"id": eid, "status_question": False, "message_digest": se.digest("still running?"), "labelled_at": "x"}}
    eps, _, summary = se.build_episodes(inputs(tmp_path, [a, b], roots, labels=labels))
    assert len(eps) == 1 and eps[0]["id"] == eid
    assert eps[0]["session_key"] is None and eps[0]["join_class"] == "unknown" and summary["origin_unknown"] == 1
    assert eps[0]["label_source"] == "reviewed" and eps[0]["status_question"] is False
    assert sum(1 for r in eps[0]["source_refs"] if "S2.jsonl" in r) >= 1 and any("S1.jsonl" in r for r in eps[0]["source_refs"])
    assert summary["anchors_multi_file"] == 1
    roots = project(tmp_path, notes=["- 2026-09-17T12:00:02Z (main): started",
                                     '  provenance: {"harness_session":"claude-code:S1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}'])
    eps, _, _ = se.build_episodes(inputs(tmp_path, [a, b], roots))
    assert eps[0]["session_key"] == "claude-code:S1" and eps[0]["join_class"] == "stamped"


def test_divergent_fork_is_ambiguous_and_unwritten(tmp_path):
    a, b = fork_pair(tmp_path, divergent=True)
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [a, b], project(tmp_path)))
    assert eps == [] and summary["turns"]["ambiguous"] == 1


def test_population_exclusions_and_determinism(tmp_path):
    sub = se.read_codex(codex_file(tmp_path, [x_meta(thread_source="subagent"), x_event("task_started", 0),
                                              x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 1),
                                              x_custom_out("c1", '{"id":"ai-000001","warnings":[]}\n', 2),
                                              x_event("task_complete", 3)], name="rollout-sub.jsonl"))
    exec_ = se.read_codex(codex_file(tmp_path, [x_meta(originator="codex_exec_batch"), x_event("task_started", 0),
                                                x_custom("c9", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 1),
                                                x_custom_out("c9", '{"id":"ai-000001","warnings":[]}\n', 2),
                                                x_event("task_complete", 3)], name="rollout-exec.jsonl"))
    s = codex_story(tmp_path)
    args = inputs(tmp_path, [sub, exec_, s], project(tmp_path))
    first = se.build_episodes(args)
    second = se.build_episodes(args)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first[2]["excluded"] == {"subagent": 1, "non-interactive": 1} and len(first[0]) == 1

def test_previous_episode_note_cannot_erase_later_confirmed_park(tmp_path):
    roots = project(tmp_path, notes=[
        '- 2026-09-17T12:00:00Z (main): parked (waiting on user): previous episode'
    ])
    extra = [x_event('task_started', 100, 't2'), x_user('park it', 100),
             x_custom('c2', 'text(await tools.exec_command({cmd:"tasks park ai-000001 later"}));', 110),
             x_custom_out('c2', '{"id":"ai-000001","warnings":[]}\n', 111),
             x_event('task_complete', 112, 't2')]
    session = codex_story(tmp_path, extra=extra, next_text=None)
    episodes, _, _ = se.build_episodes(inputs(tmp_path, [session], roots))
    assert episodes[0]['parked_at'] == ms(111)


def test_resume_copy_can_supply_start_result_missing_from_original(tmp_path):
    roots = project(tmp_path)
    head = [c_user('go', 0, 'u1'),
            c_assistant([bash('toolu_1', 'tasks start ai-000001')], 5, 'a1')]
    short = se.read_claude(claude_file(tmp_path, head, name='a-short.jsonl'))
    tail = [c_result('toolu_1', '{"id":"ai-000001","warnings":[]}', 6, 'r1'),
            c_assistant([text('done')], 60, 'a2'), c_user('still running?', 660, 'u2')]
    long = se.read_claude(claude_file(tmp_path, [dict(r, sessionId='S2') for r in head + tail], name='b-long.jsonl'))
    episodes, candidates, _ = se.build_episodes(inputs(tmp_path, [short, long], roots))
    assert len(episodes) == 1 and not candidates
    reversed_episodes, _, _ = se.build_episodes(inputs(tmp_path, [long, short], roots))
    assert episodes == reversed_episodes


def test_pipe_stderr_cannot_confirm_failed_start(tmp_path):
    saved = tmp_path / 'saved.jsonl'
    saved.write_text(OK)
    command = f'tasks start ai-000001 |& cat {saved}'
    result = subprocess.run(['bash', '-c', 'tasks() { return 1; }\n' + command], capture_output=True, text=True)
    assert result.stdout == OK
    s = codex_story(tmp_path, start_cmd='text(await tools.exec_command({cmd:' + json.dumps(command) + '}));', start_out=result.stdout)
    eps, candidates, _ = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert eps == [], (se.single_invocation(command), eps)


def test_nonshell_tool_does_not_create_start(tmp_path):
    records = [x_meta(), x_event('task_started', 0), x_user('go', 0),
               x_func('c1', 'validate_command', json.dumps({'cmd':'tasks start ai-000001'}), 1),
               x_func_out('c1', OK, 2), x_assistant('validated', 3), x_event('task_complete', 4)]
    s = se.read_codex(codex_file(tmp_path, records))
    eps, candidates, _ = se.build_episodes(inputs(tmp_path, [s], project(tmp_path)))
    assert eps == [], eps


def test_claude_thinking_tail_is_not_completed(tmp_path):
    records = [c_user('go', 0, 'u1'), c_assistant([bash('c1','tasks start ai-000001')],1,'a1'),
               c_result('c1',OK,2,'u2'), c_assistant([{'type':'thinking','thinking':'Still evaluating the next step.'}],3,'a2')]
    s = se.read_claude(claude_file(tmp_path, records))
    turn = se.turn_after(s, anchor_at(s, 'c1'))
    assert turn.outcome == 'unknown', turn


def test_claude_string_assistant_text_completes_the_turn(tmp_path):
    records = [c_user("go", 0, "u1"), c_assistant([bash("c1", "tasks start ai-000001")], 1, "a1"),
               c_result("c1", OK, 2, "u2"), c_assistant("Done.", 3, "a2")]
    session = se.read_claude(claude_file(tmp_path, records))
    assert session.events[-1].text == "Done."
    assert se.turn_after(session, anchor_at(session, "c1")).outcome == "completed"


def test_claude_mixed_result_and_human_text_preserves_human(tmp_path):
    r = c_result('c1', OK, 2, 'u2')
    r['message']['content'].append(text('Is it still running?'))
    s = se.read_claude(claude_file(tmp_path, [r]))
    assert [e.kind for e in s.events] == ['tool_result','human'], s.events



# --- CLI -----------------------------------------------------------------------

def run_cli(argv, env):
    import io, contextlib
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = se.main(argv, env)
    return code, out.getvalue(), err.getvalue()


def cli_env(tmp_path, roots, aliases=None):
    cfg = tmp_path / "cfg" / "tasks"
    cfg.mkdir(parents=True, exist_ok=True)
    text = "[projects]\n" + "".join(f'{k} = "{v}"\n' for k, v in roots.items())
    if aliases:
        text += "[aliases]\n" + "".join(f'{k} = "{v}"\n' for k, v in aliases.items())
    (cfg / "projects.toml").write_text(text)
    return {"XDG_CONFIG_HOME": str(tmp_path / "cfg"), "SESSION_LOGS_CLAUDE": str(tmp_path / "claude"),
            "SESSION_LOGS_CODEX": str(tmp_path / "codex"), "HOME": str(tmp_path)}


def test_extract_writes_episodes_candidates_and_summary(tmp_path):
    codex_story(tmp_path)  # writes the rollout file
    roots = project(tmp_path)
    out = tmp_path / "ep" / "episodes.jsonl"
    code, stdout, stderr = run_cli(["extract", "--out", str(out)], cli_env(tmp_path, roots))
    assert code == 0 and stdout == ""
    summary = json.loads(stderr)
    assert summary["episodes"] == 1 and summary["files"] == {"codex": 1}
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert rows[0]["task_id"] == "ai-000001" and "text" not in rows[0]
    assert (tmp_path / "ep" / "episodes.candidates.jsonl").read_text() == ""


def test_show_confirm_label_round_trip(tmp_path):
    s = codex_story(tmp_path, start_cmd=LIT_JS, start_out='{"id":"lit-f43833","warnings":[]}\n\nfoo\n')
    roots = {"lit": git_repo(tmp_path / "proj-lit")}
    task_file(roots["lit"], [], task_id="lit-f43833")
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    cand = json.loads((tmp_path / "episodes.candidates.jsonl").read_text().splitlines()[0])
    code, stdout, _ = run_cli(["show", cand["id"], "--episodes", str(out)], env)
    assert code == 0 and "kind: candidate" in stdout and "tasks start lit-f43833" in stdout and "-- result" in stdout
    assert run_cli(["confirm", cand["id"], "yes", "--episodes", str(out)], env)[0] == 0
    anchors = [json.loads(l) for l in (tmp_path / "episodes.anchors.jsonl").read_text().splitlines()]
    assert anchors[0]["id"] == cand["id"] and anchors[0]["confirmed"] is True and len(anchors[0]["evidence_digest"]) == 12
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    ep = json.loads(out.read_text().splitlines()[0])
    assert ep["anchor_source"] == "reviewed" and ep["status_question"] is True
    code, stdout, _ = run_cli(["show", ep["id"], "--episodes", str(out)], env)
    assert code == 0 and "kind: episode" in stdout and "Is it still running?" in stdout
    assert run_cli(["label", ep["id"], "no", "--episodes", str(out)], env)[0] == 0
    label = json.loads((tmp_path / "episodes.labels.jsonl").read_text().splitlines()[0])
    assert label["status_question"] is False and label["message_digest"] == se.digest("Is it still running?")
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    ep = json.loads(out.read_text().splitlines()[0])
    assert ep["status_question"] is False and ep["label_source"] == "reviewed"


def test_show_picks_the_call_behind_the_episode_not_the_first_on_the_line(tmp_path):
    roots = project(tmp_path)
    claude_file(tmp_path, [
        c_user("go", 0, "u1"),
        c_assistant([bash("toolu_0", "tasks show ai-000001"), bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_0", '{"task":{"id":"ai-000001"}}', 2, "u2"),
        c_result("toolu_1", '{"id":"ai-000001","warnings":[]}', 2, "u3"),
        c_assistant([text("Started.")], 3, "a2"),
        c_user("status?", 700, "u4"),
    ])
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    ep = json.loads(out.read_text().splitlines()[0])
    assert ep["id"] == se.episode_id("claude-code", "toolu_1", "ai-000001")
    code, stdout, _ = run_cli(["show", ep["id"], "--episodes", str(out)], env)
    assert code == 0 and "tasks start ai-000001" in stdout.split("-- anchor commands")[1].split("-- result")[0]
    assert "tasks show" not in stdout.split("-- anchor commands")[1].split("-- result")[0]


def test_candidate_confirmation_uses_the_compatible_continuation(tmp_path):
    head = [c_user("go", 0, "u1"),
            c_assistant([bash("toolu_1", "tasks start ai-000001 && pwd")], 5, "a1")]
    claude_file(tmp_path, head, name="a-short.jsonl")
    tail = [c_result("toolu_1", OK, 6, "r1"), c_assistant([text("done")], 60, "a2"),
            c_user("still running?", 660, "u2")]
    claude_file(tmp_path, [dict(r, sessionId="S2") for r in head + tail], name="b-long.jsonl")
    env = cli_env(tmp_path, project(tmp_path))
    out = tmp_path / "episodes.jsonl"
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    candidate = json.loads(se.sidecar(out, "candidates").read_text())
    assert "b-long.jsonl" in candidate["source_refs"][0]
    code, shown, _ = run_cli(["show", candidate["id"], "--episodes", str(out)], env)
    assert code == 0 and OK.strip() in shown
    assert run_cli(["confirm", candidate["id"], "yes", "--episodes", str(out)], env)[0] == 0
    code, _, summary = run_cli(["extract", "--out", str(out)], env)
    assert code == 0 and json.loads(summary)["stale_confirmations"] == 0
    assert json.loads(out.read_text())["anchor_source"] == "reviewed"


def test_cli_errors(tmp_path):
    roots = project(tmp_path)
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    codex_story(tmp_path)
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    code, _, err = run_cli(["show", "nope00000000", "--episodes", str(out)], env)
    assert code == 2 and "nope00000000" in err
    code, _, err = run_cli(["label", "nope00000000", "yes", "--episodes", str(out)], env)
    assert code == 2
    (tmp_path / "episodes.labels.jsonl").write_text("not json\n")
    code, _, err = run_cli(["extract", "--out", str(out)], env)
    assert code == 2 and "labels.jsonl" in err and ":1" in err
    (tmp_path / "episodes.labels.jsonl").unlink()
    (roots["ai"] / "tasks").rename(roots["ai"] / "tasks-gone")
    code, _, err = run_cli(["extract", "--out", str(out)], env)
    assert code == 2 and "tasks" in err


def test_since_and_project_filters(tmp_path):
    codex_story(tmp_path)
    roots = project(tmp_path)
    roots["zz"] = git_repo(tmp_path / "proj-zz")
    (roots["zz"] / "tasks").mkdir()
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    assert run_cli(["extract", "--out", str(out), "--project", "zz"], env)[0] == 0
    assert out.read_text() == ""
    assert run_cli(["extract", "--out", str(out), "--since", "0"], env)[0] == 0
    assert out.read_text() == ""


# --- review round 10: pasted turns, refs, counters, error paths -----------------

PASTE = '<pasted_content id="7ce0">\nReview findings:\n- fix the parser\n</pasted_content id="7ce0">\n\nIs it still running?'


def test_pasted_content_turn_is_human_without_its_wrapper_tags(tmp_path):
    s = se.read_claude(claude_file(tmp_path, [
        c_user(PASTE, 0, "u1"),
        c_user('<pasted_content id="1">\nonly a paste\n</pasted_content id="1">', 1, "u2"),
        c_user("<system-reminder>x</system-reminder>", 2, "u3"),
    ]))
    assert [e.kind for e in s.events] == ["human", "human"]
    assert s.events[0].text == "Review findings:\n- fix the parser\n\nIs it still running?"
    assert s.events[1].text == "only a paste"


def test_codex_pasted_content_turn_is_human_without_its_wrapper_tags(tmp_path):
    s = se.read_codex(codex_file(tmp_path, [
        x_meta(),
        x_user(PASTE, 0),
        x_user('<pasted_content id="1">\nonly a paste\n</pasted_content id="1">', 1),
        x_user("<environment_context>x</environment_context>", 2),
        x_user("<other>x</other>", 3),
    ]))
    assert [e.kind for e in s.events] == ["human", "human"]
    assert s.events[0].text == "Review findings:\n- fix the parser\n\nIs it still running?"
    assert s.events[1].text == "only a paste"


def test_pasted_next_human_turn_is_the_episodes_next_turn(tmp_path):
    roots = project(tmp_path)
    claude_file(tmp_path, [
        c_user("go", 0, "u1"),
        c_assistant([bash("toolu_1", "tasks start ai-000001")], 1, "a1"),
        c_result("toolu_1", OK, 2, "u2"),
        c_assistant([text("Started.")], 3, "a2"),
        c_user(PASTE, 600, "u3"),
        c_user("unrelated later question", 900, "u4"),
    ])
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    ep = json.loads(out.read_text())
    assert ep["next_human_at"] == ms(600) and ep["status_question"] is True
    code, shown, _ = run_cli(["show", ep["id"], "--episodes", str(out)], env)
    assert code == 0 and "pasted_content" not in shown and "Is it still running?" in shown
    assert run_cli(["label", ep["id"], "no", "--episodes", str(out)], env)[0] == 0
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    assert json.loads(out.read_text())["label_source"] == "reviewed"


def test_task_record_refs_name_the_project(tmp_path):
    s = codex_story(tmp_path)
    roots = project(tmp_path, notes=["- 2026-09-17T12:03:00Z (main): parked (waiting on user, review): look"],
                    status="done", completed="2026-09-17T13:00:00Z")
    e = se.build_episodes(inputs(tmp_path, [s], roots))[0][0]
    task_refs = [r for r in e["source_refs"] if r.startswith("tasks:")]
    assert len(task_refs) == 2 and all(r.startswith("tasks:ai:") for r in task_refs)
    assert task_refs[1].endswith("#completed")


def test_note_missing_counts_each_transition_once(tmp_path):
    recs = [x_meta(), x_event("task_started", 0), x_user("go", 0),
            x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 5),
            x_custom_out("c1", OK, 6), x_assistant("ok", 60), x_event("task_complete", 60),
            x_event("task_started", 700, "t2"), x_user("resume", 700),
            x_custom("c3", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 705),
            x_custom_out("c3", OK, 706), x_assistant("ok", 720), x_event("task_complete", 720, "t2"),
            x_event("task_started", 800, "t3"), x_user("finish", 800),
            x_custom("c4", 'text(await tools.exec_command({cmd:"tasks done ai-000001 landed"}));', 805),
            x_custom_out("c4", OK, 806), x_assistant("ok", 810), x_event("task_complete", 810, "t3")]
    s = se.read_codex(codex_file(tmp_path, recs))
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], project(tmp_path), now=ms(810) + 10 * 60 * 1000 + 1))
    assert len(eps) == 2 and all(e["closed_at"] == ms(806) for e in eps)
    assert summary["note_missing"] == 1


def test_retired_confirmation_is_counted(tmp_path):
    s = codex_story(tmp_path, start_cmd=LIT_JS, start_out='{"id":"lit-f43833","warnings":[]}\n')
    roots = {"lit": git_repo(tmp_path / "proj-lit")}
    task_file(roots["lit"], [], task_id="lit-f43833")
    _, cands, _ = se.build_episodes(inputs(tmp_path, [s], roots))
    cid = cands[0]["id"]
    call = next(e for e in s.events if e.kind == "tool_call" and e.call_id == "c1")
    result = next(e for e in s.events if e.kind == "tool_result" and e.call_id == "c1")
    evidence = se.digest("\n".join(call.commands) + call.raw + "\n" + result.text)
    anchors = {cid: {"id": cid, "confirmed": False, "evidence_digest": evidence, "confirmed_at": "x"}}
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], roots, anchors=anchors))
    assert eps == [] and cands == [] and summary["retired"] == 1


def test_task_copies_is_listed_once_per_project(tmp_path, monkeypatch):
    s = codex_story(tmp_path)
    recs = [x_meta(sid="X2"), x_event("task_started", 0), x_user("go", 0),
            x_custom("c9", 'text(await tools.exec_command({cmd:"tasks start ai-00000a"}));', 5),
            x_custom_out("c9", '{"id":"ai-00000a","warnings":[]}\n', 6), x_assistant("ok", 60), x_event("task_complete", 60)]
    other = se.read_codex(codex_file(tmp_path, recs, name="rollout-x2.jsonl"))
    roots = project(tmp_path)
    task_file(roots["ai"], [], task_id="ai-00000a")
    calls = []
    real = se.task_copies
    monkeypatch.setattr(se, "task_copies", lambda root: (calls.append(root), real(root))[1])
    eps, _, _ = se.build_episodes(inputs(tmp_path, [s, other], roots))
    assert len(eps) == 2 and calls == [roots["ai"]]


def test_non_git_root_and_moved_call_are_errors_not_tracebacks(tmp_path):
    codex_story(tmp_path)
    roots = project(tmp_path)
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    ep = json.loads(out.read_text())
    rollout = next(tmp_path.joinpath("codex").rglob("*.jsonl"))
    rollout.write_text("\n" + rollout.read_text())  # every line moves down by one
    code, _, err = run_cli(["show", ep["id"], "--episodes", str(out)], env)
    assert code == 2 and ep["id"] in err and "re-run extract" in err
    plain = tmp_path / "plain"
    (plain / "tasks").mkdir(parents=True)
    codex_story(tmp_path, start_cmd='text(await tools.exec_command({cmd:"tasks start pl-000001"}));',
                start_out='{"id":"pl-000001","warnings":[]}\n', name="rollout-pl.jsonl")
    env = cli_env(tmp_path, {"ai": roots["ai"], "pl": plain})
    code, _, err = run_cli(["extract", "--out", str(out)], env)
    assert code == 2 and "git worktree list failed" in err and str(plain) in err


def test_project_filter_checks_only_that_projects_tasks_dir(tmp_path):
    codex_story(tmp_path)
    roots = project(tmp_path)
    roots["zz"] = git_repo(tmp_path / "proj-zz")
    (roots["zz"] / "tasks").mkdir()
    (roots["ai"] / "tasks").rename(roots["ai"] / "tasks-gone")
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    assert run_cli(["extract", "--out", str(out), "--project", "zz"], env)[0] == 0
    assert run_cli(["extract", "--out", str(out)], env)[0] == 2


# --- prefilters ----------------------------------------------------------------

def test_read_codex_first_session_meta_is_the_rollouts_own(tmp_path):
    """A rollout forked into a subagent copies the parent's session_meta in with the parent's
    history; the rollout's identity is its first record (291 of 14,460 on this host)."""
    own = x_meta(sid="CHILD", thread_source="subagent")
    parent = x_meta(sid="PARENT", thread_source="user")
    s = se.read_codex(codex_file(tmp_path, [own, parent, x_event("task_started", 0), x_user("go", 0)]))
    assert s.subagent is True and s.session_id == "CHILD"
    header = se.codex_header(s.path)
    assert (header.subagent, header.session_id, header.entrypoint) == (True, "CHILD", "codex-tui")
    assert se.codex_header(codex_file(tmp_path, [x_event("task_started", 0), own], name="late-meta.jsonl")) is None


def test_claude_header_matches_the_full_read(tmp_path):
    side = claude_file(tmp_path, [c_user("x", 0, "u1", isSidechain=True)], name="agent.jsonl")
    main = claude_file(tmp_path, [{"type": "summary", "summary": "s"}, c_user("x", 0, "u1", isSidechain=True),
                                  c_user("go", 1, "u2", sid="S9", entrypoint="sdk-ts")], name="main.jsonl")
    for path in (side, main):
        header, full = se.claude_header(path), se.read_claude(path)
        assert (header.subagent, header.session_id, header.cwd, header.entrypoint) == \
               (full.subagent, full.session_id, full.cwd, full.entrypoint), path
        assert header.events == []
    assert se.claude_header(main).entrypoint == "sdk-ts"


DISCOVERABLE = [
    "tasks start ai-000001", 'tasks start "ai-000001"', "tasks --pretty start ai-000001", "tasks -C /w start ai-000001",
    'tasks -C /w --pretty start "ai-000001" && ls', "tasks -C '/w w' start ai-000001", 'tasks -C "/w w" start ai-000001',
    "tasks\tstart ai-000001", "tasks\u00a0start ai-000001", "tasks\u001cstart ai-000001",
    "just setup && tasks start ai-000001 | sed p",
    "tasks park ai-000001 'next' --waiting-on user; tasks done ai-00000a 'x'", "tasks drop ai-000001 'why'",
    "bash <<'EOF'\ntasks start ai-000001\nEOF", "bash -c 'cd /w && tasks start ai-000001'", 'echo "$(tasks start ai-000001)"',
    "text(await tools.exec_command({cmd: `tasks ${verb} ai-000001`})); // tasks startx",  # the substring route
    "tasks note ai-000001 'tasks started'",  # prose to the loose reading, a wrapper substring all the same
]
NOT_DISCOVERABLE = ["echo tasks; start", "the tasks are done", "tasks list --sort updated",
                    "tasks ready --parallel -n 2", "tasks -C /w note ai-000001 done"]


def raw_forms(command):
    """The command as each store writes it: a Claude Bash input (non-ASCII literal or escaped),
    a Codex function_call whose arguments are JSON inside JSON, and a Codex custom tool
    call wrapping a JS literal."""
    return [json.dumps(command, ensure_ascii=False).encode(), json.dumps(command).encode(),
            json.dumps(json.dumps({"command": ["bash", "-lc", command]})).encode(),
            json.dumps("text(await tools.exec_command({cmd:" + json.dumps(command) + "}));").encode()]


def discoverable(command):
    return bool(se.start_candidates(command) or se.nested_start_candidates(command) or se.transitions_in(command)
                or "tasks start" in command)


@pytest.mark.parametrize("command", DISCOVERABLE)
def test_lifecycle_text_admits_every_discoverable_form(command):
    assert discoverable(command), command
    for raw in raw_forms(command):
        assert se.LIFECYCLE_TEXT.search(raw), raw


@pytest.mark.parametrize("command", NOT_DISCOVERABLE)
def test_lifecycle_text_rejects_what_discovery_rejects(command):
    assert not discoverable(command), command
    for raw in raw_forms(command):
        assert se.LIFECYCLE_TEXT.search(raw) is None, raw


def test_lifecycle_text_is_linear_on_a_hostile_line():
    import time
    line = (b'tasks -C "' + b"a" * 4000 + b'" --x ' + b"\\\\n" * 2000 + b"--y ") * 200 + b"nothing"
    started = time.monotonic()
    assert se.LIFECYCLE_TEXT.search(line) is None
    assert time.monotonic() - started < 2


def test_scan_stores_skips_and_still_counts_every_file(tmp_path):
    import os
    roots = project(tmp_path)
    codex_story(tmp_path)  # parsed: an interactive rollout with a start
    codex_file(tmp_path, [x_meta(sid="X2", thread_source="subagent"), x_event("task_started", 0), x_user("go", 0),
                          x_custom("c1", 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', 5)], name="sub.jsonl")
    codex_file(tmp_path, [x_meta(sid="X3", originator="codex_cli_rs"), x_event("task_started", 0), x_user("tasks list", 0)], name="quiet.jsonl")
    old = claude_file(tmp_path, [c_user("go", 0, "u1"), c_assistant([bash("toolu_1", "tasks start ai-000001")], 5, "a1"),
                                 c_result("toolu_1", OK, 6, "u2"), c_assistant([text("done")], 60, "a2")], name="old.jsonl")
    claude_file(tmp_path, [c_user("go", 0, "u1", isSidechain=True)], name="agent.jsonl")
    env = cli_env(tmp_path, roots)
    out = tmp_path / "episodes.jsonl"
    code, _, err = run_cli(["extract", "--out", str(out)], env)
    assert code == 0
    summary = json.loads(err)
    assert summary["files"] == {"claude-code": 2, "codex": 3}
    assert summary["excluded"] == {"subagent": 2, "non-interactive": 1}
    assert summary["skipped"] == {"subagent_meta": 1, "before_since": 0, "no_lifecycle_text": 2}
    assert summary["anchors_seen"] == 2 and summary["episodes"] == 2
    # the same files under --since: the old Claude file is skipped on mtime alone and, being
    # older than the window, changes nothing but the count
    stale = (se.at_ms(T0) - 3 * 86_400_000) // 1000
    os.utime(old, (stale, stale))
    for rollout in tmp_path.joinpath("codex").rglob("*.jsonl"):
        os.utime(rollout, (stale, stale))
    code, _, err = run_cli(["extract", "--out", str(out), "--since", "1"], env)
    assert code == 0
    summary = json.loads(err)
    assert summary["files"] == {"claude-code": 2, "codex": 3}
    assert summary["excluded"] == {"subagent": 2, "non-interactive": 1}
    assert summary["skipped"] == {"subagent_meta": 1, "before_since": 3, "no_lifecycle_text": 1}
    assert summary["anchors_seen"] == 0 and summary["episodes"] == 0


def test_before_since_skip_changes_no_output(tmp_path):
    """Whether a file older than --since is skipped on its mtime or parsed and filtered per
    anchor, episodes and candidates are the same."""
    import os
    roots = project(tmp_path)

    def rollout(name, sid, call_id, t0, start_out):
        recs = [x_meta(sid=sid), x_event("task_started", t0), x_user("go", t0),
                x_custom(call_id, 'text(await tools.exec_command({cmd:"tasks start ai-000001"}));', t0 + 5),
                x_custom_out(call_id, start_out, t0 + 6), x_assistant("Underway.", t0 + 60), x_event("task_complete", t0 + 60),
                x_event("task_started", t0 + 660, "t2"), x_user("Is it still running?", t0 + 660)]
        path = codex_file(tmp_path, recs, name=name)
        os.utime(path, (ms(t0 + 661) // 1000, ms(t0 + 661) // 1000))
        return path

    rollout("rollout-a-old.jsonl", "OLD", "c0", 0, "nope\n")  # a candidate, when in range
    rollout("rollout-b-new.jsonl", "NEW", "c1", 1000, OK)
    claude_root, codex_root = tmp_path / "claude", tmp_path / "codex"
    since = ms(900)
    parsed = se.scan_stores(claude_root, codex_root)
    skipped = se.scan_stores(claude_root, codex_root, since)
    assert [s.skipped for s in parsed] == [None, None] and [s.skipped for s in skipped] == ["before_since", None]

    def run(sessions):
        inp = inputs(tmp_path, sessions, roots, now=ms(1000 + 660) + 10 * 60 * 1000 + 1)
        inp.since_ms = since
        return se.build_episodes(inp)

    with_skip, without_skip = run(skipped), run(parsed)
    assert with_skip[0] == without_skip[0] and with_skip[1] == without_skip[1]
    assert [e["session_key"] for e in with_skip[0]] == ["codex:NEW"] and with_skip[1] == []
    assert without_skip[2]["anchors_seen"] == 2 and with_skip[2]["anchors_seen"] == 1


# --- ids under a retired prefix (docs/specs/2026-10-06-rename-to-hq-design.md §3.5) -----

ALIAS = {"tack-000001": "hq-000001"}


def start_js(task_id):
    return f'text(await tools.exec_command({{cmd:"tasks start {task_id}"}}));'


def renamed_project(tmp_path, notes=()):
    root = git_repo(tmp_path / "proj-hq")
    task_file(root, list(notes), task_id="hq-000001")
    return {"hq": root}


def test_a_start_written_under_a_retired_prefix_is_an_episode_of_the_canonical_task(tmp_path):
    # After the rename, `tasks start tack-…` prints the canonical id.
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"hq-000001","warnings":[]}\n')
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path), canonical=ALIAS))
    assert cands == [] and summary["unregistered"] == 0 and len(eps) == 1
    assert eps[0]["task_id"] == "hq-000001" and eps[0]["anchor_source"] == "result"
    assert eps[0]["id"] == se.episode_id("codex", "c1", "tack-000001")


def test_a_start_from_before_the_rename_keeps_its_episode_id_and_finds_the_renamed_record(tmp_path):
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n')
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path), canonical=ALIAS))
    assert summary["unregistered"] == 0 and len(eps) == 1
    assert eps[0]["task_id"] == "hq-000001" and eps[0]["join_class"] == "inferred"
    assert eps[0]["id"] == se.episode_id("codex", "c1", "tack-000001")


def test_without_resolution_a_retired_prefix_counts_unregistered(tmp_path):
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n')
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path)))
    assert eps == [] and summary["unregistered"] == 1


def test_a_close_written_after_the_rename_closes_a_start_written_before(tmp_path):
    extra = [x_event("task_started", 100, "t2"), x_user("finish it", 100),
             x_custom("c2", 'text(await tools.exec_command({cmd:"tasks done hq-000001 landed"}));', 120),
             x_custom_out("c2", '{"id":"hq-000001","warnings":[]}\n', 130), x_event("task_complete", 131, "t2")]
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n',
                    extra=extra, next_text=None)
    eps, _, _ = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path), canonical=ALIAS))
    assert len(eps) == 1 and eps[0]["task_id"] == "hq-000001"
    assert eps[0]["closed_at"] == ms(130) and eps[0]["closure_source"] == "transcript"


def test_anchor_ids_names_the_start_and_the_close(tmp_path):
    extra = [x_custom("c2", 'text(await tools.exec_command({cmd:"tasks done hq-000001 landed"}));', 120),
             x_custom_out("c2", '{"id":"hq-000001","warnings":[]}\n', 130)]
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n',
                    extra=extra, next_text=None)
    assert se.anchor_ids([s]) == ["hq-000001", "tack-000001"]


def test_anchor_ids_names_a_close_written_under_the_retired_prefix(tmp_path):
    # Started as hq-…, closed as tack-…, which prints hq-…: unconfirmed until resolved.
    extra = [x_custom("c2", 'text(await tools.exec_command({cmd:"tasks done tack-000001 landed"}));', 120),
             x_custom_out("c2", '{"id":"hq-000001","warnings":[]}\n', 130)]
    s = codex_story(tmp_path, start_cmd=start_js("hq-000001"), start_out='{"id":"hq-000001","warnings":[]}\n',
                    extra=extra, next_text=None)
    assert "tack-000001" in se.anchor_ids([s])


def test_extract_closes_with_a_close_written_under_the_retired_prefix(tmp_path):
    extra = [x_event("task_started", 100, "t2"), x_user("finish it", 100),
             x_custom("c2", 'text(await tools.exec_command({cmd:"tasks done tack-000001 landed"}));', 120),
             x_custom_out("c2", '{"id":"hq-000001","warnings":[]}\n', 130), x_event("task_complete", 131, "t2")]
    codex_story(tmp_path, start_cmd=start_js("hq-000001"), start_out='{"id":"hq-000001","warnings":[]}\n',
                extra=extra, next_text=None)
    out = tmp_path / "episodes.jsonl"
    env = cli_env(tmp_path, renamed_project(tmp_path), aliases={"tack": "hq"})
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    row = json.loads(out.read_text().splitlines()[0])
    assert row["task_id"] == "hq-000001" and row["closed_at"] == ms(130) and row["closure_source"] == "transcript"


def test_resolve_ids_follows_an_alias_through_tasks_resolve(tmp_path):
    root = git_repo(tmp_path / "proj-hq")
    env = cli_env(tmp_path, {"hq": root}, aliases={"tack": "hq"})
    roots, canonical = se.resolve_ids(["tack-000001", "hq-000002", "tack", "zz-000003"], env)
    assert roots == {"hq": root}
    assert canonical == {"tack-000001": "hq-000001", "hq-000002": "hq-000002", "tack": "hq"}


def test_extract_follows_an_alias_end_to_end(tmp_path):
    codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"hq-000001","warnings":[]}\n')
    out = tmp_path / "ep" / "episodes.jsonl"
    env = cli_env(tmp_path, renamed_project(tmp_path), aliases={"tack": "hq"})
    code, _, stderr = run_cli(["extract", "--out", str(out)], env)
    assert code == 0 and json.loads(stderr)["unregistered"] == 0
    assert [json.loads(l)["task_id"] for l in out.read_text().splitlines()] == ["hq-000001"]


def test_extract_project_accepts_a_retired_prefix(tmp_path):
    codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"hq-000001","warnings":[]}\n')
    out = tmp_path / "episodes.jsonl"
    env = cli_env(tmp_path, renamed_project(tmp_path), aliases={"tack": "hq"})
    assert run_cli(["extract", "--project", "tack", "--out", str(out)], env)[0] == 0
    assert len(out.read_text().splitlines()) == 1


def test_extract_refuses_an_unregistered_project(tmp_path):
    codex_story(tmp_path)
    env = cli_env(tmp_path, project(tmp_path))
    # main() turns a SystemExit carrying a message into exit 2 with the message on stderr.
    code, _, err = run_cli(["extract", "--project", "zz", "--out", str(tmp_path / "e.jsonl")], env)
    assert code == 2 and "--project zz is not a registered prefix" in err


def test_show_and_label_find_the_call_behind_an_episode_started_under_a_retired_prefix(tmp_path):
    codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"hq-000001","warnings":[]}\n')
    out = tmp_path / "episodes.jsonl"
    env = cli_env(tmp_path, renamed_project(tmp_path), aliases={"tack": "hq"})
    assert run_cli(["extract", "--out", str(out)], env)[0] == 0
    ep = json.loads(out.read_text().splitlines()[0])
    code, stdout, stderr = run_cli(["show", ep["id"], "--episodes", str(out)], env)
    assert code == 0 and "tasks start tack-000001" in stdout, stderr
    assert run_cli(["label", ep["id"], "no", "--episodes", str(out)], env)[0] == 0
