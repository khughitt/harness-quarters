"""pi/bin/pi against a fake pinned install under a temporary install root."""
import json
import os
import subprocess
from pathlib import Path

import pytest

CHECKOUT = Path(__file__).resolve().parent.parent
LAUNCHER = CHECKOUT / "pi" / "bin" / "pi"
PIN = CHECKOUT / "pi"
VERSION = json.loads((CHECKOUT / "pi" / "package.json").read_text())["dependencies"]["@earendil-works/pi-coding-agent"]

FAKE = """#!/usr/bin/env bash
printf '%s\\n' "$@"
printf 'skip=%s\\n' "${PI_SKIP_VERSION_CHECK-unset}"
"""


def run(root, *args):
    env = {**os.environ, "PI_INSTALL_ROOT": str(root)}
    env.pop("PI_SKIP_VERSION_CHECK", None)
    return subprocess.run([str(LAUNCHER), *args], env=env, capture_output=True, text=True)


@pytest.fixture
def installed(tmp_path):
    bin_dir = tmp_path / VERSION / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pi").write_text(FAKE)
    (bin_dir / "pi").chmod(0o755)
    (tmp_path / VERSION / "package-lock.json").write_bytes((PIN / "package-lock.json").read_bytes())
    return tmp_path


def test_runs_the_pinned_install_with_its_arguments(installed):
    result = run(installed, "--mode", "rpc", "a b")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["--mode", "rpc", "a b", "skip=1"]


def test_refuses_when_the_pinned_version_is_not_installed(tmp_path):
    (tmp_path / "0.0.1" / "node_modules" / ".bin").mkdir(parents=True)
    result = run(tmp_path, "--version")
    assert result.returncode == 127
    assert f"pi {VERSION} is not installed" in result.stderr
    assert "just pi-install" in result.stderr


def test_refuses_an_install_that_does_not_match_the_lock(installed):
    (installed / VERSION / "package-lock.json").write_text("{}")
    result = run(installed, "--version")
    assert result.returncode == 127
    assert "does not match pi/package-lock.json" in result.stderr
    assert "just pi-install" in result.stderr


@pytest.mark.parametrize("args", [["update"], ["update", "--force"], ["update", "self"], ["update", "pi"],
                                  ["update", "--self"], ["update", "--all"], ["update", "--models", "--all"]])
def test_refuses_updating_pi_itself(installed, args):
    result = run(installed, *args)
    assert result.returncode == 2
    assert "pi/package.json" in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("args", [["update", "--models"], ["update", "--extensions"], ["update", "npm:some-pkg"],
                                  ["update", "--extension", "npm:some-pkg"], ["--print", "update"]])
def test_passes_updates_that_leave_pi_alone(installed, args):
    result = run(installed, *args)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[:-1] == args
