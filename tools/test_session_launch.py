"""Check the executable launchers with local substitutes for the two leaf commands."""

import os
import subprocess
from pathlib import Path

import pytest

from test_worker_defaults import agy_installed, installed  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("tool", ["agy", "pi"])
@pytest.mark.parametrize("setting", ["0", "1", "typo"])
def test_session_launcher_routes_only_when_enabled(request, tmp_path, tool, setting):
    env = request.getfixturevalue("agy_installed" if tool == "agy" else "installed")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "scoped"
    budget = bin_dir / "host-budget"
    budget.write_text('#!/bin/sh\n[ "$1" = session ] && [ "$2" = -- ] || exit 9\n'
                      'shift 2\nprintf "%s\\n" "$@" > "$LAUNCH_TRACE"\nexec "$@"\n')
    budget.chmod(0o755)
    env.update(PATH=f"{bin_dir}:{os.environ['PATH']}", HOSTKIT_AGENT_SESSIONS=setting,
               LAUNCH_TRACE=str(marker), CARGO_BUILD_JOBS="9")
    command = [str(ROOT / "harnesses" / tool / "bin" / tool), "${HOME}", "a b"]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
    if setting == "typo":
        assert result.returncode == 2
        assert "HOSTKIT_AGENT_SESSIONS" in result.stderr
        assert not marker.exists()
        return
    assert result.returncode == 0, result.stderr
    assert "CARGO_BUILD_JOBS=9" in result.stdout
    assert marker.exists() == (setting == "1")
    if setting == "1":
        assert marker.read_text().splitlines()[-2:] == ["${HOME}", "a b"]
        budget.write_text("#!/bin/sh\nexit 7\n")
        failed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        assert failed.returncode == 7
        assert failed.stdout == ""
