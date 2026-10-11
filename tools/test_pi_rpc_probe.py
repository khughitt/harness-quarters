"""pi/probes/rpc-probe.py cleanup: a copy of the probe beside a fake pi whose RPC mode
never answers, interrupted while it waits. Every process it started must be gone before
its temporary directory is."""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROBES = Path(__file__).resolve().parent.parent / "pi" / "probes"

# --version answers; RPC mode records its pid and process group, leaves a grandchild in
# the group, and never reads a command.
FAKE = """#!/usr/bin/env bash
if [[ ${1-} == --version ]]; then echo 1.1.0; exit 0; fi
sleep 300 &
echo "$$ $(ps -o pgid= $$ | tr -d ' ') $!" > "$FAKE_PI_PIDS"
wait
"""


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    with open(f"/proc/{pid}/stat") as handle:  # a zombie is not running
        return handle.read().rsplit(")", 1)[1].split()[0] != "Z"


@pytest.fixture
def probe(tmp_path):
    (tmp_path / "pi" / "probes").mkdir(parents=True)
    (tmp_path / "pi" / "bin").mkdir()
    for name in ("rpc-probe.py", "mcp-probe-server.py"):
        shutil.copy(PROBES / name, tmp_path / "pi" / "probes" / name)
    fake = tmp_path / "pi" / "bin" / "pi"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    return tmp_path


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_an_interrupted_probe_stops_pi_before_removing_its_directory(probe, tmp_path, sig):
    pids = tmp_path / "pids"
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = {**os.environ, "FAKE_PI_PIDS": str(pids), "TMPDIR": str(scratch)}
    run = subprocess.Popen([sys.executable, str(probe / "pi" / "probes" / "rpc-probe.py")], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while not (pids.exists() and len(pids.read_text().split()) == 3):
            assert time.monotonic() < deadline, "the fake pi never started"
            time.sleep(0.05)
        pid, group, grandchild = map(int, pids.read_text().split())
        run.send_signal(sig)
        run.wait(15)
        assert run.returncode != 0
        assert not alive(pid) and not alive(grandchild), "pi outlived the probe"
        with pytest.raises(ProcessLookupError):
            os.killpg(group, 0)
        assert list(scratch.iterdir()) == [], "the temporary directory was left behind"
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
        if pids.exists():
            for p in map(int, pids.read_text().split()[::2]):
                if alive(p):
                    os.kill(p, signal.SIGKILL)
