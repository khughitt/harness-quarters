# Session logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `session-logs` skill that explains the four harness stores, and an `agents/bin/session-episodes` tool that turns the Claude Code and Codex stores plus task records into source-referenced pre-flow episodes for obs's proxy baseline.

**Architecture:** One standard-library Python script with five internal layers — record readers (Claude, Codex) producing a common `Event` stream; command extraction and start attribution; task-record reading across worktree copies; turn/continuation classification; episode assembly with labels, reviewed anchors, candidates and a run summary — behind an argparse CLI (`extract`, `show`, `confirm`, `label`). Tests build synthetic store files in a temp directory and load the script the way `agents/bin/test_flow_state.py` does.

**Tech Stack:** Python ≥ 3.11 standard library only (`json`, `re`, `hashlib`, `argparse`, `subprocess` for `git worktree list`, `tomllib`); pytest for tests; `git` on PATH for the task-copy tests.

**Spec:** `docs/specs/2026-09-19-session-logs-design.md` (approved 2026-09-19). Section numbers below refer to it.

## Global Constraints

- Python 3.11+ standard library only; no third-party packages; the script is invoked by path (`~/.agents/bin/session-episodes` or `agents/bin/session-episodes`) and is never installed on PATH.
- Read-only over every store and every `tasks/` directory; the only files written are `--out`, `<stem>.candidates.jsonl`, `<stem>.labels.jsonl`, `<stem>.anchors.jsonl`.
- No transcript text in `episodes.jsonl` or the candidates file; text is printed only by `show`.
- Store roots come from `SESSION_LOGS_CLAUDE` / `SESSION_LOGS_CODEX` (defaults `~/.claude/projects`, `~/.codex/sessions`); project roots from `~/.config/tasks/projects.toml` (`XDG_CONFIG_HOME` respected).
- Timestamps in output are UTC epoch milliseconds (`int`).
- Fail early: a malformed labels/anchors line, a registered project without `tasks/`, an unknown id to `show`/`confirm`/`label` are errors (§6); malformed store lines are skipped and counted.
- Tests never read a real store; fixtures are written under `tmp_path`.
- Population (§4.1 as revised at plan review): every file is scanned; `subagent` and `non-interactive` exclude per file; `unregistered` excludes per anchor by the task id's prefix — a `tasks start lit-…` run from `/tmp` belongs to `lit`. `test_session_from_an_unregistered_cwd_still_yields_an_episode` pins it.

---

## File structure

- `agents/bin/session-episodes` — the whole tool, in this order: constants and regexes; `Event`/`Session` model; `read_claude`, `read_codex`; command extraction (`commands_of_custom_input`, `linear`, `start_candidates`, `id_lines`, `attribute`); task records (`registry`, `task_copies`, `read_task`, `transitions`); turns (`turn_after`, `next_human_after`, `continuation`); episodes (`episode_id`, `heuristic_label`, `digest`, `build_episodes`); files (`read_jsonl_map`, `write_jsonl`); CLI (`cmd_extract`, `cmd_show`, `cmd_confirm`, `cmd_label`, `main`).
- `agents/bin/test_session_episodes.py` — all tests, grouped by the same layers, with fixture builders `claude_file(...)` and `codex_file(...)` at the top.
- `agents/skills/session-logs/SKILL.md` — the skill (§3).
- `agents/skills/README.md` — one bullet for the new skill.
- `~/.claude/skills/session-logs` → symlink to the skill directory (outside the repo, the documented convention for every skill here).

The script stays one file because the spec fixed its path and the `exec`-loading test pattern; the layer order above is the map an implementer reads it by.

---

### Task 1: Event model and the two store readers

**Files:**
- Create: `agents/bin/session-episodes` (executable, `#!/usr/bin/env python3`)
- Create: `agents/bin/test_session_episodes.py`

**Interfaces:**
- Produces:
  - `Event(kind, at_ms, line, uuid=None, text="", call_id=None, tool=None, commands=(), unsupported=False, raw="", text_only=False, pending=(), interrupted=False, turn_id=None)` — frozen dataclass; `raw` is the JavaScript source of a Codex custom tool call (empty for every other call), kept for `show`, the confirmation digest, and the whole-wrapper check in Task 2. `kind` ∈ `human | interrupt | assistant | tool_call | tool_result | turn_start | turn_end | turn_aborted`.
  - `Session(harness, path, session_id, cwd, entrypoint, subagent, events, malformed)` — dataclass; `harness` ∈ `"claude-code" | "codex"`; `events` is a list in file order.
  - `read_claude(path: Path) -> Session`, `read_codex(path: Path) -> Session`.
  - `at_ms(text: str) -> int` — ISO-8601 `…Z` (with optional fraction) to epoch ms.
  - `CLAUDE_HARNESS = "claude-code"`, `CODEX_HARNESS = "codex"`, `WAIT_TOOLS = {"AskUserQuestion", "EnterPlanMode", "ExitPlanMode"}`, `CODEX_WAIT_TOOL = "request_user_input"`, `CODEX_INJECTED` (the tuple from §3), `INTERACTIVE = {"claude-code": ("cli",), "codex": ("codex-tui", "codex_exec")}`.

- [ ] **Step 1: Write the fixture builders and the first failing tests**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd $WORK_ROOT/ai/.worktrees/session-logs && python3 -m pytest agents/bin/test_session_episodes.py -q`
Expected: FAIL — `FileNotFoundError` for the script (or `AttributeError: module has no attribute 'at_ms'` once the file exists).

- [ ] **Step 3: Write the model and readers**

```python
#!/usr/bin/env python3
"""Prepare pre-flow episodes from the Claude Code and Codex session stores.

session-episodes extract  [--since DAYS] [--project PREFIX] [--window-minutes N]
                          [--labels PATH] [--anchors PATH] --out PATH
session-episodes show     <id>        --episodes PATH
session-episodes confirm  <id> yes|no --episodes PATH [--anchors PATH]
session-episodes label    <id> yes|no --episodes PATH [--labels PATH]

The contract is docs/specs/2026-09-19-session-logs-design.md in the ai checkout.
Read-only over the stores and every tasks/ directory; standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

CLAUDE_HARNESS = "claude-code"
CODEX_HARNESS = "codex"
WAIT_TOOLS = {"AskUserQuestion", "EnterPlanMode", "ExitPlanMode"}
CODEX_WAIT_TOOL = "request_user_input"
CODEX_INJECTED = ("# AGENTS.md", "<environment_context>", "<INSTRUCTIONS>", "<skills_instruct",
                  "<turn_aborted>", "<permissions", "<user_shell", "<collaboration_mode")
INTERACTIVE = {CLAUDE_HARNESS: ("cli",), CODEX_HARNESS: ("codex-tui", "codex_exec")}
INTERRUPT_MARK = "[Request interrupted by user"


# --- model ---------------------------------------------------------------------

@dataclass(frozen=True)
class Event:
    kind: str
    at_ms: int
    line: int
    uuid: str | None = None
    text: str = ""
    call_id: str | None = None
    tool: str | None = None
    commands: tuple[str, ...] = ()
    unsupported: bool = False
    raw: str = ""
    text_only: bool = False
    pending: tuple[str, ...] = ()
    interrupted: bool = False
    turn_id: str | None = None


@dataclass
class Session:
    harness: str
    path: Path
    session_id: str | None
    cwd: str | None
    entrypoint: str | None
    subagent: bool
    events: list[Event]
    malformed: int


def at_ms(text: str) -> int:
    t = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    return int(t.timestamp() * 1000)


def _text_blocks(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _lines(path: Path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield number, json.loads(line)
            except json.JSONDecodeError:
                yield number, None


# --- Claude Code ---------------------------------------------------------------

def read_claude(path: Path) -> Session:
    s = Session(CLAUDE_HARNESS, path, None, None, None, True, [], 0)
    for line, r in _lines(path):
        if r is None:
            s.malformed += 1
            continue
        if "timestamp" not in r or r.get("isSidechain"):
            continue
        s.subagent = False
        t = at_ms(r["timestamp"])
        s.session_id = s.session_id or r.get("sessionId")
        s.cwd = s.cwd or r.get("cwd")
        s.entrypoint = s.entrypoint or r.get("entrypoint")
        kind = r.get("type")
        content = (r.get("message") or {}).get("content")
        if kind == "user":
            if r.get("isMeta") or r.get("isCompactSummary"):
                continue
            results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"] if isinstance(content, list) else []
            for b in results:
                body = b.get("content")
                body = body if isinstance(body, str) else _text_blocks(body)
                s.events.append(Event("tool_result", t, line, r.get("uuid"), body, call_id=b.get("tool_use_id"),
                                      interrupted=body.lstrip().startswith(INTERRUPT_MARK)))
            body = _text_blocks(content).strip()
            if body.startswith(INTERRUPT_MARK):
                s.events.append(Event("interrupt", t, line, r.get("uuid"), body))
            elif body and not body.startswith("<"):
                s.events.append(Event("human", t, line, r.get("uuid"), body))
        elif kind == "assistant":
            blocks = content if isinstance(content, list) else []
            uses = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"]
            body = _text_blocks(content)
            s.events.append(Event("assistant", t, line, r.get("uuid"), body,
                                  text_only=bool(body.strip()) and not uses,
                                  pending=tuple(b.get("id") for b in uses)))
            for b in uses:
                inp = b.get("input") or {}
                commands = (str(inp.get("command", "")),) if b.get("name") == "Bash" else ()
                s.events.append(Event("tool_call", t, line, r.get("uuid"), call_id=b.get("id"),
                                      tool=b.get("name"), commands=commands))
    return s


# --- Codex ---------------------------------------------------------------------

def _codex_output_text(output) -> str:
    if isinstance(output, list):
        return "".join(b.get("text", "") for b in output if isinstance(b, dict))
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return output
        if isinstance(parsed, dict) and isinstance(parsed.get("output"), str):
            return parsed["output"]
        return output
    return ""


def _codex_function_commands(name: str, arguments) -> tuple[str, ...]:
    if name not in ("shell", "exec_command"):
        return ()
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    except json.JSONDecodeError:
        return ()
    if not isinstance(args, dict):
        return ()
    command = args.get("command")
    if isinstance(command, list) and command:
        if len(command) >= 3 and command[0] in ("bash", "sh", "zsh") and command[1] in ("-lc", "-c"):
            return (str(command[2]),)
        return (" ".join(str(c) for c in command),)
    if isinstance(command, str):
        return (command,)
    if isinstance(args.get("cmd"), str):
        return (args["cmd"],)
    return ()


def read_codex(path: Path) -> Session:
    s = Session(CODEX_HARNESS, path, None, None, None, False, [], 0)
    for line, r in _lines(path):
        if r is None:
            s.malformed += 1
            continue
        p = r.get("payload") or {}
        kind = r.get("type")
        if kind == "session_meta":
            s.session_id = p.get("id")
            s.cwd = p.get("cwd")
            s.entrypoint = p.get("originator")
            s.subagent = p.get("thread_source") not in (None, "user")
            continue
        if "timestamp" not in r:
            continue
        t = at_ms(r["timestamp"])
        pt = p.get("type")
        if kind == "event_msg":
            if pt == "task_started":
                s.events.append(Event("turn_start", t, line, turn_id=p.get("turn_id")))
            elif pt == "task_complete":
                s.events.append(Event("turn_end", t, line, turn_id=p.get("turn_id")))
            elif pt == "turn_aborted":
                s.events.append(Event("turn_aborted", t, line, turn_id=p.get("turn_id")))
            continue
        if kind != "response_item":
            continue
        if pt == "message":
            body = "\n".join(c.get("text", "") for c in (p.get("content") or [])
                             if isinstance(c, dict) and c.get("type") in ("input_text", "output_text")).strip()
            if p.get("role") == "user":
                if body and not body.startswith(CODEX_INJECTED) and not body.startswith("<"):
                    s.events.append(Event("human", t, line, text=body))
            elif p.get("role") == "assistant":
                s.events.append(Event("assistant", t, line, text=body, text_only=True))
        elif pt == "function_call":
            s.events.append(Event("tool_call", t, line, call_id=p.get("call_id"), tool=p.get("name"),
                                  commands=_codex_function_commands(p.get("name"), p.get("arguments"))))
        elif pt == "custom_tool_call":
            source = str(p.get("input") or "")
            commands, unsupported = commands_of_custom_input(source)
            s.events.append(Event("tool_call", t, line, call_id=p.get("call_id"), tool=p.get("name"),
                                  commands=commands, unsupported=unsupported, raw=source))
        elif pt in ("function_call_output", "custom_tool_call_output"):
            s.events.append(Event("tool_result", t, line, call_id=p.get("call_id"),
                                  text=_codex_output_text(p.get("output"))))
    return s


def commands_of_custom_input(source: str) -> tuple[tuple[str, ...], bool]:
    """Task 2 defines this; a stub keeps Task 1's reader importable."""
    return (), "tasks start" in source
```

- [ ] **Step 4: Make the script executable and run the tests**

Run: `chmod +x agents/bin/session-episodes && python3 -m pytest agents/bin/test_session_episodes.py -q`
Expected: 6 passed, except `test_read_codex_yields_turn_events_and_tool_calls` FAILS on `commands == ("tasks start ai-000001",)` because the custom-input extractor is a stub. Mark that one test `@pytest.mark.xfail(strict=True, reason="Task 2")` for this commit and remove the marker in Task 2.

- [ ] **Step 5: Commit**

```bash
git add agents/bin/session-episodes agents/bin/test_session_episodes.py
git commit -m "feat(session-episodes): event model and Claude/Codex store readers"
```

---

### Task 2: Command extraction and start attribution

**Files:**
- Modify: `agents/bin/session-episodes` (replace the `commands_of_custom_input` stub; add the section after the readers)
- Modify: `agents/bin/test_session_episodes.py`

**Interfaces:**
- Consumes: `Event` (Task 1).
- Produces:
  - `commands_of_custom_input(source: str) -> tuple[tuple[str, ...], bool]` — static `cmd` literals in the four forms, for *discovery* only; second value is `unsupported` (mentions `tasks start`, no literal carries it).
  - `single_wrapper_command(source: str) -> str | None` — the command when the *whole* JavaScript wrapper is one of the four observed single-call forms (`const r = await tools.exec_command({…}); text(r.output);`, `text(await tools.exec_command({…}));`, `text((await tools.exec_command({…})).output);`, `const r = await tools.exec_command({…}); text(r);`) with an object literal of scalar properties; otherwise `None`.
  - `attributable_commands(event: Event) -> tuple[str, ...] | None` — what `attribute` may read for this call: a Codex custom call's whole-wrapper command, or a plain call's commands; `None` when a wrapper is not a supported single-call form.
  - `START_RE`, `TASK_ID_RE`, `TASKS_ID_CMD`; `ID_PRINTING = ("start", "note", "edit", "park", "done", "drop", "dep", "shelve", "unshelve")`.
  - `start_candidates(command: str) -> list[str]` — ids a `tasks start` names in the *loose* reading (heredoc bodies lifted, quoted strings blanked); `nested_start_candidates(command: str) -> list[str]` — ids found only in nested executable text (`nested_text(command) -> list[str]`: shell heredoc bodies, a shell's quoted string argument, a double-quoted `$(…)`).
  - `transitions_in(command: str) -> list[tuple[str, str]]` — `(subcommand, task_id)` for `park|done|drop` in the loose reading.
  - `Invocation(subcommand, task_id, pretty)` frozen dataclass; `single_invocation(command: str) -> Invocation | None` — the *strict* reading (§4.2): optional `cd <path> &&`, then exactly one `tasks [-C path] [--pretty] SUBCOMMAND args…`, optional trailing `2>&1` or `2>/dev/null`, arguments without `$`/backticks, no other operator, no newline, no heredoc.
  - `id_lines(result_text: str, task_id: str, pretty: bool = False) -> int`; `ids_in_result(result_text: str) -> list[str]`; `has_error_line(result_text: str) -> bool`.
  - `attribute(commands: tuple[str, ...], result_text: str, task_id: str, subcommand: str = "start") -> str` — `"confirmed" | "outside-grammar" | "no-id-line" | "error-output"`: exactly one literal whose strict reading is this subcommand on this task, and at least one id line for it.

- [ ] **Step 1: Write the failing tests**

```python
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
```

Also delete the `xfail` marker added in Task 1.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q -k "custom_input or linear or candidates or id_lines or attribute"`
Expected: FAIL with `AttributeError` on `linear` and wrong tuples from the stub.

- [ ] **Step 3: Implement the section (replace the stub)**

```python
# --- commands and attribution --------------------------------------------------

# the literal must be the whole property value: a `+`, a `?`, or anything but `,`/`}` after
# the closing quote means the command is assembled at run time and only partly visible
_CMD_LITERAL = re.compile(
    r'''(?:"cmd"|(?<![\w"'])cmd)\s*:\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|`((?:[^`\\]|\\.)*)`)(?=\s*[,}])''', re.S)
START_RE = re.compile(r"\btasks\s+(?:-C\s+\S+\s+)?(?:--\S+\s+)*start\b(?:\s+--\S+)*\s+([a-z0-9]+-[0-9a-f]{6})\b")
TASK_ID_RE = re.compile(r"^[a-z0-9]+-[0-9a-f]{6}$")
ID_PRINTING = ("start", "note", "edit", "park", "done", "drop", "dep", "shelve", "unshelve")
TASKS_ID_CMD = re.compile(
    r"\btasks\s+(?:-C\s+\S+\s+)?(?:--\S+\s+)*(" + "|".join(ID_PRINTING) + r")\b(?:\s+--\S+)*\s+([a-z0-9]+-[0-9a-f]{6})\b")
_HEREDOC = re.compile(r"(?P<open>[^\n]*<<-?\s*(['\"]?)(?P<tag>[A-Za-z_][A-Za-z0-9_]*)\2[^\n]*)\n(?P<body>.*?)\n[ \t]*(?P=tag)[ \t]*(?:\n|$)", re.S)
_SHELLS = ("bash", "sh", "zsh", "dash", "ssh", "sudo", "env", "nohup", "eval", "source", ".")
_QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'')
# a shell word at the start of a segment, then its first quoted argument on that segment
_SHELL_STRING = re.compile(r"(?:^|[;&|\n]\s*)(" + "|".join(re.escape(w) for w in ("bash", "sh", "zsh", "dash", "ssh", "sudo", "env", "nohup", "eval"))
                           + r")\b[^;&|\n\"']*?(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)')")
_ERROR_LINE = re.compile(r"^error:", re.M)
_JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "`": "`", "$": "$", "'": "'", '"': '"', "0": "\0", "b": "\b", "f": "\f", "v": "\v"}
_STDERR_ONLY = (("2", ">&", "1"), ("2", ">", "/dev/null"))


def _decode_js(body: str) -> str | None:
    """A single- or template-quoted JS literal body: the plain escapes are decoded, anything
    else (\\u, \\x, a line continuation, an interpolation) makes the literal unsupported."""
    if "${" in body:
        return None
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= len(body) or body[i + 1] not in _JS_ESCAPES:
            return None
        out.append(_JS_ESCAPES[body[i + 1]])
        i += 2
    return "".join(out)


def _decode(double: str | None, single: str | None, template: str | None) -> str | None:
    if double is not None:
        return json.loads('"' + double + '"')
    if single is not None:
        return _decode_js(single)
    if template is not None:
        return _decode_js(template)
    return None


# a JS object literal made only of scalar properties, e.g. {"cmd":"…","workdir":"…","yield_time_ms":10000}
_SCALAR = r'(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`[^`$]*`|-?\d+(?:\.\d+)?|true|false|null)'
_OBJECT = r"\{\s*(?:(?:\"[A-Za-z_]\w*\"|[A-Za-z_]\w*)\s*:\s*" + _SCALAR + r"\s*,?\s*)*\}"
_WRAPPER_FORMS = tuple(re.compile(pattern.replace("OBJ", "(" + _OBJECT + ")"), re.S) for pattern in (
    r"^const\s+(\w+)\s*=\s*await\s+tools\.exec_command\(\s*OBJ\s*\)\s*;\s*text\(\s*\1\.output\s*\)\s*;?$",
    r"^const\s+(\w+)\s*=\s*await\s+tools\.exec_command\(\s*OBJ\s*\)\s*;\s*text\(\s*\1\s*\)\s*;?$",
    r"^text\(\s*await\s+tools\.exec_command\(\s*OBJ\s*\)\s*\)\s*;?$",
    r"^text\(\s*\(\s*await\s+tools\.exec_command\(\s*OBJ\s*\)\s*\)\.output\s*\)\s*;?$",
))


def single_wrapper_command(source: str) -> str | None:
    """The command of a Codex custom tool call whose *entire* JavaScript is one observed
    single-call form around an object literal of scalars. Extracting a `cmd` literal from
    any other wrapper says nothing about whether that command ran, so only this shape may
    have its output attributed. The four forms cover 550 of the 555 single-exec wrappers
    with a start in September's rollouts."""
    text = source.strip()
    for form in _WRAPPER_FORMS:
        m = form.match(text)
        if m is None:
            continue
        obj = m.group(m.lastindex)
        commands, _ = commands_of_custom_input(obj)
        if len(commands) == 1 and _CMD_LITERAL.search(obj) and len(_CMD_LITERAL.findall(obj)) == 1:
            return commands[0]
        return None
    return None


def attributable_commands(event) -> tuple[str, ...] | None:
    """What `attribute` may read for a tool call: a plain shell call's commands, or the one
    command of a Codex wrapper in a supported single-call form. None otherwise."""
    if event.raw:
        command = single_wrapper_command(event.raw)
        return (command,) if command is not None else None
    return event.commands


def commands_of_custom_input(source: str) -> tuple[tuple[str, ...], bool]:
    """Static shell strings handed to a `cmd` key inside a Codex custom tool call. This is
    the discovery reading — it finds candidates; it never proves a command ran."""
    commands = []
    for m in _CMD_LITERAL.finditer(source):
        try:
            decoded = _decode(*m.groups())
        except json.JSONDecodeError:
            decoded = None
        if decoded is not None:
            commands.append(decoded)
    unsupported = "tasks start" in source and not any("tasks start" in c for c in commands)
    return tuple(commands), unsupported


# --- reading a command -----------------------------------------------------------
#
# Two readings, for two purposes. For *finding* candidates the tool reads loosely: heredoc
# bodies lifted out, quoted strings blanked, a regex over what is left, plus the executable
# text (shell heredocs, -c strings, "$(…)") kept as nested candidates. For *confirming* a
# transition from its own output the tool reads strictly: the command must be one literal
# `tasks` invocation and nothing else (§4.2). Everything between those two is review.

@dataclass(frozen=True)
class Invocation:
    subcommand: str
    task_id: str
    pretty: bool


def _lift_heredocs(command: str) -> tuple[str, list[str], int]:
    """(command without heredoc bodies, bodies handed to a shell, number of heredocs)."""
    nested, count = [], 0

    def lift(m):
        nonlocal count
        count += 1
        opener = m.group("open")
        words = opener.strip().split()
        if words and words[0] in _SHELLS:
            nested.append(m.group("body"))
        return re.sub(r"<<(-?)\s*(['\"])(\w+)\2", r"<<\1\3", opener) + "\n"

    return _HEREDOC.sub(lift, command), nested, count


def _loose(command: str) -> str:
    """The shell text a candidate regex may read: no heredoc bodies, no string contents —
    except a quoted string that is exactly one task id, which is an argument, not prose."""
    text, _, _ = _lift_heredocs(command)
    return _QUOTED.sub(lambda m: m.group(0)[1:-1] if TASK_ID_RE.match(m.group(0)[1:-1]) else '""', text)


def nested_text(command: str) -> list[str]:
    """Executable text hidden from the loose reading: shell heredoc bodies, the string
    argument of a shell (`bash -c '…'`, `ssh host "…"`), a double-quoted `$(…)`."""
    text, nested, _ = _lift_heredocs(command)
    out = list(nested)
    for m in _SHELL_STRING.finditer(text):
        out.append(m.group(2) if m.group(2) is not None else m.group(3))
    out.extend(m.group(1) for m in re.finditer(r'"([^"]*\$\([^"]*)"', text))
    return out


def start_candidates(command: str) -> list[str]:
    """The strict reading when it succeeds, else the loose one."""
    strict = single_invocation(command)
    if strict is not None:
        return [strict.task_id] if strict.subcommand == "start" else []
    return list(dict.fromkeys(m.group(1) for m in START_RE.finditer(_loose(command))))


def nested_start_candidates(command: str) -> list[str]:
    seen = set(start_candidates(command))
    out = []
    for text in nested_text(command):
        for m in START_RE.finditer(text):
            if m.group(1) not in seen:
                out.append(m.group(1))
                seen.add(m.group(1))
    return out


def transitions_in(command: str) -> list[tuple[str, str]]:
    strict = single_invocation(command)
    if strict is not None:
        return [(strict.subcommand, strict.task_id)] if strict.subcommand in ("park", "done", "drop") else []
    return [(m.group(1), m.group(2)) for m in TASKS_ID_CMD.finditer(_loose(command)) if m.group(1) in ("park", "done", "drop")]


def single_invocation(command: str) -> Invocation | None:
    """The one command shape whose output the tool attributes: optionally `cd <path> &&`,
    then exactly one `tasks [-C path] SUBCOMMAND args…` with optional `--pretty` and an
    optional trailing `2>&1` or `2>/dev/null`. Arguments are plain words or quoted strings
    without `$` or backticks. Anything else is None."""
    if "\n" in command or "<<" in command:
        return None
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    if any("$" in t or "`" in t for t in tokens):
        return None  # no expansion anywhere: not in a path, a -C argument, a message, or a redirection target
    if len(tokens) >= 3 and tokens[0] == "cd" and tokens[2] == "&&":
        tokens = tokens[3:]
    for tail in _STDERR_ONLY:
        if tuple(tokens[-3:]) == tail:
            tokens = tokens[:-3]
            break
    if not tokens or tokens[0] != "tasks":
        return None
    i = 1
    if i < len(tokens) and tokens[i] == "-C":
        i += 2
    pretty = False
    while i < len(tokens) and tokens[i] == "--pretty":
        pretty, i = True, i + 1
    if i >= len(tokens):
        return None
    subcommand, args = tokens[i], tokens[i + 1:]
    if any(re.fullmatch(r"[();<>|&]+", t) for t in tokens):
        return None
    pretty = pretty or "--pretty" in args
    task_id = next((a for a in args if TASK_ID_RE.match(a)), None)
    if task_id is None:
        return None
    return Invocation(subcommand, task_id, pretty)


def has_error_line(result_text: str) -> bool:
    return bool(_ERROR_LINE.search(result_text))


def _id_objects(result_text: str):
    for line in result_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("id"), str) and "warnings" in obj:
            yield obj["id"]


def id_lines(result_text: str, task_id: str, pretty: bool = False) -> int:
    count = sum(1 for i in _id_objects(result_text) if i == task_id)
    if pretty:
        count += sum(1 for line in result_text.splitlines() if line.strip() == task_id)
    return count


def ids_in_result(result_text: str) -> list[str]:
    return list(dict.fromkeys(_id_objects(result_text)))


def attribute(commands: tuple[str, ...], result_text: str, task_id: str, subcommand: str = "start") -> str:
    """Does this call's output prove that its `tasks <subcommand> <task_id>` ran? (§4.2)
    confirmed | outside-grammar | no-id-line | error-output"""
    if has_error_line(result_text):
        return "error-output"
    if len(commands) != 1:
        return "outside-grammar"  # several literals share one output
    invocation = single_invocation(commands[0])
    if invocation is None:
        return "outside-grammar"
    if invocation.subcommand != subcommand or invocation.task_id != task_id:
        return "outside-grammar"
    return "confirmed" if id_lines(result_text, task_id, invocation.pretty) >= 1 else "no-id-line"
```

- [ ] **Step 4: Run the whole file**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q`
Expected: all pass (Task 1's Codex reader test now passes without the marker).

- [ ] **Step 5: Commit**

```bash
git add agents/bin/session-episodes agents/bin/test_session_episodes.py
git commit -m "feat(session-episodes): command literals, linear form and start attribution"
```

---

### Task 3: Task records across worktree copies

**Files:**
- Modify: `agents/bin/session-episodes` (new section after attribution)
- Modify: `agents/bin/test_session_episodes.py`

**Interfaces:**
- Produces:
  - `registry(env: dict) -> dict[str, Path]` — prefix → resolved root from `$XDG_CONFIG_HOME/tasks/projects.toml` or `~/.config/tasks/projects.toml`; `{}` when absent.
  - `task_copies(root: Path) -> tuple[list[Path], list[Path]]` — `(readable_tasks_dirs, unreadable_paths)`: the root's `tasks/` and each `git worktree list --porcelain` path's `tasks/`; a listed worktree path that does not exist or has no `tasks/` goes in the second list.
  - `Note(at_ms, text, harness_session, path, line)` frozen dataclass.
  - `TaskRecord(task_id, status, started_ms, completed, notes, copies, unreadable)` dataclass; `started_ms` is the earliest `started:` stamp across copies (the task's first start; it survives resumes) or `None`; `notes` unioned across copies, sorted by `(at_ms, text)`, deduplicated on `(at_ms, text)`; `completed` is the list of `(at_ms, path)` stamps, one per copy that has one, sorted — a completion recorded only in a worktree copy is kept.
  - `read_task(root: Path, task_id: str) -> TaskRecord | None` — `None` when no copy has the file.
  - `note_kind(text: str) -> str | None` — `"park" | "close" | "start"` or `None`.
  - `NOTE_RE`, `PROVENANCE_RE`.

- [ ] **Step 1: Write the failing tests**

```python
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


def test_registry_reads_projects_toml(tmp_path):
    cfg = tmp_path / "cfg" / "tasks"
    cfg.mkdir(parents=True)
    (cfg / "projects.toml").write_text(f'[projects]\nai = "{tmp_path / "ai"}"\n')
    assert se.registry({"XDG_CONFIG_HOME": str(tmp_path / "cfg")}) == {"ai": (tmp_path / "ai").resolve()}
    assert se.registry({"HOME": str(tmp_path / "nohome")}) == {}


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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q -k "registry or task_copies or read_task or note_kind"`
Expected: FAIL with `AttributeError: registry`.

- [ ] **Step 3: Implement**

```python
# --- task records --------------------------------------------------------------

NOTE_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) \(([^)]*)\): (.*)$")
PROVENANCE_RE = re.compile(r"^\s+provenance: (\{.*\})\s*$")


@dataclass(frozen=True)
class Note:
    at_ms: int
    text: str
    harness_session: str | None
    path: Path
    line: int


@dataclass
class TaskRecord:
    task_id: str
    status: str | None
    started_ms: int | None
    completed: list[tuple[int, Path]]
    notes: list[Note]
    copies: list[Path]
    unreadable: list[Path]


def registry(env: dict) -> dict[str, Path]:
    if env.get("XDG_CONFIG_HOME"):
        config = Path(env["XDG_CONFIG_HOME"])
    elif env.get("HOME"):
        config = Path(env["HOME"]) / ".config"
    else:
        return {}
    path = config / "tasks" / "projects.toml"
    if not path.is_file():
        return {}
    projects = tomllib.loads(path.read_text()).get("projects", {})
    return {prefix: Path(root).expanduser().resolve() for prefix, root in projects.items()}


def task_copies(root: Path) -> tuple[list[Path], list[Path]]:
    """Every tasks/ directory holding this project's records: the root and each worktree."""
    listing = subprocess.run(["git", "-C", str(root), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, check=True).stdout
    paths = [Path(line[len("worktree "):]) for line in listing.splitlines() if line.startswith("worktree ")]
    if root.resolve() not in [p.resolve() if p.exists() else p for p in paths]:
        paths.insert(0, root)
    readable, unreadable = [], []
    for p in paths:
        tasks_dir = p / "tasks"
        (readable if tasks_dir.is_dir() else unreadable).append(tasks_dir if tasks_dir.is_dir() else p)
    return readable, unreadable


def note_kind(text: str) -> str | None:
    if text in ("started", "resumed"):
        return "start"
    if text.startswith("parked (waiting on "):
        return "park"
    if text in ("done", "dropped") or text.startswith("completed; next due"):
        return "close"
    return None


def _parse_task_file(path: Path) -> tuple[dict, list[Note]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    head, _, body = text[4:].partition("\n---\n") if text.startswith("---\n") else ("", "", text)
    fields = {}
    for line in head.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    notes: list[Note] = []
    first_body_line = head.count("\n") + 4  # opening fence, the head lines, closing fence, then the body
    for offset, line in enumerate(body.splitlines(), first_body_line):
        m = NOTE_RE.match(line)
        if m:
            notes.append(Note(at_ms(m.group(1)), m.group(3).strip(), None, path, offset))
            continue
        pm = PROVENANCE_RE.match(line)
        if pm and notes:
            try:
                session = json.loads(pm.group(1)).get("harness_session")
            except json.JSONDecodeError:
                session = None
            notes[-1] = replace(notes[-1], harness_session=session)
    return fields, notes


def read_task(root: Path, task_id: str) -> TaskRecord | None:
    readable, unreadable = task_copies(root)
    record = None
    seen: dict[tuple[int, str], Note] = {}
    copies = []
    for tasks_dir in readable:
        path = tasks_dir / f"{task_id}.md"
        if not path.is_file():
            continue
        fields, notes = _parse_task_file(path)
        copies.append(path)
        if record is None:
            record = TaskRecord(task_id, fields.get("status"), None, [], [], [], unreadable)
        if fields.get("started"):
            stamp = at_ms(fields["started"])
            record.started_ms = stamp if record.started_ms is None else min(record.started_ms, stamp)
        if fields.get("completed"):
            record.completed.append((at_ms(fields["completed"]), path))
        for n in notes:
            seen.setdefault((n.at_ms, n.text), n)
    if record is None:
        return None
    record.notes = sorted(seen.values(), key=lambda n: (n.at_ms, n.text))
    record.completed.sort()
    record.copies = copies
    return record
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q`
Expected: all pass. If `test_read_task…` fails on `line > 0` only, check `_parse_task_file`'s offset arithmetic against the fixture (front matter of 8 lines + 2 fences → the first body line is 11).

- [ ] **Step 5: Commit**

```bash
git add agents/bin/session-episodes agents/bin/test_session_episodes.py
git commit -m "feat(session-episodes): read task records across worktree copies"
```

---

### Task 4: Turn outcome, next human turn, and continuation across files

**Files:**
- Modify: `agents/bin/session-episodes` (new section after task records)
- Modify: `agents/bin/test_session_episodes.py`

**Interfaces:**
- Consumes: `Session`, `Event` (Task 1).
- Produces:
  - `Turn(ended_at, outcome, end_index)` frozen dataclass; `outcome` ∈ `completed | interrupted | wait | unknown`; `end_index` is the index in `session.events` of the last event that belongs to the turn.
  - `turn_after(session: Session, anchor_index: int) -> Turn` — the turn containing the tool_call at `anchor_index` (§4.3).
  - `next_human_after(session: Session, end_index: int) -> Event | None`.
  - `identity(event: Event) -> tuple` — `("uuid", uuid)` when present else `(kind, at_ms, call_id, text_digest)`.
  - `continuation(sessions_and_anchors: list[tuple[Session, int]]) -> tuple[Session, int] | None` — the file to read the episode's continuation from, or `None` when files diverge before the boundary (§4.1: prefix-compatible main-line identities from the anchor through each file's boundary — its next human event inclusive, or its end).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q -k "turn or continuation"`
Expected: FAIL with `AttributeError: turn_after`.

- [ ] **Step 3: Implement**

```python
# --- turns and continuation ----------------------------------------------------

@dataclass(frozen=True)
class Turn:
    ended_at: int
    outcome: str
    end_index: int


def _claude_turn(session: Session, anchor_index: int) -> Turn:
    events = session.events
    results: set[str] = set()
    last_assistant = None
    last_index = anchor_index
    outcome = None
    for i in range(anchor_index + 1, len(events)):
        e = events[i]
        if e.kind in ("human", "interrupt"):
            if e.kind == "interrupt":
                outcome, last_index = "interrupted", i
            break
        last_index = i
        if e.kind == "tool_result":
            results.add(e.call_id)
            if e.interrupted:
                outcome = "interrupted"
        elif e.kind == "assistant":
            last_assistant = e
    for i in range(anchor_index, -1, -1):  # the anchor's own assistant record precedes it
        if events[i].kind == "assistant":
            last_assistant = last_assistant or events[i]
            break
    ended_at = last_assistant.at_ms if last_assistant else events[anchor_index].at_ms
    if outcome is None:
        tail = events[last_index]
        if tail.kind == "assistant" and tail.text_only:
            outcome = "completed"
        elif last_assistant is not None and any(p not in results for p in last_assistant.pending):
            pending_tools = {e.tool for e in events if e.kind == "tool_call" and e.call_id in last_assistant.pending and e.call_id not in results}
            outcome = "wait" if pending_tools and pending_tools <= WAIT_TOOLS else "unknown"
        else:
            outcome = "unknown"
    return Turn(ended_at, outcome, last_index)


def _codex_turn(session: Session, anchor_index: int) -> Turn:
    events = session.events
    answered: set[str] = set()
    last_call = None
    last_index = anchor_index
    for i in range(anchor_index + 1, len(events)):
        e = events[i]
        if e.kind == "turn_start":
            break
        last_index = i
        if e.kind == "turn_end":
            return Turn(e.at_ms, "completed", i)
        if e.kind == "turn_aborted":
            return Turn(events[i - 1].at_ms if i else e.at_ms, "interrupted", i)
        if e.kind == "tool_call":
            last_call = e
        elif e.kind == "tool_result":
            answered.add(e.call_id)
    ended_at = events[last_index].at_ms
    if last_call is not None and last_call.tool == CODEX_WAIT_TOOL and last_call.call_id not in answered:
        return Turn(ended_at, "wait", last_index)
    return Turn(ended_at, "unknown", last_index)


def turn_after(session: Session, anchor_index: int) -> Turn:
    return _claude_turn(session, anchor_index) if session.harness == CLAUDE_HARNESS else _codex_turn(session, anchor_index)


def next_human_after(session: Session, end_index: int) -> Event | None:
    for e in session.events[end_index + 1:]:
        if e.kind == "human":
            return e
    return None


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def identity(event: Event) -> tuple:
    if event.uuid:
        return ("uuid", event.uuid, event.kind, event.call_id)
    return (event.kind, event.at_ms, event.call_id, digest(event.text))


def _boundary(session: Session, anchor_index: int) -> int:
    turn = turn_after(session, anchor_index)
    nxt = next_human_after(session, turn.end_index)
    return session.events.index(nxt) if nxt else len(session.events) - 1


def continuation(candidates: list[tuple[Session, int]]) -> tuple[Session, int] | None:
    """The file whose main line runs longest past the anchor, provided every file agrees
    with it record-for-record up to its own boundary."""
    seqs = []
    for session, anchor_index in candidates:
        stop = _boundary(session, anchor_index)
        seqs.append(([identity(e) for e in session.events[anchor_index:stop + 1]], session, anchor_index))
    # longest boundary sequence first; among equals, the file with more records after the anchor
    seqs.sort(key=lambda s: (len(s[0]), len(s[1].events) - s[2]), reverse=True)
    longest = seqs[0][0]
    for ids, _, _ in seqs[1:]:
        if longest[:len(ids)] != ids:
            return None
    return seqs[0][1], seqs[0][2]
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add agents/bin/session-episodes agents/bin/test_session_episodes.py
git commit -m "feat(session-episodes): turn outcomes, next human turn and fork continuation"
```

---

### Task 5: Episode assembly — anchors, transitions, window, labels, candidates, summary

**Files:**
- Modify: `agents/bin/session-episodes` (new section after turns)
- Modify: `agents/bin/test_session_episodes.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `episode_id(harness: str, call_id: str, task_id: str) -> str` — first 12 hex of SHA-256 over `f"{harness}\n{call_id}\n{task_id}"`.
  - `STATUS_PATTERNS: tuple[re.Pattern, ...]` (§4.5 list); `heuristic_label(text: str) -> bool`.
  - `source_ref(session: Session, event: Event) -> str` — `f"{harness}:{session_id}:{path}#L{line}"`; `task_ref(note: Note) -> str` — `f"tasks:{path}#L{line}"`.
  - `Inputs(sessions: list[Session], roots: dict[str, Path], labels: dict[str, dict], anchors: dict[str, dict], now_ms: int, window_ms: int, since_ms: int | None, project: str | None)` dataclass.
  - `Transition(at_ms, source, refs, interval)` frozen dataclass; `_transitions_of(kind, task_id, record, transitions, started_at) -> list[Transition]` sorted by time; `_straddles(found, cutoff) -> bool`.
  - `build_episodes(inputs: Inputs) -> tuple[list[dict], list[dict], dict]` — `(episodes, candidates, summary)`. Episode keys exactly: `id, task_id, session_key, started_at, ended_at, parked_at, closed_at, next_human_at, status_question, label_source, anchor_source, closure_source, window_complete, join_class, source_refs`. Candidate keys: `id, task_id, reason, sessions, call_at, stamp_delta_s, source_refs` — `stamp_delta_s` is the signed distance from the record's `started:` stamp when it is within 120 s, else `null`: a hint for the reviewer, never a confirmation. `anchor_source` ∈ `result | note | reviewed`. Summary keys: `files {harness: n}, excluded {subagent, non-interactive}, anchors_seen, anchors_multi_file, anchors_collapsed, unconfirmed {outside-grammar, no-id-line, error-output, nested, unsupported-wrapper}, unsupported_unknown_task, unregistered, turns {completed, wait, interrupted, unknown, ambiguous}, episodes, label_sources {heuristic, reviewed}, stale_labels, stale_confirmations, note_missing, origin_unknown, window_ms, since_ms, roots {claude, codex}, malformed_lines`.

- [ ] **Step 1: Write the failing tests**

```python
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


def inputs(tmp_path, sessions, roots, now=ms(60) + 10 * 60 * 1000 + 1, labels=None, anchors=None, window_min=10):
    return se.Inputs(sessions, roots, labels or {}, anchors or {}, now, window_min * 60 * 1000, None, None)


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

```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q -k "episode or lit_shape or unsupported or collapse or completed_turns or park_and_close or transcript or note_inside or window or missing_record or labels or heuristic or fork or divergent or population"`
Expected: FAIL with `AttributeError: Inputs`.

- [ ] **Step 3: Implement**

```python
# --- episodes ------------------------------------------------------------------

STATUS_PATTERNS = tuple(re.compile(p) for p in (
    r"still (running|executing|going|working)",
    r"is (it|that|this|the task) (still )?(running|done|finished|complete)",
    r"(did|has) (it|that) (finish|complete|stop)",
    r"\bstatus\b",
    r"\bprogress\b",
    r"where (are we|is it|did .* (stop|leave off))",
    r"what('s| is) (left|next|happening)",
    r"(are|is) (you|anything) (still )?(working|running)",
))
TOLERANCE_MS = 120_000


def heuristic_label(text: str) -> bool:
    low = text.lower()
    return any(p.search(low) for p in STATUS_PATTERNS)


def episode_id(harness: str, call_id: str, task_id: str) -> str:
    return hashlib.sha256(f"{harness}\n{call_id}\n{task_id}".encode("utf-8")).hexdigest()[:12]


def source_ref(session: Session, event: Event) -> str:
    return f"{session.harness}:{session.session_id}:{session.path}#L{event.line}"


def task_ref(note: Note) -> str:
    return f"tasks:{note.path}#L{note.line}"


def session_key(session: Session) -> str:
    return f"{session.harness}:{session.session_id}"


@dataclass
class Inputs:
    sessions: list[Session]
    roots: dict[str, Path]
    labels: dict[str, dict]
    anchors: dict[str, dict]
    now_ms: int
    window_ms: int
    since_ms: int | None = None
    project: str | None = None


@dataclass
class _Anchor:
    task_id: str
    call_id: str
    holders: list[tuple[Session, int]] = field(default_factory=list)
    nested: bool = False  # the start text sits only in executable heredoc/-c text: review only


def _result_for(session: Session, index: int) -> Event | None:
    call_id = session.events[index].call_id
    for e in session.events[index + 1:]:
        if e.kind == "tool_result" and e.call_id == call_id:
            return e
    return None


def _new_summary(inputs: Inputs) -> dict:
    return {"files": {}, "excluded": {"subagent": 0, "non-interactive": 0}, "anchors_seen": 0, "anchors_multi_file": 0, "anchors_collapsed": 0,
            "unconfirmed": {"outside-grammar": 0, "no-id-line": 0, "error-output": 0, "nested": 0, "unsupported-wrapper": 0},
            "unsupported_unknown_task": 0, "unregistered": 0,
            "turns": {"completed": 0, "wait": 0, "interrupted": 0, "unknown": 0, "ambiguous": 0},
            "episodes": 0, "label_sources": {"heuristic": 0, "reviewed": 0}, "stale_labels": 0,
            "stale_confirmations": 0, "note_missing": 0, "origin_unknown": 0, "window_ms": inputs.window_ms,
            "since_ms": inputs.since_ms, "roots": {}, "malformed_lines": 0}


def _collect_anchors(inputs: Inputs, summary: dict) -> tuple[dict[tuple, _Anchor], dict[tuple, dict]]:
    """Every tasks-start candidate keyed by (harness, call_id, task_id), and per-session
    confirmed transitions keyed the same way for §4.4."""
    anchors: dict[tuple, _Anchor] = {}
    transitions: dict[tuple, dict] = {}
    for s in inputs.sessions:
        summary["files"][s.harness] = summary["files"].get(s.harness, 0) + 1
        summary["malformed_lines"] += s.malformed
        if s.subagent:
            summary["excluded"]["subagent"] += 1
            continue
        if s.entrypoint not in INTERACTIVE[s.harness]:
            summary["excluded"]["non-interactive"] += 1
            continue
        for i, e in enumerate(s.events):
            if e.kind != "tool_call":
                continue
            if e.unsupported and not any(start_candidates(c) for c in e.commands):
                result = _result_for(s, i)
                named = ids_in_result(result.text) if result is not None else []
                if not named:
                    summary["unsupported_unknown_task"] += 1
                for task_id in named:
                    anchors.setdefault((s.harness, e.call_id, task_id), _Anchor(task_id, e.call_id)).holders.append((s, i))
            for c in e.commands:
                for task_id in start_candidates(c):
                    anchors.setdefault((s.harness, e.call_id, task_id), _Anchor(task_id, e.call_id)).holders.append((s, i))
                for task_id in nested_start_candidates(c):
                    anchors.setdefault((s.harness, e.call_id, task_id), _Anchor(task_id, e.call_id, nested=True)).holders.append((s, i))
                for sub, task_id in transitions_in(c):
                    result = _result_for(s, i)
                    readable = attributable_commands(e)
                    if result is not None and readable is not None and attribute(readable, result.text, task_id, sub) == "confirmed":
                        # a fork copies the call under the same id; keep one per (call_id, times)
                        transitions.setdefault((task_id, sub), {}).setdefault(
                            (e.at_ms, result.at_ms, e.call_id), (s, e, result))
    return anchors, transitions


def _confirm(anchor: _Anchor, record: TaskRecord | None, inputs: Inputs, summary: dict,
             holder: tuple[Session, int]) -> tuple[str | None, str | None, str | None]:
    """(anchor_source, reason, stamped_session): how this start is corroborated (§4.2).
    Order: the call's own output; this session's lifecycle note; a reviewed confirmation.
    Any error line blocks the automatic routes, and the started: stamp alone is only a hint."""
    session, index = holder
    call = session.events[index]
    result = _result_for(session, index)
    text = result.text if result is not None else ""
    if anchor.nested:
        reason = "nested"
    elif call.unsupported and not any(anchor.task_id in start_candidates(c) for c in call.commands):
        reason = "unsupported-wrapper"
    elif result is not None:
        readable = attributable_commands(call)  # a wrapper outside the single-call forms is unreadable
        verdict = attribute(readable, text, anchor.task_id) if readable is not None else "outside-grammar"
        if verdict == "confirmed":
            return "result", None, None
        reason = verdict
    else:
        reason = "no-id-line"
    if record is not None and not has_error_line(text) and not anchor.nested:
        candidates = {session_key(s) for s, _ in anchor.holders}
        for n in record.notes:
            if note_kind(n.text) == "start" and n.harness_session in candidates and abs(n.at_ms - call.at_ms) <= TOLERANCE_MS:
                return "note", None, n.harness_session
    eid = episode_id(session.harness, anchor.call_id, anchor.task_id)
    review = inputs.anchors.get(eid)
    if review is not None:
        evidence = digest("\n".join(call.commands) + call.raw + "\n" + text)
        if review.get("evidence_digest") != evidence:
            summary["stale_confirmations"] += 1
        elif review.get("confirmed"):
            return "reviewed", None, None
        else:
            return None, "retired", None
    return None, reason, None


def _stamp_delta_s(record: TaskRecord | None, call_at: int) -> int | None:
    if record is None or record.started_ms is None or abs(record.started_ms - call_at) > TOLERANCE_MS:
        return None
    return (record.started_ms - call_at) // 1000


@dataclass(frozen=True)
class Transition:
    at_ms: int
    source: str                      # note | transcript | stamp
    refs: tuple[str, ...]
    interval: tuple[int, int] | None  # (call_at, result_at) when only the transcript places it


def _transitions_of(kind: str, task_id: str, record: TaskRecord | None, transitions: dict,
                    started_at: int) -> list[Transition]:
    """Every park (kind='park') or close (kind='close') candidate at or after started_at, from
    notes, confirmed transcript calls, and — for closes — completion stamps (§4.4)."""
    found: list[Transition] = []
    notes = [n for n in (record.notes if record else []) if note_kind(n.text) == kind and n.at_ms >= started_at]
    for n in notes:
        found.append(Transition(n.at_ms, "note", (task_ref(n),), None))
    subs = ("park",) if kind == "park" else ("done", "drop")
    calls = []
    for sub in subs:
        for (call_at, result_at, _), (s, call, result) in sorted(
                transitions.get((task_id, sub), {}).items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2]))):
            if result_at >= started_at:
                calls.append((call_at, result_at, s, call, result))
    # a note is written by exactly one call: give each note to the narrowest interval holding
    # it, so a wide uncertain call cannot borrow the note of a later, tighter one
    claimed: dict[int, Note] = {}
    for n in notes:
        holders = [i for i, (call_at, result_at, *_) in enumerate(calls)
                   if i not in claimed and call_at - TOLERANCE_MS <= n.at_ms <= result_at + TOLERANCE_MS]
        if holders:
            claimed[min(holders, key=lambda i: calls[i][1] - calls[i][0])] = n
    for i, (call_at, result_at, s, call, result) in enumerate(calls):
        if i in claimed:
            continue  # already listed above by its note; the call's ref is not repeated
        found.append(Transition(result_at, "transcript", (source_ref(s, call), source_ref(s, result)),
                                (call_at, result_at)))
    if kind == "close" and record is not None:
        for stamp_ms, path in record.completed:
            if stamp_ms >= started_at:
                found.append(Transition(stamp_ms, "stamp", (f"tasks:{path}#completed",), None))
    return sorted(found, key=lambda t: (t.at_ms, t.source))


def _straddles(found: list[Transition], cutoff: int) -> bool:
    """Could a transcript-only transition have happened on the other side of the cutoff?
    Irrelevant once some transition is definitely inside the window."""
    if any(t.interval is None and t.at_ms <= cutoff for t in found):
        return False
    return any(t.interval is not None and t.interval[0] <= cutoff < t.interval[1] for t in found)


def build_episodes(inputs: Inputs) -> tuple[list[dict], list[dict], dict]:
    summary = _new_summary(inputs)
    anchors, transitions = _collect_anchors(inputs, summary)
    records: dict[str, TaskRecord | None] = {}
    episodes, candidates = [], []
    collapsed: set[tuple] = set()
    for key, anchor in sorted(anchors.items(), key=lambda kv: (str(kv[1].holders[0][0].path), kv[1].holders[0][1], kv[0][2])):
        harness, call_id, task_id = key
        summary["anchors_seen"] += 1
        if len({s.path for s, _ in anchor.holders}) > 1:
            summary["anchors_multi_file"] += 1
        prefix = task_id.rsplit("-", 1)[0]
        if prefix not in inputs.roots or (inputs.project and prefix != inputs.project):
            summary["unregistered"] += prefix not in inputs.roots
            continue
        if task_id not in records:
            records[task_id] = read_task(inputs.roots[prefix], task_id)
        record = records[task_id]
        chosen = continuation(anchor.holders)
        if chosen is None:
            summary["turns"]["ambiguous"] += 1
            continue
        session, index = chosen
        source, reason, stamped = _confirm(anchor, record, inputs, summary, chosen)
        call = session.events[index]
        holder_keys = {session_key(s) for s, _ in anchor.holders}
        if stamped is None and record is not None:  # origin is a fact about the notes, whatever confirmed the start
            stamped = next((n.harness_session for n in record.notes if note_kind(n.text) == "start"
                            and n.harness_session in holder_keys and abs(n.at_ms - call.at_ms) <= TOLERANCE_MS), None)
        if inputs.since_ms is not None and call.at_ms < inputs.since_ms:
            continue
        eid = episode_id(harness, call_id, task_id)
        if source is None:
            if reason in summary["unconfirmed"]:
                summary["unconfirmed"][reason] += 1
                candidates.append({"id": eid, "task_id": task_id, "reason": reason,
                                   "sessions": sorted({session_key(s) for s, _ in anchor.holders}),
                                   "call_at": call.at_ms, "stamp_delta_s": _stamp_delta_s(record, call.at_ms),
                                   "source_refs": [source_ref(session, call)] +
                                                  [source_ref(s, s.events[i]) for s, i in anchor.holders if s is not session]})
            continue
        turn = turn_after(session, index)
        collapse_key = (session.path, task_id, turn.end_index)
        if collapse_key in collapsed:
            summary["anchors_collapsed"] += 1
            continue
        collapsed.add(collapse_key)
        summary["turns"][turn.outcome] += 1
        if turn.outcome != "completed":
            continue
        refs = [source_ref(session, session.events[index]), source_ref(session, session.events[turn.end_index])]
        cutoff = turn.ended_at + inputs.window_ms
        parks = _transitions_of("park", task_id, record, transitions, call.at_ms)
        closes = _transitions_of("close", task_id, record, transitions, call.at_ms)
        summary["note_missing"] += sum(1 for t in parks + closes if t.source == "transcript")
        first_park = parks[0] if parks else None
        first_close = closes[0] if closes else None
        parked_at = first_park.at_ms if first_park else None
        closed_at = first_close.at_ms if first_close else None
        closure_source = first_close.source if first_close else None
        for t in (first_park, first_close):
            if t is not None:
                refs.extend(t.refs)
        # a definite park OR close inside the window settles the question; otherwise any
        # transcript-only transition whose interval crosses the cutoff leaves it open
        definite_inside = any(t.interval is None and t.at_ms <= cutoff for t in parks + closes)
        uncertain = not definite_inside and (_straddles(parks, cutoff) or _straddles(closes, cutoff))
        nxt = next_human_after(session, turn.end_index)
        status, label_source = None, None
        if nxt is not None:
            refs.append(source_ref(session, nxt))
            review = inputs.labels.get(eid)
            if review is not None and review.get("message_digest") == digest(nxt.text):
                status, label_source = bool(review["status_question"]), "reviewed"
            else:
                if review is not None:
                    summary["stale_labels"] += 1
                status, label_source = heuristic_label(nxt.text), "heuristic"
            summary["label_sources"][label_source] += 1
        for s, i in anchor.holders:
            if s is not session:
                refs.append(source_ref(s, s.events[i]))
        sessions_holding = {session_key(s) for s, _ in anchor.holders}
        if len(sessions_holding) == 1:
            key_out = next(iter(sessions_holding))
        elif stamped:
            key_out = stamped
        else:
            key_out = None
            summary["origin_unknown"] += 1
        if record is None or key_out is None:
            join_class = "unknown"
        elif stamped or any(note_kind(n.text) == "start" and n.harness_session == key_out for n in record.notes):
            join_class = "stamped"
        else:
            join_class = "inferred"
        window = (record is not None and not record.unreadable and inputs.now_ms >= cutoff
                  and join_class != "unknown" and not uncertain)
        episodes.append({"id": eid, "task_id": task_id, "session_key": key_out, "started_at": call.at_ms,
                         "ended_at": turn.ended_at, "parked_at": parked_at, "closed_at": closed_at,
                         "next_human_at": nxt.at_ms if nxt else None, "status_question": status,
                         "label_source": label_source, "anchor_source": source, "closure_source": closure_source,
                         "window_complete": window, "join_class": join_class, "source_refs": refs})
    summary["episodes"] = len(episodes)
    return episodes, candidates, summary
```

- [ ] **Step 4: Run the tests; fix until green**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q`
Expected: all pass. Known fiddly spots: (a) `test_fork_keeps_id…` asserts `join_class == "unknown"` when `session_key` is null — that is the `key_out is None` branch; (b) `test_park_and_close_sources_earliest_wins` with the `completed:` stamp only — `closure_source == "stamp"`; (c) `note_missing` counts transcript-only transitions, one per interval.

- [ ] **Step 5: Commit**

```bash
git add agents/bin/session-episodes agents/bin/test_session_episodes.py
git commit -m "feat(session-episodes): assemble episodes, candidates and the run summary"
```

---

### Task 6: CLI — extract, show, confirm, label

**Files:**
- Modify: `agents/bin/session-episodes` (final section)
- Modify: `agents/bin/test_session_episodes.py`

**Interfaces:**
- Consumes: `build_episodes`, `Inputs`, readers, `registry`.
- Produces:
  - `scan_stores(claude_root: Path, codex_root: Path) -> list[Session]` — every `*/*.jsonl` under the Claude root and `**/*.jsonl` under the Codex root, sorted by path.
  - `sidecar(episodes_path: Path, kind: str) -> Path` — `<stem>.<kind>.jsonl` beside it, `kind` ∈ `candidates | labels | anchors`.
  - `read_jsonl_map(path: Path) -> dict[str, dict]` — last line per `id` wins; a line that is not a JSON object with `id` raises `SystemExit(2)` with the path and line number.
  - `main(argv: list[str], env: dict) -> int`; exit codes: 0 ok, 2 usage/unknown id/bad sidecar.
  - `show` output format (stdout): `id`, `kind` (`episode`/`candidate`), `task_id`, then for each ref `== <ref>` followed by the record's text: the anchor's commands, the result text, the turn's last assistant text, the next human turn text — labelled `-- anchor commands`, `-- result`, `-- last assistant`, `-- next human turn`.

- [ ] **Step 1: Write the failing tests**

```python
# --- CLI -----------------------------------------------------------------------

def run_cli(argv, env):
    import io, contextlib
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = se.main(argv, env)
    return code, out.getvalue(), err.getvalue()


def cli_env(tmp_path, roots):
    cfg = tmp_path / "cfg" / "tasks"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "projects.toml").write_text("[projects]\n" + "".join(f'{k} = "{v}"\n' for k, v in roots.items()))
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q -k "cli or extract or round_trip or filters"`
Expected: FAIL with `AttributeError: main`.

- [ ] **Step 3: Implement**

```python
# --- files and CLI -------------------------------------------------------------

def scan_stores(claude_root: Path, codex_root: Path) -> list[Session]:
    sessions = []
    if claude_root.is_dir():
        sessions += [read_claude(p) for p in sorted(claude_root.glob("*/*.jsonl"))]
    if codex_root.is_dir():
        sessions += [read_codex(p) for p in sorted(codex_root.rglob("*.jsonl"))]
    return sessions


def sidecar(episodes_path: Path, kind: str) -> Path:
    return episodes_path.with_name(f"{episodes_path.stem}.{kind}.jsonl")


def read_jsonl_map(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            obj = None
        if not isinstance(obj, dict) or "id" not in obj:
            raise SystemExit(f"session-episodes: {path}:{number}: not a JSON object with an id")
        out[obj["id"]] = obj
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def _roots(env: dict) -> tuple[Path, Path]:
    home = Path(env.get("HOME", "~")).expanduser()
    return (Path(env.get("SESSION_LOGS_CLAUDE") or home / ".claude" / "projects"),
            Path(env.get("SESSION_LOGS_CODEX") or home / ".codex" / "sessions"))


def cmd_extract(args, env: dict) -> int:
    out = Path(args.out)
    labels_path = Path(args.labels) if args.labels else sidecar(out, "labels")
    anchors_path = Path(args.anchors) if args.anchors else sidecar(out, "anchors")
    roots = registry(env)
    for prefix, root in roots.items():
        if not (root / "tasks").is_dir():
            raise SystemExit(f"session-episodes: registered project {prefix} has no tasks/ under {root}")
    claude_root, codex_root = _roots(env)
    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    since = now - args.since * 86_400_000 if args.since is not None else None
    inputs = Inputs(scan_stores(claude_root, codex_root), roots, read_jsonl_map(labels_path), read_jsonl_map(anchors_path),
                    now, args.window_minutes * 60_000, since, args.project)
    episodes, candidates, summary = build_episodes(inputs)
    summary["roots"] = {"claude": str(claude_root), "codex": str(codex_root)}
    summary["missing_roots"] = [str(r) for r in (claude_root, codex_root) if not r.is_dir()]
    write_jsonl(out, episodes)
    write_jsonl(sidecar(out, "candidates"), candidates)
    print(json.dumps(summary, sort_keys=True), file=sys.stderr)
    return 0


def _lookup(episodes_path: Path, wanted: str) -> tuple[str, dict]:
    for kind, path in (("episode", episodes_path), ("candidate", sidecar(episodes_path, "candidates"))):
        row = read_jsonl_map(path).get(wanted)
        if row is not None:
            return kind, row
    raise SystemExit(f"session-episodes: unknown id {wanted} in {episodes_path} and its candidates")


def _parse_ref(ref: str) -> tuple[str, Path, int]:
    head, _, line = ref.rpartition("#L")
    harness, _, rest = head.partition(":")
    _, _, path = rest.partition(":")
    return harness, Path(path), int(line)


def _session_for(ref: str, cache: dict) -> Session:
    harness, path, _ = _parse_ref(ref)
    if path not in cache:
        cache[path] = read_claude(path) if harness == CLAUDE_HARNESS else read_codex(path)
    return cache[path]


def _evidence(row: dict, kind: str, cache: dict) -> tuple[str, str, str, str]:
    """(anchor commands, result text, last assistant text, next human text) for show/confirm/label."""
    session = _session_for(row["source_refs"][0], cache)
    line = _parse_ref(row["source_refs"][0])[2]
    # the episode id hashes the call id, so the call on this line whose id reproduces it is the one
    index = next(i for i, e in enumerate(session.events) if e.kind == "tool_call" and e.line == line
                 and episode_id(session.harness, e.call_id, row["task_id"]) == row["id"])
    call = session.events[index]
    result = _result_for(session, index)
    turn = turn_after(session, index)
    last_assistant = next((e for e in reversed(session.events[index:turn.end_index + 1]) if e.kind == "assistant"), None)
    nxt = next_human_after(session, turn.end_index) if kind == "episode" else None
    return ("\n".join(call.commands) + call.raw, result.text if result else "",
            last_assistant.text if last_assistant else "", nxt.text if nxt else "")


def cmd_show(args, env: dict) -> int:
    kind, row = _lookup(Path(args.episodes), args.id)
    commands, result, assistant, human = _evidence(row, kind, {})
    print(f"id: {row['id']}\nkind: {kind}\ntask_id: {row['task_id']}")
    for ref in row["source_refs"]:
        print(f"== {ref}")
    for label, body in (("anchor commands", commands), ("result", result), ("last assistant", assistant), ("next human turn", human)):
        print(f"-- {label}\n{body}")
    return 0



def cmd_confirm(args, env: dict) -> int:
    episodes_path = Path(args.episodes)
    kind, row = _lookup(episodes_path, args.id)
    commands, result, _, _ = _evidence(row, kind, {})
    anchors_path = Path(args.anchors) if args.anchors else sidecar(episodes_path, "anchors")
    read_jsonl_map(anchors_path)  # validates the file before appending
    anchors_path.parent.mkdir(parents=True, exist_ok=True)
    with open(anchors_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"id": row["id"], "confirmed": args.verdict == "yes",
                                 "evidence_digest": digest(commands + "\n" + result),
                                 "confirmed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                                sort_keys=True) + "\n")
    return 0


def cmd_label(args, env: dict) -> int:
    episodes_path = Path(args.episodes)
    kind, row = _lookup(episodes_path, args.id)
    if kind != "episode":
        raise SystemExit(f"session-episodes: {args.id} is a candidate; confirm it first")
    _, _, _, human = _evidence(row, kind, {})
    labels_path = Path(args.labels) if args.labels else sidecar(episodes_path, "labels")
    read_jsonl_map(labels_path)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    with open(labels_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"id": row["id"], "status_question": args.verdict == "yes",
                                 "message_digest": digest(human),
                                 "labelled_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                                sort_keys=True) + "\n")
    return 0


def main(argv: list[str], env: dict) -> int:
    parser = argparse.ArgumentParser(prog="session-episodes", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("--since", type=int, metavar="DAYS")
    ex.add_argument("--project", metavar="PREFIX")
    ex.add_argument("--window-minutes", type=int, default=10)
    ex.add_argument("--labels")
    ex.add_argument("--anchors")
    ex.add_argument("--out", required=True)
    ex.set_defaults(run=cmd_extract)
    for name, run, verdict, extra in (("show", cmd_show, False, None), ("confirm", cmd_confirm, True, "--anchors"),
                                      ("label", cmd_label, True, "--labels")):
        p = sub.add_parser(name)
        p.add_argument("id")
        if verdict:
            p.add_argument("verdict", choices=("yes", "no"))
        p.add_argument("--episodes", required=True)
        if extra:
            p.add_argument(extra)
        p.set_defaults(run=run)
    try:
        args = parser.parse_args(argv)
        return args.run(args, env)
    except SystemExit as error:
        if isinstance(error.code, str):
            print(error.code, file=sys.stderr)
            return 2
        return int(error.code or 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], dict(os.environ)))
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q`
Expected: all pass. If `test_cli_errors` fails on the `tasks-gone` case, the check belongs before scanning (it is in `cmd_extract` already) — confirm the message contains `tasks/`.

- [ ] **Step 5: Run the script by path against an empty store to see the summary shape**

Run: `SESSION_LOGS_CLAUDE=/nonexistent SESSION_LOGS_CODEX=/nonexistent agents/bin/session-episodes extract --out /tmp/x/episodes.jsonl; echo exit=$?`
Expected: `exit=0`, one JSON summary line on stderr with `"episodes": 0` and both paths under `"missing_roots"`.

- [ ] **Step 6: Commit**

```bash
git add agents/bin/session-episodes agents/bin/test_session_episodes.py
git commit -m "feat(session-episodes): extract, show, confirm and label commands"
```

---

### Task 7: The `session-logs` skill, its links, and the real-data acceptance run

**Files:**
- Create: `agents/skills/session-logs/SKILL.md`
- Modify: `agents/skills/README.md` (one bullet after the `flow/` bullet)
- Create (outside the repo): symlink `~/.claude/skills/session-logs` → `~/d/ai/agents/skills/session-logs`

**Interfaces:**
- Consumes: the CLI (Task 6).
- Produces: the skill text an agent follows; the acceptance evidence recorded on `ai-bc49ed`.

- [ ] **Step 1: Write the skill**

```markdown
---
name: session-logs
description: Use when you need to read a coding agent's local session store — find the session behind a task, worktree or commit, read a turn, tell human turns from injected context — or to prepare pre-flow episodes for obs's proxy baseline with session-episodes.
---

# session-logs

Where each harness keeps its sessions, what the records look like, and how to
turn them into evidence without pasting transcripts anywhere. The tool is
`~/.agents/bin/session-episodes` (`agents/bin/session-episodes` when standing
in `ai`); nothing puts it on PATH. Its contract is
`docs/specs/2026-09-19-session-logs-design.md` in the `ai` checkout.

## Stores

| Harness | Store | Unit | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl` | one JSONL file per session; a subagent transcript is a file whose records are all `isSidechain` | `--resume` forks a new uuid that copies the old records (same `uuid`s and tool ids, `sessionId` rewritten): two files, one conversation |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl` | one rollout per session; `session_meta` first | no session on this host has a second rollout |
| opencode | `~/.local/share/opencode/opencode.db` (sqlite; `opencode-local.db` beside it) | rows, not files | store only; tooling arrives with obs-175b10 |
| Crush | `~/.crush/crush.db` and `<project>/.crush/crush.db` (sqlite) | rows, per project | store only; as above |

## Record shapes

Claude Code — one JSON object per line. The ones that matter:

    {"type":"user","uuid":"…","parentUuid":"…","sessionId":"…","cwd":"…","gitBranch":"…","timestamp":"2026-09-17T12:00:00.000Z",
     "message":{"role":"user","content":"Let's pick up ai-6c8245"}}
    {"type":"assistant","uuid":"…","timestamp":"…","message":{"role":"assistant","content":[
       {"type":"tool_use","id":"toolu_…","name":"Bash","input":{"command":"tasks start ai-6c8245"}}]}}
    {"type":"user","timestamp":"…","message":{"role":"user","content":[
       {"type":"tool_result","tool_use_id":"toolu_…","content":"{\"id\":\"ai-6c8245\",\"warnings\":[]}"}]}}

`message.content` is a string or a list of `text` / `tool_use` / `tool_result`
blocks. `isMeta`, `isCompactSummary`, `isSidechain` mark records that are not
the conversation's main line. There is no `stopReason`; a turn ends where the
next human record begins.

Codex — `{"timestamp","type","payload"}` per line:

    {"type":"session_meta","payload":{"id":"…","cwd":"…","originator":"codex-tui","thread_source":"user"}}
    {"type":"event_msg","payload":{"type":"task_started","turn_id":"…"}}      # also task_complete, turn_aborted, user_message
    {"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"…"}]}}
    {"type":"response_item","payload":{"type":"custom_tool_call","call_id":"call_…","input":"const r = await tools.exec_command({cmd:\"tasks start lit-f43833\"}) …"}}
    {"type":"response_item","payload":{"type":"custom_tool_call_output","call_id":"call_…","output":[{"type":"input_text","text":"…"}]}}

Older rollouts use `function_call` (`name: "shell"`, `arguments` JSON with a
`command` array) and `function_call_output` (`output` string). A turn is
bracketed by `task_started` … `task_complete`; `turn_aborted` ends one early.

## Human or injected

Not the human, in Claude Code: `isMeta`, `isCompactSummary`, `isSidechain`,
a user record holding only `tool_result` blocks, and text beginning `<`
(system reminders, hook context). Not the human, in Codex: user messages
beginning `# AGENTS.md`, `<environment_context>`, `<INSTRUCTIONS>`,
`<skills_instruct`, `<turn_aborted>`, `<permissions`, `<user_shell`,
`<collaboration_mode`, or any `<`. The same list lives in obs's
`claude_adapter.py` / `codex_adapter.py` and in `session-episodes`; change all
three together.

## Finding the session behind a thing

- **A task id.** Since 2026-09-17 lifecycle notes carry
  `provenance: {"harness_session": "claude-code:<uuid>" | "codex:<uuid>", …}`;
  `tasks show <id>` prints them. Before that, search *tool-call inputs* for
  `tasks start <id>` — never the raw text, which also matches the tasks
  skill's own instructions and Codex's AGENTS.md injection (a text grep hits
  ~1,400 Codex files; tool calls are the real ones):

      python3 - <<'EOF'
      import json, glob, os
      for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
          for n, line in enumerate(open(f, errors="replace"), 1):
              if '"tool_use"' not in line or "tasks start ai-6c8245" not in line: continue
              r = json.loads(line)
              for b in (r.get("message") or {}).get("content") or []:
                  if isinstance(b, dict) and b.get("type") == "tool_use" and "tasks start ai-6c8245" in str((b.get("input") or {}).get("command", "")):
                      print(f"{f}#L{n}", r.get("sessionId"))
      EOF

  For Codex, filter `response_item` lines whose payload type is
  `function_call`/`custom_tool_call` and search their `arguments`/`input`.
- **A worktree.** `cwd` on any timed Claude record; `session_meta.cwd` in Codex.
- **A commit.** A tool call whose command contains `git commit`, then the sha
  in its result.

## Reading a turn

A turn is one human record through the assistant's last record before the
next human record. Print one Claude turn's texts by line range:

    sed -n '120,180p' ~/.claude/projects/<slug>/<uuid>.jsonl | python3 -c '
    import json,sys
    for l in sys.stdin:
        r=json.loads(l); c=(r.get("message") or {}).get("content")
        t=c if isinstance(c,str) else " ".join(b.get("text","") for b in c if isinstance(b,dict) and b.get("type")=="text") if isinstance(c,list) else ""
        if t.strip(): print(r["type"], r["timestamp"], t[:200])'

`session-episodes show <id> --episodes <file>` prints a known episode's anchor,
result, last assistant text and next human turn with their refs; prefer it
over hand-reading when an id exists.

## Preparing pre-flow episodes

The output feeds obs Task 4 (`obs baseline --input episodes.jsonl`). One pass:

1. `~/.agents/bin/session-episodes extract --out <dir>/episodes.jsonl`
   The JSON summary on stderr is the run's provenance: files per harness,
   exclusions, unconfirmed starts by reason, turn outcomes, label sources,
   `note_missing`, `origin_unknown`. Keep it with the file.
2. Hand over `episodes.jsonl` and the summary now: the consumer reports
   coverage per harness and does not wait for the queue.
3. Walk `<dir>/episodes.candidates.jsonl` within the budget the consumer set,
   `stamp_delta_s` candidates first, then `error-output`: for each, `show <id>
   --episodes …`; if the start's `{"id": …, "warnings": …}` line is in the
   result and belongs to this start, `confirm <id> yes`; otherwise `confirm
   <id> no`. The unreviewed remainder stays in the file and in the summary.
4. Re-run `extract`. Review every episode with `status_question: true` and a
   sample of `false` with `show`; correct with `label <id> yes|no`.
5. Re-run `extract` once more and hand over `episodes.jsonl` with the summary.

What the file contains: ids, timestamps, booleans, `source_refs`. No
transcript text, no commands beyond the task id they named. The refs are
absolute paths under your home — local evidence for a local report; do not
paste the file anywhere public. What it cannot see: a park or close recorded
only on a branch deleted unmerged by a session whose store is not on this
host; `note_missing` in the summary is the measured lower bound on that loss.
```

- [ ] **Step 2: Add the README bullet and the link**

In `agents/skills/README.md`, after the `flow/` bullet:

```markdown
- `session-logs/` — where each harness keeps its session store, how to read it,
  and the `agents/bin/session-episodes` tool that prepares pre-flow episodes for
  obs. Linked from `~/.claude/skills/session-logs` like the others.
```

Run: `ln -s ~/d/ai/agents/skills/session-logs ~/.claude/skills/session-logs && ls -la ~/.claude/skills/session-logs`
Expected: the symlink resolves to the worktree-independent path under `~/d/ai` (the main checkout; the skill file exists there only after this branch merges, which is fine — `flow` is linked the same way).

- [ ] **Step 3: Commit**

```bash
git add agents/skills/session-logs/SKILL.md agents/skills/README.md
git commit -m "docs(skills): session-logs skill over the session stores and session-episodes"
```

- [ ] **Step 4: Real-data acceptance run (recorded on the task, not in tests)**

Run, from the worktree:

```bash
mkdir -p $TMPDIR/session-episodes && agents/bin/session-episodes extract --out $TMPDIR/session-episodes/episodes.jsonl 2> $TMPDIR/session-episodes/summary.json
python3 -c 'import json; print(json.dumps(json.load(open("$TMPDIR/session-episodes/summary.json")), indent=1))'
grep -c . $TMPDIR/session-episodes/episodes.jsonl $TMPDIR/session-episodes/episodes.candidates.jsonl
grep '"task_id": "lit-f43833"' $TMPDIR/session-episodes/episodes.candidates.jsonl
```

Expected: the `lit-f43833` start from rollout `…01a0af15-98bd-7d83-8d44-56080d74f8e7.jsonl` line 44 is a candidate with `reason: outside-grammar` (three literals share one output, and only a single literal `tasks start` is attributed). Then:

```bash
agents/bin/session-episodes show <that id> --episodes $TMPDIR/session-episodes/episodes.jsonl
agents/bin/session-episodes confirm <that id> yes --episodes $TMPDIR/session-episodes/episodes.jsonl
agents/bin/session-episodes extract --out $TMPDIR/session-episodes/episodes.jsonl 2> $TMPDIR/session-episodes/summary.json
grep '"task_id": "lit-f43833"' $TMPDIR/session-episodes/episodes.jsonl | python3 -c 'import json,sys; e=json.loads(sys.stdin.read()); print({k:e[k] for k in ("anchor_source","status_question","label_source","ended_at","next_human_at","parked_at","closed_at","window_complete","join_class")})'
python3 - <<'EOF'
import json
rows=[json.loads(l) for l in open("$TMPDIR/session-episodes/episodes.jsonl")]
kids=[r for r in rows if r["task_id"].startswith("lit-") and r["closed_at"] is not None]
print("lit episodes with closed_at:", len(kids), "closure sources:", {r["closure_source"] for r in kids})
EOF
```

Expected: `anchor_source: reviewed`, `status_question: True` (the next human turn is "Great! Is the task still executing?"), `parked_at: None`; the lit children that were started in scanned sessions carry a `closed_at` with `closure_source` in `{note, transcript, stamp}`. Record the summary counts, the lit episode's field values and the commands run in a `tasks note ai-bc49ed …`; do not paste transcript text. If the lit start is *not* a candidate (for example the anchor is confirmed by result because the id line is attributable after all), record that outcome instead — the acceptance is that the episode exists with the right fields, not the route.

- [ ] **Step 5: Verify the tree and close**

Run: `python3 -m pytest agents/bin/ -q && tasks check --pretty`
Expected: all tests pass; `tasks check` reports only `doc_missing` for git-excluded plan/spec files in the worktree (they exist in the main checkout) — confirm `ok` on main after merge.

Then the fresh-context review of the whole branch diff (the tasks skill's code-review requirement), and `tasks done ai-bc49ed "<what landed>"` in the landing commit.
