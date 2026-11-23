"""Exercise the opt-in Stop bridge with relay and isolated guard state."""
import ctypes
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys

import pytest

from hook_routes import relay_runtime
from hook_routes.render import render_candidate
from hook_routes.table import load

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "harnesses/agy/hook"
CORPUS = Path(__file__).with_name("fixtures") / "agy-bridge"
CASES = json.loads((CORPUS / "cases.json").read_bytes())
EXEMPT = sorted({json.loads(case["native"])["terminationReason"] for case in CASES
                 if case["id"].startswith("agy-own-end-") and case["expected"][1] == "allow"})


@pytest.fixture
def runtime():
    table = load(ROOT / "harnesses/hook-routes.toml")
    version = "v0.5.0"
    if install := os.environ.get("HQ_TEST_RELAY_ROOT"):
        script = Path(install) / version / "node_modules/relay/bin/relay.js"
        table.runtimes[version] = replace(table.runtimes[version], script=str(script))
    return relay_runtime.package_for(table, version, Path.home())


@pytest.fixture
def sandbox(tmp_path):
    home, workspace, private_bin = (tmp_path / name for name in ("home", "workspace", "bin"))
    for path in (home, workspace, private_bin):
        assert path.resolve().is_relative_to(tmp_path.resolve())
        path.mkdir()
    (private_bin / "python3").symlink_to(sys.executable)
    env = {"PATH": str(private_bin), "HOME": str(home),
           "XDG_CONFIG_HOME": str(home / ".config"), "XDG_STATE_HOME": str(home / ".local/state"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    return workspace, env


def stub(sandbox, body):
    workspace, env = sandbox
    path = Path(env["PATH"]) / "tasks"
    path.write_text(f"#!{sys.executable}\nimport json, sys\n"
                    "assert sys.argv[1:] == ['hook', 'claim-guard']\n"
                    "request = json.load(sys.stdin)\n"
                    "assert request['schema'] == 2 and request['event']['nativeEvent'] == 'Stop'\n"
                    "assert request['event']['harness'] == 'agy'\n"
                    f"open({str(workspace / 'invoked')!r}, 'w').close()\n" + body + "\n")
    path.chmod(0o700)


def invoke(runtime, sandbox, payload, *, command=None):
    workspace, env = sandbox
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    if command is None:
        command = [HOOK, "Stop", "--runtime", runtime, "--guard", "tasks hook claim-guard"]
    result = subprocess.run(command,
                            input=raw, cwd=workspace, env=env, capture_output=True, timeout=35)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_guard_deny_becomes_continue(runtime, sandbox):
    stub(sandbox, """print(json.dumps({"decision":"deny","reason":"held claim"}))""")
    assert invoke(runtime, sandbox, {"executionNum": 1}) == {"decision": "continue", "reason": "held claim"}


def test_guard_allow_becomes_empty(runtime, sandbox):
    stub(sandbox, """print('{"decision":"allow"}')""")
    assert invoke(runtime, sandbox, {"executionNum": 0}) == {}


def test_rendered_stop_bridge_invokes_declared_guard(runtime, sandbox):
    workspace, env = sandbox
    table = load(ROOT / "harnesses/hook-routes.toml")
    agy = table.homes["agy"]
    index = next(i for i, b in enumerate(agy.bindings) if b.event == "Stop" and
                 any("claim-guard" in line.policies for line in b.lines))
    # Render against the runtime declared for this home, which is test-owned.
    table.runtimes["v0.5.0"] = replace(table.runtimes["v0.5.0"], script=str(runtime / "bin/relay.js"))
    command = shlex.quote(str(HOOK))
    candidate = workspace / "candidate.toml"
    candidate.write_text(f'''[[moves]]
home = "agy"
binding = {index}
[[moves.lines]]
policies = ["claim-guard", "agy-healing"]
runtime = "v0.5.0"
delegates = [["tasks","hook","claim-guard"]]
command = {json.dumps(command)}
[moves.lines.states.claim-guard]
state = "bridge"
evidence = "fixture"
[moves.lines.states.agy-healing]
state = "bridge"
evidence = "fixture"
''')
    rendered = render_candidate(table, candidate, Path(env["HOME"]))
    def guard_argv(image):
        [entry] = [line for line in json.loads(image[agy.path])["hq"]["Stop"] if "--guard" in line["command"]]
        return shlex.split(entry["command"])

    argv = guard_argv(rendered)
    assert argv == [str(HOOK), "Stop", "--runtime", str(runtime), "--guard", "tasks hook claim-guard"]
    stub(sandbox, """print('{"decision":"deny","reason":"held claim"}')""")
    assert invoke(runtime, sandbox, {}, command=argv) == {
        "decision": "continue", "reason": "held claim"}
    moved = workspace / "updated runtime"
    table.runtimes["v0.5.0"] = replace(table.runtimes["v0.5.0"], script=str(moved / "bin/relay.js"))
    candidate.write_text(candidate.read_text().replace('"tasks","hook"', '"fixture-tasks","hook"'))
    changed = render_candidate(table, candidate, Path(env["HOME"]))
    assert guard_argv(changed) == [str(HOOK), "Stop", "--runtime", str(moved),
                                   "--guard", "fixture-tasks hook claim-guard"]


def test_stop_escape_cancel_invalid_count_owner_missing(runtime, sandbox):
    assert invoke(runtime, sandbox, {"terminationReason": "USER_CANCELED", "executionNum": "x"}) == {}


def test_stop_escape_cancel_missing_count_timeout(runtime, sandbox):
    stub(sandbox, "import time\ntime.sleep(30)")
    assert invoke(runtime, sandbox, {"terminationReason": "USER_CANCELED"}) == {}
    assert (sandbox[0] / "invoked").exists()


@pytest.mark.parametrize("reason", EXEMPT)
def test_stop_escape_each_reason_malformed_reply(runtime, sandbox, reason):
    stub(sandbox, "print('invalid')")
    assert invoke(runtime, sandbox, {"terminationReason": reason, "executionNum": 0}) == {}
    assert (sandbox[0] / "invoked").exists()


@pytest.mark.parametrize("count", [1, 1.0, 9007199254740991])
def test_stop_escape_refire_owner_nonzero(runtime, sandbox, count):
    stub(sandbox, "sys.exit(7)")
    assert invoke(runtime, sandbox, {"executionNum": count, "terminationReason": {}}) == {}
    assert (sandbox[0] / "invoked").exists()


@pytest.mark.parametrize("count", [0, True, 0.5, -1, 9007199254740992])
def test_stop_failure_without_exemption_continues(runtime, sandbox, count):
    reply = invoke(runtime, sandbox, {"executionNum": count})
    assert reply["decision"] == "continue"
    assert "tasks" in reply["reason"] and len(reply["reason"].splitlines()) == 1


def test_stop_failure_names_bad_reply(runtime, sandbox):
    stub(sandbox, """print('{"decision":"deny"}')""")
    reply = invoke(runtime, sandbox, {"executionNum": 0})
    assert reply["decision"] == "continue" and "reason" in reply["reason"]


def test_stop_nonexecutable_guard_continues(runtime, sandbox):
    path = Path(sandbox[1]["PATH"]) / "tasks"
    path.touch(mode=0o600)
    reply = invoke(runtime, sandbox, {"executionNum": 0})
    assert reply["decision"] == "continue" and "tasks" in reply["reason"]


@pytest.mark.parametrize("raw", [b"", b"[]", b'{"extra":"\xff"}', b" " * (4 * 1024 * 1024) + b"{}"],
                         ids=["empty", "array", "invalid-utf8", "too-large"])
def test_unreadable_stop_continues(runtime, sandbox, raw):
    stub(sandbox, """print('{"decision":"allow"}')""")
    reply = invoke(runtime, sandbox, raw)
    assert reply["decision"] == "continue" and reply["reason"]
    assert not (sandbox[0] / "invoked").exists()


def test_stop_projection_failure_preserves_refire(sandbox):
    assert invoke(sandbox[0] / "missing-runtime", sandbox, {"executionNum": 1}) == {}


@pytest.mark.parametrize(("fields", "inner", "exempt"), [
    (b'"terminationReason":"USER_CANCELED","executionNum":"unknown"', b'{"text":"[}"}', True),
    (b'"executionNum":1.0', b'false', True),
    (b'"executionNum":9007199254740992', b'null', False),
    (b'"executionNum":1', b'false,', False),
    (b'"executionNum":1', b'NaN', False),
])
def test_deep_metadata_with_unavailable_projection(sandbox, fields, inner, exempt):
    nested = b'[' * 1800 + inner + b']' * 1800
    raw = b'{"metadata":' + nested + b',' + fields + b'}'
    reply = invoke(sandbox[0] / "absent-runtime", sandbox, raw)
    if exempt:
        assert reply == {}
    else:
        assert reply["decision"] == "continue"


def test_escape_when_json_decoder_reaches_its_nesting_limit(monkeypatch):
    escape = runpy.run_path(str(HOOK))["_owner_failure_exempt"]
    original = json.loads

    def limited(text, **kwargs):
        if "[" * 128 in text:
            raise RecursionError("JSON decoder depth exceeded")
        return original(text, **kwargs)

    monkeypatch.setattr(json, "loads", limited)
    raw = '{"executionNum":1,"metadata":' + "[" * 600 + "null" + "]" * 600 + "}"
    assert escape(raw)
    assert not escape(raw.replace("null", "null,"))


@pytest.mark.parametrize("marks", [1, 2])
def test_stop_bom_matches_relay(runtime, sandbox, marks):
    stub(sandbox, """print('{"decision":"allow"}')""")
    raw = b"\xef\xbb\xbf" * marks + b'{"executionNum":1}'
    reply = invoke(runtime, sandbox, raw)
    assert (sandbox[0] / "invoked").exists() == (marks == 1)
    assert (reply == {}) == (marks == 1)


def test_escape_reasons_match_tasks_corpus():
    manifest = json.loads((CORPUS / "manifest.json").read_bytes())
    assert sha256((CORPUS / "cases.json").read_bytes()).hexdigest() == manifest["cases_sha256"]
    assert manifest["case_count"] == len(CASES)
    assert runpy.run_path(str(HOOK))["NON_BLOCKING_REASONS"] == set(EXEMPT)


def write_owner_state(case, workspace, env):
    home = Path(env["HOME"])
    registry = Path(env["XDG_CONFIG_HOME"]) / "tasks/projects.toml"
    store = Path(env["XDG_STATE_HOME"]) / "tasks/claims/sci.toml"
    facts = home / ".agents/bin/harness-facts"
    for target in (registry, store, facts):
        assert target.resolve().is_relative_to(home)
        target.parent.mkdir(parents=True)
    registry.write_text("broken [toml" if case.get("broken_registry") else
                        f'[projects]\nsci = {json.dumps(str(workspace))}\n')
    if case["claims"] != "none":
        session = {"own": "agy:actor", "cross": "codex:actor"}[case["claims"]]
        pid_view = Path("/proc/self/ns/pid").stat()
        start = Path("/proc/self/stat").read_text().rsplit(") ", 1)[1].split()[19]
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        claim = dict(owner="fixture", session=session, host="fixture", worktree=str(workspace),
                     pid=os.getpid(), pid_start=int(start), boot_id=boot,
                     pid_view=f"{pid_view.st_dev}:{pid_view.st_ino}",
                     started="2026-11-15T00:00:00Z", seen="2026-11-15T00:00:00Z")
        store.write_text('[claims."sci-000001"]\n' + "".join(f"{k} = {json.dumps(v)}\n" for k, v in claim.items()))
    entries = {}
    for name, key, kind in (("controller-wake", "wake", "boolean"), ("controller-wake-kinds", "kinds", "set"),
                            ("stop-input-in-flight-statuses", "statuses", "set")):
        entries[name] = {"type": kind, "harness": {"agy": {"type": kind, "status": "probed", "value": case[key]}}}
    view = {"schema": 1, "harnesses": ["agy"], "facts": entries}
    facts.write_text(f"#!{sys.executable}\nprint({json.dumps(view)!r})\n")
    facts.chmod(0o700)


@pytest.fixture
def owner(sandbox):
    binary = shutil.which("tasks")
    if binary is None:
        pytest.skip("tasks owner command is absent")
    workspace, env = sandbox
    (Path(env["PATH"]) / "tasks").symlink_to(Path(binary).resolve())
    return workspace, env


def test_owner_timeout_reaps_facts_reader_and_child(runtime, owner):
    workspace, env = owner
    case = next(case for case in CASES if case["id"] == "agy-own")
    write_owner_state(case, workspace, env)
    reader = Path(env["HOME"]) / ".agents/bin/harness-facts"
    marker = workspace / "facts-pids"
    release = workspace / "release"
    child_code = (f"from pathlib import Path\nimport time\nend = time.monotonic() + 15\n"
                  f"while not Path({str(release)!r}).exists() and time.monotonic() < end: time.sleep(0.02)")
    reader.write_text(f"""#!{sys.executable}
import json, os, subprocess, sys
from pathlib import Path
env = {{key: os.environ[key] for key in ("HOME", "PATH")}}
with subprocess.Popen([sys.executable, "-c", {child_code!r}], env=env) as child:
    Path({str(marker)!r}).write_text(json.dumps([os.getpid(), os.getpgrp(), child.pid]))
""")
    # The test adopts only fixture descendants if a cleanup regression occurs.
    libc = ctypes.CDLL(None, use_errno=True)
    original = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(original), 0, 0, 0) == 0  # PR_GET_CHILD_SUBREAPER
    assert libc.prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER
    try:
        native = case["native"].replace("$CWD", json.dumps(str(workspace))[1:-1]).encode()
        reply = invoke(runtime, owner, native)
        assert reply["decision"] == "continue" and "timed out" in reply["reason"]
        reader_pid, group, child_pid = json.loads(marker.read_text())
        assert group == reader_pid
        for pid in (reader_pid, child_pid):
            assert not Path(f"/proc/{pid}").exists(), f"owned facts process {pid} remains after Stop"
    finally:
        release.touch()
        if marker.exists():
            reader_pid, _, child_pid = json.loads(marker.read_text())
            for pid in (reader_pid, child_pid):
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
        assert libc.prctl(36, original.value, 0, 0, 0) == 0


def test_held_claim_check_repeats_when_agy_becomes_idle(runtime, owner):
    case = next(case for case in CASES if case["id"] == "agy-busy")
    write_owner_state(case, *owner)
    event = json.loads(case["native"].replace("$CWD", str(owner[0])))
    assert invoke(runtime, owner, event) == {}
    event["fullyIdle"] = True
    reply = invoke(runtime, owner, event)
    assert reply["decision"] == "continue" and "sci-000001" in reply["reason"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_bridge_replays_tasks_agy_stop_corpus(runtime, owner, case):
    workspace, env = owner
    write_owner_state(case, workspace, env)
    native = case["native"].replace("$CWD", json.dumps(str(workspace))[1:-1]).encode()
    reply = invoke(runtime, owner, native)
    if case.get("decoder_reject"):
        assert reply["decision"] == "continue" and "project" in reply["reason"]
    elif case["expected"][1] == "allow":
        assert reply == {}
    else:
        assert reply["decision"] == "continue" and reply["reason"]
        assert "owner: tasks" in reply["reason"] or "executionNum" in reply["reason"] or "conversationId" in reply["reason"]
        if "contains" in case:
            assert case["contains"] in reply["reason"]
