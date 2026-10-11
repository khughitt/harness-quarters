"""pi/probes/rpc-probe.py cleanup: a copy of the probe beside a fake pi, stopped by a
signal or by an exception. Every process it caused must be gone before its temporary
directory is: pi, a child in pi's group, and a child in its own session, as pi's bash
tool runs commands."""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROBES = Path(__file__).resolve().parent.parent / "pi" / "probes"

# --version answers. RPC mode starts a child in its group and a detached one, records
# pid, group and both children, then either never answers (silent) or answers every
# command with an empty success and settles every prompt at once (answer), which makes
# the probe fail on the first response it reads a field from. On SIGTERM it records
# whether the probe's directory still exists, then exits, or with FAKE_PI_STUBBORN keeps
# running, so the probe's cleanup must wait for it and then kill it.
FAKE = """#!{python}
import json, os, signal, subprocess, sys
if sys.argv[1:2] == ["--version"]:
    print("1.1.0")
    sys.exit()
def on_term(*_):
    with open(os.environ["FAKE_PI_PIDS"] + ".term", "w") as out:
        out.write("present" if os.path.isdir(os.environ["PI_CODING_AGENT_DIR"]) else "gone")
    if not os.environ.get("FAKE_PI_STUBBORN"):
        os._exit(0)
signal.signal(signal.SIGTERM, on_term)
grouped = subprocess.Popen(["sleep", "300"])
detached = subprocess.Popen(["sleep", "301"], start_new_session=True)
with open(os.environ["FAKE_PI_PIDS"] + ".tmp", "w") as out:
    out.write(f"{{os.getpid()}} {{os.getpgid(0)}} {{grouped.pid}} {{detached.pid}}")
os.rename(os.environ["FAKE_PI_PIDS"] + ".tmp", os.environ["FAKE_PI_PIDS"])
for line in sys.stdin:
    if os.environ["FAKE_PI_MODE"] == "answer":
        command = json.loads(line)
        print(json.dumps({{"type": "response", "id": command["id"], "success": True, "data": {{}}}}), flush=True)
        if command["type"] == "prompt":
            print(json.dumps({{"type": "agent_settled", "aborted": False}}), flush=True)
"""


def alive(pid):
    try:
        with open(f"/proc/{pid}/stat") as handle:  # a zombie is not running
            return handle.read().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def group_gone(group, within=2.0):
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def probe(tmp_path):
    (tmp_path / "pi" / "probes").mkdir(parents=True)
    (tmp_path / "pi" / "bin").mkdir()
    for name in ("rpc-probe.py", "mcp-probe-server.py"):
        shutil.copy(PROBES / name, tmp_path / "pi" / "probes" / name)
    fake = tmp_path / "pi" / "bin" / "pi"
    fake.write_text(FAKE.format(python=sys.executable))
    fake.chmod(0o755)
    return tmp_path


def start(probe, tmp_path, mode, stubborn=False):
    pids, scratch = tmp_path / "pids", tmp_path / "scratch"
    scratch.mkdir()
    env = {**os.environ, "FAKE_PI_PIDS": str(pids), "FAKE_PI_MODE": mode, "TMPDIR": str(scratch)}
    if stubborn:
        env["FAKE_PI_STUBBORN"] = "1"
    run = subprocess.Popen([sys.executable, str(probe / "pi" / "probes" / "rpc-probe.py")], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    deadline = time.monotonic() + 10
    while not pids.exists():
        assert time.monotonic() < deadline, "the fake pi never started"
        time.sleep(0.05)
    return run, scratch, [int(n) for n in pids.read_text().split()]


def assert_cleaned(run, scratch, pids, tmp_path):
    pid, group, grouped, detached = pids
    assert run.returncode != 0
    assert (tmp_path / "pids.term").read_text() == "present", "the directory went before pi was stopped"
    assert not alive(pid), "pi outlived the probe"
    assert not alive(grouped), "a child in pi's group outlived the probe"
    assert not alive(detached), "a detached child outlived the probe"
    assert group_gone(group)
    assert list(scratch.iterdir()) == [], "the temporary directory was left behind"


def reap(run, tmp_path):
    if run.poll() is None:
        os.killpg(run.pid, signal.SIGKILL)
        run.wait()
    pids = tmp_path / "pids"
    if pids.exists():
        numbers = [int(n) for n in pids.read_text().split()]
        for p in (numbers[0], *numbers[2:]):
            if alive(p):
                os.kill(p, signal.SIGKILL)


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT])
def test_a_signalled_probe_stops_what_it_started_before_removing_its_directory(probe, tmp_path, sig):
    run, scratch, pids = start(probe, tmp_path, "silent")
    try:
        run.send_signal(sig)
        run.wait(20)
        assert_cleaned(run, scratch, pids, tmp_path)
    finally:
        reap(run, tmp_path)


def test_a_second_signal_during_cleanup_does_not_cut_it_short(probe, tmp_path):
    run, scratch, pids = start(probe, tmp_path, "silent", stubborn=True)
    try:
        run.send_signal(signal.SIGINT)
        deadline = time.monotonic() + 5
        while not (tmp_path / "pids.term").exists():  # cleanup is now waiting on pi
            assert time.monotonic() < deadline, "cleanup never signalled pi"
            time.sleep(0.05)
        run.send_signal(signal.SIGINT)
        run.wait(30)
        assert_cleaned(run, scratch, pids, tmp_path)
    finally:
        reap(run, tmp_path)


def test_a_failing_probe_stops_what_it_started_before_removing_its_directory(probe, tmp_path):
    run, scratch, pids = start(probe, tmp_path, "answer")
    try:
        run.wait(20)
        assert "KeyError" in run.stderr.read()
        assert_cleaned(run, scratch, pids, tmp_path)
    finally:
        reap(run, tmp_path)
