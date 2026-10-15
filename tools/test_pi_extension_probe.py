"""Exercise the extension's event contract with real child processes, without pi or an API."""
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "pi" / "extensions" / "harness-state.ts"
DRIVER = r'''
const { default: extension } = await import(process.env.EXTENSION);
const handlers = {}, warnings = [];
extension({ on(name, handler) { handlers[name] = handler; } });
const ctx = { ui: { notify(message, level) { warnings.push({message, level}); } } };
for (const event of JSON.parse(process.env.EVENTS)) {
  if (typeof event === "number") await new Promise(resolve => setTimeout(resolve, event));
  else await handlers[event]({}, ctx);
}
await handlers.session_shutdown({}, ctx);
console.log(JSON.stringify(warnings));
'''


def run_extension(tmp_path, body, events):
    stub = tmp_path / "refresh"
    stub.write_text("#!/usr/bin/env python3\n" + body)
    stub.chmod(0o755)
    log = tmp_path / "calls"
    env = {**os.environ, "EXTENSION": str(EXTENSION), "EVENTS": json.dumps(events),
           "HQ_HARNESS_STATE_REFRESH": str(stub), "LOG": str(log)}
    done = subprocess.run(["node", "--input-type=module", "-e", DRIVER], env=env,
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout), [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_shutdown_waits_for_refresh_with_closed_empty_stdin(tmp_path):
    warnings, calls = run_extension(tmp_path, '''import json, os, sys, time
assert sys.stdin.read() == ""
time.sleep(0.05)
print("captured stdout")
print("captured stderr", file=sys.stderr)
with open(os.environ["LOG"], "a") as out: out.write(json.dumps("done") + "\\n")
''', [])
    assert calls == ["done"]
    assert warnings == []


def test_events_coalesce_and_shutdown_replaces_pending_rerun(tmp_path):
    warnings, calls = run_extension(tmp_path, '''import json, os, time
with open(os.environ["LOG"], "a") as out: out.write(json.dumps("start") + "\\n")
time.sleep(0.1)
with open(os.environ["LOG"], "a") as out: out.write(json.dumps("end") + "\\n")
''', ["model_select", "thinking_level_select", "agent_settled", "agent_settled"])
    assert calls == ["start", "end", "start", "end"]
    assert warnings == []


def test_failure_warns_once_without_failing_pi_or_skipping_final_run(tmp_path):
    warnings, calls = run_extension(tmp_path, '''import json, os, sys
with open(os.environ["LOG"], "a") as out: out.write(json.dumps("failed") + "\\n")
print("stub refused", file=sys.stderr)
sys.exit(7)
''', ["agent_settled", "model_select"])
    assert calls == ["failed", "failed"]
    assert len(warnings) == 1
    assert warnings[0]["level"] == "warning"
    assert "7" in warnings[0]["message"]
    assert "stub refused" in warnings[0]["message"]


@pytest.mark.parametrize("command", ["missing", ""])
def test_invalid_command_warns_once_and_does_not_fail_pi(tmp_path, command):
    env = {**os.environ, "EXTENSION": str(EXTENSION), "EVENTS": '["agent_settled"]',
           "HQ_HARNESS_STATE_REFRESH": str(tmp_path / command) if command else ""}
    done = subprocess.run(["node", "--input-type=module", "-e", DRIVER], env=env,
                          capture_output=True, text=True, timeout=10)
    assert done.returncode == 0, done.stderr
    warnings = json.loads(done.stdout)
    assert len(warnings) == 1
    assert warnings[0]["level"] == "warning"
    assert ("ENOENT" if command else "empty") in warnings[0]["message"]


def test_requests_during_a_run_schedule_just_one_serial_rerun(tmp_path):
    warnings, calls = run_extension(tmp_path, '''import json, os, time
with open(os.environ["LOG"], "a") as out: out.write(json.dumps("start") + "\\n")
time.sleep(0.05)
with open(os.environ["LOG"], "a") as out: out.write(json.dumps("end") + "\\n")
''', ["agent_settled", "agent_settled", "agent_settled", 400])
    assert calls == ["start", "end", "start", "end", "start", "end"]
    assert warnings == []


def test_default_command_resolves_in_scratch_home(tmp_path):
    command = tmp_path / ".local" / "bin" / "harness-state-refresh"
    command.parent.mkdir(parents=True)
    log = tmp_path / "calls"
    command.write_text("#!/usr/bin/env python3\nimport os\nfrom pathlib import Path\nPath(os.environ['LOG']).write_text('done')\n")
    command.chmod(0o755)
    env = {**os.environ, "HOME": str(tmp_path), "EXTENSION": str(EXTENSION), "EVENTS": "[]", "LOG": str(log)}
    env.pop("HQ_HARNESS_STATE_REFRESH", None)
    done = subprocess.run(["node", "--input-type=module", "-e", DRIVER], env=env,
                          capture_output=True, text=True, timeout=10)
    assert done.returncode == 0, done.stderr
    assert log.read_text() == "done"
    assert json.loads(done.stdout) == []


@pytest.fixture
def reap_refresh_groups(tmp_path):
    """Adopt the stub's orphaned descendants so failed assertions still kill and reap them."""
    import ctypes
    import signal

    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    try:
        yield
    finally:
        log = tmp_path / "calls"
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        for record in calls:
            try:
                os.killpg(record["group"], signal.SIGKILL)
            except ProcessLookupError:
                pass
        for record in calls:
            try:
                os.waitpid(record["child"], 0)
            except ChildProcessError:
                pass
        assert libc.prctl(36, previous.value, 0, 0, 0) == 0


@pytest.mark.parametrize("exit_code", [0, 7])
def test_early_leader_exit_cleans_its_group_before_another_run(tmp_path, reap_refresh_groups, exit_code):
    warnings, calls = run_extension(tmp_path, '''import json, os, signal, subprocess, sys, time
from pathlib import Path
log = Path(os.environ["LOG"])
def alive(pid):
    try: return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError: return False
previous = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
ready = str(log) + f".{os.getpid()}.ready"
child = subprocess.Popen([sys.executable, "-c", "import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM, signal.SIG_IGN); Path(os.environ['READY']).touch(); time.sleep(60)"],
                         env={**os.environ, "READY": ready}, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while not Path(ready).exists(): time.sleep(0.005)
with log.open("a") as out:
    out.write(json.dumps({"pid": os.getpid(), "group": os.getpgrp(), "child": child.pid,
                          "previous_alive": any(alive(r["child"]) for r in previous)}) + "\\n")
sys.exit(''' + str(exit_code) + ''')
''', ["agent_settled", "agent_settled"])
    assert len(calls) == 2
    assert [record["previous_alive"] for record in calls] == [False, False], calls
    surviving = []
    for record in calls:
        state = Path(f"/proc/{record['child']}/stat")
        if state.exists() and state.read_text().rsplit(")", 1)[1].split()[0] != "Z":
            surviving.append(record["child"])
    assert surviving == [], surviving
    assert len(warnings) <= 1
    if exit_code:
        assert "7" in warnings[0]["message"]
