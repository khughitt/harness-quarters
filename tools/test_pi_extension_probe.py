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
