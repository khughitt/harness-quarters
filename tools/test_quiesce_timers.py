"""quiesce-timers against a fake systemctl that keeps unit state in a JSON file."""
import json
import os
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent / "quiesce-timers"

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
path = os.environ["FAKE_SYSTEMD"]
state = json.load(open(path))
args = sys.argv[1:]
assert args[0] == "--user", args
verb, unit = args[1], args[-1]
state["log"].append(" ".join(args[1:]))
units = state["units"]
code = 0
if unit not in units:
    print(f"Failed to get unit file state for {unit}: No such file or directory", file=sys.stderr)
    code = 1
else:
    u = units[unit]
    if verb == "is-enabled":
        print(u["enabled"])
        code = 0 if u["enabled"] == "enabled" else 1
    elif verb == "is-active":
        if u.get("runs_for", 0) > 0:
            u["runs_for"] -= 1
            print("active")
        else:
            u["active"] = "inactive" if "runs_for" in u else u["active"]
            print(u["active"])
            code = 0 if u["active"] == "active" else 3
    elif verb == "show":
        print(u["unit"])
    elif verb in ("start", "stop"):
        u["active"] = "active" if verb == "start" else "inactive"
    else:
        code = 1
json.dump(state, open(path, "w"))
sys.exit(code)
'''


@pytest.fixture
def systemd(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "systemctl").write_text(FAKE)
    (bin_ / "systemctl").chmod(0o755)
    path = tmp_path / "units.json"
    units = {
        "obs-index.timer": {"enabled": "enabled", "active": "active", "unit": "obs-index.service"},
        "obs-index.service": {"enabled": "static", "active": "inactive", "unit": ""},
        "prune.timer": {"enabled": "linked", "active": "inactive", "unit": "prune.service"},
        "prune.service": {"enabled": "linked", "active": "inactive", "unit": ""},
    }
    path.write_text(json.dumps({"units": units, "log": []}))

    class Systemd:
        state_file = tmp_path / "window" / "timers.json"

        def run(self, *args, check=True):
            env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "FAKE_SYSTEMD": str(path)}
            result = subprocess.run([str(TOOL), *args], text=True, capture_output=True, env=env)
            if check and result.returncode != 0:
                raise AssertionError(result.stdout + result.stderr)
            return result

        def units(self):
            return json.loads(path.read_text())["units"]

        def log(self):
            return json.loads(path.read_text())["log"]

        def set(self, unit, **fields):
            data = json.loads(path.read_text())
            data["units"][unit].update(fields)
            path.write_text(json.dumps(data))

    return Systemd()


def test_record_saves_each_timers_enablement_activity_and_service(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "prune.timer")
    assert json.loads(systemd.state_file.read_text())["timers"] == [
        {"timer": "obs-index.timer", "service": "obs-index.service", "enabled": "enabled", "active": "active"},
        {"timer": "prune.timer", "service": "prune.service", "enabled": "linked", "active": "inactive"},
    ]


def test_record_refuses_an_existing_record(systemd):
    systemd.state_file.parent.mkdir()
    systemd.state_file.write_text("{}")
    result = systemd.run("record", "--state", systemd.state_file, "obs-index.timer", check=False)
    assert result.returncode == 1 and "exists" in result.stderr
    assert systemd.state_file.read_text() == "{}"


def test_record_refuses_a_timer_systemd_does_not_know(systemd):
    result = systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "gone.timer", check=False)
    assert result.returncode == 1 and "gone.timer" in result.stderr
    assert not systemd.state_file.exists()


def test_record_refuses_a_unit_that_is_not_a_timer(systemd):
    result = systemd.run("record", "--state", systemd.state_file, "obs-index.service", check=False)
    assert result.returncode == 1 and "not a timer" in result.stderr


def test_stop_stops_every_recorded_timer(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "prune.timer")
    systemd.run("stop", "--state", systemd.state_file)
    assert systemd.units()["obs-index.timer"]["active"] == "inactive"
    assert "stop obs-index.timer" in systemd.log() and "stop prune.timer" in systemd.log()


def test_wait_returns_once_a_running_service_finishes(systemd):
    systemd.set("obs-index.service", active="active", runs_for=2)
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer")
    result = systemd.run("wait", "--state", systemd.state_file, "--timeout", "60", "--poll", "0")
    assert "waiting on obs-index.service" in result.stdout and "every service is inactive" in result.stdout
    assert not [line for line in systemd.log() if "obs-index.service" in line and line.split()[0] in ("stop", "kill")]


def test_wait_stops_at_the_timeout_and_kills_nothing(systemd):
    systemd.set("obs-index.service", active="active", runs_for=1000)
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer")
    result = systemd.run("wait", "--state", systemd.state_file, "--timeout", "0", "--poll", "0", check=False)
    assert result.returncode == 1
    assert "obs-index.service" in result.stderr and "nothing was killed" in result.stderr
    assert not [line for line in systemd.log() if line.split()[0] in ("stop", "kill")]


def test_restore_returns_each_timer_to_its_record(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "prune.timer")
    systemd.run("stop", "--state", systemd.state_file)
    result = systemd.run("restore", "--state", systemd.state_file)
    units = systemd.units()
    assert units["obs-index.timer"]["active"] == "active" and units["prune.timer"]["active"] == "inactive"
    assert "start prune.timer" not in systemd.log()
    assert "every timer matches its record" in result.stdout


def test_restore_reports_a_timer_whose_enablement_changed(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer")
    systemd.run("stop", "--state", systemd.state_file)
    systemd.set("obs-index.timer", enabled="disabled")
    result = systemd.run("restore", "--state", systemd.state_file, check=False)
    assert result.returncode == 1
    assert "obs-index.timer is disabled, active; recorded enabled, active" in result.stderr
